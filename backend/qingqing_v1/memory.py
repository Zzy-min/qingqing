"""User memory: session/run summaries + style preference injection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .store import store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokenize(text: str) -> set[str]:
    """Tokenize for mixed Chinese/English retrieval (words + CJK bigrams)."""
    raw = (text or "").lower().replace("，", " ").replace("。", " ").replace(",", " ")
    tokens = {part for part in raw.split() if len(part) > 1}
    cjk = [ch for ch in raw if "\u4e00" <= ch <= "\u9fff"]
    for i in range(len(cjk) - 1):
        tokens.add(cjk[i] + cjk[i + 1])
    for ch in cjk:
        tokens.add(ch)
    return tokens


def remember_run(user_id: str, run: dict[str, Any], invocations: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Persist a lightweight summary after a completed run."""
    prefs = store.get_preferences(user_id)
    if prefs.get("memory_enabled") is False:
        return None
    invocations = invocations or store.list_invocations(user_id, run.get("id"))
    snippets = []
    for inv in invocations:
        if inv.get("status") != "completed":
            continue
        out = inv.get("output") or {}
        if out.get("content"):
            snippets.append(str(out["content"])[:280])
        elif out.get("artifact_id"):
            snippets.append(f"[{inv.get('capability')}] artifact:{out['artifact_id']}")
        elif out.get("images"):
            snippets.append(f"[image] {out['images'][0].get('url', '')}")
    body = " | ".join(snippets) if snippets else "（无文本输出）"
    skill = (run.get("plan") or {}).get("skill_id") or run.get("skill_id")
    item = {
        "id": str(uuid4()),
        "kind": "run_summary",
        "run_id": run.get("id"),
        "goal": run.get("goal") or "",
        "skill_id": skill,
        "status": run.get("status"),
        "content": f"目标：{run.get('goal') or ''}；结果摘要：{body}",
        "tags": [c for c in {inv.get("capability") for inv in invocations if inv.get("capability")}],
        "created_at": _now(),
    }
    store.save_memory(user_id, item)
    return item


def add_note(user_id: str, content: str, *, kind: str = "note", tags: list[str] | None = None) -> dict[str, Any]:
    item = {
        "id": str(uuid4()),
        "kind": kind,
        "content": content.strip(),
        "tags": tags or [],
        "created_at": _now(),
    }
    store.save_memory(user_id, item)
    return item


def list_memory(user_id: str, *, limit: int = 50, query: str | None = None) -> list[dict[str, Any]]:
    items = sorted(store.list_memory(user_id), key=lambda x: x.get("created_at", ""), reverse=True)
    if not query:
        return items[: max(1, min(limit, 200))]
    q = query.strip()
    q_tokens = _tokenize(q)
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in items:
        hay = f"{item.get('goal', '')} {item.get('content', '')} {' '.join(item.get('tags') or [])}"
        hay_l = hay.lower()
        score = 0
        if q.lower() in hay_l:
            score += 10
        score += sum(3 for token in q_tokens if token in hay_l)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (pair[0], pair[1].get("created_at", "")), reverse=True)
    return [item for _, item in scored[: max(1, min(limit, 200))]]


def delete_memory(user_id: str, memory_id: str) -> bool:
    return store.delete_memory(user_id, memory_id)


def build_memory_context(user_id: str, goal: str, *, limit: int = 5) -> str:
    """Build a short context block for prompt injection."""
    prefs = store.get_preferences(user_id)
    if prefs.get("memory_enabled") is False:
        return ""
    parts: list[str] = []
    style = (prefs.get("style_notes") or "").strip()
    avoid = (prefs.get("avoid_notes") or "").strip()
    tone = (prefs.get("preferred_tone") or "").strip()
    if style or avoid or tone:
        profile = []
        if tone:
            profile.append(f"语气：{tone}")
        if style:
            profile.append(f"风格：{style}")
        if avoid:
            profile.append(f"避免：{avoid}")
        parts.append("用户偏好：" + "；".join(profile))

    memories = list_memory(user_id, limit=40, query=goal)
    if not memories:
        memories = list_memory(user_id, limit=limit)
    selected = memories[:limit]
    if selected:
        lines = [f"- {item.get('content', '')[:220]}" for item in selected]
        parts.append("相关历史记忆：\n" + "\n".join(lines))
    return "\n\n".join(parts)
