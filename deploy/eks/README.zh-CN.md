# EKS 部署

本目录包含用于在 AWS EKS 上引导 OpenClaw 部署的清单，包括：

- AWS ALB Ingress
- EBS `gp3` 持久化存储
- 在公网域名暴露 OpenClaw 网关仪表板
- 禁用 ClawPort
- 默认启用 MemOS

以下步骤描述当前 `openclaw.claw-farm.com` 环境使用的部署形态，但使用占位符值，你需要替换为自己的 AWS 账户、证书、主机名和密钥。

## 文件

- `auto-ebs-gp3.yaml` - EKS Auto Mode 集群的 EBS `StorageClass`
- `openclaw-alb-class.yaml` - AWS ALB 的 `IngressClassParams` 和 `IngressClass`

## 前置条件

- 运行 Kubernetes 1.28+ 的 EKS 集群
- 集群中已安装 OpenClaw Operator
- 集群中可用 EKS ALB 支持
- 公网主机名的 ACM 证书
- OpenClaw 实例的命名空间，例如 `openclaw`
- 包含提供商 API 密钥的 Secret

## 1. 创建命名空间

```bash
kubectl create namespace openclaw
```

## 2. 创建存储类

若使用 EKS Auto Mode，应用提供的 `gp3` 存储类：

```bash
kubectl apply -f deploy/eks/auto-ebs-gp3.yaml
```

若不使用 EKS Auto Mode，创建或复用其他 `StorageClass`，并在实例清单中更新为该类而非 `auto-ebs-gp3`。

## 3. 创建 ALB Ingress 类

在应用前编辑 `deploy/eks/openclaw-alb-class.yaml`：

- 替换 ACM 证书 ARN
- 若不部署到 `openclaw`，调整命名空间选择器

对于多实例 HTTPS，使用通配符 ACM 证书（如 `*.example.com`），以便添加新实例主机时无需为每次部署签发新证书。

然后应用：

```bash
kubectl apply -f deploy/eks/openclaw-alb-class.yaml
```

## 4. 创建提供商 Secret

在与实例相同的命名空间中创建 Secret。示例：

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

应用：

```bash
kubectl apply -f xai-provider-keys.yaml
```

## 5. 部署 OpenClaw 实例

使用如下 `OpenClawInstance`：

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

应用：

```bash
kubectl apply -f xai-assistant.yaml
```

要启动两个实例并分别使用不同域名，从 `deploy/eks/two-openclaw-instances.example.yaml` 开始，将两个示例主机替换为 ACM 证书覆盖的域名，然后应用：

```bash
kubectl apply -f deploy/eks/two-openclaw-instances.example.yaml
```

两个实例协调完成后，打印域名和网关令牌：

```bash
make instance-access OPENCLAW_NAMESPACE=openclaw
```

若要在扩展 ACM 证书前快速冒烟测试，可移除 `tls` 块并将 ALB `listen-ports` 注解改为仅 HTTP。网关 UI 仍可通过 `http://...` 访问，Operator 会从这些 HTTP 主机正确推导 Control UI 来源。

若需要一键部署 N 个实例，使用：

```bash
make deploy-instances \
  OPENCLAW_NAMESPACE=openclaw \
  INSTANCE_COUNT=3 \
  INSTANCE_PREFIX=agent \
  INSTANCE_DOMAIN_TEMPLATE='{name}.claw-farm.com' \
  INSTANCE_ROUTE53_ZONE_ID=Z01850443D2JAQL992O3
```

该命令会：

- 生成编号实例如 `agent-01`、`agent-02`、`agent-03`
- 将 CR 应用到集群
- 等待 StatefulSet 和 Ingress
- 设置 `INSTANCE_ROUTE53_ZONE_ID` 时 upsert Route53 DNS 记录
- 最后打印每个实例的域名和网关令牌

## 为何本清单禁用 ClawPort

本 EKS 方案有意暴露 OpenClaw 网关仪表板而非 ClawPort sidecar。

- `spec.clawport.enabled: false` 移除 ClawPort sidecar 及其 init job
- `paths[].port: 18789` 将 ALB Ingress 指向网关仪表板
- `alb.ingress.kubernetes.io/healthcheck-path: /healthz` 匹配网关代理健康端点

若之后希望 ALB 指回 ClawPort，重新启用 ClawPort 并移除 `paths[].port` 或将其设为 `3000`。

## 可选：禁用 MemOS

当前 Operator 行为默认启用 MemOS。若不需要内置记忆插件，添加：

```yaml
spec:
  memos:
    enabled: false
```

## 验证部署

检查实例和 Pod 健康：

```bash
kubectl get openclawinstance -n openclaw
kubectl get pods -n openclaw
kubectl get svc -n openclaw xai-assistant
kubectl get ingress -n openclaw xai-assistant
make instance-access OPENCLAW_NAMESPACE=openclaw
```

确认公网主机提供网关仪表板：

```bash
curl -I https://openclaw.example.com/
```

应看到 `200` 响应，获取完整页面内容时网关 UI HTML 标题为 `OpenClaw Control`。

## 故障排查

- 若 ALB 持续不健康，确保 Ingress 注解 `alb.ingress.kubernetes.io/healthcheck-path` 设为 `/healthz`
- 若 PVC 无法绑定，确认实例中的 `StorageClass` 名称与集群中安装的类一致
- 若主机解析正常但返回错误应用，检查 Ingress 后端端口是否为 `18789` 且 ClawPort 已禁用
- 若提供商请求失败，确认 API 密钥 Secret 存在于同一命名空间且键名与配置占位符匹配
