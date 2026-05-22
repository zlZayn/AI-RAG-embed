# AI-RAG-embed

## Overview

Drop your .txt/.md files into `documents/`, embed them locally to build the index, then ask questions and get answers from a remote LLM based on your content.

## Quick Start

```bash
pip install -r requirements.txt

# 1. Copy config_example.json to config.json and fill in your API key
cp config_example.json config.json

# 2. Put your .txt / .md files in documents/

# 3. Build the vector index (downloads ~641MB embedding model on first run)
python rag_qa.py --build

# 4. Ask a question (interactive mode)
python rag_qa.py
```

> **Note**: The code uses `hf-mirror.com` as the default HuggingFace endpoint. Do not override `HF_ENDPOINT` with `huggingface.co` -- it will cause connection timeouts.

## Usage

### Build Index

```bash
python rag_qa.py --build    # incremental: skip if no files changed
python rag_qa.py --rebuild  # force full re-embed
```

`--build` only detects file content changes. If you change `chunk_size`, `chunk_overlap`, or `embedding_model_name` in `config.json`, use `--rebuild` to re-embed everything.

### Interactive Mode

Multi-turn conversation with history.

```bash
python rag_qa.py
```

```text
>>> What is exponential smoothing?
Exponential smoothing is a forecasting method...

>>> How many types are there?
The system understands "types" refers to exponential smoothing types from our previous discussion.

>>> /exit
```

### Single-Question Mode

One-shot, saves result to `output/`.

```bash
python rag_qa.py "What is exponential smoothing?"
```

### Search-Only Mode

Retrieve relevant document chunks without generating an answer.

```bash
python rag_qa.py --search "What is exponential smoothing?"

# With query enhancement (retrieval-optimized rewriting before searching)
python rag_qa.py --search --enhance "什么是指数平滑？"
```

Returns the top `retrieval_k` chunks (default: 3) directly to stdout. With `--enhance`, the query is processed through the enhancer before retrieval, same as `cmd_ask`. See [Query Enhancement](#query-enhancement-enhancer) for mode differences.

### CLI Overrides

Some config fields can be overridden via CLI arguments. If omitted, values fall back to `config.json`, then to code defaults.

```bash
python rag_qa.py --retrieval_k 10 --retrieval_distance_threshold 0.25 --strict_context true "your question"

python rag_qa.py --search --enhance --retrieval_k 3 --retrieval_distance_threshold 0.15 "your question"
```

Supported: `--retrieval_k`, `--retrieval_distance_threshold`, `--strict_context`. Works with all modes (ask, chat, search).

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
| `docs_dir` | Folder containing your `.txt` / `.md` files (including subfolders). Use `.doc_loader_ignore` to exclude files (`.gitignore` syntax). |
| `docs_lang` | Language of your documents (e.g., `"en"`, `"zh"`). The enhancer generates output in this language for retrieval. |
| `chunk_size` | Target characters per chunk. Larger = more context, less precise retrieval. Typical range: 300-1000. |
| `chunk_overlap` | Overlapping characters between adjacent chunks. Recommended: 10-20% of `chunk_size`. |
| `embedding_model_name` | HuggingFace model ID for vector embeddings. See notes below. |
| `chroma_persist_dir` | Folder where the vector database is saved. |

> **Switching models**: The code has model-specific defaults that may need manual adjustment:
>
> - **Embedding model**: A query prefix is hardcoded for the mxbai model family. Other models (e.g., `all-MiniLM-L6-v2`) do not use it — leaving it in will hurt retrieval. Check `lib/embed_engine.py` `_QUERY_PREFIX`.
> - **Translation model**: The local enhancer auto-selects `Helsinki-NLP/opus-mt-{query_lang}-{docs_lang}`. To use a different model series, set `model_name` explicitly in `config.json`.
> - **HuggingFace mirror**: `hf-mirror.com` is set as the default endpoint for users in China. Remove or override `HF_ENDPOINT` if you have direct access to HuggingFace.

### Retrieval

| Key | Description |
| --- | --- |
| `retrieval_k` | Number of chunks to retrieve per query. Default: `3`. |
| `retrieval_distance_threshold` | Global fallback cosine distance threshold. Overridden by per-mode `distance_threshold` in the enhancer config when enhancement is enabled. Set `null` to disable filtering. Default: `0.3`. |

### Query Enhancement (`enhancer`)

Rewrites your question before searching to improve retrieval quality. The enhanced output is used **only for retrieval** — the answer LLM always receives the original question.

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
documents/              # put your .txt / .md files here
chroma_db/              # persisted vector database (generated)
output/                 # conversation exports (generated)
lib/
├── doc_loader.py       # file I/O + text chunking + ignore patterns
├── embed_engine.py     # embedding model wrapper (sentence-transformers)
├── vector_db.py        # Chroma vector store operations
├── llm_api.py          # remote LLM API client (OpenAI-compatible)
├── query_enhancer.py   # query enhancement (retrieval-optimized rewriting)
└── local_translator.py # MarianMT local translation backend
```

## Requirements

### Dependencies

- Python 3.10+
- `sentence-transformers`, `chromadb`, `openai`, `pathspec` (core)
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

See `ARCHITECTURE.md` for build/query workflow, module internals, and environment setup (`sentence-transformers` version).
