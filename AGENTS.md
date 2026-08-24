# AI-RAG-embed — 维护索引

## 全局规则
- 架构：见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 双件分离：AGENTS.md 只写规则，README.md 只写是什么/怎么改
- 输出铁律：一句话一个物理行、子弹列表、禁长段落
- 决策记录 → [.agents/notes/](.agents/notes/)

## 常用命令
- uv run python rag_qa.py --help
- uv run python web.py（网页入口，http://localhost:5000）
- uv run pytest tests/test_chunking.py -v

## 验证快照（2026-08-24）
- pytest tests/test_chunking.py: 42 passed / 0 failed
- 其余测试未跑：thinking_probe.py 为联网探测脚本（凭据走 OPENAI_API_KEY 环境变量）

## 待办
- [ ] 无

## 活跃坑
- HF 端点默认 hf-mirror.com，勿覆盖为 huggingface.co
- documents/ 教科书 math 会被 check-links 误报为断链
- docs/ 与 tests/ 已放开 gitignore 跟踪（2026-08-24）

## 文档地图
- 架构 → docs/ARCHITECTURE.md
- lib → lib/README.md · servers → servers/README.md
- tools → tools/README.md · tests → tests/README.md