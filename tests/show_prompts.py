"""Print current prompt templates and workflow to console.

Usage:
    python tests/show_prompts.py
"""

import os
import sys
import textwrap


def main() -> None:
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    from lib.prompt_templates import (
        ENHANCER_PROMPT,
        ENHANCER_PROMPT_WITH_HISTORY,
        SYSTEM_PROMPT_DEFAULT,
        _SYSTEM_PROMPT_LAX,
        _SYSTEM_PROMPT_STRICT,
    )

    _W = 74

    def _section(title: str) -> None:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}\n")

    def _template(name: str, text: str, placeholders: list[str]) -> None:
        ph = ", ".join(f"{{{p}}}" for p in placeholders)
        print(f"  Template: {name}")
        print(f"  Placeholders: {ph}")
        print("  ```text")
        for para in text.split("\n"):
            if para.strip():
                for line in textwrap.fill(para, width=_W - 4).split("\n"):
                    print(f"    {line}")
            else:
                print()
        print("  ```")
        print()

    # ── 1 ────────────────────────────────────────────────────────
    _section("1. Answer Generation (System Prompt)")

    print(
        "  This prompt is sent as the system message. It tells the LLM how to\n"
        "  use the retrieved context and how to format its final answer.\n"
    )

    _template("SYSTEM_PROMPT_DEFAULT", SYSTEM_PROMPT_DEFAULT, ["question", "context"])

    print("  Deprecated legacy fallbacks\n")

    _template(
        "_SYSTEM_PROMPT_STRICT  (strict_context = true)",
        _SYSTEM_PROMPT_STRICT,
        ["question", "context"],
    )
    _template(
        "_SYSTEM_PROMPT_LAX  (no strict_context override)",
        _SYSTEM_PROMPT_LAX,
        ["question", "context"],
    )

    # ── 2 ────────────────────────────────────────────────────────
    _section("2. Query Enhancement (Enhancer Prompts)")

    print(
        "  These prompts are sent to a separate LLM (or a translation model) to\n"
        "  rewrite the user's question before vector search.\n"
    )

    _template(
        "ENHANCER_PROMPT  (no conversation history)",
        ENHANCER_PROMPT,
        ["docs_lang", "question"],
    )
    _template(
        "ENHANCER_PROMPT_WITH_HISTORY  (multi-turn chat)",
        ENHANCER_PROMPT_WITH_HISTORY,
        ["docs_lang", "conversation", "question"],
    )

    # ── 3 ────────────────────────────────────────────────────────
    _section("3. Assembly Flow")

    print(
        "  How the pieces connect:\n"
        "\n"
        "  1. build_system_prompt(config)\n"
        "     Resolution: config.system_prompt -> strict_context -> SYSTEM_PROMPT_DEFAULT\n"
        "     Returns a template string with {question} and {context} placeholders\n"
        "\n"
        "  2. format_system_prompt(template, question, context)\n"
        "     Fills {question} with the user's original question\n"
        '     Fills {context} with retrieved chunks joined by "\\n\\n"\n'
        "\n"
        "  3. build_qa_messages(template, question, context, history)\n"
        "     Wraps into: [system, ...conversation_history?, user]\n"
        "\n"
        "  4. (parallel) build_enhancer_prompt(docs_lang, question, history)\n"
        "     Selects the right enhancer template\n"
        "     Fills {docs_lang} and optionally {conversation}\n"
        "     Sent as a user message to the enhancer LLM -> rewritten question\n"
    )

    # ── 4 ────────────────────────────────────────────────────────
    _section("4. Where Placeholders Come From")

    print(
        "  {question}      Answer generation + enhancer\n"
        "                  The original question from user input\n"
        "\n"
        "  {context}       Answer generation\n"
        '                  Retrieved document chunks joined by "\\n\\n"\n'
        "\n"
        "  {docs_lang}     Query enhancement\n"
        '                  config.json field: docs_lang (e.g. "en", "zh")\n'
        "\n"
        "  {conversation}  Query enhancement (with history only)\n"
        "                  Formatted from previous turns:\n"
        "                    User: <question>\n"
        "                    Assistant: <answer>\n"
    )


if __name__ == "__main__":
    main()
