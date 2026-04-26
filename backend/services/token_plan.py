import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from services.minimax_config import auth_headers, load_minimax_config

logger = logging.getLogger(__name__)

NON_TEXT_DISPLAY_NAMES = (
    ("speech-2.8-hd", "speech-2.8-hd"),
    ("speech-2.6-hd", "speech-2.6-hd"),
    ("speech-02-hd", "speech-02-hd"),
    ("speech-hd", "TTS HD"),
    ("speech", "TTS HD"),
    ("tts", "TTS HD"),
    ("minimax-hailuo-2.3-fast", "Hailuo-2.3-Fast (768P 6s)"),
    ("minimax-hailuo-2.3", "Hailuo-2.3 (768P 6s)"),
    ("minimax-hailuo-02", "Hailuo-02 (首尾帧插帧)"),
    ("hailuo-2.3-fast", "Hailuo-2.3-Fast (768P 6s)"),
    ("hailuo-2.3", "Hailuo-2.3 (768P 6s)"),
    ("hailuo-02", "Hailuo-02 (首尾帧插帧)"),
    ("s2v-01", "S2V-01 (角色一致性)"),
    ("hailuo", "视频生成"),
    ("video", "视频生成"),
    ("music-2.6", "Music-2.6 (最长5分钟)"),
    ("music-2.5+", "Music-2.5+"),
    ("music-2.5", "Music-2.5"),
    ("music-cover", "Music Cover (翻唱)"),
    ("music", "音乐生成"),
    ("image-01", "图像生成"),
    ("image-01-live", "图像生成（实时）"),
    ("image", "图像生成"),
)

# Model name -> category slug used by frontend routing
MODEL_CATEGORY_MAP = (
    ("speech", "tts"),
    ("tts", "tts"),
    ("hailuo", "video"),
    ("s2v", "video"),
    ("video", "video"),
    ("music", "music"),
    ("image", "photo"),
)


