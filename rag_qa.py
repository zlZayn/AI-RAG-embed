"""RAG-QA CLI entry point.

Handles command dispatch, retrieval orchestration, streaming output,
and file export. Initialization and config logic lives in lib/engine.py.
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import NamedTuple

from lib.doc_loader import load_documents
from lib.engine import (
    build_indexing_summary,
    build_retrieval_summary,
    get_retrieval_cfg,
    get_retrieval_mode,
    init_enhancer,
    init_llm,
    init_reranker,
    init_retrieval,
    load_config,
    resolve_model_name,
    resolve_path,
    timed,
)
from lib.prompt_templates import build_qa_messages, build_system_prompt

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


_PROJECT_DIR = os.path.dirname(__file__)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Retrieval orchestration
# ---------------------------------------------------------------------------


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
    debug=False,
) -> RetrieveResult:
    """Retrieve relevant document chunks and build messages for LLM."""
    rewritten_question = question
    enhance_label = "Enhanced Question"

    print("[step] processing... ", end="", flush=True)

    if query_enhancer:
        rewritten_question = query_enhancer.enhance(question, messages_history)
        enhance_label = query_enhancer.label

    if debug:
        print(f"\n[debug] original question: {question}")
        if rewritten_question != question:
            print(f"[debug] rewritten question: {rewritten_question}")
        print(
            f"[debug] retrieval_k={retrieval_k}, threshold={retrieval_distance_threshold}"
        )

    # Retrieve more candidates when reranker will refine
    k_for_search = retrieval_k * 4 if reranker else retrieval_k

    if debug and reranker:
        print(
            f"[debug] reranker active: searching {k_for_search} candidates, will keep top {reranker_top_k or retrieval_k}"
        )

    print("\r\033[K[step] retrieving... ", end="", flush=True)
    chunks = store.query(
        rewritten_question,
        k=k_for_search,
        distance_threshold=retrieval_distance_threshold,
    )
    if not chunks:
        mode_tag = get_retrieval_mode(store)
        q = rewritten_question[:60]
        print(
            f'\r\033[K[info] no relevant chunks found for "{q}" [{mode_tag}], skipping\n'
        )
        return RetrieveResult([], None, rewritten_question, enhance_label)

    # Rerank and trim to final retrieval_k
    if reranker:
        print(f"\r\033[K[step] reranking {len(chunks)} chunks... ", end="", flush=True)
        top_k = reranker_top_k or retrieval_k
        chunks = reranker.rerank(rewritten_question, chunks, top_k=top_k, debug=debug)

    print(f"\r\033[K[step] retrieved {len(chunks)} chunks, generating...")

    context = "\n\n".join(chunks)
    messages = build_qa_messages(system_prompt, question, context, messages_history)

    return RetrieveResult(chunks, messages, rewritten_question, enhance_label)


def _init_ask_chat(config: dict, debug: bool = False):
    """Initialize all components for ask/chat modes. Returns (store, llm, enhancer, system_prompt, reranker)."""
    store, LlmApi = init_retrieval(config, debug=debug)
    llm = init_llm(config, LlmApi)
    query_enhancer = init_enhancer(config)
    reranker = init_reranker(config)
    system_prompt = build_system_prompt(config)
    return store, llm, query_enhancer, system_prompt, reranker


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


def _stream_answer(llm, messages: list[dict], file=None) -> str:
    answer = ""
    print("[step] generating answer...", end="", flush=True)
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


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


def cmd_search(
    config: dict, question: str, use_enhancer: bool = False, debug: bool = False
) -> None:
    """Search only: retrieve document chunks without LLM generation."""
    store, _ = init_retrieval(config, debug=debug)

    retrieval_cfg = get_retrieval_cfg(config)
    distance_threshold = retrieval_cfg.get("distance_threshold")
    original_question = question

    reranker_on = config.get("reranker_enabled", False)
    mode_tag = get_retrieval_mode(store)
    print(
        f"[info] retrieval: {build_retrieval_summary(retrieval_cfg, reranker_on, mode_tag)}"
    )
    if debug:
        print(
            f"[debug] config: {build_indexing_summary(config)}, {build_retrieval_summary(retrieval_cfg, reranker_on, mode_tag)}, llm=search-only"
        )

    if use_enhancer:
        enhancer = init_enhancer(config)
        if enhancer:
            question = enhancer.enhance(question)
            print(f"[info] {enhancer.label}: {question}")

    if debug:
        print(f"\n[debug] original question: {original_question}")
        if question != original_question:
            print(f"[debug] rewritten question: {question}")

    reranker = init_reranker(config)

    retrieval_k = retrieval_cfg.get("k", 3)
    k_for_search = retrieval_k * 4 if reranker else retrieval_k
    chunks = store.query(
        question, k=k_for_search, distance_threshold=distance_threshold
    )

    if not chunks:
        mode_tag = get_retrieval_mode(store)
        print(f'[info] no relevant chunks found for "{question[:60]}" [{mode_tag}]')
        return

    if reranker:
        print(f"\r\033[K[step] reranking {len(chunks)} chunks... ", end="", flush=True)
        top_k = config.get("reranker", {}).get("top_k") or retrieval_k
        chunks = reranker.rerank(question, chunks, top_k=top_k, debug=debug)

    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- Chunk {i} ---")
        print(chunk)


def cmd_ask(
    config: dict, question: str, use_enhancer: bool = False, debug: bool = False
) -> None:
    if use_enhancer:
        config["query_enhance_enabled"] = True
    store, llm, query_enhancer, system_prompt, reranker = _init_ask_chat(
        config, debug=debug
    )

    retrieval_cfg = get_retrieval_cfg(config)

    reranker_on = config.get("reranker_enabled", False)
    mode_tag = get_retrieval_mode(store)
    print(
        f"[info] retrieval: {build_retrieval_summary(retrieval_cfg, reranker_on, mode_tag)}"
    )
    if debug:
        print(
            f"[debug] config: {build_indexing_summary(config)}, {build_retrieval_summary(retrieval_cfg, reranker_on, mode_tag)}, llm={llm._model}"
        )

    chunks, messages, rewritten_question, enhance_label = _retrieve_context(
        store,
        llm,
        question,
        system_prompt,
        retrieval_k=retrieval_cfg.get("k", 3),
        retrieval_distance_threshold=retrieval_cfg.get("distance_threshold"),
        query_enhancer=query_enhancer,
        reranker=reranker,
        reranker_top_k=config.get("reranker", {}).get("top_k"),
        debug=debug,
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


def cmd_build(config: dict, force: bool = False, debug: bool = False) -> None:
    t0 = time.perf_counter()

    docs_dir = resolve_path(config, "docs_dir")

    if not os.path.isdir(docs_dir):
        print(f"[error] docs directory not found: {docs_dir}")
        print("[hint] check docs_dir in config.json, or create the directory")
        sys.exit(1)

    with timed("Loading and chunking documents"):
        chunks, file_hashes = load_documents(docs_dir, config)
    if not chunks:
        print("[error] no .txt or .md files found in docs directory")
        sys.exit(1)
    print(
        f"[info] {len(chunks)} chunks from {len({c['source'] for c in chunks})} files"
    )
    print(f"[info] indexing: {build_indexing_summary(config)}")

    store, _ = init_retrieval(config)

    if debug:
        mode_tag = get_retrieval_mode(store)
        retrieval_cfg = get_retrieval_cfg(config)
        reranker_on = config.get("reranker_enabled", False)
        llm_model = config.get("llm", {}).get("model", "?")
        ret = build_retrieval_summary(retrieval_cfg, reranker_on, mode_tag)
        print(
            f"[debug] config: {build_indexing_summary(config)}, {ret}, llm={llm_model}"
        )

    # Warn when embedding model changed
    vector_enabled = config.get("vector_enabled", True)
    if vector_enabled:
        old_model = store.get_meta_model()
        new_model = resolve_model_name(config)
        if old_model and old_model != new_model:
            print(f"[warn] model changed: {old_model} -> {new_model}")
            print("[hint] run --rebuild to rebuild index with new model")

    if not force and not store.has_changes(file_hashes):
        # Check chunking config change — warn even if files unchanged
        old_chunking = store.get_meta_value("_chunking")
        if old_chunking:
            new_chunking = build_indexing_summary(config)
            if old_chunking != new_chunking:
                print(
                    f"[warn] chunking config changed: {old_chunking} -> {new_chunking}"
                )
                print("[hint] run --rebuild to rebuild index with new chunking config")

        print("[step] no changes detected, skipping")
        print(f"[step] build complete [{time.perf_counter() - t0:.1f}s total]")
        return

    with timed("Building vector index"):
        if force:
            store.rebuild_full(chunks, file_hashes)
        else:
            store.rebuild(chunks, file_hashes)

    store.store_meta_value("_chunking", build_indexing_summary(config))

    print(f"[step] build complete [{time.perf_counter() - t0:.1f}s total]")


def cmd_chat(config: dict, debug: bool = False) -> None:
    store, llm, query_enhancer, system_prompt, reranker = _init_ask_chat(
        config, debug=debug
    )

    retrieval_cfg = get_retrieval_cfg(config)

    reranker_on = config.get("reranker_enabled", False)
    mode_tag = get_retrieval_mode(store)
    print(
        f"[info] retrieval: {build_retrieval_summary(retrieval_cfg, reranker_on, mode_tag)}"
    )
    if debug:
        print(
            f"[debug] config: {build_indexing_summary(config)}, {build_retrieval_summary(retrieval_cfg, reranker_on, mode_tag)}, llm={llm._model}"
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
            retrieval_k=retrieval_cfg.get("k", 3),
            retrieval_distance_threshold=retrieval_cfg.get("distance_threshold"),
            query_enhancer=query_enhancer,
            messages_history=recent_history,
            reranker=reranker,
            reranker_top_k=config.get("reranker", {}).get("top_k"),
            debug=debug,
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

    with timed("Loading config"):
        config = load_config()

    # CLI overrides
    if args.retrieval_k is not None:
        config.setdefault("retrieval", {})["k"] = args.retrieval_k
    if args.retrieval_distance_threshold is not None:
        config.setdefault("retrieval", {})["distance_threshold"] = (
            args.retrieval_distance_threshold
        )
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
        cmd_build(config, debug=debug)
    elif args.rebuild:
        if question:
            print("[warn] question ignored with --rebuild", file=sys.stderr)
        cmd_build(config, force=True, debug=debug)
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
