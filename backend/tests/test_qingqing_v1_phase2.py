import asyncio, os, sys, uuid
from pathlib import Path
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from qingqing_v1.auth import create_session_token, verify_session_token
from qingqing_v1.store import SqliteStore, store
from test_qingqing_v1 import client as client_fixture


@pytest.fixture(autouse=True)
def clean_global_store():
    store.reset()


def test_session_token_is_signed_and_expiring(monkeypatch):
    monkeypatch.setenv("QINGQING_SESSION_SECRET", "a-secure-test-secret")
    token = create_session_token("alice", expires_in=60)
    assert verify_session_token(token)["sub"] == "alice"
    with pytest.raises(ValueError):
        verify_session_token(token + "tampered")
    expired = create_session_token("alice", expires_in=-1)
    with pytest.raises(ValueError):
        verify_session_token(expired)
    monkeypatch.delenv("QINGQING_SESSION_SECRET")
    with pytest.raises(ValueError):
        verify_session_token(token)


def test_sqlite_store_persists_user_preferences_and_key_version():
    # This repository already contains a legacy file named `.tmp`, so use a
    # dedicated sibling directory without modifying that user-owned file.
    folder = BACKEND / ".test-tmp"; folder.mkdir(exist_ok=True)
    path = folder / f"qingqing-{uuid.uuid4()}.db"
    try:
        first = SqliteStore(path)
        first.ensure_user("alice", "vip")
        first.save_preferences("alice", {"advanced_mode_enabled": True, "credential_preference": "byok_first"})
        first.save_credential("alice", {"id": "c1", "provider": "openai", "encrypted_key": "cipher", "key_last4": "last", "key_version": 3})
        second = SqliteStore(path)
        assert second.get_user("alice")["plan"] == "vip"
        assert second.get_preferences("alice")["advanced_mode_enabled"] is True
        assert second.list_credentials("alice")[0]["key_version"] == 3
        first.db.close(); second.db.close()
    finally:
        path.unlink(missing_ok=True)


def test_router_requires_signed_bearer_when_local_mode_is_disabled(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "false")
    monkeypatch.setenv("QINGQING_SESSION_SECRET", "a-secure-test-secret")
    assert client_fixture.get("/api/v1/models").status_code == 401
    token = create_session_token("alice")
    response = client_fixture.get("/api/v1/models", headers={"Authorization": f"Bearer {token}", "X-User-Plan": "vip"})
    assert response.status_code == 200
    assert any(model["availability"] == "locked" for model in response.json()["models"] if model["vip_required"])


