# MiniMax 多模态控制台 → 多供应商多模态控制台 升级设计

## 概述

将现有的 MiniMax 单供应商多模态控制台升级为支持多供应商的统一多模态工作台。采用 OpenAI-Compatible 网关模式，后端做薄代理层，前端精简为单页面工作台 + 命令面板切换模型。

## 目标

1. 支持所有具备多模态能力的主流模型供应商（OpenAI、Google Gemini、国产模型、MiniMax 可选）
2. 模型切换采用命令面板（Cmd+K / `/` 命令）方式，类似 Claude Code 的 switch 机制
3. UI 从 10 个路由页面精简为 1 个工作台页面 + 1 个设置页面
4. 后端从 MiniMax 硬编码改为统一网关路由 + 可插拔适配器

## 供应商策略

### 核心供应商（第一批）

| 供应商 | 能力覆盖 |
|--------|----------|
| OpenAI | chat (GPT-4o), image (DALL·E 3), tts (TTS-1), vision |
| Google Gemini | chat (Gemini 2.5 Pro), vision, image (Imagen, 预留) |
| 通义千问 (Qwen) | chat (Qwen-VL-Max), image, tts, vision |
| 文心一言 (ERNIE) | chat, image |
| 智谱 (Zhipu/GLM) | chat, vision, image (CogView-3) |

### 可选供应商

| 供应商 | 能力覆盖 |
|--------|----------|
| MiniMax | chat, image, tts, music, video（保留完整适配器，但不再是默认） |

## 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────┐ │
│  │ Workbench │  │ Settings  │  │ Command Palette  │ │
│  │  (主页)    │  │  (设置)    │  │  (Cmd+K 切换)    │ │
│  └───────────┘  └───────────┘  └──────────────────┘ │
│           │                                         │
│    ┌──────┴──────┐                                  │
│    │ Unified API │  /api/chat  /api/image  /api/tts │
│    │   Client    │  /api/music /api/video            │
│    └──────┬──────┘                                  │
└───────────┼─────────────────────────────────────────┘
            │
┌───────────┼─────────────────────────────────────────┐
│           ▼      Backend (FastAPI Thin Proxy)       │
│  ┌────────────────┐                                 │
│  │  Router Layer  │  统一入口，解析 model_id          │
│  └───────┬────────┘                                 │
│          │                                          │
│  ┌───────▼────────┐                                 │
│  │ Model Registry │  model_id → provider + caps     │
│  └───────┬────────┘                                 │
│          │                                          │
│  ┌───────▼──────────────────────────────────────┐   │
│  │         Provider Adapters (可插拔)             │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │   │
│  │  │ OpenAI │ │ Gemini │ │ Qwen   │ │ MiniMax│ │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Provider Adapter 层

### 抽象基类

```python
from abc import ABC, abstractmethod
from enum import Enum
from typing import AsyncIterator

class Capability(str, Enum):
    CHAT = "chat"
    IMAGE = "image"
    TTS = "tts"
    MUSIC = "music"
    VIDEO = "video"

class ProviderAdapter(ABC):
    """每个供应商的适配器基类"""

    provider_id: str                          # 如 "openai", "google", "qwen"
    capabilities: set[Capability]             # 该供应商支持的能力
    request_timeout: int = 60               # 单次请求超时（秒），chat 默认 60s，image 可覆盖为 120s

    def get_auth_headers(self, api_key: str, base_url: str | None = None) -> dict[str, str]:
        """返回供应商 API 请求所需的认证 Header。
        默认实现适用于 Bearer Token 认证（OpenAI/Gemini/Qwen/智谱）。
        ERNIE 等非标准认证的 adapter 覆盖此方法，在内部处理 token 交换。
        base_url 可选，覆盖 .env 中的默认值（用于代理/私有部署）。"""
        return {"Authorization": f"Bearer {api_key}"}

    @abstractmethod
    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        """文本对话（流式）"""

    @abstractmethod
    async def image(self, request: ImageRequest) -> ImageResponse:
        """图片生成"""

    async def tts(self, request: TTSRequest) -> bytes:
        """语音合成 — 不支持则抛 CapabilityNotSupported"""
        raise CapabilityNotSupported(self.provider_id, "tts")

    async def music(self, request: MusicRequest) -> MusicResponse:
        """音乐生成 — 不支持则抛 CapabilityNotSupported"""
        raise CapabilityNotSupported(self.provider_id, "music")

    async def video(self, request: VideoRequest) -> VideoResponse:
        """视频生成 — 不支持则抛 CapabilityNotSupported"""
        raise CapabilityNotSupported(self.provider_id, "video")
```

