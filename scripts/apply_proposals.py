#!/usr/bin/env python3
"""Apply reviewed proposed changes to the corpus.

Reads the run a checking agent produced (<book>/data/proposals.json) and the
verdicts a reviewer exported from the viewer (decisions.json), and writes the
accepted text into the chapter JSON. Rejected proposals are counted and
dropped; nothing else in the data is touched.

Usage:
  apply_proposals.py --book sga3 --decisions ~/Downloads/decisions.json
  apply_proposals.py --book sga3 --decisions decisions.json --dry-run
  apply_proposals.py --book sga3 --validate       # check the run, no decisions

Every write must clear these guards; a proposal that trips one is reported and
skipped, never forced:

  run identity  the decisions' proposalsGeneratedAt must match the run's
  address       chapterId/pageId/blockIndex must resolve in the data
  conflict      the block's html must still equal the proposal's `before`
  multi-root    the new html must be exactly one root element — the viewer's
                blockEl() keeps the first and silently drops the rest
  structure     block and footnote counts are never changed, and fr/en block
                counts stay equal (the corpus is aligned 1:1 by block index)

Serialization is preserved exactly (indent=1, per-file trailing-newline state)
so an edited block shows up as a one-line diff; see proposals_lib.write_chapter.
"""
import argparse
import os
from collections import defaultdict
from pathlib import Path

from proposals_lib import (
    BOOKS, VERDICTS, data_dir, find_page, load_chapter, load_json,
    proposals_path, rebuild_page_html, root_count, validate, write_chapter,
)


def chapter_path(book, lang, chapter_id):
    return data_dir(book, lang) / "chapters" / f"{chapter_id}.json"


def load_decisions(path):
    doc = load_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("decisions"), list):
        raise SystemExit(f"{path}: expected an object with a 'decisions' array")
    return doc


