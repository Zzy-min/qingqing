# 轻青模型选择、权益与 BYOK 设计

## 目标

将现有多供应商工作台升级为供应商中立的“轻青”个人创作 Agent 基座。普通用户默认使用 Auto，也能手选权限内模型；VIP 权益与高阶 API 能力正交；高阶用户可安全托管内置供应商凭据或 OpenAI 兼容端点。

## 边界

- 本阶段交付现有 FastAPI + React Web 的可运行基座。
- Flutter Web、Windows、Android 客户端属于后续工程，不在当前仓库中伪装成交付。
- 首版采用单用户开发身份，但所有领域对象保留用户归属，API 不信任客户端传入的 plan 或 entitlement。
- 不支持任意协议插件、脚本、HTTP/内网端点或受保护请求头覆盖。

## 领域设计

- `UserProfile`：`plan` 与 `advanced_mode_enabled` 独立。
- `Entitlement`：由服务端按 plan 计算模型、额度、并发、队列与功能标志。
- `ModelDescriptor`：统一供应商、能力、输入输出模态、成本/质量/速度、来源与可用性。
- `RoutingPreference`：`platform_first`、`byok_first`、`byok_only`。
- `RoutingMode`：`auto`、`preferred`、`locked`。
- `Credential`：只返回元数据和尾号；密钥加密后存储，永不回显。
- `CustomModel`：仅允许 HTTPS OpenAI 兼容端点，保存和调用前都做 SSRF 检查。
- `AgentRun`：保存目标、路由快照、费用区间、选择原因和状态，避免后续注册表变化改写历史。

## 安全设计

- API Key 使用服务端主密钥派生的认证加密；缺失生产密钥时仅允许显式开发密钥。
- URL 校验拒绝回环、私网、链路本地、组播、保留地址、用户信息段、非 HTTPS 与危险端口；DNS 解析结果同样校验。
- 凭据测试禁止自动重定向，日志和响应不包含密钥。
- entitlement、模型访问和高阶模式均在服务端重新校验。

## 用户体验

- Chat 首选项为 `Auto · 推荐`，普通列表只呈现任务适配、速度、消耗和不可用原因。
- 模型技术参数收起；结果处展示实际模型、来源、选择原因和费用区间。
- 设置页默认隐藏 API 管理；用户主动开启高阶模式并阅读风险说明后显示。
- 不出现 VIP 购买、续费或营销入口。

## 验收

- 后端 API、路由、安全边界和前端关键交互有自动化测试。
- 现有 API 保持可用；新接口统一位于 `/api/v1`。
- 前端构建、后端测试、安全扫描与宽窄 viewport 视觉检查通过。
