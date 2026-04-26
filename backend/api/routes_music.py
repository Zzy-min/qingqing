import asyncio
import base64
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException

from api.key_override import normalize_override_key
from api.schemas_music import MusicGenerateRequest, MusicCoverRequest, MusicResponse
from services.music import MusicService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["music"])

_music_service: Optional[MusicService] = None
_music_lock = asyncio.Lock()


async def get_music_service() -> MusicService:
    global _music_service
    if _music_service is None:
        async with _music_lock:
            if _music_service is None:
                _music_service = MusicService()
    return _music_service


async def _resolve_music_service(
    x_minimax_api_key: Optional[str],
) -> tuple[MusicService, bool]:
    override_key = normalize_override_key(x_minimax_api_key)
    if override_key:
        return MusicService(api_key=override_key), True
    return await get_music_service(), False


async def _fetch_audio_as_data_url(audio_url: str) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(audio_url)
        resp.raise_for_status()
    content_type = resp.headers.get("content-type", "audio/mpeg")
    b64 = base64.b64encode(resp.content).decode("ascii")
    return f"data:{content_type};base64,{b64}"


@router.post("/music/generate", response_model=MusicResponse)
async def generate_music(
    request: MusicGenerateRequest,
    x_minimax_api_key: Optional[str] = Header(default=None, alias='X-MiniMax-API-Key'),
):
    """Generate music. MiniMax returns audio directly (status=2), no polling needed."""
    service, close_after = await _resolve_music_service(x_minimax_api_key)
    try:
        result = await service.generate_music(
            prompt=request.prompt,
            lyrics=request.lyrics,
            instrumental=request.instrumental,
            lyrics_optimizer=request.lyrics_optimizer,
            model=request.model,
            vocals=request.vocals,
            genre=request.genre,
            mood=request.mood,
            instruments=request.instruments,
            tempo=request.tempo,
            bpm=request.bpm,
            key=request.key,
            avoid=request.avoid,
            use_case=request.use_case,
            structure=request.structure,
            references=request.references,
            extra=request.extra,
            format=request.format,
            sample_rate=request.sample_rate,
            bitrate=request.bitrate,
            aigc_watermark=request.aigc_watermark,
        )

        audio_url = result.get("audio_url")
        task_id = result.get("task_id")

        # Music returns a public OSS URL — return it directly, no fetch needed
        if audio_url:
            return MusicResponse(
                success=True,
                audio_url=audio_url,
                task_id=task_id,
                message="Music generated successfully",
            )

        status = result.get("status")
        if status in (None, 1):
            if task_id:
                return MusicResponse(
                    success=True,
                    task_id=task_id,
                    message="Music generation submitted, audio not ready yet",
                )
        raise HTTPException(status_code=502, detail=f"No audio_url in music response (status={status})")

    except httpx.HTTPStatusError as e:
        logger.error("Music API error: %s %s", e.response.status_code, e.response.text[:200])
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text[:200])
    except httpx.RequestError as e:
        logger.error("Music network error: %s", e)
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in generate_music")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        if close_after:
            try:
                await service.close()
            except Exception:
                logger.warning("Failed to close request-scoped music service")


@router.get("/music/task/{task_id}", response_model=MusicResponse)
async def get_music_task_status(
    task_id: str,
    x_minimax_api_key: Optional[str] = Header(default=None, alias='X-MiniMax-API-Key'),
):
    """Poll music generation task status."""
    service, close_after = await _resolve_music_service(x_minimax_api_key)
    try:
        task = await service.get_music_task(task_id)
        audio_url = task.get("audio_url")
        status = task.get("status", "unknown")

        if status == 2 and audio_url:
            try:
                data_url = await _fetch_audio_as_data_url(audio_url)
                return MusicResponse(success=True, audio_data=data_url, task_id=task_id, message="Music ready")
            except Exception:
                return MusicResponse(success=True, audio_url=audio_url, task_id=task_id, message="Music ready (direct URL)")
        elif status == 3:
            return MusicResponse(success=False, task_id=task_id, message=f"Music generation failed: {task.get('status_msg', 'Unknown')}")
        else:
            return MusicResponse(success=True, task_id=task_id, message=f"Music generation status={status}: not ready yet")

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text[:200])
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in get_music_task_status")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        if close_after:
            try:
                await service.close()
            except Exception:
                logger.warning("Failed to close request-scoped music service")


@router.post("/music/cover", response_model=MusicResponse)
async def generate_music_cover(
    request: MusicCoverRequest,
    x_minimax_api_key: Optional[str] = Header(default=None, alias='X-MiniMax-API-Key'),
):
    service, close_after = await _resolve_music_service(x_minimax_api_key)
    try:
        result = await service.generate_cover(
            prompt=request.prompt,
            audio_url=request.audio_url,
            audio_data=request.audio_data,
            lyrics=request.lyrics,
            model=request.model,
            seed=request.seed,
            format=request.format,
            sample_rate=request.sample_rate,
            bitrate=request.bitrate,
            channels=request.channels,
        )

        audio_url = result.get("audio_url")
        task_id = result.get("task_id")

        if audio_url:
            return MusicResponse(
                success=True,
                audio_url=audio_url,
                task_id=task_id,
                message="Music cover generated successfully",
            )

        status = result.get("status")
        if status in (None, 1):
            if task_id:
                return MusicResponse(success=True, task_id=task_id, message="Music cover submitted, audio not ready yet")
        raise HTTPException(status_code=502, detail=f"No audio_url in music cover response (status={status})")

    except httpx.HTTPStatusError as e:
        logger.error("Music cover API error: %s %s", e.response.status_code, e.response.text[:200])
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text[:200])
    except httpx.RequestError as e:
        logger.error("Music cover network error: %s", e)
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in generate_music_cover")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        if close_after:
            try:
                await service.close()
            except Exception:
                logger.warning("Failed to close request-scoped music service")
