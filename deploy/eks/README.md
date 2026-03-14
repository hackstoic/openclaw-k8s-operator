# EKS Deployment

This directory contains the AWS EKS manifests used to bootstrap an OpenClaw
deployment with:

- AWS ALB ingress
- EBS `gp3` persistent storage
- OpenClaw gateway dashboard exposed at the public domain
- ClawPort disabled
- MemOS left enabled by default

The steps below describe the deployment shape currently used for the
`openclaw.claw-farm.com` environment, but use placeholder values where you
should substitute your own AWS account, certificate, host name, and secrets.

## Files

- `auto-ebs-gp3.yaml` - EBS `StorageClass` for EKS Auto Mode clusters
- `openclaw-alb-class.yaml` - `IngressClassParams` and `IngressClass` for AWS ALB

## Prerequisites

- An EKS cluster running Kubernetes 1.28+
- The OpenClaw operator installed in the cluster
- EKS ALB support available in the cluster
- An ACM certificate for your public host name
- A namespace for the OpenClaw instance, for example `openclaw`
- A secret containing your provider API keys

## 1. Create the namespace

```bash
kubectl create namespace openclaw
```

## 2. Create the storage class

If you are using EKS Auto Mode, apply the provided `gp3` storage class:

```bash
kubectl apply -f deploy/eks/auto-ebs-gp3.yaml
```

If you are not using EKS Auto Mode, create or reuse a different `StorageClass`
and update the instance manifest to point at that class instead of
`auto-ebs-gp3`.

## 3. Create the ALB ingress class

Edit `deploy/eks/openclaw-alb-class.yaml` before applying it:

- replace the ACM certificate ARN
- adjust the namespace selector if you do not deploy into `openclaw`

For multi-instance HTTPS, use a wildcard ACM certificate such as
`*.example.com` so new instance hosts can be added without minting a new
certificate for every deployment.

Then apply it:

```bash
kubectl apply -f deploy/eks/openclaw-alb-class.yaml
```

## 4. Create the provider secret

Create a secret in the same namespace as the instance. Example:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: xai-provider-keys
  namespace: openclaw
type: Opaque
stringData:
  XAI_API_KEY: xai-...
```

Apply it with:

```bash
kubectl apply -f xai-provider-keys.yaml
```

## 5. Deploy the OpenClaw instance

Use an `OpenClawInstance` like the following:

```yaml
apiVersion: openclaw.rocks/v1alpha1
kind: OpenClawInstance
metadata:
  name: xai-assistant
  namespace: openclaw
spec:
  clawport:
    enabled: false
  memos:
    enabled: true

  envFrom:
    - secretRef:
        name: xai-provider-keys

  config:
    raw:
      agents:
        defaults:
          model:
            primary: "xai/grok-4-1-fast-reasoning"
      models:
        mode: "merge"
        providers:
          xai:
            api: "openai-completions"
            apiKey: "${XAI_API_KEY}"
            baseUrl: "https://api.x.ai/v1"
            models:
              - id: "grok-4-1-fast-reasoning"
                name: "Grok 4.1 Fast Reasoning"
                reasoning: true
                input:
                  - "text"
                contextWindow: 200000
                maxTokens: 8192

  storage:
    persistence:
      enabled: true
      storageClass: auto-ebs-gp3
      size: 10Gi

  networking:
    service:
      type: ClusterIP
    ingress:
      enabled: true
      className: openclaw-alb
      annotations:
        alb.ingress.kubernetes.io/scheme: internet-facing
        alb.ingress.kubernetes.io/target-type: ip
        alb.ingress.kubernetes.io/listen-ports: '[{"HTTP":80},{"HTTPS":443}]'
        alb.ingress.kubernetes.io/ssl-redirect: "443"
        alb.ingress.kubernetes.io/load-balancer-attributes: idle_timeout.timeout_seconds=3600
        alb.ingress.kubernetes.io/healthcheck-path: /healthz
      hosts:
        - host: openclaw.example.com
          paths:
            - path: /
              pathType: Prefix
              port: 18789
      tls:
        - hosts:
            - openclaw.example.com
```

Apply it with:

```bash
kubectl apply -f xai-assistant.yaml
```

To launch two instances with separate domains, start from
`deploy/eks/two-openclaw-instances.example.yaml`, replace the two example hosts
with domains covered by your ACM certificate, then apply it:

```bash
kubectl apply -f deploy/eks/two-openclaw-instances.example.yaml
```

After both instances reconcile, print the domains and gateway tokens with:

```bash
make instance-access OPENCLAW_NAMESPACE=openclaw
```

For a quick smoke test without extending your ACM certificate first, remove the
`tls` blocks and switch the ALB `listen-ports` annotation to HTTP-only. The
gateway UI will still work over `http://...`, and the operator will derive the
correct Control UI origins from those HTTP hosts.

If you want a one-command flow for N instances, use:

```bash
make deploy-instances \
  OPENCLAW_NAMESPACE=openclaw \
  INSTANCE_COUNT=3 \
  INSTANCE_PREFIX=agent \
  INSTANCE_DOMAIN_TEMPLATE='{name}.claw-farm.com' \
  INSTANCE_ROUTE53_ZONE_ID=Z01850443D2JAQL992O3
```

This command:

- generates numbered instances like `agent-01`, `agent-02`, `agent-03`
- applies the CRs to the cluster
- waits for the StatefulSets and ingresses
- upserts Route53 DNS records when `INSTANCE_ROUTE53_ZONE_ID` is set
- prints each instance's domain and gateway token at the end

## Why this manifest disables ClawPort

This EKS recipe intentionally exposes the OpenClaw gateway dashboard instead of
the ClawPort sidecar.

- `spec.clawport.enabled: false` removes the ClawPort sidecar and its init job
- `paths[].port: 18789` points the ALB ingress at the gateway dashboard
- `alb.ingress.kubernetes.io/healthcheck-path: /healthz` matches the gateway
  proxy health endpoint

If you want the ALB to point back to ClawPort later, re-enable ClawPort and
either remove `paths[].port` or set it to `3000`.

## Optional: disable MemOS

MemOS is enabled by default in the current operator behavior. If you do not
want the built-in memory plugin installed, add:

```yaml
spec:
  memos:
    enabled: false
```

## Verify the deployment

Check the instance and pod health:

```bash
kubectl get openclawinstance -n openclaw
kubectl get pods -n openclaw
kubectl get svc -n openclaw xai-assistant
kubectl get ingress -n openclaw xai-assistant
make instance-access OPENCLAW_NAMESPACE=openclaw
```

Confirm the public host serves the gateway dashboard:

```bash
curl -I https://openclaw.example.com/
```

You should see a `200` response and the gateway UI HTML title `OpenClaw Control`
when fetching the full page body.

## Troubleshooting

- If the ALB stays unhealthy, make sure the ingress annotation
  `alb.ingress.kubernetes.io/healthcheck-path` is set to `/healthz`
- If the PVC does not bind, confirm that the `StorageClass` name in the
  instance matches the class installed in the cluster
- If the host resolves but returns the wrong app, verify the ingress backend
  port is `18789` and ClawPort is disabled
- If provider requests fail, confirm the API key secret exists in the same
  namespace and the key names match the config placeholders