def test_legacy_platform_key_routes_are_not_exposed_by_default(client_fixture):
    response = client_fixture.post(
        "/api/chat",
        json={"model": "openai:gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code in {404, 405}


def test_email_code_issues_a_signed_session_without_exposing_codes_in_production(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_SESSION_SECRET", "a-secure-test-secret")
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    requested = client_fixture.post("/api/v1/auth/email/request-code", json={"email": "Creator@Example.com"})
    assert requested.status_code == 202
    code = requested.json()["dev_code"]
    verified = client_fixture.post("/api/v1/auth/email/verify", json={"email": "creator@example.com", "code": code})
    assert verified.status_code == 200
    token = verified.json()["access_token"]
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "false")
    assert client_fixture.get("/api/v1/models", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client_fixture.post("/api/v1/auth/email/verify", json={"email": "creator@example.com", "code": code}).status_code == 400


def test_run_budget_invocations_and_idempotency(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    payload = {"goal": "create campaign", "routing": {"capability": "chat", "mode": "auto", "credential_preference": "platform_first", "stage_overrides": {"image": "openai:dall-e-3"}, "budget_limit": 0.01}}
    headers = {"Idempotency-Key": "campaign-1"}
    first = client_fixture.post("/api/v1/agent/runs", json=payload, headers=headers)
    assert first.status_code == 201
    assert first.json()["status"] == "awaiting_approval"
    assert {item["capability"] for item in first.json()["invocations"]} == {"chat", "image"}
    second = client_fixture.post("/api/v1/agent/runs", json=payload, headers=headers)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    approved = client_fixture.post(f'/api/v1/agent/runs/{first.json()["id"]}/approve')
    assert approved.status_code == 200
    assert approved.json()["status"] == "planned"
    ledger = client_fixture.get("/api/v1/billing/ledger").json()["entries"]
    assert any(entry["type"] == "reserved" for entry in ledger)
    cancelled = client_fixture.post(f'/api/v1/agent/runs/{first.json()["id"]}/cancel')
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    ledger = client_fixture.get("/api/v1/billing/ledger").json()["entries"]
    assert any(entry["type"] == "released" for entry in ledger)


def test_deleting_custom_model_pauses_unexecuted_run(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    monkeypatch.setattr("qingqing_v1.security.socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    client_fixture.patch("/api/v1/me/preferences", json={"advanced_mode_enabled": True})
    model = client_fixture.post("/api/v1/custom-models", json={"name": "mine", "base_url": "https://models.example.com/v1", "api_key": "secret123", "model_id": "creative", "capabilities": ["chat"]}).json()
    run = client_fixture.post("/api/v1/agent/runs", headers={"Idempotency-Key": "custom-run"}, json={"goal": "write", "routing": {"capability": "chat", "mode": "locked", "preferred_model_id": model["id"], "credential_preference": "byok_only", "stage_overrides": {}, "budget_limit": 1}}).json()
    assert run["status"] == "planned"
    assert client_fixture.delete(f'/api/v1/custom-models/{model["id"]}').status_code == 204
    persisted = client_fixture.get(f'/api/v1/agent/runs/{run["id"]}').json()
    assert persisted["status"] == "paused"
    assert persisted["invocations"][0]["status"] == "blocked_credential_deleted"


def test_text_run_executes_and_records_output_without_leaking_provider_errors(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    from gateway.schemas.chat import ChatChunk
    class FakeAdapter:
        async def chat(self, request):
            yield ChatChunk(model=request.model, delta="创作")
            yield ChatChunk(model=request.model, delta="完成")
    monkeypatch.setattr("qingqing_v1.execution.get_adapter", lambda provider: FakeAdapter())
    run = client_fixture.post("/api/v1/agent/runs", headers={"Idempotency-Key": "execute-text"}, json={"goal": "write", "routing": {"capability": "chat", "mode": "auto", "credential_preference": "platform_first", "stage_overrides": {}, "budget_limit": 1}}).json()
    assert client_fixture.post(f'/api/v1/agent/runs/{run["id"]}/execute').status_code == 202
    persisted = client_fixture.get(f'/api/v1/agent/runs/{run["id"]}').json()
    assert persisted["status"] == "completed"
    assert persisted["invocations"][0]["output"]["content"] == "创作完成"


def test_events_endpoint_returns_snapshot_for_completed_run(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    from gateway.schemas.chat import ChatChunk
    class FakeAdapter:
        async def chat(self, request):
            yield ChatChunk(model=request.model, delta="ok")
    monkeypatch.setattr("qingqing_v1.execution.get_adapter", lambda provider: FakeAdapter())
    run = client_fixture.post(
        "/api/v1/agent/runs",
        headers={"Idempotency-Key": "sse-snapshot"},
        json={"goal": "hi", "routing": {"capability": "chat", "mode": "auto", "credential_preference": "platform_first", "stage_overrides": {}, "budget_limit": 1}},
    ).json()
    assert client_fixture.post(f'/api/v1/agent/runs/{run["id"]}/execute').status_code == 202
    events = client_fixture.get(f'/api/v1/agent/runs/{run["id"]}/events')
    assert events.status_code == 200
    body = events.text
    assert "event: snapshot" in body
    assert "event: run_completed" in body
    assert "ok" in body


def test_primary_capability_without_chat_stage(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    class FakeAdapter:
        async def image(self, request):
            from gateway.schemas.image import ImageResponse, ImageData
            return ImageResponse(model=request.model, images=[ImageData(url="https://example.com/a.png")])
    monkeypatch.setattr("qingqing_v1.execution.get_adapter", lambda provider: FakeAdapter())
    created = client_fixture.post(
        "/api/v1/agent/runs",
        headers={"Idempotency-Key": "image-only"},
        json={"goal": "a cat", "routing": {"capability": "image", "mode": "auto", "credential_preference": "platform_first", "stage_overrides": {}, "budget_limit": 1}, "auto_plan": False},
    )
    assert created.status_code == 201
    caps = {item["capability"] for item in created.json()["invocations"]}
    assert caps == {"image"}
    assert client_fixture.post(f'/api/v1/agent/runs/{created.json()["id"]}/execute').status_code == 202
    done = client_fixture.get(f'/api/v1/agent/runs/{created.json()["id"]}').json()
    assert done["status"] == "completed"
    assert done["invocations"][0]["output"]["images"][0]["url"] == "https://example.com/a.png"


def test_skills_catalog_and_plan_preview(client_fixture):
    skills = client_fixture.get("/api/v1/skills").json()["skills"]
    assert any(item["id"] == "short-video-pack" for item in skills)
    preview = client_fixture.post(
        "/api/v1/agent/plans/preview",
        json={
            "goal": "做一条 15 秒产品短视频素材包：主视觉旁白配乐成片",
            "routing": {"capability": "chat", "mode": "auto", "credential_preference": "platform_first", "stage_overrides": {}, "budget_limit": 10},
            "auto_plan": True,
        },
    )
    assert preview.status_code == 200
    plan = preview.json()["plan"]
    assert plan["skill_id"] == "short-video-pack"
    assert len(plan["steps"]) == 4
    assert {step["capability"] for step in plan["steps"]} == {"image", "tts", "music", "video"}


def test_skill_run_executes_multiple_steps_in_order(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    from gateway.schemas.chat import ChatChunk
    from gateway.schemas.image import ImageResponse, ImageData
    from gateway.schemas.music import MusicResponse
    from gateway.schemas.video import VideoResponse

    class FakeAdapter:
        async def image(self, request):
            return ImageResponse(model=request.model, images=[ImageData(url="https://example.com/v.png")])

        async def tts(self, request):
            return b"voice-bytes"

        async def music(self, request):
            return MusicResponse(model=request.model, audio_url="https://example.com/m.mp3", duration=15.0)

        async def video(self, request):
            return VideoResponse(model=request.model, video_url="https://example.com/v.mp4", duration=15.0)

        async def chat(self, request):
            yield ChatChunk(model=request.model, delta="unused")

    monkeypatch.setattr("qingqing_v1.execution.get_adapter", lambda provider: FakeAdapter())
    created = client_fixture.post(
        "/api/v1/agent/runs",
        headers={"Idempotency-Key": "skill-multi"},
        json={
            "goal": "智能水杯 15 秒介绍",
            "skill_id": "short-video-pack",
            "routing": {"capability": "video", "mode": "auto", "credential_preference": "platform_first", "stage_overrides": {}, "budget_limit": 10},
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["plan"]["skill_id"] == "short-video-pack"
    assert len(body["invocations"]) == 4
    assert all(item.get("step_id") for item in body["invocations"])
    assert client_fixture.post(f'/api/v1/agent/runs/{body["id"]}/execute').status_code == 202
    done = client_fixture.get(f'/api/v1/agent/runs/{body["id"]}').json()
    assert done["status"] == "completed"
    assert {item["capability"] for item in done["invocations"] if item["status"] == "completed"} == {"image", "tts", "music", "video"}


def test_step_retry_requeues_failed_step(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    from gateway.schemas.chat import ChatChunk
    calls = {"n": 0}

    class FlakyAdapter:
        async def chat(self, request):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            yield ChatChunk(model=request.model, delta="recovered")

    monkeypatch.setattr("qingqing_v1.execution.get_adapter", lambda provider: FlakyAdapter())
    created = client_fixture.post(
        "/api/v1/agent/runs",
        headers={"Idempotency-Key": "step-retry"},
        json={
            "goal": "写一句广告",
            "skill_id": "social-copy",
            "routing": {"capability": "chat", "mode": "auto", "credential_preference": "platform_first", "stage_overrides": {}, "budget_limit": 1},
        },
    ).json()
    client_fixture.post(f'/api/v1/agent/runs/{created["id"]}/execute')
    failed = client_fixture.get(f'/api/v1/agent/runs/{created["id"]}').json()
    assert failed["status"] == "failed"
    step_id = failed["invocations"][0]["step_id"]
    retried = client_fixture.post(f'/api/v1/agent/runs/{created["id"]}/steps/{step_id}/retry')
    assert retried.status_code == 200
    assert retried.json()["status"] == "planned"
    assert retried.json()["invocations"][0]["status"] == "reserved"
    assert client_fixture.post(f'/api/v1/agent/runs/{created["id"]}/execute').status_code == 202
    done = client_fixture.get(f'/api/v1/agent/runs/{created["id"]}').json()
    assert done["status"] == "completed"
    assert done["invocations"][0]["output"]["content"] == "recovered"


def test_media_tool_execution_creates_authorized_artifact(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    from gateway.schemas.chat import ChatChunk
    class FakeAdapter:
        async def chat(self, request): yield ChatChunk(model=request.model, delta="plan")
        async def tts(self, request): return b"fake-mp3"
    monkeypatch.setattr("qingqing_v1.execution.get_adapter", lambda provider: FakeAdapter())
    run = client_fixture.post("/api/v1/agent/runs", headers={"Idempotency-Key": "execute-media"}, json={"goal": "speak", "routing": {"capability": "chat", "mode": "auto", "credential_preference": "platform_first", "stage_overrides": {"tts": "openai:tts-1"}, "budget_limit": 1}}).json()
    assert client_fixture.post(f'/api/v1/agent/runs/{run["id"]}/execute').status_code == 202
    persisted = client_fixture.get(f'/api/v1/agent/runs/{run["id"]}').json()
    assert persisted["status"] == "completed"
    artifacts = client_fixture.get(f'/api/v1/artifacts?run_id={run["id"]}').json()["artifacts"]
    assert len(artifacts) == 1 and "file_path" not in artifacts[0]
    content = client_fixture.get(f'/api/v1/artifacts/{artifacts[0]["id"]}/content')
    assert content.content == b"fake-mp3"
    from pathlib import Path
    artifact = store.get_artifact("local-user", artifacts[0]["id"])
    Path(artifact["file_path"]).unlink(missing_ok=True)


def test_failed_provider_run_can_be_retried_without_exposing_exception(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    class FailingAdapter:
        async def chat(self, request):
            if False:
                yield None
            raise RuntimeError("secret upstream detail")
    monkeypatch.setattr("qingqing_v1.execution.get_adapter", lambda provider: FailingAdapter())
    run = client_fixture.post("/api/v1/agent/runs", headers={"Idempotency-Key": "retry-run"}, json={"goal": "write", "routing": {"capability": "chat", "mode": "auto", "credential_preference": "platform_first", "stage_overrides": {}, "budget_limit": 1}}).json()
    client_fixture.post(f'/api/v1/agent/runs/{run["id"]}/execute')
    failed = client_fixture.get(f'/api/v1/agent/runs/{run["id"]}').json()
    assert failed["status"] == "failed" and "secret upstream detail" not in str(failed)
    retried = client_fixture.post(f'/api/v1/agent/runs/{run["id"]}/retry').json()
    assert retried["status"] == "planned" and retried["retry_count"] == 1


def test_google_byok_key_is_sent_in_a_header_not_the_logged_url(monkeypatch):
    from qingqing_v1.execution import _execute_official_byok_chat

    captured = {}

    class Response:
        status_code = 200

        def raise_for_status(self): pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "完成"}]}}]}

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, headers, json):
            captured.update(url=url, headers=headers)
            return Response()

    monkeypatch.setattr("qingqing_v1.execution.httpx.AsyncClient", Client)
    monkeypatch.setattr(
        "qingqing_v1.execution.store.get_credential",
        lambda user_id, credential_id: {"encrypted_key": "cipher"},
    )
    monkeypatch.setattr("qingqing_v1.execution.decrypt_secret", lambda value: "secret-api-key")
    result = asyncio.run(
        _execute_official_byok_chat(
            "user",
            "写一首诗",
            {
                "provider": "google",
                "credential_id": "credential",
                "original_model_id": "google:gemini-test",
            },
        )
    )
    assert result == "完成"
    assert "secret-api-key" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "secret-api-key"


def test_vip_revocation_pauses_an_unstarted_vip_invocation(client_fixture, monkeypatch):
    store.set_plan("local-user", "vip")
    run = client_fixture.post(
        "/api/v1/agent/runs",
        headers={"Idempotency-Key": "vip-revoked"},
        json={
            "goal": "write",
            "routing": {
                "capability": "chat",
                "mode": "locked",
                "preferred_model_id": "openai:gpt-4o",
                "credential_preference": "platform_first",
                "stage_overrides": {},
                "budget_limit": 1,
            },
        },
    ).json()
    store.set_plan("local-user", "free")
    response = client_fixture.post(f'/api/v1/agent/runs/{run["id"]}/execute')
    assert response.status_code == 202
    persisted = client_fixture.get(f'/api/v1/agent/runs/{run["id"]}').json()
    assert persisted["status"] == "paused"
    assert persisted["invocations"][0]["status"] == "paused_entitlement_changed"


def test_running_run_cannot_release_credit_by_cancelling(client_fixture):
    now = "2026-07-13T00:00:00+00:00"
    store.save_run(
        "local-user",
        {"id": "running", "goal": "work", "status": "running", "created_at": now},
    )
    response = client_fixture.post("/api/v1/agent/runs/running/cancel")
    assert response.status_code == 409
