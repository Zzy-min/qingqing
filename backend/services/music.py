"""
MiniMax Music Service — music generation + task polling
"""
import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from services.minimax_config import auth_headers, load_minimax_config

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 180.0
MAX_RETRIES = 2

POLL_INTERVAL = 5
POLL_TIMEOUT = 300


class MusicService:

    def __init__(self, api_key: Optional[str] = None):
        self.config = load_minimax_config(api_key=api_key)
        self.api_key = self.config.api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.rest_base_url,
                headers=auth_headers(self.api_key),
                timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=10.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def _request_with_retry(self, method: str, url: str, **kwargs):
        last_error = None
        for attempt in range(MAX_RETRIES):
            client = await self._get_client()
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if 400 <= e.response.status_code < 500:
                    raise
                last_error = e
                logger.warning("Music API %s error (attempt %d/%d): %s", method, attempt + 1, MAX_RETRIES, e.response.status_code)
            except httpx.RequestError as e:
                last_error = e
                logger.warning("Music network error (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, e)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
        raise last_error or RuntimeError("Max retries exceeded")

    def _build_prompt(self, prompt: str, **kwargs) -> str:
        parts = [prompt] if prompt else []
        for key in ("vocals", "genre", "mood", "instruments", "tempo", "bpm", "key", "avoid", "use_case", "structure", "references", "extra"):
            val = kwargs.get(key)
            if val:
                label = key.replace("_", " ").capitalize()
                parts.append(f"{label}: {val}")
        return ". ".join(parts)

    async def generate_music(
        self,
        prompt: str,
        lyrics: Optional[str] = None,
        instrumental: bool = False,
        lyrics_optimizer: bool = False,
        model: str = "music-2.6",
        **kwargs,
    ) -> Dict[str, Any]:
        full_prompt = self._build_prompt(prompt, **kwargs)

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": full_prompt,
            "lyrics": lyrics,
            "is_instrumental": instrumental,
            "lyrics_optimizer": lyrics_optimizer,
            "audio_setting": {
                "format": kwargs.get("format", "mp3"),
                "sample_rate": kwargs.get("sample_rate", 44100),
                "bitrate": kwargs.get("bitrate", 256000),
            },
            "output_format": "url",
        }
        if kwargs.get("aigc_watermark"):
            payload["aigc_watermark"] = True

        payload = {k: v for k, v in payload.items() if v is not None or k in ("model", "prompt", "is_instrumental")}

        logger.info("Music generate: model=%s, prompt=%s", model, full_prompt[:80])

        resp = await self._request_with_retry("POST", "/music_generation", json=payload)
        data = resp.json()
        logger.info("Music response: %s", str(data)[:500])

        base_resp = data.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code != 0:
            raise ValueError(f"Music API error (code={status_code}): {base_resp.get('status_msg', 'Unknown')}")

        return {
            "task_id": data.get("data", {}).get("task_id"),
            "audio_url": data.get("data", {}).get("audio") or data.get("data", {}).get("audio_url"),
            "status": data.get("data", {}).get("status"),
            "_raw": data,
        }

    async def get_music_task(self, task_id: str) -> Dict[str, Any]:
        client = await self._get_client()
        resp = await client.get(f"/music_generation/{task_id}")
        resp.raise_for_status()
        data = resp.json()
        logger.info("Music task %s response: %s", task_id, str(data)[:500])

        base_resp = data.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code != 0:
            raise ValueError(f"Music task query error (code={status_code}): {base_resp.get('status_msg', 'Unknown')}")

        task_data = data.get("data", {})
        return {
            "task_id": task_id,
            "audio_url": task_data.get("audio") or task_data.get("audio_url"),
            "status": task_data.get("status"),
            "status_msg": task_data.get("status_msg"),
            "_raw": data,
        }

    async def wait_for_music(self, task_id: str, poll_interval: int = POLL_INTERVAL, timeout: int = POLL_TIMEOUT) -> Dict[str, Any]:
        elapsed = 0
        while elapsed < timeout:
            task = await self.get_music_task(task_id)
            status = task.get("status")
            logger.info("Music task %s status: %s", task_id, status)
            if status == 2:
                if task.get("audio_url"):
                    return task
            elif status == 3:
                raise RuntimeError(f"Music generation failed: {task.get('status_msg', 'Unknown error')}")
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"Music generation timed out after {timeout}s")

    async def generate_cover(
        self,
        prompt: str,
        audio_url: Optional[str] = None,
        audio_data: Optional[str] = None,
        lyrics: Optional[str] = None,
        model: str = "music-cover",
        seed: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "audio_setting": {
                "format": kwargs.get("format", "mp3"),
                "sample_rate": kwargs.get("sample_rate", 44100),
                "bitrate": kwargs.get("bitrate", 256000),
                "channel": kwargs.get("channels", 2),
            },
            "output_format": "url",
        }
        if audio_url:
            payload["audio_url"] = audio_url
        elif audio_data:
            if "," in audio_data:
                audio_data = audio_data.split(",", 1)[1]
            payload["audio_base64"] = audio_data
        if lyrics:
            payload["lyrics"] = lyrics
        if seed is not None:
            payload["seed"] = seed

        logger.info("Music cover: model=%s, prompt=%s", model, prompt[:80])

        resp = await self._request_with_retry("POST", "/music_generation", json=payload)
        data = resp.json()
        logger.info("Music cover response: %s", str(data)[:500])

        base_resp = data.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code != 0:
            raise ValueError(f"Music cover API error (code={status_code}): {base_resp.get('status_msg', 'Unknown')}")

        return {
            "task_id": data.get("data", {}).get("task_id"),
            "audio_url": data.get("data", {}).get("audio") or data.get("data", {}).get("audio_url"),
            "status": data.get("data", {}).get("status"),
            "_raw": data,
        }

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
