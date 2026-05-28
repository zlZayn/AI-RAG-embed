import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from typing import NamedTuple

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from lib.doc_loader import load_documents


def _import_lib():
    from lib.embed_engine import EmbedEngine
    from lib.llm_api import LlmApi
    from lib.vector_db import VectorDb

    return EmbedEngine, LlmApi, VectorDb


@contextmanager
def _timed(label: str):
    t0 = time.perf_counter()
    print(f"[step] {label}... ", end="", flush=True)
    yield
    print(f"\r\033[K[step] {label}... done [{time.perf_counter() - t0:.1f}s]")


def _resolve_model_name(config: dict) -> str:
    model = config["embedding_model_name"]
    if isinstance(model, dict):
        lang = config.get("docs_lang", "en")
        return model.get(lang) or next(iter(model.values()))
    return model


def _init_retrieval(config: dict, debug: bool = False):
    from lib.llm_api import LlmApi
    from lib.vector_db import VectorDb

    vector_enabled = config.get("vector_enabled", True)
    bm25_enabled = config.get("bm25_enabled", False)

    if not vector_enabled and not bm25_enabled:
        print("[error] At least one of vector_enabled or bm25_enabled must be true.")
        raise SystemExit(1)

    EmbedEngine = None
    if vector_enabled:
        with _timed("Importing modules"):
            from lib.embed_engine import EmbedEngine

    model_name = _resolve_model_name(config) if vector_enabled else ""
    embed_engine = None
    if vector_enabled:
        lang = config.get("docs_lang", "en")
        with _timed("Loading embedding model"):
            embed_engine = EmbedEngine(model_name=model_name, lang=lang)

    with _timed("Loading retrieval store"):
        store = VectorDb(
            persist_dir=_resolve_path(config, "chroma_persist_dir"),
            embed_engine=embed_engine,
            vector_enabled=vector_enabled,
            bm25_enabled=bm25_enabled,
            model_name=model_name,
            debug=debug,
        )
    return store, LlmApi


_SYSTEM_BASE_STRICT = (
    "You are a helpful assistant. Answer the user's question based ONLY on the provided context. "
    "If the answer is not in the context, say 'I don't know'. "
    "Always respond in the same language as the user's question."
)

_SYSTEM_BASE = (
    "You are a helpful assistant. Use the provided context to enrich your answer, "
    "but also draw on your own knowledge when the context is insufficient. "
    "If the context is provided, prefer it over your own knowledge for factual claims. "
    "Always respond in the same language as the user's question."
)

_PROJECT_DIR = os.path.dirname(__file__)


def load_config() -> dict:
    config_path = os.path.join(_PROJECT_DIR, "config.json")
    if not os.path.exists(config_path):
        print(f"[error] config file not found: {config_path}")
        print(
            "[hint] copy config_example.json to config.json and fill in your settings"
        )
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_path(config: dict, key: str) -> str:
    path = config[key]
    if path.startswith("./") or path.startswith(".\\"):
        return os.path.join(_PROJECT_DIR, path[2:])
    return path


def _build_system_prompt(rules: str, strict_context: bool = False) -> str:
    base = _SYSTEM_BASE_STRICT if strict_context else _SYSTEM_BASE
    if not rules:
        return base
    return base + "\n\n" + rules


def _sanitize_name(text: str, max_len: int = 60) -> str:
    name = text.strip().replace(" ", "_")
    name = re.sub(r"[^\w\-]", "", name)
    return name[:max_len]


def _init_output_dir(first_question: str) -> str:
    output_root = os.path.join(_PROJECT_DIR, "output")
    os.makedirs(output_root, exist_ok=True)

    prefix = _sanitize_name(first_question)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dirname = f"{prefix}_{stamp}"
    dirpath = os.path.join(output_root, dirname)
    os.makedirs(dirpath, exist_ok=True)
    return dirpath


def _sanitize_chunk(text: str) -> str:
    """Remove leading/trailing backtick debris from chunk boundaries."""
    text = text.strip("`")
    text = text.replace("```", "``")
    return text


