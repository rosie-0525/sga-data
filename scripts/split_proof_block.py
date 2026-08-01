#!/usr/bin/env python3
"""Split one oversized `proof` block into several consecutive blocks.

A proof is stored as one block per `\\begin{proof}`, and a few of them swallowed
whole runs of numbered items: sga4.5 `proof-VI:7-3` holds lemma 7.9 and
subsections 7.10-7.14 in 12 KB of html. One block is one aligned row, so such a
proof lines up with its translation only at its top, and — the reason this
exists — the review UI cannot word-diff it. `translation-viewer/proposals.js`
trims the common head and tail of a proposal, then falls back to a whole-block
before|after view when what is left still exceeds MAX_DIFF_TOKENS (1200). Every
proposal on these blocks is therefore unreviewable.

This pass cuts the proof body between its top-level children and wraps each
piece as its own block, tied back together by `data-proof-group` so the viewer
still renders one proof: one head, one QED, one unbroken rule, one collapse
toggle (see translation-viewer/docs/chapter.schema.md).

Usage:
  split_proof_block.py --book sga4.5 --chapter VI --page VI:7 --block 36
  split_proof_block.py --book sga4.5 --chapter VI --page VI:7 --block 36 --write
      [--cap 1200] [--resplit-proposals] [--shift-refs] [--number-anchors]

Cuts land before a heading, a nested theorem-like environment or a nested proof;
if a piece is still over the cap, the displayed formula nearest its midpoint is
added as a further cut. Never mid-prose. Both languages are cut at the same
anchors — the 1:1 block alignment is what the whole corpus is addressed by — and
every guard is a refusal, not a warning: the slices must reconcatenate byte for
byte, each new block must be a single root, and no anchor id may be lost.

A proposal may not itself split a block (docs/proposals.schema.md), so a live
proposal on the target would be stranded — its 12 KB `before` can never match
again and the applier refuses it. `--resplit-proposals` cuts such a proposal's
`before`/`after` at the same anchors and re-emits one card per changed piece;
`--shift-refs` renumbers proposals sitting after the split on the same page.
"""
import argparse
import json
import re
import sys
from html.parser import HTMLParser

from glossary_lib import BOOKS, load_chapter, load_json
from proposals_lib import (
    chapter_path,
    check_alignment,
    find_page,
    proposals_path,
    root_count,
    write_chapter,
    write_proposals,
)
from repair_anchor_index import ID_RE

LANGS = ("fr", "en")

# The proof's own shape, as the convert step emits it. Anything else is refused
# rather than guessed at: this pass rewrites the wrapper, so it has to know it.
SHELL_RE = re.compile(
    r'\A(?P<open><div class="proof"(?P<attrs>[^>]*)>)\n'
    r'(?P<pad>[ ]*)(?P<head><div class="proof-head">.*?</div>)\n'
    r'[ ]*<div class="proof-body">(?P<inner>.*)</div>\n</div>\Z',
    re.S)


# ---------------------------------------------------------------------------
# The diff cap
#
# A faithful port of translation-viewer/proposals.js tokenize(): tags, math
# (indivisible), whitespace runs, punctuation, words. The cap is what decides
# whether a piece is reviewable, so it has to agree with the viewer exactly.

WS_RE = re.compile(r"\s")
PUNCT_RE = re.compile(r"[.,;:!?«»“”‘’\"'()\[\]{}…—–\-/+=*&|@#$%^~`]")


