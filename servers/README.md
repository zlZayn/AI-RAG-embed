# servers/ — MCP 服务器手册

- 职责：把 RAG 系统暴露为 MCP 工具（stdio 传输）
- rag_server.py：FastMCP 入口，注册 rag_search/rag_ask/rag_get_info，启动时暖机
- 运行：uv run python servers/rag_server.py
- 变更影响路由：改这里 → 同步根 [AGENTS.md](../AGENTS.md) + 架构写 [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) MCP 章节
- 使用约束与工作偏好 → 见 [AGENTS.md](AGENTS.md)