### 适配器目录结构

```
backend/
  adapters/
    __init__.py              # 自动发现 + 注册所有 adapter
    base.py                  # ProviderAdapter ABC + 异常定义
    openai_adapter.py        # OpenAI: chat + image + tts
    gemini_adapter.py        # Gemini: chat + image
    qwen_adapter.py          # 通义千问: chat + image + tts
    ernie_adapter.py         # 文心一言: chat + image
    zhipu_adapter.py         # 智谱: chat + image
    minimax_adapter.py       # MiniMax: chat + image + tts + music + video
```

### 自动发现机制

```python
# backend/adapters/__init__.py
import importlib
import pkgutil
from .base import ProviderAdapter

_registry: dict[str, ProviderAdapter] = {}

def discover_adapters():
    """扫描 adapters/ 目录，自动注册所有 ProviderAdapter 子类"""
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        if module_name.startswith("_") or module_name == "base":
            continue
        module = importlib.import_module(f".{module_name}", __package__)
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, ProviderAdapter) and obj is not ProviderAdapter:
                instance = obj()
                _registry[instance.provider_id] = instance

def get_adapter(provider_id: str) -> ProviderAdapter:
    return _registry[provider_id]

def list_adapters() -> dict[str, ProviderAdapter]:
    return dict(_registry)
```

## Model Registry（模型注册表）

### 数据结构

```python
from dataclasses import dataclass

@dataclass
class ModelEntry:
    provider: str                    # provider_id
    display_name: str                # UI 显示名
    capabilities: set[Capability]    # 支持的能力（chat/image/tts/music/video）
    context_window: int = 0          # 上下文窗口大小
    supports_vision: bool = False    # chat 的子能力：是否支持图片输入
    supports_streaming: bool = True  # 是否支持流式
```

**关于 vision 的定位**：`supports_vision` 是 `chat` 能力的子能力标记，不是独立的 capability。当 `supports_vision=True` 且当前 capability 为 `chat` 时，前端 ChatPanel 的输入框自动显示"上传图片"按钮。vision 不影响 Tab 显示，不影响路由逻辑。

### 注册表内容

