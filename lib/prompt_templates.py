"""Centralized prompt template management.

All prompt templates and their assembly logic live here.
Config should only contain runtime parameters, not prompt text.
"""

# ── System Prompt (answer generation) ──────────────────────────

SYSTEM_PROMPT_DEFAULT = (
    "You are a helpful assistant. Answer the user's question below.\n\n"
    "Before using the provided context, assess whether it is actually relevant "
    "to the question. If the context is irrelevant or unhelpful, ignore it and "
    "answer from your own knowledge.\n\n"
    "When the context is relevant, use it as a primary source. You may supplement "
    "with your own knowledge when the context is insufficient, but prefer the "
    "context for factual claims.\n\n"
    "Always respond in the same language as the user's question.\n\n"
    "No emoji. No ASCII art diagrams.\n"
    "Answer directly as if the knowledge is your own. Do not use phrases like "
    '"according to the context" or "based on the provided information".\n\n'
    "Guidelines:\n"
    "- If you add substantive information that is not present in the retrieved "
    'context, briefly append "[general knowledge]" at the end of that sentence.\n'
    "- If the retrieved context is missing minor details (e.g., a specific number, "
    'date, or name), you may use your best judgment, but mark it with "[inferred]".\n'
    "- If the retrieved context directly contradicts your knowledge, follow the "
    'context and note the discrepancy with "[source says X, general knowledge '
    'says Y]".\n\n'
    "Formatting rules (strict):\n"
    "- ALWAYS start your answer with a level-1 markdown heading (#) that captures "
    "the topic.\n"
    "- Then use ##, ### etc. for subsections as appropriate.\n"
    "- Surround headings with blank lines.\n"
    "- Surround fenced code blocks with blank lines.\n"
    "- Surround lists with blank lines.\n"
    "- Never have more than one consecutive blank line.\n"
    "- Wrap math formulas in $...$ or $$...$$.\n\n"
    "---\n\n"
    "Question: {question}\n\n"
    "Context:\n{context}"
)

# Legacy fallback templates (when config lacks system_prompt)
_SYSTEM_PROMPT_STRICT = (
    "You are a helpful assistant. Answer the user's question based ONLY "
    "on the provided context. If the answer is not in the context, say "
    "'I don't know'. Always respond in the same language as the user's "
    "question."
)

_SYSTEM_PROMPT_LAX = (
    "You are a helpful assistant. Use the provided context to enrich "
    "your answer, but also draw on your own knowledge when the context "
    "is insufficient. If the context is provided, prefer it over your "
    "own knowledge for factual claims. Always respond in the same "
    "language as the user's question."
)

# ── Enhancer Prompts (query enhancement) ───────────────────────

ENHANCER_PROMPT = (
    "You are a retrieval query optimizer. Your output is used ONLY for "
    "vector similarity search, never shown to the user.\n\n"
    "Given a user question, produce a dense retrieval paragraph in {docs_lang} "
    "that maximizes the chance of matching relevant document chunks. Include:\n"
    "1. The core topic expressed as a clear statement\n"
    "2. Key technical terms and their full forms\n"
    "3. Related concepts that relevant document sections might discuss\n"
    "4. Brief descriptions of what answers might cover\n\n"
    "Write 3-5 natural sentences. No formatting, no explanation, no bullet points.\n\n"
    "Question: {question}\nOutput:"
)

ENHANCER_PROMPT_WITH_HISTORY = (
    "Below is a conversation history. The user's latest question may refer "
    "to previous context.\n"
    "Rewrite the latest question as a standalone query for retrieval in "
    "{docs_lang}.\n"
    "Resolve any pronouns/ellipsis using the conversation history.\n"
    "Output only the rewritten question, no explanation.\n\n"
    "History:\n{conversation}\n\n"
    "Latest question: {question}\nRewritten:"
)


# ── Assembly Functions ─────────────────────────────────────────


def build_system_prompt(config: dict) -> str:
    """Return system prompt template.

    Uses SYSTEM_PROMPT_DEFAULT from this module.
    If strict_context is true, uses the strict template instead.
    """
    if config.get("strict_context"):
        return (
            _SYSTEM_PROMPT_STRICT
            + "\n\n---\n\nQuestion: {question}\n\nContext:\n{context}"
        )

    return SYSTEM_PROMPT_DEFAULT


def format_system_prompt(template: str, question: str, context: str) -> str:
    """Fill system prompt template with actual question and context."""
    return template.format(question=question, context=context)


def build_enhancer_prompt(
    docs_lang: str,
    question: str,
    history: list | None = None,
) -> str:
    """Build the enhancer prompt for query rewriting."""
    if history:
        conv_parts = []
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            conv_parts.append(f"{role}: {msg['content']}")
        conversation = "\n".join(conv_parts)
        return ENHANCER_PROMPT_WITH_HISTORY.format(
            docs_lang=docs_lang,
            conversation=conversation,
            question=question,
        )
    return ENHANCER_PROMPT.format(
        docs_lang=docs_lang,
        question=question,
    )


def build_qa_messages(
    system_prompt_template: str,
    question: str,
    context: str,
    messages_history: list[dict] | None = None,
) -> list[dict]:
    """Assemble the full messages array for answer generation.

    Returns a list with a system message (filled template), optional
    conversation history, and the user's question as the final message.
    """
    formatted = format_system_prompt(system_prompt_template, question, context)
    messages = [{"role": "system", "content": formatted}]
    if messages_history:
        messages.extend(messages_history)
    messages.append({"role": "user", "content": question})
    return messages
