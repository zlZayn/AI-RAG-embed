# servers/ — 规则层

继承根规则，见 [../AGENTS.md](../AGENTS.md)。

servers/ 特有约束：
- 新工具函数先写 tools/，再在 rag_server.py 注册
- stdout 只走 MCP 协议（JSON-RPC），日志走 lib/log.py 到 stderr
- 组件初始化复用 tools/shared_store.py 缓存，不重复加载模型