def _write_round_header(
    filepath: str,
    index: int,
    question: str,
    rewritten_question: str | None = None,
    enhance_label: str = "Enhanced Question",
) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"========== *Round {index}* ==========\n\n")
        f.write(f"**Question:**\n\n```text\n{question}\n```\n\n")
        if rewritten_question and rewritten_question != question:
            f.write(f"**{enhance_label}:**\n\n```text\n{rewritten_question}\n```\n\n")
        f.write("**Answer:**\n\n")


def _write_round_context(
    filepath: str,
    chunks: list[str],
) -> None:
    safe_chunks = [_sanitize_chunk(c) for c in chunks]
    context_blocks = "\n\n".join(f"```text\n{c}\n```" for c in safe_chunks)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"\n\n========== *Retrieved Context* ==========\n\n{context_blocks}\n")


def _export_round(
    out_dir: str,
    index: int,
    question: str,
    chunks: list[str],
    answer: str,
    rewritten_question: str | None = None,
    enhance_label: str = "Enhanced Question",
) -> None:
    safe_chunks = [_sanitize_chunk(c) for c in chunks]
    context_blocks = "\n\n".join(f"```text\n{c}\n```" for c in safe_chunks)

    parts = [
        f"========== *Round {index}* ==========\n\n",
        f"**Question:**\n\n```text\n{question}\n```\n\n",
    ]
    if rewritten_question and rewritten_question != question:
        parts.append(f"**{enhance_label}:**\n\n```text\n{rewritten_question}\n```\n\n")
    parts.append(f"**Answer:**\n\n{answer}\n\n")
    parts.append(f"========== *Retrieved Context* ==========\n\n{context_blocks}\n")

    filepath = os.path.join(out_dir, f"{index:02d}_round.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("".join(parts))


class RetrieveResult(NamedTuple):
    chunks: list[str]
    messages: list[dict] | None
    rewritten_question: str
    enhance_label: str


def _retrieve_context(
    store,
    llm,
    question,
    system_prompt,
    retrieval_k,
    retrieval_distance_threshold=None,
    query_enhancer=None,
    messages_history=None,
    reranker=None,
    reranker_top_k=None,
) -> RetrieveResult:
    """检索相关文档块。"""
    rewritten_question = question
    enhance_label = "Enhanced Question"

    print("[step] processing... ", end="", flush=True)

    if query_enhancer:
        rewritten_question = query_enhancer.enhance(question, messages_history)
        enhance_label = query_enhancer.label

    # Retrieve more candidates when reranker will refine
    k_for_search = retrieval_k * 4 if reranker else retrieval_k

    print("\r\033[K[step] retrieving... ", end="", flush=True)
    chunks = store.query(
        rewritten_question,
        k=k_for_search,
        distance_threshold=retrieval_distance_threshold,
    )
    if not chunks:
        print("\r\033[K[info] no relevant chunks found, skipping\n")
        return RetrieveResult([], None, rewritten_question, enhance_label)

    # Rerank and trim to final retrieval_k
    if reranker:
        print(f"\r\033[K[step] reranking {len(chunks)} chunks... ", end="", flush=True)
        top_k = reranker_top_k or retrieval_k
        chunks = reranker.rerank(rewritten_question, chunks, top_k=top_k)

    print(f"\r\033[K[step] retrieved {len(chunks)} chunks, generating...")

    context = "\n\n".join(chunks)
    messages = [{"role": "system", "content": system_prompt}]
    if messages_history:
        messages.extend(messages_history)
    messages.append(
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}",
        },
    )

    return RetrieveResult(chunks, messages, rewritten_question, enhance_label)


