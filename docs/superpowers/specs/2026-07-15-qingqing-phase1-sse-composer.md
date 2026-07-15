# Phase 1：SSE 事件流 + 统一创作入口

## 目标

1. 执行过程通过 SSE 推送 `step_started` / `delta` / `step_completed` / `run_completed|failed`。
2. React Chat 优先消费 SSE，终态仍兼容轮询。
3. Dashboard 增加创作 Composer；Voice/Music/Video（及 Photo AI）默认走 AgentRun。

## API

- `GET /api/v1/agent/runs/{run_id}/events` — `text/event-stream`，鉴权同其它 v1 接口。
- 首包 `snapshot`；已结束则立即 `run_completed`/`run_failed` 并关闭。

## 边界

- 不引入 Redis 事件总线（进程内总线即可）
- 不移除 Multimodal.jsx 文件（模态页不再引用即可）
- Flutter SSE 可后续跟进；本阶段以 React 为主
