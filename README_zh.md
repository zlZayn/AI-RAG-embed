# AI-RAG-embed

[English](README.md) | [简体中文](README_zh.md)

## 概述

将 `.txt/.md` 文件放入 `documents/` 目录，本地构建向量索引，然后基于你的文档内容向远程 LLM 提问获取答案。

## 快速开始

```bash
pip install -r requirements.txt

# 1. 将 config_example.json 复制为 config.json 并填入 API Key
cp config_example.json config.json

# 2. 将 .txt / .md 文件放入 documents/ 目录

# 3. 构建向量索引（首次运行会下载约 641MB 的嵌入模型）
python rag_qa.py --build

# 4. 提问（交互模式）
python rag_qa.py
```

> **注意**：代码默认使用 `hf-mirror.com` 作为 HuggingFace 镜像端点。不要将 `HF_ENDPOINT` 覆盖为 `huggingface.co`——会导致连接超时。

## 使用方法

### 构建索引

```bash
python rag_qa.py --build    # 增量构建：无文件变更时跳过
python rag_qa.py --rebuild  # 强制重新嵌入
```

`--build` 仅检测文件内容变更。如果修改了 `config.json` 中的 `chunk_size`、`chunk_overlap` 或 `embedding_model_name`，需要使用 `--rebuild` 重新嵌入所有内容。

### 交互模式

支持多轮对话，保留历史记录。

```bash
python rag_qa.py
```

```text
>>> 什么是指数平滑？
指数平滑是一种预测方法……

>>> 有几种类型？
系统理解"类型"指的是上一轮讨论中的指数平滑类型。

>>> /exit
```

### 单次提问模式

一次性提问，结果保存到 `output/` 目录。

```bash
python rag_qa.py "什么是指数平滑？"
```

### 仅检索模式

检索相关文档片段，不生成答案。

```bash
python rag_qa.py --search "什么是指数平滑？"

# 使用查询增强（检索优化改写后再搜索）
python rag_qa.py --search --enhance "什么是指数平滑？"
```

