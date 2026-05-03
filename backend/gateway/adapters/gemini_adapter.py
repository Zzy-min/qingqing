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
