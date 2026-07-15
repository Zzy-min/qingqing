# 轻青项目身份重命名设计

## 目标

将仓库与本地工程的**项目身份**从历史名 `minimax-photo-agent` / `minimax-multimodal` / `MiniMax Photo Agent` 统一为 **轻青 / qingqing**，覆盖 GitHub 仓库名、本地目录名、npm 包名、API 标题与文档标题。

## 命名约定

| 层级 | 旧名 | 新名 |
|------|------|------|
| 产品中文名 | MiniMax Multimodal Workbench / Photo Agent | 轻青 |
| 产品英文/slug | minimax-photo-agent / minimax-multimodal | qingqing |
| GitHub 仓库 | Zzy-min/minimax-multimodal | Zzy-min/qingqing |
| 本地目录 | projects/minimax-photo-agent | projects/qingqing |
| npm package | minimax-photo-agent | qingqing |
| FastAPI title | MiniMax Photo Agent API | 轻青 API |
| 临时目录前缀 | minimax-photo-agent | qingqing |

## 明确不改

以下是 **MiniMax 供应商集成**，不是项目名，保持不变：

- 环境变量 `MINIMAX_*`、请求头 `X-MiniMax-API-Key`
- 模块 `services/minimax.py`、`minimax_config.py`、`gateway/adapters/minimax_adapter.py`
- 模型 ID（如 `MiniMax-Hailuo-*`）与官方 API 域名
- Flutter 已使用的 `qingqing` / `com.qingqing.qingqing` / 标签「轻青」

## 验收

- 代码与文档中不再出现作为**项目身份**的 `minimax-photo-agent`、`minimax-multimodal`、`MiniMax Photo Agent`、`MiniMax Multimodal Workbench`
- GitHub 仓库与 remote 指向 `qingqing`
- 本地根目录名为 `qingqing`
- 后端/前端既有测试仍通过
