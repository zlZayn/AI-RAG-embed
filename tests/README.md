# tests/ — 测试手册

- test_chunking.py：分块行为 pytest 用例，本地可跑
- test_thinking.py：联网探测 reasoning_content，需真实 API key，勿提交
- show_prompts.py：打印当前提示词模板（uv run python tests/show_prompts.py）
- batch_check_template.md：批量检索验证方法论
- 特殊坑：tests/ 整目录被 .gitignore 忽略（git 不跟踪测试）
- 变更影响路由：改分块逻辑 → 跑 test_chunking.py → 更新根 [AGENTS.md](../AGENTS.md) 快照