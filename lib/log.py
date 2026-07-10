"""Minimal logging utils for RAG-QA.

All progress, debug, info, warning, and error messages go to stderr.
Stdout is reserved for command output (answers, retrieved chunks)
or JSON-RPC (MCP mode).
"""

import sys


def log_step(msg: str, end: str = "\n", flush: bool = False) -> None:
    print(f"[step] {msg}", end=end, flush=flush, file=sys.stderr)


def log_info(msg: str) -> None:
    print(f"[info] {msg}", file=sys.stderr)


def log_warn(msg: str) -> None:
    print(f"[warn] {msg}", file=sys.stderr)


def log_error(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)


def log_debug(msg: str) -> None:
    print(f"[debug] {msg}", file=sys.stderr)


def log_load(msg: str) -> None:
    print(f"[load] {msg}", file=sys.stderr)


def log_retry(msg: str) -> None:
    print(f"[retry] {msg}", file=sys.stderr)
