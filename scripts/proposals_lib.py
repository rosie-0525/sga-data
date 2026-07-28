#!/usr/bin/env python3
"""Shared helpers for the proposed-changes review loop.

A checking agent audits the corpus and writes `<book>/data/proposals.json`; the
viewer (translation-viewer/proposals.js) renders each proposal as a diff and a
human accepts, edits or rejects it; apply_proposals.py writes the verdicts back
into the chapter JSON. This module is the Python half of that contract — the
agent builds proposals through `new_proposal()` so it cannot mis-address a
block, and both `proposals_check.py`-style validation and the applier share the
guards defined here.

The normative spec for both files is
translation-viewer/docs/proposals.schema.md.

Addressing follows the same scheme comments.js uses:
    data/<lang>/chapters/<chapterId>.json -> pages[].id == pageId ->
    blocks[blockIndex]  (or footnotes[footnoteIndex])
`blockIndex` is the canonical key: `blockId` is null on ~54% of blocks and is
not unique across a book, so it travels as a label and is only warned about.
"""
import json
from html.parser import HTMLParser
from pathlib import Path

from glossary_lib import (  # noqa: F401  (re-exported for the checking agent)
    BOOKS,
    ROOT,
    chapter_ids,
    cite,
    data_dir,
    load_chapter,
    load_json,
    load_manifest,
    iter_aligned_blocks,
    iter_aligned_footnotes,
)

SCHEMA_VERSION = 1
CATEGORIES = ("transcription", "translation", "markup")
VERDICTS = ("accept", "edit", "reject")


def proposals_path(book):
    return ROOT / book / "data" / "proposals.json"


# ---------------------------------------------------------------------------
# Structural guards
#
# The viewer's blockEl() keeps only the FIRST top-level element of a block's
# html and silently drops the rest, so a multi-root replacement loses content.
# This is the same defect the sga-check-errors skill reports as a block-shape
# issue; refusing it here keeps it from ever reaching the data.

