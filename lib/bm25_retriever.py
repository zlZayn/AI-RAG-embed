import re

from rank_bm25 import BM25Okapi

try:
    import jieba

    jieba.setLogLevel(jieba.logging.WARNING)
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False

_PUNCT_RE = re.compile(
    r"[\s　，、。．；：（）《》"
    r"？！—…·\"\"‘’＂＇,.:;!?()\[\]{}]"
)


def _tokenize(text: str) -> list[str]:
    if _HAS_JIEBA:
        tokens = jieba.lcut(text)
    else:
        tokens = list(text)
    return [t for t in tokens if len(t.strip()) > 0 and not _PUNCT_RE.fullmatch(t)]


class BM25Retriever:
    def __init__(self):
        self._bm25 = None
        self._texts = []

    def build(self, texts: list[str]) -> None:
        self._texts = texts
        tokenized = [_tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(tokenized)

    def query(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        if self._bm25 is None or not self._texts:
            return []
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(i, float(scores[i])) for i in indices]

    @property
    def ready(self) -> bool:
        return self._bm25 is not None and len(self._texts) > 0
