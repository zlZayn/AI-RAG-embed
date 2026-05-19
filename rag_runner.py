import json
import os
import re
import sys
from datetime import datetime

from lib.embed_engine import EmbedEngine
from lib.doc_loader import load_documents
from lib.llm_api import LlmApi
from lib.vector_db import VectorDb

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question based on the provided context. "
    "If the answer is not in the context, say 'I don't know'."
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


def _export_round(
    out_dir: str,
    index: int,
    question: str,
    chunks: list[str],
    answer: str,
) -> None:
    context = "\n\n".join(chunks)
    text = (
        f"# Round {index}\n\n"
        f"## Question\n\n{question}\n\n"
        f"## Retrieved Context\n\n{context}\n\n"
        f"## Answer\n\n{answer}\n\n---\n"
    )
    filepath = os.path.join(out_dir, f"{index:02d}_round.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)


def cmd_ask(config: dict, question: str) -> None:
    persist_dir = _resolve_path(config, "chroma_persist_dir")
    model_name = config["embedding_model_name"]

    print("Loading embedding model...")
    embed_engine = EmbedEngine(model_name=model_name)

    print("Loading vector store...")
    store = VectorDb(persist_dir=persist_dir, embed_engine=embed_engine)

    llm = LlmApi(
        api_key=config["api_key"],
        base_url=config["api_base_url"],
        model=config["llm_model"],
    )

    chunks = store.query(question, k=3)
    if not chunks:
        print("No relevant documents found.")
        return

    context = "\n\n".join(chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]

    answer = llm.generate(messages)
    print(f"\n{answer}\n")

    out_dir = _init_output_dir(question)
    _export_round(out_dir, 1, question, chunks, answer)
    print(f"Saved to {out_dir}")


def cmd_build(config: dict) -> None:
    docs_dir = _resolve_path(config, "docs_dir")
    persist_dir = _resolve_path(config, "chroma_persist_dir")
    model_name = config["embedding_model_name"]

    if not os.path.isdir(docs_dir):
        print(f"Documents directory not found: {docs_dir}")
        sys.exit(1)

    print("Loading and chunking documents...")
    chunks = load_documents(
        docs_dir,
        chunk_size=config["chunk_size"],
        chunk_overlap=config["chunk_overlap"],
    )
    if not chunks:
        print("No .txt or .md files found in documents directory.")
        sys.exit(1)
    print(f"  {len(chunks)} chunks from {len({c['source'] for c in chunks})} files")

    print("Loading embedding model...")
    embed_engine = EmbedEngine(model_name=model_name)

    print("Building vector index...")
    store = VectorDb(persist_dir=persist_dir, embed_engine=embed_engine)
    store.rebuild(chunks)
    print(f"Index built and saved to {persist_dir}")


def cmd_chat(config: dict) -> None:
    persist_dir = _resolve_path(config, "chroma_persist_dir")
    model_name = config["embedding_model_name"]

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

        chunks = store.query(question, k=3)
        if not chunks:
            print("No relevant documents found.\n")
            continue

        context = "\n\n".join(chunks)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ]

        print("thinking...")
        answer = llm.generate(messages)
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


if __name__ == "__main__":
    main()
