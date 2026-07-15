"""Built-in tools + MCP whitelist registry (no arbitrary network by default)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from .memory import list_memory
from .planner import CAPABILITY_COST, estimate_cost
from .skills import list_skills
from .store import store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_mcp_servers() -> list[dict[str, Any]]:
    """Return user/env whitelisted MCP servers (metadata only)."""
    raw = os.environ.get("QINGQING_MCP_SERVERS", "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    servers = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            url = str(item.get("url") or "").strip()
            if not name:
                continue
            servers.append(
                {
                    "name": name,
                    "url": url or None,
                    "enabled": bool(item.get("enabled", False)),
                    "transport": item.get("transport") or "stdio",
                    "note": "Phase 3: registration only; tools are not auto-invoked over the network.",
                }
            )
    return servers


def _tool_list_artifacts(user_id: str, args: dict[str, Any]) -> dict[str, Any]:
    run_id = args.get("run_id")
    items = store.list_artifacts(user_id, run_id)
    public = [{k: v for k, v in item.items() if k != "file_path"} for item in items]
    return {"artifacts": public[:50], "count": len(public)}


def _tool_search_memory(user_id: str, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "")
    limit = int(args.get("limit") or 10)
    return {"items": list_memory(user_id, limit=limit, query=query or None)}


def _tool_list_models(user_id: str, args: dict[str, Any]) -> dict[str, Any]:
    from gateway.registry.models import MODEL_REGISTRY

    capability = args.get("capability")
    models = []
    for mid, entry in MODEL_REGISTRY.items():
        caps = sorted(c.value for c in entry.capabilities)
        if capability and capability not in caps:
            continue
        models.append({"id": mid, "provider": entry.provider, "display_name": entry.display_name, "capabilities": caps})
    return {"models": models}


def _tool_list_skills(user_id: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"skills": list_skills()}


def _tool_estimate_cost(user_id: str, args: dict[str, Any]) -> dict[str, Any]:
    capabilities = args.get("capabilities") or []
    if not isinstance(capabilities, list):
        capabilities = []
    steps = [{"capability": str(c)} for c in capabilities if str(c) in CAPABILITY_COST]
    return {"estimated_cost": estimate_cost(steps), "breakdown": {c: CAPABILITY_COST[c] for c in CAPABILITY_COST if c in {s["capability"] for s in steps}}}


TOOL_SPECS: dict[str, dict[str, Any]] = {
    "list_artifacts": {
        "name": "list_artifacts",
        "description": "列出当前用户的作品/产物元数据（不含本地路径）",
        "parameters": {"run_id": "optional run id"},
        "handler": _tool_list_artifacts,
    },
    "search_memory": {
        "name": "search_memory",
        "description": "按关键词检索用户记忆与历史摘要",
        "parameters": {"query": "string", "limit": "int optional"},
        "handler": _tool_search_memory,
    },
    "list_models": {
        "name": "list_models",
        "description": "列出平台模型目录",
        "parameters": {"capability": "optional chat|image|tts|music|video"},
        "handler": _tool_list_models,
    },
    "list_skills": {
        "name": "list_skills",
        "description": "列出内置创作 Skills",
        "parameters": {},
        "handler": _tool_list_skills,
    },
    "estimate_cost": {
        "name": "estimate_cost",
        "description": "估算一组 capability 的平台额度成本",
        "parameters": {"capabilities": "list of capability names"},
        "handler": _tool_estimate_cost,
    },
}


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": spec["name"],
            "description": spec["description"],
            "parameters": spec["parameters"],
            "source": "builtin",
        }
        for spec in TOOL_SPECS.values()
    ]


def invoke_tool(user_id: str, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    arguments = arguments or {}
    spec = TOOL_SPECS.get(name)
    call_id = str(uuid4())
    started = _now()
    if not spec:
        record = {
            "id": call_id,
            "tool": name,
            "arguments": arguments,
            "status": "failed",
            "error_code": "unknown_tool",
            "created_at": started,
            "finished_at": _now(),
        }
        store.save_tool_call(user_id, record)
        raise ValueError("unknown tool")
    try:
        handler: Callable[[str, dict[str, Any]], dict[str, Any]] = spec["handler"]
        result = handler(user_id, arguments)
        record = {
            "id": call_id,
            "tool": name,
            "arguments": arguments,
            "status": "completed",
            "result": result,
            "created_at": started,
            "finished_at": _now(),
        }
        store.save_tool_call(user_id, record)
        return {"call_id": call_id, "tool": name, "status": "completed", "result": result}
    except Exception as exc:
        record = {
            "id": call_id,
            "tool": name,
            "arguments": arguments,
            "status": "failed",
            "error_code": "tool_execution_failed",
            "error_message": str(exc)[:200],
            "created_at": started,
            "finished_at": _now(),
        }
        store.save_tool_call(user_id, record)
        raise


def list_tool_calls(user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    items = sorted(store.list_tool_calls(user_id), key=lambda x: x.get("created_at", ""), reverse=True)
    return items[: max(1, min(limit, 200))]
