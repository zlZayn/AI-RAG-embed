from lib.prompt_templates import build_enhancer_prompt


class QueryEnhancer:
    def __init__(
        self,
        llm_api=None,
        docs_lang: str = "en",
        translator=None,
    ):
        self._llm = llm_api
        self._translator = translator
        self._docs_lang = docs_lang

    @property
    def label(self) -> str:
        if self._translator:
            return "Translated Question"
        return "Enhanced Question"

    def enhance(self, question: str, history: list | None = None) -> str:
        if self._translator:
            return self._translator.translate(question)

        if not self._llm:
            return question

        prompt = build_enhancer_prompt(self._docs_lang, question, history)
        messages = [{"role": "user", "content": prompt}]
        try:
            response = self._llm.generate(messages)
            response = response.strip()
            if response:
                return response
            print("[warn] enhancement returned empty, using original question")
            return question
        except Exception as e:
            print(f"[warn] enhancement failed: {e}, using original question")
            return question
