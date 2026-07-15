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
| 多端 | React Web 工作台 + Flutter（Web / Windows / Android） |

### 当前能力边界（Phase 0–2）

| 已具备 | 尚未具备（后续阶段） |
|--------|----------------------|
| 创建 Run 后**轮询终态**并展示模型输出 | 跨会话记忆 / MCP 工具（Phase 3） |
| **SSE** `GET /api/v1/agent/runs/{id}/events` | 耐久 Worker / PostgreSQL（Phase 4） |
| **Planner + Skills** 多步配方与 step retry | Flutter SSE / Skills 对齐 |
| 预算超限审批后再执行并取回结果 | |
| Dashboard Composer + 模态页 AgentRun | |
| 路由透明（模型、原因、费用区间） | |
| 生产默认仅 `/api/v1` | |

改造蓝图见 `docs/superpowers/specs/`。

## 仓库结构

```
qingqing/
├── backend/                 # FastAPI
│   ├── qingqing_v1/         # /api/v1 轻青 Agent、鉴权、权益、凭据
│   ├── gateway/             # 多供应商适配（legacy 可选挂载）
│   └── services/            # 供应商能力实现（含 MiniMax 等）
├── frontend/                # React 18 + Vite 工作台
├── apps/qingqing_flutter/   # Flutter 三端客户端
└── docs/superpowers/        # 设计 / 计划 / 评审
```

## 技术栈

- **Backend:** FastAPI、httpx、SQLite（可替换仓储）、cryptography
- **Frontend:** React 18、Vite、TailwindCSS、Zustand
- **Clients:** Flutter（Web / Windows / Android）
- **模型接入:** 多供应商注册表；平台 Key 与用户 BYOK 可组合路由

## 快速开始

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

# 本地开发：允许本机回环免登录（生产必须 false）
QINGQING_ALLOW_LOCAL_USER=true

# 仅本机旧工作台联调时开启；会挂载会绕过账本的 /api/*
# QINGQING_ENABLE_LEGACY_API=true

# 可选
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3001
QINGQING_DATABASE_PATH=./qingqing.db

# 生产登录邮件（本地无 SMTP 时，request-code 可能返回 dev_code）
# QINGQING_SMTP_HOST=
# QINGQING_SMTP_PORT=587
# QINGQING_SMTP_USERNAME=
# QINGQING_SMTP_PASSWORD=
# QINGQING_SMTP_FROM=noreply@qingqing.local
```

启动：

```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

- API 文档：http://127.0.0.1:8001/docs  
- 健康检查：http://127.0.0.1:8001/api/health（需开启 legacy 时才有 `/api/health`；否则以 `/docs` 与 `/api/v1/*` 为准）

### 2. React 工作台

```bash
cd frontend
npm install
npm run dev
```

默认：http://localhost:5173

主要路由：`/dashboard`、`/chat`、`/photo`、`/voice`、`/music`、`/video`、`/token`、`/usage`、`/settings`、`/login` 等。

### 3. Flutter 客户端

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
# Windows 需要 VS Desktop C++ workload
puro -e stable flutter build windows --release --dart-define=API_BASE_URL=https://your-api.example.com
```

- Android / Windows：会话令牌走系统安全存储  
- Flutter Web：不做跨浏览器重启的持久令牌  
- Release 请勿使用示例域名

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