def resolve_target(page, proposal):
    """(container_list, index) for the record a proposal edits, or (None, None)."""
    if proposal.get("target") == "footnote":
        return page.get("footnotes") or [], proposal.get("footnoteIndex")
    return page.get("blocks") or [], proposal.get("blockIndex")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True, choices=BOOKS)
    ap.add_argument("--decisions", help="decisions.json exported from the viewer")
    ap.add_argument("--proposals", help="override the run path "
                                        "(default <book>/data/proposals.json)")
    ap.add_argument("--dry-run", action="store_true",
                    help="run every guard, write nothing")
    ap.add_argument("--validate", action="store_true",
                    help="only check the run against the data, then exit")
    args = ap.parse_args()

    run_path = Path(args.proposals) if args.proposals else proposals_path(args.book)
    if not run_path.exists():
        raise SystemExit(f"no proposals run at {run_path}")
    run = load_json(run_path)
    if run.get("book") != args.book:
        raise SystemExit(f"{run_path} is for book {run.get('book')!r}, not {args.book!r}")
    proposals = {p["id"]: p for p in run.get("proposals") or [] if p.get("id")}

    if args.validate or not args.decisions:
        problems = validate(run)
        for msg in problems:
            print(f"  {msg}")
        print(f"{args.book}: {len(proposals)} proposals, {len(problems)} problem(s)")
        raise SystemExit(1 if problems else 0)

    doc = load_decisions(args.decisions)
    if doc.get("book") and doc["book"] != args.book:
        raise SystemExit(f"{args.decisions} is for book {doc['book']!r}, not {args.book!r}")
    # A verdict only means anything against the run it was made on: proposal ids
    # are reused across runs, so a mismatch would silently apply the wrong text.
    if doc.get("proposalsGeneratedAt") != run.get("generatedAt"):
        raise SystemExit(
            f"decisions were made against run {doc.get('proposalsGeneratedAt')!r} "
            f"but {run_path} is {run.get('generatedAt')!r} — re-review, or pass "
            "the matching proposals file with --proposals")

    counts = defaultdict(int)
    skipped = []
    # chapter file -> (loaded json, {page id of each edited page})
    touched = {}

    for dec in doc["decisions"]:
        pid = dec.get("id")
        verdict = dec.get("verdict")
        if verdict not in VERDICTS:
            skipped.append(f"{pid}: unknown verdict {verdict!r}")
            counts["refused"] += 1
            continue
        if verdict == "reject":
            counts["rejected"] += 1
            continue
        p = proposals.get(pid)
        if p is None:
            skipped.append(f"{pid}: not in this run")
            counts["refused"] += 1
            continue

        new_html = dec.get("html") if verdict == "edit" else p.get("after")
        if not isinstance(new_html, str):
            skipped.append(f"{pid}: edit verdict with no html")
            counts["refused"] += 1
            continue

        path = chapter_path(args.book, p["lang"], p["chapterId"])
        key = str(path)
        if key not in touched:
            chapter = load_chapter(args.book, p["lang"], p["chapterId"])
            if chapter is None:
                skipped.append(f"{pid}: no chapter file {path}")
                counts["refused"] += 1
                continue
            touched[key] = {"path": path, "chapter": chapter, "pages": set(),
                            "lang": p["lang"], "chapterId": p["chapterId"], "edits": 0}
        entry = touched[key]

        page = find_page(entry["chapter"], p["pageId"])
        if page is None:
            skipped.append(f"{pid}: no page {p['pageId']} in {path.name}")
            counts["refused"] += 1
            continue
        items, idx = resolve_target(page, p)
        if idx is None or idx < 0 or idx >= len(items):
            skipped.append(f"{pid}: {p.get('target', 'block')} index {idx} out of range "
                           f"on {p['pageId']}")
            counts["refused"] += 1
            continue
        rec = items[idx]

        if rec.get("html") != p.get("before"):
            skipped.append(f"{pid}: conflict — {p['pageId']}#{idx} no longer matches `before`")
            counts["conflicts"] += 1
            continue
        n = root_count(new_html)
        if n != 1:
            skipped.append(f"{pid}: refused — replacement has {n} root elements "
                           "(the viewer would keep only the first)")
            counts["refused"] += 1
            continue
        # A pre-existing fr/en id mismatch exists in the corpus (sga2 XIII-1
        # block 12), so a differing blockId is a warning, not a veto.
        if p.get("blockId") and rec.get("id") and p["blockId"] != rec.get("id"):
            skipped.append(f"{pid}: NOTE blockId {p['blockId']!r} != data id "
                           f"{rec.get('id')!r} (applied anyway, index is canonical)")

        rec["html"] = new_html
        entry["pages"].add(p["pageId"])
        entry["edits"] += 1
        counts["edited" if verdict == "edit" else "applied"] += 1

    # Structural check + write, one file at a time.
    written = []
    for entry in touched.values():
        if not entry["edits"]:
            continue
        chapter = entry["chapter"]
        for page in chapter.get("pages", []):
            if page.get("id") in entry["pages"]:
                rebuild_page_html(page)
        other = "en" if entry["lang"] == "fr" else "fr"
        mate = load_chapter(args.book, other, entry["chapterId"])
        if mate is not None:
            mate_pages = {pg.get("id"): pg for pg in mate.get("pages", [])}
            for page in chapter.get("pages", []):
                mp = mate_pages.get(page.get("id"))
                if mp is not None and len(page.get("blocks") or []) != len(mp.get("blocks") or []):
                    raise SystemExit(
                        f"ABORT: {entry['path'].name} page {page.get('id')} would have "
                        f"{len(page.get('blocks') or [])} blocks vs {len(mp.get('blocks') or [])} "
                        f"in {other} — the 1:1 alignment must hold")
        if not args.dry_run:
            write_chapter(entry["path"], chapter)
        written.append((entry["path"], entry["edits"]))

    for msg in skipped:
        print(f"  {msg}")
    for path, n in sorted(written):
        print(f"  {'would write' if args.dry_run else 'wrote'} "
              f"{os.path.relpath(path)} ({n} block(s))")
    print(f"{args.book}: applied {counts['applied']} · edited {counts['edited']} · "
          f"rejected {counts['rejected']} · conflicts {counts['conflicts']} · "
          f"refused {counts['refused']}"
          + ("  [dry run — nothing written]" if args.dry_run else ""))


if __name__ == "__main__":
    main()
