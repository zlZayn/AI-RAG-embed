"""rag_ask tool: end-to-end RAG QA with retrieval + LLM generation."""

import sys
from pathlib import Path

# Add project root to sys.path so we can import rag_qa
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from rag_qa import (
    _get_retrieval_cfg,
    _init_ask_chat,
    _init_enhancer,
    _retrieve_context,
    load_config,
)
from tools import _mcp_safe

# --- cached state ---
_store = None
_llm = None
_enhancer = None
_system_prompt = None
_reranker = None
_initialized = False


def _get_components():
    global _store, _llm, _enhancer, _system_prompt, _reranker, _initialized
    if not _initialized:
        config = load_config()
        with _mcp_safe():
            _store, _llm, _enhancer, _system_prompt, _reranker = _init_ask_chat(config)
        _initialized = True
    return _store, _llm, _enhancer, _system_prompt, _reranker


def rag_ask(
    question: str,
    enhance: bool = False,
    debug: bool = False,
    k: int | None = None,
) -> str:
    """Ask a question and get an answer grounded in documents.

    Retrieves relevant document chunks, then uses an LLM to generate
    an answer based on the retrieved context.

    Args:
        question: The question to ask.
        enhance: Enable query enhancement (rewrite/translate) for better retrieval.
        debug: Include debug info in output.
        k: Number of chunks to retrieve. Omit to use config default.
    """
    store, llm, enhancer, system_prompt, reranker = _get_components()

    config = load_config()
    retrieval_cfg = _get_retrieval_cfg(config)

    # Override enhance if requested and not already configured
    query_enhancer = enhancer
    if enhance and not query_enhancer:
        with _mcp_safe():
            query_enhancer = _init_enhancer(config)

    retrieval_k = k or retrieval_cfg.get("k", 3)

    with _mcp_safe():
        chunks, messages, _, _ = _retrieve_context(
            store,
            llm,
            question,
            system_prompt,
            retrieval_k=retrieval_k,
            retrieval_distance_threshold=retrieval_cfg.get("distance_threshold"),
            query_enhancer=query_enhancer,
            reranker=reranker,
            reranker_top_k=config.get("reranker", {}).get("top_k"),
            debug=debug,
        )

    if not chunks:
        return "No relevant documents found."

    # Generate answer (non-streaming)
    with _mcp_safe():
        answer = llm.generate(messages)

    return answer