def _init_ask_chat(config: dict, debug: bool = False):
    store, LlmApi = _init_retrieval(config, debug=debug)

    with _timed("Initializing LLM"):
        llm = LlmApi(
            api_key=config["llm"]["api_key"],
            base_url=config["llm"]["api_base_url"],
            model=config["llm"]["model"],
            temperature=config["llm"].get("temperature", 0.3),
            thinking_mode=config["llm"].get("thinking_mode", False),
        )

    query_enhancer, enhancer_threshold = _init_enhancer(config)
    reranker = _init_reranker(config)

    system_prompt = _build_system_prompt(
        config.get("system_rules", ""), config.get("strict_context", False)
    )

    return store, llm, query_enhancer, system_prompt, enhancer_threshold, reranker


def _init_enhancer(config: dict):
    """Initialize query enhancer from config. Returns (enhancer, threshold) or (None, None)."""
    if not config.get("query_enhance_enabled", False):
        return None, None

    from lib.query_enhancer import QueryEnhancer
    from lib.llm_api import LlmApi

    enhancer_cfg = config["enhancer"]
    mode = enhancer_cfg.get("mode")
    docs_lang = config.get("docs_lang", "en")

    with _timed("Initializing query enhancer"):
        if mode == "local":
            from lib.local_translator import LocalTranslator

            local_cfg = enhancer_cfg["local"]
            translator = LocalTranslator(
                query_lang=local_cfg["query_lang"],
                docs_lang=docs_lang,
                model_name=local_cfg.get("model_name"),
            )
            enhancer = QueryEnhancer(translator=translator, docs_lang=docs_lang)
            threshold = local_cfg.get("distance_threshold")
            return enhancer, threshold
        elif mode == "llm":
            llm_cfg = enhancer_cfg["llm"]
            enhancer_llm = LlmApi(
                api_key=llm_cfg["api_key"],
                base_url=llm_cfg["api_base_url"],
                model=llm_cfg["model"],
                temperature=llm_cfg.get("temperature", 0.0),
                thinking_mode=llm_cfg.get("thinking_mode", False),
            )
            enhancer = QueryEnhancer(llm_api=enhancer_llm, docs_lang=docs_lang)
            threshold = llm_cfg.get("distance_threshold")
            return enhancer, threshold
        else:
            raise ValueError(
                f"Invalid enhancer mode: '{mode}'. Must be 'local' or 'llm'."
            )


def _init_reranker(config: dict):
    """Initialize cross-encoder reranker from config. Returns Reranker or None."""
    if not config.get("reranker_enabled", False):
        return None
    from lib.reranker import Reranker

    cfg = config.get("reranker", {})
    with _timed("Loading reranker model"):
        return Reranker(model_name=cfg.get("model_name", "BAAI/bge-reranker-v2-m3"))


def cmd_search(
    config: dict, question: str, use_enhancer: bool = False, debug: bool = False
) -> None:
    """Search only: retrieve document chunks without LLM generation."""
    store, _ = _init_retrieval(config, debug=debug)

    distance_threshold = config.get("retrieval_distance_threshold")
    enhancer_threshold = None

    if use_enhancer:
        enhancer, enhancer_threshold = _init_enhancer(config)
        if enhancer:
            question = enhancer.enhance(question)
            print(f"[info] {enhancer.label}: {question}")
            if enhancer_threshold is not None and not config.get("_cli_threshold"):
                distance_threshold = enhancer_threshold

    reranker = _init_reranker(config)

    retrieval_k = config.get("retrieval_k", 3)
    k_for_search = retrieval_k * 4 if reranker else retrieval_k
    chunks = store.query(
        question, k=k_for_search, distance_threshold=distance_threshold
    )

    if not chunks:
        print("[info] no relevant chunks found")
        return

    if reranker:
        print(f"[step] reranking {len(chunks)} chunks... ", end="", flush=True)
        top_k = config.get("reranker", {}).get("top_k") or retrieval_k
        chunks = reranker.rerank(question, chunks, top_k=top_k)
        print("done")

    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- Chunk {i} ---")
        print(chunk)


