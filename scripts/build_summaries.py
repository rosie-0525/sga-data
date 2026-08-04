#!/usr/bin/env python3
"""Beginner-facing exposé summaries for the landing page (summaries.json).

index.html shows a daily "featured exposé" card: title plus a short
bilingual hook, picked date-deterministically from repo-root summaries.json.
That file is owned by this script; the convert step never touches it, so
hand-written text survives any upstream manifest regeneration.

The skeleton (identity, display titles, deep links) is derived from each
book's fr manifest (`alias == "EXPOSÉ"` chapters) and the en chapter files.
Titles are made render-ready at ingestion — index.html has no MathJax, so
inline TeX folds to Unicode (\\(\\ell\\) → ℓ), shouty ALL-CAPS titles are
sentence-cased (known proper nouns re-capitalized) and `EXPOSÉ N` prefixes
dropped, N being the chapter's own number — a generic roman-numeral regex
would eat the "A" of "EXPOSÉ XII A THEOREM…". summary_fr / summary_en start
empty and are hand-written (see --merge); --write never overwrites a
non-empty authored field (title_fr, title_en, summary_fr, summary_en), it
only refreshes identity fields (number, href, order) and adds/drops entries
to match the manifests.

Usage:
  build_summaries.py                 # dry run: report skeleton drift
  build_summaries.py --write         # build/refresh the skeleton
  build_summaries.py --merge F [F…]  # fold authored fragments in, by (book, id)
  build_summaries.py --check         # coverage gate: exit 1 on any problem

Fragment shape for --merge:
  {"book": "sga3", "entries": [{"id": "I", "title_fr": …, "title_en": …,
                                "summary_fr": …, "summary_en": …}]}
Only non-empty fields are taken from a fragment.
"""
import argparse
import json
import re

from glossary_lib import ROOT, BOOKS, dump_json, load_chapter, load_json, \
    load_manifest

SUMMARIES_PATH = ROOT / "summaries.json"
BOOK_LABELS = {"sga4.5": "SGA 4½"}
AUTHORED = ("title_fr", "title_en", "summary_fr", "summary_en")
IDENTITY = ("book_label", "number", "href")

# ---------------------------------------------------------------------------
# Title normalization

MATH_SPAN_RE = re.compile(r"\\\((.*?)\\\)", re.S)
# Innermost-first, iterated to a fixed point: \mathop{\underline{\mathrm{X}}}
# unwraps in three passes.
TEX_STEPS = [
    (re.compile(r"\\(?:operatorname|mathrm|mathop|mathbf|mathit|underline|"
                r"text)\{([^{}]*)\}"), r"\1"),
    (re.compile(r"\\nolimits"), ""),
    (re.compile(r"\\ell\b"), "ℓ"),
    (re.compile(r"\\lambda\b"), "λ"),
    (re.compile(r"\\zeta\b"), "ζ"),
    (re.compile(r"\^\{?\\bullet\}?"), "•"),
    (re.compile(r"\^\{?i\}?"), "ⁱ"),
    (re.compile(r"\^\{?n\}?"), "ⁿ"),
    (re.compile(r"\\[,;!]"), " "),
    (re.compile(r"'"), "′"),
]

# Proper nouns flattened by sentence-casing an ALL-CAPS title. Plain \b so
# hyphenated pairs (Riemann-Roch, Euler-Poincaré) match word by word.
NAMES = ["Cartan", "Chern", "Euler", "Frobenius", "Griffiths", "Grothendieck",
         "Lefschetz", "Lie", "Milnor", "Néron", "Nielsen", "Noether",
         "Picard", "Poincaré", "Riemann", "Roch", "Wecken", "Weil", "Weyl"]
RECAP_STEPS = [(re.compile(r"\b" + n.lower() + r"\b"), n) for n in NAMES]
RECAP_STEPS += [
    (re.compile(r"\bk\b(?!['’])"), "K"),      # groupes K, K-groups
    (re.compile(r"\bl\b(?!['’])"), "L"),      # fonctions L (not l'/l’)
    (re.compile(r"\ba\.(?=\s)"), "A."),       # A. Grothendieck
]
FIRST_LETTER_RE = re.compile(r"[a-zà-öø-ÿ]")
AFTER_STOP_RE = re.compile(r"(?<=[.!?])(\s+)([a-zà-öø-ÿ])")


