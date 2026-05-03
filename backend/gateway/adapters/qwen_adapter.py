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
