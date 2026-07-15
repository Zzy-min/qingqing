# 轻青项目身份重命名实施计划

1. 更新 README / SPEC / package.json / package-lock / FastAPI title / 启动脚本中的项目路径与身份文案。
2. 将临时 TTS 目录前缀改为 `qingqing`。
3. 历史 docs 中的绝对路径改为新根目录（或相对表述）。
4. `gh repo rename qingqing` 并 `git remote set-url`。
5. 将本地目录 `minimax-photo-agent` 重命名为 `qingqing`。
6. 在新路径下跑后端 pytest 与前端 vitest 做冒烟验证。
