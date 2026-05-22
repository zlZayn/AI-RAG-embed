import json
import os

import chromadb
from chromadb.config import Settings

_META_FILE = "build_meta.json"


class VectorDb:
    def __init__(self, persist_dir: str, embed_engine=None):
        self._persist_dir = persist_dir
        self._embed_engine = embed_engine
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

    def _meta_path(self) -> str:
        return os.path.join(self._persist_dir, _META_FILE)

    def _load_meta(self) -> dict[str, str]:
        path = self._meta_path()
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_meta(self, meta: dict[str, str]) -> None:
        with open(self._meta_path(), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def has_changes(self, file_hashes: dict[str, str]) -> bool:
        old_meta = self._load_meta()
        if set(old_meta.keys()) != set(file_hashes.keys()):
            return True
        return any(old_meta[f] != file_hashes[f] for f in file_hashes)

    def rebuild(self, chunks: list[dict], file_hashes: dict[str, str]) -> None:
        old_meta = self._load_meta()

        removed = [f for f in old_meta if f not in file_hashes]
        added = [f for f in file_hashes if f not in old_meta]
        changed = [
            f for f in file_hashes if f in old_meta and file_hashes[f] != old_meta[f]
        ]

        for source in removed + changed:
            self._collection.delete(where={"source": source})

        to_add = added + changed
        if to_add:
            new_chunks = [c for c in chunks if c["source"] in to_add]
            texts = [c["text"] for c in new_chunks]
            sources = [c["source"] for c in new_chunks]
            base = len(self._collection.get()["ids"])
            ids = [f"{sources[i]}_{base + i}" for i in range(len(new_chunks))]

            embeddings = self._embed_engine.embed_batch(texts)
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=[{"source": s} for s in sources],
            )

        self._save_meta(file_hashes)

        total = self._collection.count()
        print(
            f">> Incremental: +{len(added)} new, ~{len(changed)} updated, "
            f"-{len(removed)} removed. Total: {total} chunks"
        )

    def rebuild_full(self, chunks: list[dict], file_hashes: dict[str, str]) -> None:
        texts = [c["text"] for c in chunks]
        sources = [c["source"] for c in chunks]
        ids = [str(i) for i in range(len(chunks))]

        embeddings = self._embed_engine.embed_batch(texts)

        existing = self._collection.get()["ids"]
        if existing:
            self._collection.delete(ids=existing)

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=[{"source": s} for s in sources],
        )

        self._save_meta(file_hashes)

    def query(self, question: str, k: int = 3) -> list[str]:
        question_embedding = self._embed_engine.get_embedding(question)

        results = self._collection.query(
            query_embeddings=[question_embedding],
            n_results=k,
        )

        return results["documents"][0] if results["documents"] else []
