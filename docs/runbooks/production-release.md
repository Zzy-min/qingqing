# 轻青生产发布与回滚

## 发布前

1. 从干净提交构建，CI 的 backend、integration、frontend、flutter、flutter-windows 全部通过。
2. 设置 `QINGQING_ENVIRONMENT=production`，并确认：
   - `QINGQING_ALLOW_LOCAL_USER=false`
   - `QINGQING_SESSION_SECRET` 与 `QINGQING_CREDENTIAL_KEY` 由密钥系统注入
   - `CORS_ORIGINS` 只包含正式 Web Origin
   - SMTP 已配置
   - Worker 使用 `redis` 或 `durable`，不得使用进程内 `background`
3. 执行 `python backend/scripts/db_migrate.py`，必须显示 schema version 1。
4. 访问 `/api/v1/ready`，必须返回 HTTP 200 和 `ready=true`。

## 备份

SQLite：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\sqlite_backup.py
```

PostgreSQL：

```bash
pg_dump --format=custom --file=qingqing-before-release.dump "$QINGQING_DATABASE_URL"
pg_restore --list qingqing-before-release.dump
```

对象存储需要启用 bucket versioning 或在发布前创建快照。Redis 队列不作为业务事实来源，任务与账本仍以数据库为准。

## 发布检查

1. 先部署一个实例，不立即扩大流量。
2. 检查 `/api/v1/health`、`/api/v1/ready`、登录邮件、创建任务、预算审批、Worker ACK、作品读取。
3. 观察 15 分钟错误率、队列 processing/dead 数量和任务账本，再逐步放量。

## 回滚

1. 停止新任务入口和 Worker 消费。
2. 回滚到上一版本镜像。
3. 如果本次发布没有写入不兼容数据，只回滚应用，不恢复数据库。
4. 必须恢复 SQLite 时：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\sqlite_backup.py `
  --restore path\to\backup.db --confirm-restore
```

该命令会先生成 `.pre-restore.bak`。PostgreSQL 恢复使用新的空数据库执行 `pg_restore`，验证后切换连接串；不要直接覆盖仍在提供服务的数据库。

## 事故边界

- Redis processing 中的任务超过 visibility timeout 会自动回队；超过最大尝试次数进入 `:dead`。
- 凭据或会话密钥疑似泄露时先轮换密钥，再恢复流量。
- readiness 失败时实例必须退出负载均衡，liveness 仍用于区分进程死亡与依赖故障。
