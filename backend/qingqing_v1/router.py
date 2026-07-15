import asyncio
import hmac
import json
import os
import re
import secrets
import smtplib
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from gateway.registry.models import MODEL_REGISTRY
from .auth import create_session_token, hash_login_code, verify_session_token
from .events import event_bus
from .planner import build_plan
from .security import decrypt_secret, encrypt_secret, validate_public_https_url
from .skills import get_skill, list_skills
from .store import store
from .execution import execute_chat_run, verify_provider_credential

router = APIRouter(prefix="/api/v1", tags=["qingqing-v1"])
bearer = HTTPBearer(auto_error=False)
VIP_MODELS = {"openai:gpt-4o", "google:gemini-2.5-pro"}
VALID_CAPABILITIES = {"chat", "image", "tts", "music", "video"}
CAPABILITY_COST = {"chat": 0.02, "image": 0.15, "tts": 0.05, "music": 0.5, "video": 1.0}
ALLOWED_CUSTOM_HEADERS = {
    "openai-organization",
    "openai-project",
    "x-api-version",
    "x-organization",
    "x-project",
}


class Identity(BaseModel):
    user_id: str
    plan: Literal["free", "vip"]


class EmailCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class EmailCodeVerify(EmailCodeRequest):
    code: str = Field(pattern=r"^\d{6}$")


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Invalid email address")
    return email


