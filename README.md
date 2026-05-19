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

Copy `config_example.json` to `config.json` and edit:

| Key | Required | Default | Description |
| --- | --- | --- | --- |
| `docs_dir` | yes | — | Directory containing `.txt` / `.md` files |
| `chunk_size` | yes | — | Characters per text chunk |
| `chunk_overlap` | yes | — | Overlapping characters between adjacent chunks |
| `embedding_model_name` | yes | — | HuggingFace model ID for embeddings |
| `chroma_persist_dir` | yes | — | Directory for the vector database |
| `retrieval_k` | no | `5` | Number of relevant chunks to retrieve |
| `api_base_url` | yes | — | Base URL of the OpenAI-compatible API |
| `api_key` | yes | — | API key for the LLM service |
| `llm_model` | yes | — | Model name to pass to the API |
| `llm_temperature` | no | `0.3` | Sampling temperature |
| `strict_context` | no | `false` | If `true`, LLM answers only from retrieved context; if `false`, LLM supplements with its own knowledge |
| `system_rules` | no | `""` | Additional rules appended to the system prompt |

### strict_context

- `false` (default) — LLM uses retrieved context to enrich its answer but can also draw on its own knowledge. Best for general Q&A.
- `true` — LLM answers **only** from the retrieved chunks. If no relevant chunks are found, it says "I don't know". Best for factual audit scenarios.

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
