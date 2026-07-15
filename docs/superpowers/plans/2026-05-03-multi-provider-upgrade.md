# Multi-Provider Multimodal Console — Revised Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade MiniMax single-provider console to a multi-provider multimodal workbench with unified gateway routing, preserving all existing functionality.

**Architecture:** Dual-track gradual — existing routes/services untouched, new gateway layer added in parallel at `backend/gateway/*`. Frontend keeps all existing routes, adds `/chat` page and provider/model dropdowns.

**Tech Stack:** React 18, Vite 5, TailwindCSS 3.4, Zustand, FastAPI, httpx, Pydantic v2, PyJWT

**Baseline verified:** Backend `36 passed, 9 skipped`, frontend `vite build` passes.

**Principles:**
- Old interfaces zero-break: `/api/generate`, `/api/process`, `/api/tts/*`, `/api/music/*`, `/api/video/*`, `/api/token-plan/remains` all preserved
- New gateway at `backend/gateway/*`, old `backend/api/` and `backend/services/` untouched
- 6 providers all implemented: OpenAI, Gemini, Qwen, ERNIE, Zhipu, MiniMax
- Unconfigured providers show `enabled=false` in `/api/models`
- Settings page + module dropdown for model switching; Cmd+K deferred
- `model` format: `provider:model_id`

---

## Chunk 1: Gateway Skeleton — Schemas, Adapter Base, Registry

### Task 1: Gateway Directory Structure + Schemas

**Files:**
- Create: `backend/gateway/__init__.py`
- Create: `backend/gateway/schemas/__init__.py`
- Create: `backend/gateway/schemas/common.py`
- Create: `backend/gateway/schemas/chat.py`
- Create: `backend/gateway/schemas/image.py`
- Create: `backend/gateway/schemas/tts.py`
- Create: `backend/gateway/schemas/music.py`
- Create: `backend/gateway/schemas/video.py`
- Create: `backend/gateway/schemas/task.py`

- [ ] **Step 1: Create gateway __init__.py**

```python
# backend/gateway/__init__.py
```

- [ ] **Step 2: Create common schema**

```python
# backend/gateway/schemas/common.py
from pydantic import BaseModel

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int

class UnifiedResponse(BaseModel):
    success: bool = True
    model: str | None = None
    provider: str | None = None
    data: dict | None = None
    task: dict | None = None
    error: dict | None = None
```

- [ ] **Step 3: Create chat schema**

```python
# backend/gateway/schemas/chat.py
from pydantic import BaseModel
from typing import Literal
from .common import TokenUsage

class ContentPart(BaseModel):
    type: Literal["text", "image_url"]
    text: str | None = None
    image_url: str | None = None

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str | list[ContentPart]

class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = True

class ChatChunk(BaseModel):
    model: str
    delta: str
    finish_reason: str | None = None
    usage: TokenUsage | None = None

class ChatResponse(BaseModel):
    model: str
    content: str
    finish_reason: str
    usage: TokenUsage
```

- [ ] **Step 4: Create image schema**

```python
# backend/gateway/schemas/image.py
from pydantic import BaseModel

class ImageRequest(BaseModel):
    model: str
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    n: int = 1
    style: str | None = None

class ImageData(BaseModel):
    url: str | None = None
    b64_json: str | None = None
    revised_prompt: str | None = None

class ImageResponse(BaseModel):
    model: str
    images: list[ImageData]
```

- [ ] **Step 5: Create TTS schema**

```python
# backend/gateway/schemas/tts.py
from pydantic import BaseModel

class TTSRequest(BaseModel):
    model: str
    input: str
    voice: str = "alloy"
    speed: float = 1.0
    response_format: str = "mp3"
```

- [ ] **Step 6: Create music schema**

```python
# backend/gateway/schemas/music.py
from pydantic import BaseModel

class MusicRequest(BaseModel):
    model: str
    prompt: str
    duration: int = 30
    style: str | None = None
    lyrics: str | None = None

class MusicResponse(BaseModel):
    model: str
    audio_url: str | None = None
    audio_b64: str | None = None
    duration: float
```

- [ ] **Step 7: Create video schema**

```python
# backend/gateway/schemas/video.py
from pydantic import BaseModel

class VideoRequest(BaseModel):
    model: str
    prompt: str
    image_url: str | None = None
    duration: int = 5
    resolution: str = "720p"

class VideoResponse(BaseModel):
    model: str
    video_url: str | None = None
    cover_url: str | None = None
    duration: float
```

- [ ] **Step 8: Create task schema**

```python
# backend/gateway/schemas/task.py
from pydantic import BaseModel
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
    progress: float | None = None
    result: dict | None = None
    error: str | None = None
    created_at: float
    expires_at: float
```

- [ ] **Step 9: Create schemas __init__.py**

```python
# backend/gateway/schemas/__init__.py
from .chat import ChatRequest, ChatChunk, ChatResponse, ChatMessage, ContentPart
from .image import ImageRequest, ImageResponse, ImageData
from .tts import TTSRequest
from .music import MusicRequest, MusicResponse
from .video import VideoRequest, VideoResponse
from .task import TaskStatus, TaskStatusEnum
from .common import TokenUsage, UnifiedResponse
```

- [ ] **Step 10: Verify imports**

Run: `cd backend && python -c "from gateway.schemas import ChatRequest, ImageRequest, TTSRequest; print('OK')"`
Expected: `OK`

- [ ] **Step 11: Commit**

```bash
git add backend/gateway/
git commit -m "feat(gateway): add unified schemas for all capabilities"
```

### Task 2: Provider Adapter Base + Capability Enum

**Files:**
- Create: `backend/gateway/adapters/__init__.py`
- Create: `backend/gateway/adapters/base.py`

- [ ] **Step 1: Create adapter base**

```python
# backend/gateway/adapters/base.py
from abc import ABC, abstractmethod
from enum import Enum
from typing import AsyncIterator
from gateway.schemas.chat import ChatRequest, ChatChunk
from gateway.schemas.image import ImageRequest, ImageResponse
from gateway.schemas.music import MusicRequest, MusicResponse
from gateway.schemas.video import VideoRequest, VideoResponse
from gateway.schemas.tts import TTSRequest


class Capability(str, Enum):
    CHAT = "chat"
    IMAGE = "image"
    TTS = "tts"
    MUSIC = "music"
    VIDEO = "video"


class CapabilityNotSupported(Exception):
    def __init__(self, provider_id: str, capability: str):
        self.provider_id = provider_id
        self.capability = capability
        super().__init__(f"Provider '{provider_id}' does not support: {capability}")


class ProviderAdapter(ABC):
    provider_id: str
    capabilities: set[Capability]
    request_timeout: int = 60

    def get_auth_headers(self, api_key: str, base_url: str | None = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    @abstractmethod
    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        ...

    @abstractmethod
    async def image(self, request: ImageRequest) -> ImageResponse:
        ...

    async def tts(self, request: TTSRequest) -> bytes:
        raise CapabilityNotSupported(self.provider_id, "tts")

    async def music(self, request: MusicRequest) -> MusicResponse:
        raise CapabilityNotSupported(self.provider_id, "music")

    async def video(self, request: VideoRequest) -> VideoResponse:
        raise CapabilityNotSupported(self.provider_id, "video")
```