def send_login_email(email: str, code: str):
    host = os.environ.get("QINGQING_SMTP_HOST")
    if not host:
        if os.environ.get("QINGQING_ALLOW_LOCAL_USER", "false").lower() == "true": return
        raise HTTPException(503, "Email service is not configured")
    message = EmailMessage(); message["Subject"] = "轻青登录验证码"; message["From"] = os.environ.get("QINGQING_SMTP_FROM", "noreply@qingqing.local"); message["To"] = email
    message.set_content(f"你的轻青登录验证码是 {code}，10 分钟内有效。请勿转发给他人。")
    port = int(os.environ.get("QINGQING_SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=10) as client:
        client.starttls(); username = os.environ.get("QINGQING_SMTP_USERNAME"); password = os.environ.get("QINGQING_SMTP_PASSWORD")
        if username and password: client.login(username, password)
        client.send_message(message)


def is_loopback_request(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "testclient"}


def current_identity(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Identity:
    if credentials:
        if credentials.scheme.lower() != "bearer":
            raise HTTPException(401, "Bearer token required")
        try:
            uid = verify_session_token(credentials.credentials)["sub"]
        except ValueError:
            raise HTTPException(401, "Invalid or expired session")
    elif os.environ.get("QINGQING_ALLOW_LOCAL_USER", "false").lower() == "true" and is_loopback_request(request):
        uid = "local-user"
    else:
        raise HTTPException(401, "Authentication required")
    store.ensure_user(uid)
    return Identity(user_id=uid, plan=store.get_user(uid)["plan"])


def entitlement(identity: Identity):
    vip = identity.plan == "vip"
    return {
        "plan": identity.plan,
        "accessible_model_ids": list(MODEL_REGISTRY) if vip else [m for m in MODEL_REGISTRY if m not in VIP_MODELS],
        "monthly_credit_limit": 1000 if vip else 100,
        "concurrent_run_limit": 5 if vip else 1,
        "queue_priority": 10 if vip else 0,
        "max_asset_size": 200_000_000 if vip else 20_000_000,
        "max_run_steps": 50 if vip else 10,
        "feature_flags": ["advanced_api"], "valid_from": None, "valid_until": None,
    }


def describe_models(identity: Identity):
    values = []
    for mid, entry in MODEL_REGISTRY.items():
        locked = mid in VIP_MODELS and identity.plan != "vip"
        quality = "premium" if mid in VIP_MODELS else "standard"
        values.append({
            "id": mid, "provider": entry.provider, "display_name": entry.display_name, "source": "platform",
            "capabilities": sorted(c.value for c in entry.capabilities),
            "input_modalities": ["text", "image"] if entry.supports_vision else ["text"],
            "output_modalities": sorted(c.value for c in entry.capabilities),
            "availability": "locked" if locked else "available", "unavailable_reason": "VIP required" if locked else None,
            "speed_tier": "standard", "quality_tier": quality, "cost_tier": "high" if quality == "premium" else "medium",
            "vip_required": mid in VIP_MODELS, "credential_id": None,
            "health_score": 1.0, "success_score": 0.95,
        })
    for credential in store.list_credentials(identity.user_id):
        provider = credential.get("provider")
        if provider == "openai-compatible" or credential.get("status") != "active": continue
        for original in [item for item in values if item["source"] == "platform" and item["provider"] == provider and "chat" in item["capabilities"]]:
            values.append({**original, "id": f"byok:{credential['id']}:{original['id']}", "source": "byok", "availability": "available", "unavailable_reason": None, "vip_required": False, "credential_id": credential["id"], "original_model_id": original["id"], "cost_tier": "provider_billed"})
    values.extend(store.list_custom_models(identity.user_id))
    return values


class Preferences(BaseModel):
    advanced_mode_enabled: bool | None = None
    credential_preference: Literal["platform_first", "byok_first", "byok_only"] | None = None


class RouteRequest(BaseModel):
    capability: Literal["chat", "image", "tts", "music", "video"] = "chat"
    mode: Literal["auto", "preferred", "locked"] = "auto"
    preferred_model_id: str | None = Field(None, max_length=200)
    credential_preference: Literal["platform_first", "byok_first", "byok_only"] = "platform_first"
    budget_limit: float | None = Field(None, ge=0)


class RunRouting(RouteRequest):
    stage_overrides: dict[str, str] = Field(default_factory=dict)


class RunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)
    routing: RunRouting
    skill_id: str | None = Field(None, max_length=80)
    auto_plan: bool = True


class PlanPreviewRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)
    routing: RunRouting = Field(default_factory=RunRouting)
    skill_id: str | None = Field(None, max_length=80)
    auto_plan: bool = True


class CredentialCreate(BaseModel):
    provider: Literal["openai", "google", "qwen", "zhipu", "minimax"]
    api_key: str = Field(min_length=8, max_length=4096)


class CustomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(max_length=2048)
    api_key: str = Field(min_length=8, max_length=4096)
    model_id: str = Field(min_length=1, max_length=120)
    capabilities: list[Literal["chat", "image", "tts", "music", "video"]] = Field(min_length=1, max_length=5)
    context_window: int | None = Field(None, ge=1, le=10_000_000)
    custom_headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("custom_headers")
    @classmethod
    def validate_custom_headers(cls, value: dict[str, str]):
        if len(value) > len(ALLOWED_CUSTOM_HEADERS):
            raise ValueError("Too many custom headers")
        sanitized = {}
        for name, raw in value.items():
            header = name.strip()
            content = raw.strip()
            if header.lower() not in ALLOWED_CUSTOM_HEADERS:
                raise ValueError("Custom header is not allowed")
            if not content or len(content) > 256 or any(char in content for char in "\r\n\0"):
                raise ValueError("Custom header value is invalid")
            sanitized[header] = content
        return sanitized


class CustomPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)


def require_advanced(identity: Identity):
    if not store.get_preferences(identity.user_id)["advanced_mode_enabled"]:
        raise HTTPException(403, "Advanced mode is disabled")


def public_credential(item):
    return {k: v for k, v in item.items() if k != "encrypted_key"}


def pause_runs_for_deleted_credential(identity: Identity, credential_id: str):
    affected_runs = set()
    for invocation in store.list_invocations(identity.user_id):
        if invocation.get("model", {}).get("credential_id") == credential_id and invocation["status"] in {"reserved", "awaiting_approval"}:
            store.save_invocation(identity.user_id, {**invocation, "status": "blocked_credential_deleted"})
            affected_runs.add(invocation["run_id"])
    for run_id in affected_runs:
        run = store.get_run(identity.user_id, run_id)
        if run: store.save_run(identity.user_id, {**run, "status": "paused", "pause_reason": "credential_deleted"})


