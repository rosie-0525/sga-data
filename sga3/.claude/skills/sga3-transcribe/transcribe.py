#!/usr/bin/env python3
"""Transcribe an SGA 3 exposé PDF into a rough minimal-HTML draft.

SGA 3 has no recoverable original LaTeX (unlike SGA1/SGA2) — 00-source_pdf/
holds only the mimeographed-era PDFs. This script's job is only to save
retyping the prose; pdftotext mangles math, diagrams, and structure (headings,
theorem/definition environments) beyond use, so it can only ever produce a
rough draft. The real transcription is a full manual rewrite of that draft
against the source PDF pages — see SKILL.md.

Usage:
    python3 transcribe.py origExp2.pdf     # by PDF filename
    python3 transcribe.py II               # by chapter_id (see chapter-map.json)
    python3 transcribe.py --all            # every entry not already transcribed
    python3 transcribe.py II --force       # overwrite an existing draft/transcription
"""
import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # .../sga3
SOURCE_DIR = ROOT / "00-source_pdf"
OUT_DIR = ROOT / "01-transcribed"
CHAPTER_MAP_PATH = ROOT / "chapter-map.json"

# Offline MathJax 3 + XyJax-v3, vendored under translation-viewer/ at the
# super-repo root.
HTML_HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script>
window.MathJax = {{
  loader: {{
    load: ['[custom]/xypic.js'],
    paths: {{ custom: '../../translation-viewer/vendor/xyjax' }}
  }},
  tex: {{
    packages: {{ '[+]': ['xypic', 'ams', 'color', 'mathtools'] }},
    inlineMath: [['\\\\(', '\\\\)']],
    displayMath: [['\\\\[', '\\\\]']],
    tags: 'none'
  }},
  options: {{ enableMenu: true }},
  startup: {{ typeset: false }}
}};
</script>
<script src="../../translation-viewer/vendor/mathjax/tex-svg-full.js" id="MathJax-script" async></script>
<style>
body {{ max-width: 46em; margin: 2em auto; padding: 0 1em; font-family: Georgia, "Times New Roman", serif; line-height: 1.5; }}
h1 {{ text-align: center; font-size: 1.3em; }}
h1 .author {{ display: block; font-size: 0.8em; font-weight: normal; margin-top: 0.5em; }}
h2 {{ margin-top: 2em; }}
h3 {{ margin-bottom: 0.3em; }}
.thm {{ margin: 1.2em 0; }}
.thm-head {{ font-weight: bold; }}
.thm-plain .thm-body {{ font-style: italic; }}
a.ref {{ text-decoration: none; }}
table.tabular {{ border-collapse: collapse; }}
table.tabular td {{ padding: 0.2em 0.6em; vertical-align: top; }}
ol.enumerate {{ list-style: none; padding-left: 1.5em; }}
ol.enumerate .item-label {{ display: inline-block; width: 2.5em; margin-left: -2.5em; }}
</style>
</head>
<body>
"""

HTML_TAIL = """
</body>
</html>
"""


def load_chapter_map():
    with open(CHAPTER_MAP_PATH, encoding="utf-8") as f:
        return json.load(f)


def find_entry(chapter_map, target):
    """Resolve a CLI target (pdf filename, with or without .pdf, or a
    chapter_id) to its chapter-map.json entry. Only searches `entries` —
    `excluded` and `outOfScope` are intentionally never matched."""
    target_pdf = target if target.lower().endswith(".pdf") else target + ".pdf"
    for entry in chapter_map["entries"]:
        if entry["pdf"] == target or entry["pdf"] == target_pdf:
            return entry
        ids = entry["chapter_id"] if isinstance(entry["chapter_id"], list) else [entry["chapter_id"]]
        if target in ids:
            return entry
    return None


def chapter_title(volume_title, chapter_id, kind):
    if kind == "front-matter":
        return f"{volume_title} — {chapter_id.capitalize()}"
    return f"{volume_title} — Exposé {chapter_id}"


def extract_text_from_pdf(pdf_path):
    result = subprocess.run(["pdftotext", str(pdf_path), "-"], capture_output=True, text=True, check=True)
    return result.stdout


def page_to_paragraphs(page_text):
    blocks = re.split(r"\n\s*\n", page_text.strip())
    paragraphs = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Reflow: join wrapped lines with spaces, PDF line breaks are not paragraph breaks.
        text = re.sub(r"\s*\n\s*", " ", block).strip()
        paragraphs.append(text)
    return paragraphs


def render_draft(pdf_path, title, extra_note=None):
    text = extract_text_from_pdf(pdf_path)
    pages = text.split("\x0c")
    parts = [HTML_HEAD.format(title=html.escape(title))]
    if extra_note:
        parts.append(f"<!-- {extra_note.replace('--', '——')} -->\n")
    for page_text in pages:
        if not page_text.strip():
            continue
        for paragraph in page_to_paragraphs(page_text):
            parts.append(f"<p>{html.escape(paragraph)}</p>\n")
    parts.append(HTML_TAIL)
    return "".join(parts)


def transcribe_entry(chapter_map, entry, force):
    pdf_path = SOURCE_DIR / entry["pdf"]
    if not pdf_path.exists():
        print(f"skip {entry['pdf']}: not found in {SOURCE_DIR}", file=sys.stderr)
        return False
    ids = entry["chapter_id"] if isinstance(entry["chapter_id"], list) else [entry["chapter_id"]]
    is_multi = len(ids) > 1
    volume_title = chapter_map.get("bookTitle", chapter_map.get("volume", "SGA"))

    note = None
    if is_multi:
        note = (
            f"NOTE: {entry['pdf']} contains multiple chapters ({', '.join(ids)}). "
            + (entry.get("note", "") or "")
            + " This draft has the FULL extracted text for all of them — split it"
            " manually between the chapter files."
        )

    wrote_any = False
    for chapter_id in ids:
        out_path = OUT_DIR / f"{chapter_id}.html"
        if out_path.exists() and not force:
            print(f"skip {out_path.relative_to(ROOT)}: already exists (use --force to overwrite)")
            continue
        title = chapter_title(volume_title, chapter_id, entry.get("kind"))
        draft = render_draft(pdf_path, title, extra_note=note)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path.write_text(draft, encoding="utf-8")
        print(f"wrote {out_path.relative_to(ROOT)} (draft — needs manual correction against {entry['pdf']})")
        wrote_any = True
    return wrote_any


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", help="PDF filename (e.g. origExp2.pdf) or chapter_id (e.g. II)")
    parser.add_argument("--all", action="store_true", help="transcribe every entry in chapter-map.json")
    parser.add_argument("--force", action="store_true", help="overwrite an existing draft/transcription")
    args = parser.parse_args()

    if not args.target and not args.all:
        parser.print_help()
        sys.exit(2)

    if not shutil.which("pdftotext"):
        print("error: pdftotext not found (install poppler-utils / poppler)", file=sys.stderr)
        sys.exit(1)

    chapter_map = load_chapter_map()

    if args.all:
        for entry in chapter_map["entries"]:
            transcribe_entry(chapter_map, entry, args.force)
        sys.exit(0)

    entry = find_entry(chapter_map, args.target)
    if entry is None:
        print(f"error: {args.target!r} is not a recognized PDF filename or chapter_id in {CHAPTER_MAP_PATH.relative_to(ROOT)}", file=sys.stderr)
        print("(note: entries under 'excluded' or 'outOfScope' are intentionally not transcribed)", file=sys.stderr)
        sys.exit(1)

    transcribe_entry(chapter_map, entry, args.force)


if __name__ == "__main__":
    main()