def _stream_answer(llm, messages: list[dict], file=None) -> str:
    answer = ""
    print("[generating]...", end="", flush=True)
    if file:
        file.write("[generating]...")
        file.flush()
    for token in llm.generate_stream(messages):
        if not answer:
            print("\r\033[K", end="", flush=True)
            if file:
                filepath = file.name
                file.close()
                _remove_placeholder(filepath)
                file = open(filepath, "a", encoding="utf-8")
        print(token, end="", flush=True)
        answer += token
        if file:
            file.write(token)
            file.flush()
    print()
    return answer


def _remove_placeholder(filepath: str) -> None:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    cleaned = re.sub(r"\[generating]\.\.\.", "", content)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(cleaned)


def cmd_ask(
    config: dict, question: str, use_enhancer: bool = False, debug: bool = False
) -> None:
    if use_enhancer:
        config["query_enhance_enabled"] = True
    store, llm, query_enhancer, system_prompt, enhancer_threshold, reranker = (
        _init_ask_chat(config, debug=debug)
    )

    distance_threshold = (
        enhancer_threshold
        if enhancer_threshold is not None and not config.get("_cli_threshold")
        else config.get("retrieval_distance_threshold")
    )

    chunks, messages, rewritten_question, enhance_label = _retrieve_context(
        store,
        llm,
        question,
        system_prompt,
        retrieval_k=config.get("retrieval_k", 3),
        retrieval_distance_threshold=distance_threshold,
        query_enhancer=query_enhancer,
        reranker=reranker,
        reranker_top_k=config.get("reranker", {}).get("top_k"),
    )
    if not chunks:
        return

    out_dir = _init_output_dir(question)
    filepath = os.path.join(out_dir, "01_round.md")

    _write_round_header(filepath, 1, question, rewritten_question, enhance_label)
    f = open(filepath, "a", encoding="utf-8")
    _stream_answer(llm, messages, file=f)

    _write_round_context(filepath, chunks)
    print(f"\n[info] saved to {out_dir}")


def _has_file_changes(persist_dir: str, file_hashes: dict[str, str]) -> bool:
    meta_path = os.path.join(persist_dir, "build_meta.json")
    if not os.path.exists(meta_path):
        return True
    with open(meta_path, "r", encoding="utf-8") as f:
        old_meta = json.load(f)
    if set(old_meta.keys()) != set(file_hashes.keys()):
        return True
    return any(old_meta[f] != file_hashes[f] for f in file_hashes)


def cmd_build(config: dict, force: bool = False) -> None:
    t0 = time.perf_counter()

    docs_dir = _resolve_path(config, "docs_dir")

    if not os.path.isdir(docs_dir):
        print(f"[error] docs directory not found: {docs_dir}")
        print("[hint] check docs_dir in config.json, or create the directory")
        sys.exit(1)

    with _timed("Loading and chunking documents"):
        chunks, file_hashes = load_documents(docs_dir, config)
    if not chunks:
        print("[error] no .txt or .md files found in docs directory")
        sys.exit(1)
    print(
        f"[info] {len(chunks)} chunks from {len({c['source'] for c in chunks})} files"
    )

    store, _ = _init_retrieval(config)

    # Auto full-rebuild when embedding model changed
    vector_enabled = config.get("vector_enabled", True)
    if vector_enabled:
        old_model = store.get_meta_model()
        new_model = _resolve_model_name(config)
        if old_model and old_model != new_model:
            print(
                f"[info] model changed: {old_model} -> {new_model}, forcing full rebuild"
            )
            force = True

    if not force and not store.has_changes(file_hashes):
        print("[info] no changes detected, skipping")
        print(f"[step] build complete [{time.perf_counter() - t0:.1f}s total]")
        return

    with _timed("Building vector index"):
        if force:
            store.rebuild_full(chunks, file_hashes)
        else:
            store.rebuild(chunks, file_hashes)

    print(f"[step] build complete [{time.perf_counter() - t0:.1f}s total]")


