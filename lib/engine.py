"""Shared initialization and config logic for RAG-QA.

Used by both CLI (rag_qa.py) and MCP server (tools/).
All functions here are public API — no underscore prefix.
"""

import json
import os
import sys
import time
from contextlib import contextmanager

_PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_config() -> dict:
    """Read config.json from the project root."""
    config_path = os.path.join(_PROJECT_DIR, "config.json")
    if not os.path.exists(config_path):
        print(f"[error] config file not found: {config_path}")
        print(
            "[hint] copy config_example.json to config.json and fill in your settings"
        )
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_path(config: dict, key: str) -> str:
    """Resolve a config path value. Relative paths (./) are resolved against the project root."""
    path = config[key]
    if path.startswith("./") or path.startswith(".\\"):
        return os.path.join(_PROJECT_DIR, path[2:])
    return path


def resolve_model_name(config: dict) -> str:
    """Resolve embedding model name. Supports per-lang dict or plain string."""
    model = config["embedding_model_name"]
    if isinstance(model, dict):
        lang = config.get("docs_lang", "en")
        return model.get(lang) or next(iter(model.values()))
    return model


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


@contextmanager
def timed(label: str):
    """Print '[step] label... done [Xs]' around a block."""
    t0 = time.perf_counter()
    print(f"[step] {label}... ", end="", flush=True)
    yield
    print(f"\r\033[K[step] {label}... done [{time.perf_counter() - t0:.1f}s]")


# ---------------------------------------------------------------------------
# Retrieval config helpers
# ---------------------------------------------------------------------------


def get_retrieval_cfg(config: dict) -> dict:
    """Get retrieval config block, with legacy fallback for old config format."""
    if "retrieval" in config:
        return config["retrieval"]
    print(
        "[warn] top-level retrieval_k/retrieval_distance_threshold/enhancer "
        "is deprecated, use retrieval.* instead"
    )
    return {
        "mode": config.get("enhancer", {}).get("mode"),
        "k": config.get("retrieval_k", 3),
        "distance_threshold": config.get("retrieval_distance_threshold"),
        "enhancer": config.get("enhancer", {}),
    }


def get_retrieval_mode(store) -> str:
    """Return the retrieval mode tag: 'hybrid', 'vector', 'bm25', or 'none'."""
    v = store._vector_enabled
    b = store._bm25_enabled
    if v and b:
        return "hybrid"
    if v:
        return "vector"
    if b:
        return "bm25"
    return "none"


def build_indexing_summary(config: dict) -> str:
    """Human-readable summary of indexing config (lang, model, chunking)."""
    lang = config.get("docs_lang", "en")
    model = resolve_model_name(config)
    chunking_cfg = config.get("chunking", {})
    mode = chunking_cfg.get("mode", "auto")
    if mode == "fixed":
        fixed_cfg = chunking_cfg.get("fixed", {})
        split_by = fixed_cfg.get("split_by", "char")
        if split_by == "char":
            cc = fixed_cfg.get("char", {})
            chunk_str = f"fixed(char, max={cc.get('max_chars', 700)}, overlap={cc.get('overlap_chars', 70)})"
        else:
            lc = fixed_cfg.get("line", {})
            chunk_str = f"fixed(line, max={lc.get('max_lines', 20)}, overlap={lc.get('overlap_lines', 3)})"
    else:
        ac = chunking_cfg.get("auto", {})
        chunk_str = f"auto(target={ac.get('target_chars', 700)})"
    return f"lang={lang}, model={model}, chunking={chunk_str}"


def build_retrieval_summary(
    retrieval_cfg: dict, reranker_on: bool, mode_tag: str
) -> str:
    """Human-readable summary of retrieval config (k, threshold, reranker, mode)."""
    k = retrieval_cfg.get("k", 3)
    threshold = retrieval_cfg.get("distance_threshold", "none")
    reranker_str = "on" if reranker_on else "off"
    return f"k={k}, threshold={threshold}, reranker={reranker_str} [{mode_tag}]"


# ---------------------------------------------------------------------------
# Component initialization
# ---------------------------------------------------------------------------


def init_retrieval(config: dict, debug: bool = False):
    """Initialize VectorDb and EmbedEngine. Returns (store, LlmApi class).

    LlmApi is returned as a class (not instance) — the caller decides
    whether and how to instantiate it.
    """
    from lib.llm_api import LlmApi
    from lib.vector_db import VectorDb

    vector_enabled = config.get("vector_enabled", True)
    bm25_enabled = config.get("bm25_enabled", False)

    if not vector_enabled and not bm25_enabled:
        print("[error] At least one of vector_enabled or bm25_enabled must be true.")
        raise SystemExit(1)

    EmbedEngine = None
    if vector_enabled:
        with timed("Importing modules"):
            from lib.embed_engine import EmbedEngine

    model_name = resolve_model_name(config) if vector_enabled else ""
    embed_engine = None
    if vector_enabled:
        lang = config.get("docs_lang", "en")
        with timed("Loading embedding model"):
            embed_engine = EmbedEngine(model_name=model_name, lang=lang)

    with timed("Loading retrieval store"):
        store = VectorDb(
            persist_dir=resolve_path(config, "chroma_persist_dir"),
            embed_engine=embed_engine,
            vector_enabled=vector_enabled,
            bm25_enabled=bm25_enabled,
            model_name=model_name,
            debug=debug,
        )
    return store, LlmApi


def init_llm(config, LlmApi):
    """Create LlmApi instance for answer generation."""
    with timed("Initializing LLM"):
        return LlmApi(
            api_key=config["llm"]["api_key"],
            base_url=config["llm"]["api_base_url"],
            model=config["llm"]["model"],
            temperature=config["llm"].get("temperature", 0.3),
            thinking_mode=config["llm"].get("thinking_mode", False),
        )


def init_enhancer(config: dict):
    """Initialize query enhancer from config. Returns enhancer or None."""
    if not config.get("query_enhance_enabled", False):
        return None

    from lib.llm_api import LlmApi
    from lib.query_enhancer import QueryEnhancer

    retrieval_cfg = get_retrieval_cfg(config)
    enhancer_cfg = retrieval_cfg.get("enhancer", {})
    mode = retrieval_cfg.get("mode")
    docs_lang = config.get("docs_lang", "en")

    with timed("Initializing query enhancer"):
        if mode == "local":
            from lib.local_translator import LocalTranslator

            local_cfg = enhancer_cfg["local"]
            translator = LocalTranslator(
                query_lang=local_cfg["query_lang"],
                docs_lang=docs_lang,
                model_name=local_cfg.get("model_name"),
            )
            return QueryEnhancer(translator=translator, docs_lang=docs_lang)
        elif mode == "llm":
            llm_cfg = enhancer_cfg["llm"]
            enhancer_llm = LlmApi(
                api_key=llm_cfg["api_key"],
                base_url=llm_cfg["api_base_url"],
                model=llm_cfg["model"],
                temperature=llm_cfg.get("temperature", 0.0),
                thinking_mode=llm_cfg.get("thinking_mode", False),
            )
            return QueryEnhancer(llm_api=enhancer_llm, docs_lang=docs_lang)
        else:
            raise ValueError(
                f"Invalid enhancer mode: '{mode}'. Must be 'local' or 'llm'."
            )


def init_reranker(config: dict):
    """Initialize cross-encoder reranker from config. Returns Reranker or None."""
    if not config.get("reranker_enabled", False):
        return None
    from lib.reranker import Reranker

    cfg = config.get("reranker", {})
    with timed("Loading reranker model"):
        return Reranker(model_name=cfg.get("model_name", "BAAI/bge-reranker-v2-m3"))