def model_score(model: dict) -> float:
    quality = {"premium": 1.0, "standard": 0.75, "unknown": 0.6}.get(model.get("quality_tier"), 0.5)
    cost = {"low": 1.0, "medium": 0.75, "high": 0.45, "provider_billed": 0.6}.get(model.get("cost_tier"), 0.5)
    speed = {"fast": 1.0, "standard": 0.75, "slow": 0.5, "unknown": 0.6}.get(model.get("speed_tier"), 0.5)
    return round(quality * .4 + cost * .25 + speed * .15 + model.get("health_score", 1) * .1 + model.get("success_score", .9) * .1, 4)


@router.post("/auth/email/request-code", status_code=202)
def request_email_code(body: EmailCodeRequest, request: Request):
    email = normalize_email(body.email); now = int(time.time())
    local_delivery = os.environ.get("QINGQING_ALLOW_LOCAL_USER", "false").lower() == "true" and is_loopback_request(request)
    if not os.environ.get("QINGQING_SMTP_HOST") and not local_delivery:
        raise HTTPException(503, "Email service is not configured")
    if store.count_recent_auth_codes(email, now - 600) >= 3: raise HTTPException(429, "Too many verification requests")
    code = f"{secrets.randbelow(1_000_000):06d}"
    store.save_auth_code({"id": str(uuid4()), "email": email, "code_hash": hash_login_code(email, code), "expires_at": now + 600, "created_at": now})
    send_login_email(email, code)
    response = {"accepted": True, "expires_in": 600}
    if local_delivery: response["dev_code"] = code
    return response


@router.post("/auth/email/verify")
def verify_email_code(body: EmailCodeVerify):
    email = normalize_email(body.email); item = store.latest_auth_code(email); now = int(time.time())
    if not item or item["consumed"] or item["expires_at"] < now or item["attempts"] >= 5: raise HTTPException(400, "Invalid or expired verification code")
    if not hmac.compare_digest(item["code_hash"], hash_login_code(email, body.code)):
        store.increment_auth_attempt(item["id"]); raise HTTPException(400, "Invalid or expired verification code")
    store.consume_auth_code(item["id"]); uid = store.user_for_email(email) or str(uuid4()); store.bind_email(email, uid)
    return {"access_token": create_session_token(uid), "token_type": "bearer", "expires_in": 3600}


def select_route(req: RouteRequest, identity: Identity):
    all_models = describe_models(identity)
    exact = next((m for m in all_models if m["id"] == req.preferred_model_id), None) if req.preferred_model_id else None
    if exact and exact.get("source") == "byok" and exact.get("base_url"):
        validate_public_https_url(exact["base_url"])
    if exact and exact["availability"] != "available":
        raise HTTPException(403, exact["unavailable_reason"])
    if exact and req.capability in exact["capabilities"]:
        return exact, "User-selected model", [{"id": exact["id"], "score": model_score(exact)}]
    if req.mode == "locked" and req.preferred_model_id:
        raise HTTPException(409, "Locked model is unavailable or incompatible")
    candidates = [m for m in all_models if req.capability in m["capabilities"] and m["availability"] == "available"]
    for candidate in candidates:
        if candidate.get("source") == "byok" and candidate.get("base_url"):
            validate_public_https_url(candidate["base_url"])
    byok = [m for m in candidates if m["source"] == "byok"]
    platform = [m for m in candidates if m["source"] == "platform"]
    if req.credential_preference == "byok_only": candidates = byok
    elif req.credential_preference == "byok_first": candidates = byok or platform
    else: candidates = platform or byok
    ranked = sorted((({"model": m, "score": model_score(m)}) for m in candidates), key=lambda item: (-item["score"], item["model"]["id"]))
    if not ranked: raise HTTPException(409, "No eligible model")
    return ranked[0]["model"], "Balanced quality, cost, speed, health and success rate", [{"id": x["model"]["id"], "score": x["score"]} for x in ranked]


@router.get("/me/entitlements")
def get_entitlements(identity: Annotated[Identity, Depends(current_identity)]): return entitlement(identity)


@router.get("/me/preferences")
def get_preferences(identity: Annotated[Identity, Depends(current_identity)]):
    return store.get_preferences(identity.user_id)


