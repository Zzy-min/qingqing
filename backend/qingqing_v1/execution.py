from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from gateway.adapters import get_adapter
from gateway.schemas.chat import ChatMessage, ChatRequest
from gateway.schemas.image import ImageRequest
from gateway.schemas.music import MusicRequest
from gateway.schemas.tts import TTSRequest
from gateway.schemas.video import VideoRequest
from .events import event_bus
from .memory import build_memory_context, remember_run
from .planner import resolve_step_prompt, topological_invocation_order
from .security import decrypt_secret, validate_public_https_url
from .store import store


async def _emit(run_id: str, event_type: str, **payload):
    await event_bus.publish(run_id, {"type": event_type, **payload})


async def execute_chat_run(user_id: str, run_id: str):
    run = store.get_run(user_id, run_id)
    if not run or run["status"] != "running":
        return
    invocations = topological_invocation_order(store.list_invocations(user_id, run_id))
    completed: dict[str, dict] = {}
    try:
        await _emit(run_id, "run_started", status="running", plan=run.get("plan"))
        for invocation in invocations:
            if invocation["status"] not in {"reserved", "running"}:
                if invocation["status"] == "completed":
                    step_key = invocation.get("step_id") or invocation["id"]
                    completed[step_key] = invocation
                continue
            model = invocation["model"]
            user = store.get_user(user_id)
            credential = store.get_credential(user_id, model.get("credential_id")) if model.get("credential_id") else None
            entitlement_revoked = model.get("source") == "platform" and model.get("vip_required") and user.get("plan") != "vip"
            credential_revoked = model.get("source") == "byok" and (not credential or credential.get("status") != "active")
            if entitlement_revoked or credential_revoked:
                reason = "entitlement_changed" if entitlement_revoked else "credential_unavailable"
                store.save_invocation(user_id, {**invocation, "status": f"paused_{reason}"})
                store.save_run(user_id, {**run, "status": "paused", "pause_reason": reason})
                await _emit(run_id, "run_paused", pause_reason=reason, status="paused")
                return
            invocation = {**invocation, "status": "running"}
            store.save_invocation(user_id, invocation)
            step_key = invocation.get("step_id") or invocation["id"]
            await _emit(
                run_id,
                "step_started",
                invocation_id=invocation["id"],
                step_id=step_key,
                capability=invocation["capability"],
                title=invocation.get("title"),
                model=model,
            )
            step_goal = resolve_step_prompt(invocation, completed, run.get("goal") or "")
            if invocation.get("capability") == "chat":
                memory_ctx = build_memory_context(user_id, run.get("goal") or step_goal)
                if memory_ctx:
                    step_goal = f"{memory_ctx}\n\n---\n当前任务：\n{step_goal}"
            output = await _execute_capability(user_id, run_id, step_goal, invocation)
            done = {**invocation, "status": "completed", "output": output, "completed_at": _now(), "resolved_prompt": step_goal}
            store.save_invocation(user_id, done)
            completed[step_key] = done
            await _emit(
                run_id,
                "step_completed",
                invocation_id=invocation["id"],
                step_id=step_key,
                capability=invocation["capability"],
                title=invocation.get("title"),
                output=output,
            )
        store.save_run(user_id, {**run, "status": "completed", "completed_at": _now()})
        reserved = sum(entry["amount"] for entry in store.list_ledger(user_id, run_id) if entry["type"] == "reserved")
        if reserved:
            store.save_ledger(user_id, {"id": str(uuid4()), "run_id": run_id, "type": "charged", "amount": reserved, "created_at": _now()})
            store.save_ledger(user_id, {"id": str(uuid4()), "run_id": run_id, "type": "released", "amount": reserved, "created_at": _now()})
        final = store.get_run(user_id, run_id)
        invocations = store.list_invocations(user_id, run_id)
        try:
            remember_run(user_id, final or run, invocations)
        except Exception:
            pass
        await _emit(
            run_id,
            "run_completed",
            status="completed",
            run={**final, "invocations": invocations},
        )
    except Exception:
        for invocation in store.list_invocations(user_id, run_id):
            if invocation["status"] == "running":
                store.save_invocation(
                    user_id,
                    {
                        **invocation,
                        "status": "failed",
                        "error_code": "provider_execution_failed",
                        "failed_at": _now(),
                    },
                )
        store.save_run(user_id, {**run, "status": "failed", "error_code": "provider_execution_failed", "failed_at": _now()})
        final = store.get_run(user_id, run_id)
        await _emit(
            run_id,
            "run_failed",
            status="failed",
            error_code="provider_execution_failed",
            run={**final, "invocations": store.list_invocations(user_id, run_id)},
        )


