import json
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse, JSONResponse
from gateway.schemas.chat import ChatRequest
from gateway.registry.models import get_model
from gateway.adapters.base import Capability
from gateway.adapters import get_adapter
from gateway.config import get_api_key, get_base_url
from gateway.errors import ModelNotFoundError, AuthError, ProviderError

router = APIRouter(prefix="/api", tags=["gateway-chat"])


@router.post("/chat")
async def chat_endpoint(
    request_body: ChatRequest,
    x_openai_api_key: str | None = Header(None),
    x_google_api_key: str | None = Header(None),
    x_qwen_api_key: str | None = Header(None),
    x_ernie_api_key: str | None = Header(None),
    x_ernie_secret_key: str | None = Header(None),
    x_zhipu_api_key: str | None = Header(None),
    x_minimax_api_key: str | None = Header(None),
    x_openai_base_url: str | None = Header(None),
    x_qwen_base_url: str | None = Header(None),
):
    model_entry = get_model(request_body.model)
    if not model_entry:
        raise ModelNotFoundError(request_body.model)
    if Capability.CHAT not in model_entry.capabilities:
        raise ProviderError(model_entry.provider, "Model does not support chat", "capability_not_supported")

    header_keys = {
        "openai": x_openai_api_key, "google": x_google_api_key, "qwen": x_qwen_api_key,
        "ernie": x_ernie_api_key, "zhipu": x_zhipu_api_key, "minimax": x_minimax_api_key,
    }
    header_urls = {"openai": x_openai_base_url, "qwen": x_qwen_base_url}
    api_key = get_api_key(model_entry.provider, header_keys.get(model_entry.provider))
    if not api_key:
        raise AuthError(model_entry.provider, f"API key not configured for: {model_entry.provider}")

    if model_entry.provider == "ernie":
        import os
        secret = x_ernie_secret_key or os.getenv("ERNIE_SECRET_KEY", "")
        if not secret:
            raise AuthError("ernie", "ERNIE requires both API_KEY and SECRET_KEY")

    adapter = get_adapter(model_entry.provider)
    base_url = get_base_url(model_entry.provider, header_urls.get(model_entry.provider))

    if request_body.stream:
        async def event_stream():
            try:
                async for chunk in adapter.chat(request_body):
                    yield f"data: {chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
            except Exception:
                yield f"data: {json.dumps({'error': 'Provider request failed', 'code': 'provider_error'})}\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        full_content = ""
        usage = None
        async for chunk in adapter.chat(request_body):
            full_content += chunk.delta
            if chunk.usage:
                usage = chunk.usage
        return JSONResponse({"success": True, "model": request_body.model, "provider": model_entry.provider,
                             "data": {"content": full_content, "finish_reason": "stop", "usage": usage.model_dump() if usage else None}})