- [ ] **Step 2: Create adapters __init__.py with auto-discovery**

```python
# backend/gateway/adapters/__init__.py
import importlib
import pkgutil
from .base import ProviderAdapter, Capability, CapabilityNotSupported

_registry: dict[str, ProviderAdapter] = {}


def discover_adapters():
    _registry.clear()
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
    if provider_id not in _registry:
        raise KeyError(f"No adapter for provider: {provider_id}")
    return _registry[provider_id]


def list_adapters() -> dict[str, ProviderAdapter]:
    return dict(_registry)
```

- [ ] **Step 3: Commit**

```bash
git add backend/gateway/adapters/
git commit -m "feat(gateway): add ProviderAdapter base with auto-discovery"
```

### Task 3: Model Registry

**Files:**
- Create: `backend/gateway/registry/__init__.py`
- Create: `backend/gateway/registry/models.py`

- [ ] **Step 1: Create model registry**

```python
# backend/gateway/registry/models.py
from dataclasses import dataclass
from gateway.adapters.base import Capability


@dataclass
class ModelEntry:
    provider: str
    display_name: str
    capabilities: set[Capability]
    context_window: int = 0
    supports_vision: bool = False
    supports_streaming: bool = True


MODEL_REGISTRY: dict[str, ModelEntry] = {
    # OpenAI
    "openai:gpt-4o": ModelEntry(provider="openai", display_name="GPT-4o", capabilities={Capability.CHAT}, context_window=128000, supports_vision=True),
    "openai:gpt-4o-mini": ModelEntry(provider="openai", display_name="GPT-4o Mini", capabilities={Capability.CHAT}, context_window=128000, supports_vision=True),
    "openai:dall-e-3": ModelEntry(provider="openai", display_name="DALL·E 3", capabilities={Capability.IMAGE}),
    "openai:tts-1": ModelEntry(provider="openai", display_name="TTS-1", capabilities={Capability.TTS}),
    # Gemini
    "google:gemini-2.5-pro": ModelEntry(provider="google", display_name="Gemini 2.5 Pro", capabilities={Capability.CHAT}, context_window=1000000, supports_vision=True),
    "google:gemini-2.5-flash": ModelEntry(provider="google", display_name="Gemini 2.5 Flash", capabilities={Capability.CHAT}, context_window=1000000, supports_vision=True),
    "google:imagen-3": ModelEntry(provider="google", display_name="Imagen 3", capabilities={Capability.IMAGE}),
    # Qwen
    "qwen:qwen-vl-max": ModelEntry(provider="qwen", display_name="通义千问 VL Max", capabilities={Capability.CHAT}, supports_vision=True),
    "qwen:qwen-turbo": ModelEntry(provider="qwen", display_name="通义千问 Turbo", capabilities={Capability.CHAT}),
    "qwen:wanx-v1": ModelEntry(provider="qwen", display_name="通义万相", capabilities={Capability.IMAGE}),
    # ERNIE
    "ernie:ernie-4.0": ModelEntry(provider="ernie", display_name="文心一言 4.0", capabilities={Capability.CHAT}),
    # Zhipu
    "zhipu:glm-4": ModelEntry(provider="zhipu", display_name="GLM-4", capabilities={Capability.CHAT}, supports_vision=True),
    "zhipu:cogview-3": ModelEntry(provider="zhipu", display_name="CogView-3", capabilities={Capability.IMAGE}),
    # MiniMax
    "minimax:abab6.5s-chat": ModelEntry(provider="minimax", display_name="MiniMax ABAB 6.5s", capabilities={Capability.CHAT}),
    "minimax:image-01": ModelEntry(provider="minimax", display_name="MiniMax Image-01", capabilities={Capability.IMAGE}),
    "minimax:video-01": ModelEntry(provider="minimax", display_name="MiniMax Video-01", capabilities={Capability.VIDEO}),
    "minimax:music-01": ModelEntry(provider="minimax", display_name="MiniMax Music-01", capabilities={Capability.MUSIC}),
    "minimax:tts-01": ModelEntry(provider="minimax", display_name="MiniMax TTS-01", capabilities={Capability.TTS}),
}


def get_model(model_id: str) -> ModelEntry | None:
    return MODEL_REGISTRY.get(model_id)


def list_models(enabled_only: bool = False, available_providers: set[str] | None = None) -> dict[str, dict]:
    result = {}
    for model_id, entry in MODEL_REGISTRY.items():
        enabled = available_providers is None or entry.provider in available_providers
        if enabled_only and not enabled:
            continue
        result[model_id] = {
            "id": model_id,
            "provider": entry.provider,
            "display_name": entry.display_name,
            "capabilities": [c.value for c in entry.capabilities],
            "supports_vision": entry.supports_vision,
            "supports_streaming": entry.supports_streaming,
            "enabled": enabled,
            "disabled_reason": None if enabled else f"Provider '{entry.provider}' API key not configured",
        }
    return result
```

- [ ] **Step 2: Create registry __init__.py**

```python
# backend/gateway/registry/__init__.py
from .models import MODEL_REGISTRY, ModelEntry, get_model, list_models
```

- [ ] **Step 3: Verify**

Run: `cd backend && python -c "from gateway.registry import MODEL_REGISTRY, list_models; print(len(MODEL_REGISTRY), 'models')"`
Expected: `18 models`

- [ ] **Step 4: Commit**

```bash
git add backend/gateway/registry/
git commit -m "feat(gateway): add declarative model registry with 18 models"
```

### Task 4: Config + Task Store

**Files:**
- Create: `backend/gateway/config.py`
- Create: `backend/gateway/task_store.py`

- [ ] **Step 1: Create config**

```python
# backend/gateway/config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ProviderKeys:
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    google_api_key: str = ""
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    ernie_api_key: str = ""
    ernie_secret_key: str = ""
    zhipu_api_key: str = ""
    minimax_api_key: str = ""
    minimax_group_id: str = ""

    @classmethod
    def from_env(cls) -> "ProviderKeys":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
            qwen_api_key=os.getenv("QWEN_API_KEY", ""),
            qwen_base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/api/v1"),
            ernie_api_key=os.getenv("ERNIE_API_KEY", ""),
            ernie_secret_key=os.getenv("ERNIE_SECRET_KEY", ""),
            zhipu_api_key=os.getenv("ZHIPU_API_KEY", ""),
            minimax_api_key=os.getenv("MINIMAX_API_KEY", ""),
            minimax_group_id=os.getenv("MINIMAX_GROUP_ID", ""),
        )

    def available_providers(self) -> set[str]:
        providers = set()
        if self.openai_api_key: providers.add("openai")
        if self.google_api_key: providers.add("google")
        if self.qwen_api_key: providers.add("qwen")
        if self.ernie_api_key and self.ernie_secret_key: providers.add("ernie")
        if self.zhipu_api_key: providers.add("zhipu")
        if self.minimax_api_key: providers.add("minimax")
        return providers


_keys = None


def get_keys() -> ProviderKeys:
    global _keys
    if _keys is None:
        _keys = ProviderKeys.from_env()
    return _keys


def get_api_key(provider_id: str, header_key: str | None = None) -> str:
    if header_key:
        return header_key
    return getattr(get_keys(), f"{provider_id}_api_key", "") or ""


def get_base_url(provider_id: str, header_url: str | None = None) -> str | None:
    if header_url:
        return header_url
    return getattr(get_keys(), f"{provider_id}_base_url", None) or None
```

