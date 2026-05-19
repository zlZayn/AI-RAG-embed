# Architecture

## Overview

Local RAG (Retrieval-Augmented Generation) system. Ingests documents into a vector database, then answers user questions by retrieving relevant chunks and prompting a remote LLM with that context.

Two-phase design:

- **Offline**: build the vector index from documents (run once or on document change).
- **Online**: interactive Q&A loop, each question triggers retrieve-then-generate.

---

## Directory Structure

```text
AI-RAG-embed/
├── rag_runner.py          # single entry point (--build | question | interactive)
├── config.json            # runtime configuration (gitignored)
├── ARCHITECTURE.md        # this file
├── README.md              # user-facing quick start
├── requirements.txt       # Python dependencies
├── documents/             # user's raw .txt / .md files (source of truth)
├── chroma_db/             # persisted vector database (generated, gitignored)
├── output/                # exported conversation logs (generated, gitignored)
├── lib/                   # all domain logic modules
│   ├── __init__.py
│   ├── doc_loader.py      # file I/O + text chunking
│   ├── embed_engine.py    # embedding model wrapper
│   ├── vector_db.py       # Chroma vector store operations
│   └── llm_api.py         # remote LLM API client
└── plan/
    └── plan1.md           # original design plan (gitignored)
```

---

## Configuration Flow

`config.json` is the single source of runtime parameters:

```json
{
    "docs_dir": "./documents",
    "embedding_model_name": "mixedbread-ai/mxbai-embed-large-v1",
    "chroma_persist_dir": "./chroma_db",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "api_key": "...",
    "api_base_url": "https://token-plan-cn.xiaomimimo.com/v1",
    "llm_model": "mimo-v2.5-pro"
}
```

`rag_runner.py` reads the file on startup, resolves relative paths against the project root, and passes values as constructor/function arguments to each lib module. No module reads the config file directly -- they receive only the parameters they need.

---

## Dependency Rationale

| Package | Role | Why |
| --- | --- | --- |
| `sentence-transformers` | Embedding model | Pre-built Windows wheels, loads PyTorch models from HuggingFace, no C compiler needed |
| `chromadb` | Vector store | Embedded persistent DB, cosine similarity search, no external service required |
| `openai` | LLM client | OpenAI-compatible API, works with any provider sharing that protocol |
| `pathspec` | Ignore patterns | Parses `.doc_loader_ignore` files with `.gitignore` syntax |

Key version constraint: `sentence-transformers>=3.0,<5.0`. Version 5.x pulls in `torchcodec` which requires FFmpeg system libraries for video/audio modalities that this project does not use. Staying on 3.x avoids the entire problem.

---

## Environment Setup

### Python

Python 3.10 or later. The project uses `os.walk`, `pathspec`, `openai`, `chromadb`, and `sentence-transformers`.

### GPU Acceleration (CUDA)

The embedding model (`mixedbread-ai/mxbai-embed-large-v1`) runs inside PyTorch. By default, `pip install torch` gives the CPU-only build, which is orders of magnitude slower for embedding generation.

To enable GPU acceleration:

- Verify your GPU supports CUDA: `nvidia-smi`
- Install a CUDA-compatible PyTorch build:

```bash
# Remove CPU build first
pip uninstall torch torchvision -y

# Install CUDA 12.1 build (works with CUDA 12.x and 13.x drivers)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

- Verify the install:

```python
import torch
print(torch.cuda.is_available())  # must be True
print(torch.cuda.get_device_name(0))
```

**torchvision compatibility**: Keep torch and torchvision on the same CUDA index. Mixing a newer torchvision (from PyPI default) with an older torch (from cu121 index) causes `RuntimeError: operator torchvision::nms does not exist`.

**sentence-transformers version**: Use 3.x, not 5.x. Version 5.x depends on `torchcodec`, which requires FFmpeg shared libraries (not needed for text embeddings). If you accidentally install 5.x and get `Could not load libtorchcodec` errors, run:

```bash
pip uninstall torchcodec sentence-transformers -y
pip install sentence-transformers==3.4.1
```

### HuggingFace Mirror (China)

The embedding model is downloaded from HuggingFace on first use. In China, HuggingFace is blocked. The `embed_engine.py` module sets `HF_ENDPOINT=https://hf-mirror.com` via `os.environ.setdefault` automatically. If the mirror is down, you can override:

```bash
set HF_ENDPOINT=https://hf-mirror.com    # Windows
export HF_ENDPOINT=https://hf-mirror.com # Linux/Mac
```

The model is cached to `~/.cache/huggingface/` after first download, so the mirror is only needed once.

---

## Build Workflow

Triggered by `python rag_runner.py --build`.

```text
rag_runner.cmd_build()
  │
  ├─► doc_loader.load_documents(docs_dir, chunk_size, chunk_overlap)
  │     │
  │     ├─ pre-scan: walk entire tree, collect all .doc_loader_ignore specs
  │     ├─ os.walk(docs_dir) recursively (second pass)
  │     ├─ skip .doc_loader_ignore files themselves
  │     ├─ skip files matched by ancestor .doc_loader_ignore patterns
  │     ├─ filter *.txt, *.md
  │     ├─ read file content (UTF-8)
  │     ├─ sliding window: [start, start+chunk_size)
  │     │   next start = current_end - chunk_overlap
  │     └─ return [{"text": str, "source": "relative/path"}, ...]
  │
  ├─► embed_engine.EmbedEngine(model_name)
  │     │
  │     └─ SentenceTransformer(model_name)
  │           downloads model from HF mirror on first run
  │           caches to ~/.cache/huggingface/
  │
  └─► vector_db.VectorDb(persist_dir, embed_engine).rebuild(chunks)
        │
        ├─ embed_engine.embed_batch([text1, text2, ...])
        │     adds mxbai query prefix to each text
        │     returns list[list[float]] (one vector per chunk)
        │
        ├─ collection.get() → existing ids
        ├─ collection.delete(existing_ids)  // full clear
        └─ collection.add(ids, embeddings, documents, metadatas)
              persisted to chroma_persist_dir/ on disk
```