```python
MODEL_REGISTRY: dict[str, ModelEntry] = {
    # ── OpenAI ──
    "openai:gpt-4o": ModelEntry(
        provider="openai",
        display_name="GPT-4o",
        capabilities={Capability.CHAT},
        context_window=128000,
        supports_vision=True,
    ),
    "openai:gpt-4o-mini": ModelEntry(
        provider="openai",
        display_name="GPT-4o Mini",
        capabilities={Capability.CHAT},
        context_window=128000,
        supports_vision=True,
    ),
    "openai:dall-e-3": ModelEntry(
        provider="openai",
        display_name="DALL·E 3",
        capabilities={Capability.IMAGE},
    ),
    "openai:tts-1": ModelEntry(
        provider="openai",
        display_name="TTS-1",
        capabilities={Capability.TTS},
    ),

    # ── Google Gemini ──
    "google:gemini-2.5-pro": ModelEntry(
        provider="google",
        display_name="Gemini 2.5 Pro",
        capabilities={Capability.CHAT},
        context_window=1000000,
        supports_vision=True,
    ),
    "google:gemini-2.5-flash": ModelEntry(
        provider="google",
        display_name="Gemini 2.5 Flash",
        capabilities={Capability.CHAT},
        context_window=1000000,
        supports_vision=True,
    ),
    "google:imagen-3": ModelEntry(
        provider="google",
        display_name="Imagen 3",
        capabilities={Capability.IMAGE},
    ),

    # ── 通义千问 ──
    "qwen:qwen-vl-max": ModelEntry(
        provider="qwen",
        display_name="通义千问 VL Max",
        capabilities={Capability.CHAT},
        supports_vision=True,
    ),
    "qwen:qwen-turbo": ModelEntry(
        provider="qwen",
        display_name="通义千问 Turbo",
        capabilities={Capability.CHAT},
    ),
    "qwen:wanx-v1": ModelEntry(
        provider="qwen",
        display_name="通义万相",
        capabilities={Capability.IMAGE},
    ),

    # ── 文心一言 ──
    "ernie:ernie-4.0": ModelEntry(
        provider="ernie",
        display_name="文心一言 4.0",
        capabilities={Capability.CHAT},
    ),

    # ── 智谱 ──
    "zhipu:glm-4": ModelEntry(
        provider="zhipu",
        display_name="GLM-4",
        capabilities={Capability.CHAT},
        supports_vision=True,
    ),
    "zhipu:cogview-3": ModelEntry(
        provider="zhipu",
        display_name="CogView-3",
        capabilities={Capability.IMAGE},
    ),

    # ── MiniMax（可选）──
    "minimax:abab6.5s-chat": ModelEntry(
        provider="minimax",
        display_name="MiniMax ABAB 6.5s",
        capabilities={Capability.CHAT},
    ),
    "minimax:image-01": ModelEntry(
        provider="minimax",
        display_name="MiniMax Image-01",
        capabilities={Capability.IMAGE},
    ),
    "minimax:video-01": ModelEntry(
        provider="minimax",
        display_name="MiniMax Video-01",
        capabilities={Capability.VIDEO},
    ),
    "minimax:music-01": ModelEntry(
        provider="minimax",
        display_name="MiniMax Music-01",
        capabilities={Capability.MUSIC},
    ),
    "minimax:tts-01": ModelEntry(
        provider="minimax",
        display_name="MiniMax TTS-01",
        capabilities={Capability.TTS},
    ),
}
```

### Model ID 格式

`{provider_id}:{model_name}`，如 `openai:gpt-4o`、`qwen:qwen-vl-max`

## 请求/响应 Schema

### Chat Schema

```python
# backend/schemas/chat.py
from pydantic import BaseModel
from typing import Literal

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str | list[ContentPart]  # str 或多模态内容列表

class ContentPart(BaseModel):
    type: Literal["text", "image_url"]
    text: str | None = None
    image_url: str | None = None  # 支持 vision 的模型可用

class ChatRequest(BaseModel):
    model: str                      # "openai:gpt-4o"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = True

class ChatChunk(BaseModel):
    """流式响应的每个 chunk"""
    model: str
    delta: str                      # 本次增量文本
    finish_reason: str | None = None  # "stop" | "length" | null
    usage: TokenUsage | None = None   # 仅最后一个 chunk 包含

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int

class ChatResponse(BaseModel):
    """非流式响应（stream=False 时）"""
    model: str
    content: str                       # 完整回复文本
    finish_reason: str                 # "stop" | "length"
    usage: TokenUsage
```

### Image Schema

```python
# backend/schemas/image.py
class ImageRequest(BaseModel):
    model: str                      # "openai:dall-e-3"
    prompt: str
    size: str = "1024x1024"         # "256x256" | "512x512" | "1024x1024"
    quality: str = "standard"       # "standard" | "hd"
    n: int = 1                      # 生成数量
    style: str | None = None        # 供应商特定参数

class ImageResponse(BaseModel):
    model: str
    images: list[ImageData]         # 通常 1 张，可扩展为多张

class ImageData(BaseModel):
    url: str | None = None          # 远程 URL
    b64_json: str | None = None     # base64 数据（二选一）
    revised_prompt: str | None = None  # DALL·E 会改写 prompt
```

