import asyncio
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from gateway.schemas.music import MusicRequest
from gateway.schemas.task import TaskStatusEnum
from gateway.registry.models import get_model
from gateway.adapters.base import Capability
from gateway.adapters import get_adapter
from gateway.config import get_api_key
from gateway.task_store import create_task, update_task
from gateway.errors import ModelNotFoundError, AuthError, ProviderError

router = APIRouter(prefix="/api", tags=["gateway-music"])


@router.post("/music")
async def music_endpoint(request_body: MusicRequest, x_minimax_api_key: str | None = Header(None)):
    model_entry = get_model(request_body.model)
    if not model_entry:
        raise ModelNotFoundError(request_body.model)
    if Capability.MUSIC not in model_entry.capabilities:
        raise ProviderError(model_entry.provider, "Model does not support music generation", "capability_not_supported")

    api_key = get_api_key(model_entry.provider, x_minimax_api_key)
    if not api_key:
        raise AuthError(model_entry.provider, f"API key not configured for: {model_entry.provider}")

    task = create_task()
    adapter = get_adapter(model_entry.provider)

    async def run():
        try:
            update_task(task.task_id, status=TaskStatusEnum.PROCESSING)
            result = await adapter.music(request_body)
            update_task(task.task_id, status=TaskStatusEnum.COMPLETED, result=result.model_dump())
        except Exception as e:
            update_task(task.task_id, status=TaskStatusEnum.FAILED, error=str(e))

    asyncio.create_task(run())
    return JSONResponse({"success": True, "task": {"task_id": task.task_id, "status": task.status.value}})
