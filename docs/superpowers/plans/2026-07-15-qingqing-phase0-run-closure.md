# Phase 0 实施计划

1. 在 `qingqingApi.js` 增加 `pollAgentRun` / `formatRunMessage` 工具。
2. 改造 `Chat.jsx`：planned/approve 后轮询并写回 assistant 消息；更新 `Chat.test.jsx`。
3. 改造 Flutter `AgentPage`：监听 controller 轮询结果并展示 output。
4. README 补充当前能力边界（真结果闭环 / 尚无真流式）。
5. 运行 backend pytest、frontend vitest、flutter test。
