"""Tests: design-property tests for smart chunking.

Each test group verifies a specific design decision.
Input data is crafted to hit exact boundaries.

Design
------
- make_config(): all _load_markdown tests go through real _parse_chunking_config,
  so config format changes are caught immediately.
- _load_fixed_by_chars / _load_fixed_by_lines / _chunk_plain_text tests call functions directly with raw params,
  isolating function behavior from config parsing.
- _parse_chunking_config tests verify validation and backward compatibility.

When to update
--------------
- New chunking mode or atomic unit type.
- Config schema changes (field rename, nesting, validation rules).
- Behavior semantics change (e.g. min_chars from drop to merge).

Not covered (out of scope)
--------------------------
- rag_qa.py orchestration, llm_api.py, vector_db.py, embed_engine.py.

Run: pytest tests/test_chunking.py -v
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.doc_loader import (
    _chunk_plain_text,
    _load_fixed_by_chars,
    _load_fixed_by_lines,
    _load_markdown,
    _load_typst,
    _parse_chunking_config,
    load_documents,
)


def make_config(
    size,
    *,
    mode="auto",
    split_at_level=3,
    min_chars=5,
    include_heading=False,
    overlap_chars=0,
    split_by="char",
    max_lines=20,
    overlap_lines=3,
):
    """Build a parsed chunking config via _parse_chunking_config.

    Ensures tests go through real config parsing rather than hardcoded dicts.
    """
    if mode == "auto":
        raw = {
            "chunking": {
                "mode": "auto",
                "auto": {
                    "target_chars": size,
                    "split_at_level": split_at_level,
                    "min_chars": min_chars,
                    "include_heading": include_heading,
                },
            }
        }
    else:
        raw = {
            "chunking": {
                "mode": "fixed",
                "fixed": {
                    "split_by": split_by,
                    "char": {
                        "max_chars": size,
                        "overlap_chars": overlap_chars,
                    },
                    "line": {
                        "max_lines": max_lines,
                        "overlap_lines": overlap_lines,
                    },
                },
            }
        }
    return _parse_chunking_config(raw)


# ======================================================================
# Atomic units
# ======================================================================


def test_code_block_atomic():
    """Code blocks are never split, even when > target_chars."""
    code_lines = ["```python"]
    for i in range(20):
        code_lines.append(f"    result.append(i * {i})")
    code_lines.append("```")
    code_block = "\n".join(code_lines)
    code_len = len(code_block)

    md = f"# Section\n\nSome text before.\n\n{code_block}\n\nSome text after.\n"
    chunks = _load_markdown(md, make_config(100), source="t.md")

    code_chunks = [c for c in chunks if "```python" in c["text"]]
    assert len(code_chunks) == 1, f"code block in {len(code_chunks)} chunks"

    text = code_chunks[0]["text"]
    assert text.startswith("```python"), f"starts with: {text[:30]!r}"
    assert text.strip().endswith("```"), f"ends with: {text[-20:]!r}"
    assert len(text) >= code_len, f"chunk={len(text)}, code={code_len}"

    other = [
        c for c in chunks if c is not code_chunks[0] and "result.append" in c["text"]
    ]
    assert len(other) == 0, "code fragments leaked into other chunks"


def test_table_atomic():
    """Tables are never split, even when > target_chars."""
    table_lines = ["| Col A | Col B | Col C |", "|---|---|---|"]
    for i in range(15):
        table_lines.append(f"| val {i}a | val {i}b | val {i}c |")
    table = "\n".join(table_lines)
    table_len = len(table)

    md = f"# Data\n\n{table}\n\nSome text after.\n"
    chunks = _load_markdown(md, make_config(80), source="t.md")

    table_chunks = [c for c in chunks if "Col A" in c["text"]]
    assert len(table_chunks) == 1, f"table in {len(table_chunks)} chunks"

    text = table_chunks[0]["text"]
    assert "| Col A |" in text, "missing first row"
    assert "val 14c" in text, "missing last row"
    assert len(text) >= table_len, f"chunk={len(text)}, table={table_len}"


def test_paragraph_atomic():
    """Paragraphs are never split in auto mode."""
    long_para = "This is a single long paragraph that exceeds the max_chars limit. " * 5
    para_len = len(long_para)

    md = f"# Title\n\n{long_para}\n\nShort para.\n"
    chunks = _load_markdown(md, make_config(100), source="t.md")

    para_chunks = [c for c in chunks if long_para[:30] in c["text"]]
    assert len(para_chunks) == 1, f"paragraph in {len(para_chunks)} chunks"

    assert long_para[-30:] in para_chunks[0]["text"], "paragraph truncated"
    assert len(para_chunks[0]["text"]) >= para_len


# ======================================================================
# Heading boundaries
# ======================================================================


def test_heading_hard_boundary():
    """No chunk spans across heading boundaries."""
    md = """\
