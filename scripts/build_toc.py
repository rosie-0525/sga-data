#!/usr/bin/env python3
"""Record the books' full sectioning depth in each manifest's `toc`.

The convert step (outside this repo) writes a two-level `toc`: one row per
page, level 0 for a chapter landing page, level 1 for a section page. The
books themselves go two levels deeper — subsections and subsubsections exist
only as `type: "heading"` blocks in the chapter JSON, their depth encoded in
the `<h3>`/`<h4>` tag. This pass mines those blocks and inserts one row per
deep heading right after its page's row:

    {"page_id": "IV-3", "anchor": "IV.3.1", "label": "3.1",
     "title": "Relations d'équivalence : définitions", "level": 2}

Rows carrying an `anchor` key are owned by this script: a re-run strips and
rebuilds them (idempotent). Convert-owned page rows keep their identity, but
their titles get the same markup sanitizing as anchor rows (a page title can
cite a statement via a ref link — e.g. "Fin de la preuve de <a …>4.10</a>").
Re-run with --write after any upstream manifest regeneration — that wipes the
anchor rows.

Titles are sanitized for the sidebar: footnote markers are dropped, links are
unwrapped (a nested <a> would split the sidebar link and a duplicated
id="…ref" would shadow content ids in the viewer's DOM-first hash
resolution). A heading that is just a number ("3.4.1.") gets `title: null`;
the viewer renders titled rows only.

Usage:
  build_toc.py                  # every book, dry run
  build_toc.py --book sga3      # one book, dry run
  build_toc.py --write          # apply
"""
import argparse
import json
import re

from glossary_lib import BOOKS, data_dir, load_chapter, load_manifest

H_RE = re.compile(r"<h([1-6])\b[^>]*>(.*)</h\1>", re.S)
# Leading section number: "1.6. Changement…" / "3.4.1." — the trailing dot is
# consumed but kept out of the label.
NUM_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)*)\.?(?=\s| |&nbsp;|<|$)")
SUP_A_RE = re.compile(r"<sup\b[^>]*>\s*<a\b[^>]*>.*?</a>\s*</sup>", re.S)
A_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.S)
# Empty spans are pure anchor targets (<span class="label-anchor" id="…">) —
# dropping only the id would leave contentless cruft in the sidebar.
EMPTY_SPAN_RE = re.compile(r"<span\b[^>]*>\s*</span>")
ID_ATTR_RE = re.compile(r'\s*\bid\s*=\s*"[^"]*"')
SEP_RE = re.compile(r"^[\s ]*(?:[—–-][\s ]*)?")


def strip_markup(html, warn, where):
    """Footnote sups, <a> wrappers, empty spans and id attrs removed —
    the shared sanitizing between anchor-row and page-row titles."""
    html = SUP_A_RE.sub("", html)
    while A_RE.search(html):
        html = A_RE.sub(r"\1", html)
    while EMPTY_SPAN_RE.search(html):
        html = EMPTY_SPAN_RE.sub("", html)
    if ID_ATTR_RE.search(html):
        warn(f"{where}: id= attribute survived sanitizing — stripped")
        html = ID_ATTR_RE.sub("", html)
    return html.strip()


def split_label_title(inner, block_label, warn, where):
    """Sanitized (label, title) for a heading's inner html."""
    inner = re.sub(r"\s+", " ", inner).strip()
    inner = strip_markup(inner, warn, where)

    if block_label and inner.startswith(block_label):
        label = block_label
        rest = inner[len(block_label):]
        rest = rest[1:] if rest.startswith(".") else rest
    else:
        if block_label:
            warn(f"{where}: label {block_label!r} is not a prefix of the "
                 f"heading text — deriving from the text instead")
        m = NUM_RE.match(inner)
        if m:
            label, rest = m.group(1), inner[m.end():]
        else:
            label, rest = None, inner

    title = SEP_RE.sub("", rest, count=1).strip() or None
    if label is None and title is None:
        warn(f"{where}: heading has neither number nor title")
    return label, title


