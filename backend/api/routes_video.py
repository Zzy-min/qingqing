import asyncio
import base64
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException

from api.key_override import normalize_override_key
from api.schemas_video import VideoGenerateRequest, VideoTaskRequest, VideoResponse
from services.video import VideoService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["video"])

_video_service: Optional[VideoService] = None
_video_lock = asyncio.Lock()


async def get_video_service() -> VideoService:
    global _video_service
    if _video_service is None:
        async with _video_lock:
            if _video_service is None:
                _video_service = VideoService()
    return _video_service


async def _resolve_video_service(
    x_minimax_api_key: Optional[str],
) -> tuple[VideoService, bool]:
    override_key = normalize_override_key(x_minimax_api_key)
    if override_key:
        return VideoService(api_key=override_key), True
    return await get_video_service(), False


async def _fetch_video_as_data_url(video_url: str) -> str:
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.get(video_url)
        resp.raise_for_status()
    content_type = resp.headers.get("content-type", "video/mp4")
    b64 = base64.b64encode(resp.content).decode("ascii")
    return f"data:{content_type};base64,{b64}"


@router.post("/video/generate", response_model=VideoResponse)
async def generate_video(
    request: VideoGenerateRequest,
    x_minimax_api_key: Optional[str] = Header(default=None, alias='X-MiniMax-API-Key'),
):
    service, close_after = await _resolve_video_service(x_minimax_api_key)
    try:
        result = await service.generate_video(
            prompt=request.prompt,
            model=request.model,
            first_frame=request.first_frame,
            last_frame=request.last_frame,
            subject_image=request.subject_image,
            duration=request.duration,
            resolution=request.resolution,
            prompt_optimizer=request.prompt_optimizer,
            fast_pretreatment=request.fast_pretreatment,
            aigc_watermark=request.aigc_watermark,
            callback_url=request.callback_url,
            no_wait=request.no_wait,
        )

        task_id = result.get("task_id")
        status = result.get("status")
        model_adjustment = result.get("model_adjustment")

        # Async mode — return task_id immediately
        if request.no_wait or status == "Pending":
            if not task_id:
                raise HTTPException(status_code=502, detail="Video task submission succeeded but task_id is missing")
            message = "Video generation submitted (use /video/task to poll status)"
            if model_adjustment:
                message += f" | {model_adjustment}"
            return VideoResponse(
                success=True,
                task_id=task_id,
                status=status or "Pending",
                message=message,
            )

        # Sync mode — poll until done
        file_id = result.get("file_id")
        if not file_id:
            # Polling already happened inside generate_video, check result
            raw = result.get("_raw", {})
            file_id = raw.get("file_id")

        if file_id:
            download_url = await service.get_download_url(file_id)
            if download_url:
                try:
                    data_url = await _fetch_video_as_data_url(download_url)
                    return VideoResponse(
                        success=True,
                        task_id=task_id,
                        status=status or "Success",
                        video_data=data_url,
                        video_width=result.get("_raw", {}).get("video_width"),
                        video_height=result.get("_raw", {}).get("video_height"),
                        message=("Video generated successfully" + (f" | {model_adjustment}" if model_adjustment else "")),
                    )
                except Exception as e:
                    logger.warning("Failed to fetch video: %s", e)
                    return VideoResponse(
                        success=True,
                        task_id=task_id,
                        status=status or "Success",
                        video_url=download_url,
                        video_width=result.get("_raw", {}).get("video_width"),
                        video_height=result.get("_raw", {}).get("video_height"),
                        message=("Video generated (direct URL)" + (f" | {model_adjustment}" if model_adjustment else "")),
                    )

        return VideoResponse(
            success=True,
            task_id=task_id,
            status=status,
            message=("Video generation completed" + (f" | {model_adjustment}" if model_adjustment else "")),
        )

    except httpx.HTTPStatusError as e:
        logger.error("Video API error: %s %s", e.response.status_code, e.response.text[:200])
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text[:200])
    except httpx.RequestError as e:
        logger.error("Video network error: %s", e)
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in generate_video")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        if close_after:
            try:
                await service.close()
            except Exception:
                logger.warning("Failed to close request-scoped video service")


@router.post("/video/task", response_model=VideoResponse)
async def query_video_task(
    request: VideoTaskRequest,
    x_minimax_api_key: Optional[str] = Header(default=None, alias='X-MiniMax-API-Key'),
):
    service, close_after = await _resolve_video_service(x_minimax_api_key)
    try:
        result = await service.query_task(request.task_id)
        status = result.get("status", "Unknown")
        file_id = result.get("file_id")
        if status == "Failed":
            return VideoResponse(
                success=False,
                task_id=request.task_id,
                status=status,
                message=result.get("message") or result.get("status_msg") or "Video task failed",
            )

        if status == "Success" and not file_id:
            return VideoResponse(
                success=False,
                task_id=request.task_id,
                status=status,
                message="Video task reported Success but no file_id was returned",
            )

        if status == "Success" and file_id:
            download_url = await service.get_download_url(file_id)
            if download_url:
                try:
                    data_url = await _fetch_video_as_data_url(download_url)
                    return VideoResponse(
                        success=True,
                        task_id=request.task_id,
                        status=status,
                        video_data=data_url,
                        video_width=result.get("video_width"),
                        video_height=result.get("video_height"),
                        message="Video ready",
                    )
                except Exception as e:
                    logger.warning("Failed to fetch video in query: %s", e)
                    return VideoResponse(
                        success=True,
                        task_id=request.task_id,
                        status=status,
                        video_url=download_url,
                        video_width=result.get("video_width"),
                        video_height=result.get("video_height"),
                        message="Video ready (direct URL)",
                    )

        return VideoResponse(
            success=True,
            task_id=request.task_id,
            status=status,
            message=f"Video task status: {status}",
        )

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text[:200])
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in query_video_task")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        if close_after:
            try:
                await service.close()
            except Exception:
                logger.warning("Failed to close request-scoped video service")
