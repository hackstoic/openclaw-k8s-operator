<p align="center">
  <img src="docs/images/banner.svg" alt="OpenClaw Kubernetes Operator — OpenClaws sailing the Kubernetes seas" width="100%">
</p>

# OpenClaw Kubernetes Operator

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Go Report Card](https://goreportcard.com/badge/github.com/OpenClaw-rocks/k8s-operator)](https://goreportcard.com/report/github.com/OpenClaw-rocks/k8s-operator)
[![CI](https://github.com/OpenClaw-rocks/k8s-operator/actions/workflows/ci.yaml/badge.svg)](https://github.com/OpenClaw-rocks/k8s-operator/actions/workflows/ci.yaml)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.28%2B-326CE5?logo=kubernetes&logoColor=white)](https://kubernetes.io)
[![Go](https://img.shields.io/badge/Go-1.24-00ADD8?logo=go&logoColor=white)](https://go.dev)

**在 Kubernetes 上自托管 [OpenClaw](https://openclaw.ai) AI 智能体，具备生产级安全、可观测性和生命周期管理。**

OpenClaw 是一个 AI 智能体平台，可代表你在 Telegram、Discord、WhatsApp 和 Signal 等渠道执行操作，通过 50+ 集成管理收件箱、日历、智能家居等。虽然 [OpenClaw.rocks](https://openclaw.rocks) 提供全托管服务，本 Operator 让你能在自有基础设施上以相同的运维标准运行 OpenClaw。

---

## 为什么需要 Operator？

在 Kubernetes 上部署 AI 智能体远不止一个 Deployment 和一个 Service。你需要网络隔离、密钥管理、持久化存储、健康监控、可选的浏览器自动化、配置发布等，且都要正确配置。本 Operator 将这些关注点编码到单一的 `OpenClawInstance` 自定义资源中，让你在几分钟内从零到生产环境：

```yaml
apiVersion: openclaw.rocks/v1alpha1
kind: OpenClawInstance
metadata:
  name: my-agent
spec:
  envFrom:
    - secretRef:
        name: openclaw-api-keys
  storage:
    persistence:
      enabled: true
      size: 10Gi
```

Operator 会将此资源协调为 9+ 个 Kubernetes 资源的完整托管栈：安全、可监控、自愈。

## 自适应智能体

智能体可以自主安装技能、修补配置、添加环境变量、预置工作区文件，全部通过 Kubernetes API 完成，每次请求都由 Operator 校验。

```yaml
# 1. 在实例上启用自配置
spec:
  selfConfigure:
    enabled: true
    allowedActions: [skills, config, envVars, workspaceFiles]
```

```yaml
# 2. 智能体创建此资源以在运行时安装技能
apiVersion: openclaw.rocks/v1alpha1
kind: OpenClawSelfConfig
metadata:
  name: add-fetch-skill
spec:
  instanceRef: my-agent
  addSkills:
    - "@anthropic/mcp-server-fetch"
```

每个请求都会根据实例的允许列表策略进行校验。受保护的配置键不能被覆盖，被拒绝的请求会记录原因。详见 [自配置](#self-configure)。

## 功能特性

| | 功能 | 说明 |
|---|---|---|
| **声明式** | 单一 CRD | 一个资源定义完整栈：StatefulSet、Service、RBAC、NetworkPolicy、PVC、PDB、Ingress 等 |
| **自适应** | 智能体自配置 | 智能体通过 K8s API 自主安装技能、修补配置、调整环境，每次变更都按允许列表策略校验 |
| **安全** | 默认加固 | 非 root（UID 1000）、只读根文件系统、丢弃所有 capabilities、seccomp RuntimeDefault、默认拒绝 NetworkPolicy、校验 Webhook |
| **可观测** | 内置指标 | Prometheus 指标、ServiceMonitor 集成、结构化 JSON 日志、Kubernetes 事件 |
| **灵活** | 提供商无关配置 | 通过环境变量和内联或外部配置使用任意 AI 提供商（Anthropic、OpenAI 等） |
| **配置模式** | 合并或覆盖 | `overwrite` 在重启时替换配置；`merge` 与 PVC 配置深度合并，保留运行时变更。每次容器重启时通过 init 容器恢复配置。 |
| **技能** | 声明式安装 | 通过 `spec.skills` 安装 ClawHub 技能、npm 包或 GitHub 托管的技能包，支持 `npm:` 和 `pack:` 前缀 |
| **运行时依赖** | pnpm 与 Python/uv | 内置 init 容器安装 pnpm（通过 corepack）或 Python 3.12 + uv，用于 MCP 服务器和技能 |
| **内置 UI** | ClawPort 仪表板 | 每个实例在端口 `3000` 安装 `clawport-ui@0.8.3` 作为 sidecar；默认 Ingress 后端指向它 |
| **内置记忆** | MemOS 插件 | 每个实例安装 `@memtensor/memos-local-openclaw-plugin@1.0.2`，注入所需配置默认值并保留用户覆盖 |
| **自动更新** | OCI 仓库轮询 | 可选版本跟踪：检查仓库新 semver 版本，先备份再发布，若新版本健康检查失败则自动回滚 |
| **可扩展** | 自动扩缩 | HPA 集成 CPU 和内存指标，最小/最大副本边界，自动 StatefulSet 副本管理 |
| **Resilient** | 自愈生命周期 | PodDisruptionBudgets、健康探针、通过内容哈希自动配置发布、5 分钟漂移检测 |
| **备份/恢复** | S3 快照 | 删除、更新前和 cron 计划时自动备份到 S3 兼容存储；从任意快照恢复到新实例 |
| **工作区预置** | 初始文件与目录 | 在智能体启动前预填充工作区 |
| **网关认证** | 自动生成令牌 | 每个实例自动生成网关令牌 Secret，绕过 mDNS 配对（在 k8s 中不可用） |
| **Tailscale** | Tailnet 访问 | 通过 Tailscale Serve 或 Funnel 暴露，支持 SSO 认证，无需 Ingress |
| **可扩展** | Sidecar 与 init 容器 | Chromium 浏览器自动化、Ollama 本地 LLM、Tailscale tailnet 访问，以及自定义 init 容器和 sidecar |
| **云原生** | SA 注解与 CA 包 | 通过 ServiceAccount 注解支持 AWS IRSA / GCP Workload Identity；企业代理的 CA 包注入 |

## 架构

```
+-----------------------------------------------------------------+
|  OpenClawInstance CR          OpenClawSelfConfig CR              |
|  (你的声明式配置)            (智能体自修改请求)                    |
+---------------+-------------------------------------------------+
                | watch
                v
+-----------------------------------------------------------------+
|  OpenClaw Operator                                              |
|  +-----------+  +-------------+  +----------------------------+ |
|  | Reconciler|  |   Webhooks  |  |   Prometheus Metrics       | |
|  |           |  |  (validate  |  |  (reconcile count,         | |
|  |  creates ->  |   & default)|  |   duration, phases)        | |
|  +-----------+  +-------------+  +----------------------------+ |
+---------------+-------------------------------------------------+
                | manages
                v
+-----------------------------------------------------------------+
|  托管资源（每个实例）                                            |
|                                                                 |
|  ServiceAccount -> Role -> RoleBinding    NetworkPolicy         |
|  ConfigMap        PVC      PDB            ServiceMonitor        |
|  GatewayToken Secret                                            |
|                                                                 |
|  StatefulSet                                                    |
|  +-----------------------------------------------------------+ |
|  | Init: config -> runtime deps* -> skills* -> memos*         | |
|  |        -> clawport* -> custom                              | |
|  |                                        (* = 可选)          | |
|  +------------------------------------------------------------+ |
|  | OpenClaw 容器  Gateway Proxy (nginx)  ClawPort UI          | |
|  |                     Chromium (可选) / Ollama (可选)        | |
|  |                     Tailscale (可选) + 自定义 sidecars     | |
|  +------------------------------------------------------------+ |
|                                                                 |
|  Service (默认: 3000, 18789, 18793 或自定义) -> Ingress         |
+-----------------------------------------------------------------+
```

## 快速开始

### 前置条件

- Kubernetes 1.28+
- Helm 3

### 1. 安装 Operator

```bash
helm install openclaw-operator \
  oci://ghcr.io/openclaw-rocks/charts/openclaw-operator \
  --namespace openclaw-operator-system \
  --create-namespace
```

<details>
<summary>备选：使用 Kustomize 安装</summary>

```bash
# 安装 CRD
make install

# 部署 Operator
make deploy IMG=ghcr.io/openclaw-rocks/openclaw-operator:latest
```

</details>

### 2. 创建包含 API 密钥的 Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: openclaw-api-keys
type: Opaque
stringData:
  ANTHROPIC_API_KEY: "sk-ant-..."
```

### 3. 部署 OpenClaw 实例

```yaml
apiVersion: openclaw.rocks/v1alpha1
kind: OpenClawInstance
metadata:
  name: my-agent
spec:
  envFrom:
    - secretRef:
        name: openclaw-api-keys
  storage:
    persistence:
      enabled: true
      size: 10Gi
```

```bash
kubectl apply -f secret.yaml -f openclawinstance.yaml
```

### 4. 验证

```bash
kubectl get openclawinstances
# NAME       PHASE     AGE
# my-agent   Running   2m

kubectl get pods
# NAME         READY   STATUS    AGE
# my-agent-0   1/1     Running   2m
```

## 配置

### 内联配置 (openclaw.json)

```yaml
spec:
  config:
    raw:
      agents:
        defaults:
          model:
            primary: "anthropic/claude-sonnet-4-20250514"
          sandbox: true
      session:
        scope: "per-sender"
```

### 外部 ConfigMap 引用

```yaml
spec:
  config:
    configMapRef:
      name: my-openclaw-config
      key: openclaw.json
```

配置变更通过 SHA-256 哈希检测，自动触发滚动更新，无需手动重启。

### 网关认证

Operator 为每个实例自动生成网关令牌 Secret，并注入到配置 JSON（`gateway.auth.mode: token`）和 `OPENCLAW_GATEWAY_TOKEN` 环境变量中。这绕过了 Bonjour/mDNS 配对，后者在 Kubernetes 中不可用。

- 令牌生成一次且不会被覆盖，如需轮换请直接编辑 Secret
- 若在配置中设置 `gateway.auth.token` 或在 `spec.env` 中设置 `OPENCLAW_GATEWAY_TOKEN`，你的值优先
- 若要使用自有令牌 Secret，设置 `spec.gateway.existingSecret`，Operator 将使用它而非自动生成（Secret 必须包含名为 `token` 的键）
- Operator 自动设置 `gateway.controlUi.dangerouslyDisableDeviceAuth: true`，设备配对与 Kubernetes 不兼容（用户无法在容器内批准配对，连接始终经过代理，且 mDNS 不可用）
- **不要在配置中设置 `gateway.mode: local`**，此模式用于桌面安装，会强制设备身份校验，在 Kubernetes 反向代理后无法工作
- 默认 Ingress 后端现在指向端口 `3000` 的 ClawPort，而非网关 Control UI
- 若要通过 Ingress 暴露网关 Control UI 或 canvas，将 `spec.networking.ingress.hosts[].paths[].port` 设为 `18789` 或 `18793`
- 通过 Ingress 连接网关 Control UI 时，在 URL fragment 中传递网关令牌：`https://openclaw.example.com/#token=<your-token>`
- 自 v2026.2.24 起，OpenClaw 默认将 `gateway.allowedOrigins` 限制为同源，若通过非默认主机名（如 Ingress）访问，需在配置中设置 `gateway.allowedOrigins: ["*"]`

### Control UI 允许来源

Operator 自动注入 `gateway.controlUi.allowedOrigins`，使 Control UI 在反向代理后正常工作且无 CORS 错误。来源来自：

- **本地**（始终）：`http://localhost:18789`、`http://127.0.0.1:18789` 用于 port-forward
- **Ingress 主机**：scheme 由 TLS 配置决定（有 TLS 则为 `https://`，否则为 `http://`）
- **显式额外**：`spec.gateway.controlUiOrigins` 用于自定义代理 URL

若在配置 JSON 中直接设置 `gateway.controlUi.allowedOrigins`，Operator 不会覆盖。

### ClawPort 与 MemOS 默认

每个实例默认启用两个内置集成：

- `spec.clawport.enabled: true` 安装 `clawport-ui@0.8.3`，在 init 容器中构建，在 Service 端口 `3000` 暴露，并将默认 Ingress 后端指向它
- `spec.memos.enabled: true` 安装 `@memtensor/memos-local-openclaw-plugin@1.0.2`，仅在你尚未自行设置时注入以下配置默认值：
  - `agents.defaults.memorySearch.enabled=false`
  - `plugins.slots.memory="memos-local-openclaw-plugin"`
  - `plugins.entries["memos-local-openclaw-plugin"].enabled=true`

若需旧行为，可按实例禁用任一集成：

```yaml
spec:
  clawport:
    enabled: false
  memos:
    enabled: false
```

### Chromium Sidecar

启用无头浏览器自动化，用于网页抓取、截图和基于浏览器的集成：

```yaml
spec:
  chromium:
    enabled: true
    image:
      repository: ghcr.io/browserless/chromium
      tag: "v2.0.0"
    resources:
      requests:
        cpu: "250m"
        memory: "512Mi"
      limits:
        cpu: "1000m"
        memory: "2Gi"
    # 向 Chromium 进程传递额外参数（追加到内置反爬虫默认值后）
    extraArgs:
      - "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    # 向 sidecar 注入额外环境变量
    extraEnv:
      - name: DEFAULT_STEALTH
        value: "true"
```

启用后，Operator 自动：
- 向主容器注入 `CHROMIUM_URL` 环境变量
- 在 OpenClaw 配置中配置浏览器配置文件，`"default"` 和 `"chrome"` 均指向 sidecar 的 CDP 端点，无论 LLM 传入哪个 profile 名，浏览器工具调用都能工作
- 为 sidecar 配置共享内存、安全上下文和健康探针
- 默认应用反爬虫检测参数（`--disable-blink-features=AutomationControlled`、`--disable-features=AutomationControlled`、`--no-first-run`）

#### 持久化浏览器配置

默认情况下，所有浏览器状态（cookies、localStorage、会话令牌）在 Pod 重启时丢失。启用持久化以在重启间保留浏览器配置：

```yaml
spec:
  chromium:
    enabled: true
    persistence:
      enabled: true          # 默认: false
      storageClass: ""        # 可选，空则使用集群默认
      size: "1Gi"             # 默认: 1Gi
      existingClaim: ""       # 可选，使用已有 PVC
```

启用持久化后，Operator 创建专用 PVC 并向 Chrome 传递 `--user-data-dir=/chromium-data`，使 cookies、localStorage、IndexedDB、缓存凭据和会话令牌在 Pod 重启后保留。适用于认证浏览器自动化、MFA 保护服务和长时间运行的浏览器工作流。

**安全说明：** 持久化浏览器配置包含敏感会话令牌。PVC 与其他实例卷具有相同安全策略。对敏感工作负载请确保 StorageClass 支持静态加密。

### Ollama Sidecar

在智能体旁运行本地 LLM，实现私有、低延迟推理，无需外部 API 调用：

```yaml
spec:
  ollama:
    enabled: true
    models:
      - llama3.2
      - nomic-embed-text
    gpu: 1
    storage:
      sizeLimit: 30Gi
    resources:
      requests:
        cpu: "1"
        memory: "4Gi"
      limits:
        cpu: "4"
        memory: "16Gi"
```

启用后，Operator：
- 向主容器注入 `OLLAMA_HOST` 环境变量
- 在智能体启动前通过 init 容器预拉取指定模型
- 设置 `gpu` 时配置 GPU 资源限制（`nvidia.com/gpu`）
- 挂载模型缓存卷（默认 emptyDir，或通过 `storage.existingClaim` 使用已有 PVC）

通过环境变量配置 OpenClaw 使用 Ollama 模型，参见 [自定义 AI 提供商](docs/custom-providers.md)。

### Web 终端 Sidecar

提供基于浏览器的 shell 访问，用于调试和检查运行中的实例，无需 `kubectl exec`：

```yaml
spec:
  webTerminal:
    enabled: true
    readOnly: false
    credential:
      secretRef:
        name: my-terminal-creds
    resources:
      requests:
        cpu: "50m"
        memory: "64Mi"
      limits:
        cpu: "200m"
        memory: "128Mi"
```

启用后，Operator：
- 在端口 7681 注入 [ttyd](https://github.com/tsl0922/ttyd) sidecar 容器
- 将实例数据卷挂载到 `/home/openclaw/.openclaw`，便于检查配置、日志和数据文件
- 将 web 终端端口加入 Service 和 NetworkPolicy 以支持外部访问
- 通过包含 `username` 和 `password` 键的 Secret 支持基本认证
- 支持只读模式（`readOnly: true`），适用于生产环境中禁用 shell 输入

### Tailscale 集成

通过 [Tailscale](https://tailscale.com) Serve（仅 tailnet）或 Funnel（公网）暴露实例，无需 Ingress 或 LoadBalancer：

```yaml
spec:
  tailscale:
    enabled: true
    mode: serve          # "serve"（仅 tailnet）或 "funnel"（公网）
    authKeySecretRef:
      name: tailscale-auth
    authSSO: true        # 允许 tailnet 成员无密码登录
    hostname: my-agent   # 默认使用实例名
    image:
      repository: ghcr.io/tailscale/tailscale  # 默认
      tag: latest
    resources:
      requests:
        cpu: 50m
        memory: 64Mi
      limits:
        cpu: 200m
        memory: 256Mi
```

启用后，Operator 运行 **Tailscale sidecar**（`tailscaled`），通过 `TS_SERVE_CONFIG` 声明式处理 serve/funnel。**init 容器**将 `tailscale` CLI 二进制复制到共享卷，使主容器可调用 `tailscale whois` 进行 SSO 认证。Sidecar 以用户空间模式运行（`TS_USERSPACE=true`），无需 `NET_ADMIN` capability。

**状态持久化：** Tailscale 节点身份和 TLS 证书通过 `TS_KUBE_SECRET` 自动持久化到 Kubernetes Secret（`<instance>-ts-state`）。这避免主机名递增（device-1、device-2...）和 Let's Encrypt 证书在 Pod 重启时重新签发。Operator 预创建状态 Secret，授予 Pod 的 ServiceAccount 对其的 `get/update/patch` 权限，并自动挂载 SA 令牌。

使用 [Tailscale 管理控制台](https://login.tailscale.com/admin/settings/keys) 的临时可复用认证密钥。启用 `authSSO` 后，tailnet 成员无需网关令牌即可认证。

### 配置合并模式

默认情况下，Operator 在每次 Pod 重启时覆盖配置文件。设置 `mergeMode: merge` 可将 Operator 配置与现有 PVC 配置深度合并，保留智能体所做的运行时变更：

```yaml
spec:
  config:
    mergeMode: merge
    raw:
      agents:
        defaults:
          model:
            primary: "anthropic/claude-sonnet-4-20250514"
```

**注意：** 在 merge 模式下，从 CR 中移除键不会从 PVC 配置中移除，旧值会保留，因为深度合并只添加或更新键。若需移除过时配置键（例如移除 `gateway.mode: local` 后），可临时切换到 `mergeMode: replace`，应用并等待 Pod 重启，再切回 `merge`。

### 技能安装

声明式安装技能。Operator 在智能体启动前运行 init 容器拉取每个技能。条目默认使用 ClawHub，或加 `npm:` 前缀从 npmjs.com 安装。ClawHub 安装是幂等的，若技能已安装（例如使用持久化存储时），会跳过而非失败：

```yaml
spec:
  skills:
    - "@anthropic/mcp-server-fetch"       # ClawHub（默认）
    - "npm:@openclaw/matrix"              # 来自 npmjs.com 的 npm 包
```

init 容器全局禁用 npm 生命周期脚本（`NPM_CONFIG_IGNORE_SCRIPTS=true`）以降低供应链攻击风险。

### 技能包

技能包将多个文件（SKILL.md、脚本、配置）打包为托管在 GitHub 上的可安装单元。使用 `pack:` 前缀和 `owner/repo/path` 格式：

```yaml
spec:
  skills:
    - "pack:openclaw-rocks/skills/image-gen"            # 默认分支最新
    - "pack:openclaw-rocks/skills/image-gen@v1.0.0"     # 固定到标签
    - "pack:myorg/private-skills/custom-tool@main"       # 私有仓库（需 GITHUB_TOKEN）
```

每个包目录必须包含 `skillpack.json` 清单：

```json
{
  "files": {
    "skills/image-gen/SKILL.md": "SKILL.md",
    "skills/image-gen/scripts/generate.py": "scripts/generate.py"
  },
  "directories": ["skills/image-gen/scripts"],
  "config": {
    "image-gen": {"enabled": true}
  }
}
```

Operator 通过 GitHub Contents API 解析包（缓存 5 分钟），通过 init 容器将文件预置到工作区，并将配置条目注入 `config.raw.skills.entries`（用户覆盖优先）。访问私有仓库时需在 Operator 部署上设置 `GITHUB_TOKEN`。

### 自配置

允许智能体通过 K8s API 创建 `OpenClawSelfConfig` 资源来修改自身配置。Operator 在应用变更前根据实例的 `allowedActions` 策略校验每个请求：

```yaml
spec:
  selfConfigure:
    enabled: true
    allowedActions:
      - skills        # 添加/移除技能
      - config        # 修补 openclaw.json
      - workspaceFiles # 添加/移除工作区文件
      - envVars       # 添加/移除环境变量
```

启用后，Operator：
- 授予实例 ServiceAccount 读取自身 CRD 和创建 `OpenClawSelfConfig` 的 RBAC 权限
- 启用 SA 令牌自动挂载，使智能体能通过 K8s API 认证
- 将 `SELFCONFIG.md` 技能文件和 `selfconfig.sh` 辅助脚本注入工作区
- 在 NetworkPolicy 中开放端口 6443 出站以访问 K8s API

智能体创建如下请求：

```yaml
apiVersion: openclaw.rocks/v1alpha1
kind: OpenClawSelfConfig
metadata:
  name: add-fetch-skill
spec:
  instanceRef: my-agent
  addSkills:
    - "@anthropic/mcp-server-fetch"
```

Operator 校验请求，应用到父 `OpenClawInstance`，并将请求状态设为 `Applied`、`Denied` 或 `Failed`。终止态请求在 1 小时后自动删除。

完整 `OpenClawSelfConfig` CRD 规范和 `spec.selfConfigure` 字段见 [API 参考](docs/api-reference.md)。

### 持久化存储

默认 Operator 创建 10Gi PVC，并在 CR 删除时保留（orphan 行为）。可覆盖大小、存储类或保留策略：

```yaml
spec:
  storage:
    persistence:
      size: 20Gi
      storageClass: fast-ssd
      orphan: true   # 默认，CR 删除时 PVC 保留
      # orphan: false  -- CR 删除时 PVC 一并删除（垃圾回收）
```

复用已有 PVC（例如从备份恢复后）：

```yaml
spec:
  storage:
    persistence:
      existingClaim: my-agent-data
```

> **保留是状态数据的保护。** 由于智能体工作区包含不可替代的数据（记忆、笔记本、对话历史等），默认 `orphan: true`。要将保留的 PVC 重新挂到新实例，将 `existingClaim` 设为其名称。

### 运行时依赖

启用内置 init 容器，将 pnpm 或 Python/uv 安装到数据 PVC，供 MCP 服务器和技能使用：

```yaml
spec:
  runtimeDeps:
    pnpm: true    # 通过 corepack 安装 pnpm
    python: true  # 安装 Python 3.12 + uv
```

### 自定义 init 容器与 sidecar

添加自定义 init 容器（在 Operator 管理的之后运行）和 sidecar 容器：

```yaml
spec:
  initContainers:
    - name: fetch-models
      image: curlimages/curl:8.5.0
      command: ["sh", "-c", "curl -o /data/model.bin https://..."]
      volumeMounts:
        - name: data
          mountPath: /data
  sidecars:
    - name: cloud-sql-proxy
      image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.14.3
      args: ["--structured-logs", "my-project:us-central1:my-db"]
      ports:
        - containerPort: 5432
  sidecarVolumes:
    - name: proxy-creds
      secret:
        secretName: cloud-sql-proxy-sa
```

保留的 init 容器名（`init-config`、`init-pnpm`、`init-python`、`init-skills`、`init-ollama`）会被 webhook 拒绝。

### 额外卷与挂载

将额外 ConfigMap、Secret 或 CSI 卷挂载到主容器：

```yaml
spec:
  extraVolumes:
    - name: shared-data
      persistentVolumeClaim:
        claimName: shared-pvc
  extraVolumeMounts:
    - name: shared-data
      mountPath: /shared
```

### Ingress Basic Auth

为 Ingress 添加 HTTP Basic 认证。Operator 自动生成随机密码并存入托管 Secret：

```yaml
spec:
  networking:
    ingress:
      enabled: true
      className: nginx
      hosts:
        - host: my-agent.example.com
      security:
        basicAuth:
          enabled: true
          username: admin          # 默认: "openclaw"
          realm: "My Agent"        # 默认: "OpenClaw"
```

生成的 Secret 名为 `<name>-basic-auth`，包含三个键：`auth`（ingress 控制器的 htpasswd 格式）、`username` 和 `password`（明文，用于获取自动生成的凭据）。在 `status.managedResources.basicAuthSecret` 中追踪。若要使用自有凭据，提供预格式化的 htpasswd Secret：

```yaml
spec:
  networking:
    ingress:
      security:
        basicAuth:
          enabled: true
          existingSecret: my-htpasswd-secret  # 必须包含 "auth" 键
```

对于 Traefik ingress，会自动创建 `Middleware` CRD 资源（需已安装 Traefik CRD）。

### 多实例与独立域名

Operator 已支持在同一集群运行多个 `OpenClawInstance`。关键是给每个实例不同的名称和 Ingress 主机。可编辑的 EKS 双实例示例位于 `deploy/eks/two-openclaw-instances.example.yaml`。

- 为每个实例使用不同的 `metadata.name`，使 PVC、Service、Secret 等托管资源隔离
- 为每个实例设置唯一的 `spec.networking.ingress.hosts[].host`
- 确保 TLS 证书和 DNS 记录覆盖你分配的所有主机
- 使用 `make instance-access OPENCLAW_NAMESPACE=openclaw` 获取当前访问信息
- 对于编号批量部署，使用 `make deploy-instances INSTANCE_COUNT=3 INSTANCE_PREFIX=agent INSTANCE_DOMAIN_TEMPLATE='{name}.example.com'`

`make instance-access` 读取每个实例配置的 Ingress 主机以及 `status.managedResources.gatewayTokenSecret` 追踪的每实例 Secret 中的网关令牌。

### 自定义服务端口

默认 Operator 创建包含 ClawPort Web（`3000`）、gateway（`18789`）和 canvas（`18793`）端口的 Service。若要暴露自定义端口（例如非默认应用），设置 `spec.networking.service.ports`：

```yaml
spec:
  networking:
    service:
      type: ClusterIP
      ports:
        - name: http
          port: 3978
          targetPort: 3978
```

设置 `ports` 时，会完全替换默认端口，包括 ClawPort、gateway、canvas 和任何可选 sidecar 端口。若要在自定义端口旁保留默认端口，需显式包含。若同时启用 Ingress 且使用自定义 Service 端口，每个 `paths[]` 条目必须设置 `port`。省略 `targetPort` 时默认为 `port`。所有字段见 [API 参考](docs/api-reference.md#specnetworkingservice)。

### CA 包注入

在存在 TLS 拦截代理或私有 CA 的环境中注入自定义 CA 证书包：

```yaml
spec:
  security:
    caBundle:
      configMapName: corporate-ca-bundle  # 或 secretName
      key: ca-bundle.crt                  # 默认键名
```

包会挂载到所有容器，并自动设置 `SSL_CERT_FILE` / `NODE_EXTRA_CA_CERTS` 环境变量。

### ServiceAccount 注解

为云提供商集成向托管 ServiceAccount 添加注解：

```yaml
spec:
  security:
    rbac:
      serviceAccountAnnotations:
        # AWS IRSA
        eks.amazonaws.com/role-arn: "arn:aws:iam::123456789:role/openclaw"
        # GCP Workload Identity
        # iam.gke.io/gcp-service-account: "openclaw@project.iam.gserviceaccount.com"
```

### 自动更新

选择自动版本跟踪，Operator 会检测新版本并在无需人工干预的情况下发布：

```yaml
spec:
  autoUpdate:
    enabled: true
    checkInterval: "24h"         # 轮询仓库频率（1h-168h）
    backupBeforeUpdate: true     # 更新前备份 PVC
    rollbackOnFailure: true      # 新版本健康检查失败时自动回滚
    healthCheckTimeout: "10m"    # 等待 Pod 就绪的最长时间（2m-30m）
```

启用后，Operator 在创建时将 `latest` 解析为最高稳定 semver 标签，然后在每个 `checkInterval` 轮询新版本。更新前可选运行 S3 备份，然后 patch 镜像标签并监控发布。若 Pod 在 `healthCheckTimeout` 内未能就绪，则回滚镜像标签并（可选）从更新前快照恢复 PVC。

安全机制包括失败版本跟踪（跳过健康检查失败的版本）、熔断器（连续 3 次回滚后暂停）以及启用 `backupBeforeUpdate` 时的完整数据恢复。对摘要固定的镜像（`spec.image.digest`），自动更新为 no-op。

更新进度见 `status.autoUpdate`：`kubectl get openclawinstance my-agent -o jsonpath='{.status.autoUpdate}'`

### 备份与恢复

Operator 使用 [rclone](https://rclone.org/) 将 PVC 数据备份到 S3 兼容存储或从中恢复。所有备份操作需要在 **Operator 命名空间** 中名为 `s3-backup-credentials` 的 Secret：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: s3-backup-credentials
  namespace: openclaw-operator-system
stringData:
  S3_ENDPOINT: "https://s3.us-east-1.amazonaws.com"
  S3_BUCKET: "my-openclaw-backups"
  S3_ACCESS_KEY_ID: "<key-id>"            # 可选，工作负载身份时省略
  S3_SECRET_ACCESS_KEY: "<secret-key>"    # 可选，工作负载身份时省略
  # S3_PROVIDER: "Other"    # 可选，设为 "AWS"、"GCS" 等以使用原生凭据链
  # S3_REGION: "us-east-1"  # 可选，MinIO 或自定义区域时需设置
```

兼容 AWS S3、Backblaze B2、Cloudflare R2、MinIO、Wasabi 及任何 S3 兼容 API。

**云工作负载身份：** 省略 `S3_ACCESS_KEY_ID` 和 `S3_SECRET_ACCESS_KEY`，并设置 `S3_PROVIDER`（如 `AWS`、`GCS`）以使用提供商原生凭据链。将 `spec.backup.serviceAccountName` 设为支持工作负载身份的 ServiceAccount（IRSA、GKE Workload Identity、AKS Workload Identity），使备份 Job 继承云 IAM 角色。完整示例见 API 参考中的 [工作负载身份章节](docs/api-reference.md#workload-identity-cloud-native-auth)。

**自动备份时机：**

- **删除时**：Operator 在移除任何资源前备份 PVC。受 `spec.backup.timeout` 限制（默认 30m），超时则自动跳过。添加 `openclaw.rocks/skip-backup: "true"` 可立即跳过。
- **自动更新前**：当 `spec.autoUpdate.backupBeforeUpdate: true`（默认）。
- **按计划**：当设置 `spec.backup.schedule`（cron 表达式）时。

若 Secret 不存在，备份会静默跳过，操作照常进行。

**定期计划备份：**

```yaml
spec:
  backup:
    schedule: "0 2 * * *"   # 每天 UTC 2:00
    historyLimit: 3          # 保留的成功 Job 运行数（默认 3）
    failedHistoryLimit: 1    # 保留的失败 Job 运行数（默认 1）
    timeout: "30m"           # 删除前备份最长时间（默认 30m，最小 5m，最大 24h）
    serviceAccountName: ""   # 可选：备份 Job 的 IRSA/Pod Identity SA
```

Operator 创建 Kubernetes CronJob，使用 rclone 将 PVC 数据同步到 S3。CronJob 以只读方式挂载 PVC（热备份，无停机），并使用 pod affinity 与 StatefulSet Pod 同节点（RWO PVC 所需）。每次运行将数据存到唯一时间戳路径：`backups/<tenantId>/<instanceName>/periodic/<timestamp>`。

**从备份恢复：**

```yaml
spec:
  # 源实例 status.lastBackupPath 中记录的路径
  restoreFrom: "backups/my-tenant/my-agent/2026-01-15T10:30:00Z"
```

Operator 运行恢复 Job 在启动 StatefulSet 前填充 PVC，然后自动清除 `restoreFrom`。备份路径格式为 `backups/<tenantId>/<instanceName>/<timestamp>`。

完整说明见 API 参考中的 [备份与恢复章节](docs/api-reference.md#backup-and-restore)。

### Operator 自动管理的行为

以下行为始终应用，无需配置：

| 行为 | 说明 |
|----------|---------|
| `gateway.bind=loopback` | 始终注入配置；nginx 反向代理 sidecar 暴露 gateway 和 canvas 端口供外部访问 |
| ClawPort 仪表板 | 默认启用；安装 `clawport-ui@0.8.3`，暴露 Service 端口 `3000`，作为默认 Ingress 后端 |
| 网关认证令牌 | 每实例自动生成 Secret；注入配置和 env |
| Control UI 来源 | `gateway.controlUi.allowedOrigins` 从 localhost + ingress 主机 + `spec.gateway.controlUiOrigins` 自动注入 |
| MemOS 默认 | 默认启用；安装 `@memtensor/memos-local-openclaw-plugin@1.0.2`，注入记忆插件默认值且不覆盖用户配置 |
| `OPENCLAW_DISABLE_BONJOUR=1` | 始终设置（mDNS 在 Kubernetes 中不可用） |
| 浏览器配置 | 启用 Chromium 时，`"default"` 和 `"chrome"` 配置自动指向 sidecar 的 CDP 端点 |
| Tailscale serve 配置 | 启用 Tailscale 时，向 ConfigMap 添加 `tailscale-serve.json` 键供 sidecar 的 `TS_SERVE_CONFIG` |
| Tailscale 状态持久化 | 启用 Tailscale 时，节点身份和 TLS 证书通过 `TS_KUBE_SECRET` 持久化到 `<instance>-ts-state` Secret |
| 配置哈希发布 | 配置变更通过 SHA-256 哈希注解触发滚动更新 |
| 配置恢复 | init 容器在每次 Pod 重启时恢复配置（overwrite 或 merge 模式） |

完整配置选项见 [API 参考](docs/api-reference.md) 和 [完整示例 YAML](config/samples/openclaw_v1alpha1_openclawinstance_full.yaml)。

## 安全

Operator 遵循 **默认安全** 原则。每个实例开箱即用加固设置，无需额外配置。

### 默认值

- **非 root 执行**：容器以 UID 1000 运行；root（UID 0）被校验 webhook 阻止（例外：Ollama sidecar 按官方镜像要求需 root）
- **只读根文件系统**：主容器和 Chromium sidecar 默认启用；`~/.openclaw/` 的 PVC 提供可写 home，`/tmp` emptyDir 处理临时文件
- **丢弃所有 capabilities**：无环境 Linux capabilities
- **Seccomp RuntimeDefault**：启用 syscall 过滤
- **默认拒绝 NetworkPolicy**：仅允许 DNS（53）和 HTTPS（443）出站；入站限制为同命名空间
- **最小 RBAC**：每个实例有独立 ServiceAccount，对其 ConfigMap 只读；Operator 仅能为 Operator 托管的网关令牌创建/更新 Secret
- **无自动令牌挂载**：ServiceAccount 和 Pod spec 上 `automountServiceAccountToken: false`（仅在 `selfConfigure` 激活时启用）
- **Secret 校验**：Operator 检查所有引用 Secret 是否存在，并设置 `SecretsReady` 条件
- **安全上下文传播**：当 `podSecurityContext.runAsNonRoot` 设为 `false` 时，Operator 将其传播到 init 容器和适用的 sidecar（tailscale、web terminal），使 Pod 级与容器级设置一致。自洽的 sidecar（gateway-proxy、chromium、ollama）保留各自安全上下文。`containerSecurityContext.runAsNonRoot` 和 `containerSecurityContext.runAsUser` 允许独立于 Pod 级对主容器进行细粒度控制。

### 校验 Webhook

| 检查 | 严重性 | 行为 |
|-------|----------|----------|
| `runAsUser: 0` | Error | 阻止：不允许 root 执行 |
| 保留 init 容器名 | Error | `init-config`、`init-pnpm`、`init-python`、`init-skills`、`init-ollama` 为保留 |
| 无效技能名 | Error | 仅允许字母数字、`-`、`_`、`/`、`.`、`@`（最多 128 字符）。npm 包用 `npm:` 前缀，技能包用 `pack:` 前缀；裸 `npm:` 或 `pack:` 被拒绝 |
| 无效 CA 包配置 | Error | 必须恰好设置 `configMapName` 或 `secretName` 之一 |
| 内联 raw 配置使用 JSON5 | Error | JSON5 需 `configMapRef`（内联必须为有效 JSON） |
| JSON5 与 merge 模式 | Error | JSON5 与 `mergeMode: merge` 不兼容 |
| 无效 `checkInterval` | Error | 必须是 1h 到 168h 之间的有效 Go duration |
| 无效 `healthCheckTimeout` | Error | 必须是 2m 到 30m 之间的有效 Go duration |

<details>
<summary>警告级检查（部署会继续但带警告）</summary>

| 检查 | 行为 |
|-------|----------|
| 禁用 NetworkPolicy | 部署继续，带警告 |
| Ingress 无 TLS | 部署继续，带警告 |
| Chromium 无摘要固定 | 部署继续，带警告 |
| Ollama 无摘要固定 | 部署继续，带警告 |
| Web 终端无摘要固定 | 部署继续，带警告 |
| Ollama 以 root 运行 | 官方镜像要求； informational |
| 摘要固定时启用自动更新 | 摘要覆盖自动更新；更新不会应用 |
| 禁用 `readOnlyRootFilesystem` | 继续，带安全建议 |
| 未检测到 AI 提供商密钥 | 扫描 `env`/`envFrom` 中的已知提供商 env 变量 |
| 未知配置键 | 对 `spec.config.raw` 中未识别的顶层键发出警告 |

</details>

## 可观测性

### Prometheus 指标

| 指标 | 类型 | 说明 |
|--------|------|------|
| `openclaw_reconcile_total` | Counter | 按结果（成功/错误）的协调次数 |
| `openclaw_reconcile_duration_seconds` | Histogram | 协调延迟 |
| `openclaw_instance_phase` | Gauge | 每个实例的当前阶段 |
| `openclaw_instance_info` | Gauge | PromQL join 用的实例元数据（始终为 1） |
| `openclaw_instance_ready` | Gauge | 实例 Pod 是否就绪（1/0） |
| `openclaw_managed_instances` | Gauge | 托管实例总数 |
| `openclaw_resource_creation_failures_total` | Counter | 资源创建失败次数 |
| `openclaw_autoupdate_checks_total` | Counter | 按结果的自动更新版本检查次数 |
| `openclaw_autoupdate_applied_total` | Counter | 成功应用的自动更新次数 |
| `openclaw_autoupdate_rollbacks_total` | Counter | 触发的自动更新回滚次数 |

### ServiceMonitor

```yaml
spec:
  observability:
    metrics:
      enabled: true
      serviceMonitor:
        enabled: true
        interval: 15s
        labels:
          release: prometheus
```

### PrometheusRule（告警）

自动配置带 7 个告警及 runbook URL 的 PrometheusRule：

```yaml
spec:
  observability:
    metrics:
      prometheusRule:
        enabled: true
        labels:
          release: kube-prometheus-stack  # 必须匹配 Prometheus ruleSelector
        runbookBaseURL: https://openclaw.rocks/docs/runbooks  # 默认
```

告警：`OpenClawReconcileErrors`、`OpenClawInstanceDegraded`、`OpenClawSlowReconciliation`、`OpenClawPodCrashLooping`、`OpenClawPodOOMKilled`、`OpenClawPVCNearlyFull`、`OpenClawAutoUpdateRollback`

### Grafana 仪表板

自动配置两个 Grafana 仪表板 ConfigMap（通过 `grafana_dashboard: "1"` 标签发现）：

```yaml
spec:
  observability:
    metrics:
      grafanaDashboard:
        enabled: true
        folder: OpenClaw  # Grafana 文件夹（默认）
        labels:
          grafana_dashboard_instance: my-grafana  # 可选额外标签
```

仪表板：
- **OpenClaw Operator**：包含协调指标、实例表、工作队列和自动更新面板的集群概览
- **OpenClaw Instance**：包含 CPU、内存、存储、网络和 Pod 健康面板的每实例详情

### 自动扩缩（HPA）

启用水平 Pod 自动扩缩，根据 CPU 和内存利用率自动调整副本数：

```yaml
spec:
  availability:
    autoScaling:
      enabled: true
      minReplicas: 1
      maxReplicas: 10
      targetCPUUtilization: 80
      targetMemoryUtilization: 70  # 可选
```

启用后，Operator 创建以 StatefulSet 为目标的 `HorizontalPodAutoscaler`，并将 StatefulSet 的 replica 数设为 nil，由 HPA 管理扩缩。禁用自动扩缩时删除 HPA。

### 拓扑分布约束

在拓扑域（可用区、节点）间分布 Pod 以提高可用性：

```yaml
spec:
  availability:
    topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app.kubernetes.io/instance: my-instance
```

### Pod 注解

将额外注解合并到 StatefulSet Pod 模板。Operator 管理的键（`openclaw.rocks/config-hash`、`openclaw.rocks/secret-hash`）始终优先且不可覆盖。

可用于云提供商提示，例如防止 GKE Autopilot 驱逐长时间运行的智能体 Pod：

```yaml
spec:
  podAnnotations:
    cluster-autoscaler.kubernetes.io/safe-to-evict: "false"
```

阶段：`Pending` -> `Restoring` -> `Provisioning` -> `Running` | `Updating` | `BackingUp` | `Degraded` | `Failed` | `Terminating`

## 部署指南

平台特定部署指南：

- [AWS EKS](docs/deployment.md#aws-eks)
- [Google GKE](docs/deployment.md#google-gke)
- [Azure AKS](docs/deployment.md#azure-aks)
- [Kind（本地开发）](docs/deployment.md#kind)

## 开发

```bash
# 克隆并设置
git clone https://github.com/OpenClaw-rocks/k8s-operator.git
cd k8s-operator
go mod download

# 生成代码和清单
make generate manifests

# 运行测试
make test

# 运行 linter
make lint

# 在 Kind 集群上本地运行
kind create cluster
make install
make run
```

完整开发指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 路线图

- **v1.0.0**：API 升级至 `v1`、一致性测试套件、自动更新 semver 约束、HPA 集成、cert-manager 集成、多集群支持

详见 [路线图](ROADMAP.md)。

## 不想自托管？

[OpenClaw.rocks](https://openclaw.rocks) 提供全托管服务，起价 **15 欧元/月**。无需 Kubernetes 集群，安装、更新和 24/7 可用性由我们负责。

## 贡献

欢迎贡献。重大变更请先开 issue 讨论再提交 PR。指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 免责声明：AI 辅助开发

本仓库由人类与 [Claude Code](https://claude.ai/claude-code) 协作开发维护，包括编写代码、审查评论 issue、排查 bug 和合并 pull request。人类会审阅所有内容并作为最终把关，但 Claude 承担主要工作，从诊断到实现到 CI。

未来，本仓库可能完全自主运营，无论我们人类是否乐意。

## 许可证

Apache License 2.0，与 Kubernetes、Prometheus 和大多数 CNCF 项目相同。详见 [LICENSE](LICENSE)。
