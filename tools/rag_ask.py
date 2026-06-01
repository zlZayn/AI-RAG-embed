"""rag_ask tool: end-to-end RAG QA with retrieval + LLM generation."""

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
from rag_qa import _retrieve_context  # noqa: E402
from tools import _mcp_safe  # noqa: E402
from tools.shared_store import (  # noqa: E402
    get_enhancer,
    get_llm,
    get_reranker,
    get_store,
    get_system_prompt,
)


def rag_ask(
    question: str,
    enhance: bool = False,
    k: int | None = None,
) -> str:
    """Ask a question and get an answer grounded in documents.

    Retrieves relevant document chunks, then uses an LLM to generate
    an answer based on the retrieved context.

    Args:
        question: The question to ask.
        enhance: Enable query enhancement (rewrite/translate) for better retrieval.
        k: Number of chunks to retrieve. Omit to use config default.
    """
    store = get_store()
    llm = get_llm()
    enhancer = get_enhancer()
    system_prompt = get_system_prompt()
    reranker = get_reranker()

    config = load_config()
    retrieval_cfg = get_retrieval_cfg(config)

    # Override enhance if requested and not already configured
    query_enhancer = enhancer
    if enhance and not query_enhancer:
        with _mcp_safe():
            query_enhancer = init_enhancer(config)

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
            debug=False,
        )

    if not chunks:
        return "No relevant documents found."

    # Generate answer (non-streaming)
    with _mcp_safe():
        answer = llm.generate(messages)

    return answer
