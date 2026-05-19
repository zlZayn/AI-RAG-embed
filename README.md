# AI-RAG-embed

Local RAG (Retrieval-Augmented Generation) knowledge base. Ingest your documents, then ask questions and get answers grounded in your content.

Embedding runs locally. Answer generation uses a remote LLM API (OpenAI-compatible).

## Quick Start

```bash
pip install -r requirements.txt

# 1. Copy config and fill in your API key
cp config_example.json config.json

# 2. Put your .txt / .md files in documents/

# 3. Build the vector index
python rag_runner.py --build

# 4. Ask a question (interactive mode)
python rag_runner.py
```

## Usage

**Build index** (run once, or after documents change):

```bash
python rag_runner.py --build
```

**Interactive mode** (multi-turn conversation):

```bash
python rag_runner.py
```

```text
>>> What is exponential smoothing?
Exponential smoothing is a forecasting method...

>>> /exit
```

**Single-question mode** (one-shot, saves result to `output/`):

```bash
python rag_runner.py "What is exponential smoothing?"
```

## Configuration

Copy `config_example.json` to `config.json` and edit. All settings are JSON strings unless noted.

| Key | Required | Default | Description |
| --- | --- | --- | --- |
| `docs_dir` | yes | `"./documents"` | Root directory for `.txt` / `.md` files. Supports nested subdirectories and `.doc_loader_ignore` filtering. |
| `chunk_size` | yes | `500` | Character count per text chunk. Larger values preserve more context but may dilute retrieval precision; typical range: 300–1000. |
| `chunk_overlap` | yes | `50` | Overlap in characters between adjacent chunks (recommended: 10–20% of `chunk_size`). Prevents semantic fragmentation at chunk boundaries. |
| `embedding_model_name` | yes | `"mixedbread-ai/mxbai-embed-large-v1"` | HuggingFace model ID for embedding. The default produces 1024-dim vectors and balances speed/quality. |
| `chroma_persist_dir` | yes | `"./chroma_db"` | Filesystem path for ChromaDB persistence. Automatically created on first build. |
| `retrieval_k` | no | `5` | Number of top-ranked chunks returned per query. Higher values improve recall but increase prompt length and latency. |
| `api_base_url` | yes | — | Endpoint URL of an OpenAI-compatible LLM API (e.g., DeepSeek, Azure OpenAI). |
| `api_key` | yes | — | Authentication key for the LLM API. Keep this secret; `config.json` is gitignored by default. |
| `llm_model` | yes | — | Model identifier recognized by the API (e.g., `"deepseek-chat"`). |
| `llm_temperature` | no | `0.3` | Sampling temperature in `[0.0, 2.0]`. Lower → more deterministic; higher → more creative. Set near `0` for factual tasks. |
| `strict_context` | no | `false` | **`false`** — LLM may blend retrieved context with its own knowledge (suitable for general Q&A).<br>**`true`** — LLM must answer **only** from retrieved chunks; replies "I don't know" when context is insufficient (suitable for audit/compliance scenarios). |
| `system_rules` | no | `""` | Free-text instructions appended to the system prompt. Use to enforce output format, tone, or constraints (e.g., `"No emoji. Use $...$ for math."`). |

## Document Filtering

Place a `.doc_loader_ignore` file in any subdirectory under `documents/`. Uses `.gitignore` syntax.

```text
# documents/fpp3_textbook/.doc_loader_ignore
README.md
*.log
_draft/
```

Patterns apply to the directory containing the ignore file and all its subdirectories.

## Output

Conversation logs are saved to `output/<session>/` as numbered Markdown files.

```text
output/
└── What_is_exponential_smoothing_20260519_173334/
    ├── 01_round.md
    └── 02_round.md
```

Each round file contains the question, answer, and sanitized retrieved context (wrapped in a code fence to prevent Markdown corruption).

## Project Structure

```text
rag_runner.py           # entry point (--build | question | interactive)
config.json             # your configuration (gitignored)
config_example.json     # configuration template
documents/              # put your .txt / .md files here
chroma_db/              # persisted vector database (generated)
output/                 # conversation exports (generated)
lib/
├── doc_loader.py       # file I/O + text chunking + ignore patterns
├── embed_engine.py     # embedding model wrapper (sentence-transformers)
├── vector_db.py        # Chroma vector store operations
└── llm_api.py          # remote LLM API client (OpenAI-compatible)
```

## Requirements

- Python 3.10+
- Dependencies: `sentence-transformers`, `chromadb`, `openai`, `pathspec`

See `ARCHITECTURE.md` for details on GPU acceleration, HuggingFace mirror setup, and design decisions.