Key detail: `rebuild()` does a full delete-then-add cycle, not an upsert. This guarantees removed documents do not leave orphaned chunks.

---

## Query Workflows

Two modes, both share the same retrieve-then-generate core.

### Interactive mode

Triggered by `python rag_runner.py` (no arguments).

```text
rag_runner.cmd_chat()
  │
  ├─► embed_engine.EmbedEngine(model_name)
  ├─► vector_db.VectorDb(persist_dir, embed_engine)
  ├─► llm_api.LlmApi(api_key, base_url, model)
  │
  └─► loop:
        │
        ├─ input(">>> ") → question
        │   exit on "/exit", "/quit", "/q", Ctrl+C, or EOF
        │
        ├─► store.query(question, k=3)         }  shared
        │     ...                               }  retrieve-
        ├─► llm.generate(messages)              }  generate
        │     ...                               }  core
        │
        └─► _export_round(out_dir, ...)
              creates output dir on first question
```

### Single-question mode

Triggered by `python rag_runner.py "your question here"`.

```text
rag_runner.cmd_ask(question)
  │
  ├─► embed_engine.EmbedEngine(model_name)
  ├─► vector_db.VectorDb(persist_dir, embed_engine)
  ├─► llm_api.LlmApi(api_key, base_url, model)
  │
  ├─► store.query(question, k=3)
  ├─► llm.generate(messages)
  │
  └─► _init_output_dir(question)
      _export_round(out_dir, 1, question, chunks, answer)
        prints save path, exits
```

### Shared retrieve-generate core

```text
store.query(question, k=3)
  │
  ├─ embed_engine.get_embedding(question)
  │     adds mxbai query prefix
  │     returns list[float]
  │
  └─ collection.query(query_embeddings=[vec], n_results=3)
        Chroma cosine similarity search
        returns list[str] (top 3 document chunks)

llm.generate(messages)
  │
  └─ POST {base_url}/chat/completions
        model: llm_model
        messages: [
          {system: "You are a helpful assistant..."},
          {user: "Context:\n{chunks}\n\nQuestion: {question}"}
        ]
        returns response.choices[0].message.content
```

---

## Module Details

### lib/doc_loader.py

```text
load_documents(docs_dir, chunk_size, chunk_overlap) -> list[dict]
```

- Pure function, no class, no state.
- Walks directory tree with `os.walk`.
- Pre-scans for `.doc_loader_ignore` files in any directory. Patterns use `.gitignore` syntax. A pattern in `some/dir/.doc_loader_ignore` applies to all files under `some/dir/`.
- Opens each `.txt`/`.md` with UTF-8 encoding.
- Sliding window chunking: window size `chunk_size`, step = `chunk_size - chunk_overlap`.
- Each chunk carries its source file path (relative to `docs_dir`).
- Skips empty files.

Edge cases: files with content shorter than `chunk_size` produce a single chunk. Very long files produce N chunks.

### lib/embed_engine.py

```text
EmbedEngine(model_name)
  .get_embedding(text) -> list[float]
  .embed_batch(texts) -> list[list[float]]
```

- Wraps `SentenceTransformer` from `sentence-transformers`.
- Sets `HF_ENDPOINT=https://hf-mirror.com` via `os.environ.setdefault` (does not override if user has it set).
- Prepends mxbai query prefix `"Represent this sentence for searching relevant passages: "` to every text before encoding. This is required by the mxbai model family for correct retrieval behavior.
- Model is loaded once at init and kept in memory for the session lifetime.
- `embed_batch` processes all texts in one call for efficiency.

### lib/vector_db.py

```text
VectorDb(persist_dir, embed_engine)
  .rebuild(chunks) -> None
  .query(question, k) -> list[str]
```

- Uses `chromadb.PersistentClient` with cosine distance (`hnsw:space: "cosine"`).
- Collection name: `"documents"`.
- `rebuild`: deletes all existing entries, then adds new ones. IDs are sequential integers as strings (`"0"`, `"1"`, ...).
- `query`: embeds the question via `embed_engine.get_embedding`, then calls `collection.query` with the vector.
- Telemetry disabled (`anonymized_telemetry=False`).

### lib/llm_api.py

```text
LlmApi(api_key, base_url, model)
  .generate(messages) -> str
```

- Thin wrapper over `openai.OpenAI`.
- `messages` must be a list of `{"role": str, "content": str}` dicts.
- Returns the content string from the first choice.
- No retry logic -- network errors bubble up to the caller.

---

## Output Export

After each Q&A round, `_export_round` writes a Markdown file to the output directory:

```text
output/
└── What_is_a_tsibble_object_20260519_153000/
    ├── 01_round.md
    ├── 02_round.md
    └── ...
```

Directory naming: `{full_question_sanitized_truncated_to_60_chars}_{YYYYMMDD_HHMMSS}`.

Each round file contains:

- The user's question
- The retrieved context chunks
- The LLM's answer

The directory is created lazily on the first answered question.

---

## Error Handling Strategy

- Missing `documents/` at build time: prints message and exits with code 1.
- Empty documents directory: prints message and exits with code 1.
- No relevant chunks found for a question: prints message, continues loop (does not crash).
- API network errors: bubble up as unhandled exceptions (stack trace visible to user).
- Embedding model download failure: `SentenceTransformer` raises, process exits.
- Chroma persistence errors: raised by `chromadb`, not caught (indicates disk/permission issue).
