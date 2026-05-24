import hashlib
import os
import re

import pathspec

_IGNORE_FILE = ".doc_loader_ignore"

_BREAK_PRIORITY = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "]

# Markdown parsing constants
UNIT_HEADING = "heading"
UNIT_PARAGRAPH = "paragraph"
UNIT_CODE = "code"
UNIT_TABLE = "table"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
CODE_FENCE = "```"
TABLE_ROW_RE = re.compile(r"^\|.+\||.+\|.+\|")


# ---------------------------------------------------------------------------
# Ignore-spec helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


def _parse_chunking_config(config: dict) -> dict:
    """Extract and validate chunking config, filling defaults."""
    raw = config.get("chunking", config)

    mode = raw.get("mode", "auto")
    if mode not in ("auto", "fixed"):
        raise ValueError(f"Invalid chunking mode: '{mode}'. Must be 'auto' or 'fixed'.")

    # Backward compat: top-level max_chars serves as fallback for both modes
    shared_max = raw.get("max_chars")

    auto_cfg = raw.get("auto", {})
    fixed_cfg = raw.get("fixed", {})

    if mode == "auto":
        max_chars = auto_cfg.get("target_chars", shared_max or 700)
    else:
        max_chars = fixed_cfg.get("max_chars", shared_max or 700)

    if max_chars <= 0:
        raise ValueError(f"max_chars must be positive, got {max_chars}")

    split_at_level = auto_cfg.get("split_at_level", 3)
    if not 1 <= split_at_level <= 6:
        raise ValueError(f"split_at_level must be 1-6, got {split_at_level}")

    return {
        "mode": mode,
        "max_chars": max_chars,
        "auto": {
            "target_chars": auto_cfg.get("target_chars", shared_max or 700),
            "split_at_level": split_at_level,
            "min_chars": auto_cfg.get("min_chars", 100),
            "include_heading": auto_cfg.get("include_heading", False),
        },
        "fixed": {
            "max_chars": fixed_cfg.get("max_chars", shared_max or 700),
            "overlap_chars": fixed_cfg.get("overlap_chars", 70),
        },
    }


# ---------------------------------------------------------------------------
# fixed mode
# ---------------------------------------------------------------------------


def _find_break(text: str, end: int, min_end: int) -> int:
    """Find the best break position in [min_end, end] by separator priority."""
    for sep in _BREAK_PRIORITY:
        idx = text.rfind(sep, min_end, end)
        if idx != -1:
            return idx + len(sep)
    return end


def _load_fixed(text: str, source: str, max_chars: int, overlap: int) -> list[dict]:
    """Fixed-length chunking with separator-priority fallback."""
    chunks = []
    start = 0

    while start < len(text):
        end = start + max_chars
        if end < len(text):
            min_end = start + max_chars // 2
            end = _find_break(text, end, min_end)
        else:
            end = len(text)

        chunk_text = text[start:end]
        chunks.append({"text": chunk_text, "source": source})
        if end >= len(text):
            break
        start = end - overlap

    return chunks


# ---------------------------------------------------------------------------
# auto mode - plain text
# ---------------------------------------------------------------------------


