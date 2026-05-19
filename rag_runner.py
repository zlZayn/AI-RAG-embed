import json
import os
import re
import sys
import time
from datetime import datetime

from lib.doc_loader import load_documents


def _import_lib():
    from lib.embed_engine import EmbedEngine
    from lib.llm_api import LlmApi
    from lib.vector_db import VectorDb

    return EmbedEngine, LlmApi, VectorDb


_SYSTEM_BASE_STRICT = (
    "You are a helpful assistant. Answer the user's question based ONLY on the provided context. "
    "If the answer is not in the context, say 'I don't know'."
)

_SYSTEM_BASE = (
    "You are a helpful assistant. Use the provided context to enrich your answer, "
    "but also draw on your own knowledge when the context is insufficient. "
    "If the context is provided, prefer it over your own knowledge for factual claims."
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
) -> None:
    safe_chunks = [_sanitize_chunk(c) for c in chunks]
    context_blocks = "\n\n".join(f"```\n{c}\n```" for c in safe_chunks)
    text = (
        f"\n--- Round {index} ---\n\n"
        f"Question: {question}\n\n"
        f"Answer:\n\n{answer}\n\n"
        f"--- Retrieved Context ---\n\n"
        f"{context_blocks}\n"
    )
    filepath = os.path.join(out_dir, f"{index:02d}_round.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)


def _retrieve_and_ask(store, llm, question, system_prompt, retrieval_k, temperature):
    chunks = store.query(question, k=retrieval_k)
    if not chunks:
        return [], ""

    context = "\n\n".join(chunks)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]

    answer = llm.generate(messages, temperature=temperature)
    return chunks, answer


def cmd_ask(config: dict, question: str) -> None:
    EmbedEngine, LlmApi, VectorDb = _import_lib()
    persist_dir = _resolve_path(config, "chroma_persist_dir")
    model_name = config["embedding_model_name"]
    retrieval_k = config.get("retrieval_k", 3)
    temperature = config.get("llm_temperature", 0.3)
    system_rules = config.get("system_rules", "")
    strict_context = config.get("strict_context", False)
    system_prompt = _build_system_prompt(system_rules, strict_context)

    print("Loading embedding model...")
    embed_engine = EmbedEngine(model_name=model_name)

    print("Loading vector store...")
    store = VectorDb(persist_dir=persist_dir, embed_engine=embed_engine)

    llm = LlmApi(
        api_key=config["api_key"],
        base_url=config["api_base_url"],
        model=config["llm_model"],
    )

    chunks, answer = _retrieve_and_ask(
        store,
        llm,
        question,
        system_prompt,
        retrieval_k,
        temperature,
    )
    if not chunks:
        print("No relevant documents found.")
        return

    print(f"\n{answer}\n")

    out_dir = _init_output_dir(question)
    _export_round(out_dir, 1, question, chunks, answer)
    print(f"Saved to {out_dir}")


def cmd_build(config: dict) -> None:
    EmbedEngine, _, VectorDb = _import_lib()
    t0 = time.perf_counter()

    docs_dir = _resolve_path(config, "docs_dir")
    persist_dir = _resolve_path(config, "chroma_persist_dir")
    model_name = config["embedding_model_name"]

    if not os.path.isdir(docs_dir):
        print(f"Documents directory not found: {docs_dir}")
        sys.exit(1)

    print("Loading and chunking documents...")
    t1 = time.perf_counter()
    chunks = load_documents(
        docs_dir,
        chunk_size=config["chunk_size"],
        chunk_overlap=config["chunk_overlap"],
    )
    if not chunks:
        print("No .txt or .md files found in documents directory.")
        sys.exit(1)
    print(
        f"  {len(chunks)} chunks from {len({c['source'] for c in chunks})} files  [{time.perf_counter() - t1:.1f}s]"
    )

    print("Loading embedding model...")
    t2 = time.perf_counter()
    embed_engine = EmbedEngine(model_name=model_name)
    print(f"  model ready  [{time.perf_counter() - t2:.1f}s]")

    print("Building vector index...")
    t3 = time.perf_counter()
    store = VectorDb(persist_dir=persist_dir, embed_engine=embed_engine)
    store.rebuild(chunks)
    print(f"  index saved to {persist_dir}  [{time.perf_counter() - t3:.1f}s]")

    print(f"\nBuild complete  [{time.perf_counter() - t0:.1f}s total]")


def cmd_chat(config: dict) -> None:
    EmbedEngine, LlmApi, VectorDb = _import_lib()
    persist_dir = _resolve_path(config, "chroma_persist_dir")
    model_name = config["embedding_model_name"]
    retrieval_k = config.get("retrieval_k", 3)
    temperature = config.get("llm_temperature", 0.3)
    system_rules = config.get("system_rules", "")
    strict_context = config.get("strict_context", False)
    system_prompt = _build_system_prompt(system_rules, strict_context)

    print("Loading embedding model...")
    embed_engine = EmbedEngine(model_name=model_name)

    print("Loading vector store...")
    store = VectorDb(persist_dir=persist_dir, embed_engine=embed_engine)

    llm = LlmApi(
        api_key=config["api_key"],
        base_url=config["api_base_url"],
        model=config["llm_model"],
    )

    print("Ready. Type your question (or /exit /quit /q to quit).\n")

    out_dir = None
    round_index = 0

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

        chunks, answer = _retrieve_and_ask(
            store,
            llm,
            question,
            system_prompt,
            retrieval_k,
            temperature,
        )
        if not chunks:
            print("No relevant documents found.\n")
            continue

        print(f"\n{answer}\n")

        if out_dir is None:
            out_dir = _init_output_dir(question)
        round_index += 1
        _export_round(out_dir, round_index, question, chunks, answer)


def main() -> None:
    config = load_config()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--build":
            cmd_build(config)
        else:
            cmd_ask(config, " ".join(sys.argv[1:]))
    else:
        cmd_chat(config)


if __name__ == "__main__":
    main()
