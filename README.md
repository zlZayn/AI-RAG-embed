# AI-RAG-embed

Local RAG (Retrieval-Augmented Generation) knowledge base. Ask questions about your documents and get answers backed by the actual content.

Embedding runs locally. Answer generation uses a remote LLM API.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Put your .txt / .md files in documents/

# 3. Build the vector index (first time, or after changing documents)
python rag_runner.py --build

# 4. Start asking questions
python rag_runner.py
```

## Configuration

Copy `config.json.example` (if provided) or create `config.json`:

```json
{
    "docs_dir": "./documents",
    "embedding_model_name": "mixedbread-ai/mxbai-embed-large-v1",
    "chroma_persist_dir": "./chroma_db",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "api_key": "your-api-key",
    "api_base_url": "https://your-api.com/v1",
    "llm_model": "your-model-name"
}
```

| Key | Description |
| --- | --- |
| `docs_dir` | Directory containing your `.txt` / `.md` files |
| `embedding_model_name` | HuggingFace model ID for embeddings |
| `chroma_persist_dir` | Where to store the vector database |
| `chunk_size` | Characters per text chunk |
| `chunk_overlap` | Overlapping characters between adjacent chunks |
| `api_key` | API key for the LLM service |
| `api_base_url` | Base URL of the OpenAI-compatible API |
| `llm_model` | Model name to pass to the API |

## Usage

**Interactive mode** (multi-turn conversation):

```bash
python rag_runner.py
```

Type your question and press Enter. The system retrieves the 3 most relevant document chunks and sends them as context to the LLM.

```text
>>> What is the GIL?
thinking...

The GIL (Global Interpreter Lock) allows only one thread to execute
Python bytecode at a time. Multiprocessing bypasses it by spawning
separate processes.
```

Type `/exit`, `/quit`, or `/q` to quit.

**Single-question mode** (one-shot, result saved to `output/`):

```bash
python rag_runner.py "What is a tsibble object in R?"
```

Conversation logs are saved to `output/<session>/` as numbered Markdown files.

## Document Filtering

Place a `.doc_loader_ignore` file in any document subdirectory to exclude files from indexing. Uses `.gitignore` syntax.

```text
# documents/fpp3_textbook/.doc_loader_ignore
README.md       # skip table-of-contents files
*.log           # skip log files
_draft/         # skip draft directories
```

Patterns apply to the directory containing the ignore file and all its subdirectories.

## Project Structure

```text
├── rag_runner.py          # entry point (--build | chat)
├── config.json            # your configuration
├── documents/             # put your files here
│   └── .doc_loader_ignore # optional: exclude patterns
├── output/                # conversation exports
├── lib/
│   ├── doc_loader.py      # file reading + text chunking + ignore
│   ├── embed_engine.py    # embedding model (mxbai)
│   ├── vector_db.py       # Chroma vector store
│   └── llm_api.py         # remote LLM API client
└── ARCHITECTURE.md        # detailed architecture doc
```

See `ARCHITECTURE.md` for full details on data flow, module internals, GPU setup, and design decisions.

## Requirements

- Python 3.10+
- NVIDIA GPU + CUDA PyTorch for fast embedding (see ARCHITECTURE.md)
- `sentence-transformers` -- embedding model (3.x recommended)
- `chromadb` -- vector store
- `openai` -- LLM API client
- `pathspec` -- `.doc_loader_ignore` pattern matching
