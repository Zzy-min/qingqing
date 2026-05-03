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