@router.patch("/me/preferences")
def patch_preferences(body: Preferences, identity: Annotated[Identity, Depends(current_identity)]):
    value = {**store.get_preferences(identity.user_id), **body.model_dump(exclude_none=True)}
    store.save_preferences(identity.user_id, value); return value


@router.get("/models")
def models(identity: Annotated[Identity, Depends(current_identity)], capability: str | None = None, source: str | None = None):
    values = describe_models(identity)
    if capability: values = [m for m in values if capability in m["capabilities"]]
    if source: values = [m for m in values if m["source"] == source]
    return {"models": values}


@router.post("/model-routes/preview")
def preview(req: RouteRequest, identity: Annotated[Identity, Depends(current_identity)]):
    model, reason, ranking = select_route(req, identity); cost = CAPABILITY_COST[req.capability]
    return {"selected_model": model, "reason": reason, "ranking": ranking, "estimated_cost": {"min": 0 if model["source"] == "byok" else round(cost * .8, 3), "max": None if model["source"] == "byok" else cost}, "byok_cost_notice": model["source"] == "byok"}


@router.get("/skills")
def skills_catalog(identity: Annotated[Identity, Depends(current_identity)]):
    return {"skills": list_skills()}


@router.post("/agent/plans/preview")
def preview_plan(req: PlanPreviewRequest, identity: Annotated[Identity, Depends(current_identity)]):
    if req.skill_id and not get_skill(req.skill_id):
        raise HTTPException(404, "Skill not found")
    plan = build_plan(
        req.goal,
        capability=req.routing.capability,
        skill_id=req.skill_id,
        auto_plan=req.auto_plan,
        stage_overrides=req.routing.stage_overrides,
    )
    # Attach routed model previews per step without creating a run.
    routed_steps = []
    total = 0.0
    for step in plan["steps"]:
        preferred = req.routing.stage_overrides.get(step["capability"], req.routing.preferred_model_id if step["capability"] == req.routing.capability else None)
        stage_request = RouteRequest(
            **{
                **req.routing.model_dump(exclude={"stage_overrides"}),
                "capability": step["capability"],
                "preferred_model_id": preferred,
            }
        )
        model, reason, ranking = select_route(stage_request, identity)
        cost = 0 if model["source"] == "byok" else CAPABILITY_COST[step["capability"]]
        total += cost
        routed_steps.append({**step, "model": model, "routing_reason": reason, "estimated_cost": cost, "candidate_ranking": ranking})
    plan = {**plan, "steps": routed_steps, "estimated_cost": round(total, 3)}
    return {"plan": plan}


