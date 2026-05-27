# AI-RAG-embed

[English](README.md) | [简体中文](README_zh.md)

## Overview

Drop your `.txt`/`.md`/`.typ` files into `documents/`, embed them locally to build the index, then ask questions and get answers from a remote LLM based on your content.

## Quick Start

```bash
pip install -r requirements.txt

# 1. Copy config_example.json to config.json and fill in your API key
cp config_example.json config.json

# 2. Put your .txt / .md / .typ files in documents/

# 3. Build the vector index (downloads embedding model on first run)
python rag_qa.py --build

# 4. Ask a question
python rag_qa.py        # interactive mode (multi-turn)
```

> **Note**: The code uses `hf-mirror.com` as the default HuggingFace endpoint. Do not override `HF_ENDPOINT` with `huggingface.co` -- it will cause connection timeouts.

### CLI Quick Reference

```bash
python rag_qa.py --build              # build index (incremental)
python rag_qa.py --rebuild            # force rebuild index
python rag_qa.py --search "question"  # retrieve only, no answer
python rag_qa.py "question"           # single question
python rag_qa.py                      # interactive mode
python rag_qa.py --help               # show all commands and options
```

## Usage

### Build Index

```bash
python rag_qa.py --build    # incremental: skip if no files changed
python rag_qa.py --rebuild  # force full re-embed
```

`--build` detects file content changes and embedding model changes. Switching models in `config.json` triggers an automatic full rebuild -- no manual `--rebuild` needed.

### Interactive Mode

Multi-turn conversation with history.

```bash
python rag_qa.py
```

```text
Ask a question. Be specific. /quit or /q to quit.

>>> What is exponential smoothing?
Exponential smoothing is a forecasting method...

>>> How many types are there?
The system understands "types" refers to exponential smoothing types from our previous discussion.

>>> /quit
```

### Single-Question Mode

One-shot, saves result to `output/`.

```bash
python rag_qa.py "What is exponential smoothing?"

# With query enhancement (retrieval-optimized rewriting before searching)
python rag_qa.py --enhance "What is exponential smoothing?"
```

Use `--retrieval_k`, `--retrieval_distance_threshold`, `--strict_context` to override config.json settings temporarily.

### Search-Only Mode

Retrieve relevant document chunks without generating an answer.

```bash
python rag_qa.py --search "What is exponential smoothing?"

# With query enhancement (retrieval-optimized rewriting before searching)
python rag_qa.py --search --enhance "What is exponential smoothing?"
```

