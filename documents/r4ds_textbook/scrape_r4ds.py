#!/usr/bin/env python3
"""
R4DS (R for Data Science, 2e) Textbook Scraper
Scrapes all pages from https://r4ds.hadley.nz/ and organizes by chapter.
"""

import subprocess
import time
from pathlib import Path
from bs4 import BeautifulSoup

OUTPUT_DIR = Path(__file__).parent
DELAY = 0.5

# slug -> (section_num, chapter_dir, title_override)
# chapter_dir is None for part headers, actual dir for chapters
PAGES = {
    # Front matter
    "index": ("0", "00_front_matter", "Welcome"),
    "preface-2e": ("0.1", "00_front_matter", "Preface to the second edition"),
    "intro": ("0.2", "00_front_matter", "Introduction"),
    # Part I: Whole Game
    "whole-game": ("1", "01_whole_game", "Whole game"),
    "data-visualize": ("1.1", "01_whole_game", None),
    "workflow-basics": ("1.2", "01_whole_game", None),
    "data-transform": ("1.3", "01_whole_game", None),
    "workflow-style": ("1.4", "01_whole_game", None),
    "data-tidy": ("1.5", "01_whole_game", None),
    "workflow-scripts": ("1.6", "01_whole_game", None),
    "data-import": ("1.7", "01_whole_game", None),
    "workflow-help": ("1.8", "01_whole_game", None),
    # Part II: Visualize
    "visualize": ("2", "02_visualize", "Visualize"),
    "layers": ("2.1", "02_visualize", None),
    "EDA": ("2.2", "02_visualize", None),
    "communication": ("2.3", "02_visualize", None),
    # Part III: Transform
    "transform": ("3", "03_transform", "Transform"),
    "logicals": ("3.1", "03_transform", None),
    "numbers": ("3.2", "03_transform", None),
    "strings": ("3.3", "03_transform", None),
    "regexps": ("3.4", "03_transform", None),
    "factors": ("3.5", "03_transform", None),
    "datetimes": ("3.6", "03_transform", None),
    "missing-values": ("3.7", "03_transform", None),
    "joins": ("3.8", "03_transform", None),
    # Part IV: Import
    "import": ("4", "04_import", "Import"),
    "spreadsheets": ("4.1", "04_import", None),
    "databases": ("4.2", "04_import", None),
    "arrow": ("4.3", "04_import", None),
    "rectangling": ("4.4", "04_import", None),
    "webscraping": ("4.5", "04_import", None),
    # Part V: Program
    "program": ("5", "05_program", "Program"),
    "functions": ("5.1", "05_program", None),
    "iteration": ("5.2", "05_program", None),
    "base-R": ("5.3", "05_program", None),
    # Part VI: Communicate
    "communicate": ("6", "06_communicate", "Communicate"),
    "quarto": ("6.1", "06_communicate", None),
    "quarto-formats": ("6.2", "06_communicate", None),
}


def fetch_with_curl(url):
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "30", url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=35,
        )
        return result.stdout if result.returncode == 0 else None
    except Exception as e:
        print(f"Curl error: {e}")
        return None


def extract_content(html):
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    content = soup.find("div", class_="content")
    if not content:
        content = soup.find("main")
    if not content:
        content = soup.find("body")
    if not content:
        return None

    lines = []
    for element in content.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"]
    ):
        text = element.get_text(strip=True)
        if not text:
            continue

        if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            level = int(element.name[1])
            lines.append(f"\n{'#' * level} {text}\n")
        elif element.name == "p":
            lines.append(f"\n{text}\n")
        elif element.name == "li":
            lines.append(f"- {text}")
        elif element.name == "blockquote":
            lines.append(f"\n> {text}\n")
        elif element.name == "pre":
            code = element.get_text()
            lines.append(f"\n```\n{code}\n```\n")

    return "\n".join(lines)


def get_filename(section_num, slug):
    clean = slug.replace("-", "_")
    if section_num == "0":
        return "welcome.md"
    if "." in section_num:
        parts = section_num.split(".")
        return f"{parts[0]}_{parts[1]}_{clean}.md"
    return f"ch{section_num}_{clean}.md"


def main():
    print("=" * 60)
    print("R4DS Textbook Scraper")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = []

    for slug, (section_num, chapter_dir, title_override) in PAGES.items():
        url = f"https://r4ds.hadley.nz/{slug}.html"
        dir_path = OUTPUT_DIR / chapter_dir
        dir_path.mkdir(parents=True, exist_ok=True)

        html = fetch_with_curl(url)
        content = extract_content(html)

        if content:
            filename = get_filename(section_num, slug)
            filepath = dir_path / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[{section_num}] {slug} -> {chapter_dir}/{filename}")
            success += 1
        else:
            failed.append((section_num, slug))
            print(f"[{section_num}] FAILED: {slug}")

        time.sleep(DELAY)

    print(f"\n{'=' * 60}")
    print(f"Complete: {success} success, {len(failed)} failed")
    if failed:
        print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
