from pydantic import BaseModel
from enum import Enum


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class TaskStatus(BaseModel):
    task_id: str
    status: TaskStatusEnum
    progress: float | None = None
    result: dict | None = None
    error: str | None = None
    created_at: float
    expires_at: float
