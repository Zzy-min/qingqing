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
