from lib.llm_api import LlmApi


class QueryEnhancer:
    def __init__(self, llm_api: LlmApi, docs_lang: str = "en"):
        self._llm = llm_api
        self._docs_lang = docs_lang
        self._prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return f"""Extract key technical terms from the user's question.
Rules:
1. Only extract terms that appear explicitly in the question
2. Do NOT infer, expand, or add related terms
3. Translate each term to {self._docs_lang}
4. Output format: JSON array, no explanation

Question: {{question}}
Output:"""

    def enhance(self, question: str) -> tuple[str, list[str]]:
        tags = self._extract_tags(question)
        if tags:
            enhanced_question = f"{question}\n\nRelated terms: {', '.join(tags)}"
            return enhanced_question, tags
        return question, tags

    def _extract_tags(self, question: str) -> list[str]:
        messages = [{"role": "user", "content": self._prompt.format(question=question)}]
        response = self._llm.generate(messages)
        try:
            import json

            tags = json.loads(response)
            if isinstance(tags, list):
                return [str(t).strip() for t in tags if t]
            return []
        except Exception:
            return []