- [ ] **Step 2: Create task store**

```python
# backend/gateway/task_store.py
import time
import uuid
from gateway.schemas.task import TaskStatus, TaskStatusEnum

_store: dict[str, TaskStatus] = {}
TASK_TTL = 3600
TASK_TIMEOUT = 300


def create_task() -> TaskStatus:
    task_id = str(uuid.uuid4())[:8]
    now = time.time()
    task = TaskStatus(task_id=task_id, status=TaskStatusEnum.PENDING, created_at=now, expires_at=now + TASK_TTL)
    _store[task_id] = task
    return task


def update_task(task_id: str, **kwargs) -> TaskStatus | None:
    task = _store.get(task_id)
    if not task:
        return None
    for k, v in kwargs.items():
        setattr(task, k, v)
    return task


def get_task(task_id: str) -> TaskStatus | None:
    task = _store.get(task_id)
    if not task:
        return None
    if time.time() > task.expires_at:
        task.status = TaskStatusEnum.EXPIRED
    return task
```

- [ ] **Step 3: Verify**

Run: `cd backend && python -c "from gateway.config import get_keys; k = get_keys(); print('Config OK, providers:', k.available_providers())"`
Expected: `Config OK, providers: {...}`

- [ ] **Step 4: Commit**

```bash
git add backend/gateway/config.py backend/gateway/task_store.py
git commit -m "feat(gateway): add config management and task store"
```

---

## Chunk 2: All 6 Provider Adapters

### Task 5: OpenAI Adapter

**Files:**
- Create: `backend/gateway/adapters/openai_adapter.py`

- [ ] **Step 1: Create OpenAI adapter**

```python
# backend/gateway/adapters/openai_adapter.py
import httpx
import json
from typing import AsyncIterator
from .base import ProviderAdapter, Capability
from gateway.schemas.chat import ChatRequest, ChatChunk
from gateway.schemas.image import ImageRequest, ImageResponse, ImageData
from gateway.schemas.tts import TTSRequest
from gateway.config import get_keys


class OpenAIAdapter(ProviderAdapter):
    provider_id = "openai"
    capabilities = {Capability.CHAT, Capability.IMAGE, Capability.TTS}
    request_timeout = 60

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        keys = get_keys()
        base_url = keys.openai_base_url
        model_name = request.model.split(":", 1)[1]
        messages = [{"role": m.role, "content": m.content if isinstance(m.content, str) else [p.model_dump() for p in m.content]} for m in request.messages]
        payload = {"model": model_name, "messages": messages, "temperature": request.temperature, "max_tokens": request.max_tokens, "stream": True}

        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            async with client.stream("POST", f"{base_url}/chat/completions",
                                     headers={"Authorization": f"Bearer {keys.openai_api_key}", "Content-Type": "application/json"},
                                     json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {}).get("content", "")
                    finish = chunk["choices"][0].get("finish_reason")
                    usage_data = chunk.get("usage")
                    from gateway.schemas.common import TokenUsage
                    usage = TokenUsage(**usage_data) if usage_data else None
                    yield ChatChunk(model=request.model, delta=delta, finish_reason=finish, usage=usage)

    async def image(self, request: ImageRequest) -> ImageResponse:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        payload = {"model": model_name, "prompt": request.prompt, "size": request.size, "quality": request.quality, "n": request.n}

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{keys.openai_base_url}/images/generations",
                                     headers={"Authorization": f"Bearer {keys.openai_api_key}", "Content-Type": "application/json"},
                                     json=payload)
            resp.raise_for_status()
            data = resp.json()

        images = [ImageData(url=img.get("url"), b64_json=img.get("b64_json"), revised_prompt=img.get("revised_prompt")) for img in data.get("data", [])]
        return ImageResponse(model=request.model, images=images)

    async def tts(self, request: TTSRequest) -> bytes:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        payload = {"model": model_name, "input": request.input, "voice": request.voice, "speed": request.speed, "response_format": request.response_format}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{keys.openai_base_url}/audio/speech",
                                     headers={"Authorization": f"Bearer {keys.openai_api_key}", "Content-Type": "application/json"},
                                     json=payload)
            resp.raise_for_status()
            return resp.content
```

- [ ] **Step 2: Verify**

Run: `cd backend && python -c "from gateway.adapters.openai_adapter import OpenAIAdapter; a = OpenAIAdapter(); print(a.provider_id, a.capabilities)"`
Expected: `openai {<Capability.CHAT: 'chat'>, <Capability.IMAGE: 'image'>, <Capability.TTS: 'tts'>}`

- [ ] **Step 3: Commit**

```bash
git add backend/gateway/adapters/openai_adapter.py
git commit -m "feat(gateway): add OpenAI adapter (chat + image + tts)"
```

### Task 6: Gemini Adapter

**Files:**
- Create: `backend/gateway/adapters/gemini_adapter.py`

- [ ] **Step 1: Create Gemini adapter**

```python
# backend/gateway/adapters/gemini_adapter.py
import httpx
import json
from typing import AsyncIterator
from .base import ProviderAdapter, Capability
from gateway.schemas.chat import ChatRequest, ChatChunk
from gateway.schemas.image import ImageRequest, ImageResponse, ImageData
from gateway.config import get_keys


class GeminiAdapter(ProviderAdapter):
    provider_id = "google"
    capabilities = {Capability.CHAT, Capability.IMAGE}
    request_timeout = 60

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        contents = []
        for m in request.messages:
            role = "user" if m.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.content if isinstance(m.content, str) else str(m.content)}]})
        payload = {"contents": contents, "generationConfig": {"temperature": request.temperature, "maxOutputTokens": request.max_tokens}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={keys.google_api_key}"

        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = json.loads(line[6:])
                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    finish = candidates[0].get("finishReason")
                    yield ChatChunk(model=request.model, delta=text, finish_reason=finish.lower() if finish else None)

    async def image(self, request: ImageRequest) -> ImageResponse:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:predict?key={keys.google_api_key}"
        payload = {"instances": [{"prompt": request.prompt}], "parameters": {"sampleCount": request.n}}

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        images = [ImageData(b64_json=pred.get("bytesBase64Encoded")) for pred in data.get("predictions", [])]
        return ImageResponse(model=request.model, images=images)
```

- [ ] **Step 2: Commit**

```bash
git add backend/gateway/adapters/gemini_adapter.py
git commit -m "feat(gateway): add Gemini adapter (chat + image)"
```

### Task 7: Qwen Adapter

**Files:**
- Create: `backend/gateway/adapters/qwen_adapter.py`

- [ ] **Step 1: Create Qwen adapter**

