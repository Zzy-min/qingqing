"""Built-in creative workflow skills (templates)."""

from __future__ import annotations

from typing import Any


SKILLS: dict[str, dict[str, Any]] = {
    "product-poster": {
        "id": "product-poster",
        "name": "产品海报",
        "description": "一句话生成产品主视觉海报图。",
        "capabilities": ["image"],
        "steps": [
            {
                "id": "poster",
                "capability": "image",
                "title": "主视觉海报",
                "depends_on": [],
                "prompt_template": "商业产品海报主视觉，高质量，干净构图：{goal}",
            }
        ],
    },
    "voiceover-script": {
        "id": "voiceover-script",
        "name": "口播文案+配音",
        "description": "先写口播稿，再合成语音。",
        "capabilities": ["chat", "tts"],
        "steps": [
            {
                "id": "script",
                "capability": "chat",
                "title": "撰写口播稿",
                "depends_on": [],
                "prompt_template": "为以下主题写一段 60 秒口播文案，口语化、有节奏，只输出正文：{goal}",
            },
            {
                "id": "voice",
                "capability": "tts",
                "title": "合成旁白",
                "depends_on": ["script"],
                "prompt_template": "{previous_script}",
            },
        ],
    },
    "bgm-pack": {
        "id": "bgm-pack",
        "name": "短视频配乐",
        "description": "按情绪与风格生成 BGM。",
        "capabilities": ["music"],
        "steps": [
            {
                "id": "bgm",
                "capability": "music",
                "title": "生成配乐",
                "depends_on": [],
                "prompt_template": "短视频背景音乐，完整可循环：{goal}",
            }
        ],
    },
    "short-video-pack": {
        "id": "short-video-pack",
        "name": "短视频素材包",
        "description": "主视觉 + 旁白 + 配乐 + 视频，适合 15 秒产品介绍。",
        "capabilities": ["image", "tts", "music", "video"],
        "steps": [
            {
                "id": "visual",
                "capability": "image",
                "title": "主视觉",
                "depends_on": [],
                "prompt_template": "适合短视频封面的产品主视觉：{goal}",
            },
            {
                "id": "narration",
                "capability": "tts",
                "title": "旁白",
                "depends_on": [],
                "prompt_template": "用清晰普通话旁白介绍：{goal}",
            },
            {
                "id": "score",
                "capability": "music",
                "title": "配乐",
                "depends_on": [],
                "prompt_template": "轻快现代短视频 BGM，约 15 秒，匹配：{goal}",
            },
            {
                "id": "clip",
                "capability": "video",
                "title": "成片",
                "depends_on": ["visual", "narration", "score"],
                "prompt_template": "15 秒竖版产品介绍短视频，镜头推进，主题：{goal}",
            },
        ],
    },
    "social-copy": {
        "id": "social-copy",
        "name": "种草文案",
        "description": "生成社交媒体种草文案。",
        "capabilities": ["chat"],
        "steps": [
            {
                "id": "copy",
                "capability": "chat",
                "title": "撰写文案",
                "depends_on": [],
                "prompt_template": "写一条适合小红书/微博的种草文案，含标题与正文，主题：{goal}",
            }
        ],
    },
}


def list_skills() -> list[dict[str, Any]]:
    return [
        {
            "id": skill["id"],
            "name": skill["name"],
            "description": skill["description"],
            "capabilities": list(skill["capabilities"]),
            "step_count": len(skill["steps"]),
            "steps": [
                {
                    "id": step["id"],
                    "capability": step["capability"],
                    "title": step["title"],
                    "depends_on": list(step.get("depends_on") or []),
                }
                for step in skill["steps"]
            ],
        }
        for skill in SKILLS.values()
    ]


def get_skill(skill_id: str | None) -> dict[str, Any] | None:
    if not skill_id:
        return None
    return SKILLS.get(skill_id)
