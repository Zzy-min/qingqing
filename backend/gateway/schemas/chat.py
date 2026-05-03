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
