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

**Interactive mode** (multi-turn conversation with history):

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

**Single-question mode** (one-shot, saves result to `output/`):

```bash
python rag_runner.py "What is exponential smoothing?"
```

## Configuration

Copy `config_example.json` to `config.json` and edit.

### Document & Retrieval Configuration

| Key | Description |
| --- | --- |
| `docs_dir` | Root directory for your `.txt` / `.md` files. All files in this directory (and subdirectories) will be loaded when running `--build`. Supports `.doc_loader_ignore` filtering to exclude specific files. |
| `docs_lang` | Target language for query enhancement. The enhancer will translate and rephrase the question into this language to match your documents. Use `"en"` for English, `"zh"` for Chinese, etc. |
| `chunk_size` | Number of characters per text chunk when building the vector index. Larger chunks preserve more context but may dilute retrieval precision. Typical range: 300-1000. |
| `chunk_overlap` | Number of overlapping characters between adjacent chunks. Prevents semantic fragmentation when concepts span chunk boundaries. Recommended: 10-20% of `chunk_size`. |
| `embedding_model_name` | HuggingFace model ID used to convert text chunks and queries into vector embeddings. |
| `retrieval_k` | Number of top-ranked chunks retrieved for each query. More chunks provide more context but increase prompt length and LLM cost. Defaults to 3 if not set. |
| `chroma_persist_dir` | Directory where the vector database is stored. Automatically created when running `--build`. |
| `query_enhance_enabled` | Whether to enable query enhancement. When enabled, the enhancer translates and rephrases the question into `docs_lang`, replacing technical terms with their equivalents, to improve retrieval accuracy. In interactive mode, conversation history is used to resolve pronouns and ellipsis (e.g., "what about the second type" → fully rewritten standalone query). |
| `strict_context` | Controls how the LLM uses its own knowledge. `false` = LLM may blend retrieved context with its own knowledge. `true` = LLM must answer **only** from retrieved chunks and will say "I don't know" if context is insufficient. |
| `system_rules` | Free-text instructions that are always included in the system prompt. Use to enforce output format, tone, or constraints (e.g., "No emoji. Use $...$ for math formulas."). |

### Enhancer Model Configuration (`enhancer`)

The enhancer model translates and rephrases the user's question into the document language, replacing technical terms with their equivalents. Use a small, fast model for this.

| Key | Description |
| --- | --- |
| `api_base_url` | API endpoint URL for the enhancer model (OpenAI-compatible). |
| `api_key` | API key for authentication. Keep this secret. |
| `model` | Model identifier (e.g., `"deepseek-chat"`, `"gpt-3.5-turbo"`). |
| `temperature` | Sampling temperature for translation. Use `0.0` for deterministic results. |
| `thinking_mode` | Enable thinking mode (if supported by your API). |

### Answer Generation Model Configuration (`llm`)

The LLM model generates the final answer from retrieved chunks.

| Key | Description |
| --- | --- |
| `api_base_url` | API endpoint URL for the answer generation model (OpenAI-compatible). |
| `api_key` | API key for authentication. Keep this secret. |
| `model` | Model identifier (e.g., `"deepseek-chat"`, `"gpt-4"`). |
| `temperature` | Sampling temperature for answer generation. Lower = more deterministic, higher = more creative. Range: 0.0-2.0. |
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

Each round file contains the question, answer, enhanced question trace (if query enhancement is enabled), and sanitized retrieved context -- each wrapped in a code fence to prevent Markdown corruption.

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
└── query_enhancer.py   # query enhancement (question translation + rewording)
```

## Requirements

- Python 3.10+
- Dependencies: `sentence-transformers`, `chromadb`, `openai`, `pathspec`

See `ARCHITECTURE.md` for details on GPU acceleration, HuggingFace mirror setup, and design decisions.
