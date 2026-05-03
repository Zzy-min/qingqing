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
