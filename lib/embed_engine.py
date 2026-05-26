import os

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from sentence_transformers import SentenceTransformer

_QUERY_PREFIXES = {
    "zh": "为这个句子生成表示以用于检索中文文档: ",
    "en": "Represent this sentence for searching relevant passages: ",
}


class EmbedEngine:
    def __init__(self, model_name: str, lang: str = "en"):
        try:
            self._model = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            print(f"[load] downloading embedding model: {model_name}")
            self._model = SentenceTransformer(model_name)
        self._query_prefix = _QUERY_PREFIXES.get(lang, _QUERY_PREFIXES["en"])

    def get_embedding(self, text: str) -> list[float]:
        return self._model.encode(self._query_prefix + text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()
