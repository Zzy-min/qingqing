# Phase 0：AgentRun 结果闭环

## 目标

消除 Chat「只创建任务、不展示真实输出」的断裂，使用户在 React 与 Flutter 上都能完成：

创建 Run →（预算审批）→ 执行 → 轮询终态 → 展示 invocation 输出 / 失败原因。

## 边界

- 不引入 SSE/WebSocket（Phase 1）
- 不改多步 Planner / 工作流
- 不迁移 Photo/Music/Video 页
- 保留现有 `/api/v1/agent/runs` 契约；客户端主动轮询

## 行为

1. `planned` 立即 `POST .../execute`，进入 `running` 后轮询 `GET .../runs/{id}`。
2. `awaiting_approval` 用户确认后同样 execute + 轮询。
3. 终态：`completed | failed | cancelled | paused`。
4. `completed` 时优先展示 chat invocation 的 `output.content`；失败展示 `error_code`。
5. 轮询有上限与退避，避免无限请求。

## 验收

- 前端单测覆盖「执行后轮询得到模型文本」
- Flutter Agent 页在完成后展示输出
- 后端既有 execute 测试仍通过
