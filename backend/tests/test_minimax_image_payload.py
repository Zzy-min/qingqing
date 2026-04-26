import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MINIMAX_API_KEY", "test-image-key")

from services.minimax import MiniMaxService


class DummyResponse:
    def json(self):
        return {
            "base_resp": {"status_code": 0, "status_msg": "success"},
            "data": {"image_base64": ["QUJD"]},
        }


def test_image_service_sends_official_options(monkeypatch):
    service = MiniMaxService(api_key="test-image-key")
    seen_payload = {}

    @asynccontextmanager
    async def fake_request_with_retry(method, url, **kwargs):
        assert method == "POST"
        assert url == "/image_generation"
        seen_payload.update(kwargs["json"])
        yield DummyResponse()

    monkeypatch.setattr(service, "_request_with_retry", fake_request_with_retry)

    result = asyncio.run(
        service.generate_image(
            prompt="test",
            model="image-01",
            aspect_ratio="16:9",
            n=9,
            seed=123,
            prompt_optimizer=True,
            response_format="base64",
            aigc_watermark=False,
            width=1024,
            height=768,
        )
    )

    assert seen_payload["model"] == "image-01"
    assert seen_payload["n"] == 9
    assert seen_payload["seed"] == 123
    assert seen_payload["prompt_optimizer"] is True
    assert seen_payload["response_format"] == "base64"
    assert seen_payload["aigc_watermark"] is False
    assert seen_payload["width"] == 1024
    assert seen_payload["height"] == 768
    assert "aspect_ratio" not in seen_payload
    assert result["image_base64"] == ["QUJD"]
