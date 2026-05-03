from pydantic import BaseModel


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int


class UnifiedResponse(BaseModel):
    success: bool = True
    model: str | None = None
    provider: str | None = None
    data: dict | None = None
    task: dict | None = None
    error: dict | None = None
