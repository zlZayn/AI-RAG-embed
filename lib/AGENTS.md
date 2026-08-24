# lib/ — 规则层

继承根规则，见 [../AGENTS.md](../AGENTS.md)。

lib/ 特有约束：
- 新增模块必须在 [README.md](README.md) 文件索引登记
- 配置读取集中在 engine.py，库文件不直接读 config.json
- 日志一律走 log.py 输出到 stderr，不 print 到 stdout
- 重依赖（sentence-transformers/chromadb/openai）保持惰性导入