async def _execute_chat(user_id: str, run_id: str, goal: str, model: dict, invocation_id: str) -> str:
    if model["source"] == "byok":
        if model.get("original_model_id"):
            content = await _execute_official_byok_chat(user_id, goal, model)
            if content:
                await _emit(run_id, "delta", invocation_id=invocation_id, capability="chat", delta=content)
            return content
        base_url = validate_public_https_url(model["base_url"])
        credential = store.get_credential(user_id, model["credential_id"])
        if not credential:
            raise RuntimeError("credential unavailable")
        headers = {
            "Authorization": f"Bearer {decrypt_secret(credential['encrypted_key'])}",
            "Content-Type": "application/json",
            **model.get("custom_headers", {}),
        }
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={"model": model["remote_model_id"], "messages": [{"role": "user", "content": goal}], "stream": False},
            )
            if 300 <= response.status_code < 400:
                raise RuntimeError("redirect refused")
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if content:
                await _emit(run_id, "delta", invocation_id=invocation_id, capability="chat", delta=content)
            return content
    adapter = get_adapter(model["provider"])
    request = ChatRequest(model=model["id"], messages=[ChatMessage(role="user", content=goal)], stream=True)
    parts = []
    async for chunk in adapter.chat(request):
        delta = chunk.delta or ""
        if delta:
            parts.append(delta)
            await _emit(run_id, "delta", invocation_id=invocation_id, capability="chat", delta=delta)
    return "".join(parts)


