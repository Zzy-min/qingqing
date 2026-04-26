import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_MINIMAX_REST_BASE = "https://api.minimaxi.com/v1"
DEFAULT_MINIMAX_ANTHROPIC_BASE = "https://api.minimaxi.com/anthropic"
DEFAULT_TOKEN_PLAN_BASE = "https://www.minimaxi.com/v1"
DEFAULT_TOKEN_PLAN_FALLBACK_BASE = "https://api.minimaxi.com/v1"


@dataclass(frozen=True)
class MiniMaxConfig:
    api_key: str
    rest_base_url: str
    anthropic_base_url: str
    token_plan_base_url: str
    token_plan_fallback_base_url: Optional[str]


def _normalize_base(base_url: str) -> str:
    return (base_url or "").strip().rstrip("/")


def load_minimax_config(
    api_key: Optional[str] = None,
    require_api_key: bool = True,
) -> MiniMaxConfig:
    key = (api_key or os.getenv("MINIMAX_API_KEY", "")).strip()
    if require_api_key and not key:
        raise RuntimeError(
            "MINIMAX_API_KEY is required. "
            "Token Plan Key and pay-as-you-go Key are not interchangeable."
        )

    rest_base_url = _normalize_base(
        os.getenv("MINIMAX_REST_BASE_URL", DEFAULT_MINIMAX_REST_BASE)
    )
    anthropic_base_url = _normalize_base(
        os.getenv("MINIMAX_ANTHROPIC_BASE_URL", DEFAULT_MINIMAX_ANTHROPIC_BASE)
    )
    token_plan_base_url = _normalize_base(
        os.getenv("MINIMAX_TOKEN_PLAN_BASE_URL", DEFAULT_TOKEN_PLAN_BASE)
    )
    token_plan_fallback = _normalize_base(
        os.getenv("MINIMAX_TOKEN_PLAN_FALLBACK_BASE_URL", DEFAULT_TOKEN_PLAN_FALLBACK_BASE)
    )

    if token_plan_fallback == token_plan_base_url:
        token_plan_fallback = None

    return MiniMaxConfig(
        api_key=key,
        rest_base_url=rest_base_url,
        anthropic_base_url=anthropic_base_url,
        token_plan_base_url=token_plan_base_url,
        token_plan_fallback_base_url=token_plan_fallback or None,
    )


def auth_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def get_tts_audio_dir() -> str:
    configured_dir = os.getenv("TTS_AUDIO_DIR", "").strip()
    if configured_dir:
        target = Path(configured_dir)
    else:
        target = Path(tempfile.gettempdir()) / "minimax-photo-agent" / "tts_outputs"

    target.mkdir(parents=True, exist_ok=True)
    return str(target)


def log_minimax_bases(logger: logging.Logger, config: MiniMaxConfig) -> None:
    logger.info("MiniMax REST base: %s", config.rest_base_url)
    logger.info("MiniMax Anthropic-compatible base: %s", config.anthropic_base_url)
    logger.info("MiniMax Token Plan base: %s", config.token_plan_base_url)
    if config.token_plan_fallback_base_url:
        logger.info("MiniMax Token Plan fallback base: %s", config.token_plan_fallback_base_url)