def collect(book):
    """anchors_for_page: page_id -> [new toc rows, document order]."""
    manifest = load_manifest(book)
    anchor_index = manifest.get("anchor_index") or {}
    anchors_for_page = {}
    warnings = []
    warn = warnings.append
    for chapter in manifest.get("chapters") or []:
        data = load_chapter(book, "fr", chapter["id"])
        if not data:
            warn(f"{chapter['id']}: chapter file missing")
            continue
        for page in data.get("pages") or []:
            page_id = page.get("id")
            for i, block in enumerate(page.get("blocks") or []):
                if block.get("type") != "heading":
                    continue
                m = H_RE.search(block.get("html") or "")
                if not m:
                    warn(f"{page_id}[{i}]: heading block without <hN> tag")
                    continue
                depth = int(m.group(1))
                if i == 0 and depth <= 2:
                    continue  # the page's own heading — already a toc page row
                if depth <= 2:
                    level = 1
                    warn(f"{page_id}[{i}]: mid-page h{depth} recorded as level 1")
                elif depth <= 4:
                    level = depth - 1
                else:
                    warn(f"{page_id}[{i}]: h{depth} skipped")
                    continue
                hid = block.get("id")
                if not hid:
                    warn(f"{page_id}[{i}]: h{depth} has no id — skipped")
                    continue
                if anchor_index.get(hid) != page_id:
                    warn(f"{hid}: anchor_index says "
                         f"{anchor_index.get(hid)!r}, lives on {page_id} "
                         f"— run repair_anchor_index.py")
                label, title = split_label_title(
                    m.group(2), block.get("label"), warn, hid)
                anchors_for_page.setdefault(page_id, []).append({
                    "page_id": page_id, "anchor": hid,
                    "label": label, "title": title, "level": level,
                })
    return manifest, anchors_for_page, warnings


def rebuild_toc(manifest, anchors_for_page, warn):
    """Page rows kept in place (titles sanitized), anchor rows re-inserted
    after each."""
    pending = dict(anchors_for_page)
    new_toc = []
    for row in manifest.get("toc") or []:
        if "anchor" in row:
            continue
        title = row.get("title")
        if title:
            clean = strip_markup(title, warn, row["page_id"])
            if clean != title:
                row = {**row, "title": clean}
        new_toc.append(row)
        new_toc.extend(pending.pop(row["page_id"], []))
    for page_id, rows in pending.items():
        warn(f"{page_id}: has headings but no toc row — {len(rows)} entries dropped")
    return new_toc


def write_manifest(book, manifest):
    """indent=1 and the file's own trailing-newline state, so the rewrite is
    a diff of the inserted rows only (see repair_anchor_index.write_manifest)."""
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
    total_warnings = 0
    changed = 0
    for book in books:
        manifest, anchors_for_page, warnings = collect(book)
        new_toc = rebuild_toc(manifest, anchors_for_page, warnings.append)
        added = [r for r in new_toc if "anchor" in r]
        by_level = {}
        for r in added:
            by_level[r["level"]] = by_level.get(r["level"], 0) + 1
        levels = ", ".join(f"level{lv}: {n}" for lv, n in sorted(by_level.items()))
        if new_toc == manifest.get("toc"):
            print(f"{book}: toc already up to date ({len(added)} anchor rows)")
        else:
            changed += 1
            print(f"{book}: +{len(added)} anchor entries ({levels}), "
                  f"{len(warnings)} warning(s)")
            if args.write:
                manifest["toc"] = new_toc
                print(f"    wrote {write_manifest(book, manifest)}")
        for w in warnings:
            print(f"    ! {w}")
        total_warnings += len(warnings)

    if not args.write and changed:
        print(f"\n{changed} book(s) would change — re-run with --write to apply")
    return 1 if total_warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
