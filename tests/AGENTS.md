# tests/ — 规则层

继承根规则，见 [../AGENTS.md](../AGENTS.md)。

tests/ 特有约束：
- 新增分块/配置行为必须在 test_chunking.py 补用例
- test_thinking.py 是联网探测脚本（含真实 API key），不纳入 pytest
- 测试数字更新后同步根 [AGENTS.md](../AGENTS.md) 验证快照