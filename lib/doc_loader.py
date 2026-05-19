import os

import pathspec

_IGNORE_FILE = ".doc_loader_ignore"


def _collect_ignore_specs(docs_dir: str) -> list[tuple[str, pathspec.PathSpec]]:
    specs: list[tuple[str, pathspec.PathSpec]] = []
    for root, _, files in os.walk(docs_dir):
        if _IGNORE_FILE in files:
            filepath = os.path.join(root, _IGNORE_FILE)
            with open(filepath, "r", encoding="utf-8") as f:
                spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
                specs.append((root, spec))
    return specs


def _is_ignored(filepath: str, specs: list[tuple[str, pathspec.PathSpec]]) -> bool:
    for base, spec in specs:
        if filepath.startswith(base):
            rel = os.path.relpath(filepath, base)
            if spec.match_file(rel):
                return True
    return False


def load_documents(
    docs_dir: str, chunk_size: int = 500, chunk_overlap: int = 50
) -> list[dict]:
    ignore_specs = _collect_ignore_specs(docs_dir)
    chunks = []

    for root, _, files in os.walk(docs_dir):
        for filename in files:
            if filename == _IGNORE_FILE:
                continue
            if not filename.endswith((".txt", ".md")):
                continue

            filepath = os.path.join(root, filename)

            if _is_ignored(filepath, ignore_specs):
                continue

            relative_path = os.path.relpath(filepath, docs_dir)

            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()

            if not text.strip():
                continue

            start = 0
            while start < len(text):
                end = start + chunk_size
                chunk_text = text[start:end]
                chunks.append({"text": chunk_text, "source": relative_path})
                if end >= len(text):
                    break
                start = end - chunk_overlap

    return chunks
