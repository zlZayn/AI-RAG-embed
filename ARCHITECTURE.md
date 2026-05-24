# Architecture

## Design Philosophy

Most RAG systems embed the user's raw question directly into the vector space and hope the embedding model bridges the gap. It often doesn't. A question like "ARIMA 怎么选参数?" is concise and natural for a human, but a poor match for document chunks that discuss "order determination via AIC/BIC criteria" and "automated model selection with auto_arima." The embedding model may bridge the semantic gap, or it may not — and when it fails, the user gets irrelevant chunks with no obvious way to fix it.

In the AI era, calling an LLM as a thin middleware layer costs almost nothing but returns disproportionately. The enhancer rewrites the user's question into a dense retrieval paragraph optimized for vector similarity matching. The rewritten query is used only for retrieval; the answer LLM always receives the original question.

## Overview

Local RAG system with two phases:

### Build Phase (`--build`)

1. Load all `.txt` and `.md` files from `documents/` directory, computing MD5 hashes for change detection
2. Split files into text chunks at natural boundaries (paragraph > sentence > word)
3. Check for file changes against stored hashes; skip if none (only with `--build`)
4. Convert chunks to vector embeddings using a local embedding model
5. Store embeddings and original text in a Chroma vector database

### Query Phase

1. (Optional) Enhance user question for retrieval. In LLM mode, generate a retrieval-optimized paragraph in `docs_lang`. In local mode, translate to `docs_lang`. For follow-up questions, rewrite using conversation history first
2. Convert enhanced question to vector embedding
3. Retrieve top-k most similar chunks from the vector database
4. (Optional) Rerank retrieved chunks with a cross-encoder model for precision re-ranking. Retrieves `retrieval_k * 4` candidates from vector search, then reranks and trims to `retrieval_k`
5. Send **original** question + retrieved chunks to a remote LLM as context (enhanced question is retrieval-only, preserving the user's language for the answer)
6. Generate answer and save to `output/` directory

## Directory Structure

```text
rag_qa.py               # single entry point
config.json             # runtime config (gitignored)
config_example.json     # config template (committed)
documents/              # raw .txt / .md files
chroma_db/              # persisted Chroma DB (generated, gitignored)
output/                 # conversation logs (generated, gitignored)
lib/
├── __init__.py
├── doc_loader.py       # os.walk + smart boundary chunking + ignore patterns + file hashing
├── embed_engine.py     # SentenceTransformer wrapper
├── vector_db.py       # Chroma PersistentClient + incremental rebuild via file hash diff
├── llm_api.py         # openai.OpenAI wrapper
├── query_enhancer.py  # query enhancement (retrieval-optimized rewriting)
├── local_translator.py # MarianMT local translation backend
└── reranker.py        # cross-encoder reranker for precision re-ranking
```

## Configuration

`rag_qa.py` reads `config.json` at startup. No lib module reads the config directly -- they receive only the parameters they need. "Default" below refers to the code's hardcoded fallback when a key is omitted.

| Field | Group | Description |
| --- | --- | --- |
| `docs_dir` | Indexing | Source document directory |
| `docs_lang` | Indexing | Target language for enhancer output |
| `chunking` | Indexing | Chunking config: `mode` (`"auto"` / `"fixed"`), plus mode-specific sub-keys (`auto.target_chars`, `fixed.max_chars`). See `config_example.json`. |
| `embedding_model_name` | Indexing | HuggingFace model ID |
| `chroma_persist_dir` | Indexing | Chroma persistence directory |
| `query_enhance_enabled` | Enhancement | Enable query enhancement (Default: `false`) |
| `enhancer` | Enhancement | Enhancer config with mode switch: `"llm"` (retrieval-optimized paragraph) or `"local"` (MarianMT translation). Each mode has its own `distance_threshold`. |
| `retrieval_k` | Retrieval | Number of chunks to retrieve (Default: `3`) |
| `retrieval_distance_threshold` | Retrieval | Global fallback cosine distance threshold. Overridden by per-mode `distance_threshold` in enhancer config when enhancement is enabled. `null` disables filtering (Default: `0.3`) |
| `reranker_enabled` | Retrieval | Enable cross-encoder reranker for precision re-ranking (Default: `false`) |
| `reranker` | Retrieval | Reranker config: `model_name` (Default: `"BAAI/bge-reranker-v2-m3"`), `top_k` (Default: `null`, uses `retrieval_k`) |
| `llm` | Generation | LLM model config (api_base_url, api_key, model, temperature (Default: `0.3`), thinking_mode) |
| `max_history_rounds` | Behavior | Recent conversation rounds to keep (Default: `10`) |
| `strict_context` | Behavior | `true` = answer only from context; `false` = supplement with own knowledge (Default: `false`) |
| `system_rules` | Behavior | Additional system prompt rules (Default: `""`) |

Relative paths (`./`) are resolved against the project root.

## Entry Point

`rag_qa.py` dispatches based on `sys.argv`:

```text
python rag_qa.py                       →  cmd_chat()             (interactive)
python rag_qa.py "question"            →  cmd_ask()              (single-shot)
python rag_qa.py --search "q"          →  cmd_search()           (retrieve only, no enhancer)
python rag_qa.py --search --enhance "q"→  cmd_search(use_enhancer=True)  (retrieve with enhancement)
python rag_qa.py --build               →  cmd_build()            (incremental build)
python rag_qa.py --rebuild             →  cmd_build(force=True)  (full rebuild)
```

Optional CLI overrides: `--retrieval_k`, `--retrieval_distance_threshold`, `--strict_context`. These override the corresponding `config.json` fields; if omitted, config values (or code defaults) are used. CLI override takes highest priority, even over per-mode enhancer thresholds.

Only query-time parameters are exposed as CLI overrides. Indexing parameters (`chunking`, `embedding_model_name`) are intentionally excluded: changing them requires a full `--rebuild`, which is a deliberate operation that should not be triggered accidentally by a CLI flag.

Heavy imports (`sentence-transformers`, `chromadb`, `openai`) are lazy-loaded via `_import_lib()`. `cmd_ask` and `cmd_chat` call it through `_init_ask_chat()`, which delegates embedding+vector-store init to `_init_embed_store()`. `cmd_search` and `cmd_build` call `_init_embed_store()` directly (skipping LLM init). `cmd_search` with `--enhance` additionally calls `_init_enhancer()` to initialize the query enhancer. `cmd_build` first checks for file changes using only stdlib `json`; `_import_lib()` is called only when changes are detected. This avoids import-time side effects in IPython (`%run`) environments where signal handling can conflict with these libraries.

Progress messages use the `_timed(label)` context manager for consistent `">> {label}... done  [Xs]"` formatting.

## Build Workflow

```text
cmd_build()
├─► doc_loader.load_documents(docs_dir, config)
│   ├─ pre-scan: walk tree, collect .doc_loader_ignore specs
│   ├─ os.walk: collect .txt/.md files, skip ignored
│   ├─ read UTF-8 content, compute MD5 hash per file
│   └─ smart split: auto mode (md: heading-aware; txt: paragraph-first) or fixed mode (separator-priority fallback)
│       returns (chunks, file_hashes)
│       chunks: [{"text": str, "source": "relative/path"}, ...]
│       file_hashes: {"relative/path": "md5hex", ...}
│
├─► _has_file_changes(persist_dir, file_hashes)
│   ├─ read build_meta.json directly (json.load, no heavy imports)
│   ├─ compare keys + hash values
│   └─ if no changes → print "No changes detected", return early
│
└─► [only if changes detected]
    ├─► _init_embed_store(config)
    │   ├─ _import_lib()  →  EmbedEngine, LlmApi, VectorDb
    │   ├─ embed_engine.EmbedEngine(model_name)
    │   │   └─ SentenceTransformer(model_name)
    │   └─ vector_db.VectorDb(persist_dir, embed_engine)
    │
    └─► store.rebuild / store.rebuild_full
        ├─ --build:   .rebuild(chunks, file_hashes)       # incremental
        └─ --rebuild: .rebuild_full(chunks, file_hashes)   # delete all, re-embed
```

`--rebuild` skips change detection and forces a full delete-then-add cycle. `--build` reads `build_meta.json` via stdlib `json` only — no `sentence-transformers`, `chromadb`, or `openai` imported when no files changed.

Change detection compares file content hashes only. Config changes to `chunking` or `embedding_model_name` are not detected — use `--rebuild` after changing these.

`rebuild()` performs incremental updates by comparing file content hashes stored in `build_meta.json`. Only changed, added, or removed files are re-embedded. `rebuild_full()` does a full delete-then-add cycle for when a clean rebuild is needed.

## Query Workflow

Both `cmd_ask` and `cmd_chat` share `_init_ask_chat()` for engine initialization and `_retrieve_context()` for retrieval.
`cmd_chat` additionally maintains a `history` list across rounds, truncated to the last `max_history_rounds` rounds (default: 10), and passes it for context-aware enhancement and message construction.
`cmd_search` uses only `_init_embed_store()` for retrieval without LLM generation. With `--enhance`, it additionally calls `_init_enhancer()` to initialize the query enhancer and rewrites the question before retrieval — same enhancement logic as `cmd_ask`, but without LLM answer generation.

`cmd_search` with `--enhance` follows a simplified path compared to `_retrieve_context`:

```text
cmd_search(question, use_enhancer=True)
├─► _init_embed_store(config)          →  store
├─► _init_enhancer(config)             →  enhancer
├─► enhancer.enhance(question)         →  rewritten_question
│   (same logic as _retrieve_context: LLM retrieval-paragraph, or local MarianMT)
├─► _init_reranker(config)             →  reranker
├─► store.query(rewritten_question, k_for_search, distance_threshold)
│   k_for_search = retrieval_k * 4  (if reranker enabled, else retrieval_k)
├─► [optional] reranker.rerank(rewritten_question, chunks, top_k=retrieval_k)
└─► print chunks to stdout
```

```text
_retrieve_context(..., retrieval_distance_threshold=None, reranker=None) -> RetrieveResult(chunks, messages, rewritten_question, enhance_label)
├─► print ">> Processing..."
│
├─► [optional] query_enhancer.enhance(question, messages_history)
│   ├─ LLM mode:
│   │   Without history: generate retrieval-optimized paragraph in docs_lang
│   │   With history: rewrite as standalone query (resolve pronouns/ellipsis), then generate retrieval paragraph
│   └─ Local mode: translate to docs_lang via MarianMT (no rewrite, no term replacement)
│
├─► print ">> Retrieving..."
├─► k_for_search = retrieval_k * 4  (if reranker enabled, else retrieval_k)
├─► store.query(rewritten_question, k_for_search, distance_threshold)
│   ├─ embed_engine.get_embedding(rewritten_question)  →  vector
│   ├─ collection.query(query_embeddings, n_results=k_for_search)
│   │   Chroma cosine similarity search
│   │   returns top-k_for_search document chunks
│   └─ filter by distance_threshold (if set)
│       discard chunks with distance >= threshold
│       if none pass, return top-1 as fallback
│
├─► [optional] reranker.rerank(rewritten_question, chunks, top_k=retrieval_k)
│   ├─ CrossEncoder.predict([(query, chunk) ...])  →  scores
│   ├─ sort by score descending
│   └─ return top retrieval_k chunks
│
├─► print ">> Retrieved N chunks. Generating..."
│
└─► _stream_answer(llm, messages)
    llm.generate_stream(messages) → iter[str]
    POST {base_url}/chat/completions (stream=True)
    messages: [system prompt, (conversation history ...), {user:
      "Context:\n{chunks}\n\nQuestion: {original_question}"}]

Note: the enhanced question is used **only for retrieval** (store.query).
The answer LLM always receives the **original question** to preserve the user's language.
```

If no relevant chunks are found, the system prints a message and skips the round.

### _init_enhancer(config)

Shared helper that initializes the query enhancer from config. Returns `(enhancer, threshold)` tuple — `(None, None)` if `query_enhance_enabled` is `false`. The `threshold` is the per-mode `distance_threshold` from the active enhancer config (local or llm). Used by both `cmd_search(use_enhancer=True)` and `_init_ask_chat()`. Callers use the enhancer threshold when available, falling back to the global `retrieval_distance_threshold`.

### Chunk Sanitization

Retrieved chunks are sanitized before wrapping to prevent Markdown rendering corruption:

1. `strip("`")` -- removes leading/trailing backtick debris from chunk boundaries (common when chunks are truncated mid-code-block).
2. `replace("```", "``")` -- reduces any remaining triple-backtick to double-backtick (prevents premature fence closure).

After sanitization, the context block is wrapped in a standard 3-backtick fence with `text` info string.

## System Prompt

Two modes controlled by `strict_context`:

**strict_context = false** (default):
> You are a helpful assistant. Use the provided context to enrich your answer, but also draw on your own knowledge when the context is insufficient. If the context is provided, prefer it over your own knowledge for factual claims.

**strict_context = true**:
> You are a helpful assistant. Answer the user's question based ONLY on the provided context. If the answer is not in the context, say 'I don't know'.

If `system_rules` is set, it is appended after the base prompt.

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

## Module Details

### lib/doc_loader.py

```text
load_documents(docs_dir, config) -> (list[dict], dict[str, str])
```

- Walks directory tree with `os.walk`.
- Pre-scans for `.doc_loader_ignore` files (`.gitignore` syntax via `pathspec`).
- Each chunk carries its source file path relative to `docs_dir`.
- Computes MD5 hash per file for incremental rebuild detection.
- Skips empty files.
- Two chunking modes controlled by `chunking.mode`:

**auto mode** (default, `chunking.auto`):

- `.md` files: parses Markdown into structural units (headings, paragraphs, code blocks, tables), groups by heading level (`split_at_level`), then merges within sections. Code blocks and tables are atomic — never split even if they exceed `target_chars`.
- `.txt` files: splits on paragraph boundaries (`\n\n`, falls back to `\n`). Paragraphs are never cut — a paragraph either fits into the current chunk or starts a new one.
- `target_chars`: target chunk size. Atomic units (code blocks, tables) may exceed this. Default: `700`.
- `min_chars`: sections shorter than this are dropped as noise.
- `include_heading`: if `true`, prepends the section heading (`> heading`) to each chunk.

**fixed mode** (`chunking.fixed`):

- Splits at `max_chars` (hard ceiling, never exceeded), then searches backward for the best separator by priority: paragraph break (`\n\n`) > newline (`\n`) > sentence-ending punctuation (`。！？.!？`) > space > hard cut. Minimum boundary = `max_chars // 2`.
- `max_chars`: hard limit per chunk. Default: `700`.
- `overlap_chars`: adjacent chunks overlap by this many characters to preserve context.

### lib/embed_engine.py

```text
EmbedEngine(model_name)
  .get_embedding(text) -> list[float]
  .embed_batch(texts) -> list[list[float]]
```

- Wraps `SentenceTransformer`.
- Sets `HF_ENDPOINT=https://hf-mirror.com` via `os.environ.setdefault` (China mirror, does not override user-set values).
- Model loaded with `local_files_only=True` first, falls back to network download if not cached.
- `get_embedding(text)` prepends the mxbai query prefix `"Represent this sentence for searching relevant passages: "` before encoding -- required by the mxbai model family for query embeddings. Other models do not use this prefix; leaving it in will hurt retrieval. Check `_QUERY_PREFIX` when switching models.
- `embed_batch(texts)` does **not** add the prefix -- document embeddings should be encoded as-is for correct semantic alignment with query embeddings.

### lib/vector_db.py

```text
VectorDb(persist_dir, embed_engine=None)
  .rebuild(chunks, file_hashes) -> None    # incremental: only re-embed changed files
  .rebuild_full(chunks, file_hashes) -> None  # full delete-then-add
  .query(question, k, distance_threshold=None) -> list[str]
```

- `chromadb.PersistentClient` with cosine distance (`hnsw:space: "cosine"`).
- Collection name: `"documents"`.
- Telemetry disabled.
- `rebuild()` prints an incremental summary: `+N new, ~N updated, -N removed. Total: N`.

### lib/llm_api.py

```text
LlmApi(api_key, base_url, model, temperature=0.3, thinking_mode=False)
  .generate(messages) -> str          # non-streaming (used by query_enhancer, LLM mode only)
  .generate_stream(messages) -> iter  # streaming (used by rag_qa)
```

- Wraps `openai.OpenAI`.
- Temperature and thinking_mode are set at initialization.
- `generate()` is implemented as `"".join(generate_stream(messages))` -- not a separate code path.
- `thinking_mode` is passed via `extra_body={"thinking_mode": True}` in the API request.
- No retry logic -- network errors propagate to caller.

### lib/query_enhancer.py

```text
QueryEnhancer(llm_api=None, docs_lang="en", translator=None)
  .enhance(question, history=None) -> str
  .label -> str          # "Enhanced Question" (LLM) or "Translated Question" (local)
```

Two backends, selected by which constructor argument is provided:

**LLM mode** (`llm_api` provided):

- Without history (`cmd_ask` single question): Generates a dense retrieval paragraph in `docs_lang` covering the core topic, key technical terms, related concepts, and likely document content. Optimized for vector similarity matching, not human readability.
- With conversation history (`cmd_chat` follow-up questions): Rewrites the latest question as a standalone query using conversation context (resolving pronouns/ellipsis), then generates the retrieval paragraph.

**Local mode** (`translator` provided):

- Calls `translator.translate(question)` directly. Pure translation via MarianMT — no term replacement, no conversation-context rewrite. History parameter is accepted but ignored.

Returns the result as a single string. If the LLM call fails, silently falls back to the original question. Used **only for retrieval** — the answer LLM always receives the original question to preserve the user's language.

### lib/local_translator.py

```text
LocalTranslator(query_lang, docs_lang, model_name=None)
  .translate(text) -> str
```

- Loads a Helsinki-NLP MarianMT model via `transformers.MarianMTModel` and `MarianTokenizer`.
- Model loaded via `from_pretrained` with `local_files_only=True` first (avoids network calls when cached). Falls back to network download if not cached.
- `model_name`: explicit HuggingFace model ID. If `None`, auto-selects `Helsinki-NLP/opus-mt-{query_lang}-{docs_lang}` (e.g., `query_lang="zh"`, `docs_lang="en"` → `Helsinki-NLP/opus-mt-zh-en`). To use a different model series, pass `model_name` explicitly in `config.json`.
- `HF_ENDPOINT` set to `https://hf-mirror.com` via `os.environ.setdefault` (China mirror, does not override user-set values).
- Class-level cache (`_cache` dict): keyed by model name. Same language pair shares one loaded model across all instances within the process.
- First load downloads from HuggingFace (approx. 300 MB). Subsequent loads read from the local HuggingFace cache (`~/.cache/huggingface/`).
- `translate()`: tokenizes input, runs `model.generate()`, decodes output tokens. Returns the translated string.

### lib/reranker.py

```text
Reranker(model_name="BAAI/bge-reranker-v2-m3")
  .rerank(query, chunks, top_k) -> list[str]
```

- Wraps `sentence_transformers.CrossEncoder` for precision re-ranking of retrieved chunks.
- Two-stage retrieval: vector search (bi-encoder) retrieves `k * 4` candidates, cross-encoder reranks and trims to final `top_k`.
- Cross-encoder encodes (query, chunk) pairs jointly with full attention interaction, yielding higher precision than bi-encoder cosine similarity alone.
- Model loaded with `max_length=512`. First load downloads from HuggingFace; subsequent loads use local cache.
- `rerank()`: scores each (query, chunk) pair, sorts by score descending, returns top_k chunks.
- Initialized by `_init_reranker(config)` when `reranker_enabled` is `true`. Used by `_retrieve_context()` and `cmd_search()`.

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
| Invalid enhancer `mode` value | `ValueError` raised with valid options |
| API network errors | Unhandled exception (stack trace visible) |
| Embedding model download failure | `SentenceTransformer` raises, process exits |
| Chroma persistence errors | Raised by `chromadb`, not caught (disk/permission issue) |