### TTS Schema

```python
# backend/schemas/tts.py
class TTSRequest(BaseModel):
    model: str                      # "openai:tts-1"
    input: str                      # 要合成的文本
    voice: str = "alloy"            # 声音选项（供应商特定）
    speed: float = 1.0              # 语速 0.25-4.0
    response_format: str = "mp3"    # "mp3" | "opus" | "aac" | "flac"

# TTS 响应直接返回音频二进制流（bytes），不走 JSON
```

### Music Schema

```python
# backend/schemas/music.py
class MusicRequest(BaseModel):
    model: str                      # "minimax:music-01"
    prompt: str                     # 音乐描述
    duration: int = 30              # 时长（秒）
    style: str | None = None        # 风格
    lyrics: str | None = None       # 歌词（如有）

class MusicResponse(BaseModel):
    model: str
    audio_url: str | None = None    # 完成后的音频 URL
    audio_b64: str | None = None    # base64 音频数据
    duration: float                 # 实际时长（秒）
```

### Video Schema

```python
# backend/schemas/video.py
class VideoRequest(BaseModel):
    model: str                      # "minimax:video-01"
    prompt: str                     # 视频描述
    image_url: str | None = None    # 图生视频时的参考图
    duration: int = 5               # 时长（秒）
    resolution: str = "720p"        # "480p" | "720p" | "1080p"

class VideoResponse(BaseModel):
    model: str
    video_url: str | None = None    # 完成后的视频 URL
    cover_url: str | None = None    # 封面图 URL
    duration: float                 # 实际时长（秒）
```

### Task Schema

```python
# backend/schemas/task.py
from enum import Enum

class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

class TaskStatus(BaseModel):
    task_id: str
    status: TaskStatusEnum
    progress: float | None = None   # 0.0-1.0
    result: dict | None = None      # 完成时包含结果（MusicResponse/VideoResponse）
    error: str | None = None        # 失败时的错误信息
    created_at: float               # unix timestamp
    expires_at: float               # 过期时间
```

## 后端路由

### 统一端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 文本对话（流式 SSE） |
| `/api/image` | POST | 图片生成 |
| `/api/tts` | POST | 语音合成（返回音频流） |
| `/api/music` | POST | 音乐生成（异步任务） |
| `/api/video` | POST | 视频生成（异步任务） |
| `/api/models` | GET | 获取模型注册表列表 |
| `/api/tasks/{task_id}` | GET | 轮询异步任务状态 |
| `/api/health` | GET | 健康检查 |

### 流式协议（SSE）

`/api/chat` 使用 Server-Sent Events 流式返回：

**正常流**：
```
data: {"model":"openai:gpt-4o","delta":"Hello","finish_reason":null,"usage":null}

data: {"model":"openai:gpt-4o","delta":" world","finish_reason":null,"usage":null}

data: {"model":"openai:gpt-4o","delta":"","finish_reason":"stop","usage":{"prompt_tokens":10,"completion_tokens":2}}
```

**流中错误**：
```
data: {"error":"Rate limit exceeded","code":"rate_limit"}
```
发送 error event 后关闭连接。

**客户端取消**：前端通过 `AbortController.abort()` 断开连接，后端检测到客户端断开后取消对供应商 API 的请求（透传 abort signal）。

### API Key 认证策略

**优先级规则**：
1. 后端 `.env` 中配置的 API Key 为**默认 Key**
2. 前端可通过请求 Header `X-Provider-Key: {key}` 传入自定义 Key（覆盖后端默认值）
3. 前端设置页配置的 Key 存 localStorage，每次请求时通过 Header 传入

