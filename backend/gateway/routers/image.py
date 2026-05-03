from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from gateway.schemas.image import ImageRequest
from gateway.registry.models import get_model
from gateway.adapters.base import Capability
from gateway.adapters import get_adapter
from gateway.config import get_api_key
from gateway.errors import ModelNotFoundError, AuthError, ProviderError

router = APIRouter(prefix="/api", tags=["gateway-image"])


@router.post("/image")
async def image_endpoint(request_body: ImageRequest, x_openai_api_key: str | None = Header(None), x_google_api_key: str | None = Header(None), x_qwen_api_key: str | None = Header(None), x_ernie_api_key: str | None = Header(None), x_ernie_secret_key: str | None = Header(None), x_zhipu_api_key: str | None = Header(None), x_minimax_api_key: str | None = Header(None)):
    model_entry = get_model(request_body.model)
    if not model_entry:
        raise ModelNotFoundError(request_body.model)
    if Capability.IMAGE not in model_entry.capabilities:
        raise ProviderError(model_entry.provider, "Model does not support image generation", "capability_not_supported")

    header_keys = {"openai": x_openai_api_key, "google": x_google_api_key, "qwen": x_qwen_api_key, "ernie": x_ernie_api_key, "zhipu": x_zhipu_api_key, "minimax": x_minimax_api_key}
    api_key = get_api_key(model_entry.provider, header_keys.get(model_entry.provider))
    if not api_key:
        raise AuthError(model_entry.provider, f"API key not configured for: {model_entry.provider}")

    adapter = get_adapter(model_entry.provider)
    result = await adapter.image(request_body)
    return JSONResponse({"success": True, "model": request_body.model, "provider": model_entry.provider, "data": result.model_dump()})
