# AI-RAG-embed

[English](README.md) | [简体中文](README_zh.md)

## 概述

将 `.txt`/`.md`/`.typ` 文件放入 `documents/` 目录，本地构建向量索引，然后基于你的文档内容向远程 LLM 提问获取答案。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

将 `config_example.json` 复制为 `config.json` 并填入 API Key。

```bash
# bash
cp config_example.json config.json
```

```powershell
# pwsh
Copy-Item config_example.json config.json
```

### 3. 放入文档

将 `.txt` / `.md` / `.typ` 文件放入 `documents/` 目录。首次运行会下载嵌入模型到本地缓存。

### 4. 构建索引并提问

```bash
python rag_qa.py --build    # 构建索引（增量，无变更则跳过）
python rag_qa.py            # 交互模式（一问一答循环）
```

> **注意**：代码默认使用 `hf-mirror.com` 作为 HuggingFace 镜像端点。不要将 `HF_ENDPOINT` 覆盖为 `huggingface.co`——会导致连接超时。

### CLI 速查

```bash
python rag_qa.py --build              # 构建索引（增量，无变更则跳过）
python rag_qa.py --rebuild            # 强制重建索引
python rag_qa.py --search "问题"      # 仅检索，不生成答案
python rag_qa.py "问题"               # 单次问答
python rag_qa.py                      # 交互模式
python rag_qa.py --help               # 查看所有参数说明
```

### MCP 服务器

将 RAG 系统暴露为 MCP 工具，供 Agent 框架（Claude Code 等）集成使用。

```bash
python servers/rag_server.py          # stdio 传输（供 Agent 连接）
```

注册的工具：

| 工具 | 说明 | 参数 |
| --- | --- | --- |
| `rag_search` | 检索相关片段，不生成答案 | `question`（必填）、`enhance`、`k` |
| `rag_ask` | 检索 + LLM 生成答案 | `question`（必填）、`enhance`、`k` |
| `rag_get_info` | 获取 RAG 系统配置、已索引文档和路径 | （无） |

`enhance` 启用查询增强（等同于 CLI 的 `--enhance`）。`k` 覆盖检索数量（默认取配置值）。在 Agent 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "rag-qa": {
      "type": "stdio",
      "command": "mcp",
      "args": ["run", "D:\\path\\to\\AI-RAG-embed\\servers\\rag_server.py", "-t", "stdio"],
      "env": {}
    }
  }
}
```

## 使用方法

### 构建索引

```bash
python rag_qa.py --build    # 增量构建：无文件变更时跳过
python rag_qa.py --rebuild  # 强制重新嵌入
```

`--build` 检测文件内容变更和嵌入模型变更。在 `config.json` 中切换模型会自动触发全量重建，无需手动 `--rebuild`。

### 交互模式

支持多轮对话，保留历史记录。

```bash
python rag_qa.py
```

```text
Ask a question. Be specific. /quit or /q to quit.

>>> 什么是指数平滑？
指数平滑是一种预测方法……

>>> 有几种类型？
系统理解"类型"指的是上一轮讨论中的指数平滑类型。

>>> /quit
```

### 单次提问模式

一次性提问，结果保存到 `output/` 目录。

```bash
python rag_qa.py "什么是指数平滑？"

# 开启查询增强（检索优化改写后再搜索）
python rag_qa.py --enhance "什么是指数平滑？"
```

可用 `--retrieval_k`、`--retrieval_distance_threshold`、`--strict_context`、`--debug` 临时覆盖配置。`--debug` 会输出查询参数、查询路径、问题改写、逐 chunk 分数和来源预览。

### 仅检索模式

检索相关文档片段，不生成答案。

```bash
python rag_qa.py --search "什么是指数平滑？"