**安全约束**：
- 前端 Key **不经过后端存储**，仅在请求时透传
- 如果后端 `.env` 未配置该供应商的 Key 且前端未传入，返回 `401 {"error": "API key not configured for provider: {provider_id}"}`
- 设置页对已配置 Key 的供应商显示"已配置（来自 .env）"标签，允许用户覆盖

**自定义 Base URL**：
- 前端通过请求 Header `X-Provider-Base-URL: {url}` 传入自定义 base URL
- 优先级：Header 传入 > .env 中的 `*_BASE_URL` > adapter 内置默认值
- 用途：代理、私有部署、自定义端点
- 设置页为每个供应商提供可选的 Base URL 输入框，存 localStorage

### 路由流程

```
请求进入
  → 路由层解析 model_id（如 "openai:gpt-4o"）
  → 查 MODEL_REGISTRY 获取 ModelEntry
  → 校验 capability（该模型是否支持请求的能力）
  → 获取 API Key：优先 X-Provider-Key Header，回退 .env
  → 通过 provider_id 获取 ProviderAdapter
  → adapter 将标准请求转换为供应商原生格式
  → 调用供应商 API
  → adapter 将响应转换为标准格式
  → 返回前端
```

**错误处理**：
- model_id 不在注册表 → `404 {"error": "Model not found: {model_id}", "code": "model_not_found", "provider": null}`
- 模型不支持请求的能力 → `422 {"error": "Model {model_id} does not support capability: {cap}", "code": "capability_not_supported", "provider": "{provider_id}"}`
- API Key 缺失 → `401 {"error": "API key not configured for provider: {provider_id}", "code": "auth_missing", "provider": "{provider_id}"}`
- 供应商 API 调用失败 → `502 {"error": "Provider API error: {detail}", "code": "provider_error", "provider": "{provider_id}"}`
- ERNIE token 交换失败（secret 过期/网络错误）→ `401 {"error": "ERNIE auth failed: {detail}", "code": "auth_failed", "provider": "ernie"}`

### 异步任务处理（Music/Video）

**任务存储**：内存字典（单实例部署足够，无需 Redis）

```python
# backend/task_store.py
_task_store: dict[str, TaskStatus] = {}

TASK_TTL = 3600       # 任务结果保留 1 小时
TASK_TIMEOUT = 300     # 任务执行超时 5 分钟
```

**生命周期**：
1. `POST /api/music` → 创建任务，status=pending，返回 `task_id`
2. 后台异步调用供应商 API → status=processing
3. 完成 → status=completed，result 包含结果数据
4. 失败 → status=failed，error 包含错误信息
5. 超时（5 分钟无响应）→ status=failed，error="Task timed out"
6. 过期（1 小时后）→ status=expired，自动清理

**轮询**：
```
GET /api/tasks/{task_id}
→ 200 {"task_id":"xxx","status":"processing","progress":0.5,...}
→ 200 {"task_id":"xxx","status":"completed","result":{...},...}
→ 200 {"task_id":"xxx","status":"failed","error":"..."}
→ 404 {"error":"Task not found or expired"}
```

### 统一错误响应格式

所有非流式端点（`/api/image`、`/api/tts`、`/api/music`、`/api/video`）的错误响应统一为：

```json
{
  "error": "Human-readable error message",
  "code": "error_code",
  "provider": "openai"
}
```

通过 FastAPI 全局异常处理中间件统一处理，adapter 内部抛出的异常自动转换为此格式。

### `supports_streaming` 字段说明

`ModelEntry.supports_streaming` 标记该供应商是否原生支持流式响应。当 `False` 时，adapter 内部将供应商的完整响应 buffer 后逐块 yield 为 `AsyncIterator[ChatChunk]`，对前端透明。当前所有核心供应商均支持流式，此字段为预留。

### 后端目录结构（重构后）

