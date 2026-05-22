import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from typing import NamedTuple

from lib.doc_loader import load_documents


def _import_lib():
    from lib.embed_engine import EmbedEngine
    from lib.llm_api import LlmApi
    from lib.vector_db import VectorDb

    return EmbedEngine, LlmApi, VectorDb


@contextmanager
def _timed(label: str):
    t0 = time.perf_counter()
    print(f">> {label}... ", end="", flush=True)
    yield
    print(f"\r\033[K>> {label}... done  [{time.perf_counter() - t0:.1f}s]")


def _init_embed_store(config: dict):
    with _timed("Importing modules"):
        EmbedEngine, LlmApi, VectorDb = _import_lib()
    with _timed("Loading embedding model"):
        embed_engine = EmbedEngine(model_name=config["embedding_model_name"])
    with _timed("Loading vector index"):
        store = VectorDb(
            persist_dir=_resolve_path(config, "chroma_persist_dir"),
            embed_engine=embed_engine,
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
) -> RetrieveResult:
    """检索相关文档块。"""
    rewritten_question = question
    enhance_label = "Enhanced Question"

    print(">> Processing... ", end="", flush=True)

    if query_enhancer:
        rewritten_question = query_enhancer.enhance(question, messages_history)
        enhance_label = query_enhancer.label

    print("\r\033[K>> Retrieving... ", end="", flush=True)
    chunks = store.query(
        rewritten_question,
        k=retrieval_k,
        distance_threshold=retrieval_distance_threshold,
    )
    if not chunks:
        print("\r\033[K>> No relevant chunks found. Skipping.\n")
        return RetrieveResult([], None, rewritten_question, enhance_label)

    print(f"\r\033[K>> Retrieved {len(chunks)} chunks. Generating...")

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


def _init_ask_chat(config: dict):
    store, LlmApi = _init_embed_store(config)

    with _timed("Initializing LLM"):
        llm = LlmApi(
            api_key=config["llm"]["api_key"],
            base_url=config["llm"]["api_base_url"],
            model=config["llm"]["model"],
            temperature=config["llm"].get("temperature", 0.3),
            thinking_mode=config["llm"].get("thinking_mode", False),
        )

    query_enhancer = None
    if config.get("query_enhance_enabled", False):
        from lib.query_enhancer import QueryEnhancer

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
                query_enhancer = QueryEnhancer(
                    translator=translator, docs_lang=docs_lang
                )
            elif mode == "llm":
                llm_cfg = enhancer_cfg["llm"]
                enhancer_llm = LlmApi(
                    api_key=llm_cfg["api_key"],
                    base_url=llm_cfg["api_base_url"],
                    model=llm_cfg["model"],
                    temperature=llm_cfg.get("temperature", 0.0),
                    thinking_mode=llm_cfg.get("thinking_mode", False),
                )
                query_enhancer = QueryEnhancer(
                    llm_api=enhancer_llm, docs_lang=docs_lang
                )
            else:
                raise ValueError(
                    f"Invalid enhancer mode: '{mode}'. Must be 'local' or 'llm'."
                )

    system_prompt = _build_system_prompt(
        config.get("system_rules", ""), config.get("strict_context", False)
    )

    return store, llm, query_enhancer, system_prompt


def cmd_search(config: dict, question: str) -> None:
    """Search only: retrieve document chunks without LLM generation."""
    store, _ = _init_embed_store(config)

    k = config.get("retrieval_k", 3)
    distance_threshold = config.get("retrieval_distance_threshold")
    chunks = store.query(question, k=k, distance_threshold=distance_threshold)

    if not chunks:
        print(">> No relevant chunks found.")
        return

    enc = sys.stdout.encoding or "utf-8"
    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- Chunk {i} ---")
        print(chunk.encode(enc, errors="replace").decode(enc))


def _stream_answer(llm, messages: list[dict]) -> str:
    answer = ""
    for token in llm.generate_stream(messages):
        print(token, end="", flush=True)
        answer += token
    print()
    return answer


def cmd_ask(config: dict, question: str) -> None:
    store, llm, query_enhancer, system_prompt = _init_ask_chat(config)

    chunks, messages, rewritten_question, enhance_label = _retrieve_context(
        store,
        llm,
        question,
        system_prompt,
        retrieval_k=config.get("retrieval_k", 3),
        retrieval_distance_threshold=config.get("retrieval_distance_threshold"),
        query_enhancer=query_enhancer,
    )
    if not chunks:
        return

    answer = _stream_answer(llm, messages)

    out_dir = _init_output_dir(question)
    _export_round(
        out_dir, 1, question, chunks, answer, rewritten_question, enhance_label
    )
    print(f"\nSaved to {out_dir}")


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
    persist_dir = _resolve_path(config, "chroma_persist_dir")

    if not os.path.isdir(docs_dir):
        print(f">> Error: documents directory not found: {docs_dir}")
        sys.exit(1)

    with _timed("Loading and chunking documents"):
        chunks, file_hashes = load_documents(
            docs_dir,
            chunk_size=config["chunk_size"],
            chunk_overlap=config["chunk_overlap"],
        )
    if not chunks:
        print(">> No .txt or .md files found in documents directory.")
        sys.exit(1)
    print(f">> {len(chunks)} chunks from {len({c['source'] for c in chunks})} files")

    if not force and not _has_file_changes(persist_dir, file_hashes):
        print(">> No changes detected. Skipping.")
        print(f">> Build complete  [{time.perf_counter() - t0:.1f}s total]")
        return

    store, _ = _init_embed_store(config)

    with _timed("Building vector index"):
        if force:
            store.rebuild_full(chunks, file_hashes)
        else:
            store.rebuild(chunks, file_hashes)

    print(f">> Build complete  [{time.perf_counter() - t0:.1f}s total]")


def cmd_chat(config: dict) -> None:
    store, llm, query_enhancer, system_prompt = _init_ask_chat(config)

    print("\nReady. Type your question (or /exit /quit /q to quit).\n")

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
        if question in ("/exit", "/quit", "/q"):
            break

        recent_history = history[-max_rounds * 2 :] if max_rounds else history

        chunks, messages, rewritten_question, enhance_label = _retrieve_context(
            store,
            llm,
            question,
            system_prompt,
            retrieval_k=config.get("retrieval_k", 3),
            retrieval_distance_threshold=config.get("retrieval_distance_threshold"),
            query_enhancer=query_enhancer,
            messages_history=recent_history,
        )
        if not chunks:
            continue

        answer = _stream_answer(llm, messages)

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})

        if out_dir is None:
            out_dir = _init_output_dir(question)
        round_index += 1
        _export_round(
            out_dir,
            round_index,
            question,
            chunks,
            answer,
            rewritten_question,
            enhance_label,
        )


def main() -> None:
    with _timed("Loading config"):
        config = load_config()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--build":
            cmd_build(config)
        elif sys.argv[1] == "--rebuild":
            cmd_build(config, force=True)
        elif sys.argv[1] == "--search":
            cmd_search(config, " ".join(sys.argv[2:]))
        else:
            cmd_ask(config, " ".join(sys.argv[1:]))
    else:
        cmd_chat(config)


if __name__ == "__main__":
    main()
