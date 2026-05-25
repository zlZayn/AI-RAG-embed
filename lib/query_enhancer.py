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
            if response:
                return response
            print("[warn] enhancement returned empty, using original question")
            return question
        except Exception as e:
            print(f"[warn] enhancement failed: {e}, using original question")
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
        return f"""You are a retrieval query optimizer. Your output is used ONLY for vector similarity search, never shown to the user.

Given a user question, produce a dense retrieval paragraph in {self._docs_lang} that maximizes the chance of matching relevant document chunks. Include:
1. The core topic expressed as a clear statement
2. Key technical terms and their full forms
3. Related concepts that relevant document sections might discuss
4. Brief descriptions of what answers might cover

Write 3-5 natural sentences. No formatting, no explanation, no bullet points.

Question: {question}
Output:"""