def cmd_chat(config: dict, debug: bool = False) -> None:
    store, llm, query_enhancer, system_prompt, enhancer_threshold, reranker = (
        _init_ask_chat(config, debug=debug)
    )

    distance_threshold = (
        enhancer_threshold
        if enhancer_threshold is not None and not config.get("_cli_threshold")
        else config.get("retrieval_distance_threshold")
    )

    print("\nAsk a question. Be specific. /quit or /q to quit.\n")

    out_dir = None
    round_index = 0
    history = []
    max_rounds = config.get("max_history_rounds", 10)

    while True:
        try:
            question = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question in ("/quit", "/q"):
            break

        recent_history = history[-max_rounds * 2 :] if max_rounds else history

        chunks, messages, rewritten_question, enhance_label = _retrieve_context(
            store,
            llm,
            question,
            system_prompt,
            retrieval_k=config.get("retrieval_k", 3),
            retrieval_distance_threshold=distance_threshold,
            query_enhancer=query_enhancer,
            messages_history=recent_history,
            reranker=reranker,
            reranker_top_k=config.get("reranker", {}).get("top_k"),
        )
        if not chunks:
            continue

        if out_dir is None:
            out_dir = _init_output_dir(question)
        round_index += 1
        filepath = os.path.join(out_dir, f"{round_index:02d}_round.md")
        _write_round_header(
            filepath, round_index, question, rewritten_question, enhance_label
        )
        f = open(filepath, "a", encoding="utf-8")
        answer = _stream_answer(llm, messages, file=f)

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})

        _write_round_context(filepath, chunks)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="rag_qa.py",
        description="RAG-QA: local document retrieval + remote LLM answer generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "modes:\n"
            "  --build             Incremental build (skip if no changes)\n"
            "  --rebuild           Force full re-embed\n"
            "  --search QUESTION   Retrieve chunks without LLM generation\n"
            "  QUESTION            Single-question mode\n"
            "  (no args)           Interactive multi-turn chat\n"
        ),
    )
    parser.add_argument("--build", action="store_true", help="incremental index build")
    parser.add_argument("--rebuild", action="store_true", help="force full re-embed")
    parser.add_argument(
        "--search", action="store_true", help="search-only mode (no LLM)"
    )
    parser.add_argument(
        "--enhance", action="store_true", help="enhance query before retrieval"
    )
    parser.add_argument("--retrieval_k", type=int, help="number of chunks to retrieve")
    parser.add_argument(
        "--retrieval_distance_threshold", type=float, help="cosine distance threshold"
    )
    parser.add_argument(
        "--strict_context", type=str, help="true/false: answer only from context"
    )
    parser.add_argument(
        "--debug", action="store_true", help="enable debug output for retrieval"
    )
    parser.add_argument("question", nargs="*", help="your question")
    args = parser.parse_args()

    with _timed("Loading config"):
        config = load_config()

    # CLI overrides
    if args.retrieval_k is not None:
        config["retrieval_k"] = args.retrieval_k
    if args.retrieval_distance_threshold is not None:
        config["retrieval_distance_threshold"] = args.retrieval_distance_threshold
        config["_cli_threshold"] = True
    if args.strict_context is not None:
        config["strict_context"] = args.strict_context.lower() in ("true", "1", "yes")

    # debug: CLI --debug overrides config
    debug = args.debug or config.get("debug", False)

    question = " ".join(args.question)

    # Validate mode/question combinations
    if args.search:
        if not question:
            parser.error("--search requires a question")
        cmd_search(config, question, use_enhancer=args.enhance, debug=debug)
    elif args.build:
        if question:
            print("[warn] question ignored with --build", file=sys.stderr)
        cmd_build(config)
    elif args.rebuild:
        if question:
            print("[warn] question ignored with --rebuild", file=sys.stderr)
        cmd_build(config, force=True)
    elif question:
        cmd_ask(config, question, use_enhancer=args.enhance, debug=debug)
    else:
        if args.enhance:
            print(
                "[warn] --enhance ignored without --search or question",
                file=sys.stderr,
            )
        cmd_chat(config, debug=debug)


if __name__ == "__main__":
    main()