# 使用查询增强（检索优化改写后再搜索）
python rag_qa.py --search --enhance "什么是指数平滑？"
```

返回排名前 `retrieval_k` 个片段（默认 3 个）直接输出到标准输出。使用 `--enhance` 时，查询会先经过增强器处理再进行检索，逻辑与问答模式相同。参见[查询增强](#查询增强)了解模式差异。

### 查询技巧

增强器会改写查询以获得更好的向量相似度，但它无法检索文档中不存在的内容。

- 在知识库的领域范围内提问，使用文档中出现的术语。
- 提供足够的上下文以消除歧义。"预测区间太窄"是模糊的；"ARIMA 预测区间太窄"则不是。
- 本地模式仅做翻译，因此提问的措辞比 LLM 模式更关键。

## 配置说明

编辑 `config.json` 配置系统。相对路径（`./`）以项目根目录为基准。下面的"默认值"指代码中的硬编码回退值（当配置项省略时）。

### 模型槽位

系统有 3 个本地模型槽位和 1 个远程 LLM 槽位。每个本地槽位由各自的配置项控制开关——未启用的模型不会加载。

| 槽位 | 配置项 | 类型 | 用途 |
| --- | --- | --- | --- |
| 嵌入模型 | `vector_enabled` | 本地 | 将文档和查询向量化，用于相似度检索 |
| 增强器 | `query_enhance_enabled` | 本地或远程 | 检索前改写或翻译查询 |
| 精排器 | `reranker_enabled` | 本地 | 用 cross-encoder 对检索结果重新打分 |
| LLM | 始终启用 | 远程 (API) | 生成最终答案 |

增强器在本地模式下加载 MarianMT 模型，在 LLM 模式下调用远程 API（与 LLM 槽位共享）。三个本地槽位可同时启用。纯 BM25 配置不加载任何本地模型。

### 文档与索引

| 配置项 | 说明 |
| --- | --- |
| `docs_dir` | 存放文档文件的目录（含子目录）。使用 `.doc_loader_ignore` 排除文件（`.gitignore` 语法）。 |
| `docs_lang` | 文档语言（`"en"`、`"zh"` 等）。控制嵌入模型的选择和查询前缀的使用。 |
| `chunking` | 分块配置对象，包含 `mode` 及模式专属子项，详见下方。 |
| `embedding_model_name` | 嵌入模型配置。支持字符串（单模型）或对象（按 `docs_lang` 映射模型 ID），详见下方。 |
| `chroma_persist_dir` | 向量数据库的保存目录。 |

**`embedding_model_name`** 支持两种格式：

```json
// 单模型：所有语言共用
"embedding_model_name": "BAAI/bge-small-zh-v1.5"

// 按语言映射：根据 docs_lang 自动选择
"embedding_model_name": {
    "zh": "BAAI/bge-small-zh-v1.5",
    "en": "mixedbread-ai/mxbai-embed-large-v1"
}
```

使用按语言映射格式时，修改 `docs_lang` 会自动切换模型和查询前缀。模型维度变化会被自动处理——`--build` 检测到切换后会从头重建索引。首次运行自动下载模型到本地缓存：`bge-small-zh-v1.5` 约 92MB，`mxbai-embed-large-v1` 约 641MB。

### 分块配置（`chunking`）

控制文档如何切分为片段以进行嵌入。

| 配置项 | 说明 |
| --- | --- |
| `mode` | `"auto"`（默认）= 智能分块。`"fixed"` = 固定长度 + 分隔符回退。 |

**auto 模式**（`chunking.auto`）：`.md` 和 `.typ` 文件按标题层级智能分块（`.typ` 文件会识别标题、表格、引用块，跳过前置配置和注释）。`.txt` 文件按段落优先分块。代码块和表格不会被切断。

| 配置项 | 说明 |
| --- | --- |
| `target_chars` | 目标片段大小。atomic 单元（代码块、表格）可能超过此值。默认值：`700`。 |
| `split_at_level` | 在几级标题处切分（1-6）。`2` = 在 `#` 和 `##` 处切分。默认值：`3`。 |
| `min_chars` | 最小字符数，低于此值的片段会被丢弃。默认值：`100`。 |
| `include_heading` | 在每个片段开头附加所属标题（`> 标题`）。默认值：`false`。 |

**fixed 模式**（`chunking.fixed`）：由 `split_by` 控制两种子模式：

- `"char"`（默认）：在 `max_chars` 处切分（硬上限，绝不超出），按优先级回退到最近的分隔符（`\n\n` > `\n` > 标点 > 空格）。`overlap_chars` 控制相邻片段重叠字符数。
- `"line"`：按行数切分（`max_lines`），保留完整行边界不截断。优先在空行（段落边界）处切分。`overlap_lines` 控制相邻片段重叠行数。

