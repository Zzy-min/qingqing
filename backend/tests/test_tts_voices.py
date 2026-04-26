import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MINIMAX_API_KEY", "test-tts-key")

from api import routes_tts
from services.tts import TTSService


def _make_voice(voice_id: str, name: str, source: str = "system_voice"):
    return {
        "voice_id": voice_id,
        "voice_name": name,
        "source": source,
        "description": [],
        "created_time": "1970-01-01",
    }


def test_extract_voice_items_supports_top_level_get_voice_shape():
    service = TTSService(api_key="test-tts-key")
    payload = {
        "system_voice": [
            {"voice_id": "male-qn-qingse", "voice_name": "青涩青年音色", "description": []},
            {"voice_id": "female-yujie", "voice_name": "御姐音色", "description": []},
        ],
        "voice_generation": [
            {"voice_id": "custom-voice-1", "voice_name": "我的定制音色", "description": []},
        ],
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }

    voices = service._extract_voice_items(payload)
    voice_ids = [item["voice_id"] for item in voices]

    assert "male-qn-qingse" in voice_ids
    assert "female-yujie" in voice_ids
    assert "custom-voice-1" in voice_ids


def test_list_voices_tries_compatible_payload_candidates(monkeypatch):
    service = TTSService(api_key="test-tts-key")
    attempts = []

    async def fake_fetch_voice_catalog(payload):
        attempts.append(payload)
        if payload == {"voice_type": "all"}:
            raise ValueError("first payload rejected")
        return [_make_voice("female-tianmei", "甜美女性音色")]

    monkeypatch.setattr(service, "_fetch_voice_catalog", fake_fetch_voice_catalog)

    voices = asyncio.run(service.list_voices())
    assert voices[0]["voice_id"] == "female-tianmei"
    assert attempts[0] == {"voice_type": "all"}
    assert attempts[1] == {"voice_type": "all", "model": "speech-2.8-hd"}


def _patch_tts_service(monkeypatch, list_impl):
    class StubTTSService:
        async def list_voices(self):
            return await list_impl()

    async def _get_stub_service():
        return StubTTSService()

    monkeypatch.setattr(routes_tts, "get_tts_service", _get_stub_service)


def test_list_voices_route_returns_items(monkeypatch):
    async def _list():
        return [
            {
                "voice_id": "male-qn-qingse",
                "voice_name": "青涩青年音色",
                "source": "system_voice",
                "description": [],
                "created_time": "1970-01-01",
            }
        ]

    _patch_tts_service(monkeypatch, _list)
    payload = asyncio.run(routes_tts.list_voices())

    assert payload.source == "official"
    assert payload.voices == ["male-qn-qingse"]
    assert len(payload.items) == 1
    assert payload.items[0].voice_name == "青涩青年音色"


def test_list_voices_route_falls_back_to_static_voices(monkeypatch):
    async def _list():
        raise RuntimeError("MiniMax unavailable")

    _patch_tts_service(monkeypatch, _list)
    payload = asyncio.run(routes_tts.list_voices())

    assert payload.source == "fallback"
    assert "male-qn-qingse" in payload.voices
    assert "female-yujie" in payload.voices
    assert len(payload.items) >= 8
