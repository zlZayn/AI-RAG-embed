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
        vector_enabled: bool = True,
        bm25_enabled: bool = False,
        model_name: str = "",
        debug: bool = False,
    ):
        self._persist_dir = persist_dir
        self._embed_engine = embed_engine
        self._model_name = model_name
        self._vector_enabled = vector_enabled
        self._bm25_enabled = bm25_enabled
        self._debug = debug
        self._bm25_texts: list[str] = []
        self._bm25_sources: list[str] = []

        if vector_enabled:
            self._client = chromadb.PersistentClient(
                path=persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"},
            )
        else:
            self._client = None
            self._collection = None

        self._bm25 = BM25Retriever() if bm25_enabled else None
        if bm25_enabled:
            if vector_enabled:
                self._rebuild_bm25_from_store()
            else:
                self._load_bm25_from_file()

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

    def store_meta_value(self, key: str, value: str) -> None:
        meta = self._load_meta()
        meta[key] = value
        self._save_meta(meta)

    def get_meta_value(self, key: str) -> str | None:
        meta = self._load_meta()
        return meta.get(key)

    # ------------------------------------------------------------------
    # BM25 file storage (BM25-only mode)
    # ------------------------------------------------------------------

    def _bm25_store_path(self) -> str:
        return os.path.join(self._persist_dir, "bm25_store.json")

    def _load_bm25_from_file(self) -> None:
        path = self._bm25_store_path()
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._bm25_texts = [c["text"] for c in data["chunks"]]
        self._bm25_sources = [c["source"] for c in data["chunks"]]
        self._bm25.build(self._bm25_texts)
        print(f"[info] BM25 index loaded from file: {len(self._bm25_texts)} chunks")

    def _save_bm25_to_file(
        self, chunks: list[dict], file_hashes: dict[str, str]
    ) -> None:
        data = {"chunks": chunks, "file_hashes": file_hashes}
        with open(self._bm25_store_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # BM25 from ChromaDB (hybrid mode)
    # ------------------------------------------------------------------

    def _rebuild_bm25_from_store(self) -> None:
        """Load all documents from Chroma into BM25 index."""
        all_data = self._collection.get(include=["documents", "metadatas"])
        if all_data["documents"]:
            self._bm25_texts = all_data["documents"]
            self._bm25_sources = [m["source"] for m in all_data["metadatas"]]
            self._bm25.build(self._bm25_texts)
            print(f"[info] BM25 index loaded: {len(self._bm25_texts)} chunks")

    # ------------------------------------------------------------------
    # Change detection
    # ------------------------------------------------------------------

    def has_changes(self, file_hashes: dict[str, str]) -> bool:
        if self._vector_enabled:
            old_meta = self._load_meta()
            if set(old_meta.keys()) != set(file_hashes.keys()):
                return True
            return any(old_meta[f] != file_hashes[f] for f in file_hashes)
        elif self._bm25_enabled:
            path = self._bm25_store_path()
            if not os.path.exists(path):
                return True
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            old_hashes = data.get("file_hashes", {})
            return old_hashes != file_hashes
        return False

    # ------------------------------------------------------------------
    # Build / rebuild
    # ------------------------------------------------------------------

    def rebuild(self, chunks: list[dict], file_hashes: dict[str, str]) -> None:
        if self._vector_enabled:
            old_meta = self._load_meta()

            removed = [f for f in old_meta if f not in file_hashes]
            added = [f for f in file_hashes if f not in old_meta]
            changed = [
                f
                for f in file_hashes
                if f in old_meta and file_hashes[f] != old_meta[f]
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
                f"[info] incremental: +{len(added)} new, ~{len(changed)} updated, "
                f"-{len(removed)} removed, total {total} chunks"
            )

        if self._bm25_enabled:
            if self._vector_enabled:
                self._rebuild_bm25_from_store()
            else:
                self._save_bm25_to_file(chunks, file_hashes)
                self._bm25_texts = [c["text"] for c in chunks]
                self._bm25_sources = [c["source"] for c in chunks]
                self._bm25.build(self._bm25_texts)
                print(f"[info] BM25 index built: {len(self._bm25_texts)} chunks")

    def rebuild_full(self, chunks: list[dict], file_hashes: dict[str, str]) -> None:
        if self._vector_enabled:
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
            self._bm25_texts = [c["text"] for c in chunks]
            self._bm25_sources = [c["source"] for c in chunks]
            self._bm25.build(self._bm25_texts)
            if not self._vector_enabled:
                self._save_bm25_to_file(chunks, file_hashes)
            print(f"[info] BM25 index rebuilt: {len(self._bm25_texts)} chunks")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self, question: str, k: int = 3, distance_threshold: float = None
    ) -> list[str]:
        """Retrieve top-k document chunks."""
        if self._debug:
            print(f"\n[debug] query params: k={k}, threshold={distance_threshold}")

        if self._vector_enabled and self._bm25_enabled and self._bm25.ready:
            if self._debug:
                print("[debug] query path: hybrid (vector + BM25, RRF fusion)")
            return self._hybrid_query(
                question, k=k, distance_threshold=distance_threshold
            )
        elif self._vector_enabled:
            if self._debug:
                print("[debug] query path: vector-only")
            return self._vector_query(
                question, k=k, distance_threshold=distance_threshold
            )
        elif self._bm25_enabled and self._bm25.ready:
            if self._debug:
                print("[debug] query path: BM25-only")
            return self._bm25_query(question, k=k)
        else:
            if self._debug:
                print("[debug] query path: none (vector and BM25 both disabled)")
            return []

    def _vector_query(
        self, question: str, k: int = 3, distance_threshold: float = None
    ) -> list[str]:
        """Vector-only retrieval."""
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

        if self._debug:
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
                if self._debug:
                    print(
                        f"[debug] filtered to {len(documents)} chunks (threshold={distance_threshold})"
                    )
            else:
                print(
                    f"[warn] no vector chunks passed threshold={distance_threshold}, returning closest"
                )
                documents = [documents[0]]

        return documents

    def _bm25_query(self, question: str, k: int = 3) -> list[str]:
        """BM25-only retrieval."""
        hits = self._bm25.query(question, k=k)
        documents = [self._bm25_texts[i] for i, _ in hits]

        if self._debug:
            print("\n[debug] BM25 retrieval details")
            for i, (idx, score) in enumerate(hits):
                src = self._bm25_sources[idx] if idx < len(self._bm25_sources) else ""
                print(
                    f"[debug]   chunk {i + 1}: bm25_score={score:.4f} [source: {src}]"
                )
                print(f"[debug]     preview: {self._bm25_texts[idx][:80]}...")

        return documents

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

        if self._debug:
            print("\n[debug] hybrid retrieval details")
            for i, (doc, score) in enumerate(ranked[:k]):
                src = ""
                if doc in self._bm25_texts:
                    idx = self._bm25_texts.index(doc)
                    src = f" [source: {self._bm25_sources[idx]}]"
                print(f"[debug]   chunk {i + 1}: rrf_score={score:.6f}{src}")
                print(f"[debug]     preview: {doc[:80]}...")

        return documents
