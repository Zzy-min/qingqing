# Phase 2：Planner、多步 Runtime 与 Skills

## 目标

1. 将 goal 解析为有序 **Plan**（步骤 capability、依赖、费用预估）。
2. 按依赖顺序执行 invocation；失败可 **单步 retry**。
3. 提供内置 **Skills** 创作配方；可 `skill_id` 实例化。

## Plan 结构

```json
{
  "skill_id": "short-video-pack|null",
  "source": "skill|auto|manual",
  "steps": [
    {
      "id": "step-1",
      "capability": "image",
      "title": "主视觉",
      "depends_on": [],
      "prompt": "..."
    }
  ],
  "estimated_cost": 1.65
}
```

## API

- `GET /api/v1/skills`
- `POST /api/v1/agent/plans/preview`
- `POST /api/v1/agent/runs` 支持 `skill_id` / `auto_plan`
- `POST /api/v1/agent/runs/{id}/steps/{step_id}/retry`

## 边界

- Planner 首版为规则 + 模板，不强制 LLM 规划
- 不引入 LangGraph 依赖
- 不实现完整 Comfy 节点编辑器
