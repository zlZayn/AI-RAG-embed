import json
import os

import chromadb
from chromadb.config import Settings

from lib.bm25_retriever import BM25Retriever

_META_FILE = "build_meta.json"


class VectorDb:
    def __init__(
        self,
        persist_dir: str,
        embed_engine=None,
        bm25_enabled: bool = False,
        model_name: str = "",
    ):
        self._persist_dir = persist_dir
        self._embed_engine = embed_engine
        self._model_name = model_name
        self._bm25_enabled = bm25_enabled
        self._bm25 = BM25Retriever() if bm25_enabled else None
        self._bm25_texts = []
        self._bm25_sources = []
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
        if bm25_enabled:
            self._rebuild_bm25_from_store()

    def _meta_path(self) -> str:
        return os.path.join(self._persist_dir, _META_FILE)

    def _load_meta(self) -> dict[str, str]:
        path = self._meta_path()
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_meta(self, meta: dict[str, str]) -> None:
        meta["_model"] = self._model_name
        with open(self._meta_path(), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def get_meta_model(self) -> str | None:
        old = self._load_meta()
        return old.get("_model")

    def _rebuild_bm25_from_store(self) -> None:
        """Load all documents from Chroma into BM25 index."""
        all_data = self._collection.get(include=["documents", "metadatas"])
        if all_data["documents"]:
            self._bm25_texts = all_data["documents"]
            self._bm25_sources = [m["source"] for m in all_data["metadatas"]]
            self._bm25.build(self._bm25_texts)
            print(f"[info] BM25 index loaded: {len(self._bm25_texts)} chunks")

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

        if self._bm25_enabled:
            self._rebuild_bm25_from_store()

        total = self._collection.count()
        print(
            f"[info] incremental: +{len(added)} new, ~{len(changed)} updated, "
            f"-{len(removed)} removed, total {total} chunks"
        )

    def rebuild_full(self, chunks: list[dict], file_hashes: dict[str, str]) -> None:
        texts = [c["text"] for c in chunks]
        sources = [c["source"] for c in chunks]
        ids = [str(i) for i in range(len(chunks))]

        embeddings = self._embed_engine.embed_batch(texts)

        # Delete and recreate collection to handle dimension changes
        self._client.delete_collection("documents")
        self._collection = self._client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=[{"source": s} for s in sources],
        )

        self._save_meta(file_hashes)

        if self._bm25_enabled:
            self._bm25_texts = texts
            self._bm25_sources = sources
            self._bm25.build(texts)

    def _hybrid_query(
        self, question: str, k: int = 3, distance_threshold: float = None
    ) -> list[str]:
        """Vector + BM25 hybrid retrieval with Reciprocal Rank Fusion."""
        # Vector search — fetch 2k candidates
        question_embedding = self._embed_engine.get_embedding(question)
        vec_results = self._collection.query(
            query_embeddings=[question_embedding],
            n_results=min(k * 2, self._collection.count()),
            include=["documents", "distances"],
        )
        vec_docs = vec_results["documents"][0] if vec_results["documents"] else []
        vec_dists = vec_results["distances"][0] if vec_results["distances"] else []

        # BM25 search — fetch 2k candidates
        bm25_hits = self._bm25.query(question, k=k * 2)
        bm25_docs = [self._bm25_texts[i] for i, _ in bm25_hits]

        # RRF fusion
        rrf_k = 60
        doc_scores: dict[str, float] = {}
        doc_map: dict[str, str] = {}

        for rank, (doc, dist) in enumerate(zip(vec_docs, vec_dists)):
            doc_scores[doc] = doc_scores.get(doc, 0) + 1.0 / (rrf_k + rank)
            doc_map[doc] = doc
            if distance_threshold is not None and dist >= distance_threshold:
                continue

        for rank, doc in enumerate(bm25_docs):
            doc_scores[doc] = doc_scores.get(doc, 0) + 1.0 / (rrf_k + rank)
            doc_map[doc] = doc

        if not doc_scores:
            return []

        # Sort by fused score, return top-k
        ranked = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        documents = [doc for doc, _ in ranked[:k]]

        print("\n[debug] hybrid retrieval details")
        for i, (doc, score) in enumerate(ranked[:k]):
            src = ""
            if doc in self._bm25_texts:
                idx = self._bm25_texts.index(doc)
                src = f" [source: {self._bm25_sources[idx]}]"
            print(f"[debug]   chunk {i + 1}: rrf_score={score:.6f}{src}")
            print(f"[debug]     preview: {doc[:80]}...")

        return documents

    def query(
        self, question: str, k: int = 3, distance_threshold: float = None
    ) -> list[str]:
        """检索最相似的文档块，可选按余弦距离阈值过滤。"""
        if self._bm25_enabled and self._bm25.ready:
            return self._hybrid_query(
                question, k=k, distance_threshold=distance_threshold
            )

        question_embedding = self._embed_engine.get_embedding(question)

        results = self._collection.query(
            query_embeddings=[question_embedding],
            n_results=k,
            include=["documents", "distances"],
        )

        documents = results["documents"][0] if results["documents"] else []
        distances = results["distances"][0] if results["distances"] else []

        if not documents:
            return []

        print("\n[debug] retrieval details")
        for i, (doc, dist) in enumerate(zip(documents, distances)):
            similarity = 1 - dist
            print(
                f"[debug]   chunk {i + 1}: distance={dist:.4f}, similarity={similarity:.4f}"
            )

        if distance_threshold is not None:
            filtered = [
                (doc, dist)
                for doc, dist in zip(documents, distances)
                if dist < distance_threshold
            ]
            if filtered:
                documents = [item[0] for item in filtered]
                print(
                    f"[debug] filtered to {len(documents)} chunks (threshold={distance_threshold})"
                )
            else:
                print(
                    f"[warn] no chunks passed threshold={distance_threshold}, returning closest"
                )
                documents = [documents[0]]

        return documents