def _materialize_run_from_plan(req: RunRequest, identity: Identity, idempotency_key: str | None):
    if req.skill_id and not get_skill(req.skill_id):
        raise HTTPException(404, "Skill not found")
    limits = entitlement(identity)
    active = [r for r in store.list_runs(identity.user_id) if r["status"] in {"planned", "running", "awaiting_approval"}]
    if len(active) >= limits["concurrent_run_limit"]:
        raise HTTPException(429, "Concurrent run limit reached")
    plan = build_plan(
        req.goal,
        capability=req.routing.capability,
        skill_id=req.skill_id,
        auto_plan=req.auto_plan,
        stage_overrides=req.routing.stage_overrides,
    )
    if len(plan["steps"]) > limits["max_run_steps"]:
        raise HTTPException(403, "Run step limit exceeded")
    selections = []
    total = 0.0
    for step in plan["steps"]:
        if step["capability"] not in VALID_CAPABILITIES:
            raise HTTPException(422, f"Unsupported stage: {step['capability']}")
        preferred = req.routing.stage_overrides.get(
            step["capability"],
            req.routing.preferred_model_id if step["capability"] == req.routing.capability else None,
        )
        stage_request = RouteRequest(
            **{
                **req.routing.model_dump(exclude={"stage_overrides"}),
                "capability": step["capability"],
                "preferred_model_id": preferred,
            }
        )
        model, reason, ranking = select_route(stage_request, identity)
        cost = 0 if model["source"] == "byok" else CAPABILITY_COST[step["capability"]]
        total += cost
        selections.append((step, model, reason, ranking, cost))
    plan = {**plan, "estimated_cost": round(total, 3)}
    status = "awaiting_approval" if req.routing.budget_limit is not None and total > req.routing.budget_limit else "planned"
    rid = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    run = {
        "id": rid,
        "goal": req.goal,
        "status": status,
        "idempotency_key": idempotency_key,
        "routing_snapshot": req.routing.model_dump(),
        "skill_id": plan.get("skill_id"),
        "plan": plan,
        "estimated_cost": round(total, 3),
        "created_at": now,
    }
    ledger = store.list_ledger(identity.user_id)
    used = sum(entry["amount"] for entry in ledger if entry["type"] in {"reserved", "charged"}) - sum(
        entry["amount"] for entry in ledger if entry["type"] == "released"
    )
    if used + total > limits["monthly_credit_limit"]:
        raise HTTPException(402, "Monthly credit limit exceeded")
    if not store.create_run_once(identity.user_id, run):
        winner = store.get_run_by_idempotency(identity.user_id, idempotency_key)
        if winner:
            return {**winner, "invocations": store.list_invocations(identity.user_id, winner["id"])}
        raise HTTPException(409, "Run idempotency conflict")
    for step, model, reason, ranking, cost in selections:
        store.save_invocation(
            identity.user_id,
            {
                "id": str(uuid4()),
                "run_id": rid,
                "step_id": step["id"],
                "title": step.get("title"),
                "depends_on": list(step.get("depends_on") or []),
                "prompt": step.get("prompt") or req.goal,
                "capability": step["capability"],
                "model": model,
                "routing_reason": reason,
                "candidate_ranking": ranking,
                "estimated_cost": cost,
                "credential_source": model["source"],
                "status": "reserved" if status == "planned" else "awaiting_approval",
                "created_at": now,
            },
        )
    if total > 0:
        store.save_ledger(
            identity.user_id,
            {
                "id": str(uuid4()),
                "run_id": rid,
                "type": "reservation_pending" if status == "awaiting_approval" else "reserved",
                "amount": round(total, 3),
                "created_at": now,
            },
        )
    return {**run, "invocations": store.list_invocations(identity.user_id, rid)}


@router.post("/agent/runs", status_code=201)
def create_run(req: RunRequest, identity: Annotated[Identity, Depends(current_identity)], idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
    if idempotency_key:
        existing = store.get_run_by_idempotency(identity.user_id, idempotency_key)
        if existing:
            return existing
    return _materialize_run_from_plan(req, identity, idempotency_key)


@router.get("/agent/runs")
def list_runs(identity: Annotated[Identity, Depends(current_identity)]):
    runs = sorted(
        store.list_runs(identity.user_id),
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )
    return {
        "runs": [
            {
                **run,
                "invocations": store.list_invocations(identity.user_id, run["id"]),
            }
            for run in runs
        ]
    }


@router.get("/agent/runs/{run_id}")
def get_run(run_id: str, identity: Annotated[Identity, Depends(current_identity)]):
    run = store.get_run(identity.user_id, run_id)
    if not run: raise HTTPException(404, "Run not found")
    return {**run, "invocations": store.list_invocations(identity.user_id, run_id)}


TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "paused"}


