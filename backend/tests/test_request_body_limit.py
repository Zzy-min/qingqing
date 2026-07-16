import asyncio
import json
import sys
from pathlib import Path

from starlette.requests import Request
from starlette.responses import Response

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import (
    MAX_REQUEST_BODY,
    MAX_REQUEST_BODY_MUSIC_COVER,
    limit_request_body,
    request_body_limit_for_path,
)


def _make_request(path: str, content_length: int) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [
            (b"host", b"testserver"),
            (b"content-length", str(content_length).encode("utf-8")),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def _make_chunked_request(path: str, chunks: list[bytes]) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [(b"host", b"testserver"), (b"transfer-encoding", b"chunked")],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    queue = list(chunks)

    async def receive():
        body = queue.pop(0)
        return {"type": "http.request", "body": body, "more_body": bool(queue)}

    return Request(scope, receive)


def test_request_body_limit_for_path_uses_route_specific_override():
    assert request_body_limit_for_path("/api/music/cover") == MAX_REQUEST_BODY_MUSIC_COVER
    assert request_body_limit_for_path("/api/video/generate") == MAX_REQUEST_BODY


def test_limit_request_body_blocks_oversized_music_cover_request():
    request = _make_request("/api/music/cover", MAX_REQUEST_BODY_MUSIC_COVER + 1)

    async def _call_next(_request):
        return Response(content="ok", status_code=200)

    response = asyncio.run(limit_request_body(request, _call_next))

    assert response.status_code == 413
    payload = json.loads(response.body.decode("utf-8"))
    assert "80MB" in payload["detail"]


def test_limit_request_body_allows_default_sized_request():
    request = _make_request("/api/video/generate", MAX_REQUEST_BODY)
    touched = {"value": False}

    async def _call_next(_request):
        touched["value"] = True
        return Response(content="ok", status_code=200)

    response = asyncio.run(limit_request_body(request, _call_next))

    assert response.status_code == 200
    assert touched["value"] is True


def test_limit_request_body_rejects_chunked_body_without_content_length(monkeypatch):
    monkeypatch.setattr("main.request_body_limit_for_path", lambda _path: 6)
    request = _make_chunked_request("/api/v1/upload", [b"1234", b"5678"])
    touched = {"value": False}

    async def _call_next(_request):
        touched["value"] = True
        return Response(content="ok", status_code=200)

    response = asyncio.run(limit_request_body(request, _call_next))

    assert response.status_code == 413
    assert touched["value"] is False
