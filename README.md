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
python rag_runner.py --build

# 4. Ask a question (interactive mode)
python rag_runner.py
```

> **Note**: The code uses `hf-mirror.com` as the default HuggingFace endpoint. Do not override `HF_ENDPOINT` with `huggingface.co` -- it will cause connection timeouts.

## Usage

### Build Index

Run once, or after documents change.

```bash
python rag_runner.py --build
```

### Interactive Mode

Multi-turn conversation with history.

```bash
python rag_runner.py
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
python rag_runner.py "What is exponential smoothing?"
```

## Configuration

Copy `config_example.json` to `config.json` and edit.

### Document & Retrieval Configuration

| Key | Description |
| --- | --- |
| `docs_dir` | Folder containing your `.txt` / `.md` files. All files (including subfolders) are loaded when running `--build`. Supports `.doc_loader_ignore` for excluding files. |
| `docs_lang` | Language of your documents. The enhancer translates your question into this language before searching. Use `"en"` for English, `"zh"` for Chinese, etc. |
| `chunk_size` | Characters per chunk when building the index. Larger = more context per chunk, but less precise retrieval. Typical range: 300-1000. |
| `chunk_overlap` | Overlapping characters between adjacent chunks. Prevents sentences at chunk boundaries from being split. Recommended: 10-20% of `chunk_size`. |
| `embedding_model_name` | HuggingFace model ID for converting text into vector embeddings. |
| `retrieval_k` | Number of chunks to retrieve per query. More chunks = more context, but longer prompts. Default: 3. |
| `chroma_persist_dir` | Folder where the vector database is saved. Created automatically by `--build`. |
| `query_enhance_enabled` | Enable query enhancement. Translates your question into `docs_lang` before searching. In LLM mode, also replaces technical terms and rewrites follow-up questions using conversation history. In local mode, translation only. |
| `strict_context` | `false` = LLM may use its own knowledge to supplement the answer. `true` = LLM answers **only** from retrieved chunks. |
| `system_rules` | Extra instructions added to the system prompt (e.g., "No emoji. Use $...$ for math formulas."). |

### Enhancer Configuration (`enhancer`)

The enhancer translates your question into the document language before searching. Two backends are available, selected by `mode`.

| Key | Description |
| --- | --- |
| `mode` | `"llm"` = use an LLM API. `"local"` = use a local MarianMT model. |

#### LLM Mode (`mode: "llm"`)

Calls an OpenAI-compatible API. Can translate, replace technical terms, and rewrite follow-up questions using conversation history.

| Key | Description |
| --- | --- |
| `api_base_url` | API endpoint URL (OpenAI-compatible). |
| `api_key` | API key. Keep this secret. |
| `model` | Model name (e.g., `"deepseek-v4-flash"`, `"gpt-3.5-turbo"`). |
| `temperature` | Sampling temperature. Use `0.0` for deterministic results. |
| `thinking_mode` | Enable thinking mode (if supported by your API). |

#### Local Mode (`mode: "local"`)

Runs a MarianMT translation model locally. Fast, offline, no API key needed. Only does translation — does not replace technical terms or rewrite follow-up questions.

| Key | Description |
| --- | --- |
| `src_lang` | Language you ask questions in (e.g., `"zh"`, `"en"`). |
| `model_name` | HuggingFace model ID (optional). If omitted, auto-selects `Helsinki-NLP/opus-mt-{src_lang}-{docs_lang}`. For example, if you ask in Chinese and your docs are in English, it loads `Helsinki-NLP/opus-mt-zh-en`. |

### Answer Generation Model Configuration (`llm`)

The LLM that generates the final answer using the retrieved chunks.

| Key | Description |
| --- | --- |
| `api_base_url` | API endpoint URL (OpenAI-compatible). |
| `api_key` | API key. Keep this secret. |
| `model` | Model name (e.g., `"deepseek-v4-flash"`, `"gpt-4"`). |
| `temperature` | Lower = more focused, higher = more creative. Range: 0.0-2.0. |
| `thinking_mode` | Enable thinking mode (if supported by your API). |

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

Each round file contains the question, answer, processed question (labeled "Enhanced Question" in LLM mode or "Translated Question" in local mode), and the retrieved chunks used.

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