```python
# backend/gateway/adapters/qwen_adapter.py
import httpx
import json
import asyncio
from typing import AsyncIterator
from .base import ProviderAdapter, Capability
from gateway.schemas.chat import ChatRequest, ChatChunk
from gateway.schemas.image import ImageRequest, ImageResponse, ImageData
from gateway.config import get_keys


class QwenAdapter(ProviderAdapter):
    provider_id = "qwen"
    capabilities = {Capability.CHAT, Capability.IMAGE}
    request_timeout = 60

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        messages = [{"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)} for m in request.messages]
        payload = {"model": model_name, "messages": messages, "temperature": request.temperature, "max_tokens": request.max_tokens, "stream": True}

        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            async with client.stream("POST", f"{keys.qwen_base_url}/chat/completions",
                                     headers={"Authorization": f"Bearer {keys.qwen_api_key}", "Content-Type": "application/json"},
                                     json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {}).get("content", "")
                    finish = chunk["choices"][0].get("finish_reason")
                    yield ChatChunk(model=request.model, delta=delta, finish_reason=finish)

    async def image(self, request: ImageRequest) -> ImageResponse:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        payload = {"model": model_name, "input": {"prompt": request.prompt}, "parameters": {"size": request.size, "n": request.n}}

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{keys.qwen_base_url}/services/aigc/text2image/image-synthesis",
                                     headers={"Authorization": f"Bearer {keys.qwen_api_key}", "Content-Type": "application/json", "X-DashScope-Async": "enable"},
                                     json=payload)
            resp.raise_for_status()
            data = resp.json()

        task_id = data.get("output", {}).get("task_id")
        if not task_id:
            raise Exception("No task_id from DashScope")

        for _ in range(60):
            await asyncio.sleep(2)
            async with httpx.AsyncClient() as client:
                poll = await client.get(f"{keys.qwen_base_url}/tasks/{task_id}", headers={"Authorization": f"Bearer {keys.qwen_api_key}"})
                poll_data = poll.json()
                status = poll_data.get("output", {}).get("task_status")
                if status == "SUCCEEDED":
                    results = poll_data.get("output", {}).get("results", [])
                    return ImageResponse(model=request.model, images=[ImageData(url=r.get("url")) for r in results])
                elif status == "FAILED":
                    raise Exception(f"DashScope failed: {poll_data}")
        raise Exception("DashScope timeout")
```

- [ ] **Step 2: Commit**

```bash
git add backend/gateway/adapters/qwen_adapter.py
git commit -m "feat(gateway): add Qwen adapter (chat + DashScope image)"
```

### Task 8: ERNIE Adapter

**Files:**
- Create: `backend/gateway/adapters/ernie_adapter.py`

- [ ] **Step 1: Create ERNIE adapter**

```python
# backend/gateway/adapters/ernie_adapter.py
import httpx
from typing import AsyncIterator
from .base import ProviderAdapter, Capability
from gateway.schemas.chat import ChatRequest, ChatChunk
from gateway.schemas.image import ImageRequest, ImageResponse, ImageData
from gateway.config import get_keys
from gateway.errors import AuthError


class ERNIEAdapter(ProviderAdapter):
    provider_id = "ernie"
    capabilities = {Capability.CHAT, Capability.IMAGE}
    request_timeout = 60

    async def _get_access_token(self) -> str:
        keys = get_keys()
        if not keys.ernie_api_key or not keys.ernie_secret_key:
            raise AuthError("ernie", "ERNIE requires both API_KEY and SECRET_KEY", "auth_missing")
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://aip.baidubce.com/oauth/2.0/token",
                                    params={"grant_type": "client_credentials", "client_id": keys.ernie_api_key, "client_secret": keys.ernie_secret_key})
            if resp.status_code != 200:
                raise AuthError("ernie", "ERNIE token exchange failed", "auth_failed")
            return resp.json()["access_token"]

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        token = await self._get_access_token()
        model_name = request.model.split(":", 1)[1]
        messages = [{"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)} for m in request.messages]
        payload = {"messages": messages, "temperature": request.temperature, "max_output_tokens": request.max_tokens}
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model_name}?access_token={token}"

        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        yield ChatChunk(model=request.model, delta=data.get("result", ""), finish_reason="stop")

    async def image(self, request: ImageRequest) -> ImageResponse:
        token = await self._get_access_token()
        model_name = request.model.split(":", 1)[1]
        payload = {"prompt": request.prompt, "size": request.size.replace("x", "×")}
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/text2image/{model_name}?access_token={token}"

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        images = [ImageData(b64_json=img.get("image")) for img in data.get("data", [])]
        return ImageResponse(model=request.model, images=images)
```

- [ ] **Step 2: Commit**

```bash
git add backend/gateway/adapters/ernie_adapter.py
git commit -m "feat(gateway): add ERNIE adapter (chat + image)"
```

### Task 9: Zhipu Adapter

**Files:**
- Create: `backend/gateway/adapters/zhipu_adapter.py`

- [ ] **Step 1: Create Zhipu adapter**

```python
# backend/gateway/adapters/zhipu_adapter.py
import httpx
import json
import jwt
import time
from typing import AsyncIterator
from .base import ProviderAdapter, Capability
from gateway.schemas.chat import ChatRequest, ChatChunk
from gateway.schemas.image import ImageRequest, ImageResponse, ImageData
from gateway.config import get_keys


class ZhipuAdapter(ProviderAdapter):
    provider_id = "zhipu"
    capabilities = {Capability.CHAT, Capability.IMAGE}
    request_timeout = 60

    def _generate_token(self) -> str:
        api_key = get_keys().zhipu_api_key
        if "." not in api_key:
            raise Exception("Invalid Zhipu API key format (expected id.secret)")
        id_part, secret = api_key.split(".", 1)
        return jwt.encode({"api_key": id_part, "exp": int(time.time()) + 3600, "timestamp": int(time.time())}, secret, algorithm="HS256")

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        token = self._generate_token()
        model_name = request.model.split(":", 1)[1]
        messages = [{"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)} for m in request.messages]
        payload = {"model": model_name, "messages": messages, "temperature": request.temperature, "max_tokens": request.max_tokens, "stream": True}

        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            async with client.stream("POST", "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                                     json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {}).get("content", "")
                    finish = chunk["choices"][0].get("finish_reason")
                    yield ChatChunk(model=request.model, delta=delta, finish_reason=finish)

    async def image(self, request: ImageRequest) -> ImageResponse:
        token = self._generate_token()
        model_name = request.model.split(":", 1)[1]
        payload = {"model": model_name, "prompt": request.prompt, "size": request.size}

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post("https://open.bigmodel.cn/api/paas/v4/images/generations",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                                     json=payload)
            resp.raise_for_status()
            data = resp.json()

        return ImageResponse(model=request.model, images=[ImageData(url=img.get("url")) for img in data.get("data", [])])
```

- [ ] **Step 2: Install PyJWT**

Run: `cd backend && pip install PyJWT>=2.8.0`

- [ ] **Step 3: Commit**

```bash
git add backend/gateway/adapters/zhipu_adapter.py
git commit -m "feat(gateway): add Zhipu adapter (chat + CogView image)"
```

### Task 10: MiniMax Adapter

**Files:**
- Create: `backend/gateway/adapters/minimax_adapter.py`

- [ ] **Step 1: Create MiniMax adapter**