class _RootCounter(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.roots = 0
        self.stray_text = False

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            if self.depth == 0:
                self.roots += 1
            return
        if self.depth == 0:
            self.roots += 1
        self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.depth == 0:
            self.roots += 1

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.depth > 0:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth == 0 and data.strip():
            self.stray_text = True


def root_count(html):
    """Number of top-level nodes in a block's html. Anything but 1 is content
    loss in the viewer. Stray top-level text counts as an extra root."""
    p = _RootCounter()
    p.feed(html or "")
    p.close()
    return p.roots + (1 if p.stray_text else 0)


# ---------------------------------------------------------------------------
# Locating a target

def find_page(chapter, page_id):
    for page in (chapter or {}).get("pages", []):
        if page.get("id") == page_id:
            return page
    return None


def find_record(book, lang, chapter_id, page_id, target="block",
                block_index=None, footnote_index=None):
    """The dict a proposal targets — a block or a footnote — or None."""
    chapter = load_chapter(book, lang, chapter_id)
    page = find_page(chapter, page_id)
    if page is None:
        return None
    if target == "footnote":
        items = page.get("footnotes") or []
        idx = footnote_index
    else:
        items = page.get("blocks") or []
        idx = block_index
    if idx is None or idx < 0 or idx >= len(items):
        return None
    return items[idx]


def chapter_path(book, lang, chapter_id):
    return data_dir(book, lang) / "chapters" / f"{chapter_id}.json"


def resolve_target(page, proposal):
    """(container_list, index) for the record a proposal edits, or ([], None)."""
    if proposal.get("target") == "footnote":
        return page.get("footnotes") or [], proposal.get("footnoteIndex")
    return page.get("blocks") or [], proposal.get("blockIndex")


# ---------------------------------------------------------------------------
# The guards
#
# One implementation, shared by the batch applier (apply_proposals.py) and the
# review server (review_server.py). Every guard returns a message instead of
# raising, so a caller serving HTTP can turn it into a 409 and a caller running
# in a terminal can print it — but neither can skip it.

def check_target(chapter, proposal):
    """Locate the record a proposal edits inside an already-loaded chapter.

    Returns (record, error). The address must resolve and the record's html must
    still equal the proposal's `before` — that equality is the whole conflict
    story, since `before` is the block's html verbatim at proposal time.
    """
    page = find_page(chapter, proposal.get("pageId"))
    if page is None:
        return None, f"no page {proposal.get('pageId')} in {proposal.get('chapterId')}"
    items, idx = resolve_target(page, proposal)
    if idx is None or idx < 0 or idx >= len(items):
        return None, (f"{proposal.get('target', 'block')} index {idx} out of range "
                      f"on {proposal.get('pageId')}")
    rec = items[idx]
    if rec.get("html") != proposal.get("before"):
        return None, (f"conflict — {proposal.get('pageId')}#{idx} no longer matches "
                      "`before`")
    return rec, None


def check_replacement(html):
    """The viewer's blockEl() keeps only the first top-level element, so anything
    but a single root silently loses content. Returns an error message or None."""
    if not isinstance(html, str):
        return "replacement is not a string"
    n = root_count(html)
    if n != 1:
        return (f"refused — replacement has {n} root elements "
                "(the viewer would keep only the first)")
    return None


def check_alignment(book, lang, chapter_id, chapter):
    """The corpus is aligned 1:1 by block index, so an edit must never change a
    page's block count relative to its mate language. Returns a message or None."""
    other = "en" if lang == "fr" else "fr"
    mate = load_chapter(book, other, chapter_id)
    if mate is None:
        return None
    mate_pages = {pg.get("id"): pg for pg in mate.get("pages", [])}
    for page in chapter.get("pages", []):
        mp = mate_pages.get(page.get("id"))
        if mp is None:
            continue
        mine, theirs = len(page.get("blocks") or []), len(mp.get("blocks") or [])
        if mine != theirs:
            return (f"ABORT: {chapter_id} page {page.get('id')} would have {mine} "
                    f"blocks vs {theirs} in {other} — the 1:1 alignment must hold")
    return None


def apply_decision(book, proposal, new_html):
    """Write one accepted/edited proposal into the chapter JSON.

    Loads the chapter fresh from disk, runs every guard, and writes only if all
    of them pass. Returns (ok, error, path). The caller is responsible for any
    locking — see review_server.py, which serializes concurrent admins.
    """
    lang, chapter_id = proposal.get("lang"), proposal.get("chapterId")
    path = chapter_path(book, lang, chapter_id)
    chapter = load_chapter(book, lang, chapter_id)
    if chapter is None:
        return False, f"no chapter file {path}", path

    err = check_replacement(new_html)
    if err:
        return False, err, path
    rec, err = check_target(chapter, proposal)
    if err:
        return False, err, path

    rec["html"] = new_html
    page = find_page(chapter, proposal.get("pageId"))
    rebuild_page_html(page)
    err = check_alignment(book, lang, chapter_id, chapter)
    if err:
        return False, err, path

    write_chapter(path, chapter)
    return True, None, path


# ---------------------------------------------------------------------------
# Building a run

def new_proposal(book, lang, chapter_id, page_id, after, rationale,
                 block_index=None, footnote_index=None, target="block",
                 category="translation", evidence=None, proposal_id=None):
    """Build one proposal, reading `before` off disk so it is always verbatim.

    Raises ValueError when the address does not resolve, when `after` would not
    be a single root element, or when the change is a no-op.
    """
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {CATEGORIES}, got {category!r}")
    rec = find_record(book, lang, chapter_id, page_id, target,
                      block_index, footnote_index)
    if rec is None:
        raise ValueError(
            f"no {target} at {book}/{lang}/{chapter_id}/{page_id}"
            f"#{footnote_index if target == 'footnote' else block_index}")
    before = rec.get("html", "")
    if after == before:
        raise ValueError(f"proposal is a no-op at {page_id}#{block_index}")
    n = root_count(after)
    if n != 1:
        raise ValueError(
            f"`after` has {n} root elements at {page_id}#{block_index}; the "
            "viewer keeps only the first")
    idx = footnote_index if target == "footnote" else block_index
    out = {
        "id": proposal_id or f"p-{book}-{lang}-{page_id}-{target[:2]}{idx}",
        "chapterId": chapter_id,
        "pageId": page_id,
        "lang": lang,
        "target": target,
        "category": category,
        "before": before,
        "after": after,
        "rationale": rationale,
    }
    if target == "footnote":
        out["footnoteIndex"] = footnote_index
    else:
        out["blockIndex"] = block_index
        out["blockId"] = rec.get("id")
    if evidence:
        out["evidence"] = evidence
    return out


def validate(run):
    """Check a whole proposals run against the data. Returns a list of problem
    strings — empty means every proposal is applicable right now."""
    problems = []
    book = run.get("book")
    if book not in BOOKS:
        return [f"unknown book {book!r}"]
    seen = set()
    for i, p in enumerate(run.get("proposals") or []):
        where = f"proposals[{i}] ({p.get('id')})"
        pid = p.get("id")
        if not pid:
            problems.append(f"{where}: missing id")
        elif pid in seen:
            problems.append(f"{where}: duplicate id")
        else:
            seen.add(pid)
        if p.get("category") not in CATEGORIES:
            problems.append(f"{where}: category {p.get('category')!r} not in {CATEGORIES}")
        if p.get("lang") not in ("fr", "en"):
            problems.append(f"{where}: lang {p.get('lang')!r} not in ('fr', 'en')")
        for key in ("chapterId", "pageId", "before", "after"):
            if not isinstance(p.get(key), str):
                problems.append(f"{where}: missing/invalid {key}")
        if problems and problems[-1].startswith(where + ": missing/invalid"):
            continue
        rec = find_record(book, p.get("lang"), p.get("chapterId"), p.get("pageId"),
                          p.get("target", "block"), p.get("blockIndex"),
                          p.get("footnoteIndex"))
        if rec is None:
            problems.append(f"{where}: address does not resolve")
            continue
        if rec.get("html") != p.get("before"):
            problems.append(f"{where}: stale — `before` no longer matches the data")
        n = root_count(p.get("after"))
        if n != 1:
            problems.append(f"{where}: `after` has {n} root elements")
        if p.get("blockId") and rec.get("id") and p["blockId"] != rec.get("id"):
            problems.append(f"{where}: blockId {p['blockId']!r} != data id {rec.get('id')!r}")
    return problems


def write_proposals(book, proposals, generator=None, generated_at=None,
                    base_commit=None):
    """Write <book>/data/proposals.json. Committing that file publishes the
    review UI for the book; deleting it takes it down."""
    run = {
        "schemaVersion": SCHEMA_VERSION,
        "book": book,
        "generatedAt": generated_at,
        "generator": generator,
        "baseCommit": base_commit,
        "proposals": list(proposals),
    }
    path = proposals_path(book)
    path.write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Writing chapter files
#
# The corpus is serialized as json.dumps(indent=1) — NOT indent=2 — and its
# trailing-newline state varies per file (sga1/sga2 mostly lack one, sga3-7 are
# mixed). Rewriting a file without preserving both turns a one-line edit into a
# whole-file diff, so every writer goes through here.

def write_chapter(path, obj):
    path = Path(path)
    had_newline = path.read_text(encoding="utf-8").endswith("\n")
    text = json.dumps(obj, ensure_ascii=False, indent=1)
    path.write_text(text + ("\n" if had_newline else ""), encoding="utf-8")


def rebuild_page_html(page):
    """sga1/sga2/sga4.5 pages carry an `html` field that is the concatenation of
    their blocks' html. Rebuild it after editing a block; pages without the
    field (sga3-sga7) are left alone."""
    if "html" not in page:
        return False
    page["html"] = "\n".join(b.get("html", "") for b in page.get("blocks", []))
    return True