@router.get("/agent/runs/{run_id}/events")
async def stream_run_events(run_id: str, identity: Annotated[Identity, Depends(current_identity)]):
    """Server-Sent Events for live AgentRun progress (delta, steps, terminal)."""
    run = store.get_run(identity.user_id, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    async def event_stream():
        def encode(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        snapshot = {**run, "invocations": store.list_invocations(identity.user_id, run_id)}
        yield encode("snapshot", {"type": "snapshot", "run": snapshot})
        if snapshot.get("status") in TERMINAL_RUN_STATUSES:
            terminal = "run_completed" if snapshot["status"] == "completed" else (
                "run_failed" if snapshot["status"] == "failed" else f"run_{snapshot['status']}"
            )
            yield encode(terminal, {"type": terminal, "status": snapshot["status"], "run": snapshot})
            return

        queue = await event_bus.subscribe(run_id)
        try:
            # Re-check in case execution finished between snapshot and subscribe.
            latest = store.get_run(identity.user_id, run_id)
            if latest and latest.get("status") in TERMINAL_RUN_STATUSES:
                full = {**latest, "invocations": store.list_invocations(identity.user_id, run_id)}
                terminal = "run_completed" if full["status"] == "completed" else (
                    "run_failed" if full["status"] == "failed" else f"run_{full['status']}"
                )
                yield encode(terminal, {"type": terminal, "status": full["status"], "run": full})
                return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    current = store.get_run(identity.user_id, run_id)
                    if current and current.get("status") in TERMINAL_RUN_STATUSES:
                        full = {**current, "invocations": store.list_invocations(identity.user_id, run_id)}
                        terminal = "run_completed" if full["status"] == "completed" else (
                            "run_failed" if full["status"] == "failed" else f"run_{full['status']}"
                        )
                        yield encode(terminal, {"type": terminal, "status": full["status"], "run": full})
                        return
                    yield encode("ping", {"type": "ping"})
                    continue
                event_type = event.get("type", "message")
                yield encode(event_type, event)
                if event_type in {"run_completed", "run_failed", "run_paused", "run_cancelled"}:
                    return
        finally:
            await event_bus.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/agent/runs/{run_id}/execute", status_code=202)
def execute_run(run_id: str, background: BackgroundTasks, identity: Annotated[Identity, Depends(current_identity)]):
    run = store.get_run(identity.user_id, run_id)
    if not run: raise HTTPException(404, "Run not found")
    running = store.claim_run_status(
        identity.user_id,
        run_id,
        "planned",
        {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()},
    )
    if not running: raise HTTPException(409, "Run is not ready for execution")
    background.add_task(execute_chat_run, identity.user_id, run_id)
    return running


@router.post("/agent/runs/{run_id}/approve")
def approve_run(run_id: str, identity: Annotated[Identity, Depends(current_identity)]):
    run = store.get_run(identity.user_id, run_id)
    if not run: raise HTTPException(404, "Run not found")
    if run["status"] != "awaiting_approval": raise HTTPException(409, "Run is not awaiting approval")
    run = {**run, "status": "planned", "approved_at": datetime.now(timezone.utc).isoformat()}; store.save_run(identity.user_id, run)
    for invocation in store.list_invocations(identity.user_id, run_id):
        store.save_invocation(identity.user_id, {**invocation, "status": "reserved"})
    for entry in store.list_ledger(identity.user_id, run_id):
        if entry["type"] == "reservation_pending": store.save_ledger(identity.user_id, {**entry, "type": "reserved"})
    return {**run, "invocations": store.list_invocations(identity.user_id, run_id)}


@router.post("/agent/runs/{run_id}/cancel")
def cancel_run(run_id: str, identity: Annotated[Identity, Depends(current_identity)]):
    run = store.get_run(identity.user_id, run_id)
    if not run: raise HTTPException(404, "Run not found")
    if run["status"] in {"running", "completed", "cancelled"}: raise HTTPException(409, "Run cannot be cancelled")
    now = datetime.now(timezone.utc).isoformat(); run = {**run, "status": "cancelled", "cancelled_at": now}; store.save_run(identity.user_id, run)
    for invocation in store.list_invocations(identity.user_id, run_id):
        if invocation["status"] in {"reserved", "awaiting_approval"}: store.save_invocation(identity.user_id, {**invocation, "status": "cancelled"})
    reserved = sum(entry["amount"] for entry in store.list_ledger(identity.user_id, run_id) if entry["type"] in {"reserved", "reservation_pending"})
    if reserved: store.save_ledger(identity.user_id, {"id": str(uuid4()), "run_id": run_id, "type": "released", "amount": reserved, "created_at": now})
    return run


@router.post("/agent/runs/{run_id}/retry")
def retry_run(run_id: str, identity: Annotated[Identity, Depends(current_identity)]):
    run = store.get_run(identity.user_id, run_id)
    if not run: raise HTTPException(404, "Run not found")
    if run["status"] != "failed": raise HTTPException(409, "Only failed runs can be retried")
    for invocation in store.list_invocations(identity.user_id, run_id):
        if invocation["status"] == "failed":
            cleaned = {k: v for k, v in invocation.items() if k not in {"error_code", "failed_at", "output", "resolved_prompt"}}
            store.save_invocation(identity.user_id, {**cleaned, "status": "reserved"})
    retried = {k: v for k, v in run.items() if k not in {"error_code", "failed_at"}}
    retried = {**retried, "status": "planned", "retry_count": int(run.get("retry_count", 0)) + 1, "updated_at": datetime.now(timezone.utc).isoformat()}
    store.save_run(identity.user_id, retried); return retried


@router.post("/agent/runs/{run_id}/steps/{step_id}/retry")
def retry_step(run_id: str, step_id: str, identity: Annotated[Identity, Depends(current_identity)]):
    """Re-queue a single failed step and reset the run to planned for re-execution."""
    run = store.get_run(identity.user_id, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run["status"] not in {"failed", "paused"}:
        raise HTTPException(409, "Only failed or paused runs support step retry")
    target = None
    for invocation in store.list_invocations(identity.user_id, run_id):
        key = invocation.get("step_id") or invocation["id"]
        if key == step_id or invocation["id"] == step_id:
            target = invocation
            break
    if not target:
        raise HTTPException(404, "Step not found")
    if target["status"] not in {"failed", "paused_entitlement_changed", "paused_credential_unavailable", "blocked_credential_deleted"}:
        raise HTTPException(409, "Step is not retryable")
    cleaned = {k: v for k, v in target.items() if k not in {"error_code", "failed_at", "output", "resolved_prompt", "pause_reason"}}
    store.save_invocation(identity.user_id, {**cleaned, "status": "reserved"})
    # Leave completed siblings as completed; executor skips them.
    retried = {k: v for k, v in run.items() if k not in {"error_code", "failed_at", "pause_reason"}}
    retried = {
        **retried,
        "status": "planned",
        "retry_count": int(run.get("retry_count", 0)) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    store.save_run(identity.user_id, retried)
    return {**retried, "invocations": store.list_invocations(identity.user_id, run_id)}


@router.get("/billing/ledger")
def billing_ledger(identity: Annotated[Identity, Depends(current_identity)]): return {"entries": store.list_ledger(identity.user_id)}


def public_artifact(item: dict): return {k: v for k, v in item.items() if k != "file_path"}


@router.get("/artifacts")
def list_artifacts(identity: Annotated[Identity, Depends(current_identity)], run_id: str | None = None):
    return {"artifacts": [public_artifact(item) for item in store.list_artifacts(identity.user_id, run_id)]}


@router.get("/artifacts/{artifact_id}/content")
def artifact_content(artifact_id: str, identity: Annotated[Identity, Depends(current_identity)]):
    artifact = store.get_artifact(identity.user_id, artifact_id)
    if not artifact or artifact.get("storage") != "local": raise HTTPException(404, "Artifact content not found")
    root = (Path(__file__).resolve().parents[1] / "artifacts").resolve(); path = Path(artifact["file_path"]).resolve()
    if root not in path.parents or not path.is_file(): raise HTTPException(404, "Artifact content not found")
    return FileResponse(path)


@router.get("/credentials")
def list_credentials(identity: Annotated[Identity, Depends(current_identity)]): return [public_credential(v) for v in store.list_credentials(identity.user_id)]


@router.post("/credentials", status_code=201)
def create_credential(body: CredentialCreate, identity: Annotated[Identity, Depends(current_identity)]):
    require_advanced(identity); cid = str(uuid4()); now = datetime.now(timezone.utc).isoformat()
    item = {"id": cid, "provider": body.provider, "encrypted_key": encrypt_secret(body.api_key), "key_last4": body.api_key[-4:], "key_version": int(os.environ.get("QINGQING_CREDENTIAL_KEY_VERSION", "1")), "updated_at": now, "status": "active"}
    store.save_credential(identity.user_id, item); return public_credential(item)


@router.patch("/credentials/{cid}")
def update_credential(cid: str, body: CredentialCreate, identity: Annotated[Identity, Depends(current_identity)]):
    require_advanced(identity); old = store.get_credential(identity.user_id, cid)
    if not old: raise HTTPException(404, "Credential not found")
    item = {**old, "provider": body.provider, "encrypted_key": encrypt_secret(body.api_key), "key_last4": body.api_key[-4:], "key_version": int(os.environ.get("QINGQING_CREDENTIAL_KEY_VERSION", "1")), "updated_at": datetime.now(timezone.utc).isoformat()}
    store.save_credential(identity.user_id, item); return public_credential(item)


@router.post("/credentials/{cid}/test")
async def test_credential(cid: str, identity: Annotated[Identity, Depends(current_identity)]):
    require_advanced(identity)
    credential = store.get_credential(identity.user_id, cid)
    if not credential: raise HTTPException(404, "Credential not found")
    if credential["provider"] == "openai-compatible": return {"status": "configured", "live_check": False, "reason": "Test the associated custom model endpoint"}
    try: valid = await verify_provider_credential(credential["provider"], decrypt_secret(credential["encrypted_key"]))
    except Exception: valid = False
    if not valid: raise HTTPException(422, "Provider rejected the credential or was unavailable")
    return {"status": "verified", "live_check": True}


@router.delete("/credentials/{cid}", status_code=204)
def delete_credential(cid: str, identity: Annotated[Identity, Depends(current_identity)]):
    if not store.delete_credential(identity.user_id, cid): raise HTTPException(404, "Credential not found")
    pause_runs_for_deleted_credential(identity, cid)
    return Response(status_code=204)


@router.get("/custom-models")
def custom_models(identity: Annotated[Identity, Depends(current_identity)]): return store.list_custom_models(identity.user_id)


@router.post("/custom-models", status_code=201)
def create_custom(body: CustomCreate, identity: Annotated[Identity, Depends(current_identity)]):
    require_advanced(identity); base = validate_public_https_url(body.base_url); model_id = f"custom:{uuid4()}"; credential_id = str(uuid4())
    store.save_credential(identity.user_id, {"id": credential_id, "provider": "openai-compatible", "encrypted_key": encrypt_secret(body.api_key), "key_last4": body.api_key[-4:], "key_version": int(os.environ.get("QINGQING_CREDENTIAL_KEY_VERSION", "1")), "status": "active"})
    item = {"id": model_id, "provider": "openai-compatible", "display_name": body.name, "source": "byok", "base_url": base, "remote_model_id": body.model_id, "capabilities": list(dict.fromkeys(body.capabilities)), "input_modalities": ["text"], "output_modalities": body.capabilities, "availability": "available", "unavailable_reason": None, "speed_tier": "unknown", "quality_tier": "unknown", "cost_tier": "provider_billed", "vip_required": False, "credential_id": credential_id, "context_window": body.context_window, "custom_headers": body.custom_headers, "health_score": 1.0, "success_score": .9}
    store.save_custom_model(identity.user_id, item); return item


@router.patch("/custom-models/{mid:path}")
def patch_custom(mid: str, body: CustomPatch, identity: Annotated[Identity, Depends(current_identity)]):
    key = mid if mid.startswith("custom:") else f"custom:{mid}"; item = store.get_custom_model(identity.user_id, key)
    if not item: raise HTTPException(404, "Custom model not found")
    if body.name: item = {**item, "display_name": body.name}
    store.save_custom_model(identity.user_id, item); return item


@router.delete("/custom-models/{mid:path}", status_code=204)
def delete_custom(mid: str, identity: Annotated[Identity, Depends(current_identity)]):
    key = mid if mid.startswith("custom:") else f"custom:{mid}"; item = store.get_custom_model(identity.user_id, key)
    if not item: raise HTTPException(404, "Custom model not found")
    store.delete_custom_model(identity.user_id, key); store.delete_credential(identity.user_id, item["credential_id"])
    pause_runs_for_deleted_credential(identity, item["credential_id"])
    return Response(status_code=204)
