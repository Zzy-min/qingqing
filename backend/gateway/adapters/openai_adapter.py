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
