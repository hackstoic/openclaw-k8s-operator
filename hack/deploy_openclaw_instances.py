#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path


DEFAULT_RAW_CONFIG = """agents:
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
"""


def run(cmd, stdin=None, capture_output=False, check=True):
    return subprocess.run(
        cmd,
        input=stdin,
        text=True,
        capture_output=capture_output,
        check=check,
    )


def format_bool(value):
    return "true" if value else "false"


def build_manifest(
    name,
    namespace,
    host,
    raw_config,
    provider_secret,
    ingress_class,
    storage_class,
    storage_size,
    fleet_label,
    https_enabled,
):
    if https_enabled:
        listen_ports = '[{"HTTP":80},{"HTTPS":443}]'
        redirect_block = '        alb.ingress.kubernetes.io/ssl-redirect: "443"\n'
        tls_block = textwrap.indent(
            f"""tls:
  - hosts:
      - {host}
""",
            "      ",
        )
    else:
        listen_ports = '[{"HTTP":80}]'
        redirect_block = ""
        tls_block = ""

    return f"""apiVersion: openclaw.rocks/v1alpha1
kind: OpenClawInstance
metadata:
  name: {name}
  namespace: {namespace}
  labels:
    openclaw.rocks/fleet: {fleet_label}
  annotations:
    openclaw.rocks/skip-backup: "true"
spec:
  clawport:
    enabled: false
  memos:
    enabled: false
  envFrom:
    - secretRef:
        name: {provider_secret}
  config:
    raw:
{textwrap.indent(raw_config.rstrip(), "      ")}
  storage:
    persistence:
      enabled: true
      storageClass: {storage_class}
      size: {storage_size}
  networking:
    service:
      type: ClusterIP
    ingress:
      enabled: true
      className: {ingress_class}
      annotations:
        alb.ingress.kubernetes.io/scheme: internet-facing
        alb.ingress.kubernetes.io/target-type: ip
        alb.ingress.kubernetes.io/listen-ports: '{listen_ports}'
{redirect_block}        alb.ingress.kubernetes.io/load-balancer-attributes: idle_timeout.timeout_seconds=3600
        alb.ingress.kubernetes.io/healthcheck-path: /healthz
      hosts:
        - host: {host}
          paths:
            - path: /
              pathType: Prefix
              port: 18789
{tls_block}"""


def build_manifests(args):
    width = max(2, len(str(args.count)))
    docs = []
    for index in range(1, args.count + 1):
        suffix = f"{index:0{width}d}"
        name = f"{args.name_prefix}-{suffix}"
        host = args.domain_template.format(
            name=name,
            index=index,
            suffix=suffix,
            prefix=args.name_prefix,
        )
        docs.append(
            build_manifest(
                name=name,
                namespace=args.namespace,
                host=host,
                raw_config=args.raw_config,
                provider_secret=args.provider_secret,
                ingress_class=args.ingress_class,
                storage_class=args.storage_class,
                storage_size=args.storage_size,
                fleet_label=args.name_prefix,
                https_enabled=not args.http_only,
            )
        )
    return "\n---\n".join(docs) + "\n"


def wait_for_ingress_hostname(namespace, name, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = run(
            [
                "kubectl",
                "-n",
                namespace,
                "get",
                "ingress",
                name,
                "-o",
                "jsonpath={.status.loadBalancer.ingress[0].hostname}",
            ],
            capture_output=True,
            check=False,
        )
        hostname = result.stdout.strip()
        if hostname:
            return hostname
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for ingress hostname for {name}")


def wait_for_statefulset(namespace, name, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = run(
            ["kubectl", "-n", namespace, "get", "statefulset", name],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            run(
                [
                    "kubectl",
                    "-n",
                    namespace,
                    "rollout",
                    "status",
                    f"statefulset/{name}",
                    f"--timeout={timeout_seconds}s",
                ]
            )
            return
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for StatefulSet {name}")


def sync_route53(zone_id, records):
    changes = {
        "Comment": "UPSERT OpenClaw instance DNS records",
        "Changes": [
            {
                "Action": "UPSERT",
                "ResourceRecordSet": {
                    "Name": host,
                    "Type": "CNAME",
                    "TTL": 60,
                    "ResourceRecords": [{"Value": target}],
                },
            }
            for host, target in records.items()
        ],
    }

    change_file = Path("/tmp/openclaw-route53-batch.json")
    change_file.write_text(json.dumps(changes))
    response = run(
        [
            "aws",
            "route53",
            "change-resource-record-sets",
            "--hosted-zone-id",
            zone_id,
            "--change-batch",
            f"file://{change_file}",
        ],
        capture_output=True,
    )
    change_id = json.loads(response.stdout)["ChangeInfo"]["Id"]
    run(["aws", "route53", "wait", "resource-record-sets-changed", "--id", change_id])


def print_access(namespace, fleet_label):
    run(
        [
            "bash",
            "hack/list-instance-access.sh",
            namespace,
            f"openclaw.rocks/fleet={fleet_label}",
        ]
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate or deploy multiple OpenClawInstance resources.",
    )
    parser.add_argument("--count", type=int, required=True, help="Number of instances to create")
    parser.add_argument(
        "--name-prefix",
        required=True,
        help="Instance name prefix. Instances are numbered as <prefix>-01, <prefix>-02, ...",
    )
    parser.add_argument("--namespace", default="openclaw")
    parser.add_argument(
        "--domain-template",
        default="{name}.example.com",
        help="Python format string for instance domains. Available fields: name, index, suffix, prefix",
    )
    parser.add_argument("--provider-secret", default="xai-provider-keys")
    parser.add_argument("--ingress-class", default="openclaw-alb")
    parser.add_argument("--storage-class", default="auto-ebs-gp3")
    parser.add_argument("--storage-size", default="10Gi")
    parser.add_argument("--raw-config-file", help="Path to YAML content for spec.config.raw")
    parser.add_argument("--http-only", action="store_true", help="Create HTTP-only ingresses")
    parser.add_argument("--apply", action="store_true", help="Apply the generated manifests")
    parser.add_argument("--route53-zone-id", help="Optional Route53 hosted zone id for DNS UPSERTs")
    parser.add_argument(
        "--wait-timeout-seconds",
        type=int,
        default=900,
        help="Timeout for StatefulSet and ingress readiness checks",
    )
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be at least 1")

    if args.raw_config_file:
        args.raw_config = Path(args.raw_config_file).read_text().rstrip() + "\n"
    else:
        args.raw_config = DEFAULT_RAW_CONFIG

    manifests = build_manifests(args)

    if not args.apply:
        sys.stdout.write(manifests)
        return

    run(["kubectl", "apply", "-f", "-"], stdin=manifests)

    width = max(2, len(str(args.count)))
    names = [f"{args.name_prefix}-{index:0{width}d}" for index in range(1, args.count + 1)]
    for name in names:
        wait_for_statefulset(args.namespace, name, args.wait_timeout_seconds)

    records = {}
    for index, name in enumerate(names, start=1):
        suffix = f"{index:0{width}d}"
        host = args.domain_template.format(
            name=name,
            index=index,
            suffix=suffix,
            prefix=args.name_prefix,
        )
        records[host] = wait_for_ingress_hostname(args.namespace, name, args.wait_timeout_seconds)

    if args.route53_zone_id:
        sync_route53(args.route53_zone_id, records)

    print_access(args.namespace, args.name_prefix)


if __name__ == "__main__":
    main()