def fold_math(tex):
    """One \\( … \\) body → plain Unicode text."""
    prev = None
    while prev != tex:
        prev = tex
        for pat, repl in TEX_STEPS:
            tex = pat.sub(repl, tex)
    return tex


def shouty(text):
    """True for ALL-CAPS-set titles; tolerant of lowercase symbols (ℓ, ζ)."""
    cased = [c for c in text if c.isalpha()]
    if len(cased) < 4:
        return False
    return sum(1 for c in cased if c.isupper()) / len(cased) >= 0.9


def strip_expose_prefix(title, number):
    """Drop a leading 'EXPOSÉ <number>' — only this chapter's own number, in
    its glued or spaced spelling (VIA / VI A)."""
    variants = {number}
    m = re.fullmatch(r"([IVXLC]+)([AB])", number)
    if m:
        variants.add(m.group(1) + " " + m.group(2))
    if number.lower() == "vbis":
        variants.add("V bis")
    alt = "|".join(re.escape(v) for v in sorted(variants, key=len, reverse=True))
    return re.sub(r"^\s*EXPOS[ÉE]\s+(?:" + alt + r")[\s.:—–-]+", "", title,
                  count=1, flags=re.IGNORECASE)


def sentence_case(text):
    text = text.lower()
    text = FIRST_LETTER_RE.sub(lambda m: m.group(0).upper(), text, count=1)
    text = AFTER_STOP_RE.sub(lambda m: m.group(1) + m.group(2).upper(), text)
    for pat, repl in RECAP_STEPS:
        text = pat.sub(repl, text)
    return text


def normalize_title(raw, number):
    title = MATH_SPAN_RE.sub(lambda m: fold_math(m.group(1)), raw)
    title = strip_expose_prefix(title, number)
    title = re.sub(r"\s+", " ", title).strip()
    if shouty(title):
        title = sentence_case(title)
    return title


# ---------------------------------------------------------------------------
# Skeleton

def expected_entries():
    """The 125 exposés in book/manifest order, titles normalized, summaries
    empty — what summaries.json must contain, identity-wise."""
    entries = []
    for book in BOOKS:
        for c in load_manifest(book)["chapters"]:
            if c.get("alias") != "EXPOSÉ":
                continue
            number = c.get("number") or c["id"]
            en = load_chapter(book, "en", c["id"])
            entries.append({
                "book": book,
                "book_label": BOOK_LABELS.get(book, "SGA " + book[3:]),
                "id": c["id"],
                "number": number,
                "href": book + "/paper.html#" + c["page_ids"][0],
                "title_fr": normalize_title(c["title"], number),
                "title_en": normalize_title(en["title"], number) if en else "",
                "summary_fr": "",
                "summary_en": "",
            })
    return entries


def load_summaries():
    if SUMMARIES_PATH.exists():
        return load_json(SUMMARIES_PATH)
    return {"version": 1, "entries": []}


def save_summaries(doc):
    SUMMARIES_PATH.write_text(dump_json(doc), encoding="utf-8")


def refresh(doc):
    """Merge the expected skeleton into doc. Returns (new_entries, report):
    added / removed keys and refreshed-identity counts; authored fields of
    surviving entries are kept verbatim."""
    old = {(e["book"], e["id"]): e for e in doc["entries"]}
    new_entries, retouched = [], 0
    for exp in expected_entries():
        kept = old.pop((exp["book"], exp["id"]), None)
        if kept:
            if any(exp[f] != kept.get(f) for f in IDENTITY):
                retouched += 1
            for f in AUTHORED:
                if kept.get(f):
                    exp[f] = kept[f]
        new_entries.append(exp)
    added = [k for k in ((e["book"], e["id"]) for e in new_entries)
             if k not in {(e["book"], e["id"]) for e in doc["entries"]}]
    return new_entries, {"added": added, "removed": sorted(old),
                         "retouched": retouched}


# ---------------------------------------------------------------------------
# Modes

