import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MINIMAX_API_KEY", "test-default-key")

from api import routes
from api.key_override import normalize_override_key


class _StubService:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.closed = False

    async def fetch_remains(self):
        return {"success": True}

    async def close(self):
        self.closed = True


def test_normalize_override_key():
    assert normalize_override_key(None) is None
    assert normalize_override_key("") is None
    assert normalize_override_key("  ") is None
    assert normalize_override_key(" abc ") == "abc"


def test_resolve_token_plan_service_prefers_header(monkeypatch):
    monkeypatch.setattr(routes, "TokenPlanService", _StubService)
    service, close_after = asyncio.run(routes._resolve_token_plan_service("override-key"))
    assert close_after is True
    assert isinstance(service, _StubService)
    assert service.api_key == "override-key"


def test_resolve_token_plan_service_fallback_default_getter(monkeypatch):
    default_service = _StubService(api_key="from-env")

    async def _get_default():
        return default_service

    monkeypatch.setattr(routes, "get_token_plan_service", _get_default)
    service, close_after = asyncio.run(routes._resolve_token_plan_service(None))
    assert close_after is False
    assert service is default_service


def test_token_plan_remains_closes_request_scoped_service(monkeypatch):
    scoped = _StubService(api_key="scoped")

    async def _resolve(_header):
        return scoped, True

    monkeypatch.setattr(routes, "_resolve_token_plan_service", _resolve)
    payload = asyncio.run(routes.token_plan_remains("scoped-key"))
    assert payload["success"] is True
    assert scoped.closed is True
