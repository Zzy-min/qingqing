# 轻青（qingqing）多模态工作台 Spec

## 1. 目标
1. 将“照片编辑”并入全站多模态工作台，取消“photo / multimodal”双页面分裂。
2. 按 MiniMax 中国站 Token Plan 文档对齐调用方式，避免沿用旧基座与旧配额路径。
3. 提升交互体验：统一导航、统一反馈、统一加载与失败重试链路。

## 2. 后端设计
### 2.1 统一配置
- 新增 `services/minimax_config.py`：
  - `MINIMAX_REST_BASE_URL` 默认 `https://api.minimaxi.com/v1`
  - `MINIMAX_ANTHROPIC_BASE_URL` 默认 `https://api.minimaxi.com/anthropic`
  - `MINIMAX_TOKEN_PLAN_BASE_URL` 默认 `https://www.minimaxi.com/v1`
  - `MINIMAX_TOKEN_PLAN_FALLBACK_BASE_URL` 默认 `https://api.minimaxi.com/v1`
- 统一 `MINIMAX_API_KEY` 读取与基础日志输出。

### 2.2 Token Plan 配额接口
- 新增服务：`services/token_plan.py`
- 新增路由：`GET /api/token-plan/remains`
- 路由行为：
  - 优先请求 primary remains endpoint
  - 必要时 fallback
  - 透传 `raw` 原始返回
  - 统一错误映射：401/429/5xx/网络错误

### 2.3 兼容性原则
- 保持以下既有接口不破坏：
  - `/api/generate`
  - `/api/process`
  - `/api/tts/*`
  - `/api/music/*`
  - `/api/video/*`

## 3. 前端设计
### 3.1 单入口工作台
- `App.jsx` 统一为单入口导航：
  - 照片编辑
  - 语音合成
  - 音乐生成
  - 视频生成

### 3.2 照片编辑成为一级模块
- 保留原图输入 / 工具区 / 处理结果三段式流程。
- 在同一导航层级与 TTS、音乐、视频并列。

### 3.3 统一反馈体系
- 替换阻断式 `alert`。
- 使用：
  - 顶部 toast（全局）
  - 模块内 inline error（局部）
  - 重试按钮（失败可恢复）

### 3.4 Token Plan 卡片
- 调用 `/api/token-plan/remains`
- 展示两类核心额度：
  - 文本（5 小时窗口）
  - 非文本（日配额）

### 3.5 视频结果双路径渲染
- 同时支持：
  - `video_data`
  - `video_url`

## 4. 响应式策略
- 桌面：三栏高效编辑。
- 移动端：单列分步布局，保持 CTA 可见与路径完整。

## 5. 文档与安全
- README 与实现保持一致，移除未落地 `speech-to-text` 描述。
- 所有密钥示例必须使用占位符。
- 如果历史曾暴露密钥，必须立即轮换旧密钥。

