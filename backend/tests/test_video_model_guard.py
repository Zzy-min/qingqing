import asyncio
import base64
import io
import os
import sys
from pathlib import Path

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MINIMAX_API_KEY", "test-video-key")

from services.video import MAX_FRAME_ASPECT_RATIO, MIN_FRAME_ASPECT_RATIO, MIN_FRAME_SHORT_SIDE, VideoService


def make_data_url(width: int, height: int, color: tuple[int, int, int] = (80, 120, 180)) -> str:
    image = Image.new("RGB", (width, height), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


VALID_FRAME_IMAGE = make_data_url(640, 640)


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_video_service_auto_switches_model_for_first_last_frame(monkeypatch):
    service = VideoService(api_key="test-video-key")

    async def fake_request_with_retry(method, url, **kwargs):
        # Validate outgoing payload before hitting network.
        if method == "POST" and url == "/video_generation":
            assert kwargs["json"]["model"] == "MiniMax-Hailuo-02"
            return DummyResponse({"task_id": "task123", "base_resp": {"status_code": 0, "status_msg": "success"}})
        raise AssertionError("unexpected request path")

    monkeypatch.setattr(service, "_request_with_retry", fake_request_with_retry)

    result = asyncio.run(
        service.generate_video(
            prompt="test",
            model="MiniMax-Hailuo-2.3",
            first_frame=VALID_FRAME_IMAGE,
            last_frame=VALID_FRAME_IMAGE,
            no_wait=True,
        )
    )

    assert result["status"] == "Pending"
    assert result["model_used"] == "MiniMax-Hailuo-02"
    assert "auto-switched" in (result.get("model_adjustment") or "")


def test_video_service_disables_subject_reference_in_first_last_mode(monkeypatch):
    service = VideoService(api_key="test-video-key")

    async def fake_request_with_retry(method, url, **kwargs):
        if method == "POST" and url == "/video_generation":
            payload = kwargs["json"]
            assert payload["model"] == "MiniMax-Hailuo-02"
            assert "subject_reference" not in payload
            return DummyResponse({"task_id": "task456", "base_resp": {"status_code": 0, "status_msg": "success"}})
        raise AssertionError("unexpected request path")

    monkeypatch.setattr(service, "_request_with_retry", fake_request_with_retry)

    result = asyncio.run(
        service.generate_video(
            prompt="test",
            model="MiniMax-Hailuo-02",
            first_frame=VALID_FRAME_IMAGE,
            last_frame=VALID_FRAME_IMAGE,
            subject_image=VALID_FRAME_IMAGE,
            no_wait=True,
        )
    )

    assert result["status"] == "Pending"
    assert "subject_reference is incompatible" in (result.get("model_adjustment") or "")


def test_video_service_fallback_when_hailuo_02_not_in_token_plan(monkeypatch):
    service = VideoService(api_key="test-video-key")
    calls = []

    async def fake_request_with_retry(method, url, **kwargs):
        if method == "POST" and url == "/video_generation":
            payload = kwargs["json"]
            calls.append(payload.copy())
            if len(calls) == 1:
                # First attempt: Hailuo-02 rejected by token plan
                assert payload["model"] == "MiniMax-Hailuo-02"
                assert "last_frame_image" in payload
                return DummyResponse(
                    {
                        "base_resp": {
                            "status_code": 2061,
                            "status_msg": "your current token plan not support model, MiniMax-Hailuo-02-6s-768p",
                        }
                    }
                )
            # Second attempt: fallback to i2v Fast should be used.
            assert payload["model"] == "MiniMax-Hailuo-2.3-Fast"
            assert "last_frame_image" not in payload
            assert "subject_reference" not in payload
            return DummyResponse({"task_id": "task789", "base_resp": {"status_code": 0, "status_msg": "success"}})
        raise AssertionError("unexpected request path")

    monkeypatch.setattr(service, "_request_with_retry", fake_request_with_retry)

    result = asyncio.run(
        service.generate_video(
            prompt="test",
            model="MiniMax-Hailuo-2.3",
            first_frame=VALID_FRAME_IMAGE,
            last_frame=VALID_FRAME_IMAGE,
            subject_image=VALID_FRAME_IMAGE,
            no_wait=True,
        )
    )

    assert len(calls) == 2
    assert result["status"] == "Pending"
    assert result["model_used"] == "MiniMax-Hailuo-2.3-Fast"
    assert "auto-fallback to first-frame mode" in (result.get("model_adjustment") or "")


def test_video_service_raises_when_task_id_missing(monkeypatch):
    service = VideoService(api_key="test-video-key")

    async def fake_request_with_retry(method, url, **kwargs):
        if method == "POST" and url == "/video_generation":
            return DummyResponse({"base_resp": {"status_code": 0, "status_msg": "success"}})
        raise AssertionError("unexpected request path")

    monkeypatch.setattr(service, "_request_with_retry", fake_request_with_retry)

    try:
        asyncio.run(
            service.generate_video(
                prompt="test",
                model="MiniMax-Hailuo-2.3",
                no_wait=True,
            )
        )
    except ValueError as exc:
        assert "missing task_id" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing task_id")


def test_video_query_task_raises_on_base_resp_error(monkeypatch):
    service = VideoService(api_key="test-video-key")

    async def fake_request_with_retry(method, url, **kwargs):
        if method == "GET" and url.startswith("/query/video_generation?task_id="):
            return DummyResponse(
                {
                    "base_resp": {
                        "status_code": 2013,
                        "status_msg": "invalid params",
                    }
                }
            )
        raise AssertionError("unexpected request path")

    monkeypatch.setattr(service, "_request_with_retry", fake_request_with_retry)

    try:
        asyncio.run(service.query_task("task-error"))
    except ValueError as exc:
        assert "Video task query error" in str(exc)
        assert "2013" in str(exc)
    else:
        raise AssertionError("expected ValueError for task query API error")


def test_video_service_normalizes_frame_aspect_ratio_and_short_side():
    service = VideoService(api_key="test-video-key")

    # Very tall source image: ratio 0.2 (< 0.4) and short side 80 (< 320)
    source = make_data_url(80, 400)
    normalized = service._normalize_frame_image(source, "first_frame_image")

    assert normalized.startswith("data:image/jpeg;base64,")
    encoded = normalized.split(",", 1)[1]
    decoded = base64.b64decode(encoded)

    with Image.open(io.BytesIO(decoded)) as image:
        width, height = image.size

    ratio = width / height
    assert MIN_FRAME_ASPECT_RATIO <= ratio <= MAX_FRAME_ASPECT_RATIO
    assert min(width, height) >= MIN_FRAME_SHORT_SIDE


def test_video_service_normalizes_duration_resolution_combo(monkeypatch):
    service = VideoService(api_key="test-video-key")

    async def fake_request_with_retry(method, url, **kwargs):
        if method == "POST" and url == "/video_generation":
            payload = kwargs["json"]
            assert payload["duration"] == 6
            assert payload["resolution"] == "1080P"
            assert payload["prompt_optimizer"] is True
            assert payload["fast_pretreatment"] is True
            assert payload["aigc_watermark"] is False
            return DummyResponse({"task_id": "task-options", "base_resp": {"status_code": 0, "status_msg": "success"}})
        raise AssertionError("unexpected request path")

    monkeypatch.setattr(service, "_request_with_retry", fake_request_with_retry)

    result = asyncio.run(
        service.generate_video(
            prompt="test",
            model="MiniMax-Hailuo-2.3",
            duration=10,
            resolution="1080P",
            prompt_optimizer=True,
            fast_pretreatment=True,
            aigc_watermark=False,
            no_wait=True,
        )
    )

    assert result["task_id"] == "task-options"
    assert "1080P only supports 6 seconds" in (result.get("model_adjustment") or "")


def test_video_service_omits_duration_resolution_for_s2v(monkeypatch):
    service = VideoService(api_key="test-video-key")

    async def fake_request_with_retry(method, url, **kwargs):
        if method == "POST" and url == "/video_generation":
            payload = kwargs["json"]
            assert payload["model"] == "S2V-01"
            assert "duration" not in payload
            assert "resolution" not in payload
            assert "fast_pretreatment" not in payload
            return DummyResponse({"task_id": "task-s2v", "base_resp": {"status_code": 0, "status_msg": "success"}})
        raise AssertionError("unexpected request path")

    monkeypatch.setattr(service, "_request_with_retry", fake_request_with_retry)

    result = asyncio.run(
        service.generate_video(
            prompt="test",
            model="S2V-01",
            duration=10,
            resolution="768P",
            fast_pretreatment=True,
            no_wait=True,
        )
    )

    assert result["task_id"] == "task-s2v"
    assert "duration/resolution" in (result.get("model_adjustment") or "")