# Chapter

## Section A

Content of section A with some extra text to make it longer.

## Section B

Content of section B with some extra text to make it longer.
"""
    chunks = _load_markdown(md, make_config(2000, split_at_level=2), source="t.md")

    assert len(chunks) >= 2, f"expected >= 2 chunks, got {len(chunks)}"
    for i, c in enumerate(chunks):
        has_a = "Content of section A" in c["text"]
        has_b = "Content of section B" in c["text"]
        assert not (has_a and has_b), f"chunk {i} spans both sections"


def test_split_at_level():
    """Higher split_at_level produces more chunks."""
    md = """\
# Top

## Section 1

Paragraph one.

### Sub 1.1

Sub paragraph A.

### Sub 1.2

Sub paragraph B.

## Section 2

Paragraph two.
"""
    cfg2 = make_config(2000, split_at_level=2)
    cfg3 = make_config(2000, split_at_level=3)

    chunks2 = _load_markdown(md, cfg2, source="t.md")
    chunks3 = _load_markdown(md, cfg3, source="t.md")

    assert len(chunks3) > len(chunks2), f"level2={len(chunks2)}, level3={len(chunks3)}"

    # At level=2, sub-sections merged into section 1
    s1_chunk = [c for c in chunks2 if "Sub paragraph A" in c["text"]]
    if s1_chunk:
        assert "Sub paragraph B" in s1_chunk[0]["text"], (
            "level=2 should merge sub-sections"
        )

    # At level=3, sub-sections separated
    s11 = [
        c
        for c in chunks3
        if "Sub paragraph A" in c["text"] and "Sub paragraph B" not in c["text"]
    ]
    s12 = [
        c
        for c in chunks3
        if "Sub paragraph B" in c["text"] and "Sub paragraph A" not in c["text"]
    ]
    assert len(s11) == 1 and len(s12) == 1, f"s11={len(s11)}, s12={len(s12)}"


def test_min_chars_filter():
    """Short sections below min_chars are dropped, not merged."""
    md = """\
# Main

## Short Section

Tiny.

## Long Section

This section has enough content to meet the minimum character threshold
and should definitely appear in the output as a separate chunk.
"""
    chunks = _load_markdown(md, make_config(2000, min_chars=40), source="t.md")
    texts = [c["text"] for c in chunks]

    assert not any("Tiny." in t for t in texts), "short section should be dropped"
    assert any("minimum character threshold" in t for t in texts), (
        "long section should be kept"
    )
    assert not any("Tiny." in t and "minimum character" in t for t in texts), (
        "short should not merge into long"
    )


# ======================================================================
# include_heading
# ======================================================================


def test_include_heading():
    """include_heading=true prepends '> heading' to each chunk."""
    md = """\
# Chapter

## Section Alpha

Content of alpha.

## Section Beta

Content of beta.
"""
    chunks = _load_markdown(md, make_config(2000, include_heading=True), source="t.md")

    assert all(c["text"].startswith("> ") for c in chunks), (
        f"first lines: {[c['text'][:20] for c in chunks]}"
    )
    assert any(c["text"].startswith("> Section Alpha") for c in chunks)
    assert any(c["text"].startswith("> Section Beta") for c in chunks)


def test_no_include_heading():
    """include_heading=false produces no heading prefix."""
    md = """\
# Chapter

## Section

