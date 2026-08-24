# tools/ — 规则层

继承根规则，见 [../AGENTS.md](../AGENTS.md)。

tools/ 特有约束：
- 工具函数签名保持 (question, enhance, k) 风格，返回 str/dict
- 共享 store 走 shared_store.py，不重复加载模型
- stdout 留给 MCP 协议，日志走 lib/log.py