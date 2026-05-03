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
