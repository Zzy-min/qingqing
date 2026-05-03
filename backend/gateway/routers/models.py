from fastapi import APIRouter
from fastapi.responses import JSONResponse
from gateway.registry.models import list_models
from gateway.config import get_keys

router = APIRouter(prefix="/api", tags=["gateway-models"])


@router.get("/models")
async def list_models_endpoint():
    keys = get_keys()
    available = keys.available_providers()
    models = list_models(available_providers=available)
    return JSONResponse({"success": True, "data": {"models": models}})
