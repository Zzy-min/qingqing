import asyncio
import os
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MINIMAX_API_KEY", "test-token-plan-key")

from api import routes
from services.token_plan import TokenPlanService


def _patch_token_service(monkeypatch, fetch_impl):
    class StubTokenPlanService:
        async def fetch_remains(self):
            return await fetch_impl()

    async def _get_stub_service():
        return StubTokenPlanService()

    monkeypatch.setattr(routes, "get_token_plan_service", _get_stub_service)


def _make_status_error(status_code: int, body: str):
    request = httpx.Request("GET", "https://www.minimaxi.com/v1/token_plan/remains")
    response = httpx.Response(status_code=status_code, request=request, text=body)
    return httpx.HTTPStatusError("status error", request=request, response=response)


def test_token_plan_remains_success(monkeypatch):
    async def _fetch():
        return {
            "success": True,
            "text_window_usage": 13,
            "text_window_limit": 80,
            "non_text_daily_usage": 2,
            "non_text_daily_limit": 15,
            "raw": {"ok": True},
        }

    _patch_token_service(monkeypatch, _fetch)
    payload = asyncio.run(routes.token_plan_remains())
    assert payload["success"] is True
    assert payload["text_window_usage"] == 13
    assert payload["non_text_daily_limit"] == 15


@pytest.mark.parametrize(
    "status_code,body",
    [
        (401, "unauthorized"),
        (429, "too many requests"),
        (503, "service unavailable"),
    ],
)
def test_token_plan_remains_propagates_http_errors(monkeypatch, status_code, body):
    async def _fetch():
        raise _make_status_error(status_code, body)

    _patch_token_service(monkeypatch, _fetch)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(routes.token_plan_remains())

    assert exc_info.value.status_code == status_code
    assert body in exc_info.value.detail


def test_token_plan_remains_request_error_returns_502(monkeypatch):
    async def _fetch():
        request = httpx.Request("GET", "https://www.minimaxi.com/v1/token_plan/remains")
        raise httpx.RequestError("network down", request=request)

    _patch_token_service(monkeypatch, _fetch)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(routes.token_plan_remains())

    assert exc_info.value.status_code == 502
    assert "Network error" in exc_info.value.detail


def test_token_plan_service_parse_nested_usage_limit():
    service = TokenPlanService(api_key="test-token-plan-key")
    parsed = service._parse_remains_payload(
        {
            "data": {
                "text_window": {"usage": 5, "limit": 30},
                "non_text_daily": {
                    "image": {"usage": 1, "limit": 5},
                    "video": {"usage": 2, "limit": 4},
                },
            }
        }
    )
    assert parsed["success"] is True
    assert parsed["text_window_usage"] == 5
    assert parsed["text_window_limit"] == 30
    assert parsed["non_text_daily_usage"] == 3
    assert parsed["non_text_daily_limit"] == 9
    assert parsed["non_text_daily_items"] == [
        {
            "model_name": "image",
            "display_name": "图像生成",
            "category": "photo",
            "usage": 1.0,
            "limit": 5.0,
            "remaining": 4.0,
            "scope": "daily",
        },
        {
            "model_name": "video",
            "display_name": "视频生成",
            "category": "video",
            "usage": 2.0,
            "limit": 4.0,
            "remaining": 2.0,
            "scope": "daily",
        },
    ]


def test_token_plan_service_parse_model_remains_shape():
    service = TokenPlanService(api_key="test-token-plan-key")
    parsed = service._parse_remains_payload(
        {
            "data": {
                "model_remains": [
                    {
                        "model_name": "MiniMax-M*",
                        "current_interval_total_count": 4500,
                        "current_interval_usage_count": 670,
                    },
                    {
                        "model_name": "speech-hd",
                        "current_interval_total_count": 11000,
                        "current_interval_usage_count": 714,
                    },
                    {
                        "model_name": "image-01",
                        "current_interval_total_count": 120,
                        "current_interval_usage_count": 30,
                    },
                ]
            }
        }
    )
    assert parsed["text_window_usage"] == 670
    assert parsed["text_window_limit"] == 4500
    assert parsed["non_text_daily_usage"] == 744
    assert parsed["non_text_daily_limit"] == 11120
    assert parsed["non_text_daily_items"][0]["display_name"] == "TTS HD"
    assert parsed["non_text_daily_items"][1]["display_name"] == "图像生成"
    assert parsed["non_text_daily_items"][0]["category"] == "tts"
    assert parsed["non_text_daily_items"][1]["category"] == "photo"


def test_token_plan_service_model_alias_category_mapping():
    service = TokenPlanService(api_key="test-token-plan-key")
    parsed = service._parse_remains_payload(
        {
            "data": {
                "model_remains": [
                    {
                        "model_name": "MiniMax-M*",
                        "current_interval_total_count": 4500,
                        "current_interval_usage_count": 1,
                    },
                    {
                        "model_name": "speech-2.8-hd",
                        "current_interval_total_count": 100,
                        "current_interval_usage_count": 10,
                    },
                    {
                        "model_name": "MiniMax-Hailuo-2.3-Fast-6s-768p",
                        "current_interval_total_count": 30,
                        "current_interval_usage_count": 3,
                    },
                    {
                        "model_name": "music-2.6",
                        "current_interval_total_count": 50,
                        "current_interval_usage_count": 5,
                    },
                    {
                        "model_name": "image-01-live",
                        "current_interval_total_count": 80,
                        "current_interval_usage_count": 8,
                    },
                    {
                        "model_name": "lyrics_generation",
                        "current_interval_total_count": 20,
                        "current_interval_usage_count": 2,
                    },
                ]
            }
        }
    )

    by_name = {item["model_name"]: item for item in parsed["non_text_daily_items"]}
    assert by_name["speech-2.8-hd"]["category"] == "tts"
    assert by_name["MiniMax-Hailuo-2.3-Fast-6s-768p"]["category"] == "video"
    assert by_name["music-2.6"]["category"] == "music"
    assert by_name["image-01-live"]["category"] == "photo"
    assert by_name["lyrics_generation"]["category"] == "other"
    assert parsed["non_text_daily_usage"] == 28
    assert parsed["non_text_daily_limit"] == 280


def test_token_plan_service_nested_shape_unknown_model_keeps_other_bucket():
    service = TokenPlanService(api_key="test-token-plan-key")
    parsed = service._parse_remains_payload(
        {
            "data": {
                "text_window": {"usage": 9, "limit": 30},
                "non_text_daily": {
                    "speech-hd": {"usage": 2, "limit": 11},
                    "MiniMax-Hailuo-2.3-6s-768p": {"usage": 1, "limit": 2},
                    "music-2.6": {"usage": 3, "limit": 10},
                    "image-01": {"usage": 4, "limit": 20},
                    "mystery-model-x": {"usage": 5, "limit": 50},
                },
            }
        }
    )

    by_name = {item["model_name"]: item for item in parsed["non_text_daily_items"]}
    assert by_name["speech-hd"]["category"] == "tts"
    assert by_name["MiniMax-Hailuo-2.3-6s-768p"]["category"] == "video"
    assert by_name["music-2.6"]["category"] == "music"
    assert by_name["image-01"]["category"] == "photo"
    assert by_name["mystery-model-x"]["category"] == "other"
    assert parsed["non_text_daily_usage"] == 15
    assert parsed["non_text_daily_limit"] == 93
