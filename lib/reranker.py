from __future__ import annotations

from sentence_transformers import CrossEncoder

from lib.log import log_debug


class Reranker:
    """Cross-encoder reranker for precision re-ranking of retrieved chunks.

    Uses a CrossEncoder model to score (query, chunk) pairs, then returns
    the top-k chunks sorted by relevance score descending.
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self._model = CrossEncoder(model_name, max_length=512)

    def rerank(
        self, query: str, chunks: list[str], top_k: int, debug: bool = False
    ) -> list[str]:
        """Re-rank chunks by relevance to query, return top_k results.

        Args:
            query: The search query (original or enhanced).
            chunks: Candidate chunks from vector retrieval.
            top_k: Number of chunks to return after re-ranking.

        Returns:
            Top-k chunks sorted by cross-encoder score, descending.
        """
        if not chunks:
            return []

        pairs = [(query, chunk) for chunk in chunks]
        scores = self._model.predict(pairs)

        ranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)

        if debug:
            log_debug("reranker scores")
            for i, (chunk, score) in enumerate(ranked):
                kept = " *" if i < top_k else ""
                log_debug(f"  chunk {i + 1}: score={score:.4f}{kept}")
                log_debug(f"    preview: {chunk[:80]}...")
            log_debug(f"  (* = kept, top {top_k} of {len(chunks)})")

        return [chunk for chunk, _ in ranked[:top_k]]
