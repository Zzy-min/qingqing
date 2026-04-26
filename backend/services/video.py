import asyncio
import base64
import io
import logging
from typing import Any, Dict, Optional

import httpx
from PIL import Image

from services.minimax_config import auth_headers, load_minimax_config

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300.0
MAX_RETRIES = 2
POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 600
MIN_FRAME_ASPECT_RATIO = 2 / 5
MAX_FRAME_ASPECT_RATIO = 5 / 2
MIN_FRAME_SHORT_SIDE = 320


class VideoService:

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
                logger.warning("Video API %s error (attempt %d/%d): %s", method, attempt + 1, MAX_RETRIES, e.response.status_code)
            except httpx.RequestError as e:
                last_error = e
                logger.warning("Video network error (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, e)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
        raise last_error or RuntimeError("Max retries exceeded")

    async def _poll_task(self, task_id: str) -> Dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + POLL_TIMEOUT_SEC
        while True:
            resp = await self._request_with_retry("GET", f"/query/video_generation?task_id={task_id}")
            data = resp.json()
            self._raise_on_api_error(data, "Video task query error")
            status = data.get("status", "")
            logger.info("Video task %s status: %s", task_id, status)
            if status == "Success":
                return data
            if status == "Failed":
                raise RuntimeError(f"Video task failed: {data.get('message') or data.get('status_msg') or 'Unknown'}")
            if asyncio.get_running_loop().time() > deadline:
                raise RuntimeError(f"Video polling timed out after {POLL_TIMEOUT_SEC}s")
            await asyncio.sleep(POLL_INTERVAL_SEC)

    async def generate_video(
        self,
        prompt: str,
        model: str = "MiniMax-Hailuo-2.3",
        first_frame: Optional[str] = None,
        last_frame: Optional[str] = None,
        subject_image: Optional[str] = None,
        duration: Optional[int] = None,
        resolution: Optional[str] = None,
        prompt_optimizer: Optional[bool] = None,
        fast_pretreatment: Optional[bool] = None,
        aigc_watermark: Optional[bool] = None,
        callback_url: Optional[str] = None,
        no_wait: bool = False,
    ) -> Dict[str, Any]:
        selected_model = model
        adjustments = []

        # Official constraint: First-and-Last-Frame mode only supports MiniMax-Hailuo-02.
        if last_frame and selected_model != "MiniMax-Hailuo-02":
            model_adjustment = (
                f"Model {selected_model} does not support first+last frame mode; "
                "auto-switched to MiniMax-Hailuo-02."
            )
            logger.warning(model_adjustment)
            adjustments.append(model_adjustment)
            selected_model = "MiniMax-Hailuo-02"

        # In first+last frame mode, subject_reference is incompatible with MiniMax-Hailuo-02.
        if last_frame and subject_image:
            disable_note = (
                "subject_reference is incompatible with first+last frame mode "
                "for MiniMax-Hailuo-02; subject reference has been disabled."
            )
            logger.warning(disable_note)
            adjustments.append(disable_note)
            subject_image = None

        duration, resolution = self._normalize_generation_options(
            selected_model=selected_model,
            duration=duration,
            resolution=resolution,
            has_last_frame=bool(last_frame),
            adjustments=adjustments,
        )

        payload: Dict[str, Any] = {"model": selected_model, "prompt": prompt}
        if duration is not None:
            payload["duration"] = duration
        if resolution:
            payload["resolution"] = resolution
        if prompt_optimizer is not None:
            payload["prompt_optimizer"] = bool(prompt_optimizer)
        if fast_pretreatment is not None and selected_model != "S2V-01":
            payload["fast_pretreatment"] = bool(fast_pretreatment)
        if aigc_watermark is not None:
            payload["aigc_watermark"] = bool(aigc_watermark)

        if first_frame:
            payload["first_frame_image"] = self._normalize_frame_image(first_frame, "first_frame_image")

        if last_frame:
            if not first_frame:
                raise ValueError("--last-frame requires --first-frame")
            payload["last_frame_image"] = self._normalize_frame_image(last_frame, "last_frame_image")

        if subject_image:
            if subject_image.startswith("http"):
                img_data = subject_image
            elif subject_image.startswith("data:"):
                img_data = subject_image
            else:
                img_data = f"data:image/jpeg;base64,{subject_image}"
            payload["subject_reference"] = [{"type": "character", "image": [img_data]}]

        if callback_url:
            payload["callback_url"] = callback_url

        logger.info("Video generate: requested_model=%s, selected_model=%s, prompt=%s", model, selected_model, prompt[:80])

        data = await self._submit_video_generation(payload)
        status_code, status_msg = self._extract_status(data)

        # Token plan fallback: if Hailuo-02 unsupported in FLF mode, degrade to first-frame mode.
        if status_code == 2061 and "last_frame_image" in payload:
            fallback_model = "MiniMax-Hailuo-2.3-Fast"
            fallback_note = (
                "Current token plan does not support MiniMax-Hailuo-02 for first+last frame mode; "
                "auto-fallback to first-frame mode with MiniMax-Hailuo-2.3-Fast."
            )
            logger.warning("%s status_msg=%s", fallback_note, status_msg)
            adjustments.append(fallback_note)

            payload["model"] = fallback_model
            payload.pop("last_frame_image", None)
            payload.pop("subject_reference", None)
            fallback_duration, fallback_resolution = self._normalize_generation_options(
                selected_model=fallback_model,
                duration=payload.get("duration"),
                resolution=payload.get("resolution"),
                has_last_frame=False,
                adjustments=adjustments,
            )
            if fallback_duration is not None:
                payload["duration"] = fallback_duration
            else:
                payload.pop("duration", None)
            if fallback_resolution:
                payload["resolution"] = fallback_resolution
            else:
                payload.pop("resolution", None)
            selected_model = fallback_model

            data = await self._submit_video_generation(payload)
            status_code, status_msg = self._extract_status(data)

        if status_code != 0:
            raise ValueError(f"Video API error (code={status_code}): {status_msg}")

        task_id_raw = data.get("task_id")
        task_id = str(task_id_raw).strip() if task_id_raw is not None else ""
        if not task_id:
            raise ValueError("Video API error: missing task_id in successful response")
        if no_wait:
            return {
                "task_id": task_id,
                "status": "Pending",
                "model_used": selected_model,
                "model_adjustment": " | ".join(adjustments) if adjustments else None,
            }

        result = await self._poll_task(task_id)
        return {
            "task_id": task_id,
            "status": result.get("status"),
            "file_id": result.get("file_id"),
            "model_used": selected_model,
            "model_adjustment": " | ".join(adjustments) if adjustments else None,
            "_raw": result,
        }

    async def _submit_video_generation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self._request_with_retry("POST", "/video_generation", json=payload)
        data = resp.json()
        logger.info("Video response: %s", str(data)[:500])
        return data

    @staticmethod
    def _normalize_generation_options(
        selected_model: str,
        duration: Optional[int],
        resolution: Optional[str],
        has_last_frame: bool,
        adjustments: list,
    ) -> tuple[Optional[int], Optional[str]]:
        if selected_model == "S2V-01":
            if duration is not None or resolution:
                adjustments.append("S2V-01 does not accept duration/resolution; these options were omitted.")
            return None, None

        normalized_duration = None
        if duration is not None:
            try:
                normalized_duration = int(duration)
            except (TypeError, ValueError):
                normalized_duration = 6
                adjustments.append("Invalid duration was normalized to 6 seconds.")
            if normalized_duration not in (6, 10):
                normalized_duration = 6
                adjustments.append("Video duration only supports 6 or 10 seconds; normalized to 6 seconds.")

        normalized_resolution = str(resolution or "").strip().upper() or None
        allowed_resolutions = {"512P", "720P", "768P", "1080P"}
        if normalized_resolution and normalized_resolution not in allowed_resolutions:
            normalized_resolution = "768P"
            adjustments.append("Unsupported video resolution was normalized to 768P.")

        if has_last_frame and normalized_resolution == "512P":
            normalized_resolution = "768P"
            adjustments.append("First-and-last-frame mode does not support 512P; normalized to 768P.")

        if normalized_duration == 10:
            if normalized_resolution == "1080P":
                normalized_duration = 6
                adjustments.append("1080P only supports 6 seconds; duration was normalized to 6 seconds.")
            elif not normalized_resolution:
                normalized_resolution = "768P"

        if normalized_resolution == "1080P" and normalized_duration is None:
            normalized_duration = 6

        return normalized_duration, normalized_resolution

    @staticmethod
    def _extract_status(data: Dict[str, Any]) -> tuple[int, str]:
        base_resp = data.get("base_resp", {}) if isinstance(data, dict) else {}
        try:
            status_code = int(base_resp.get("status_code", 0) or 0)
        except (TypeError, ValueError):
            status_code = -1
        status_msg = base_resp.get("status_msg", "Unknown")
        return status_code, status_msg

    def _raise_on_api_error(self, data: Dict[str, Any], prefix: str) -> None:
        status_code, status_msg = self._extract_status(data)
        if status_code != 0:
            raise ValueError(f"{prefix} (code={status_code}): {status_msg}")

    async def query_task(self, task_id: str) -> Dict[str, Any]:
        resp = await self._request_with_retry("GET", f"/query/video_generation?task_id={task_id}")
        data = resp.json()
        self._raise_on_api_error(data, "Video task query error")
        return data

    async def get_download_url(self, file_id: str) -> Optional[str]:
        resp = await self._request_with_retry("GET", f"/files/retrieve?file_id={file_id}")
        data = resp.json()
        self._raise_on_api_error(data, "Video file retrieve error")
        return data.get("file", {}).get("download_url")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _normalize_frame_image(self, image_input: str, field_name: str) -> str:
        value = str(image_input or "").strip()
        if not value:
            raise ValueError(f"{field_name} is empty")
        if value.startswith("http://") or value.startswith("https://"):
            return value

        payload = value.split(",", 1)[1] if value.startswith("data:") else value
        try:
            image_bytes = base64.b64decode(payload, validate=True)
        except Exception as exc:
            raise ValueError(f"{field_name} is not a valid Base64 image") from exc

        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                image = img.convert("RGB")
        except Exception as exc:
            raise ValueError(f"{field_name} cannot be decoded as image") from exc

        original_width, original_height = image.size
        adjusted = image
        adjusted_flag = False

        aspect_ratio = original_width / max(original_height, 1)
        if aspect_ratio < MIN_FRAME_ASPECT_RATIO:
            target_height = int(round(original_width / MIN_FRAME_ASPECT_RATIO))
            target_height = min(target_height, original_height)
            offset = max((original_height - target_height) // 2, 0)
            adjusted = adjusted.crop((0, offset, original_width, offset + target_height))
            adjusted_flag = True
        elif aspect_ratio > MAX_FRAME_ASPECT_RATIO:
            target_width = int(round(original_height * MAX_FRAME_ASPECT_RATIO))
            target_width = min(target_width, original_width)
            offset = max((original_width - target_width) // 2, 0)
            adjusted = adjusted.crop((offset, 0, offset + target_width, original_height))
            adjusted_flag = True

        current_width, current_height = adjusted.size
        short_side = min(current_width, current_height)
        if short_side < MIN_FRAME_SHORT_SIDE:
            scale = MIN_FRAME_SHORT_SIDE / max(short_side, 1)
            resized_width = int(round(current_width * scale))
            resized_height = int(round(current_height * scale))
            adjusted = adjusted.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
            adjusted_flag = True

        if adjusted_flag:
            logger.info(
                "Normalized %s image from %sx%s to %sx%s",
                field_name,
                original_width,
                original_height,
                adjusted.size[0],
                adjusted.size[1],
            )

        buffer = io.BytesIO()
        adjusted.save(buffer, format="JPEG", quality=92)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