def tokenize(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "<":
            gt = s.find(">", i)
            gt = n - 1 if gt == -1 else gt
            out.append(s[i:gt + 1])
            i = gt + 1
        elif c == "\\" and i + 1 < n and s[i + 1] in "([":
            close = "\\)" if s[i + 1] == "(" else "\\]"
            end = s.find(close, i + 2)
            if end == -1:
                out.append(s[i:i + 2])
                i += 2
            else:
                out.append(s[i:end + 2])
                i = end + 2
        elif WS_RE.match(c):
            j = i
            while j < n and WS_RE.match(s[j]):
                j += 1
            out.append(s[i:j])
            i = j
        elif PUNCT_RE.match(c):
            out.append(c)
            i += 1
        else:
            j = i
            while j < n:
                d = s[j]
                if d == "<" or WS_RE.match(d) or PUNCT_RE.match(d):
                    break
                if j > i and d == "\\" and j + 1 < n and s[j + 1] in "([":
                    break
                j += 1
            if j == i:
                j = i + 1
            out.append(s[i:j])
            i = j
    return out


# ---------------------------------------------------------------------------
# Where a proof may be cut

class _TopLevel(HTMLParser):
    """The top-level children of a fragment, with their byte offsets."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.kids = []
        starts = [0]
        for line in text.split("\n")[:-1]:
            starts.append(starts[-1] + len(line) + 1)
        self._starts = starts
        self.feed(text)
        self.close()

    def _offset(self):
        line, col = self.getpos()
        return self._starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        if self.depth == 0:
            a = dict(attrs)
            self.kids.append((self._offset(), tag, a.get("class", ""), a.get("id", "")))
        self.depth += 1

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.depth > 0:
            self.depth -= 1


def _is_structural(tag, cls):
    """A real boundary in the argument: a numbered item, a nested statement, a
    nested proof."""
    if re.fullmatch(r"h[1-6]", tag):
        return True
    if tag != "div":
        return False
    classes = cls.split()
    return any(c.startswith("thm") for c in classes) or classes[:1] == ["proof"]


def _is_relief(tag, cls):
    """A displayed formula — already a visual break, so usable as a fallback cut
    when a piece is still too long to diff."""
    classes = cls.split()
    return tag == "div" and ("equation" in classes or "displaymath" in classes)


def cut_offsets(inner, cap):
    """Offsets into `inner` where a new block starts. Structural cuts first,
    then the nearest-to-midpoint displayed formula for any piece still over the
    cap, repeated until every piece fits or nothing is left to cut."""
    kids = _TopLevel(inner).kids
    cuts = sorted({o for o, tag, cls, _ in kids if _is_structural(tag, cls) and o > 0})
    while True:
        bounds = [0] + cuts + [len(inner)]
        for a, b in zip(bounds, bounds[1:]):
            if len(tokenize(inner[a:b])) <= cap:
                continue
            cands = [o for o, tag, cls, _ in kids if _is_relief(tag, cls) and a < o < b]
            if not cands:
                continue
            mid = (a + b) // 2
            cuts = sorted(cuts + [min(cands, key=lambda o: abs(o - mid))])
            break
        else:
            return cuts, kids


def open_tag_at(inner, offset):
    """The cut element's opening tag, e.g. '<h4 id="VI:7-10">'. Used to locate
    the same cut inside a proposal's before/after, where offsets have shifted."""
    return inner[offset:inner.index(">", offset) + 1]


# ---------------------------------------------------------------------------
# Building the pieces

def number_map(inner, cuts, kids):
    """Empty heading anchors used as cut points render as nothing, so each piece
    would open unlabelled. Derive the item number from the id — 'VI:7-10' is
    7.10 — and fill them in. Only empty headings; never touches text."""
    out = {}
    for offset, tag, _cls, anchor in kids:
        if offset not in cuts or not re.fullmatch(r"h[1-6]", tag) or not anchor:
            continue
        tail = anchor.split(":")[-1]
        if not re.fullmatch(r"[\d.-]+", tail):
            continue
        empty = f'<{tag} id="{anchor}"></{tag}>'
        if empty in inner:
            out[empty] = f'<{tag} id="{anchor}">{tail.replace("-", ".")}</{tag}>'
    return out


def apply_numbering(text, mapping):
    for old, new in mapping.items():
        text = text.replace(old, new)
    return text


def wrap(slices, group, open_attrs, head, pad):
    """One block per slice: the first keeps the proof's attributes and its head,
    the rest are head-less continuations tied back by data-proof-group."""
    out = []
    last = len(slices) - 1
    for i, sl in enumerate(slices):
        classes = "proof proof-part " + ("proof-first" if i == 0 else "proof-cont")
        if i == last and last > 0:
            classes += " proof-last"
        if i == 0:
            open_tag = f'<div class="{classes}"{open_attrs} data-proof-group="{group}">'
            body = f"{open_tag}\n{pad}{head}\n{pad}<div class=\"proof-body\">"
        else:
            open_tag = f'<div class="{classes}" data-proof-group="{group}">'
            body = f"{open_tag}\n{pad}<div class=\"proof-body\">"
        out.append(body + sl + "</div>\n</div>")
    return out


def block_records(slices, blocks_html, first, kids, cuts):
    """The JSON records. The first piece keeps the proof's id/title; each
    continuation takes the id of the element it opens with — already in
    anchor_index, so no manifest change — and no title, since it has no head."""
    ids = {o: anchor for o, _t, _c, anchor in kids}
    recs = [dict(first, html=blocks_html[0])]
    for offset, html in zip(cuts, blocks_html[1:]):
        recs.append({
            "id": ids.get(offset) or None,
            "type": first.get("type"),
            "label": None,
            "title": None,
            "html": html,
        })
    return recs


def split_block(block, cap, number):
    """(records, cuts, kids, numbering) for one language, or raises ValueError."""
    m = SHELL_RE.match(block.get("html") or "")
    if not m:
        raise ValueError("block html is not a <div class=\"proof\"> shell")
    attrs, head, pad, inner = m["attrs"], m["head"], m["pad"], m["inner"]
    ids = ID_RE.findall(m["open"])
    if not ids:
        raise ValueError("the proof div has no id to group its pieces by")
    group = ids[0]

    kids = _TopLevel(inner).kids
    cuts, kids = cut_offsets(inner, cap)
    if not cuts:
        raise ValueError("no cut point in the proof body — nothing to split")
    numbering = number_map(inner, cuts, kids) if number else {}
    if numbering:
        inner = apply_numbering(inner, numbering)
        cuts, kids = cut_offsets(inner, cap)

    slices = [inner[a:b] for a, b in zip([0] + cuts, cuts + [len(inner)])]
    if "".join(slices) != inner:
        raise ValueError("slices do not reconcatenate — refusing to write")
    html = wrap(slices, group, attrs, head, pad)
    return block_records(slices, html, block, kids, cuts), cuts, kids, numbering, inner


# ---------------------------------------------------------------------------
# Proposals

def slice_at_anchors(text, anchors):
    """Cut a proposal's html at the same anchors. Returns None if any anchor is
    missing or ambiguous — meaning the edit touched a cut point, and re-splitting
    would not be sound."""
    m = SHELL_RE.match(text or "")
    if not m:
        return None
    inner = m["inner"]
    pos, at = [], 0
    for a in anchors:
        if inner.count(a) != 1:
            return None
        j = inner.index(a, at)
        if j < at:
            return None
        pos.append(j)
        at = j + len(a)
    parts = [inner[x:y] for x, y in zip([0] + pos, pos + [len(inner)])]
    return parts if "".join(parts) == inner else None


def resplit_proposal(prop, anchors, new_blocks, target, numbering):
    """One card per piece the proposal actually changes. Each card's `before` is
    the new block's html verbatim — that string equality is what check_target
    tests — and `after` is the same wrapper around the edited slice."""
    before = apply_numbering(prop.get("before") or "", numbering)
    after = apply_numbering(prop.get("after") or "", numbering)
    bs, as_ = slice_at_anchors(before, anchors), slice_at_anchors(after, anchors)
    if bs is None or as_ is None or len(bs) != len(as_) or len(bs) != len(new_blocks):
        return None
    out = []
    for i, (b, a) in enumerate(zip(bs, as_)):
        if b == a:
            continue
        block = new_blocks[i]
        if block["html"].count(b) != 1:
            return None
        card = dict(prop)
        card["blockIndex"] = target + i
        card["blockId"] = block.get("id")
        card["before"] = block["html"]
        card["after"] = block["html"].replace(b, a)
        card["id"] = address_id(card["bookHint"], prop["lang"], prop["pageId"],
                                target + i)
        del card["bookHint"]
        out.append(card)
    return out


def address_id(book, lang, page_id, block_index):
    """The canonical proposal id. It encodes the address, so a proposal whose
    block index moves has to be re-issued under the new one — otherwise the run
    grows two proposals claiming the same id (the pieces of a split land on the
    indices the shifted proposals used to hold)."""
    return f"p-{book}-{lang}-{page_id}-bl{block_index}"


# ---------------------------------------------------------------------------

def report_lang(lang, block, recs, cuts, kids, numbering, inner, cap):
    ids = {o: a for o, _t, _c, a in kids}
    print(f"  {lang}: 1 block ({len(block['html'])} chars) -> {len(recs)} blocks")
    bounds = [0] + cuts + [len(inner)]
    for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
        n = len(tokenize(inner[a:b]))
        flag = "" if n <= cap else f"   OVER CAP ({cap})"
        anchor = "(head)" if i == 0 else f"#{ids.get(cuts[i - 1]) or '?'}"
        print(f"      part {i}: {n:5d} tokens  {anchor}{flag}")
    for old, new in numbering.items():
        print(f"      numbered {old} -> {new}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True, choices=BOOKS)
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--page", required=True)
    ap.add_argument("--block", required=True, type=int)
    ap.add_argument("--cap", type=int, default=1200,
                    help="proposals.js MAX_DIFF_TOKENS (default: 1200)")
    ap.add_argument("--number-anchors", action="store_true",
                    help="fill empty heading anchors used as cut points with "
                         "their item number")
    ap.add_argument("--resplit-proposals", action="store_true",
                    help="re-emit a proposal on the target as one card per "
                         "changed piece (it is stranded otherwise)")
    ap.add_argument("--shift-refs", action="store_true",
                    help="renumber proposals after the split on the same page")
    ap.add_argument("--write", action="store_true",
                    help="apply the changes (default: report only)")
    args = ap.parse_args()

    book, chapter_id, page_id, target = args.book, args.chapter, args.page, args.block
    print(f"{book} {chapter_id} {page_id} block {target}")

    chapters, pages, splits = {}, {}, {}
    for lang in LANGS:
        chapter = load_chapter(book, lang, chapter_id)
        if chapter is None:
            sys.exit(f"  refused — no {lang} chapter {chapter_id}")
        page = find_page(chapter, page_id)
        if page is None:
            sys.exit(f"  refused — no page {page_id} in {lang} {chapter_id}")
        blocks = page.get("blocks") or []
        if not 0 <= target < len(blocks):
            sys.exit(f"  refused — block {target} out of range in {lang} ({len(blocks)})")
        block = blocks[target]
        if block.get("type") != "proof":
            sys.exit(f"  refused — {lang} block {target} is {block.get('type')!r}, "
                     "not 'proof'")
        try:
            recs, cuts, kids, numbering, inner = split_block(block, args.cap,
                                                            args.number_anchors)
        except ValueError as exc:
            sys.exit(f"  refused — {lang}: {exc}")
        chapters[lang], pages[lang] = chapter, page
        splits[lang] = (block, recs, cuts, kids, numbering, inner)
        report_lang(lang, block, recs, cuts, kids, numbering, inner, args.cap)

    # --- guards ------------------------------------------------------------
    problems = []
    fr, en = splits["fr"], splits["en"]
    if len(fr[1]) != len(en[1]):
        problems.append(f"fr splits into {len(fr[1])} pieces, en into {len(en[1])}")
    fr_anchors = [{o: a for o, _t, _c, a in fr[3]}.get(o) for o in fr[2]]
    en_anchors = [{o: a for o, _t, _c, a in en[3]}.get(o) for o in en[2]]
    if fr_anchors != en_anchors:
        problems.append(f"cut anchors differ: fr {fr_anchors} vs en {en_anchors}")
    for lang in LANGS:
        block, recs, cuts, _kids, _num, inner = splits[lang]
        for i, rec in enumerate(recs):
            n = root_count(rec["html"])
            if n != 1:
                problems.append(f"{lang} piece {i} has {n} root elements")
        was, now = ID_RE.findall(block["html"]), []
        for rec in recs:
            now += ID_RE.findall(rec["html"])
        if was != now:
            problems.append(f"{lang} anchor ids changed: {set(was) ^ set(now)!r}")
        for i, (a, b) in enumerate(zip([0] + cuts, cuts + [len(inner)])):
            n = len(tokenize(inner[a:b]))
            if n > args.cap:
                problems.append(f"{lang} piece {i} is {n} tokens, over the {args.cap} cap")
        counts = {lg: len(pages[lg].get("blocks") or []) for lg in LANGS}
        if len(set(counts.values())) != 1:
            problems.append(f"page block counts already differ: {counts}")

    # --- proposals ---------------------------------------------------------
    run = load_json(proposals_path(book)) or {}
    proposals = list(run.get("proposals") or [])
    decided = {d.get("id") for d in
               (load_json(proposals_path(book).with_name("decisions.json")) or {})
               .get("decisions", [])}
    delta = len(fr[1]) - 1
    anchors = {lang: [open_tag_at(splits[lang][5], o) for o in splits[lang][2]]
               for lang in LANGS}
    new_run, on_target, shifted = [], 0, 0
    for prop in proposals:
        if prop.get("pageId") != page_id or prop.get("target", "block") != "block":
            new_run.append(prop)
            continue
        idx, lang = prop.get("blockIndex"), prop.get("lang")
        if idx == target:
            on_target += 1
            if not args.resplit_proposals:
                problems.append(f"{prop['id']} targets the block being split — it would "
                                "go permanently stale; pass --resplit-proposals")
                new_run.append(prop)
                continue
            if prop["before"] != splits[lang][0]["html"]:
                problems.append(f"{prop['id']} is already stale — resolve it first")
                new_run.append(prop)
                continue
            cards = resplit_proposal(dict(prop, bookHint=book), anchors[lang],
                                     splits[lang][1], target, splits[lang][4])
            if cards is None:
                problems.append(f"{prop['id']} cannot be re-split — an edit crosses a "
                                "cut point")
                new_run.append(prop)
                continue
            clash = [c["id"] for c in cards if c["id"] in decided]
            if clash:
                problems.append(f"{prop['id']}: new card id(s) {clash} already decided")
            print(f"  {prop['id']} -> {len(cards)} card(s): "
                  + ", ".join(f"{c['id']}" for c in cards))
            new_run += cards
        elif idx is not None and idx > target:
            if not args.shift_refs:
                problems.append(f"{prop['id']} sits at block {idx}, after the split — "
                                f"it needs blockIndex {idx + delta}; pass --shift-refs")
                new_run.append(prop)
                continue
            shifted += 1
            moved = dict(prop, blockIndex=idx + delta)
            if prop["id"] == address_id(book, lang, page_id, idx):
                if prop["id"] in decided:
                    problems.append(f"{prop['id']} moves to block {idx + delta} but "
                                    "carries a verdict — re-issuing its id would "
                                    "orphan the decision; resolve the run first")
                moved["id"] = address_id(book, lang, page_id, idx + delta)
            new_run.append(moved)
        else:
            new_run.append(prop)

    seen = set()
    for prop in new_run:
        if prop["id"] in seen:
            problems.append(f"duplicate proposal id {prop['id']} in the rewritten run")
        seen.add(prop["id"])

    if problems:
        print("\nrefused:")
        for p in problems:
            print(f"    ! {p}")
        return 1

    print(f"\n  page {page_id}: {len(pages['fr'].get('blocks'))} -> "
          f"{len(pages['fr'].get('blocks')) + delta} blocks in both languages")
    print(f"  proposals: {on_target} re-split, {shifted} re-indexed")
    if not args.write:
        print("\ndry run — re-run with --write to apply")
        return 0

    for lang in LANGS:
        blocks = pages[lang].get("blocks")
        blocks[target:target + 1] = splits[lang][1]
        write_chapter(chapter_path(book, lang, chapter_id), chapters[lang])
        print(f"  wrote {chapter_path(book, lang, chapter_id)}")
    if new_run != proposals:
        write_proposals(book, new_run, generator=run.get("generator"),
                        generated_at=run.get("generatedAt"),
                        base_commit=run.get("baseCommit"))
        print(f"  wrote {proposals_path(book)} ({len(new_run)} proposals)")

    # post-write: the alignment guard reads both languages off disk
    for lang in LANGS:
        err = check_alignment(book, lang, chapter_id,
                              load_chapter(book, lang, chapter_id))
        if err:
            print(f"    ! {err}")
            return 1
    print("  alignment holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
