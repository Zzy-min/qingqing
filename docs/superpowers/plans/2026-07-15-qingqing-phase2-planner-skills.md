# Phase 2 实施计划

1. 新增 `skills.py`、`planner.py`。
2. 改造 `create_run` 写入 `plan` 与带 `step_id/depends_on/prompt` 的 invocations。
3. `execution.py` 拓扑排序执行，步骤 prompt 注入 goal。
4. 增加 skills / plan preview / step retry 路由。
5. 前端 Composer：技能选择 + 计划步骤展示 + 进度。
6. 测试覆盖多步 skill、preview、retry。
