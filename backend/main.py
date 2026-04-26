import os
import logging
from pathlib import Path

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

app = FastAPI(
    title="MiniMax Photo Agent API",
    description="MiniMax multimodal workbench API",
    version=APP_VERSION,
)

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
    return await call_next(request)


# CORS: default localhost only, configurable via CORS_ORIGINS env var (comma-separated)
_default_origins = [
    "http://localhost:3000", "http://localhost:3001", "http://localhost:8001",
    "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:8001",
]
_cors_origins = os.getenv("CORS_ORIGINS")
if _cors_origins:
    _default_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(tts_router, prefix="/api")
app.include_router(music_router, prefix="/api")
app.include_router(video_router, prefix="/api")

# TTS output files (local storage to avoid CORS)
TTS_AUDIO_DIR = get_tts_audio_dir()
os.makedirs(TTS_AUDIO_DIR, exist_ok=True)
app.mount("/api/tts/audio", StaticFiles(directory=TTS_AUDIO_DIR), name="tts_audio")

def _resolve_static_path() -> str:
    backend_dir = Path(__file__).resolve().parent
    candidates = [
        backend_dir / "static",
        backend_dir.parent / "frontend" / "temp-build",
        backend_dir.parent / "frontend" / "dist",
    ]
    existing = []
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            index_file = candidate / "index.html"
            mtime = index_file.stat().st_mtime if index_file.exists() else candidate.stat().st_mtime
            existing.append((mtime, candidate))
    if existing:
        newest = max(existing, key=lambda item: item[0])[1]
        return str(newest)
    return str(backend_dir / "static")


static_path = _resolve_static_path()
static_root = Path(static_path).resolve()
if static_root.exists():
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


@app.on_event("startup")
async def startup():
    logger = logging.getLogger(__name__)
    logger.info("MiniMax Photo Agent API v%s starting up...", APP_VERSION)
    config = load_minimax_config()
    log_minimax_bases(logger, config)


@app.on_event("shutdown")
async def shutdown():
    logger = logging.getLogger(__name__)
    logger.info("Shutting down MiniMax Photo Agent...")
    for name, getter in [
        ("MiniMax", get_minimax_service),
        ("TokenPlan", get_token_plan_service),
        ("TTS", get_tts_service),
        ("Music", get_music_service),
        ("Video", get_video_service),
    ]:
        try:
            svc = await getter()
            if svc is not None and hasattr(svc, "close"):
                await svc.close()
                logger.info("%s HTTP client closed.", name)
        except Exception as e:
            logger.warning("Error closing %s service: %s", name, e)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