def do_write(apply):
    doc = load_summaries()
    new_entries, rep = refresh(doc)
    changed = new_entries != doc["entries"]
    print(f"{len(new_entries)} exposés — +{len(rep['added'])} new, "
          f"-{len(rep['removed'])} stale, {rep['retouched']} identity refresh(es)")
    for k in rep["removed"]:
        print(f"    ! dropping stale entry {k[0]}:{k[1]}")
    if not changed:
        print("summaries.json already up to date")
        return 0
    if apply:
        doc["entries"] = new_entries
        save_summaries(doc)
        print(f"wrote {SUMMARIES_PATH}")
    else:
        print("dry run — re-run with --write to apply")
    return 0


def do_merge(paths):
    doc = load_summaries()
    by_key = {(e["book"], e["id"]): e for e in doc["entries"]}
    unknown, folded = [], 0
    for path in paths:
        frag = load_json(path)
        book = frag.get("book")
        for fe in frag["entries"]:
            key = (fe.get("book") or book, fe["id"])
            entry = by_key.get(key)
            if not entry:
                unknown.append(f"{path}: {key[0]}:{key[1]}")
                continue
            for f in AUTHORED:
                if fe.get(f):
                    entry[f] = fe[f]
            folded += 1
        print(f"{path}: {len(frag['entries'])} entr(ies)")
    if unknown:
        for u in unknown:
            print(f"    ! unknown exposé {u} — nothing merged from it")
        return 1
    save_summaries(doc)
    print(f"folded {folded} entr(ies) into {SUMMARIES_PATH}")
    return 0


def do_check():
    problems, warnings = [], []
    if not SUMMARIES_PATH.exists():
        print(f"! {SUMMARIES_PATH} missing — run --write first")
        return 1
    doc = load_summaries()
    have = {(e["book"], e["id"]): e for e in doc["entries"]}
    expected = expected_entries()
    for k in sorted({(e["book"], e["id"]) for e in doc["entries"]}
                    - {(e["book"], e["id"]) for e in expected}):
        problems.append(f"{k[0]}:{k[1]}: stale — not in any manifest")
    for exp in expected:
        key = (exp["book"], exp["id"])
        entry = have.get(key)
        where = f"{key[0]}:{key[1]}"
        if not entry:
            problems.append(f"{where}: missing entry")
            continue
        for f in IDENTITY:
            if entry.get(f) != exp[f]:
                problems.append(f"{where}: {f} is {entry.get(f)!r}, "
                                f"manifest says {exp[f]!r}")
        for f in AUTHORED:
            text = entry.get(f) or ""
            if not text.strip():
                problems.append(f"{where}: {f} empty")
                continue
            if "\\" in text:
                problems.append(f"{where}: {f} has a TeX remnant: {text!r}")
            if "<" in text or ">" in text:
                problems.append(f"{where}: {f} has markup (card renders "
                                f"plain text): {text!r}")
            if f.startswith("title") and shouty(text):
                problems.append(f"{where}: {f} still ALL-CAPS: {text!r}")
            if f.startswith("summary"):
                words = len(text.split())
                if not 18 <= words <= 60:
                    warnings.append(f"{where}: {f} is {words} words "
                                    f"(aim for 25–45)")
    for line in problems:
        print(f"! {line}")
    for line in warnings:
        print(f"~ {line}")
    n = len(expected)
    if problems:
        print(f"\n{len(problems)} problem(s) across {n} exposés")
        return 1
    print(f"OK: {n} exposés, all with bilingual titles and summaries"
          + (f" ({len(warnings)} length warning(s))" if warnings else ""))
    return 0


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true",
                      help="build/refresh the skeleton (default: report only)")
    mode.add_argument("--merge", nargs="+", metavar="FRAGMENT",
                      help="fold authored fragment file(s) into summaries.json")
    mode.add_argument("--check", action="store_true",
                      help="validate coverage and renderability; exit 1 on problems")
    args = ap.parse_args()

    if args.check:
        return do_check()
    if args.merge:
        return do_merge(args.merge)
    return do_write(args.write)


if __name__ == "__main__":
    raise SystemExit(main())