```python
# backend/gateway/adapters/minimax_adapter.py
import httpx
import json
from typing import AsyncIterator
from .base import ProviderAdapter, Capability
from gateway.schemas.chat import ChatRequest, ChatChunk
from gateway.schemas.image import ImageRequest, ImageResponse, ImageData
from gateway.schemas.tts import TTSRequest
from gateway.schemas.music import MusicRequest, MusicResponse
from gateway.schemas.video import VideoRequest, VideoResponse
from gateway.config import get_keys

BASE_URL = "https://api.minimaxi.com/v1"


class MiniMaxAdapter(ProviderAdapter):
    provider_id = "minimax"
    capabilities = {Capability.CHAT, Capability.IMAGE, Capability.TTS, Capability.MUSIC, Capability.VIDEO}
    request_timeout = 60

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        messages = [{"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)} for m in request.messages]
        payload = {"model": model_name, "messages": messages, "temperature": request.temperature, "max_tokens": request.max_tokens, "stream": True}

        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            async with client.stream("POST", f"{BASE_URL}/text/chatcompletion_v2",
                                     headers={"Authorization": f"Bearer {keys.minimax_api_key}", "Content-Type": "application/json"},
                                     json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    finish = chunk.get("choices", [{}])[0].get("finish_reason")
                    yield ChatChunk(model=request.model, delta=delta, finish_reason=finish)

    async def image(self, request: ImageRequest) -> ImageResponse:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        payload = {"model": model_name, "prompt": request.prompt, "aspect_ratio": "1:1"}

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{BASE_URL}/images/generations",
                                     headers={"Authorization": f"Bearer {keys.minimax_api_key}", "Content-Type": "application/json"},
                                     json=payload)
            resp.raise_for_status()
            data = resp.json()

        return ImageResponse(model=request.model, images=[ImageData(url=img.get("url")) for img in data.get("data", [])])

    async def tts(self, request: TTSRequest) -> bytes:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        payload = {"model": model_name, "text": request.input, "voice": request.voice}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{BASE_URL}/text/speech",
                                     headers={"Authorization": f"Bearer {keys.minimax_api_key}", "Content-Type": "application/json"},
                                     json=payload)
            resp.raise_for_status()
            return resp.content

    async def music(self, request: MusicRequest) -> MusicResponse:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        payload = {"model": model_name, "prompt": request.prompt}
        if request.lyrics:
            payload["lyrics"] = request.lyrics

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(f"{BASE_URL}/music/generation",
                                     headers={"Authorization": f"Bearer {keys.minimax_api_key}", "Content-Type": "application/json"},
                                     json=payload)
            resp.raise_for_status()
            data = resp.json()

        audio = data.get("audio_file", {})
        return MusicResponse(model=request.model, audio_url=audio.get("url"), duration=audio.get("duration", 0))

    async def video(self, request: VideoRequest) -> VideoResponse:
        keys = get_keys()
        model_name = request.model.split(":", 1)[1]
        payload = {"model": model_name, "prompt": request.prompt}
        if request.image_url:
            payload["image_url"] = request.image_url

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(f"{BASE_URL}/video/generation",
                                     headers={"Authorization": f"Bearer {keys.minimax_api_key}", "Content-Type": "application/json"},
                                     json=payload)
            resp.raise_for_status()
            data = resp.json()

        video = data.get("video_file", {})
        return VideoResponse(model=request.model, video_url=video.get("url"), cover_url=video.get("cover_url"), duration=video.get("duration", 0))
```

- [ ] **Step 2: Verify all adapters discovered**

Run: `cd backend && python -c "from gateway.adapters import discover_adapters, list_adapters; discover_adapters(); print(list(list_adapters().keys()))"`
Expected: `['openai', 'google', 'qwen', 'ernie', 'zhipu', 'minimax']`

- [ ] **Step 3: Commit**

```bash
git add backend/gateway/adapters/minimax_adapter.py
git commit -m "feat(gateway): add MiniMax adapter (all 5 capabilities)"
```

---

## Chunk 3: Unified API Routes + Error Handling

### Task 11: Error Handling

**Files:**
- Create: `backend/gateway/errors.py`

- [ ] **Step 1: Create error classes and handlers**

```python
# backend/gateway/errors.py
from fastapi import Request
from fastapi.responses import JSONResponse
from gateway.adapters.base import CapabilityNotSupported


class ProviderError(Exception):
    def __init__(self, provider: str, message: str, code: str = "provider_error"):
        self.provider = provider
        self.message = message
        self.code = code
        super().__init__(message)


class AuthError(Exception):
    def __init__(self, provider: str, message: str, code: str = "auth_missing"):
        self.provider = provider
        self.message = message
        self.code = code
        super().__init__(message)


class ModelNotFoundError(Exception):
    def __init__(self, model_id: str):
        self.model_id = model_id
        super().__init__(f"Model not found: {model_id}")


async def model_not_found_handler(request: Request, exc: ModelNotFoundError):
    return JSONResponse(status_code=404, content={"success": False, "error": {"message": f"Model not found: {exc.model_id}", "code": "model_not_found"}})


async def capability_handler(request: Request, exc: CapabilityNotSupported):
    return JSONResponse(status_code=400, content={"success": False, "error": {"message": f"Provider '{exc.provider_id}' does not support: {exc.capability}", "code": "capability_not_supported", "provider": exc.provider_id}})


async def auth_handler(request: Request, exc: AuthError):
    return JSONResponse(status_code=401, content={"success": False, "error": {"message": exc.message, "code": exc.code, "provider": exc.provider}})


async def provider_handler(request: Request, exc: ProviderError):
    return JSONResponse(status_code=502, content={"success": False, "error": {"message": f"Provider API error: {exc.message}", "code": exc.code, "provider": exc.provider}})


async def generic_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"success": False, "error": {"message": str(exc), "code": "internal_error"}})
```

- [ ] **Step 2: Commit**

```bash
git add backend/gateway/errors.py
git commit -m "feat(gateway): add unified error handling"
```

### Task 12: Chat Router

**Files:**
- Create: `backend/gateway/routers/__init__.py`
- Create: `backend/gateway/routers/chat.py`

- [ ] **Step 1: Create chat router**

