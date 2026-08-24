# tools/ — MCP 工具手册

- 职责：MCP 工具实现（检索 / 问答 / 系统信息）
- shared_store.py：共享 store 缓存 + 暖机 + 过期检测；被其余工具与 rag_server.py 依赖
- rag_search.py：rag_search(question, enhance, k)，只检索不生成
- rag_ask.py：rag_ask(question, enhance, k)，检索 + LLM 生成
- rag_get_info.py：rag_get_info()，返回配置/索引文档/路径
- 变更影响路由：改这里 → 同步根 [AGENTS.md](../AGENTS.md) + 架构写 [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) MCP 章节
- 使用约束与工作偏好 → 见 [AGENTS.md](AGENTS.md)