Content here.
"""
    chunks = _load_markdown(md, make_config(2000, include_heading=False), source="t.md")
    assert all(not c["text"].startswith("> ") for c in chunks)


# ======================================================================
# Fixed mode
# ======================================================================


def test_fixed_respects_max():
    """Fixed mode: no chunk exceeds max_chars."""
    text = "Word " * 200  # ~1000 chars
    chunks = _load_fixed_by_chars(text, "t.txt", max_chars=100, overlap_chars=0)

    max_actual = max(len(c["text"]) for c in chunks)
    assert max_actual <= 110, f"max_chars=100, actual max={max_actual}"
    assert len(chunks) > 5, f"expected > 5 chunks, got {len(chunks)}"


def test_fixed_overlap():
    """Fixed mode with overlap: adjacent chunks share content."""
    text = "A" * 100 + "BREAK" + "B" * 100 + "BREAK" + "C" * 100
    chunks_no = _load_fixed_by_chars(text, "t.txt", max_chars=120, overlap_chars=0)
    chunks_ov = _load_fixed_by_chars(text, "t.txt", max_chars=120, overlap_chars=20)

    assert len(chunks_ov) >= len(chunks_no), (
        f"no_overlap={len(chunks_no)}, overlap={len(chunks_ov)}"
    )

    if len(chunks_ov) >= 2:
        c0_end = chunks_ov[0]["text"][-20:]
        c1_start = chunks_ov[1]["text"][:20]
        shared = sum(1 for a, b in zip(c0_end, c1_start) if a == b)
        assert shared > 5, f"shared chars in overlap zone: {shared}"


def test_fixed_separator_priority():
    """Fixed mode prefers paragraph break > newline > period > space."""
    # \n\n at pos 60-61, \n at pos 80. Both in search range [45, 90].
    text = "A" * 60 + "\n\n" + "B" * 18 + "\n" + "C" * 40 + ". " + "D" * 40
    chunks = _load_fixed_by_chars(text, "t.txt", max_chars=90, overlap_chars=0)

    if chunks:
        first = chunks[0]["text"]
        assert first.rstrip() == "A" * 60, f"ends with: ...{first[-20:]!r}"


# ======================================================================
# Fixed mode - line-based
# ======================================================================


def test_fixed_by_lines_respects_max():
    """Line mode: no chunk exceeds max_lines (except possibly the last)."""
    lines = [f"Line {i} content here." for i in range(50)]
    text = "\n".join(lines)
    chunks = _load_fixed_by_lines(text, "t.txt", max_lines=10, overlap_lines=0)

    assert len(chunks) >= 5, f"expected >= 5 chunks, got {len(chunks)}"
    for c in chunks[:-1]:
        line_count = c["text"].count("\n") + 1
        assert line_count <= 10, f"chunk has {line_count} lines, max is 10"


def test_fixed_by_lines_preserves_lines():
    """Line mode: no line is split mid-way."""
    lines = [f"Line {i} with some content." for i in range(30)]
    text = "\n".join(lines)
    chunks = _load_fixed_by_lines(text, "t.txt", max_lines=8, overlap_lines=2)

    for c in chunks:
        for original_line in lines:
            if original_line in c["text"]:
                # If a line starts in this chunk, it must also end in this chunk
                idx = c["text"].index(original_line)
                after = c["text"][idx + len(original_line) :]
                # The next char should be \n or end-of-text, not a mid-line continuation
                assert not after or after[0] == "\n", (
                    f"line appears truncated: ...{c['text'][idx : idx + len(original_line) + 10]!r}"
                )


def test_fixed_by_lines_overlap():
    """Line mode with overlap: adjacent chunks share lines."""
    lines = [f"Line {i}." for i in range(30)]
    text = "\n".join(lines)
    chunks_no = _load_fixed_by_lines(text, "t.txt", max_lines=10, overlap_lines=0)
    chunks_ov = _load_fixed_by_lines(text, "t.txt", max_lines=10, overlap_lines=3)

    assert len(chunks_ov) >= len(chunks_no), (
        f"no_overlap={len(chunks_no)}, overlap={len(chunks_ov)}"
    )

    if len(chunks_ov) >= 2:
        # Last 3 lines of chunk 0 should appear at the start of chunk 1
        c0_lines = chunks_ov[0]["text"].split("\n")
        c1_lines = chunks_ov[1]["text"].split("\n")
        shared = c0_lines[-3:]
        for i, line in enumerate(shared):
            assert line == c1_lines[i], (
                f"overlap mismatch: chunk0[-{3 - i}]={line!r}, chunk1[{i}]={c1_lines[i]!r}"
            )


def test_fixed_by_lines_blank_line_break():
    """Line mode prefers blank lines as split points."""
    lines = ["A"] * 5 + [""] + ["B"] * 5 + [""] + ["C"] * 10
    text = "\n".join(lines)
    chunks = _load_fixed_by_lines(text, "t.txt", max_lines=8, overlap_lines=0)

    # Should split at blank line boundaries, not mid-group
    for c in chunks:
        c_lines = c["text"].split("\n")
        # A chunk should not mix A-group and C-group without B-group
        has_a = any(l == "A" for l in c_lines)
        has_c = any(l == "C" for l in c_lines)
        has_b = any(l == "B" for l in c_lines)
        if has_a and has_c:
            assert has_b, "chunk spans A and C without B — bad break point"


def test_fixed_by_lines_short_text():
    """Text with fewer lines than max_lines returns a single chunk."""
    text = "Line 1\nLine 2\nLine 3"
    chunks = _load_fixed_by_lines(text, "t.txt", max_lines=10, overlap_lines=0)
    assert len(chunks) == 1, f"expected 1 chunk, got {len(chunks)}"
    assert chunks[0]["text"] == text


def test_fixed_by_lines_empty_text():
    """Empty text returns no chunks."""
    assert _load_fixed_by_lines("", "t.txt", max_lines=10, overlap_lines=0) == []
    assert (
        _load_fixed_by_lines("   \n\n  ", "t.txt", max_lines=10, overlap_lines=0) == []
    )


def test_fixed_by_lines_overlap_zero():
    """overlap_lines=0 produces non-overlapping chunks."""
    lines = [f"Line {i}." for i in range(20)]
    text = "\n".join(lines)
    chunks = _load_fixed_by_lines(text, "t.txt", max_lines=5, overlap_lines=0)

    all_lines = []
    for c in chunks:
        all_lines.extend(c["text"].split("\n"))
    # Every line should appear exactly once
    for i in range(20):
        assert all_lines.count(f"Line {i}.") == 1, (
            f"Line {i} appears {all_lines.count(f'Line {i}.')} times"
        )


def test_fixed_by_lines_overlap_max_minus_one():
    """Boundary: overlap_lines = max_lines - 1 (step = 1)."""
    lines = [f"Line {i}." for i in range(10)]
    text = "\n".join(lines)
    chunks = _load_fixed_by_lines(text, "t.txt", max_lines=5, overlap_lines=4)

    assert len(chunks) > 1, "step=1 should produce multiple chunks"
    # Each chunk advances by 1 line: c0 starts at line 0, c1 starts at line 1, etc.
    for i in range(len(chunks) - 1):
        c0_lines = chunks[i]["text"].split("\n")
        c1_lines = chunks[i + 1]["text"].split("\n")
        # c1 should start 1 line after c0
        assert c0_lines[1] == c1_lines[0], (
            f"step=1 advance mismatch: c0[1]={c0_lines[1]!r} vs c1[0]={c1_lines[0]!r}"
        )
        # Overlap region: last 4 lines of c0 == first 4 lines of c1
        assert c0_lines[-4:] == c1_lines[:4], (
            f"overlap mismatch: c0 tail={c0_lines[-4:]}, c1 head={c1_lines[:4]}"
        )


# ======================================================================
# Fixed mode - config parsing and backward compat
# ======================================================================


def test_fixed_split_by_config():
    """_parse_chunking_config correctly parses split_by."""
    cfg = _parse_chunking_config(
        {"chunking": {"mode": "fixed", "fixed": {"split_by": "line"}}}
    )
    assert cfg["fixed"]["split_by"] == "line"

    cfg2 = _parse_chunking_config(
        {"chunking": {"mode": "fixed", "fixed": {"split_by": "char"}}}
    )
    assert cfg2["fixed"]["split_by"] == "char"


def test_fixed_backward_compat_flat():
    """Old format: fixed.max_chars maps to split_by='char'."""
    cfg = _parse_chunking_config(
        {
            "chunking": {
                "mode": "fixed",
                "fixed": {"max_chars": 500, "overlap_chars": 50},
            }
        }
    )
    assert cfg["fixed"]["split_by"] == "char"
    assert cfg["fixed"]["char"]["max_chars"] == 500
    assert cfg["fixed"]["char"]["overlap_chars"] == 50


def test_fixed_backward_compat_top_level():
    """Oldest format: chunking.max_chars falls back to split_by='char'."""
    cfg = _parse_chunking_config({"chunking": {"mode": "fixed", "max_chars": 400}})
    assert cfg["fixed"]["split_by"] == "char"
    assert cfg["fixed"]["char"]["max_chars"] == 400


def test_fixed_invalid_split_by():
    """split_by='invalid' raises ValueError."""
    try:
        _parse_chunking_config(
            {"chunking": {"mode": "fixed", "fixed": {"split_by": "invalid"}}}
        )
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_fixed_line_overlap_exceeds_max():
    """overlap_lines >= max_lines raises ValueError."""
    try:
        _parse_chunking_config(
            {
                "chunking": {
                    "mode": "fixed",
                    "fixed": {"line": {"max_lines": 5, "overlap_lines": 5}},
                }
            }
        )
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_fixed_char_overlap_exceeds_max():
    """overlap_chars >= max_chars raises ValueError."""
    try:
        _parse_chunking_config(
            {
                "chunking": {
                    "mode": "fixed",
                    "fixed": {"char": {"max_chars": 100, "overlap_chars": 100}},
                }
            }
        )
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_plain_text_paragraph_split():
    """Plain text: paragraphs (double newline) are not cut."""
    text = "Short A.\n\n" + "B" * 200 + "\n\nShort C.\n\n" + "D" * 200
    chunks = _chunk_plain_text(text, max_chars=150, min_chars=5)

    b_chunks = [c for c in chunks if "B" * 200 in c]
    d_chunks = [c for c in chunks if "D" * 200 in c]
    assert len(b_chunks) == 1, "long paragraph B should be in one chunk"
    assert len(d_chunks) == 1, "long paragraph D should be in one chunk"

    assert sum(len(c) for c in chunks) >= len(text) - text.count("\n\n") * 2


def test_plain_text_single_newline_fallback():
    """No double newlines falls back to single newline splitting."""
    text = "Line one.\nLine two.\nLine three.\nLine four."
    chunks = _chunk_plain_text(text, max_chars=30, min_chars=3)
    assert len(chunks) > 1, f"expected > 1 chunk, got {len(chunks)}"


# ======================================================================
# Edge cases
# ======================================================================


def test_no_heading_single_section():
    """Document with no headings treats all content as one section."""
    md = "Paragraph one with some content.\n\nParagraph two with more content.\n"
    chunks = _load_markdown(md, make_config(2000), source="t.md")

    assert len(chunks) >= 1
    assert "Paragraph one" in chunks[0]["text"] and "Paragraph two" in chunks[0]["text"]


def test_multiple_code_blocks():
    """Two code blocks in one section, both kept whole."""
    code1 = "```python\n" + "x = 1\n" * 30 + "```"
    code2 = "```python\n" + "y = 2\n" * 30 + "```"
    md = f"# Section\n\n{code1}\n\nSome text.\n\n{code2}\n"

    chunks = _load_markdown(md, make_config(100), source="t.md")

    c1 = [c for c in chunks if "x = 1" in c["text"]]
    c2 = [c for c in chunks if "y = 2" in c["text"]]
    assert len(c1) == 1, "code block 1 should be in one chunk"
    assert len(c2) == 1, "code block 2 should be in one chunk"
    assert c1[0]["text"].strip().endswith("```"), "code block 1 closing fence"
    assert c2[0]["text"].strip().endswith("```"), "code block 2 closing fence"


def test_code_after_heading():
    """Code block immediately after heading is preserved."""
    md = "# Title\n\n```python\nprint('hello')\n```\n\nText after.\n"
    chunks = _load_markdown(md, make_config(50), source="t.md")

    code_chunks = [c for c in chunks if "print('hello')" in c["text"]]
    assert len(code_chunks) == 1, f"expected 1 code chunk, got {len(code_chunks)}"

    text = code_chunks[0]["text"]
    assert "```python" in text, "missing opening fence"
    assert text.count("```") >= 2, f"found {text.count('```')} fence markers"
    assert "print('hello')" in text, "code content lost"


def test_empty_document():
    """Empty files produce no chunks, no crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "empty.md"), "w") as f:
            f.write("")
        with open(os.path.join(tmpdir, "whitespace.txt"), "w") as f:
            f.write("   \n\n  \n")

        cfg = make_config(200, min_chars=5)
        chunks, hashes = load_documents(tmpdir, cfg)
        assert len(chunks) == 0, f"expected 0 chunks, got {len(chunks)}"


