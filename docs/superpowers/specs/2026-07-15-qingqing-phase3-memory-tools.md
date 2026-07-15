# Phase 3：记忆与受控工具

## 目标

1. **会话/作品记忆**：Run 完成后写入摘要；下次创作可检索注入 prompt。
2. **用户风格偏好**：偏好字段（风格、禁忌、常用语气）参与注入。
3. **内置工具**：list_artifacts / search_memory / list_models / list_skills / estimate_cost，全程审计。
4. **MCP 白名单骨架**：仅登记与查询允许的 server；默认不发起任意网络写。

## API

- `GET/POST/DELETE /api/v1/memory`
- `GET /api/v1/tools`
- `POST /api/v1/tools/invoke`
- `GET /api/v1/tools/calls`（审计）
- `GET /api/v1/mcp/servers`（白名单）

## 边界

- 不做完整向量库与企业 RAG
- 不做任意 MCP 自动安装
- 不接 Telegram/飞书渠道
