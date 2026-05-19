import chromadb
from chromadb.config import Settings


class VectorDb:
    def __init__(self, persist_dir: str, embed_engine):
        self._embed_engine = embed_engine
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

    def rebuild(self, chunks: list[dict]) -> None:
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

    def query(self, question: str, k: int = 3) -> list[str]:
        question_embedding = self._embed_engine.get_embedding(question)

        results = self._collection.query(
            query_embeddings=[question_embedding],
            n_results=k,
        )

        return results["documents"][0] if results["documents"] else []