# ======================================================================
# Config parsing
# ======================================================================


def test_config_validation():
    """Invalid config values are rejected."""
    assert _parse_chunking_config({"chunking": {"mode": "auto"}})["mode"] == "auto"

    try:
        _parse_chunking_config({"chunking": {"mode": "bogus"}})
        assert False, "should have raised ValueError"
    except ValueError:
        pass

    try:
        _parse_chunking_config({"chunking": {"auto": {"target_chars": 0}}})
        assert False, "zero target_chars should be rejected"
    except ValueError:
        pass

    try:
        _parse_chunking_config(
            {"chunking": {"mode": "fixed", "fixed": {"max_chars": -100}}}
        )
        assert False, "negative max_chars should be rejected"
    except ValueError:
        pass

    try:
        _parse_chunking_config({"chunking": {"auto": {"split_at_level": 0}}})
        assert False, "split_at_level=0 should be rejected"
    except ValueError:
        pass

    try:
        _parse_chunking_config({"chunking": {"auto": {"split_at_level": 7}}})
        assert False, "split_at_level=7 should be rejected"
    except ValueError:
        pass


def test_flat_config_fallback():
    """Config without 'chunking' key falls back to using the whole dict."""
    cfg = _parse_chunking_config({"chunk_size": 500, "chunk_overlap": 50})
    assert cfg["max_chars"] == 700, f"expected 700, got {cfg['max_chars']}"
    assert cfg["mode"] == "auto"

    cfg2 = _parse_chunking_config({"mode": "fixed", "max_chars": 300})
    assert cfg2["max_chars"] == 300, f"expected 300, got {cfg2['max_chars']}"
    assert cfg2["mode"] == "fixed"


