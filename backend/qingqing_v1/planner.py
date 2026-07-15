"""Deterministic planner: skills + auto multi-step inference."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .skills import SKILLS, get_skill

CAPABILITY_COST = {"chat": 0.02, "image": 0.15, "tts": 0.05, "music": 0.5, "video": 1.0}
VALID_CAPABILITIES = set(CAPABILITY_COST)


def _render_prompt(template: str, goal: str) -> str:
    return template.format(goal=goal, previous_script="{previous_script}")


def _steps_from_skill(skill: dict[str, Any], goal: str) -> list[dict[str, Any]]:
    steps = []
    for raw in skill["steps"]:
        steps.append(
            {
                "id": raw["id"],
                "capability": raw["capability"],
                "title": raw["title"],
                "depends_on": list(raw.get("depends_on") or []),
                "prompt": _render_prompt(raw["prompt_template"], goal),
            }
        )
    return steps


def _auto_skill_id(goal: str, capability: str) -> str | None:
    text = goal.lower()
    if any(k in goal for k in ("短视频素材", "一条短视频", "15秒产品", "成片包")) or (
        "短视频" in goal and any(k in goal for k in ("旁白", "配乐", "主视觉", "成片"))
    ):
        return "short-video-pack"
    if any(k in goal for k in ("口播", "配音文案", "旁白稿")) and any(k in goal for k in ("语音", "配音", "tts", "朗读")):
        return "voiceover-script"
    if any(k in goal for k in ("海报", "主视觉", "封面图")):
        return "product-poster"
    if any(k in goal for k in ("配乐", "BGM", "bgm", "背景音乐")) and capability in {"music", "chat"}:
        return "bgm-pack"
    if any(k in goal for k in ("种草", "小红书文案", "推广文案")):
        return "social-copy"
    return None


def _manual_steps(capability: str, goal: str, stage_overrides: dict[str, str | None]) -> list[dict[str, Any]]:
    """Build steps from primary capability + optional stage_overrides (ordered)."""
    order = []
    seen = set()
    primary = capability if capability in VALID_CAPABILITIES else "chat"
    for cap in [primary, *stage_overrides.keys()]:
        if cap in VALID_CAPABILITIES and cap not in seen:
            seen.add(cap)
            order.append(cap)
    if not order:
        order = ["chat"]
    steps = []
    prev = None
    for index, cap in enumerate(order):
        step_id = f"step-{index + 1}-{cap}"
        depends = [prev] if prev else []
        steps.append(
            {
                "id": step_id,
                "capability": cap,
                "title": {
                    "chat": "文本生成",
                    "image": "图片生成",
                    "tts": "语音合成",
                    "music": "音乐生成",
                    "video": "视频生成",
                }.get(cap, cap),
                "depends_on": depends,
                "prompt": goal,
            }
        )
        prev = step_id
    return steps


def estimate_cost(steps: list[dict[str, Any]], byok_capabilities: set[str] | None = None) -> float:
    byok_capabilities = byok_capabilities or set()
    total = 0.0
    for step in steps:
        cap = step["capability"]
        if cap in byok_capabilities:
            continue
        total += CAPABILITY_COST.get(cap, 0.02)
    return round(total, 3)


def build_plan(
    goal: str,
    *,
    capability: str = "chat",
    skill_id: str | None = None,
    auto_plan: bool = True,
    stage_overrides: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    stage_overrides = stage_overrides or {}
    skill = get_skill(skill_id)
    source = "manual"
    if skill:
        steps = _steps_from_skill(skill, goal)
        source = "skill"
        resolved_skill = skill["id"]
    else:
        inferred = _auto_skill_id(goal, capability) if auto_plan else None
        skill = get_skill(inferred) if inferred else None
        if skill:
            steps = _steps_from_skill(skill, goal)
            source = "auto"
            resolved_skill = skill["id"]
        else:
            steps = _manual_steps(capability, goal, stage_overrides)
            source = "manual"
            resolved_skill = None

    return {
        "id": str(uuid4()),
        "skill_id": resolved_skill,
        "source": source,
        "steps": steps,
        "estimated_cost": estimate_cost(steps),
        "goal": goal,
    }


def topological_invocation_order(invocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order invocations by depends_on (step ids). Unknown deps ignored."""
    by_step = {item.get("step_id") or item["id"]: item for item in invocations}
    remaining = dict(by_step)
    ordered: list[dict[str, Any]] = []
    safety = 0
    while remaining and safety < len(invocations) + 5:
        safety += 1
        progressed = False
        for step_id, item in list(remaining.items()):
            deps = item.get("depends_on") or []
            if all(dep not in remaining for dep in deps):
                ordered.append(item)
                del remaining[step_id]
                progressed = True
        if not progressed:
            # Cycle or missing deps — append rest in original order
            ordered.extend(remaining.values())
            break
    return ordered


def resolve_step_prompt(invocation: dict[str, Any], completed: dict[str, dict[str, Any]], goal: str) -> str:
    """Fill placeholders using prior step outputs."""
    prompt = invocation.get("prompt") or goal
    script = ""
    for step_id, inv in completed.items():
        output = inv.get("output") or {}
        if inv.get("capability") == "chat" and output.get("content"):
            script = str(output["content"])
            break
    if "{previous_script}" in prompt:
        prompt = prompt.replace("{previous_script}", script or goal)
    return prompt
