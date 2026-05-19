from lib.llm_api import LlmApi


class QueryEnhancer:
    def __init__(self, llm_api: LlmApi, docs_lang: str = "en"):
        self._llm = llm_api
        self._docs_lang = docs_lang
        self._prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return f"""Translate the following question to {self._docs_lang}. Keep the original meaning.
If the question contains technical terms in another language, replace them with their {self._docs_lang} equivalents.
Output only the translated question, no explanation.

Question: {{question}}
Output:"""

    def enhance(self, question: str) -> str:
        messages = [{"role": "user", "content": self._prompt.format(question=question)}]
        try:
            response = self._llm.generate(messages)
            response = response.strip()
            return response if response else question
        except Exception:
            return question