async def _execute_official_byok_chat(user_id: str, goal: str, model: dict) -> str:
    credential = store.get_credential(user_id, model["credential_id"])
    if not credential:
        raise RuntimeError("credential unavailable")
    api_key = decrypt_secret(credential["encrypted_key"])
    provider = model["provider"]
    model_name = model["original_model_id"].split(":", 1)[1]
    if provider == "google":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {"contents": [{"role": "user", "parts": [{"text": goal}]}]}
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    else:
        bases = {
            "openai": "https://api.openai.com/v1/chat/completions",
            "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            "minimax": "https://api.minimaxi.com/v1/text/chatcompletion_v2",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        }
        url = bases.get(provider)
        if not url:
            raise RuntimeError("provider BYOK is not supported")
        token = api_key
        if provider == "zhipu":
            import jwt, time
            if "." not in api_key:
                raise RuntimeError("invalid provider credential")
            key_id, secret = api_key.split(".", 1)
            token = jwt.encode(
                {"api_key": key_id, "exp": int(time.time()) + 3600, "timestamp": int(time.time())},
                secret,
                algorithm="HS256",
            )
        payload = {"model": model_name, "messages": [{"role": "user", "content": goal}], "stream": False}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
        response = await client.post(url, headers=headers, json=payload)
        if 300 <= response.status_code < 400:
            raise RuntimeError("redirect refused")
        response.raise_for_status()
        data = response.json()
    if provider == "google":
        return data["candidates"][0]["content"]["parts"][0]["text"]
    return data["choices"][0]["message"]["content"]


async def _execute_capability(user_id: str, run_id: str, goal: str, invocation: dict) -> dict:
    capability = invocation["capability"]
    model = invocation["model"]
    if capability == "chat":
        return {"content": await _execute_chat(user_id, run_id, goal, model, invocation["id"])}
    if model["source"] == "byok":
        if capability != "image":
            raise RuntimeError("custom provider capability is not executable")
        return await _execute_byok_image(user_id, run_id, goal, model)
    adapter = get_adapter(model["provider"])
    if capability == "image":
        response = await adapter.image(ImageRequest(model=model["id"], prompt=goal))
        output = response.model_dump()
        for image in output["images"]:
            _record_remote_artifact(user_id, run_id, "image", image.get("url"), model["id"])
        return output
    if capability == "tts":
        audio = await adapter.tts(TTSRequest(model=model["id"], input=goal))
        artifact = _write_artifact(user_id, run_id, "audio", "mp3", audio, model["id"])
        return {"artifact_id": artifact["id"], "content_url": f"/api/v1/artifacts/{artifact['id']}/content"}
    if capability == "music":
        response = await adapter.music(MusicRequest(model=model["id"], prompt=goal))
        output = response.model_dump()
        _record_remote_artifact(user_id, run_id, "audio", output.get("audio_url"), model["id"])
        return output
    if capability == "video":
        response = await adapter.video(VideoRequest(model=model["id"], prompt=goal))
        output = response.model_dump()
        _record_remote_artifact(user_id, run_id, "video", output.get("video_url"), model["id"])
        return output
    raise RuntimeError("unsupported capability")


async def _execute_byok_image(user_id: str, run_id: str, goal: str, model: dict) -> dict:
    base_url = validate_public_https_url(model["base_url"])
    credential = store.get_credential(user_id, model["credential_id"])
    if not credential:
        raise RuntimeError("credential unavailable")
    headers = {
        "Authorization": f"Bearer {decrypt_secret(credential['encrypted_key'])}",
        "Content-Type": "application/json",
        **model.get("custom_headers", {}),
    }
    async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
        response = await client.post(
            f"{base_url}/images/generations",
            headers=headers,
            json={"model": model["remote_model_id"], "prompt": goal},
        )
        if 300 <= response.status_code < 400:
            raise RuntimeError("redirect refused")
        response.raise_for_status()
        output = response.json()
    for image in output.get("data", []):
        _record_remote_artifact(user_id, run_id, "image", image.get("url"), model["id"])
    return output


def _artifact_root() -> Path:
    root = Path(__file__).resolve().parents[1] / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_artifact(user_id: str, run_id: str, kind: str, extension: str, content: bytes, model_id: str):
    artifact_id = str(uuid4())
    path = (_artifact_root() / f"{artifact_id}.{extension}").resolve()
    path.write_bytes(content)
    item = {
        "id": artifact_id,
        "run_id": run_id,
        "kind": kind,
        "model_id": model_id,
        "storage": "local",
        "file_path": str(path),
        "size": len(content),
        "created_at": _now(),
    }
    store.save_artifact(user_id, item)
    return item


def _record_remote_artifact(user_id: str, run_id: str, kind: str, url: str | None, model_id: str):
    if not url:
        return
    item = {
        "id": str(uuid4()),
        "run_id": run_id,
        "kind": kind,
        "model_id": model_id,
        "storage": "remote",
        "remote_url": url,
        "created_at": _now(),
    }
    store.save_artifact(user_id, item)


def _now():
    return datetime.now(timezone.utc).isoformat()


async def verify_provider_credential(provider: str, api_key: str) -> bool:
    urls = {
        "openai": "https://api.openai.com/v1/models",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
        "minimax": "https://api.minimaxi.com/v1/models",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4/models",
    }
    if provider == "google":
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        headers = {"x-goog-api-key": api_key}
    else:
        url = urls.get(provider)
        if not url:
            return False
        token = api_key
        if provider == "zhipu":
            import jwt, time
            if "." not in api_key:
                return False
            key_id, secret = api_key.split(".", 1)
            token = jwt.encode(
                {"api_key": key_id, "exp": int(time.time()) + 300, "timestamp": int(time.time())},
                secret,
                algorithm="HS256",
            )
        headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        response = await client.get(url, headers=headers)
        return 200 <= response.status_code < 300
