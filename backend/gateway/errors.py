from fastapi import Request
from fastapi.responses import JSONResponse
from gateway.adapters.base import CapabilityNotSupported


class ProviderError(Exception):
    def __init__(self, provider: str, message: str, code: str = "provider_error"):
        self.provider = provider
        self.message = message
        self.code = code
        super().__init__(message)


class AuthError(Exception):
    def __init__(self, provider: str, message: str, code: str = "auth_missing"):
        self.provider = provider
        self.message = message
        self.code = code
        super().__init__(message)


class ModelNotFoundError(Exception):
    def __init__(self, model_id: str):
        self.model_id = model_id
        super().__init__(f"Model not found: {model_id}")


async def model_not_found_handler(request: Request, exc: ModelNotFoundError):
    return JSONResponse(status_code=404, content={"success": False, "error": {"message": f"Model not found: {exc.model_id}", "code": "model_not_found"}})


async def capability_handler(request: Request, exc: CapabilityNotSupported):
    return JSONResponse(status_code=400, content={"success": False, "error": {"message": f"Provider '{exc.provider_id}' does not support: {exc.capability}", "code": "capability_not_supported", "provider": exc.provider_id}})


async def auth_handler(request: Request, exc: AuthError):
    return JSONResponse(status_code=401, content={"success": False, "error": {"message": exc.message, "code": exc.code, "provider": exc.provider}})


async def provider_handler(request: Request, exc: ProviderError):
    return JSONResponse(status_code=502, content={"success": False, "error": {"message": f"Provider API error: {exc.message}", "code": exc.code, "provider": exc.provider}})


async def generic_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"success": False, "error": {"message": "Internal server error", "code": "internal_error"}})
