# backend/gateway/task_store.py
import time
import uuid
from gateway.schemas.task import TaskStatus, TaskStatusEnum

_store: dict[str, TaskStatus] = {}
TASK_TTL = 3600
TASK_TIMEOUT = 300


def create_task() -> TaskStatus:
    task_id = str(uuid.uuid4())[:8]
    now = time.time()
    task = TaskStatus(task_id=task_id, status=TaskStatusEnum.PENDING, created_at=now, expires_at=now + TASK_TTL)
    _store[task_id] = task
    return task


def update_task(task_id: str, **kwargs) -> TaskStatus | None:
    task = _store.get(task_id)
    if not task:
        return None
    for k, v in kwargs.items():
        setattr(task, k, v)
    return task


def get_task(task_id: str) -> TaskStatus | None:
    task = _store.get(task_id)
    if not task:
        return None
    if time.time() > task.expires_at:
        task.status = TaskStatusEnum.EXPIRED
    return task