返回排名前 `retrieval_k` 个片段（默认 3 个）直接输出到标准输出。使用 `--enhance` 时，查询会先经过增强器处理再进行检索，与 `cmd_ask` 相同。参见[查询增强](#查询增强-enhancer)了解模式差异。

### 命令行覆盖

部分配置字段可通过命令行参数覆盖。省略时回退到 `config.json`，再回退到代码默认值。

```bash
python rag_qa.py --retrieval_k 10 --retrieval_distance_threshold 0.25 --strict_context true "你的问题"

python rag_qa.py --search --enhance --retrieval_k 3 --retrieval_distance_threshold 0.15 "你的问题"
```

支持的参数：`--retrieval_k`、`--retrieval_distance_threshold`、`--strict_context`。适用于所有模式（ask、chat、search）。

### 查询技巧

增强器会改写查询以获得更好的向量相似度，但它无法检索文档中不存在的内容。

- 在知识库的领域范围内提问，使用文档中出现的术语。
- 提供足够的上下文以消除歧义。"预测区间太窄"是模糊的；"ARIMA 预测区间太窄"则不是。
- 本地模式仅做翻译，因此提问的措辞比 LLM 模式更关键。

## 配置说明

编辑 `config.json` 配置系统。相对路径（`./`）以项目根目录为基准。下面的"默认值"指代码中的硬编码回退值（当配置项省略时）。

### 文档与索引

| 配置项 | 说明 |
| --- | --- |
| `docs_dir` | 存放 `.txt` / `.md` 文件的目录（含子目录）。使用 `.doc_loader_ignore` 排除文件（`.gitignore` 语法）。 |
| `docs_lang` | 文档语言（如 `"en"`、`"zh"`）。增强器会生成此语言的输出用于检索。 |
| `chunk_size` | 每个片段的目标字符数。越大上下文越多，但检索精度越低。典型范围：300-1000。 |
| `chunk_overlap` | 相邻片段的重叠字符数。建议值：`chunk_size` 的 10-20%。 |
| `embedding_model_name` | HuggingFace 模型 ID，用于向量嵌入。详见下方说明。 |
| `chroma_persist_dir` | 向量数据库的保存目录。 |

> **切换模型**：代码有针对特定模型的默认值，可能需要手动调整：
>
> - **嵌入模型**：mxbai 模型系列硬编码了查询前缀。其他模型（如 `all-MiniLM-L6-v2`）不使用此前缀——保留会影响检索效果。查看 `lib/embed_engine.py` 中的 `_QUERY_PREFIX`。
> - **翻译模型**：本地增强器自动选择 `Helsinki-NLP/opus-mt-{query_lang}-{docs_lang}`。要使用其他模型系列，请在 `config.json` 中显式设置 `model_name`。
> - **HuggingFace 镜像**：`hf-mirror.com` 为中国用户设置为默认端点。如果你能直接访问 HuggingFace，请移除或覆盖 `HF_ENDPOINT`。

### 检索配置

| 配置项 | 说明 |
| --- | --- |
| `retrieval_k` | 每次查询检索的片段数。默认值：`3`。 |
| `retrieval_distance_threshold` | 全局余弦距离阈值回退值。启用增强时，会被增强器配置中各模式的 `distance_threshold` 覆盖。设为 `null` 禁用过滤。默认值：`0.3`。 |

### 查询增强（`enhancer`）

在搜索前改写问题以提高检索质量。增强后的输出**仅用于检索**——答案 LLM 始终接收原始问题。

| 配置项 | 说明 |
| --- | --- |
| `query_enhance_enabled` | 启用查询增强。默认值：`false`。 |
| `mode` | `"llm"` = 使用 LLM API 生成检索优化段落。`"local"` = 使用本地 MarianMT 模型（离线，仅翻译）。 |

**LLM 模式**（`enhancer.llm`）：生成密集检索段落，涵盖关键术语、相关概念和可能的文档内容。对于后续问题，先使用对话历史进行改写。

| 配置项 | 说明 |
| --- | --- |
| `api_base_url`、`api_key`、`model` | LLM API 连接设置。 |
| `temperature` | 默认值：`0.0`。 |
| `thinking_mode` | 默认值：`false`。 |
| `distance_threshold` | 此模式的余弦距离阈值。默认值：`0.2`。 |

**本地模式**（`enhancer.local`）：通过 MarianMT 将问题翻译为 `docs_lang` 语言。不替换术语，不改写上下文。

| 配置项 | 说明 |
| --- | --- |
| `query_lang` | 你提问使用的语言（如 `"zh"`、`"en"`）。 |
| `model_name` | HuggingFace 模型 ID（可选）。省略时自动选择 `Helsinki-NLP/opus-mt-{query_lang}-{docs_lang}`。 |
| `distance_threshold` | 此模式的余弦距离阈值。默认值：`0.3`。 |

### 答案生成（`llm`）

使用检索到的片段生成最终答案的 LLM。配置项：`api_base_url`、`api_key`、`model`、`temperature`（默认值：`0.3`）、`thinking_mode`。

### 对话行为

| 配置项 | 说明 |
| --- | --- |
| `max_history_rounds` | 保留的最近对话轮数，用于上下文。默认值：`10`。 |
| `strict_context` | `true` = **仅**基于检索到的片段回答。`false` = LLM 可补充自身知识。默认值：`false`。 |
| `system_rules` | 附加到系统提示词的额外指令。默认值：`""`。 |

## 文档过滤

在 `documents/` 的任意子目录下放置 `.doc_loader_ignore` 文件。使用 `.gitignore` 语法。规则适用于所在目录及所有子目录。

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
documents/              # 存放 .txt / .md 文件
chroma_db/              # 持久化向量数据库（生成）
output/                 # 对话导出（生成）
lib/
├── doc_loader.py       # 文件读取 + 文本分片 + 忽略规则
├── embed_engine.py     # 嵌入模型封装（sentence-transformers）
├── vector_db.py        # Chroma 向量存储操作
├── llm_api.py          # 远程 LLM API 客户端（OpenAI 兼容）
├── query_enhancer.py   # 查询增强（检索优化改写）
└── local_translator.py # MarianMT 本地翻译后端
```

## 依赖要求

### Python 依赖

- Python 3.10+
- `sentence-transformers`、`chromadb`、`openai`、`pathspec`（核心依赖）
- `transformers`、`sentencepiece`、`sacremoses`（仅 `mode: "local"` 需要）

### GPU 配置（可选）

1. 检查是否有 NVIDIA GPU 和驱动：`nvidia-smi`
2. 安装支持 CUDA 的 PyTorch（默认 `pip install torch` 仅支持 CPU）：

   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cu121
   ```

3. 验证：`python -c "import torch; print(torch.cuda.is_available())"` -- 应输出 `True`

没有 GPU 时一切照常运行，但**速度会慢很多**。

---

详见 `ARCHITECTURE.md` 了解构建/查询工作流、模块内部实现和环境配置（`sentence-transformers` 版本）。
