import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MINIMAX_API_KEY", "test-tts-key")

from services.tts import TTSService


def _build_payload(**overrides):
    service = TTSService(api_key="test-tts-key")
    kwargs = {
        "text": "hello world",
        "model": "speech-2.8-hd",
        "voice": "male-qn-qingse",
        "speed": 1.0,
        "volume": 1.0,
        "pitch": 0,
        "format": "mp3",
        "sample_rate": 32000,
        "bitrate": 128000,
        "channels": 1,
        "language_boost": None,
        "subtitles": False,
        "pronunciation": None,
    }
    kwargs.update(overrides)
    return service._build_synthesize_payload(**kwargs)


def test_build_payload_maps_legacy_model_aliases():
    payload_26 = _build_payload(model="speech-2.6")
    payload_02 = _build_payload(model="speech-02")
    payload_hd = _build_payload(model="speech-2.8-hd")

    assert payload_26["model"] == "speech-2.6-hd"
    assert payload_02["model"] == "speech-02-hd"
    assert payload_hd["model"] == "speech-2.8-hd"


def test_build_payload_maps_language_boost_short_codes():
    zh_payload = _build_payload(language_boost="zh")
    en_payload = _build_payload(language_boost="en")
    empty_payload = _build_payload(language_boost="")

    assert zh_payload.get("language_boost") == "Chinese"
    assert en_payload.get("language_boost") == "English"
    assert "language_boost" not in empty_payload


def test_build_payload_clamps_speed_volume_pitch_to_official_ranges():
    payload_high = _build_payload(speed=9, volume=0, pitch=99)
    payload_low = _build_payload(speed=0.1, volume=99, pitch=-99)

    assert payload_high["voice_setting"]["speed"] == 2.0
    assert payload_high["voice_setting"]["vol"] == 0.01
    assert payload_high["voice_setting"]["pitch"] == 12

    assert payload_low["voice_setting"]["speed"] == 0.5
    assert payload_low["voice_setting"]["vol"] == 10.0
    assert payload_low["voice_setting"]["pitch"] == -12


def test_build_payload_uses_expected_defaults():
    payload = _build_payload(speed=None, volume=None, pitch=None)

    assert payload["voice_setting"]["speed"] == 1.0
    assert payload["voice_setting"]["vol"] == 1.0
    assert payload["voice_setting"]["pitch"] == 0