Returns the top `retrieval_k` chunks (default: 3) directly to stdout. With `--enhance`, the query is processed through the enhancer before retrieval, same as `cmd_ask`. See [Query Enhancement](#query-enhancement-enhancer) for mode differences.

### Query Tips

The enhancer rewrites queries for better vector similarity, but it cannot retrieve what the documents do not contain.

- Stay within the knowledge base's domain and use terms that appear in the documents.
- Provide enough context to disambiguate. "Prediction intervals are too narrow" is ambiguous; "ARIMA prediction intervals are too narrow" is not.
- Local mode only translates, so how you phrase the question matters more than in LLM mode.

## Configuration

Edit `config.json` to configure the system. Relative paths (`./`) are resolved against the project root. "Default" below refers to the code's hardcoded fallback when a key is omitted.

### Document & Indexing

| Key | Description |
| --- | --- |
| `docs_dir` | Folder containing your document files (including subfolders). Use `.doc_loader_ignore` to exclude files (`.gitignore` syntax). |
| `docs_lang` | Language of your documents (`"en"`, `"zh"`, etc.). Controls which embedding model is selected and which query prefix is used. |
| `chunking` | Chunking config object. Mode-specific keys are listed below. |
| `embedding_model_name` | Embedding model config. Can be a string (single model) or an object mapping `docs_lang` values to model IDs. See below. |
| `chroma_persist_dir` | Folder where the vector database is saved. |

**`embedding_model_name`** accepts two formats:

```json
// Simple: one model for all languages
"embedding_model_name": "BAAI/bge-small-zh-v1.5"

// Per-language: auto-selected based on docs_lang
"embedding_model_name": {
    "zh": "BAAI/bge-small-zh-v1.5",
    "en": "mixedbread-ai/mxbai-embed-large-v1"
}
```

When using the per-language format, changing `docs_lang` automatically switches the model and query prefix. Model dimension changes are handled automatically -- `--build` detects the switch and rebuilds the index from scratch.

### Chunking (`chunking`)

Controls how documents are split into chunks for embedding.

| Key | Description |
| --- | --- |
| `mode` | `"auto"` (default) = smart splitting. `"fixed"` = fixed-length with separator fallback. |

**Auto mode** (`chunking.auto`): Heading-aware for `.md` and `.typ` files (headings, tables, code blocks are detected; preamble and comments are skipped for `.typ`). Paragraph-first for `.txt` files. Code blocks and tables are never split.

| Key | Description |
| --- | --- |
| `target_chars` | Target chunk size. Atomic units (code blocks, tables) may exceed this. Default: `700`. |
| `split_at_level` | Heading level to split at (1-6). `2` = split at `#` and `##`. Default: `3`. |
| `min_chars` | Minimum characters per chunk. Shorter sections are dropped. Default: `100`. |
| `include_heading` | Prepend section heading to each chunk (as `> heading`). Default: `false`. |

**Fixed mode** (`chunking.fixed`): Two sub-modes controlled by `split_by`:

- `"char"` (default): splits at `max_chars` (hard ceiling), falling back to the best separator by priority (`\n\n` > `\n` > punctuation > space). `overlap_chars` controls adjacent chunk overlap.
- `"line"`: splits by line count (`max_lines`), preserving complete line boundaries. Prefers blank lines (paragraph breaks) as split points. `overlap_lines` controls adjacent chunk overlap.

| Key | Description |
| --- | --- |
| `split_by` | `"char"` (default) = split by character count. `"line"` = split by line count. |
| `char.max_chars` | Hard limit per chunk (char mode). Default: `700`. |
| `char.overlap_chars` | Overlap between adjacent chunks (char mode). Default: `70`. |
| `line.max_lines` | Max lines per chunk (line mode). Default: `20`. |
| `line.overlap_lines` | Overlap in lines between adjacent chunks (line mode). Default: `3`. |

### Query Enhancement (`enhancer`)

Rewrites your question before searching to improve retrieval quality. The enhanced output is used **only for retrieval** -- the answer LLM always receives the original question.

| Key | Description |
| --- | --- |
| `query_enhance_enabled` | Enable query enhancement. Default: `false`. |
| `mode` | `"llm"` = use an LLM API to generate retrieval-optimized paragraphs. `"local"` = use a local MarianMT model (offline, translation only). |

**LLM mode** (`enhancer.llm`): Generates a dense retrieval paragraph covering key terms, related concepts, and likely document content. For follow-up questions, rewrites using conversation history first.

| Key | Description |
| --- | --- |
| `api_base_url`, `api_key`, `model` | LLM API connection settings. |
| `temperature` | Default: `0.0`. |
| `thinking_mode` | Default: `false`. |
| `distance_threshold` | Cosine distance threshold for this mode. Default: `0.2`. |

**Local mode** (`enhancer.local`): Translates the question to `docs_lang` via MarianMT. No term replacement, no context rewrite.

| Key | Description |
| --- | --- |
| `query_lang` | Language you ask questions in (e.g., `"zh"`, `"en"`). |
| `model_name` | HuggingFace model ID (optional). Auto-selects `Helsinki-NLP/opus-mt-{query_lang}-{docs_lang}` if omitted. |
| `distance_threshold` | Cosine distance threshold for this mode. Default: `0.3`. |

### Retrieval & Reranking

| Key | Description |
| --- | --- |
| `vector_enabled` | Enable vector (embedding) retrieval. When `false`, the embedding model is not loaded — faster startup, lower memory. Default: `true`. |
| `bm25_enabled` | Enable BM25 keyword retrieval. Can be used alone or combined with vector search; combined results are merged via Reciprocal Rank Fusion (RRF). Default: `false`. |
| `retrieval_k` | Number of chunks to retrieve per query. Default: `3`. |
| `retrieval_distance_threshold` | Cosine distance threshold for vector retrieval. Chunks with distance above this value are filtered out. Only effective when `vector_enabled` is `true`. Overridden by per-mode `distance_threshold` in the enhancer config when enhancement is enabled. Set `null` to disable filtering. Default: `0.3`. |

At least one of `vector_enabled` or `bm25_enabled` must be `true`. The four combinations:

| `vector_enabled` | `bm25_enabled` | Behavior |
| --- | --- | --- |
| `true` | `true` | Hybrid: vector + BM25, merged via RRF |
| `true` | `false` | Vector-only retrieval |
| `false` | `true` | BM25-only retrieval (no embedding model loaded) |
| `false` | `false` | Error: at least one must be enabled |

**Reranker** (optional): Two-stage retrieval -- vector search retrieves `retrieval_k * 4` candidates, then a cross-encoder reranks by relevance and trims to the final `retrieval_k`. Improves precision where bi-encoder cosine similarity is insufficient.

| Key | Description |
| --- | --- |
| `reranker_enabled` | Enable cross-encoder reranker. Default: `false`. |
| `reranker.model_name` | Cross-encoder model ID. Default: `"BAAI/bge-reranker-v2-m3"`. |
| `reranker.top_k` | Number of chunks after reranking. Default: `null` (uses `retrieval_k`). |

> **Performance**: Reranking adds ~100-300ms on GPU, ~500-1000ms on CPU. First load downloads the model (~1.1GB); subsequent loads use local cache.

### Answer Generation (`llm`)

The LLM that generates the final answer using the retrieved chunks. Fields: `api_base_url`, `api_key`, `model`, `temperature` (Default: `0.3`), `thinking_mode`.

### Chat Behavior

| Key | Description |
| --- | --- |
| `max_history_rounds` | Recent conversation rounds to keep for context. Default: `10`. |
| `strict_context` | `true` = answer **only** from retrieved chunks. `false` = LLM may supplement with its own knowledge. Default: `false`. |
| `system_rules` | Extra instructions appended to the system prompt. Default: `""`. |

## Document Filtering

Place a `.doc_loader_ignore` file in any subdirectory under `documents/`. Uses `.gitignore` syntax. Patterns apply to the containing directory and all subdirectories.

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

## Output

Conversation logs are saved to `output/<session>/` as numbered Markdown files.

```text
output/
└── What_is_exponential_smoothing_20260519_173334/
    ├── 01_round.md
    └── 02_round.md
```

Each round file contains the question, answer, processed question (labeled "Enhanced Question" in LLM mode or "Translated Question" in local mode), and the retrieved chunks used.

## Project Structure

```text
rag_qa.py               # entry point (--build | --rebuild | --search | question | interactive)
config.json             # your configuration (gitignored)
config_example.json     # configuration template
documents/              # put your .txt / .md / .typ files here
chroma_db/              # persisted vector database (generated)
output/                 # conversation exports (generated)
lib/
├── doc_loader.py       # file I/O + text chunking + ignore patterns
├── embed_engine.py     # embedding model wrapper (sentence-transformers)
├── vector_db.py        # Chroma vector store + hybrid retrieval
├── bm25_retriever.py   # BM25 keyword retriever (jieba + rank-bm25)
├── llm_api.py          # remote LLM API client (OpenAI-compatible)
├── query_enhancer.py   # query enhancement (retrieval-optimized rewriting)
├── local_translator.py # MarianMT local translation backend
└── reranker.py         # cross-encoder reranker for precision re-ranking
```

## Requirements

### Dependencies

- Python 3.10+
- `sentence-transformers`, `chromadb`, `openai`, `pathspec` (core)
- `jieba`, `rank-bm25` (BM25 hybrid retrieval)
- `transformers`, `sentencepiece`, `sacremoses` (only needed for `mode: "local"`)

### GPU Setup (Optional)

1. Check if you have an NVIDIA GPU and driver: `nvidia-smi`
2. Install CUDA-enabled PyTorch (default `pip install torch` is CPU-only):

   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cu121
   ```

3. Verify: `python -c "import torch; print(torch.cuda.is_available())"` -- should print `True`

Without GPU, everything still works, but **much slower**.

---

See [ARCHITECTURE.md](ARCHITECTURE.md) for build/query workflow, module internals, and environment setup (`sentence-transformers` version).
