# Phase 4：生产化底座（v1）

## 目标

1. **Worker 抽象**：统一入队执行 Run（默认 BackgroundTasks，可切换 inline）。
2. **Artifact 存储接口**：本地目录后端；远程产物经受控代理下载。
3. **密钥版本**：支持 `QINGQING_CREDENTIAL_KEY` + 可选 previous key 解密。
4. **可观测性**：请求 ID 中间件 + Run 执行结构化日志。
5. **健康检查**：`GET /api/v1/health` 无需鉴权。

## 边界

- 本阶段不强制依赖 Redis/PostgreSQL 安装
- S3/MinIO 仅预留接口与配置键
- 不做完整 KMS 云服务对接
