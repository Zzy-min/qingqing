# 轻青（qingqing）

供应商中立的个人创作 Agent 与多模态工作台，统一覆盖：
- 照片编辑（文生图 / 图生图 / 本地滤镜）
- 语音合成（TTS）
- 音乐生成（Music / Cover）
- 视频生成（Video）
- Token Plan 配额展示（文本 5 小时窗口 + 非文本日配额）

当前前端已升级为路由式工作台（非单页滚动）：
- `/dashboard` 工作台首页
- `/photo` 照片编辑
- `/voice` 语音合成
- `/music` 音乐生成
- `/video` 视频生成
- `/token` Token Plan
- `/usage` 用量分析
- `/help` 帮助文档
- `/api-docs` API 文档
- `/settings` 设置（含 API Key 配置）

## 技术栈
- Frontend: React 18 + Vite + TailwindCSS + Zustand
- Backend: FastAPI + httpx
- Model Access: MiniMax 中国站 Token Plan / API

## 关键接入规则（重要）
- `MINIMAX_API_KEY` 默认作为 Token Plan Key 使用。
- Token Plan Key 与按量付费 Key **不可混用**。
- REST Base（图片/语音/音乐/视频）默认：
  - `https://api.minimaxi.com/v1`
- Anthropic 兼容 Base（文本快速接入）默认：
  - `https://api.minimaxi.com/anthropic`
- Token Plan remains 查询默认：
  - `https://www.minimaxi.com/v1/token_plan/remains`
  - 可选 fallback（可配置）：`https://api.minimaxi.com/v1/token_plan/remains`

## 环境变量
在 `backend/.env` 中配置：

```bash
# 必填：MiniMax Token Plan Key 或按量 Key（二选一，不可混用）
MINIMAX_API_KEY=YOUR_MINIMAX_API_KEY

# 可选：跨域白名单（逗号分隔）
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# 可选：覆盖默认 base
MINIMAX_REST_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
MINIMAX_TOKEN_PLAN_BASE_URL=https://www.minimaxi.com/v1
MINIMAX_TOKEN_PLAN_FALLBACK_BASE_URL=https://api.minimaxi.com/v1

# 轻青 v1 必填：凭据加密与会话签名密钥（生产环境使用密钥管理服务注入）
QINGQING_CREDENTIAL_KEY=replace-with-a-long-random-secret
QINGQING_SESSION_SECRET=replace-with-another-long-random-secret
QINGQING_CREDENTIAL_KEY_VERSION=1

# 本地单用户开发才可开启；生产必须为 false
QINGQING_ALLOW_LOCAL_USER=true

# 可选：SQLite 路径。后续部署可用实现相同仓储接口的 PostgreSQL 适配器替换。
QINGQING_DATABASE_PATH=./qingqing.db
```

`/api/v1` 默认要求 `Authorization: Bearer <signed-session-token>`。只有显式设置
`QINGQING_ALLOW_LOCAL_USER=true` 时才允许无登录的本地单用户开发模式；客户端请求头不能指定用户身份或 VIP 权益。

## 通用本地部署（多用户复用）
- 本项目按“每个本地实例一个 Key”运行：每位使用者在自己的机器/环境中配置 `backend/.env` 里的 `MINIMAX_API_KEY` 即可。
- 不同使用者之间不要共享同一个 `.env` 文件或 API Key。
- 前端不会保存或展示密钥；额度与模型可用性由当前后端实例所配置的 Key 决定。
- 若在设置页填写 API Key，会保存在浏览器本地并通过请求头临时覆盖，不会写入服务器文件。

## 启动方式
### 后端
```bash
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

默认访问：
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8001`

## Flutter 三端客户端（轻青）

共享工程位于 `apps/qingqing_flutter`，目标平台为 Web、Windows、Android。所有平台复用邮箱登录、
模型选择、Agent Run、预算审批、高阶模式与 BYOK API 层。

```powershell
# 本机使用 Puro 管理 Flutter stable
puro -e stable flutter analyze
puro -e stable flutter test

# Web
puro -e stable flutter build web --release `
  --dart-define=API_BASE_URL=https://your-api.example.com

# Android
puro -e stable flutter build apk --release `
  --dart-define=API_BASE_URL=https://your-api.example.com

# Windows（需要 Visual Studio Desktop development with C++ workload）
puro -e stable flutter build windows --release `
  --dart-define=API_BASE_URL=https://your-api.example.com
```

- Android/Windows 会话令牌保存在系统安全存储；Flutter Web 不做跨浏览器重启的持久令牌保存。
- Android release 必须使用真实 HTTPS API 地址，不要使用示例域名。
- 当前本机已经验证 Web release 和 Android release；Windows 工具链需要管理员安装 Visual Studio C++ workload。

### 轻青 v1 安全运行模式

- 生产环境只使用 `/api/v1/*` Agent 接口；旧 `/api/*` 会绕过 Agent 路由快照与额度账本，因此默认不挂载。
- 仅为本机旧工作台联调时，可同时设置 `QINGQING_ALLOW_LOCAL_USER=true` 和 `QINGQING_ENABLE_LEGACY_API=true`。本机免登录只对回环请求生效，不能用于生产部署。
- 账户偏好可通过 `GET/PATCH /api/v1/me/preferences` 跨 Web、Windows、Android 同步；任务列表使用 `GET /api/v1/agent/runs`。
- 生产必须配置 `QINGQING_SESSION_SECRET`、`QINGQING_CREDENTIAL_KEY` 和 SMTP 参数，并使用 HTTPS API 地址。

## 修改后重启与一致性检查（TTS）
若修改了后端代码，请先重启后端实例再验证，避免旧进程继续提供旧逻辑：

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

建议重启后执行一次检查，确认已加载官方音色列表：

```bash
curl --location 'http://127.0.0.1:8001/api/tts/voices'
```

通过标准：
- `source` 为 `official`
- `voices` 数量显著大于 fallback（建议 `>100`）

## API 概览
- `GET /api/health`
- `GET /api/token-plan/remains`（新增）
- `POST /api/generate`
- `POST /api/process`
- `POST /api/tts/synthesize`
- `GET /api/tts/voices`
- `POST /api/music/generate`
- `POST /api/music/cover`
- `GET /api/music/task/{task_id}`
- `POST /api/video/generate`
- `POST /api/video/task`
- `GET /docs`（Swagger UI 文档页）
- `GET /openapi.json`（OpenAPI JSON 规范，不是可视页面）

可选请求头（前端设置页会自动注入）：
- `X-MiniMax-API-Key`
  - 有值时：本次请求优先使用该 Key
  - 空值时：回退后端 `.env` 的 `MINIMAX_API_KEY`

音乐异步任务说明：
- 当 `/api/music/generate` 或 `/api/music/cover` 仅返回 `task_id` 时，请继续调用 `GET /api/music/task/{task_id}` 轮询结果。

## Token Plan remains 返回格式
`GET /api/token-plan/remains` 返回：
- `success`
- `text_window_usage`
- `text_window_limit`
- `non_text_daily_usage`
- `non_text_daily_limit`
- `non_text_daily_items`（按模型的日配额明细，含 `category/usage/limit/remaining`）
- `raw`（原始透传）

## 用量分析说明
- `/usage` 页面采用浏览器本地行为埋点统计（最近调用、趋势、模块分布）。
- 该统计用于操作分析，不作为官方计费口径。

## 安全说明
- 文档与示例中禁止放真实密钥。
- 若密钥曾经泄露（包括提交到仓库、截图、日志），请立即在 MiniMax 控制台轮换并废弃旧 Key。