| 配置项 | 说明 |
| --- | --- |
| `split_by` | `"char"`（默认）= 按字符数切分。`"line"` = 按行数切分。 |
| `char.max_chars` | 单个片段硬上限字符数（char 模式）。默认值：`700`。 |
| `char.overlap_chars` | 相邻片段重叠字符数（char 模式）。默认值：`70`。 |
| `line.max_lines` | 单个片段最大行数（line 模式）。默认值：`20`。 |
| `line.overlap_lines` | 相邻片段重叠行数（line 模式）。建议小于 `max_lines // 2` 以保证断点质量。默认值：`3`。 |

### 查询增强

在搜索前改写问题以提高检索质量。增强后的输出**仅用于检索**——答案 LLM 始终接收原始问题。

| 配置项 | 说明 |
| --- | --- |
| `query_enhance_enabled` | 启用查询增强。默认值：`false`。 |

增强器配置在 `retrieval.enhancer` 下，详见检索与精排章节。

### 检索与精排

| 配置项 | 说明 |
| --- | --- |
| `retrieval.mode` | 检索策略：`"llm"` = LLM 生成检索优化段落。`"local"` = MarianMT 翻译。`null` = 直接检索（不增强）。 |
| `retrieval.k` | 每次查询检索的片段数。默认值：`3`。 |
| `retrieval.distance_threshold` | 向量检索的余弦距离阈值，超过此值的 chunk 被过滤。仅 `vector_enabled=true` 时生效。设为 `null` 禁用过滤。默认值：`0.3`。 |
| `vector_enabled` | 启用向量（embedding）检索。设为 `false` 时不加载 embedding 模型，启动更快、内存更省。默认值：`true`。 |
| `bm25_enabled` | 启用 BM25 关键词检索。可单独使用，也可与向量检索组合；组合时结果通过 RRF（Reciprocal Rank Fusion）融合排序。默认值：`false`。 |

**LLM 模式**（`retrieval.enhancer.llm`）：生成密集检索段落，涵盖关键术语、相关概念和可能的文档内容。对于后续问题，先使用对话历史进行改写。

| 配置项 | 说明 |
| --- | --- |
| `api_base_url`、`api_key`、`model` | LLM API 连接设置。 |
| `temperature` | 默认值：`0.0`。 |
| `thinking_mode` | 默认值：`false`。 |

**本地模式**（`retrieval.enhancer.local`）：通过 MarianMT 将问题翻译为 `docs_lang` 语言。不替换术语，不改写上下文。

| 配置项 | 说明 |
| --- | --- |
| `query_lang` | 你提问使用的语言（如 `"zh"`、`"en"`）。 |
| `model_name` | HuggingFace 模型 ID（可选）。省略时自动选择 `Helsinki-NLP/opus-mt-{query_lang}-{docs_lang}`（zh-en 约 599MB，en-zh 约 301MB）。 |

`vector_enabled` 和 `bm25_enabled` 至少启用一种。四种组合：

| `vector_enabled` | `bm25_enabled` | 行为 |
| --- | --- | --- |
| `true` | `true` | 混合检索：向量 + BM25，RRF 融合排序 |
| `true` | `false` | 纯向量检索 |
| `false` | `true` | 纯 BM25 检索（不加载 embedding 模型） |
| `false` | `false` | 报错：至少启用一种 |

**精排重排序**（可选）：两阶段检索——先用 `retrieval_k * 4` 条候选粗筛（无论向量还是 BM25），再用 cross-encoder 对每条候选与查询的联合语义打分，取前 `retrieval_k` 条送入 LLM。适合术语匹配不精确、语义相关性要求高的场景。

| 配置项 | 说明 |
| --- | --- |
| `reranker_enabled` | 启用 cross-encoder 精排。默认值：`false`。 |
| `reranker.model_name` | cross-encoder 模型 ID。默认值：`"BAAI/bge-reranker-v2-m3"`。 |
| `reranker.top_k` | 精排后的片段数。默认值：`null`（使用 `retrieval_k`）。 |

> **首次加载**：启动时下载模型（约 2.2GB）到本地 HuggingFace 缓存，之后直接读缓存。**每轮查询耗时**：cross-encoder 打分阶段约增加 1-2s（CPU），80 条候选约 1.8s，候选数越多耗时线性增长。

### 答案生成（`llm`）

