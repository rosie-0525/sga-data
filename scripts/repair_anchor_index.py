#!/usr/bin/env python3
"""Rebuild each book's manifest `anchor_index` from the pages that actually hold
the anchors.

The manifests are produced by the per-book convert step, which lives outside
this repo, and its `anchor_index` drifts: editorial footnotes added after the
fact ship their `fn-…`/`fn-…ref` pair in the chapter JSON but never reach the
index, and a note that moves pages leaves its old entry behind. Either way the
viewer's cross-page `#anchor` jump has nothing (or the wrong thing) to go on —
most visibly on a footnote's ↩ backref, which is how a reader gets back to the
marker they were reading.

translation-viewer/viewer.js now resolves a fragment against the live DOM before
consulting the index, so a same-page jump survives a bad index. This pass fixes
the index itself, which is what a deep link (`paper.html#fn-x1ref`) and every
cross-page reference still depend on.

Usage:
  repair_anchor_index.py                  # every book, dry run
  repair_anchor_index.py --book sga6      # one book, dry run
  repair_anchor_index.py --write          # apply

Never deletes. An existing key whose id is nowhere in the html is left alone —
the convert step may index anchors the block html does not carry, and this pass
has no way to tell those from stale ones. An id found on two different pages is
reported and skipped rather than resolved by guessing.
"""
import argparse
import json
import re
from pathlib import Path

from glossary_lib import BOOKS, data_dir, load_chapter, load_json, load_manifest

ID_RE = re.compile(r'\bid\s*=\s*"([^"]+)"')

# The viewer builds these itself, per page, from `page.footnotes` — they are not
# ids in the data and would collide across every page in the book.
GENERATED_IDS = {"footnotes"}


def ids_in_page(page):
    """Every anchor id the rendered page will carry: the ids written into the
    block/footnote html, plus each footnote's own id (viewer.js footnotesEl()
    puts it on the <li> it generates)."""
    found = set()
    for block in page.get("blocks") or []:
        found.update(ID_RE.findall(block.get("html") or ""))
    for note in page.get("footnotes") or []:
        if note.get("id"):
            found.add(note["id"])
        found.update(ID_RE.findall(note.get("html") or ""))
    return found - GENERATED_IDS


def scan_book(book):
    """id -> page_id for the whole book, plus the ids that live on more than one
    page (which we refuse to index)."""
    where = {}
    conflicts = {}
    manifest = load_manifest(book)
    for chapter in manifest.get("chapters") or []:
        chapter_data = load_chapter(book, "fr", chapter["id"])
        if not chapter_data:
            continue
        for page in chapter_data.get("pages") or []:
            page_id = page.get("id")
            for anchor in ids_in_page(page):
                if anchor in where and where[anchor] != page_id:
                    conflicts.setdefault(anchor, {where[anchor]}).add(page_id)
                else:
                    where[anchor] = page_id
    for anchor in conflicts:
        where.pop(anchor, None)
    return manifest, where, conflicts


def plan(book):
    manifest, where, conflicts = scan_book(book)
    index = manifest.get("anchor_index") or {}
    adds = {a: p for a, p in where.items() if a not in index}
    fixes = {a: (index[a], p) for a, p in where.items()
             if a in index and index[a] != p}
    return manifest, index, adds, fixes, conflicts


def report(book, adds, fixes, conflicts):
    if not (adds or fixes or conflicts):
        print(f"{book}: anchor_index already agrees with the pages")
        return False
    print(f"{book}: +{len(adds)} missing, ~{len(fixes)} misplaced, "
          f"!{len(conflicts)} ambiguous")
    for anchor in sorted(adds):
        print(f"    + {anchor} -> {adds[anchor]}")
    for anchor in sorted(fixes):
        was, now = fixes[anchor]
        print(f"    ~ {anchor}: {was} -> {now}")
    for anchor in sorted(conflicts):
        pages = ", ".join(sorted(conflicts[anchor]))
        print(f"    ! {anchor} appears on {pages} — skipped, ids must be unique")
    return True


def write_manifest(book, manifest):
    """indent=1 and the file's own trailing-newline state, so an index repair is
    a diff of the lines it touched (see proposals_lib.write_chapter)."""
    path = data_dir(book, "fr") / "manifest.json"
    had_newline = path.read_text(encoding="utf-8").endswith("\n")
    text = json.dumps(manifest, ensure_ascii=False, indent=1)
    path.write_text(text + ("\n" if had_newline else ""), encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", choices=BOOKS, help="default: every book")
    ap.add_argument("--write", action="store_true",
                    help="apply the changes (default: report only)")
    args = ap.parse_args()

    books = [args.book] if args.book else BOOKS
    changed = 0
    ambiguous = 0
    for book in books:
        manifest, index, adds, fixes, conflicts = plan(book)
        report(book, adds, fixes, conflicts)
        ambiguous += len(conflicts)
        if not (adds or fixes):
            continue
        changed += 1
        if not args.write:
            continue
        index.update(adds)
        for anchor, (_, now) in fixes.items():
            index[anchor] = now
        manifest["anchor_index"] = index
        print(f"    wrote {write_manifest(book, manifest)}")

    if not args.write and changed:
        print(f"\n{changed} book(s) would change — re-run with --write to apply")
    return 1 if ambiguous else 0


if __name__ == "__main__":
    raise SystemExit(main())
