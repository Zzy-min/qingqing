"""
MiniMax TTS Service — model: speech-2.8-hd (confirmed working 2026-04-23)
"""
import os
import logging
import uuid
from typing import Any, Dict, List, Optional

import httpx

from services.minimax_config import auth_headers, get_tts_audio_dir, load_minimax_config

logger = logging.getLogger(__name__)

TTS_MODEL_ALIAS_MAP = {
    "speech-2.6": "speech-2.6-hd",
    "speech-02": "speech-02-hd",
}

LANGUAGE_BOOST_MAP = {
    "auto": "auto",
    "zh": "Chinese",
    "zh-cn": "Chinese",
    "chinese": "Chinese",
    "yue": "Chinese,Yue",
    "zh-yue": "Chinese,Yue",
    "chinese,yue": "Chinese,Yue",
    "en": "English",
    "english": "English",
    "ja": "Japanese",
    "japanese": "Japanese",
    "ko": "Korean",
    "korean": "Korean",
    "fr": "French",
    "french": "French",
    "de": "German",
    "german": "German",
    "es": "Spanish",
    "spanish": "Spanish",
}

TTS_SPEED_MIN = 0.5
TTS_SPEED_MAX = 2.0
TTS_VOL_MIN = 0.01
TTS_VOL_MAX = 10.0
TTS_PITCH_MIN = -12
TTS_PITCH_MAX = 12