def _chunk_plain_text(text: str, max_chars: int, min_chars: int) -> list[str]:
    """Paragraph-first chunking for plain text. Returns list of text strings."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Fallback: if no double-newline paragraphs, try single newline
    if len(paragraphs) <= 1:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    # Still one chunk or fewer - return as-is
    if len(paragraphs) <= 1:
        return [text.strip()] if text.strip() else []

    chunks = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)

        if current_len + para_len <= max_chars:
            current.append(para)
            current_len += para_len
        else:
            if current:
                chunk_text = "\n\n".join(current)
                if len(chunk_text) >= min_chars:
                    chunks.append(chunk_text)
            current = [para]
            current_len = para_len

    if current:
        chunk_text = "\n\n".join(current)
        if len(chunk_text) >= min_chars:
            chunks.append(chunk_text)

    return chunks


# ---------------------------------------------------------------------------
# auto mode - markdown
# ---------------------------------------------------------------------------


def _extract_code_block(lines: list[str], start: int) -> tuple[str, int]:
    """Extract fenced code block starting at lines[start]. Returns (content, end_index)."""
    fence = lines[start].strip()
    end = start + 1
    while end < len(lines):
        if lines[end].strip().startswith(fence[:3]):
            end += 1
            break
        end += 1
    content = "\n".join(lines[start:end])
    return content, end


def _extract_table(lines: list[str], start: int) -> tuple[str, int]:
    """Extract table starting at lines[start]. Returns (content, end_index)."""
    end = start
    while end < len(lines):
        line = lines[end].strip()
        if not line or not ("|" in line):
            break
        end += 1
    content = "\n".join(lines[start:end])
    return content, end


def _extract_paragraph(lines: list[str], start: int) -> tuple[str, int]:
    """Extract paragraph starting at lines[start]. Returns (content, end_index)."""
    end = start
    while end < len(lines):
        line = lines[end].strip()
        if not line:
            break
        # Stop if we hit a heading, code fence, or table row
        if (
            HEADING_RE.match(line)
            or line.startswith(CODE_FENCE)
            or TABLE_ROW_RE.match(line)
        ):
            break
        end += 1
    content = "\n".join(lines[start:end])
    return content, end


def _parse_markdown(text: str) -> list[dict]:
    """Parse Markdown text into a list of structural units."""
    units = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # 1. Code block (highest priority)
        if line.strip().startswith(CODE_FENCE):
            content, end = _extract_code_block(lines, i)
            units.append({"type": UNIT_CODE, "content": content})
            i = end
            continue

        # 2. Heading
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            content = match.group(2).strip()
            units.append({"type": UNIT_HEADING, "content": content, "level": level})
            i += 1
            continue

        # 3. Table
        if TABLE_ROW_RE.match(line):
            content, end = _extract_table(lines, i)
            units.append({"type": UNIT_TABLE, "content": content})
            i = end
            continue

        # 4. Paragraph
        if line.strip():
            content, end = _extract_paragraph(lines, i)
            units.append({"type": UNIT_PARAGRAPH, "content": content})
            i = end
            continue

        i += 1  # skip blank lines

    return units


def _group_by_headings(units: list[dict], split_at_level: int) -> list[dict]:
    """Group structural units into sections by heading boundaries."""
    sections = []
    current = {"heading": None, "level": 0, "units": []}

    for unit in units:
        if unit["type"] == UNIT_HEADING and unit["level"] <= split_at_level:
            if current["units"]:
                sections.append(current)
            current = {
                "heading": unit["content"],
                "level": unit["level"],
                "units": [],
            }
        else:
            current["units"].append(unit)

    if current["units"]:
        sections.append(current)

    return sections


def _join_units(units: list[dict]) -> str:
    """Join a list of units into a single text string."""
    return "\n\n".join(u["content"] for u in units)


def _chunk_section(
    section: dict,
    max_chars: int,
    min_chars: int,
    include_heading: bool,
    source: str,
) -> list[dict]:
    """Chunk a single section. Returns list of {"text", "source"}."""
    units = section["units"]
    if not units:
        return []

    # Whole section fits in one chunk
    total = sum(len(u["content"]) for u in units)
    if total <= max_chars:
        text = _join_units(units)
        if len(text) >= min_chars:
            if include_heading and section["heading"]:
                text = f"> {section['heading']}\n\n{text}"
            return [{"text": text, "source": source}]
        return []

    # Need to split
    chunks: list[str] = []
    current_units: list[dict] = []
    current_len = 0

    for unit in units:
        unit_len = len(unit["content"])
        is_atomic = unit["type"] in (UNIT_CODE, UNIT_TABLE)

        if is_atomic:
            if current_units and current_len + unit_len > max_chars:
                chunk_text = _join_units(current_units)
                if len(chunk_text) >= min_chars:
                    chunks.append(chunk_text)
                current_units = []
                current_len = 0
            current_units.append(unit)
            current_len += unit_len
        else:
            if current_len + unit_len <= max_chars:
                current_units.append(unit)
                current_len += unit_len
            else:
                if current_units:
                    chunk_text = _join_units(current_units)
                    if len(chunk_text) >= min_chars:
                        chunks.append(chunk_text)
                current_units = [unit]
                current_len = unit_len

    if current_units:
        chunk_text = _join_units(current_units)
        if len(chunk_text) >= min_chars:
            chunks.append(chunk_text)

    # Attach heading and build output
    result = []
    for text in chunks:
        if include_heading and section["heading"]:
            text = f"> {section['heading']}\n\n{text}"
        result.append({"text": text, "source": source})
    return result


def _load_markdown(text: str, cfg: dict, source: str) -> list[dict]:
    """Markdown smart chunking entry point."""
    auto = cfg["auto"]
    units = _parse_markdown(text)
    sections = _group_by_headings(units, auto["split_at_level"])

    chunks = []
    for section in sections:
        chunks.extend(
            _chunk_section(
                section,
                max_chars=cfg["max_chars"],
                min_chars=auto["min_chars"],
                include_heading=auto["include_heading"],
                source=source,
            )
        )
    return chunks


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def load_documents(docs_dir: str, config: dict) -> tuple[list[dict], dict]:
    """Load and chunk documents. Returns (chunks, file_hashes)."""
    cfg = _parse_chunking_config(config)
    ignore_specs = _collect_ignore_specs(docs_dir)
    chunks = []
    file_hashes = {}

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

            file_hashes[relative_path] = hashlib.md5(text.encode("utf-8")).hexdigest()
            is_md = filename.endswith(".md")

            if cfg["mode"] == "fixed":
                file_chunks = _load_fixed(
                    text,
                    relative_path,
                    cfg["max_chars"],
                    cfg["fixed"]["overlap_chars"],
                )
            else:
                if is_md:
                    file_chunks = _load_markdown(text, cfg, source=relative_path)
                else:
                    file_chunks = [
                        {"text": t, "source": relative_path}
                        for t in _chunk_plain_text(
                            text, cfg["max_chars"], cfg["auto"]["min_chars"]
                        )
                    ]

            chunks.extend(file_chunks)

    return chunks, file_hashes