```python
# backend/gateway/routers/chat.py
import json
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse, JSONResponse
from gateway.schemas.chat import ChatRequest
from gateway.registry.models import get_model
from gateway.adapters.base import Capability
from gateway.adapters import get_adapter
from gateway.config import get_api_key, get_base_url
from gateway.errors import ModelNotFoundError, AuthError, ProviderError

router = APIRouter(prefix="/api", tags=["gateway-chat"])


@router.post("/chat")
async def chat_endpoint(
    request_body: ChatRequest,
    x_openai_api_key: str | None = Header(None),
    x_google_api_key: str | None = Header(None),
    x_qwen_api_key: str | None = Header(None),
    x_ernie_api_key: str | None = Header(None),
    x_ernie_secret_key: str | None = Header(None),
    x_zhipu_api_key: str | None = Header(None),
    x_minimax_api_key: str | None = Header(None),
    x_openai_base_url: str | None = Header(None),
    x_qwen_base_url: str | None = Header(None),
):
    model_entry = get_model(request_body.model)
    if not model_entry:
        raise ModelNotFoundError(request_body.model)
    if Capability.CHAT not in model_entry.capabilities:
        raise ProviderError(model_entry.provider, "Model does not support chat", "capability_not_supported")

    # Resolve API key from provider-specific header
    header_keys = {
        "openai": x_openai_api_key, "google": x_google_api_key, "qwen": x_qwen_api_key,
        "ernie": x_ernie_api_key, "zhipu": x_zhipu_api_key, "minimax": x_minimax_api_key,
    }
    header_urls = {"openai": x_openai_base_url, "qwen": x_qwen_base_url}
    api_key = get_api_key(model_entry.provider, header_keys.get(model_entry.provider))
    if not api_key:
        raise AuthError(model_entry.provider, f"API key not configured for: {model_entry.provider}")

    # ERNIE needs secret_key too
    if model_entry.provider == "ernie":
        import os
        secret = x_ernie_secret_key or os.getenv("ERNIE_SECRET_KEY", "")
        if not secret:
            raise AuthError("ernie", "ERNIE requires both API_KEY and SECRET_KEY")

    adapter = get_adapter(model_entry.provider)
    base_url = get_base_url(model_entry.provider, header_urls.get(model_entry.provider))

    if request_body.stream:
        async def event_stream():
            try:
                async for chunk in adapter.chat(request_body):
                    yield f"data: {chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e), 'code': 'provider_error'})}\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        full_content = ""
        usage = None
        async for chunk in adapter.chat(request_body):
            full_content += chunk.delta
            if chunk.usage:
                usage = chunk.usage
        return JSONResponse({"success": True, "model": request_body.model, "provider": model_entry.provider,
                             "data": {"content": full_content, "finish_reason": "stop", "usage": usage.model_dump() if usage else None}})
```

- [ ] **Step 2: Create routers __init__.py**

```python
# backend/gateway/routers/__init__.py
```

- [ ] **Step 3: Commit**

```bash
git add backend/gateway/routers/
git commit -m "feat(gateway): add chat router with SSE streaming"
```

### Task 13: Image + TTS + Music + Video + Models + Tasks Routers

**Files:**
- Create: `backend/gateway/routers/image.py`
- Create: `backend/gateway/routers/tts.py`
- Create: `backend/gateway/routers/music.py`
- Create: `backend/gateway/routers/video.py`
- Create: `backend/gateway/routers/models.py`
- Create: `backend/gateway/routers/tasks.py`

- [ ] **Step 1: Create image router**

```python
# backend/gateway/routers/image.py
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from gateway.schemas.image import ImageRequest
from gateway.registry.models import get_model
from gateway.adapters.base import Capability
from gateway.adapters import get_adapter
from gateway.config import get_api_key
from gateway.errors import ModelNotFoundError, AuthError, ProviderError

router = APIRouter(prefix="/api", tags=["gateway-image"])


@router.post("/image")
async def image_endpoint(request_body: ImageRequest, x_openai_api_key: str | None = Header(None), x_google_api_key: str | None = Header(None), x_qwen_api_key: str | None = Header(None), x_ernie_api_key: str | None = Header(None), x_ernie_secret_key: str | None = Header(None), x_zhipu_api_key: str | None = Header(None), x_minimax_api_key: str | None = Header(None)):
    model_entry = get_model(request_body.model)
    if not model_entry:
        raise ModelNotFoundError(request_body.model)
    if Capability.IMAGE not in model_entry.capabilities:
        raise ProviderError(model_entry.provider, "Model does not support image generation", "capability_not_supported")

    header_keys = {"openai": x_openai_api_key, "google": x_google_api_key, "qwen": x_qwen_api_key, "ernie": x_ernie_api_key, "zhipu": x_zhipu_api_key, "minimax": x_minimax_api_key}
    api_key = get_api_key(model_entry.provider, header_keys.get(model_entry.provider))
    if not api_key:
        raise AuthError(model_entry.provider, f"API key not configured for: {model_entry.provider}")

    adapter = get_adapter(model_entry.provider)
    result = await adapter.image(request_body)
    return JSONResponse({"success": True, "model": request_body.model, "provider": model_entry.provider, "data": result.model_dump()})
```

- [ ] **Step 2: Create TTS router**

```python
# backend/gateway/routers/tts.py
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from gateway.schemas.tts import TTSRequest
from gateway.registry.models import get_model
from gateway.adapters.base import Capability
from gateway.adapters import get_adapter
from gateway.config import get_api_key
from gateway.errors import ModelNotFoundError, AuthError, ProviderError

router = APIRouter(prefix="/api", tags=["gateway-tts"])


@router.post("/tts")
async def tts_endpoint(request_body: TTSRequest, x_openai_api_key: str | None = Header(None), x_google_api_key: str | None = Header(None), x_qwen_api_key: str | None = Header(None), x_ernie_api_key: str | None = Header(None), x_zhipu_api_key: str | None = Header(None), x_minimax_api_key: str | None = Header(None)):
    model_entry = get_model(request_body.model)
    if not model_entry:
        raise ModelNotFoundError(request_body.model)
    if Capability.TTS not in model_entry.capabilities:
        raise ProviderError(model_entry.provider, "Model does not support TTS", "capability_not_supported")

    header_keys = {"openai": x_openai_api_key, "google": x_google_api_key, "qwen": x_qwen_api_key, "ernie": x_ernie_api_key, "zhipu": x_zhipu_api_key, "minimax": x_minimax_api_key}
    api_key = get_api_key(model_entry.provider, header_keys.get(model_entry.provider))
    if not api_key:
        raise AuthError(model_entry.provider, f"API key not configured for: {model_entry.provider}")

    adapter = get_adapter(model_entry.provider)
    audio_bytes = await adapter.tts(request_body)
    return StreamingResponse(iter([audio_bytes]), media_type=f"audio/{request_body.response_format}")
```

- [ ] **Step 3: Create music router**

```python
# backend/gateway/routers/music.py
import asyncio
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from gateway.schemas.music import MusicRequest
from gateway.schemas.task import TaskStatusEnum
from gateway.registry.models import get_model
from gateway.adapters.base import Capability
from gateway.adapters import get_adapter
from gateway.config import get_api_key
from gateway.task_store import create_task, update_task
from gateway.errors import ModelNotFoundError, AuthError, ProviderError

router = APIRouter(prefix="/api", tags=["gateway-music"])


@router.post("/music")
async def music_endpoint(request_body: MusicRequest, x_minimax_api_key: str | None = Header(None)):
    model_entry = get_model(request_body.model)
    if not model_entry:
        raise ModelNotFoundError(request_body.model)
    if Capability.MUSIC not in model_entry.capabilities:
        raise ProviderError(model_entry.provider, "Model does not support music generation", "capability_not_supported")

    api_key = get_api_key(model_entry.provider, x_minimax_api_key)
    if not api_key:
        raise AuthError(model_entry.provider, f"API key not configured for: {model_entry.provider}")

    task = create_task()
    adapter = get_adapter(model_entry.provider)

    async def run():
        try:
            update_task(task.task_id, status=TaskStatusEnum.PROCESSING)
            result = await adapter.music(request_body)
            update_task(task.task_id, status=TaskStatusEnum.COMPLETED, result=result.model_dump())
        except Exception as e:
            update_task(task.task_id, status=TaskStatusEnum.FAILED, error=str(e))

    asyncio.create_task(run())
    return JSONResponse({"success": True, "task": {"task_id": task.task_id, "status": task.status.value}})
```

