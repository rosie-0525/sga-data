#!/usr/bin/env python3
"""One-off in-place patch of sga{3..7}/02-converted_html/data/fr/:

Split the leading "EXPOSÉ <numeral>" off every chapter title into a new
`alias` field, and lift the h1's <span class="author"> text into a new
`author` field — mirroring the same change made in each book's
scripts/build_viewer_data.py (chapter_title) so a future rebuild agrees
with the patched data. Touches manifest chapter entries, the matching toc
landing entries, and each chapter file's header + landing-page title.
Blocks/html and everything under data/en/ are left byte-identical.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ["sga3", "sga4", "sga5", "sga6", "sga7"]
# sga1/sga2 (LaTeX-converted, no build script) have clean titles and no author
# data; they only need `alias` on numbered chapters so the sidebar reads
# "EXPOSÉ I <title>" like the other books. Front matter has number null.
ALIAS_ONLY_BOOKS = ["sga1", "sga2"]

PREFIX = re.compile(r"^EXPOSÉ\s+([0-9]+|[IVXLC]+(?:\s*(?:bis|A|B))?)\b[\s.:—–-]*")
AUTHOR = re.compile(r'<span class="author">(.*?)</span>', re.S)
TAGS = re.compile(r"<[^>]+>")


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1)


def split_title(title):
    m = PREFIX.match(title or "")
    if not m:
        return title, None, None
    return title[m.end():].strip(), "EXPOSÉ", m.group(1)


def author_from_blocks(chapter):
    for page in chapter.get("pages", [])[:1]:
        for b in page.get("blocks", []):
            if b.get("html", "").startswith("<h1"):
                m = AUTHOR.search(b["html"])
                if m:
                    text = TAGS.sub(" ", m.group(1))
                    return re.sub(r"\s+", " ", text).strip() or None
                return None
    return None


def main():
    total_alias = total_author = 0
    for book in BOOKS:
        fr = ROOT / book / "02-converted_html" / "data" / "fr"
        manifest_path = fr / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # round-trip guard: our dump settings must reproduce the file as-is
        if dump(manifest) != manifest_path.read_text(encoding="utf-8"):
            sys.exit(f"{manifest_path}: round-trip mismatch, aborting")

        toc_by_page = {t["page_id"]: t for t in manifest.get("toc", [])}
        n_alias = n_author = 0
        for entry in manifest["chapters"]:
            title, alias, numeral = split_title(entry["title"])
            ch_path = fr / "chapters" / f"{entry['id']}.json"
            chapter = json.loads(ch_path.read_text(encoding="utf-8"))
            author = author_from_blocks(chapter)

            if not alias and not author:
                continue
            if numeral and numeral.replace(" ", "") != entry["number"]:
                print(f"  WARN {book}/{entry['id']}: h1 numeral {numeral!r} "
                      f"!= number {entry['number']!r}")

            if alias:
                n_alias += 1
                entry["title"] = title
                entry["alias"] = alias
                landing = entry["page_ids"][0]
                toc = toc_by_page.get(landing)
                if toc and PREFIX.match(toc["title"] or ""):
                    toc["title"] = split_title(toc["title"])[0]
                chapter["title"] = split_title(chapter["title"])[0]
                chapter["alias"] = alias
                page0 = chapter["pages"][0]
                if PREFIX.match(page0.get("title") or ""):
                    page0["title"] = split_title(page0["title"])[0]
            if author:
                n_author += 1
                entry["author"] = author
                chapter["author"] = author
            ch_path.write_text(dump(chapter), encoding="utf-8")

        manifest_path.write_text(dump(manifest), encoding="utf-8")
        print(f"{book}: {len(manifest['chapters'])} chapters, "
              f"alias added to {n_alias}, author added to {n_author}")
        total_alias += n_alias
        total_author += n_author

    for book in ALIAS_ONLY_BOOKS:
        fr = ROOT / book / "02-converted_html" / "data" / "fr"
        manifest_path = fr / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if dump(manifest) != manifest_path.read_text(encoding="utf-8"):
            sys.exit(f"{manifest_path}: round-trip mismatch, aborting")
        n_alias = 0
        for entry in manifest["chapters"]:
            if not entry.get("number") or entry.get("alias"):
                continue
            n_alias += 1
            entry["alias"] = "EXPOSÉ"
            ch_path = fr / "chapters" / f"{entry['id']}.json"
            chapter = json.loads(ch_path.read_text(encoding="utf-8"))
            chapter["alias"] = "EXPOSÉ"
            ch_path.write_text(dump(chapter), encoding="utf-8")
        manifest_path.write_text(dump(manifest), encoding="utf-8")
        print(f"{book}: {len(manifest['chapters'])} chapters, "
              f"alias added to {n_alias}")
        total_alias += n_alias
    print(f"total: alias {total_alias}, author {total_author}")


if __name__ == "__main__":
    main()
