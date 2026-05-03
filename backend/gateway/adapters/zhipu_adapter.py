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
