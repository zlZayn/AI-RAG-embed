# Architecture

## Design Philosophy

RAG fails at two boundaries: how you cut, and how you ask. Everything else is compounding marginal gains on top.

**Chunking.** Bad chunks — split mid-sentence, mid-table, mid-thought — are irrecoverable. No embedding model can represent what was never coherent. Structural awareness (heading boundaries, atomic tables, code blocks) ensures each chunk carries a complete idea.

**Retrieval.** Vector search alone is a single point of failure. BM25 keyword matching catches exact terms that embeddings miss (technical names, abbreviations, proper nouns). Cross-encoder reranking rescues precision when cosine similarity is insufficient. Multiple retrieval signals fused together are more robust than any one alone.

**Queries.** Terse, ambiguous questions using different vocabulary than the documents retrieve the wrong chunks even when the right ones exist. The enhancer rewrites the question into a dense retrieval paragraph optimized for vector similarity. It is used only for retrieval; the answer LLM always receives the original question.

Each layer addresses a distinct failure mode. No single layer is sufficient; together they close the gap between what the user means and what the system can find.

## Overview

Local RAG system with two phases:

### Build Phase (`--build`)

1. Load all `.txt`, `.md`, and `.typ` files from `documents/` directory, computing MD5 hashes for change detection
2. Split files into text chunks at natural boundaries (paragraph > sentence > word)
3. Check for file changes and embedding model changes against stored metadata; skip if none (only with `--build`)
4. If the embedding model changed, automatically force a full rebuild (delete collection, re-embed all)
5. Convert chunks to vector embeddings using a local embedding model
6. Store embeddings and original text in a Chroma vector database
7. If BM25 is enabled, build a keyword index from the same chunks

### Query Phase