- [ ] **Step 4: Create video router (same pattern)**

```python
# backend/gateway/routers/video.py
import asyncio
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from gateway.schemas.video import VideoRequest
from gateway.schemas.task import TaskStatusEnum
from gateway.registry.models import get_model
from gateway.adapters.base import Capability
from gateway.adapters import get_adapter
from gateway.config import get_api_key
from gateway.task_store import create_task, update_task
from gateway.errors import ModelNotFoundError, AuthError, ProviderError

router = APIRouter(prefix="/api", tags=["gateway-video"])


@router.post("/video")
async def video_endpoint(request_body: VideoRequest, x_minimax_api_key: str | None = Header(None)):
    model_entry = get_model(request_body.model)
    if not model_entry:
        raise ModelNotFoundError(request_body.model)
    if Capability.VIDEO not in model_entry.capabilities:
        raise ProviderError(model_entry.provider, "Model does not support video generation", "capability_not_supported")

    api_key = get_api_key(model_entry.provider, x_minimax_api_key)
    if not api_key:
        raise AuthError(model_entry.provider, f"API key not configured for: {model_entry.provider}")

    task = create_task()
    adapter = get_adapter(model_entry.provider)

    async def run():
        try:
            update_task(task.task_id, status=TaskStatusEnum.PROCESSING)
            result = await adapter.video(request_body)
            update_task(task.task_id, status=TaskStatusEnum.COMPLETED, result=result.model_dump())
        except Exception as e:
            update_task(task.task_id, status=TaskStatusEnum.FAILED, error=str(e))

    asyncio.create_task(run())
    return JSONResponse({"success": True, "task": {"task_id": task.task_id, "status": task.status.value}})
```

- [ ] **Step 5: Create models router**

```python
# backend/gateway/routers/models.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from gateway.registry.models import list_models
from gateway.config import get_keys

router = APIRouter(prefix="/api", tags=["gateway-models"])


@router.get("/models")
async def list_models_endpoint():
    keys = get_keys()
    available = keys.available_providers()
    models = list_models(available_providers=available)
    return JSONResponse({"success": True, "data": {"models": models}})
```

- [ ] **Step 6: Create tasks router**

```python
# backend/gateway/routers/tasks.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from gateway.task_store import get_task

router = APIRouter(prefix="/api", tags=["gateway-tasks"])


@router.get("/tasks/{task_id}")
async def get_task_endpoint(task_id: str):
    task = get_task(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"success": False, "error": {"message": "Task not found or expired", "code": "task_not_found"}})
    return JSONResponse({"success": True, "data": task.model_dump()})
```

- [ ] **Step 7: Commit**

```bash
git add backend/gateway/routers/
git commit -m "feat(gateway): add all unified API routers"
```

### Task 14: Register Gateway in Main App

**Files:**
- Modify: `backend/main.py` (add gateway routes alongside existing routes)

- [ ] **Step 1: Add gateway routes to existing main.py**

Add these lines to the existing `backend/main.py`, **after** existing route includes:

```python
# ── Gateway: Multi-Provider Unified API ──
from gateway.adapters import discover_adapters
from gateway.routers import chat as gw_chat, image as gw_image, tts as gw_tts, music as gw_music, video as gw_video, models as gw_models, tasks as gw_tasks
from gateway.errors import ModelNotFoundError, CapabilityNotSupported, AuthError, ProviderError
from gateway.errors import model_not_found_handler, capability_handler, auth_handler, provider_handler, generic_handler
from gateway.adapters.base import CapabilityNotSupported as _CapNotSupported

app.add_exception_handler(ModelNotFoundError, model_not_found_handler)
app.add_exception_handler(_CapNotSupported, capability_handler)
app.add_exception_handler(AuthError, auth_handler)
app.add_exception_handler(ProviderError, provider_handler)
app.add_exception_handler(Exception, generic_handler)

app.include_router(gw_chat.router)
app.include_router(gw_image.router)
app.include_router(gw_tts.router)
app.include_router(gw_music.router)
app.include_router(gw_video.router)
app.include_router(gw_models.router)
app.include_router(gw_tasks.router)
```

Also add `discover_adapters()` to the existing startup event.

- [ ] **Step 2: Verify both old and new routes work**

Run: `cd backend && python -c "from main import app; routes = [r.path for r in app.routes]; print('/api/chat' in routes, '/api/generate' in routes)"`
Expected: `True True`

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: register gateway routes alongside existing routes"
```

---

## Chunk 4: Frontend — Settings + Module Dropdowns + Chat Page

### Task 15: Settings Page — Provider Key Management

**Files:**
- Modify: `frontend/src/pages/Settings.jsx` (or equivalent settings component)

- [ ] **Step 1: Locate existing settings component**

Run: `find frontend/src -name "*etting*" -o -name "*config*" | head -10`
Expected: path to existing settings component

- [ ] **Step 2: Add provider key management section to settings**

Add a new section to the existing settings page with inputs for each provider's API key:

```jsx
// Add to existing Settings component
const PROVIDERS = [
  { id: 'openai', name: 'OpenAI', hasBaseUrl: true, keyLabel: 'API Key' },
  { id: 'google', name: 'Google Gemini', keyLabel: 'API Key' },
  { id: 'qwen', name: '通义千问', hasBaseUrl: true, keyLabel: 'API Key' },
  { id: 'ernie', name: '文心一言', hasSecret: true, keyLabel: 'API Key', secretLabel: 'Secret Key' },
  { id: 'zhipu', name: '智谱', keyLabel: 'API Key' },
  { id: 'minimax', name: 'MiniMax', keyLabel: 'API Key' },
];

// Each provider gets:
// - API Key input (stored in localStorage)
// - Optional Base URL input
// - Optional Secret Key input (ERNIE)
// - "已配置 (来自 .env)" label if backend has the key
```

- [ ] **Step 3: Verify settings page renders**

Run: `cd qingqing/frontend && npm run dev`
Open: `http://localhost:5173/settings`
Expected: Provider key inputs visible for all 6 providers

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: add provider key management to settings page"
```

### Task 16: Module Pages — Provider/Model Dropdown

**Files:**
- Modify: existing photo/voice/music/video page components

- [ ] **Step 1: Create a shared ModelSelector component**

```jsx
// frontend/src/components/ModelSelector.jsx
import { useState, useEffect } from 'react';

