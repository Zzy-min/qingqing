# 真实 Compose 联调报告 + SMTP 登录闭环

**日期：** 2026-07-15  
**仓库：** `qingqing`  
**范围：** `docker-compose.yml` 基础设施联调、可选集成测试、SMTP/MailHog 登录闭环  
**结论：** **通过（有证据）**

---

## 1. 目标

1. 在本机真实拉起 compose 依赖（Postgres / Redis / MinIO / MailHog），不只做 mock。
2. 跑可选集成测试（`QINGQING_RUN_INTEGRATION=1`）。
3. 验证登录验证码 SMTP 闭环：发信 → 收件箱可读 → 用邮件中的码完成 verify → 拿到 token 访问受保护 API。

---

## 2. 环境与启动

### 2.1 Compose 服务

```text
docker compose up -d
```

| 服务 | 镜像 | 宿主端口 | 健康/状态 |
|------|------|----------|-----------|
| postgres | postgres:16-alpine | 5432 | healthy / accepting connections |
| redis | redis:7-alpine | 6379 | healthy / PONG |
| minio | minio/minio:latest | 9000, 9001 | live 200 |
| minio-init | minio/mc:latest | — | Exited 0（bucket `qingqing` 创建） |
| mailhog | mailhog/mailhog:v1.0.1 | 1025 (SMTP), 8025 (UI/API) | Up / API v2 200 |

### 2.2 联调凭据（仅本地 compose，非生产）

| 变量 | 本地值 |
|------|--------|
| Postgres | `postgresql://qingqing:qingqing@127.0.0.1:5432/qingqing` |
| Redis | `redis://127.0.0.1:6379/0` |
| MinIO | endpoint `http://127.0.0.1:9000`, AK/SK `minioadmin`/`minioadmin`, bucket `qingqing` |
| SMTP (MailHog) | host `127.0.0.1`, port `1025`, TLS `none` |

生产请改用真实密钥与托管 SMTP，**禁止**把生产 secret 提交进仓库。

---

## 3. 代码面（本轮）

| 路径 | 作用 |
|------|------|
| `backend/qingqing_v1/smtp_mail.py` | 独立 SMTP 发送：`starttls` / `ssl` / `none`；端口 1025/25/2525 默认 `none` |
| `backend/qingqing_v1/router.py` | `POST /auth/email/request-code` 返回 `delivery.{delivered,mode}`；loopback+local 才附 `dev_code` |
| `docker-compose.yml` | 增加 `mailhog` 服务 |
| `backend/tests/test_smtp_login.py` | 单元 + 可选 MailHog 闭环（解码 base64 正文） |
| `backend/tests/test_optional_integration.py` | PG / Redis / MinIO 可选 live 测试 |

### 3.1 登录闭环行为

```text
request-code
  → store.save_auth_code(code_hash)
  → send_login_email(...)   # SMTP 已配置则真实投递
  → response.delivery
  → (仅 loopback + QINGQING_ALLOW_LOCAL_USER) dev_code

verify
  → 校验 code_hash
  → access_token
```

**安全约定：**

- 未配置 SMTP 且非 local loopback → `503`
- 生产路径不得依赖 `dev_code`；闭环证明码必须来自邮件正文（MailHog API）
- SMTP 失败对外只暴露异常类型名，不泄漏凭据

---

## 4. 验证证据

### 4.1 依赖安装（venv）

```text
pip install "psycopg[binary]" redis boto3
```

（`requirements.txt` 中仍为注释 optional，按需安装。）

### 4.2 集成测试命令

```powershell
cd backend
$env:QINGQING_RUN_INTEGRATION="1"
$env:QINGQING_ALLOW_LOCAL_USER="true"
.\.venv\Scripts\python.exe -m pytest tests/test_smtp_login.py tests/test_optional_integration.py -q --tb=short
```

### 4.3 结果（2026-07-15）

```text
.......                                                                  [100%]
7 passed in 9.77s
```

| 测试 | 结果 | 说明 |
|------|------|------|
| `test_smtp_send_login_email_none_tls` | PASS | FakeSMTP，无 TLS |
| `test_request_code_delivery_metadata_local` | PASS | `local_skip` + `dev_code` |
| `test_login_closed_loop_with_dev_code` | PASS | 本地 dev 码登录 |
| `test_mailhog_smtp_closed_loop` | PASS | **真实 SMTP → MailHog → decode → verify → entitlements** |
| `test_postgres_roundtrip_if_available` | PASS | preferences + run claim |
| `test_redis_enqueue_if_available` | PASS | enqueue + consume |
| `test_minio_s3_if_available` | PASS | S3 put/get `hello-minio` |

### 4.4 MailHog 联调发现与修复

**问题：** `EmailMessage` 对较长中文正文使用 `Content-Transfer-Encoding: base64`；MailHog `Content.Body` 返回未解码 base64，旧测试用 `\b(\d{6})\b` 直接扫 Body 会漏码。

**修复：** `test_smtp_login.py` 增加 `_decode_mailhog_body` / `_extract_login_code_from_mailhog`，支持 base64 与 quoted-printable，并优先匹配「验证码是 XXXXXX」。

**直连抽检：**

- `DELETE /api/v1/messages` → 200  
- `POST request-code` → 202，`delivery.delivered=true`, `mode=none`  
- `GET /api/v2/messages` → 可解析出 6 位码并与 `dev_code` 一致  

---

## 5. 本地一键复现清单

```powershell
# 1) 基础设施
cd C:\Users\Lenovo\projects\qingqing
docker compose up -d
docker compose ps

# 2) 后端可选依赖
cd backend
.\.venv\Scripts\python.exe -m pip install "psycopg[binary]" redis boto3

# 3) 集成测试
$env:QINGQING_RUN_INTEGRATION="1"
$env:QINGQING_ALLOW_LOCAL_USER="true"
.\.venv\Scripts\python.exe -m pytest tests/test_smtp_login.py tests/test_optional_integration.py -q

# 4) 手工 SMTP 联调（可选，API 进程）
$env:QINGQING_SMTP_HOST="127.0.0.1"
$env:QINGQING_SMTP_PORT="1025"
$env:QINGQING_SMTP_TLS="none"
$env:QINGQING_ALLOW_LOCAL_USER="true"
# 启动 uvicorn 后：
# POST /api/v1/auth/email/request-code
# 打开 http://127.0.0.1:8025 查看邮件
# POST /api/v1/auth/email/verify
```

---

## 6. 已知限制 / 后续

1. **可选依赖默认不装** — CI 若要强制 live 测试，需 compose service + pip optional + 环境变量。  
2. **MailHog 仅开发** — 生产用真实 SMTP（`starttls`/`ssl` + 账号密码）。  
3. **dev_code** 仅 loopback + `QINGQING_ALLOW_LOCAL_USER`；生产关闭 local 模式。  
4. **minio-init** 为一次性任务，重启 compose 通常幂等（`mc mb -p || true`）。  
5. 本报告不覆盖前端/ Flutter 登录 UI 的 E2E；后端 API 闭环已证。

---

## 7. 判定

| 项 | 状态 |
|----|------|
| Compose 五服务可用 | ✅ |
| Postgres / Redis / MinIO 集成测试 | ✅ |
| SMTP 单元 + local 闭环 | ✅ |
| MailHog 真实 SMTP 登录闭环 | ✅ |
| 无 secret 入库 | ✅（本地 compose 默认值仅文档） |

**整体：Compose 联调 + SMTP 登录闭环 — 完成。**

### 附录：全量后端回归

```text
QINGQING_RUN_INTEGRATION=1 pytest tests/ -q
87 passed in 14.07s
```
