from fastapi import APIRouter
from fastapi.responses import JSONResponse
from gateway.task_store import get_task

router = APIRouter(prefix="/api", tags=["gateway-tasks"])


@router.get("/tasks/{task_id}")
async def get_task_endpoint(task_id: str):
    task = get_task(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"success": False, "error": {"message": "Task not found or expired", "code": "task_not_found"}})
    return JSONResponse({"success": True, "data": task.model_dump()})
