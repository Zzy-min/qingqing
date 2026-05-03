from pydantic import BaseModel


class TTSRequest(BaseModel):
    model: str
    input: str
    voice: str = "alloy"
    speed: float = 1.0
    response_format: str = "mp3"