class TokenPlanService:
    def __init__(self, api_key: Optional[str] = None):
        self.config = load_minimax_config(api_key=api_key)
        self.headers = auth_headers(self.config.api_key)

    async def fetch_remains(self) -> Dict[str, Any]:
        primary_url = f"{self.config.token_plan_base_url}/token_plan/remains"
        fallback_url = (
            f"{self.config.token_plan_fallback_base_url}/token_plan/remains"
            if self.config.token_plan_fallback_base_url
            else None
        )

        payload: Dict[str, Any]
        used_fallback = False
        try:
            payload = await self._request_json(primary_url)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if not fallback_url or status in (401, 403, 429):
                raise
            logger.warning(
                "Token Plan primary endpoint returned %s, trying fallback: %s",
                status,
                fallback_url,
            )
            payload = await self._request_json(fallback_url)
            used_fallback = True
        except httpx.RequestError:
            if not fallback_url:
                raise
            logger.warning("Token Plan primary endpoint unavailable, trying fallback: %s", fallback_url)
            payload = await self._request_json(fallback_url)
            used_fallback = True

        parsed = self._parse_remains_payload(payload)
        parsed["raw"] = payload
        if used_fallback:
            parsed["message"] = "Primary endpoint unavailable, fallback endpoint used"
        return parsed

    async def _request_json(self, url: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0, headers=self.headers) as client:
            response = await client.get(url)
            response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data
        raise ValueError("Token Plan remains response is not a JSON object")

    def _parse_remains_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data", payload)

        model_remains = data.get("model_remains")
        if isinstance(model_remains, list) and model_remains:
            return self._parse_model_remains(model_remains)

        text_usage = self._pick_number(data, ("text_window_usage", "text_usage", "text_used"))
        text_limit = self._pick_number(data, ("text_window_limit", "text_limit", "text_total", "text_quota"))

        non_text_usage = self._pick_number(
            data, ("non_text_daily_usage", "non_text_usage", "multimodal_daily_usage")
        )
        non_text_limit = self._pick_number(
            data, ("non_text_daily_limit", "non_text_limit", "multimodal_daily_limit")
        )

        if text_usage is None or text_limit is None:
            text_usage, text_limit = self._extract_usage_limit_from_nested(
                data,
                nested_keys=("text_window", "text", "text_quota"),
                current_usage=text_usage,
                current_limit=text_limit,
            )

        if non_text_usage is None or non_text_limit is None:
            non_text_usage, non_text_limit = self._extract_usage_limit_from_nested(
                data,
                nested_keys=("non_text_daily", "non_text", "multimodal_daily"),
                current_usage=non_text_usage,
                current_limit=non_text_limit,
            )
        non_text_items = self._extract_non_text_items_from_nested(data)

        return {
            "success": True,
            "text_window_usage": text_usage,
            "text_window_limit": text_limit,
            "non_text_daily_usage": non_text_usage,
            "non_text_daily_limit": non_text_limit,
            "non_text_daily_items": non_text_items,
        }

    def _parse_model_remains(self, model_remains: list) -> Dict[str, Any]:
        text_usage = None
        text_limit = None
        non_text_usage_total = 0.0
        non_text_limit_total = 0.0
        has_non_text = False
        non_text_items = []

        for item in model_remains:
            if not isinstance(item, dict):
                continue

            model_name = str(item.get("model_name", "")).strip()
            usage = self._pick_number(item, ("current_interval_usage_count", "usage", "used"))
            limit = self._pick_number(item, ("current_interval_total_count", "limit", "quota", "total"))
            if usage is None or limit is None:
                continue

            name_lower = model_name.lower()
            is_text_bucket = name_lower.startswith("minimax-m") or name_lower.startswith("coding-plan")
            if is_text_bucket:
                # Prefer the shared M-model bucket if present.
                if model_name.startswith("MiniMax-M"):
                    text_usage = usage
                    text_limit = limit
                elif text_usage is None or text_limit is None:
                    text_usage = (text_usage or 0.0) + usage
                    text_limit = (text_limit or 0.0) + limit
            else:
                non_text_usage_total += usage
                non_text_limit_total += limit
                has_non_text = True
                non_text_items.append(self._make_non_text_item(model_name, usage, limit))

        return {
            "success": True,
            "text_window_usage": text_usage,
            "text_window_limit": text_limit,
            "non_text_daily_usage": non_text_usage_total if has_non_text else None,
            "non_text_daily_limit": non_text_limit_total if has_non_text else None,
            "non_text_daily_items": non_text_items,
        }

    def _extract_usage_limit_from_nested(
        self,
        data: Dict[str, Any],
        nested_keys: Tuple[str, ...],
        current_usage: Optional[float],
        current_limit: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        usage = current_usage
        limit = current_limit
        for key in nested_keys:
            nested = data.get(key)
            if not isinstance(nested, dict):
                continue

            nested_usage = self._pick_number(nested, ("usage", "used", "request_count", "count"))
            nested_limit = self._pick_number(nested, ("limit", "quota", "total", "max"))

            if nested_usage is None and nested_limit is None:
                # Some payloads split each modality in nested objects; aggregate if possible.
                nested_usage = self._sum_nested_numbers(nested, ("usage", "used", "request_count", "count"))
                nested_limit = self._sum_nested_numbers(nested, ("limit", "quota", "total", "max"))

            usage = usage if usage is not None else nested_usage
            limit = limit if limit is not None else nested_limit

            if usage is not None and limit is not None:
                break
        return usage, limit

    @staticmethod
    def _sum_nested_numbers(data: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[float]:
        total = 0.0
        found = False
        for value in data.values():
            if not isinstance(value, dict):
                continue
            number = TokenPlanService._pick_number(value, keys)
            if number is not None:
                total += number
                found = True
        return total if found else None

    def _extract_non_text_items_from_nested(self, data: Dict[str, Any]) -> list:
        for key in ("non_text_daily", "non_text", "multimodal_daily"):
            nested = data.get(key)
            if not isinstance(nested, dict):
                continue
            items = []
            for name, value in nested.items():
                if not isinstance(value, dict):
                    continue
                usage = self._pick_number(value, ("usage", "used", "request_count", "count"))
                limit = self._pick_number(value, ("limit", "quota", "total", "max"))
                if usage is None and limit is None:
                    continue
                items.append(self._make_non_text_item(str(name), usage, limit))
            if items:
                return items
        return []

    @staticmethod
    def _make_non_text_item(model_name: str, usage: Optional[float], limit: Optional[float]) -> Dict[str, Any]:
        remaining = None
        if usage is not None and limit is not None:
            remaining = max(limit - usage, 0.0)
        return {
            "model_name": model_name,
            "display_name": TokenPlanService._display_name_for_model(model_name),
            "category": TokenPlanService._category_for_model(model_name),
            "usage": usage,
            "limit": limit,
            "remaining": remaining,
            "scope": "daily",
        }

    @staticmethod
    def _display_name_for_model(model_name: str) -> str:
        lowered = str(model_name or "").lower()
        for token, display_name in NON_TEXT_DISPLAY_NAMES:
            if token in lowered:
                return display_name
        return model_name or "非文本模型"

    @staticmethod
    def _category_for_model(model_name: str) -> str:
        lowered = str(model_name or "").lower()
        for token, category in MODEL_CATEGORY_MAP:
            if token in lowered:
                return category
        return "other"

    @staticmethod
    def _pick_number(data: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[float]:
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value.strip())
                except ValueError:
                    continue
        return None

    async def close(self) -> None:
        return None
