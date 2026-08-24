# lib/ — 核心库手册

- 职责：分块、嵌入、检索、增强、生成；共享初始化
- engine.py：配置加载 + 惰性初始化（load_config/init_store/init_enhancer/init_llm/init_reranker）；被 rag_qa.py、tools/ 依赖；改后跑 tests/test_chunking.py
- doc_loader.py：文档读取 + 分块 + 忽略规则（.doc_loader_ignore）；被 rag_qa.py、tools/ 依赖；改后必跑 tests/test_chunking.py
- embed_engine.py：嵌入模型封装（SentenceTransformer + 查询前缀）
- vector_db.py：Chroma 存储 + 混合检索（RRF 融合）
- bm25_retriever.py：BM25 检索器（jieba + rank-bm25）
- llm_api.py：OpenAI 客户端封装（流式生成）
- query_enhancer.py：查询增强（LLM 改写 / 本地翻译路由）
- local_translator.py：MarianMT 本地翻译
- reranker.py：cross-encoder 精排
- prompt_templates.py：系统提示词 + 消息组装
- log.py：统一日志（stderr），全项目使用
- 变更影响路由：改这里 → 同步根 [AGENTS.md](../AGENTS.md) 快照/坑 + 架构影响写 [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
- 使用约束与工作偏好 → 见 [AGENTS.md](AGENTS.md)