1. (Optional) Enhance user question for retrieval. In LLM mode, generate a retrieval-optimized paragraph in `docs_lang`. In local mode, translate to `docs_lang`. For follow-up questions, rewrite using conversation history first
2. Retrieve top-k chunks via hybrid retrieval (vector similarity + BM25 keyword matching, merged with Reciprocal Rank Fusion) or vector-only search
3. (Optional) Rerank retrieved chunks with a cross-encoder model for precision re-ranking. Retrieves `retrieval_k * 4` candidates from vector search, then reranks and trims to `retrieval_k`
4. Send **original** question + retrieved chunks to a remote LLM as context (enhanced question is retrieval-only, preserving the user's language for the answer)
5. Generate answer and save to `output/` directory

## Directory Structure

```text
rag_qa.py               # single entry point
config.json             # runtime config (gitignored)
config_example.json     # config template (committed)
documents/              # raw .txt / .md / .typ files
chroma_db/              # persisted Chroma DB (generated, gitignored)
output/                 # conversation logs (generated, gitignored)
lib/
├── __init__.py
├── doc_loader.py       # os.walk + smart boundary chunking + ignore patterns + file hashing
├── embed_engine.py     # SentenceTransformer wrapper with language-based query prefix
├── vector_db.py        # Chroma PersistentClient + BM25 hybrid retrieval + model change detection
├── bm25_retriever.py   # BM25 keyword retriever (jieba tokenization + rank-bm25)
├── llm_api.py          # openai.OpenAI wrapper
├── query_enhancer.py   # query enhancement (retrieval-optimized rewriting)
├── local_translator.py # MarianMT local translation backend
└── reranker.py         # cross-encoder reranker for precision re-ranking
```

## Configuration

`rag_qa.py` reads `config.json` at startup. No lib module reads the config directly -- they receive only the parameters they need. "Default" below refers to the code's hardcoded fallback when a key is omitted.

| Field | Group | Description |
| --- | --- | --- |
| `docs_dir` | Indexing | Source document directory |
| `docs_lang` | Indexing | Document language (`"en"`, `"zh"`, etc.). Controls embedding model selection and query prefix. |
| `chunking` | Indexing | Chunking config: `mode` (`"auto"` / `"fixed"`), plus mode-specific sub-keys (`auto.target_chars`, `fixed.max_chars`). See `config_example.json`. |
| `embedding_model_name` | Indexing | Embedding model config. String (single model) or object mapping `docs_lang` values to model IDs (e.g., `{"zh": "...", "en": "..."}`). Auto-selected by `docs_lang`. |
| `chroma_persist_dir` | Indexing | Chroma persistence directory |
| `query_enhance_enabled` | Enhancement | Enable query enhancement (Default: `false`) |
| `enhancer` | Enhancement | Enhancer config with mode switch: `"llm"` (retrieval-optimized paragraph) or `"local"` (MarianMT translation). Each mode has its own `distance_threshold`. |
| `bm25_enabled` | Retrieval | Enable BM25 keyword retrieval alongside vector search. Results merged via Reciprocal Rank Fusion (RRF). Improves exact term matching (Default: `false`) |
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
python rag_qa.py --enhance "question"  →  cmd_ask(use_enhancer=True)  (single-shot with enhancement)
python rag_qa.py --search "q"          →  cmd_search()           (retrieve only, no enhancer)
python rag_qa.py --search --enhance "q"→  cmd_search(use_enhancer=True)  (retrieve with enhancement)
python rag_qa.py --build               →  cmd_build()            (incremental build)
python rag_qa.py --rebuild             →  cmd_build(force=True)  (full rebuild)
```

Optional CLI overrides: `--retrieval_k`, `--retrieval_distance_threshold`, `--strict_context`, `--enhance`. These override the corresponding `config.json` fields; if omitted, config values (or code defaults) are used. CLI override takes highest priority, even over per-mode enhancer thresholds.

Only query-time parameters are exposed as CLI overrides. Indexing parameters (`chunking`, `embedding_model_name`) are intentionally excluded: changing `chunking` requires a full `--rebuild`; changing `embedding_model_name` is auto-detected by `--build` and triggers a full rebuild automatically.

Heavy imports (`sentence-transformers`, `chromadb`, `openai`) are lazy-loaded via `_import_lib()`. `cmd_ask` and `cmd_chat` call it through `_init_ask_chat()`, which delegates embedding+vector-store init to `_init_embed_store()`. `cmd_search` and `cmd_build` call `_init_embed_store()` directly (skipping LLM init). `cmd_search` with `--enhance` additionally calls `_init_enhancer()` to initialize the query enhancer. `cmd_build` initializes the embed store early to check for model changes via `store.get_meta_model()`; if the model changed, it forces a full rebuild before checking file hashes.

Progress messages use the `_timed(label)` context manager for consistent `[step] {label}... done [Xs]` formatting.

## Build Workflow

```text
cmd_build()
├─► doc_loader.load_documents(docs_dir, config)
│   ├─ pre-scan: walk tree, collect .doc_loader_ignore specs
│   ├─ os.walk: collect .txt/.md/.typ files, skip ignored
│   ├─ read UTF-8 content, compute MD5 hash per file
│   └─ smart split: auto mode (md/typ: heading-aware; txt: paragraph-first) or fixed mode (separator-priority fallback)
│       returns (chunks, file_hashes)
│       chunks: [{"text": str, "source": "relative/path"}, ...]
│       file_hashes: {"relative/path": "md5hex", ...}
│
├─► _init_embed_store(config)
│   ├─ _resolve_model_name(config)  →  model name (resolves nested per-lang config)
│   ├─ _import_lib()  →  EmbedEngine, LlmApi, VectorDb
│   ├─ embed_engine.EmbedEngine(model_name, lang=docs_lang)
│   │   └─ SentenceTransformer(model_name)
│   └─ vector_db.VectorDb(persist_dir, embed_engine, bm25_enabled, model_name)
│
├─► model change detection
│   ├─ store.get_meta_model()  →  old model from build_meta.json._model
│   ├─ _resolve_model_name(config)  →  new model from config
│   └─ if different → print "[info] model changed: ... -> ..., forcing full rebuild", force=True
│
├─► _has_file_changes(persist_dir, file_hashes)  (skipped if force=True)
│   ├─ read build_meta.json directly (json.load, no heavy imports)
│   ├─ compare keys + hash values
│   └─ if no changes → print "[info] no changes detected, skipping", return early
│
└─► store.rebuild / store.rebuild_full
    ├─ --build:   .rebuild(chunks, file_hashes)       # incremental
    └─ --rebuild: .rebuild_full(chunks, file_hashes)   # delete collection, recreate, re-embed
```

`--rebuild` skips change detection and forces a full delete-collection-then-add cycle. `--build` reads `build_meta.json` via stdlib `json` only — no `sentence-transformers`, `chromadb`, or `openai` imported when no files changed.

Change detection compares both the embedding model name (stored as `_model` in `build_meta.json`) and file content hashes. When the model changes, `--build` automatically triggers a full rebuild — no manual `--rebuild` needed. The collection is deleted and recreated to handle dimension changes between models.

`rebuild()` performs incremental updates by comparing file content hashes stored in `build_meta.json`. Only changed, added, or removed files are re-embedded. `rebuild_full()` deletes the entire Chroma collection and recreates it (to handle embedding dimension changes), then re-embeds all chunks.

When `bm25_enabled` is true, both `rebuild()` and `rebuild_full()` sync the BM25 keyword index after updating the vector store.

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
├─► print "[step] processing..."
│
├─► [optional] query_enhancer.enhance(question, messages_history)
│   ├─ LLM mode:
│   │   Without history: generate retrieval-optimized paragraph in docs_lang
│   │   With history: rewrite as standalone query (resolve pronouns/ellipsis), then generate retrieval paragraph
│   └─ Local mode: translate to docs_lang via MarianMT (no rewrite, no term replacement)
│
├─► print "[step] retrieving..."
├─► k_for_search = retrieval_k * 4  (if reranker enabled, else retrieval_k)
├─► store.query(rewritten_question, k_for_search, distance_threshold)
│   ├─ [if bm25_enabled] _hybrid_query():
│   │   ├─ vector search: embed query → Chroma cosine similarity → 2k candidates
│   │   ├─ BM25 search: jieba tokenize query → rank_bm25 → 2k candidates
│   │   ├─ RRF fusion: score = Σ 1/(60 + rank) per candidate across both lists
│   │   └─ sort by fused score, return top-k
│   │
│   └─ [if bm25_disabled] vector-only:
│       ├─ embed_engine.get_embedding(rewritten_question)  →  vector
│       ├─ collection.query(query_embeddings, n_results=k_for_search)
│       │   Chroma cosine similarity search
│       │   returns top-k_for_search document chunks
│       └─ filter by distance_threshold (if set)
│           discard chunks with distance >= threshold
│           if none pass, return top-1 as fallback
│
├─► [optional] reranker.rerank(rewritten_question, chunks, top_k=retrieval_k)
│   ├─ CrossEncoder.predict([(query, chunk) ...])  →  scores
│   ├─ sort by score descending
│   └─ return top retrieval_k chunks
│
├─► print "[step] retrieved N chunks, generating..."
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
- Pre-scans for `.doc_loader_ignore` files (`.gitignore` syntax via `pathspec`). Supports ignoring entire directories (e.g., `r4ds_textbook/`).
- Each chunk carries its source file path relative to `docs_dir`.
- Computes MD5 hash per file for incremental rebuild detection.
- Skips empty files.
- Supported extensions: `.txt`, `.md`, `.typ`. Files with other extensions are silently skipped.
- Two chunking modes controlled by `chunking.mode`:

**auto mode** (default, `chunking.auto`):

- `.md` files: parses Markdown into structural units (headings, paragraphs, code blocks, tables), groups by heading level (`split_at_level`), then merges within sections. Code blocks and tables are atomic — never split even if they exceed `target_chars`.
- `.typ` files: parses Typst into structural units (headings via `= `, tables via `#figure`/`#table`, blockquotes via `#quote`, code blocks, paragraphs). Skips preamble (`#set`/`#show`/`#let`), comments (`//`), and non-content elements. Groups by heading level, same as Markdown. Code blocks and tables are atomic.
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
EmbedEngine(model_name, lang="en")
  .get_embedding(text) -> list[float]
  .embed_batch(texts) -> list[list[float]]
```

- Wraps `SentenceTransformer`.
- Sets `HF_ENDPOINT=https://hf-mirror.com` via `os.environ.setdefault` (China mirror, does not override user-set values).
- Model loaded with `local_files_only=True` first, falls back to network download if not cached.
- Query prefix is language-dependent, selected by `lang` parameter (from `docs_lang` config):
  - `"zh"`: `"为这个句子生成表示以用于检索中文文档: "`
  - `"en"`: `"Represent this sentence for searching relevant passages: "`
  - Fallback: English prefix
- `get_embedding(text)` prepends the language-appropriate query prefix before encoding. `embed_batch(texts)` does **not** add the prefix — document embeddings should be encoded as-is for correct semantic alignment with query embeddings.

### lib/vector_db.py

```text
VectorDb(persist_dir, embed_engine=None, bm25_enabled=False, model_name="")
  .rebuild(chunks, file_hashes) -> None        # incremental: only re-embed changed files
  .rebuild_full(chunks, file_hashes) -> None    # delete collection, recreate, re-embed all
  .query(question, k, distance_threshold=None) -> list[str]
  .get_meta_model() -> str | None              # read stored model name from build_meta.json
```

- `chromadb.PersistentClient` with cosine distance (`hnsw:space: "cosine"`).
- Collection name: `"documents"`. Telemetry disabled.
- `rebuild()` prints an incremental summary: `[info] incremental: +N new, ~N updated, -N removed, total N chunks`.
- `rebuild_full()` deletes and recreates the collection (not just clears entries) to handle embedding dimension changes when switching models.
- `build_meta.json` stores `_model` alongside file hashes for model change detection.
- When `bm25_enabled`, `query()` delegates to `_hybrid_query()` which runs vector search and BM25 in parallel, then merges results via Reciprocal Rank Fusion (RRF): `score = Σ 1/(60 + rank)` per candidate across both ranked lists. The BM25 index is synced after every `rebuild()` and `rebuild_full()` call.

### lib/bm25_retriever.py

```text
BM25Retriever()
  .build(texts: list[str]) -> None
  .query(query: str, k: int) -> list[tuple[int, float]]
  .ready -> bool
```

- Wraps `rank_bm25.BM25Okapi` for keyword-based document retrieval.
- Tokenization: uses `jieba.lcut()` for Chinese text segmentation when jieba is available; falls back to character-level splitting otherwise. Punctuation and whitespace tokens are filtered out.
- `build()` tokenizes all documents and constructs the BM25 index. Called after every vector store rebuild.
- `query()` tokenizes the query, computes BM25 scores against the index, returns top-k `(index, score)` pairs.
- Complements vector search: BM25 excels at exact term matching (technical names, abbreviations, proper nouns) where semantic embeddings may fail.

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
- Retry logic: 3 attempts with exponential backoff (1s, 2s, 4s). Prints `[retry]` status on each attempt; raises after final failure.

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

Returns the result as a single string. If the LLM call fails, prints a `[warn]` message and falls back to the original question. Used **only for retrieval** — the answer LLM always receives the original question to preserve the user's language.

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
| `documents/` not found at build time | `[error]` + `[hint]`, exit code 1 |
| No `.txt`/`.md`/`.typ` files found | `[error]`, exit code 1 |
| Config file not found | `[error]` + `[hint]`, exit code 1 |
| No relevant chunks for a question | `[info]`, skip round |
| API network errors | `[retry]` 3x with backoff (1s, 2s, 4s); `[error]` after final failure |
| Query enhancement failure | `[warn]`, fall back to original question |
| Embedding model not cached | `[load]` download status, download from HuggingFace |
| Translation model not cached | `[load]` download status, download from HuggingFace |
| Invalid enhancer `mode` value | `ValueError` raised with valid options |
| Chroma persistence errors | Raised by `chromadb`, not caught (disk/permission issue) |
