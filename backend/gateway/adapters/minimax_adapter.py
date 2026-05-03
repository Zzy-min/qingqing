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
