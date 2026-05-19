import os

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from sentence_transformers import SentenceTransformer

_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class EmbedEngine:
    def __init__(self, model_name: str):
        self._model = SentenceTransformer(model_name)

    def get_embedding(self, text: str) -> list[float]:
        return self._model.encode(_QUERY_PREFIX + text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()
