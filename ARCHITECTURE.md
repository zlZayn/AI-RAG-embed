# Architecture

## Overview

Local RAG system with two phases:

### Build Phase (`--build`)

1. Load all `.txt` and `.md` files from `documents/` directory
2. Split files into text chunks with sliding window overlap
3. Convert chunks to vector embeddings using a local embedding model
4. Store embeddings and original text in a Chroma vector database

### Query Phase

1. (Optional) Enhance user question: translate to `docs_lang` to improve retrieval. In LLM mode, also rephrase and resolve conversation references
2. Convert enhanced question to vector embedding
3. Retrieve top-k most similar chunks from the vector database
4. Send **original** question + retrieved chunks to a remote LLM as context (enhanced question is retrieval-only, preserving the user's language for the answer)
5. Generate answer and save to `output/` directory

## Directory Structure

```text
rag_qa.py           # single entry point
config.json             # runtime config (gitignored)
config_example.json     # config template (committed)
documents/              # raw .txt / .md files
chroma_db/              # persisted Chroma DB (generated, gitignored)
output/                 # conversation logs (generated, gitignored)
lib/
├── __init__.py
├── doc_loader.py       # os.walk + sliding window chunking + ignore patterns
├── embed_engine.py     # SentenceTransformer wrapper
├── vector_db.py       # Chroma PersistentClient operations
├── llm_api.py         # openai.OpenAI wrapper
├── query_enhancer.py  # query enhancement (translation + rewording)
└── local_translator.py # MarianMT local translation backend
```

## Configuration

`rag_qa.py` reads `config.json` at startup. No lib module reads the config directly -- they receive only the parameters they need.

| Field | Group | Description |
| --- | --- | --- |
| `docs_dir` | Local data | Source document directory |
| `docs_lang` | Local data | Target language for question translation |
| `chunk_size` | Local data | Characters per chunk (sliding window) |
| `chunk_overlap` | Local data | Overlapping characters between adjacent chunks |
| `embedding_model_name` | Embedding | HuggingFace model ID |
| `chroma_persist_dir` | Embedding | Chroma persistence directory |
| `retrieval_k` | Embedding | Number of chunks to retrieve (default: 3) |
| `query_enhance_enabled` | Enhancement | Enable query enhancement |
| `enhancer` | Enhancement | Enhancer config with mode switch: `"llm"` (API) or `"local"` (MarianMT) |
| `llm` | LLM | LLM model config (api_base_url, api_key, model, temperature, thinking_mode) |
| `strict_context` | Behavior | `true` = answer only from context; `false` = supplement with own knowledge |
| `system_rules` | Behavior | Additional system prompt rules (optional) |

Relative paths (`./`) are resolved against the project root.

## System Prompt

Two modes controlled by `strict_context`:

**strict_context = false** (default):
> You are a helpful assistant. Use the provided context to enrich your answer, but also draw on your own knowledge when the context is insufficient. If the context is provided, prefer it over your own knowledge for factual claims.

**strict_context = true**:
> You are a helpful assistant. Answer the user's question based ONLY on the provided context. If the answer is not in the context, say 'I don't know'.

If `system_rules` is set, it is appended after the base prompt.

## Entry Point

`rag_qa.py` dispatches based on `sys.argv`:

```text
python rag_qa.py              →  cmd_chat()    (interactive)
python rag_qa.py "question"   →  cmd_ask()     (single-shot)
python rag_qa.py --build      →  cmd_build()   (build index)
```

Heavy imports (`sentence-transformers`, `chromadb`, `openai`) are lazy-loaded via `_import_lib()`. `cmd_ask` and `cmd_chat` call it through `_init_ask_chat()`; `cmd_build` calls it directly. This avoids import-time side effects in IPython (`%run`) environments where signal handling can conflict with these libraries.

## Build Workflow

```text
cmd_build()
  ├─► doc_loader.load_documents(docs_dir, chunk_size, chunk_overlap)
  │     ├─ pre-scan: walk tree, collect .doc_loader_ignore specs
  │     ├─ os.walk: collect .txt/.md files, skip ignored
  │     ├─ read UTF-8 content
  │     └─ sliding window: [start, start+chunk_size), step = chunk_size - overlap
  │         returns [{"text": str, "source": "relative/path"}, ...]
  │
  ├─► embed_engine.EmbedEngine(model_name)
  │     └─ SentenceTransformer(model_name)
  │
  └─► vector_db.VectorDb(persist_dir, embed_engine).rebuild(chunks)
        ├─ embed_batch(texts)  →  list[list[float]]
        ├─ delete all existing entries
        └─ add(ids, embeddings, documents, metadatas)
```

`rebuild()` does a full delete-then-add cycle, ensuring removed documents leave no orphaned chunks.

## Query Workflow

Both `cmd_ask` and `cmd_chat` share `_init_ask_chat()` for engine initialization and `_retrieve_context()` for retrieval.
`cmd_chat` additionally maintains a `history` list across rounds and passes it for context-aware enhancement and message construction.

```text
_retrieve_context(store, llm, question, system_prompt, retrieval_k, query_enhancer=None, messages_history=None)
  ├─► print ">> Processing..."

  ├─► [optional] query_enhancer.enhance(question, messages_history)
  │     ├─ LLM mode:
  │     │    With history: rewrite as standalone query (resolve pronouns/ellipsis), then translate to docs_lang
  │     │    Without history: translate to docs_lang, replace technical terms with target-language equivalents
  │     └─ Local mode: translate to docs_lang via MarianMT (no rewrite, no term replacement)

  ├─► print ">> Retrieving..."
  ├─► store.query(rewritten_question, k)
  │     ├─ embed_engine.get_embedding(rewritten_question)  →  vector
  │     └─ collection.query(query_embeddings, n_results=k)
  │           Chroma cosine similarity search
  │           returns top-k document chunks

  ├─► print ">> Retrieved N chunks. Generating..."

  └─► llm.generate_stream(messages)
        POST {base_url}/chat/completions (stream=True)
        messages: [system prompt, (conversation history ...), {user:
          "Context:\n{chunks}\n\nQuestion: {original_question}"}]

Note: the enhanced question is used **only for retrieval** (store.query).
The answer LLM always receives the **original question** to preserve the user's language.
```

If no relevant chunks are found, the system prints a message and skips the round.

## Module Details

### lib/doc_loader.py

```text
load_documents(docs_dir, chunk_size, chunk_overlap) -> list[dict]
```

- Walks directory tree with `os.walk`.
- Pre-scans for `.doc_loader_ignore` files (`.gitignore` syntax via `pathspec`).
- Sliding window chunking: window = `chunk_size`, step = `chunk_size - chunk_overlap`.
- Each chunk carries its source file path relative to `docs_dir`.
- Skips empty files.

### lib/embed_engine.py

```text
EmbedEngine(model_name)
  .get_embedding(text) -> list[float]
  .embed_batch(texts) -> list[list[float]]
```

- Wraps `SentenceTransformer`.
- Sets `HF_ENDPOINT=https://hf-mirror.com` via `os.environ.setdefault` (China mirror, does not override user-set values).
- `get_embedding(text)` prepends the mxbai query prefix `"Represent this sentence for searching relevant passages: "` before encoding -- required by the mxbai model family for query embeddings.
- `embed_batch(texts)` does **not** add the prefix -- document embeddings should be encoded as-is for correct semantic alignment with query embeddings.

### lib/vector_db.py

```text
VectorDb(persist_dir, embed_engine)
  .rebuild(chunks) -> None
  .query(question, k) -> list[str]
```

- `chromadb.PersistentClient` with cosine distance (`hnsw:space: "cosine"`).
- Collection name: `"documents"`.
- Telemetry disabled.

### lib/llm_api.py

```text
LlmApi(api_key, base_url, model, temperature=0.3, thinking_mode=False)
  .generate(messages) -> str          # non-streaming (used by query_enhancer, LLM mode only)
  .generate_stream(messages) -> iter  # streaming (used by rag_qa)
```

- Wraps `openai.OpenAI`.
- Temperature and thinking_mode are set at initialization.
- No retry logic -- network errors propagate to caller.

### lib/query_enhancer.py

```text
QueryEnhancer(llm_api=None, docs_lang="en", translator=None)
  .enhance(question, history=None) -> str
  .label -> str          # "Enhanced Question" (LLM) or "Translated Question" (local)
```

Two backends, selected by which constructor argument is provided:

**LLM mode** (`llm_api` provided):

- With conversation history (`cmd_chat` follow-up questions): Constructs a prompt containing the full conversation, asks the LLM to rewrite the latest question as a standalone query (resolving pronouns and ellipsis), then translates to `docs_lang`.
- Without history (`cmd_ask` single question): Constructs a translation prompt with term-replacement instructions. The LLM translates the question to `docs_lang` and replaces technical terms with their target-language equivalents.

**Local mode** (`translator` provided):

- Calls `translator.translate(question)` directly. Pure translation via MarianMT — no term replacement, no conversation-context rewrite. History parameter is accepted but ignored.

Returns the result as a single string. Used **only for retrieval** — the answer LLM always receives the original question to preserve the user's language.

### lib/local_translator.py

```text
LocalTranslator(src_lang, docs_lang, model_name=None)
  .translate(text) -> str
```

- Loads a Helsinki-NLP MarianMT model via `transformers.MarianMTModel` and `MarianTokenizer`.
- Model loaded with `use_safetensors=True` to avoid `torch.load` security restriction (CVE-2025-32434) — works with any torch version.
- `model_name`: explicit HuggingFace model ID. If `None`, auto-selects `Helsinki-NLP/opus-mt-{src_lang}-{docs_lang}` (e.g., `src_lang="zh"`, `docs_lang="en"` → `Helsinki-NLP/opus-mt-zh-en`).
- Class-level cache (`_cache` dict): keyed by model name. Same language pair shares one loaded model across all instances within the process.
- First load downloads from HuggingFace (approx. 300 MB). Subsequent loads read from the local HuggingFace cache (`~/.cache/huggingface/`).
- `translate()`: tokenizes input, runs `model.generate()`, decodes output tokens. Returns the translated string.

## Output Export

After each Q&A round, `_export_round()` writes a Markdown file:

```text
output/<sanitized_question>_<YYYYMMDD_HHMMSS>/
├── 01_round.md
└── 02_round.md
```

Each round file:

========== *Round 1* ==========

**Question:**

```text
{original question}
```

**Enhanced Question:** (LLM mode) / **Translated Question:** (local mode)

```text
{processed question}
```

**Answer:**

...

========== *Retrieved Context* ==========

```text
{chunk 1 content}
```

```text
{chunk 2 content}
```

### Chunk Sanitization

Retrieved chunks are sanitized before wrapping to prevent Markdown rendering corruption:

1. `strip("`")` -- removes leading/trailing backtick debris from chunk boundaries (common when chunks are truncated mid-code-block).
2. `replace("```", "``")` -- reduces any remaining triple-backtick to double-backtick (prevents premature fence closure).

After sanitization, the context block is wrapped in a standard 3-backtick fence with `text` info string.

## Environment Setup

### Python

Python 3.10+.

### GPU Acceleration (CUDA)

The embedding model runs inside PyTorch. Default `pip install torch` gives CPU-only build. For GPU:

```bash
pip uninstall torch torchvision -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

Verify: `torch.cuda.is_available()` must be `True`.

### sentence-transformers Version

Use 3.x, not 5.x. Version 5.x depends on `torchcodec` (requires FFmpeg, not needed for text embeddings). If you hit `Could not load libtorchcodec`:

```bash
pip uninstall torchcodec sentence-transformers -y
pip install "sentence-transformers>=3.0,<5.0"
```

### HuggingFace Mirror (China)

`embed_engine.py` and `local_translator.py` both set `HF_ENDPOINT=https://hf-mirror.com` automatically via `os.environ.setdefault`. Override if needed:

```bash
set HF_ENDPOINT=https://hf-mirror.com    # Windows
export HF_ENDPOINT=https://hf-mirror.com # Linux/Mac
```

The model is cached to `~/.cache/huggingface/` after first download.

## Error Handling

| Condition | Behavior |
| --- | --- |
| `documents/` not found at build time | Print message, exit code 1 |
| No `.txt`/`.md` files found | Print message, exit code 1 |
| No relevant chunks for a question | Print message, skip round (does not crash) |
| API network errors | Unhandled exception (stack trace visible) |
| Embedding model download failure | `SentenceTransformer` raises, process exits |
| Chroma persistence errors | Raised by `chromadb`, not caught (disk/permission issue) |
