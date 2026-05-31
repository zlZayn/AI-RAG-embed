"""MCP server entry point for RAG-QA.

Exposes two tools:
  - rag_ask: end-to-end RAG QA (retrieve + generate)
  - rag_search: retrieve document chunks without LLM generation

Usage:
  python servers/rag_server.py          # stdio mode (for agent connection)
"""

import sys
from pathlib import Path

# Add project root to sys.path so tools/ and rag_qa are importable
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP

from tools.rag_ask import rag_ask
from tools.rag_search import rag_search

mcp = FastMCP("rag-qa")

mcp.tool()(rag_search)
mcp.tool()(rag_ask)

if __name__ == "__main__":
    mcp.run(transport="stdio")
