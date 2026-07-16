# 轻青（qingqing）

供应商中立的个人创作 Agent：用统一路由选择模型，在聊天、图片、语音、音乐、视频之间完成创作，并支持平台额度与用户自带密钥（BYOK）。

**仓库：** [github.com/Zzy-min/qingqing](https://github.com/Zzy-min/qingqing)

## 能力一览

| 能力 | 说明 |
|------|------|
| Agent Run | 目标驱动任务：路由预览、预算审批、执行、重试/取消 |
| 模型选择 | Auto / 偏好 / 锁定；服务端计算权益与可用性 |
| 多模态 | 文本、图片、TTS、音乐、视频 |
| 高阶 BYOK | 加密托管供应商密钥；OpenAI 兼容自定义端点（HTTPS + SSRF 校验） |
| 多端 | Flutter 用户端（Web / Windows / Android）+ React 旧版内部工作台 |

### 当前能力边界（Phase 0–4）

| 已具备（含生产加深） | 可选后续 |
|--------|----------|
| 结果闭环 + SSE + Planner/Skills + 记忆/工具 | 企业级向量库 / 云 KMS 服务 |
| **PostgreSQL** 适配器（`QINGQING_DATABASE_URL`） | 多区域多副本运维 |
| **Redis Worker** 模式 + `scripts/redis_worker.py` | Celery 生态 |
| **S3/MinIO** Artifact 后端 | CDN 分发策略 |
| 密钥 previous 轮换 + key_version | 硬件 HSM |
| 中文记忆检索（分词/二元组） | 嵌入向量检索 |
| **MCP 白名单 HTTPS 调用**（allowlisted tools） | 全协议 MCP stdio |
| Flutter Skills/计划预览/多步进度 | Flutter 设置记忆页完整化 |
| Worker / 远程产物代理 / 请求 ID / health | |

改造蓝图见 `docs/superpowers/specs/`。

## 仓库结构

```
qingqing/
├── backend/                 # FastAPI
│   ├── qingqing_v1/         # /api/v1 轻青 Agent、鉴权、权益、凭据
│   ├── gateway/             # 多供应商适配（legacy 可选挂载）
│   └── services/            # 供应商能力实现（含 MiniMax 等）
├── frontend/                # React 旧版内部工作台（非用户端发布入口）
├── apps/qingqing_flutter/   # Flutter 统一用户端：Web / Windows / Android
└── docs/superpowers/        # 设计 / 计划 / 评审
```

## 技术栈

- **Backend:** FastAPI、httpx、SQLite（可替换仓储）、cryptography
- **User Client:** Flutter（Web / Windows / Android，共用产品信息架构）
- **Legacy Workbench:** React 18、Vite、TailwindCSS、Zustand（仅内部迁移/诊断）
- **模型接入:** 多供应商注册表；平台 Key 与用户 BYOK 可组合路由

## 可选依赖（Docker）

Windows 本地开发可直接运行：

```powershell
.\dev-up.ps1
```

该脚本只会向被 Git 忽略的 `backend/.env` 追加缺失的本地配置，生成随机会话/凭据密钥，不会覆盖已有供应商密钥；随后启动 Compose、安装集成依赖并运行 PG / Redis / MinIO / MailHog 闭环测试。

本地一键起 PostgreSQL / Redis / MinIO：

```bash
docker compose up -d
```

集成测试（服务可用时）：

```bash
cd backend
pip install "psycopg[binary]" redis boto3
set QINGQING_RUN_INTEGRATION=1
python -m pytest tests/test_optional_integration.py -q
```

### 1. 后端

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

在 `backend/.env` 中配置（**不要提交真实密钥**）：

```bash
# 平台默认供应商 Key（示例：MiniMax Token Plan / 按量 Key，勿混用）
MINIMAX_API_KEY=YOUR_MINIMAX_API_KEY

# 轻青 v1：凭据加密与会话签名（生产请用密钥管理服务注入）
QINGQING_CREDENTIAL_KEY=replace-with-a-long-random-secret
QINGQING_SESSION_SECRET=replace-with-another-long-random-secret
QINGQING_CREDENTIAL_KEY_VERSION=1
# 可选：轮换后的旧密钥（逗号分隔），用于解密历史凭据
# QINGQING_CREDENTIAL_KEY_PREVIOUS=old-key-material

# Worker：background（默认）| inline | durable | redis
# QINGQING_WORKER_MODE=background
# QINGQING_DURABLE_QUEUE_DIR=./artifacts/worker_jobs
# QINGQING_REDIS_URL=redis://127.0.0.1:6379/0
# QINGQING_REDIS_QUEUE_KEY=qingqing:run_jobs
# QINGQING_JOB_MAX_ATTEMPTS=3
# QINGQING_JOB_VISIBILITY_TIMEOUT=300
# 仅开发降级使用；生产 Redis 故障默认失败关闭
# QINGQING_WORKER_FALLBACK_TO_BACKGROUND=false

# 数据库：默认 SQLite；PostgreSQL 示例
# QINGQING_DATABASE_PATH=./qingqing.db
# QINGQING_DATABASE_URL=postgresql://user:pass@localhost:5432/qingqing

# 产物存储：local（默认）| s3 | minio
# QINGQING_ARTIFACT_BACKEND=local
# QINGQING_ARTIFACT_ROOT=./artifacts
# QINGQING_S3_BUCKET=qingqing
# QINGQING_S3_ENDPOINT=http://127.0.0.1:9000
# QINGQING_S3_ACCESS_KEY=
# QINGQING_S3_SECRET_KEY=
# QINGQING_S3_PREFIX=qingqing/artifacts

# MCP 白名单（JSON 数组）。仅 enabled + HTTPS + allowlisted tools 可调用
# QINGQING_MCP_SERVERS=[{"name":"demo","url":"https://mcp.example.com","enabled":true,"allowed_tools":["echo"]}]

# 本地开发：允许本机回环免登录（生产必须 false）
QINGQING_ALLOW_LOCAL_USER=true

# production 不会隐式允许 localhost，必须显式列出正式 Web Origin
# QINGQING_ENVIRONMENT=production

# 仅本机旧工作台联调时开启；会挂载会绕过账本的 /api/*
# QINGQING_ENABLE_LEGACY_API=true

# 可选
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3001
QINGQING_DATABASE_PATH=./qingqing.db

# 登录邮件 SMTP（未配置时：仅 loopback + ALLOW_LOCAL_USER 返回 dev_code）
# 本地联调：docker compose 的 MailHog → SMTP 1025 / UI http://127.0.0.1:8025
# QINGQING_SMTP_HOST=127.0.0.1
# QINGQING_SMTP_PORT=1025
# QINGQING_SMTP_TLS=none          # starttls | ssl | none（1025/25/2525 默认 none）
# QINGQING_SMTP_USERNAME=
# QINGQING_SMTP_PASSWORD=
# QINGQING_SMTP_FROM=noreply@qingqing.local
# QINGQING_SMTP_SUBJECT=轻青登录验证码
# 生产示例：HOST=smtp.example.com PORT=587 TLS=starttls + 账号密码
```

可选依赖联调（需 `docker compose up -d`）：

```bash
# backend venv 内
pip install "psycopg[binary]" redis boto3
# PowerShell: $env:QINGQING_RUN_INTEGRATION="1"
pytest tests/test_smtp_login.py tests/test_optional_integration.py -q
```

联调报告见 `docs/superpowers/reviews/2026-07-15-compose-smtp-integration.md`。

启动：

```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

- API 文档：http://127.0.0.1:8001/docs  
- 健康检查：http://127.0.0.1:8001/api/health（需开启 legacy 时才有 `/api/health`；否则以 `/docs` 与 `/api/v1/*` 为准）

### 2. Web 产品边界

Flutter 是轻青唯一的用户端产品实现，Web、Windows 和 Android 共用
`apps/qingqing_flutter`。`frontend/` 中的 React 应用仅保留为旧能力迁移和内部诊断
工作台，不作为用户端继续设计，也不会被后端静默选为替代页面。

后端静态入口由 `QINGQING_WEB_CLIENT` 显式控制：

- `flutter`（默认）：只服务 `apps/qingqing_flutter/build/web`
- `react`：仅在明确需要旧版内部工作台时启用
- `none`：只启动 API，不挂载 Web 静态页面

发布 Flutter Web：

```powershell
cd apps/qingqing_flutter
puro -e stable flutter build web --release --dart-define=API_BASE_URL=https://your-api.example.com
cd ..\..\backend
$env:QINGQING_WEB_CLIENT="flutter"
uvicorn main:app --host 0.0.0.0 --port 8001
```

#### React 旧版内部工作台

```bash
cd frontend
npm install
npm run dev
```

默认：http://localhost:5173

主要路由：`/dashboard`、`/chat`、`/photo`、`/voice`、`/music`、`/video`、`/token`、`/usage`、`/settings`、`/login` 等。

### 3. Flutter 用户端

工程：`apps/qingqing_flutter`

```powershell
cd apps/qingqing_flutter

# 本机可用 Puro 管理 Flutter stable
puro -e stable flutter pub get
puro -e stable flutter analyze
puro -e stable flutter test

# Web
puro -e stable flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8001

# 发布构建请使用 HTTPS API
puro -e stable flutter build web --release --dart-define=API_BASE_URL=https://your-api.example.com
puro -e stable flutter build apk --release --dart-define=API_BASE_URL=https://your-api.example.com
# Windows 需要 VS Desktop C++ workload + ATL 组件
.\tool\build-windows-release.ps1 -ApiBaseUrl https://your-api.example.com
```

- Android / Windows：会话令牌走系统安全存储  
- Flutter Web：不做跨浏览器重启的持久令牌  
- Release 请勿使用示例域名
- Windows 原生构建必须安装 `Microsoft.VisualStudio.Component.VC.ATL`；
  `flutter_secure_storage_windows` 会使用 `atlstr.h`

## API 约定（轻青 v1）

生产默认只暴露 **`/api/v1/*`**。旧 `/api/*` 会绕过 Agent 路由快照与额度账本，**默认不挂载**。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/email/request-code` | 发送登录验证码 |
| POST | `/api/v1/auth/email/verify` | 校验并签发 Bearer 会话 |
| GET | `/api/v1/me/entitlements` | 当前权益 |
| GET/PATCH | `/api/v1/me/preferences` | 跨端偏好同步 |
| GET | `/api/v1/models` | 模型目录与可用性 |
| POST | `/api/v1/model-routes/preview` | 路由预览 |
| POST | `/api/v1/agent/runs` | 创建 Agent Run |
| GET | `/api/v1/agent/runs` | 任务列表 |
| POST | `/api/v1/agent/runs/{id}/approve` | 预算审批 |
| POST | `/api/v1/agent/runs/{id}/execute` | 执行 |
| GET | `/api/v1/agent/runs/{id}/events` | SSE 进度（snapshot / delta / step / 终态） |
| GET | `/api/v1/skills` | 内置创作 Skills 目录 |
| POST | `/api/v1/agent/plans/preview` | 预览多步计划（不落库） |
| POST | `/api/v1/agent/runs/{id}/steps/{step_id}/retry` | 单步重试 |
| GET | `/api/v1/health` | 探活（无需鉴权） |
| GET | `/api/v1/ready` | 数据库、Worker、存储与生产配置就绪检查 |
| GET/POST/DELETE | `/api/v1/memory` | 跨会话记忆与笔记 |
| GET | `/api/v1/tools` | 内置工具目录 + MCP 白名单元数据 |
| POST | `/api/v1/tools/invoke` | 调用内置工具（审计） |
| GET | `/api/v1/tools/calls` | 工具调用审计列表 |
| GET | `/api/v1/artifacts/{id}/content` | 本地产物或远程 HTTPS 受控代理 |
| GET/POST/… | `/api/v1/credentials` | BYOK 凭据（密钥不回显） |
| GET/POST/… | `/api/v1/custom-models` | 自定义 OpenAI 兼容端点 |
| GET | `/api/v1/artifacts` | 作品 / 产物 |
| GET | `/api/v1/billing/ledger` | 额度账本 |

鉴权：`Authorization: Bearer <signed-session-token>`。  
客户端**不能**用请求头自报 plan / VIP；权益一律服务端计算。

本地旧工作台联调：

```bash
QINGQING_ALLOW_LOCAL_USER=true
QINGQING_ENABLE_LEGACY_API=true
```

二者同时开启后，才会挂载历史 `/api/*`（仅建议本机回环使用）。

## 安全要点

- 示例与文档中**禁止**写入真实 API Key / 会话密钥  
- 生产必须配置 `QINGQING_SESSION_SECRET`、`QINGQING_CREDENTIAL_KEY`，使用 HTTPS，关闭 `QINGQING_ALLOW_LOCAL_USER`  
- 凭据加密存储，接口只返回元数据与尾号  
- 自定义端点仅允许 HTTPS，并做公网 URL / DNS 校验  
- 密钥若曾泄露，请立即在对应供应商控制台轮换  

## 测试

```bash
# 后端（推荐使用项目 venv）
cd backend
.\.venv\Scripts\python.exe -m pytest tests/ -q

# 前端
cd frontend
npm test

# Flutter
cd apps/qingqing_flutter
puro -e stable flutter test
```

## 文档

设计与实施记录见 `docs/superpowers/`：

- `specs/` 设计说明  
- `plans/` 实施计划  
- `reviews/` 评审与验收痕迹  

## 许可与使用

个人 / 本地实例按各自配置的供应商 Key 使用；请勿在多人之间共享 `.env` 或 API Key。
