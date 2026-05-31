"""MCP tool implementations for RAG-QA."""

import sys
from contextlib import contextmanager


@contextmanager
def _mcp_safe():
    """Redirect stdout to stderr to protect MCP stdio protocol.

    Imported functions from rag_qa.py use print() for progress messages.
    MCP stdio transport uses stdout for protocol data, so any print()
    would corrupt the stream. This context manager sends those prints
    to stderr instead, where they appear in the agent's debug log.
    """
    old = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old