```
backend/
  main.py                    # FastAPI app 入口
  config.py                  # 配置管理（从 .env 读取）
  schemas/
    chat.py                  # ChatRequest, ChatChunk
    image.py                 # ImageRequest, ImageResponse
    tts.py                   # TTSRequest
    music.py                 # MusicRequest, MusicResponse
    video.py                 # VideoRequest, VideoResponse
    task.py                  # TaskStatus
  adapters/
    __init__.py              # 自动发现 + 注册
    base.py                  # ProviderAdapter ABC
    openai_adapter.py
    gemini_adapter.py
    qwen_adapter.py
    ernie_adapter.py
    zhipu_adapter.py
    minimax_adapter.py
  routers/
    chat.py                  # POST /api/chat
    image.py                 # POST /api/image
    tts.py                   # POST /api/tts
    music.py                 # POST /api/music
    video.py                 # POST /api/video
    models.py                # GET /api/models
    tasks.py                 # GET /api/tasks/{task_id}
  registry/
    models.py                # MODEL_REGISTRY 定义
```

## 前端 UI 设计

### 路由精简

**当前**（10 个路由）→ **目标**（2 个路由 + 1 个覆盖层）：

- `/` → 工作台（唯一主页面）
- `/settings` → 设置页面
- `Cmd+K` → 命令面板覆盖层（非路由）

**删除的路由**：`/dashboard`、`/photo`、`/voice`、`/music`、`/video`、`/token`、`/usage`、`/help`、`/api-docs`

### 工作台布局

```
┌─────────────────────────────────────────────────────────┐
│  ┌──────────┐  ┌──────────────────────────────────────┐ │
│  │          │  │  顶栏: [Provider:Model] [能力切换Tab]  │ │
│  │  侧边栏   │  │  ─────────────────────────────────── │ │
│  │          │  │                                      │ │
│  │ • 会话1   │  │          工作台主区域                  │ │
│  │ • 会话2   │  │     (根据选中能力展示不同面板)          │ │
│  │ • 会话3   │  │                                      │ │
│  │          │  │  Chat → 对话面板                      │ │
│  │          │  │  Image → 图片生成面板                  │ │
│  │          │  │  TTS → 语音面板                       │ │
│  │          │  │  Music → 音乐面板                     │ │
│  │          │  │  Video → 视频面板                     │ │
│  │          │  │                                      │ │
│  │ ──────── │  │  ─────────────────────────────────── │ │
│  │ ⚙ 设置   │  │  底部: 输入框 + 发送                   │ │
│  └──────────┘  └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 命令面板（Cmd+K）

输入框按 `/` 或全局 `Cmd+K` 弹出命令面板。搜索逻辑：按 `display_name`、`provider_id`、`model_id` 三个字段做模糊匹配（不区分大小写），按 provider 分组展示。

```
┌─────────────────────────────────────┐
│  🔍 搜索模型...                      │
│  ─────────────────────────────────  │
│  OpenAI                             │
│    GPT-4o          [chat] 👁        │
│    GPT-4o Mini     [chat] 👁        │
│    DALL·E 3        [image]          │
│    TTS-1           [tts]            │
│  Google                             │
│    Gemini 2.5 Pro  [chat] 👁        │
│    Gemini 2.5 Flash [chat] 👁       │
│    Imagen 3        [image]          │
│  通义千问                            │
│    Qwen-VL-Max     [chat] 👁        │
│    通义万相          [image]          │
│  智谱                               │
│    GLM-4           [chat] 👁        │
│    CogView-3       [image]          │
│  MiniMax                            │
│    ABAB 6.5s       [chat]           │
│    Video-01        [video]          │
└─────────────────────────────────────┘
```

### 能力 Tab 切换

顶栏的 Tab 根据当前模型的 `capabilities` 动态显示：

- 如果选中 `openai:gpt-4o`（capabilities: {chat}, supports_vision: true）→ 显示 Chat Tab，ChatPanel 输入框带"上传图片"按钮
- 如果选中 `openai:dall-e-3`（capabilities: {image}）→ 只显示 Image Tab
- 如果选中 `minimax:abab6.5s-chat`（capabilities: {chat}）→ 只显示 Chat Tab，无图片上传按钮

注意：一个模型通常只对应一种能力，Tab 的主要作用是在**同一供应商内切换不同能力的模型**时提供快捷入口。

### 删除路由的处理

旧路由中的功能处理方式：
- `/dashboard` → 合并入工作台 `/`
- `/photo`, `/voice`, `/music`, `/video` → 合并入工作台的能力 Tab 面板
- `/token` → 移除（Token Plan 是 MiniMax 特有概念，多供应商后无意义）
- `/usage` → Phase 4 以新形式回归（跨供应商统一用量统计）
- `/help`, `/api-docs` → 移除（简化 UI，文档可通过 README 或外部链接提供）
- `/settings` → 保留，精简为 API Key 配置 + 默认模型选择

### 前端目录结构（重构后）

```
src/
  App.jsx                    # 路由定义（/ 和 /settings）
  stores/
    appStore.js              # Zustand 单 store
  api/
    client.js                # 统一 API 客户端（/api/chat, /api/image 等）
    models.js                # 获取模型列表
  components/
    Layout.jsx               # 主布局（侧边栏 + 主区域）
    Sidebar.jsx              # 会话列表 + 设置入口
    TopBar.jsx               # 当前模型显示 + 能力 Tab
    CommandPalette.jsx        # Cmd+K 命令面板
    CapabilityPanel.jsx       # 能力面板容器（根据 Tab 切换子面板）
    panels/
      ChatPanel.jsx           # 对话面板
      ImagePanel.jsx          # 图片生成面板
      TTSPanel.jsx            # 语音面板
      MusicPanel.jsx          # 音乐面板
      VideoPanel.jsx          # 视频面板
    common/
      ToastStack.jsx          # 通知
      HistoryPanel.jsx        # 历史记录（可折叠）
  pages/
    Workbench.jsx             # 工作台页面
    Settings.jsx              # 设置页面