def test_mode_specific_chars():
    """Auto uses target_chars, fixed uses max_chars, backward compat works."""
    # New format
    cfg = _parse_chunking_config({"chunking": {"auto": {"target_chars": 500}}})
    assert cfg["max_chars"] == 500

    cfg2 = _parse_chunking_config(
        {"chunking": {"mode": "fixed", "fixed": {"max_chars": 400}}}
    )
    assert cfg2["max_chars"] == 400

    # Backward compat: top-level max_chars fallback
    cfg3 = _parse_chunking_config({"chunking": {"max_chars": 550, "auto": {}}})
    assert cfg3["max_chars"] == 550

    cfg4 = _parse_chunking_config(
        {"chunking": {"mode": "fixed", "max_chars": 650, "fixed": {}}}
    )
    assert cfg4["max_chars"] == 650

    # Mode-specific overrides top-level
    cfg5 = _parse_chunking_config(
        {"chunking": {"max_chars": 999, "auto": {"target_chars": 333}}}
    )
    assert cfg5["max_chars"] == 333


# ======================================================================
# Pipeline integration
# ======================================================================


def test_pipeline_source_relative():
    """load_documents returns relative source paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subdir = os.path.join(tmpdir, "sub")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "doc.md"), "w") as f:
            f.write("# Title\n\nSome content.\n")

        cfg = make_config(500, min_chars=5)
        chunks, _ = load_documents(tmpdir, cfg)
        assert all(not os.path.isabs(c["source"]) for c in chunks)
        if chunks:
            assert os.sep in chunks[0]["source"] or "/" in chunks[0]["source"], (
                f"source: {chunks[0]['source']}"
            )


def test_real_file_quality():
    """Against real documents/, verify structural properties hold."""
    docs_dir = os.path.join(os.path.dirname(__file__), "..", "documents")
    if not os.path.isdir(docs_dir):
        return

    cfg = make_config(400, min_chars=30)
    chunks, hashes = load_documents(docs_dir, cfg)
    if not chunks:
        return

    # No chunk has an unclosed fenced code block
    broken_fences = []
    for i, c in enumerate(chunks):
        lines = c["text"].split("\n")
        fence_lines = [ln for ln in lines if ln.strip().startswith("```")]
        if len(fence_lines) % 2 != 0:
            broken_fences.append(i)
    assert len(broken_fences) == 0, f"unclosed code blocks in chunks: {broken_fences}"

    # Most chunks are reasonably sized
    sizes = [len(c["text"]) for c in chunks]
    above_min = sum(1 for s in sizes if s >= 30)
    assert above_min / len(sizes) > 0.8, f"{above_min}/{len(sizes)} above min_chars"


# ======================================================================
# Typst auto mode
# ======================================================================


def test_typst_preamble_skipped():
    """Typst preamble (#set, #show, #let) is skipped, content starts at first heading."""
    typ = """\
#set page(paper: "a4")
#set text(size: 10pt)
#show heading: set block(spacing: 0pt)
#let x = 5

= Chapter One

Content here.
"""
    chunks = _load_typst(typ, make_config(2000), source="t.typ")
    assert len(chunks) >= 1
    text = chunks[0]["text"]
    assert "#set" not in text, "preamble should be skipped"
    assert "#show" not in text, "preamble should be skipped"
    assert "Content here" in text


def test_typst_heading_boundary():
    """Typst headings create section boundaries."""
    typ = """\
= Chapter

== Section A

Content of section A with extra text.

== Section B

Content of section B with extra text.
"""
    chunks = _load_typst(typ, make_config(2000, split_at_level=2), source="t.typ")
    assert len(chunks) >= 2, f"expected >= 2 chunks, got {len(chunks)}"
    for c in chunks:
        has_a = "Content of section A" in c["text"]
        has_b = "Content of section B" in c["text"]
        assert not (has_a and has_b), "chunk spans both sections"


def test_typst_table_atomic():
    """Typst tables (#figure + table) are atomic, never split."""
    rows = "\n".join(
        f"    [row {i} col 1], [row {i} col 2], [row {i} col 3]," for i in range(20)
    )
    typ = f"""\
= Data

#figure(
  table(
    columns: 3,
    table.header([Col A], [Col B], [Col C]),
{rows}
  ),
  kind: table,
)

Some text after.
"""
    chunks = _load_typst(typ, make_config(100), source="t.typ")
    table_chunks = [c for c in chunks if "Col A" in c["text"]]
    assert len(table_chunks) == 1, f"table in {len(table_chunks)} chunks"
    text = table_chunks[0]["text"]
    assert "row 19 col 3" in text, "last row missing"


def test_typst_quote_preserved():
    """Typst blockquotes are preserved as paragraph units."""
    typ = """\
= Section

#quote(block: true)[
  This is a blockquote with important information.
]

Normal paragraph after.
"""
    chunks = _load_typst(typ, make_config(2000), source="t.typ")
    assert any("blockquote" in c["text"] for c in chunks), "quote content missing"


def test_typst_hr_skipped():
    """Typst #hr separators are skipped."""
    typ = """\
= Section

First part.

#hr

Second part.
"""
    chunks = _load_typst(typ, make_config(2000), source="t.typ")
    text = " ".join(c["text"] for c in chunks)
    assert "#hr" not in text, "#hr should be skipped"


def test_typst_comments_skipped():
    """Typst // comments are skipped."""
    typ = """\
= Section

// This is a comment
Actual content.
"""
    chunks = _load_typst(typ, make_config(2000), source="t.typ")
    text = " ".join(c["text"] for c in chunks)
    assert "This is a comment" not in text
    assert "Actual content" in text


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
