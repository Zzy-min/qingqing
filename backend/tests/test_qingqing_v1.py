import os
import sys
from pathlib import Path

import pytest
import httpx
import asyncio

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("QINGQING_CREDENTIAL_KEY", "test-only-key-material")
os.environ["QINGQING_ALLOW_LOCAL_USER"] = "true"

from main import app
from qingqing_v1.store import store


@pytest.fixture(autouse=True)
def clean_store():
    store.reset()


@pytest.fixture
def client():
    class Client:
        def request(self, method, url, **kwargs):
            async def call():
                transport = httpx.ASGITransport(app=app)
                headers = kwargs.pop("headers", {})
                async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as c:
                    return await c.request(method, url, **kwargs)
            return asyncio.run(call())
        def get(self, url, **kwargs): return self.request("GET", url, **kwargs)
        def post(self, url, **kwargs): return self.request("POST", url, **kwargs)
        def patch(self, url, **kwargs): return self.request("PATCH", url, **kwargs)
        def delete(self, url, **kwargs): return self.request("DELETE", url, **kwargs)
    return Client()


def test_free_entitlements_and_preferences_are_independent(client):
    ent = client.get("/api/v1/me/entitlements").json()
    assert ent["plan"] == "free"
    assert ent["concurrent_run_limit"] == 1
    prefs = client.get("/api/v1/me/preferences").json()
    assert prefs["advanced_mode_enabled"] is False
    assert prefs["credential_preference"] == "platform_first"
    assert prefs["memory_enabled"] is True
    updated = client.patch("/api/v1/me/preferences", json={"advanced_mode_enabled": True, "credential_preference": "byok_first"})
    assert updated.status_code == 200
    assert updated.json()["advanced_mode_enabled"] is True
    assert client.get("/api/v1/me/preferences").json()["credential_preference"] == "byok_first"
    assert client.get("/api/v1/me/entitlements").json()["plan"] == "free"


def test_vip_model_is_visible_but_locked_for_free_and_available_for_vip(client):
    free_models = client.get("/api/v1/models").json()["models"]
    premium = next(m for m in free_models if m["vip_required"])
    assert premium["availability"] == "locked"
    store.set_plan("local-user", "vip")
    vip = client.get("/api/v1/models").json()["models"]
    assert next(m for m in vip if m["id"] == premium["id"])["availability"] == "available"


def test_auto_route_and_vip_tampering_guard(client):
    preview = client.post("/api/v1/model-routes/preview", json={"capability": "image", "mode": "auto", "credential_preference": "platform_first"})
    assert preview.status_code == 200
    assert preview.json()["selected_model"]["capabilities"] == ["image"]
    run = client.post("/api/v1/agent/runs", json={"goal": "make image", "routing": {"mode": "locked", "preferred_model_id": "openai:gpt-4o", "credential_preference": "platform_first", "stage_overrides": {}, "budget_limit": 10}})
    assert run.status_code == 403


def test_runs_can_be_synchronized_across_clients(client):
    created = client.post(
        "/api/v1/agent/runs",
        headers={"Idempotency-Key": "cross-device-run"},
        json={
            "goal": "跨端继续创作",
            "routing": {
                "capability": "chat",
                "mode": "auto",
                "credential_preference": "platform_first",
                "stage_overrides": {},
                "budget_limit": 10,
            },
        },
    )
    assert created.status_code == 201
    runs = client.get("/api/v1/agent/runs").json()["runs"]
    assert runs[0]["id"] == created.json()["id"]
    assert runs[0]["invocations"][0]["routing_reason"]


def test_credentials_never_echo_secret_and_are_user_isolated(client, monkeypatch):
    client.patch("/api/v1/me/preferences", json={"advanced_mode_enabled": True})
    created = client.post("/api/v1/credentials", json={"provider": "openai", "api_key": "sk-super-secret-value"})
    assert created.status_code == 201
    body = created.json()
    assert "api_key" not in body and "secret" not in str(body)
    assert body["key_last4"] == "alue"
    listed = client.get("/api/v1/credentials").text
    assert "sk-super-secret-value" not in listed
    route = client.post("/api/v1/model-routes/preview", json={"capability": "chat", "mode": "auto", "credential_preference": "byok_only"})
    assert route.status_code == 200
    assert route.json()["selected_model"]["source"] == "byok"
    async def accepted(provider, api_key): return provider == "openai" and api_key == "sk-super-secret-value"
    monkeypatch.setattr("qingqing_v1.router.verify_provider_credential", accepted)
    assert client.post(f'/api/v1/credentials/{body["id"]}/test').json() == {"status": "verified", "live_check": True}
    assert client.get("/api/v1/models", headers={"X-User-Plan": "vip"}).json()["models"][0]["availability"] == "locked"
    assert client.delete(f'/api/v1/credentials/{body["id"]}').status_code == 204


@pytest.mark.parametrize("url", [
    "http://example.com/v1", "https://localhost/v1", "https://127.0.0.1/v1",
    "https://169.254.169.254/latest", "https://10.0.0.2/v1",
])
def test_custom_model_rejects_unsafe_endpoint(client, url):
    client.patch("/api/v1/me/preferences", json={"advanced_mode_enabled": True})
    response = client.post("/api/v1/custom-models", json={"name": "mine", "base_url": url, "api_key": "secret123", "model_id": "m", "capabilities": ["chat"]})
    assert response.status_code == 422


def test_custom_model_crud_and_byok_only_route(client, monkeypatch):
    client.patch("/api/v1/me/preferences", json={"advanced_mode_enabled": True})
    monkeypatch.setattr("qingqing_v1.security.socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    created = client.post("/api/v1/custom-models", json={"name": "mine", "base_url": "https://models.example.com/v1", "api_key": "secret123", "model_id": "creative", "capabilities": ["chat"]})
    assert created.status_code == 201
    model = created.json()
    assert "api_key" not in model
    route = client.post("/api/v1/model-routes/preview", json={"capability": "chat", "mode": "auto", "credential_preference": "byok_only"})
    assert route.status_code == 200
    assert route.json()["selected_model"]["source"] == "byok"
    patched = client.patch(f'/api/v1/custom-models/{model["id"]}', json={"name": "renamed"})
    assert patched.json()["display_name"] == "renamed"
    assert client.delete(f'/api/v1/custom-models/{model["id"]}').status_code == 204


def test_custom_model_headers_are_restricted_to_the_safe_allowlist(client, monkeypatch):
    monkeypatch.setattr(
        "qingqing_v1.security.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    client.patch("/api/v1/me/preferences", json={"advanced_mode_enabled": True})
    base = {
        "name": "mine",
        "base_url": "https://models.example.com/v1",
        "api_key": "secret123",
        "model_id": "creative",
        "capabilities": ["chat"],
    }
    rejected = client.post(
        "/api/v1/custom-models",
        json={**base, "custom_headers": {"Authorization": "attacker-value"}},
    )
    assert rejected.status_code == 422
    accepted = client.post(
        "/api/v1/custom-models",
        json={**base, "custom_headers": {"X-Organization": "studio-a"}},
    )
    assert accepted.status_code == 201
    assert accepted.json()["custom_headers"] == {"X-Organization": "studio-a"}