export default function ModelSelector({ capability, value, onChange }) {
  const [models, setModels] = useState({});

  useEffect(() => {
    fetch('http://localhost:8001/api/models')
      .then(r => r.json())
      .then(data => {
        if (data.success) setModels(data.data.models);
      })
      .catch(console.error);
  }, []);

  const filtered = Object.entries(models)
    .filter(([_, m]) => m.enabled && m.capabilities.includes(capability))
    .sort((a, b) => a[1].provider.localeCompare(b[1].provider));

  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      className="bg-gray-800 text-sm rounded-lg px-3 py-1.5 border border-gray-700">
      {filtered.length === 0 && <option>无可用模型</option>}
      {Object.entries(
        filtered.reduce((acc, [id, m]) => {
          (acc[m.provider] = acc[m.provider] || []).push({ id, ...m });
          return acc;
        }, {})
      ).map(([provider, modelList]) => (
        <optgroup key={provider} label={provider}>
          {modelList.map(m => (
            <option key={m.id} value={m.id}>{m.display_name}{m.supports_vision ? ' 👁' : ''}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
```

- [ ] **Step 2: Add ModelSelector to each module page**

Add to photo, voice, music, video pages:

```jsx
import ModelSelector from '../components/ModelSelector';

// In each page's toolbar/header area:
<ModelSelector
  capability="image"  // or "chat", "tts", "music", "video" per page
  value={selectedModel}
  onChange={setSelectedModel}
/>
```

- [ ] **Step 3: Verify dropdowns show correct models per capability**

Open each module page and verify:
- Photo page: shows image-capable models (DALL-E 3, 通义万相, CogView-3, etc.)
- Voice page: shows TTS-capable models (TTS-1, MiniMax TTS)
- Music page: shows music-capable models (MiniMax Music)
- Video page: shows video-capable models (MiniMax Video)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: add ModelSelector dropdown to all module pages"
```

### Task 17: New Chat Page

**Files:**
- Create: `frontend/src/pages/Chat.jsx`
- Modify: `frontend/src/App.jsx` (add /chat route)

- [ ] **Step 1: Create Chat page with streaming**

```jsx
// frontend/src/pages/Chat.jsx
import { useState, useRef, useEffect } from 'react';
import ModelSelector from '../components/ModelSelector';

export default function Chat() {
  const [model, setModel] = useState('openai:gpt-4o');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const getHeaders = () => {
    const provider = model.split(':')[0];
    const keys = JSON.parse(localStorage.getItem('providerApiKeys') || '{}');
    const urls = JSON.parse(localStorage.getItem('providerBaseUrls') || '{}');
    const headers = { 'Content-Type': 'application/json' };
    const keyMap = { openai: 'X-OpenAI-API-Key', google: 'X-Google-API-Key', qwen: 'X-QWEN-API-Key', ernie: 'X-ERNIE-API-Key', zhipu: 'X-ZHIPU-API-Key', minimax: 'X-MiniMax-API-Key' };
    const urlMap = { openai: 'X-OpenAI-Base-URL', qwen: 'X-QWEN-Base-URL' };
    if (keys[provider]) headers[keyMap[provider]] = keys[provider];
    if (urls[provider]) headers[urlMap[provider]] = urls[provider];
    return headers;
  };

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    const userMsg = { role: 'user', content: input.trim() };
    const newMessages = [...messages, userMsg, { role: 'assistant', content: '' }];
    setMessages(newMessages);
    setInput('');
    setIsStreaming(true);

    try {
      const resp = await fetch('http://localhost:8001/api/chat', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ model, messages: newMessages.filter(m => m.content).map(m => ({ role: m.role, content: m.content })), stream: true }),
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') continue;
          try {
            const chunk = JSON.parse(data);
            fullContent += chunk.delta || '';
            setMessages(prev => {
              const updated = [...prev];
              updated[updated.length - 1] = { ...updated[updated.length - 1], content: fullContent };
              return updated;
            });
          } catch {}
        }
      }
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: 'assistant', content: `Error: ${err.message}` };
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100">
      <header className="h-12 bg-gray-900 border-b border-gray-800 flex items-center px-4 gap-4">
        <h1 className="text-sm font-medium">Chat</h1>
        <ModelSelector capability="chat" value={model} onChange={setModel} />
      </header>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[70%] px-4 py-2 rounded-2xl text-sm ${msg.role === 'user' ? 'bg-blue-600' : 'bg-gray-800'}`}>
              <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="p-4 border-t border-gray-800">
        <div className="flex gap-2">
          <input value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="输入消息... (Enter 发送)"
            className="flex-1 px-4 py-2 bg-gray-800 rounded-xl text-sm border border-gray-700 focus:border-blue-500 outline-none"
            disabled={isStreaming} />
          <button onClick={handleSend} disabled={isStreaming}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-xl text-sm">
            {isStreaming ? '...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add /chat route to App.jsx**

Add to existing routes:

```jsx
import Chat from './pages/Chat';

// In Routes:
<Route path="/chat" element={<Chat />} />
```

- [ ] **Step 3: Add Chat to navigation**

Add a "Chat" link to the existing sidebar/navigation.

- [ ] **Step 4: Verify chat page works**

Open `http://localhost:5173/chat`, select a model, send a message, verify streaming response.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: add /chat page with multi-provider streaming"
```

---

## Chunk 5: Integration Testing + Visual Verification

### Task 18: Backend Integration Tests

- [ ] **Step 1: Run existing tests (must still pass)**

Run: `cd backend && python -m pytest -v`
Expected: `36 passed, 9 skipped` (same as baseline)

- [ ] **Step 2: Test /api/models endpoint**

Run: `curl http://localhost:8001/api/models | python -m json.tool`
Expected: JSON with all 18 models, `enabled` flags based on configured keys

- [ ] **Step 3: Test /api/chat with configured provider**

Run: `curl -X POST http://localhost:8001/api/chat -H "Content-Type: application/json" -d '{"model":"openai:gpt-4o","messages":[{"role":"user","content":"Say hi"}],"stream":false}'`
Expected: `{"success":true,"model":"openai:gpt-4o","provider":"openai","data":{...}}`

- [ ] **Step 4: Test error cases**

Run: `curl -X POST http://localhost:8001/api/chat -H "Content-Type: application/json" -d '{"model":"nonexistent:model","messages":[]}'`
Expected: `{"success":false,"error":{"message":"Model not found: nonexistent:model","code":"model_not_found"}}`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: verify gateway integration"
```

### Task 19: Frontend Visual Verification

- [ ] **Step 1: Verify old pages still work**

Open each existing page and verify no regressions:
- `/dashboard` — workbench loads
- `/photo` — image generation works with MiniMax
- `/voice` — TTS works
- `/music` — music generation works
- `/video` — video generation works
- `/token` — token plan display works
- `/settings` — new provider key section visible

- [ ] **Step 2: Verify new Chat page**

Open `/chat`:
- Model dropdown shows all enabled chat models grouped by provider
- Send message → streaming response works
- Switch model → next message goes to new provider

- [ ] **Step 3: Visual check at two viewport sizes**

- `390x844` (mobile): all pages usable, no overflow
- `1440x900` (desktop): all pages properly laid out

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: complete multi-provider upgrade with dual-track integration"
```

---

## Summary

| Chunk | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-4 | Gateway skeleton: schemas, adapter base, registry, config, task store |
| 2 | 5-10 | All 6 provider adapters: OpenAI, Gemini, Qwen, ERNIE, Zhipu, MiniMax |
| 3 | 11-14 | Unified API routers + error handling + register in main app |
| 4 | 15-17 | Frontend: settings keys, module dropdowns, new Chat page |
| 5 | 18-19 | Integration testing + visual verification |