使用检索到的片段生成最终答案的 LLM。配置项：`api_base_url`、`api_key`、`model`、`temperature`（默认值：`0.3`）、`thinking_mode`。

### 对话行为

| 配置项 | 说明 |
| --- | --- |
| `max_history_rounds` | 保留的最近对话轮数，用于上下文。默认值：`10`。 |
| `strict_context` | `true` = **仅**基于检索到的片段回答。`false` = LLM 可补充自身知识。默认值：`false`。 |

**系统提示词定制：** 要自定义系统提示词，请直接编辑 `lib/prompt_templates.py`。

## 文档过滤

在 `documents/` 的任意子目录下放置 `.doc_loader_ignore` 文件。使用 `.gitignore` 语法。规则适用于所在目录及所有子目录。

```text
# documents/.doc_loader_ignore
r4ds_textbook/
fpp3_textbook/
```

```text
# documents/fpp3_textbook/.doc_loader_ignore
README.md
*.log
_draft/
```

## 输出

对话日志以编号 Markdown 文件保存到 `output/<session>/` 目录。

```text
output/
└── What_is_exponential_smoothing_20260519_173334/
    ├── 01_round.md
    └── 02_round.md
```

每轮文件包含问题、答案、处理后的问题（LLM 模式标记为"Enhanced Question"，本地模式标记为"Translated Question"）以及使用的检索片段。

## 项目结构

```text
rag_qa.py               # 入口（--build | --rebuild | --search | 问题 | 交互）
config.json             # 你的配置（已 gitignore）
config_example.json     # 配置模板
documents/              # 存放 .txt / .md / .typ 文件
chroma_db/              # 持久化向量数据库（生成）
output/                 # 对话导出（生成）
servers/
└── rag_server.py       # MCP 服务器入口（stdio 传输）
tools/
├── __init__.py         # _mcp_safe() 上下文管理器
├── rag_search.py       # MCP 工具：仅检索片段
├── rag_ask.py          # MCP 工具：检索 + LLM 生成答案
└── rag_get_info.py     # MCP 工具：系统配置与已索引文档
lib/
├── doc_loader.py       # 文件读取 + 文本分片 + 忽略规则
├── embed_engine.py     # 嵌入模型封装（sentence-transformers）
├── vector_db.py        # Chroma 向量存储 + 混合检索
├── bm25_retriever.py   # BM25 关键词检索器（jieba + rank-bm25）
├── llm_api.py          # 远程 LLM API 客户端（OpenAI 兼容）
├── query_enhancer.py   # 查询增强（检索优化改写）
├── local_translator.py # MarianMT 本地翻译后端
└── reranker.py         # cross-encoder 精排重排序
```

## 依赖要求

### Python 依赖

- Python 3.10+
- `sentence-transformers`、`chromadb`、`openai`、`pathspec`（核心依赖）
- `jieba`、`rank-bm25`（BM25 混合检索）
- `transformers`、`sentencepiece`、`sacremoses`（仅 `mode: "local"` 需要）

### GPU 配置（可选）

1. 检查是否有 NVIDIA GPU 和驱动：`nvidia-smi`
2. 安装支持 CUDA 的 PyTorch（默认 `pip install torch` 仅支持 CPU）：

   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cu121
   ```

3. 验证：`python -c "import torch; print(torch.cuda.is_available())"` -- 应输出 `True`

没有 GPU 时一切照常运行，但**速度会慢很多**。

### 模型缓存

所有本地模型首次运行自动下载到 `~/.cache/huggingface/hub/`，之后直接读缓存。查看已缓存模型及大小：

```bash
# bash
du -sh ~/.cache/huggingface/hub/models--* | awk '{sub(/.*models--/, "", $2); sub(/--/, "/", $2); print $2": "$1}'
```

```powershell
# pwsh
Get-ChildItem "$env:USERPROFILE\.cache\huggingface\hub\models--*" -Directory | ForEach-Object { $name = $_.Name -replace 'models--', '' -replace '--', '/'; $size = (Get-ChildItem $_.FullName -Recurse -File | Measure-Object -Property Length -Sum).Sum; "$name`: $([math]::Round($size/1MB)) MB" }
```

---

详见 [ARCHITECTURE.md](ARCHITECTURE.md) 了解构建/查询工作流、模块内部实现和环境配置（`sentence-transformers` 版本）。
