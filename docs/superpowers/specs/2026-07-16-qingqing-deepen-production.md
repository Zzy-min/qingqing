# 生产加深：PG / Redis / S3 / KMS / FTS / MCP / Flutter

## 范围

1. PostgreSQL 仓储适配器（`QINGQING_DATABASE_URL`）
2. Redis 队列 Worker 模式（`QINGQING_WORKER_MODE=redis`）
3. S3/MinIO 对象存储（`QINGQING_S3_*`）
4. 凭据 `key_version` 写入与 previous 解密
5. 记忆检索加深（SQLite FTS5 可选）
6. MCP 白名单受控 HTTP 工具调用
7. Flutter：Skills / 记忆入口 / 步骤状态

## 原则

- 未配置可选依赖时**自动回退**，默认测试与本地 SQLite 不受影响
- 安全边界不放宽（SSRF、密钥不回显、鉴权）
