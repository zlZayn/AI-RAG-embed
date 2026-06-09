"""MCP server entry point for RAG-QA.

Exposes three tools:
  - rag_ask: end-to-end RAG QA (retrieve + generate)
  - rag_search: retrieve document chunks without LLM generation
  - rag_get_info: get RAG system config, indexed documents, and paths

Usage:
  python servers/rag_server.py          # stdio mode (for agent connection)
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add project root to sys.path so tools/ and rag_qa are importable
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP  # noqa: E402
from tools.rag_ask import rag_ask  # noqa: E402
from tools.rag_get_info import rag_get_info  # noqa: E402
from tools.rag_search import rag_search  # noqa: E402
from tools.shared_store import warm_up  # noqa: E402


@asynccontextmanager
async def _lifespan(_app):
    """Pre-load models and index in a background thread at server startup."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, warm_up)
    yield {}


mcp = FastMCP("rag-qa", lifespan=_lifespan)

_READONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

mcp.tool(annotations=_READONLY)(rag_search)
mcp.tool(annotations=_READONLY)(rag_ask)
mcp.tool(annotations=_READONLY)(rag_get_info)

if __name__ == "__main__":
    mcp.run(transport="stdio")
