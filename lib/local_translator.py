import os

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from transformers import MarianMTModel, MarianTokenizer


class LocalTranslator:
    _cache: dict[str, tuple[MarianTokenizer, MarianMTModel]] = {}

    def __init__(self, src_lang: str, docs_lang: str, model_name: str | None = None):
        if model_name is None:
            model_name = f"Helsinki-NLP/opus-mt-{src_lang}-{docs_lang}"
        self._model_name = model_name
        self._tokenizer, self._model = self._load(model_name)

    @classmethod
    def _load(cls, model_name: str):
        if model_name not in cls._cache:
            tokenizer = MarianTokenizer.from_pretrained(model_name)
            model = MarianMTModel.from_pretrained(model_name, use_safetensors=True)
            cls._cache[model_name] = (tokenizer, model)
        return cls._cache[model_name]

    def translate(self, text: str) -> str:
        inputs = self._tokenizer(
            text, return_tensors="pt", padding=True, truncation=True
        )
        tokens = self._model.generate(**inputs)
        return self._tokenizer.decode(tokens[0], skip_special_tokens=True)