```

## Session 数据模型

```typescript
interface Session {
  id: string                        // uuid
  title: string                     // 会话标题（自动取首条消息前 20 字符）
  capability: Capability            // "chat" | "image" | "tts" | "music" | "video"
  model: string                     // 创建时的 model_id，如 "openai:gpt-4o"
  messages: SessionMessage[]
  createdAt: number                 // unix timestamp
  updatedAt: number                 // unix timestamp
}

interface SessionMessage {
  id: string                        // uuid
  role: "user" | "assistant" | "system"
  content: string                   # 文本内容
  images?: string[]                 # 图片 URL/base64（vision 输入或生成结果）
  audioUrl?: string                 # TTS/音乐结果
  videoUrl?: string                 # 视频结果
  metadata?: Record<string, any>    # 供应商特定元数据
  createdAt: number
}
```

**存储策略**：
- 会话数据存 localStorage（`sessions` key），JSON 序列化
- 单个会话消息上限 500 条，超出后丢弃最早的非 system 消息
- 无后端持久化（本地单用户部署模型）
- **base64 数据不存 Session**：图片/音频/视频的 base64 数据只在内存中用于渲染，Session 持久化时只存储 URL 或丢弃（由 adapter 返回的 URL 指向供应商临时存储）
- **超限行为**：localStorage 接近 5MB 上限时，提示用户清理旧会话，或自动丢弃最旧的会话

**会话恢复行为**：点击侧边栏已有会话时，`currentModel` 和 `currentCapability` 恢复为该 Session 创建时的值（Session 内存储的 `model` 和 `capability`），而非保持当前全局状态。这样用户切换会话时上下文一致。

## 状态管理

Zustand 单 store：

```javascript
const useAppStore = create((set, get) => ({
  // 当前状态
  currentModel: 'openai:gpt-4o',
  currentCapability: 'chat',

  // 会话管理
  sessions: [],                     // Session[]
  currentSessionId: null,

  // 模型注册表（从后端获取）
  models: {},                       // { "openai:gpt-4o": ModelEntry, ... }

  // 设置
  apiKeys: {},        // provider → key（存 localStorage）
  baseUrls: {},       // provider → 自定义 base URL

  // Actions
  switchModel: (modelId) => {
    const model = get().models[modelId];
    if (!model) return;
    set({
      currentModel: modelId,
      currentCapability: [...model.capabilities][0],
    });
  },

  switchCapability: (cap) => set({ currentCapability: cap }),

  // 会话操作
  createSession: () => {
    const session = {
      id: crypto.randomUUID(),
      title: '新会话',
      capability: get().currentCapability,
      model: get().currentModel,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    set({ sessions: [...get().sessions, session], currentSessionId: session.id });
    // 持久化到 localStorage
    localStorage.setItem('sessions', JSON.stringify([...get().sessions]));
    return session;
  },

  deleteSession: (id) => {
    const sessions = get().sessions.filter(s => s.id !== id);
    const currentId = get().currentSessionId === id
      ? (sessions[0]?.id ?? null)
      : get().currentSessionId;
    set({ sessions, currentSessionId: currentId });
    localStorage.setItem('sessions', JSON.stringify(sessions));
  },

  // API Key 管理
  setApiKey: (provider, key) => {
    const keys = { ...get().apiKeys, [provider]: key };
    set({ apiKeys: keys });
    localStorage.setItem('apiKeys', JSON.stringify(keys));
  },
}));
```

## 配置管理

### 后端 .env

```
# OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# Google Gemini
GOOGLE_API_KEY=xxx

# 通义千问
QWEN_API_KEY=xxx
QWEN_BASE_URL=https://dashscope.aliyuncs.com/api/v1

# 文心一言
ERNIE_API_KEY=xxx
ERNIE_SECRET_KEY=xxx

# 智谱
ZHIPU_API_KEY=xxx

# MiniMax（可选）
MINIMAX_API_KEY=xxx
MINIMAX_GROUP_ID=xxx
```

### 前端设置页

设置页提供：
- 每个供应商的 API Key 配置（存 localStorage，不上传后端）
- 可选：自定义 Base URL（用于代理或私有部署）
- 默认模型选择（每个能力的默认模型）

## 迁移策略

1. **后端渐进式迁移**：先保留现有 MiniMax 路由，新增统一 `/api/*` 端点，两套并行直到前端切换完成
2. **前端重构**：从 10 个页面精简为 2 个页面，组件逐步迁移
3. **适配器优先级**：先实现 OpenAI adapter（覆盖最广），再 Gemini，再国产模型
4. **MiniMax 适配器**：从现有代码提取，封装为标准 adapter

## 实现优先级

### Phase 1：基础框架
- 后端 adapter 基类 + registry + 路由层
- 前端工作台布局 + 命令面板
- OpenAI adapter（chat + image）

### Phase 2：核心供应商
- Gemini adapter
- 通义千问 adapter
- 前端能力面板（Chat + Image）

### Phase 3：扩展供应商
- 文心/智谱 adapter
- MiniMax adapter 提取
- TTS/Music/Video 面板

### Phase 4：完善
- 命令面板搜索优化
- 异步任务轮询优化（Music/Video）
- 统一错误处理中间件 + 重试策略
- Provider 级别超时配置

### Phase 5：扩展
- 跨供应商统一使用量统计（替代旧 /usage）
- 用户自定义模型注册（通过设置页添加自定义 model）

## 参考来源

- **LobeChat** (lobehub/lobe-chat)：model-bank + model-runtime 分离模式，能力标记系统
- **Chatbox** (chatboxai/chatbox)：注册表 + 抽象基类模式，Vercel AI SDK 集成
- **Open-WebUI** (open-webui/open-webui)：双路由器模式，SSE 流统一
- **Vercel AI SDK** (vercel/ai)：Provider 抽象层设计参考
