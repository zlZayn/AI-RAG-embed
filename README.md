# AI-RAG-embed

Local RAG (Retrieval-Augmented Generation) knowledge base. Ingest your documents, then ask questions and get answers grounded in your content.

Embedding runs locally. Answer generation uses a remote LLM API (OpenAI-compatible).

## Quick Start

```bash
pip install -r requirements.txt

# 1. Copy config and fill in your API key
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

## Configuration

Copy `config_example.json` to `config.json` and edit. Relative paths (`./`) are resolved against the project root.

### Document & Indexing

| Key | Description |
| --- | --- |
| `docs_dir` | Folder containing your `.txt` / `.md` files (including subfolders). Use `.doc_loader_ignore` to exclude files (`.gitignore` syntax). |
| `docs_lang` | Language of your documents (e.g., `"en"`, `"zh"`). The enhancer translates your question into this language before searching. |
| `chunk_size` | Target characters per chunk. Larger = more context, less precise retrieval. Typical range: 300-1000. |
| `chunk_overlap` | Overlapping characters between adjacent chunks. Recommended: 10-20% of `chunk_size`. |
| `embedding_model_name` | HuggingFace model ID for vector embeddings. |
| `chroma_persist_dir` | Folder where the vector database is saved. |

### Retrieval

| Key | Description |
| --- | --- |
| `retrieval_k` | Number of chunks to retrieve per query. Default: `3`. |

### Query Enhancement (`enhancer`)

Translates your question into `docs_lang` before searching. In LLM mode, also replaces technical terms and rewrites follow-up questions using conversation history.

| Key | Description |
| --- | --- |
| `query_enhance_enabled` | Enable query enhancement. Default: `false`. |
| `mode` | `"llm"` = use an LLM API. `"local"` = use a local MarianMT model (offline, translation only). |

**LLM mode** (`enhancer.llm`): `api_base_url`, `api_key`, `model`, `temperature` (Default: `0.0`), `thinking_mode`.

**Local mode** (`enhancer.local`):

| Key | Description |
| --- | --- |
| `query_lang` | Language you ask questions in (e.g., `"zh"`, `"en"`). |
| `model_name` | HuggingFace model ID (optional). Auto-selects `Helsinki-NLP/opus-mt-{query_lang}-{docs_lang}` if omitted. |

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
rag_qa.py               # entry point (--build | --rebuild | question | interactive)
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
├── query_enhancer.py   # query enhancement (translation + rewording)
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
