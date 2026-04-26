import asyncio
import base64
import logging
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException

from api.key_override import normalize_override_key
from api.schemas_tts import TTSRequest, TTSResponse, VoiceItem, VoiceListResponse
from services.tts import TTSService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tts"])

_tts_service: Optional[TTSService] = None
_tts_lock = asyncio.Lock()

# Static fallback voices (confirmed working with speech-2.8-hd)
FALLBACK_VOICES = [
    "male-qn-qingse",
    "male-qn-jingying",
    "male-qn-badao",
    "male-qn-daxuesheng",
    "female-shaonv",
    "female-yujie",
    "female-chengshu",
    "female-tianmei",
    "male-qn-qingse-jingpin",
    "male-qn-jingying-jingpin",
    "male-qn-badao-jingpin",
    "male-qn-daxuesheng-jingpin",
    "female-shaonv-jingpin",
    "female-yujie-jingpin",
    "female-chengshu-jingpin",
    "female-tianmei-jingpin",
    "English_expressive_narrator",
]

FALLBACK_VOICE_NAMES: Dict[str, str] = {
    "male-qn-qingse": "青涩青年音色",
    "male-qn-jingying": "精英青年音色",
    "male-qn-badao": "霸道青年音色",
    "male-qn-daxuesheng": "青年大学生音色",
    "female-shaonv": "少女音色",
    "female-yujie": "御姐音色",
    "female-chengshu": "成熟女性音色",
    "female-tianmei": "甜美女性音色",
    "male-qn-qingse-jingpin": "青涩青年音色-beta",
    "male-qn-jingying-jingpin": "精英青年音色-beta",
    "male-qn-badao-jingpin": "霸道青年音色-beta",
    "male-qn-daxuesheng-jingpin": "青年大学生音色-beta",
    "female-shaonv-jingpin": "少女音色-beta",
    "female-yujie-jingpin": "御姐音色-beta",
    "female-chengshu-jingpin": "成熟女性音色-beta",
    "female-tianmei-jingpin": "甜美女性音色-beta",
    "English_expressive_narrator": "English expressive narrator",
}


def _fallback_voice_items() -> List[VoiceItem]:
    return [
        VoiceItem(
            voice_id=voice_id,
            voice_name=FALLBACK_VOICE_NAMES.get(voice_id),
            source="fallback",
        )
        for voice_id in FALLBACK_VOICES
    ]


async def get_tts_service() -> TTSService:
    global _tts_service
    if _tts_service is None:
        async with _tts_lock:
            if _tts_service is None:
                _tts_service = TTSService()
    return _tts_service


async def _resolve_tts_service(
    x_minimax_api_key: Optional[str],
) -> tuple[TTSService, bool]:
    override_key = normalize_override_key(x_minimax_api_key)
    if override_key:
        return TTSService(api_key=override_key), True
    return await get_tts_service(), False


async def _fetch_audio_as_data_url(audio_url: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(audio_url)
        resp.raise_for_status()
    content_type = resp.headers.get("content-type", "audio/mpeg")
    b64 = base64.b64encode(resp.content).decode("ascii")
    return f"data:{content_type};base64,{b64}"


@router.post("/tts/synthesize", response_model=TTSResponse)
async def synthesize_tts(
    request: TTSRequest,
    x_minimax_api_key: Optional[str] = Header(default=None, alias='X-MiniMax-API-Key'),
):
    service, close_after = await _resolve_tts_service(x_minimax_api_key)
    try:
        result = await service.synthesize(
            text=request.text,
            model=request.model,
            voice=request.voice,
            speed=request.speed,
            volume=request.volume,
            pitch=request.pitch,
            format=request.format,
            sample_rate=request.sample_rate,
            bitrate=request.bitrate,
            channels=request.channels,
            language_boost=request.language_boost,
            subtitles=request.subtitles,
            pronunciation=request.pronunciation,
        )

        audio_url = result.get("audio_url")
        extra_info = result.get("extra_info", {})

        if audio_url:
            try:
                data_url = await _fetch_audio_as_data_url(audio_url)
                return TTSResponse(
                    success=True,
                    audio_data=data_url,
                    duration_ms=extra_info.get("audio_length"),
                    sample_rate=extra_info.get("audio_sample_rate"),
                    subtitles=extra_info.get("subtitle_url") if request.subtitles else None,
                    message="TTS synthesized successfully",
                )
            except Exception as e:
                logger.warning("Failed to fetch TTS audio, returning URL: %s", e)
                return TTSResponse(
                    success=True,
                    audio_url=audio_url,
                    duration_ms=extra_info.get("audio_length"),
                    sample_rate=extra_info.get("audio_sample_rate"),
                    message="TTS synthesized (direct URL)",
                )
        else:
            raise HTTPException(status_code=502, detail="No audio URL in response")

    except httpx.HTTPStatusError as e:
        logger.error("TTS API error: %s %s", e.response.status_code, e.response.text[:200])
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text[:200])
    except httpx.RequestError as e:
        logger.error("TTS network error: %s", e)
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in synthesize_tts")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        if close_after:
            try:
                await service.close()
            except Exception:
                logger.warning("Failed to close request-scoped TTS service")


@router.get("/tts/voices", response_model=VoiceListResponse)
async def list_voices(
    x_minimax_api_key: Optional[str] = Header(default=None, alias='X-MiniMax-API-Key'),
):
    """Return list of available voices. Tries MiniMax API first, falls back to static list."""
    service, close_after = await _resolve_tts_service(x_minimax_api_key)
    try:
        raw_items = await service.list_voices()
        normalized_items = [
            VoiceItem(
                voice_id=item["voice_id"],
                voice_name=item.get("voice_name"),
                source=item.get("source"),
                description=item.get("description") or [],
                created_time=item.get("created_time"),
            )
            for item in raw_items
            if item.get("voice_id")
        ]
        voice_ids = [item.voice_id for item in normalized_items]
        if voice_ids:
            return VoiceListResponse(voices=voice_ids, items=normalized_items, source="official")
    except Exception as e:
        logger.warning("list_voices MiniMax API failed, using fallback: %s", e)
    finally:
        if close_after:
            try:
                await service.close()
            except Exception:
                logger.warning("Failed to close request-scoped TTS service")

    # Fallback: return static known voices
    return VoiceListResponse(
        voices=FALLBACK_VOICES,
        items=_fallback_voice_items(),
        source="fallback",
    )
