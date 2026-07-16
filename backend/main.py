import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from services.minimax_config import get_tts_audio_dir, load_minimax_config, log_minimax_bases
from version import APP_VERSION

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from api.routes import router, get_minimax_service, get_token_plan_service
from api.routes_tts import router as tts_router, get_tts_service
from api.routes_music import router as music_router, get_music_service
from api.routes_video import router as video_router, get_video_service
from gateway.adapters import discover_adapters
from qingqing_v1.observability import RequestIdMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger = logging.getLogger(__name__)
    logger.info("轻青 API v%s starting up...", APP_VERSION)
    config = load_minimax_config()
    log_minimax_bases(logger, config)
    discover_adapters()
    try:
        yield
    finally:
        logger.info("Shutting down 轻青 API...")
        for name, getter in [
            ("MiniMax", get_minimax_service),
            ("TokenPlan", get_token_plan_service),
            ("TTS", get_tts_service),
            ("Music", get_music_service),
            ("Video", get_video_service),
        ]:
            try:
                service = await getter()
                if service is not None and hasattr(service, "close"):
                    await service.close()
                    logger.info("%s HTTP client closed.", name)
            except Exception as exception:
                logger.warning("Error closing %s service: %s", name, exception)

app = FastAPI(
    title="轻青 API",
    description="轻青个人创作 Agent 与多模态工作台 API",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)

MAX_REQUEST_BODY = 20 * 1024 * 1024
MAX_REQUEST_BODY_MUSIC_COVER = 80 * 1024 * 1024
REQUEST_BODY_LIMITS = {
    "/api/music/cover": MAX_REQUEST_BODY_MUSIC_COVER,
}


def request_body_limit_for_path(path: str) -> int:
    return REQUEST_BODY_LIMITS.get(path, MAX_REQUEST_BODY)


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    content_length = request.headers.get("content-length")
    max_body = request_body_limit_for_path(request.url.path)
    if content_length:
        try:
            if int(content_length) > max_body:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large (max {max_body // 1024 // 1024}MB)"},
                )
        except ValueError:
            pass
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > max_body:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large (max {max_body // 1024 // 1024}MB)"},
                )
        # Starlette's _CachedRequest forwards _body to the downstream app.
        # Keeping the bounded copy here also preserves normal JSON/form parsing.
        request._body = bytes(body)
    return await call_next(request)


LOCAL_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",
    "http://localhost:8001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8001",
]


def resolve_cors_origins(environment: str | None, configured: str | None) -> list[str]:
    """Use exact configured origins; localhost defaults exist only outside production."""
    if configured:
        values = []
        for raw in configured.split(","):
            origin = raw.strip().rstrip("/")
            if not origin:
                continue
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"}:
                raise RuntimeError(f"Invalid CORS origin: {origin}")
            if origin not in values:
                values.append(origin)
        return values
    if (environment or "development").strip().lower() == "production":
        return []
    return list(LOCAL_CORS_ORIGINS)


_cors_origins = resolve_cors_origins(
    os.getenv("QINGQING_ENVIRONMENT"),
    os.getenv("CORS_ORIGINS"),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "Idempotency-Key"],
)

def legacy_api_enabled() -> bool:
    """Legacy routes bypass the Agent ledger, so expose them only by opt-in."""
    return (
        os.environ.get("QINGQING_ALLOW_LOCAL_USER", "false").lower() == "true"
        and os.environ.get("QINGQING_ENABLE_LEGACY_API", "false").lower() == "true"
    )


LEGACY_API_ENABLED = legacy_api_enabled()
if LEGACY_API_ENABLED:
    app.include_router(router, prefix="/api")
    app.include_router(tts_router, prefix="/api")
    app.include_router(music_router, prefix="/api")
    app.include_router(video_router, prefix="/api")

# ── Gateway: Multi-Provider Unified API ──
from gateway.routers import chat as gw_chat, image as gw_image, tts as gw_tts, music as gw_music, video as gw_video, models as gw_models, tasks as gw_tasks
from gateway.errors import ModelNotFoundError, AuthError, ProviderError
from gateway.errors import model_not_found_handler, capability_handler, auth_handler, provider_handler, generic_handler
from gateway.adapters.base import CapabilityNotSupported as _CapNotSupported

app.add_exception_handler(ModelNotFoundError, model_not_found_handler)
app.add_exception_handler(_CapNotSupported, capability_handler)
app.add_exception_handler(AuthError, auth_handler)
app.add_exception_handler(ProviderError, provider_handler)
app.add_exception_handler(Exception, generic_handler)

if LEGACY_API_ENABLED:
    app.include_router(gw_chat.router)
    app.include_router(gw_image.router)
    app.include_router(gw_tts.router)
    app.include_router(gw_music.router)
    app.include_router(gw_video.router)
    app.include_router(gw_models.router)
    app.include_router(gw_tasks.router)
from qingqing_v1.router import router as qingqing_v1_router
app.include_router(qingqing_v1_router)

# TTS output files (local storage to avoid CORS)
TTS_AUDIO_DIR = get_tts_audio_dir()
os.makedirs(TTS_AUDIO_DIR, exist_ok=True)
if LEGACY_API_ENABLED:
    app.mount("/api/tts/audio", StaticFiles(directory=TTS_AUDIO_DIR), name="tts_audio")

def _resolve_static_path(project_root: Path | None = None) -> str | None:
    """Resolve one explicit web product; never fall back across product lines."""
    root = project_root or Path(__file__).resolve().parent.parent
    client = os.getenv("QINGQING_WEB_CLIENT", "flutter").strip().lower()
    candidates_by_client = {
        "flutter": [root / "apps" / "qingqing_flutter" / "build" / "web"],
        "react": [
            root / "frontend" / "dist",
            root / "frontend" / "temp-build",
            root / "backend" / "static",
        ],
        "none": [],
    }
    if client not in candidates_by_client:
        raise RuntimeError(
            "QINGQING_WEB_CLIENT must be one of: flutter, react, none"
        )

    existing = []
    for candidate in candidates_by_client[client]:
        index_file = candidate / "index.html"
        if candidate.is_dir() and index_file.is_file():
            existing.append((index_file.stat().st_mtime, candidate))
    if not existing:
        return None
    return str(max(existing, key=lambda item: item[0])[1])


static_path = _resolve_static_path()
static_root = Path(static_path).resolve() if static_path else None
if static_root is not None:
    assets_path = static_root / "assets"
    if assets_path.exists() and assets_path.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="frontend_assets")

    @app.get("/", include_in_schema=False)
    async def serve_frontend_index():
        return FileResponse(static_root / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_frontend(path: str):
        reserved_prefixes = ("api/", "docs/", "redoc/", "openapi.json")
        if path in ("docs", "redoc", "openapi.json") or path.startswith(reserved_prefixes):
            raise HTTPException(status_code=404, detail="Not Found")

        target = (static_root / path).resolve()
        if str(target).startswith(str(static_root)) and target.exists() and target.is_file():
            return FileResponse(target)

        return FileResponse(static_root / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
