"""rag_search tool: retrieve relevant document chunks without LLM generation."""

import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.engine import (  # noqa: E402
    get_retrieval_cfg,
    init_enhancer,
    load_config,
)
from tools import _mcp_safe  # noqa: E402
from tools.shared_store import get_reranker, get_store  # noqa: E402


def rag_search(
    question: str,
    enhance: bool = False,
    k: int | None = None,
) -> str:
    """Search documents and return relevant chunks.

    Retrieves document chunks matching the query without LLM generation.
    Useful when you want raw context to reason about yourself.

    Args:
        question: Search query.
        enhance: Enable query enhancement (rewrite/translate) for better retrieval.
        k: Number of chunks to retrieve. Omit to use config default.
    """
    store = get_store()
    config = load_config()
    retrieval_cfg = get_retrieval_cfg(config)
    retrieval_k = k or retrieval_cfg.get("k", 3)
    distance_threshold = retrieval_cfg.get("distance_threshold")

    # Optional query enhancement
    rewritten = question
    if enhance:
        with _mcp_safe():
            enhancer = init_enhancer(config)
        if enhancer:
            with _mcp_safe():
                rewritten = enhancer.enhance(question)

    # Retrieve
    reranker = get_reranker()
    k_for_search = retrieval_k * 4 if reranker else retrieval_k

    with _mcp_safe():
        chunks = store.query(
            rewritten, k=k_for_search, distance_threshold=distance_threshold
        )

    if not chunks:
        return "No relevant documents found."

    # Rerank if available
    if reranker:
        with _mcp_safe():
            top_k = config.get("reranker", {}).get("top_k") or retrieval_k
            chunks = reranker.rerank(rewritten, chunks, top_k=top_k)

    # Format output
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(f"--- Chunk {i} ---\n{chunk}")
    return "\n\n".join(parts)
