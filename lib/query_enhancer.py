class QueryEnhancer:
    def __init__(self, llm_api=None, docs_lang: str = "en", translator=None):
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

        prompt = self._build_prompt(question, history)
        messages = [{"role": "user", "content": prompt}]
        try:
            response = self._llm.generate(messages)
            response = response.strip()
            return response if response else question
        except Exception:
            return question

    def _build_prompt(self, question: str, history: list | None = None) -> str:
        if history:
            conv_parts = []
            for msg in history:
                role = "User" if msg["role"] == "user" else "Assistant"
                conv_parts.append(f"{role}: {msg['content']}")
            conversation = "\n".join(conv_parts)
            return f"""Below is a conversation history. The user's latest question may refer to previous context.
Rewrite the latest question as a standalone query for retrieval in {self._docs_lang}.
Resolve any pronouns/ellipsis using the conversation history.
Output only the rewritten question, no explanation.

History:
{conversation}

Latest question: {question}
Rewritten:"""
        return f"""Translate the following question to {self._docs_lang}. Keep the original meaning.
If the question contains technical terms in another language, replace them with their {self._docs_lang} equivalents.
Output only the translated question, no explanation.

Question: {question}
Output:"""
