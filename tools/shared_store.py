"""Shared store cache for all MCP tools.

Centralizes component initialization so that:
- All three tools (rag_get_info, rag_search, rag_ask) share one store instance
- Warm-up at server startup avoids cold-start timeout on first tool call
- Stale detection via build_meta.json mtime auto-refreshes after --build
"""

import os
import threading

from rag_qa import _init_ask_chat, _resolve_path, load_config
from tools import _mcp_safe

# --- cached components ---
_store = None
_llm = None
_enhancer = None
_system_prompt = None
_reranker = None
_initialized = False

# --- synchronization ---
_lock = threading.Lock()
_ready_event = threading.Event()

# --- staleness detection ---
_meta_mtime: float = 0.0
_meta_path: str = ""


def _get_meta_mtime(path: str) -> float:
    """Get build_meta.json modification time (cheap stat call)."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _is_stale() -> bool:
    """Check if the index was rebuilt externally (via --build)."""
    if not _initialized or not _meta_path:
        return False
    return _get_meta_mtime(_meta_path) != _meta_mtime


def _do_init() -> None:
    """Full initialization of all components."""
    global _store, _llm, _enhancer, _system_prompt, _reranker
    global _initialized, _meta_mtime, _meta_path

    config = load_config()
    with _mcp_safe():
        _store, _llm, _enhancer, _system_prompt, _reranker = _init_ask_chat(config)

    chroma_dir = _resolve_path(config, "chroma_persist_dir")
    _meta_path = os.path.join(chroma_dir, "build_meta.json")
    _meta_mtime = _get_meta_mtime(_meta_path)
    _initialized = True


def warm_up() -> None:
    """Background warm-up at server startup. Thread-safe."""
    with _lock:
        if _initialized:
            return
        _do_init()
    _ready_event.set()


def _ensure_ready() -> None:
    """Guarantee cache is available: wait for warm-up + detect staleness."""
    # Wait for initial warm-up to complete
    if not _initialized:
        _ready_event.wait()
    # Check if index was rebuilt externally
    if _is_stale():
        with _lock:
            if _is_stale():  # double-check under lock
                _do_init()


def get_store():
    """Get the shared VectorDb store."""
    _ensure_ready()
    return _store


def get_llm():
    """Get the shared LLM client."""
    _ensure_ready()
    return _llm


def get_enhancer():
    """Get the shared query enhancer (may be None)."""
    _ensure_ready()
    return _enhancer


def get_system_prompt():
    """Get the shared system prompt."""
    _ensure_ready()
    return _system_prompt


def get_reranker():
    """Get the shared reranker (may be None)."""
    _ensure_ready()
    return _reranker