class TTSService:
    def __init__(self, api_key: Optional[str] = None):
        self.config = load_minimax_config(api_key=api_key)
        self.api_key = self.config.api_key
        self.headers = auth_headers(self.api_key)
        self.audio_dir = get_tts_audio_dir()
        os.makedirs(self.audio_dir, exist_ok=True)

    async def synthesize(
        self,
        text: str,
        model: str = "speech-2.8-hd",
        voice: str = "male-qn-qingse",
        speed: Optional[float] = 1.0,
        volume: Optional[float] = 1.0,
        pitch: Optional[float] = 0.0,
        format: str = "mp3",
        sample_rate: int = 32000,
        bitrate: int = 128000,
        channels: int = 1,
        language_boost: Optional[str] = None,
        subtitles: bool = False,
        pronunciation: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        payload = self._build_synthesize_payload(
            text=text,
            model=model,
            voice=voice,
            speed=speed,
            volume=volume,
            pitch=pitch,
            format=format,
            sample_rate=sample_rate,
            bitrate=bitrate,
            channels=channels,
            language_boost=language_boost,
            subtitles=subtitles,
            pronunciation=pronunciation,
        )

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.config.rest_base_url}/t2a_v2",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        status = data.get("base_resp", {}).get("status_code", 0)
        if status != 0:
            msg = data.get("base_resp", {}).get("status_msg", "unknown error")
            raise ValueError(f"TTS API error {status}: {msg}")

        resp_data = data.get("data", {})
        audio_url = None
        extra = resp_data.get("extra_info", {})

        # data.audio_url — try to download and save locally
        if resp_data.get("audio_url"):
            raw_url = resp_data["audio_url"]
            try:
                async with httpx.AsyncClient(timeout=60.0) as c:
                    audio_resp = await c.get(raw_url)
                    audio_resp.raise_for_status()
                audio_bytes = audio_resp.content
                file_id = str(uuid.uuid4())
                filename = f"{file_id}.{format or 'mp3'}"
                filepath = os.path.join(self.audio_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(audio_bytes)
                audio_url = f"/api/tts/audio/{filename}"
                logger.info(f"Saved TTS audio (URL) to {filepath}, size={len(audio_bytes)}")
            except Exception as e:
                logger.warning(f"Failed to download from {raw_url}: {e}")
                audio_url = raw_url

        # data.audio — hex-encoded binary MP3
        elif resp_data.get("audio"):
            hex_str = resp_data["audio"]
            try:
                audio_bytes = bytes.fromhex(hex_str)
                file_id = str(uuid.uuid4())
                filename = f"{file_id}.{format or 'mp3'}"
                filepath = os.path.join(self.audio_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(audio_bytes)
                audio_url = f"/api/tts/audio/{filename}"
                logger.info(f"Saved TTS audio (hex) to {filepath}, size={len(audio_bytes)}")
            except Exception as e:
                raise ValueError(f"Failed to decode audio hex: {e}")

        if not audio_url:
            raise ValueError("No audio in MiniMax response")

        return {
            "audio_url": audio_url,
            "audio_data": None,
            "extra_info": extra,
        }

    @staticmethod
    def _normalize_model(model: str) -> str:
        normalized = str(model or "").strip()
        if not normalized:
            return "speech-2.8-hd"
        return TTS_MODEL_ALIAS_MAP.get(normalized, normalized)

    @staticmethod
    def _normalize_language_boost(language_boost: Optional[str]) -> Optional[str]:
        if language_boost is None:
            return None
        raw = str(language_boost).strip()
        if not raw:
            return None
        return LANGUAGE_BOOST_MAP.get(raw.lower(), raw)

    @staticmethod
    def _normalize_speed(speed: Optional[float]) -> float:
        raw = 1.0 if speed is None else float(speed)
        return max(TTS_SPEED_MIN, min(TTS_SPEED_MAX, raw))

    @staticmethod
    def _normalize_volume(volume: Optional[float]) -> float:
        raw = 1.0 if volume is None else float(volume)
        return max(TTS_VOL_MIN, min(TTS_VOL_MAX, raw))

    @staticmethod
    def _normalize_pitch(pitch: Optional[float]) -> int:
        raw = 0 if pitch is None else int(round(float(pitch)))
        return max(TTS_PITCH_MIN, min(TTS_PITCH_MAX, raw))

    def _build_synthesize_payload(
        self,
        text: str,
        model: str,
        voice: str,
        speed: Optional[float],
        volume: Optional[float],
        pitch: Optional[float],
        format: str,
        sample_rate: int,
        bitrate: int,
        channels: int,
        language_boost: Optional[str],
        subtitles: bool,
        pronunciation: Optional[List[str]],
    ) -> Dict[str, Any]:
        normalized_model = self._normalize_model(model)
        normalized_language_boost = self._normalize_language_boost(language_boost)
        normalized_speed = self._normalize_speed(speed)
        normalized_volume = self._normalize_volume(volume)
        normalized_pitch = self._normalize_pitch(pitch)

        if normalized_model != (model or "").strip():
            logger.debug("Normalized TTS model from %s to %s", model, normalized_model)
        if speed is not None and normalized_speed != float(speed):
            logger.debug("Normalized TTS speed from %s to %s", speed, normalized_speed)
        if volume is not None and normalized_volume != float(volume):
            logger.debug("Normalized TTS volume from %s to %s", volume, normalized_volume)
        if pitch is not None and normalized_pitch != int(round(float(pitch))):
            logger.debug("Normalized TTS pitch from %s to %s", pitch, normalized_pitch)
        if (language_boost or "").strip() and normalized_language_boost != (language_boost or "").strip():
            logger.debug(
                "Normalized language_boost from %s to %s",
                language_boost,
                normalized_language_boost,
            )

        payload: Dict[str, Any] = {
            "model": normalized_model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice,
                "speed": normalized_speed,
                "vol": normalized_volume,
                "pitch": normalized_pitch,
            },
            "audio_setting": {
                "format": format,
                "sample_rate": sample_rate,
                "bitrate": bitrate,
                "channel": channels,
            },
            "subtitle_enable": bool(subtitles),
        }

        if normalized_language_boost:
            payload["language_boost"] = normalized_language_boost
        if pronunciation:
            payload["pronunciation_dict"] = {"tone": pronunciation}

        return payload

    @staticmethod
    def _voice_source_rank(source: Optional[str]) -> int:
        value = (source or "").lower()
        if "system" in value:
            return 0
        if "cloning" in value:
            return 1
        if "generation" in value:
            return 2
        if "music" in value:
            return 3
        return 9

    @staticmethod
    def _status_from_payload(payload: Dict[str, Any]) -> int:
        base_resp = payload.get("base_resp")
        if isinstance(base_resp, dict):
            try:
                return int(base_resp.get("status_code", 0))
            except (TypeError, ValueError):
                return -1

        data = payload.get("data")
        if isinstance(data, dict):
            nested = data.get("base_resp")
            if isinstance(nested, dict):
                try:
                    return int(nested.get("status_code", 0))
                except (TypeError, ValueError):
                    return -1

        return 0

    @staticmethod
    def _status_message_from_payload(payload: Dict[str, Any]) -> str:
        base_resp = payload.get("base_resp")
        if isinstance(base_resp, dict):
            return str(base_resp.get("status_msg", "") or "").strip()
        data = payload.get("data")
        if isinstance(data, dict):
            nested = data.get("base_resp")
            if isinstance(nested, dict):
                return str(nested.get("status_msg", "") or "").strip()
        return ""

    def _normalize_voice_item(self, item: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
        voice_id_raw = item.get("voice_id") or item.get("voiceId")
        voice_id = str(voice_id_raw or "").strip()

        # Only trust generic "id" when it still looks like a voice object.
        if not voice_id:
            fallback_id = item.get("id")
            has_voice_shape = any(
                key in item for key in ("voice_name", "name", "description", "created_time", "createdAt")
            )
            if fallback_id is not None and has_voice_shape:
                voice_id = str(fallback_id).strip()

        if not voice_id:
            return None

        voice_name_raw = item.get("voice_name") or item.get("name") or item.get("display_name")
        voice_name = str(voice_name_raw).strip() if voice_name_raw else None

        created_time_raw = item.get("created_time") or item.get("createdAt")
        created_time = str(created_time_raw).strip() if created_time_raw else None

        raw_description = item.get("description")
        if isinstance(raw_description, list):
            description = [str(x).strip() for x in raw_description if str(x).strip()]
        elif raw_description is None:
            description = []
        else:
            text = str(raw_description).strip()
            description = [text] if text else []

        return {
            "voice_id": voice_id,
            "voice_name": voice_name,
            "description": description,
            "created_time": created_time,
            "source": source or "voice",
        }

    def _collect_voice_items(
        self,
        node: Any,
        output: List[Dict[str, Any]],
        source_hint: str = "voice",
    ) -> None:
        if isinstance(node, dict):
            normalized = self._normalize_voice_item(node, source_hint)
            if normalized:
                output.append(normalized)

            for key, value in node.items():
                key_lower = key.lower()
                child_source = source_hint
                if "voice" in key_lower or "cloning" in key_lower or "generation" in key_lower:
                    child_source = key
                self._collect_voice_items(value, output, child_source)
            return

        if isinstance(node, list):
            for item in node:
                self._collect_voice_items(item, output, source_hint)

    def _extract_voice_items(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        extracted: List[Dict[str, Any]] = []
        self._collect_voice_items(payload, extracted, source_hint="voice")

        unique: Dict[str, Dict[str, Any]] = {}
        for item in extracted:
            voice_id = item["voice_id"]
            existing = unique.get(voice_id)
            if existing is None:
                unique[voice_id] = item
                continue

            if not existing.get("voice_name") and item.get("voice_name"):
                existing["voice_name"] = item["voice_name"]
            if not existing.get("created_time") and item.get("created_time"):
                existing["created_time"] = item["created_time"]
            if self._voice_source_rank(item.get("source")) < self._voice_source_rank(existing.get("source")):
                existing["source"] = item["source"]

            merged_desc = list(existing.get("description") or [])
            for entry in item.get("description") or []:
                if entry not in merged_desc:
                    merged_desc.append(entry)
            existing["description"] = merged_desc

        return sorted(
            unique.values(),
            key=lambda x: (
                self._voice_source_rank(x.get("source")),
                (x.get("voice_name") or "").lower(),
                x["voice_id"].lower(),
            ),
        )

    async def _fetch_voice_page(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.config.rest_base_url}/get_voice",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def _fetch_voice_catalog(self, base_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        page_size = 200
        max_pages = 6
        collected: Dict[str, Dict[str, Any]] = {}

        for page in range(1, max_pages + 1):
            payload = dict(base_payload)
            payload["page"] = page
            payload.setdefault("page_size", page_size)

            data = await self._fetch_voice_page(payload)
            status = self._status_from_payload(data)
            status_msg = self._status_message_from_payload(data)
            if status != 0:
                if page == 1:
                    raise ValueError(f"get_voice status={status}: {status_msg or 'unknown error'}")
                logger.warning("get_voice page=%s status=%s msg=%s", page, status, status_msg)
                break

            page_items = self._extract_voice_items(data)
            if not page_items:
                break

            added_count = 0
            for item in page_items:
                voice_id = item["voice_id"]
                existing = collected.get(voice_id)
                if existing is None:
                    collected[voice_id] = item
                    added_count += 1
                    continue
                if not existing.get("voice_name") and item.get("voice_name"):
                    existing["voice_name"] = item["voice_name"]
                if self._voice_source_rank(item.get("source")) < self._voice_source_rank(existing.get("source")):
                    existing["source"] = item["source"]

            if added_count == 0:
                break

            if len(page_items) < payload["page_size"]:
                break

        return sorted(
            collected.values(),
            key=lambda x: (
                self._voice_source_rank(x.get("source")),
                (x.get("voice_name") or "").lower(),
                x["voice_id"].lower(),
            ),
        )

    async def list_voices(self) -> List[Dict[str, Any]]:
        # MiniMax get_voice has changed across versions. Try current official payload first,
        # then fall back to older shapes for compatibility.
        payload_candidates = [
            {"voice_type": "all"},
            {"voice_type": "all", "model": "speech-2.8-hd"},
            {"model": "speech-2.8-hd"},
        ]
        last_error: Optional[Exception] = None

        for candidate in payload_candidates:
            try:
                voices = await self._fetch_voice_catalog(candidate)
                if voices:
                    logger.info("Fetched %s voices via get_voice payload=%s", len(voices), candidate)
                    return voices
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning("get_voice failed with payload=%s err=%s", candidate, exc)

        if last_error:
            raise RuntimeError(f"Failed to fetch voices from MiniMax: {last_error}") from last_error

        return []

    async def close(self):
        return None
