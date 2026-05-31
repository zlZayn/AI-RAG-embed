"""rag_get_info tool: return RAG system config, indexed documents, and paths."""

import json
import os
import sys
from collections import Counter
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lib.doc_loader import _collect_ignore_specs, _is_ignored  # noqa: E402
from rag_qa import (  # noqa: E402
    _build_indexing_summary,
    _build_retrieval_summary,
    _get_retrieval_cfg,
    _get_retrieval_mode,
    _resolve_path,
    load_config,
)
from tools.shared_store import get_store  # noqa: E402


def _list_source_files(docs_dir: str) -> list[str]:
    """List document source files on disk, respecting .doc_loader_ignore."""
    ignore_specs = _collect_ignore_specs(docs_dir)
    sources = []
    for root, _, files in os.walk(docs_dir):
        for filename in files:
            if filename == ".doc_loader_ignore":
                continue
            if not filename.endswith((".txt", ".md", ".typ")):
                continue
            filepath = os.path.join(root, filename)
            if _is_ignored(filepath, ignore_specs):
                continue
            sources.append(os.path.relpath(filepath, docs_dir))
    return sorted(sources)


def _count_chunks_per_file(store) -> tuple[int, dict[str, int]]:
    """Get total chunk count and per-file breakdown from the index."""
    sources = store._bm25_sources
    total = len(sources)
    per_file = dict(Counter(sources))
    return total, per_file


def _load_indexed_hashes(chroma_dir: str) -> dict[str, str]:
    """Read indexed file hashes from bm25_store.json or build_meta.json."""
    # Try bm25_store.json first (authoritative in BM25-only mode)
    bm25_path = os.path.join(chroma_dir, "bm25_store.json")
    if os.path.exists(bm25_path):
        with open(bm25_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        hashes = data.get("file_hashes", {})
        if hashes:
            return hashes

    # Fallback: build_meta.json (vector/hybrid mode)
    meta_path = os.path.join(chroma_dir, "build_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: v for k, v in raw.items() if not k.startswith("_")}

    return {}


def rag_get_info() -> dict:
    """Get RAG system info: config, indexed documents, and paths.

    Returns current retrieval/indexing config, lists source documents
    on disk vs in the index, and reports chunk counts per file.
    Useful for understanding what the RAG system can search before querying it.
    """
    config = load_config()
    retrieval_cfg = _get_retrieval_cfg(config)

    # --- static config ---
    store = get_store()
    mode = _get_retrieval_mode(store)
    reranker_on = config.get("reranker_enabled", False)
    retrieval_summary = _build_retrieval_summary(retrieval_cfg, reranker_on, mode)
    indexing_summary = _build_indexing_summary(config)

    docs_dir = _resolve_path(config, "docs_dir")
    chroma_dir = _resolve_path(config, "chroma_persist_dir")

    # --- dynamic index state ---
    sources_on_disk = _list_source_files(docs_dir)
    indexed_hashes = _load_indexed_hashes(chroma_dir)
    total_chunks, per_file = _count_chunks_per_file(store)

    return {
        "retrieval": {
            "mode": mode,
            "summary": retrieval_summary,
            "query_enhance": config.get("query_enhance_enabled", False),
        },
        "indexing": {
            "summary": indexing_summary,
        },
        "documents": {
            "sources_on_disk": sources_on_disk,
            "indexed_file_hashes": indexed_hashes,
            "total_chunks": total_chunks,
            "per_file": per_file,
        },
        "paths": {
            "docs_dir": docs_dir,
            "chroma_dir": chroma_dir,
        },
    }
