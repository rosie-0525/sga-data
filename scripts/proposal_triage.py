#!/usr/bin/env python3
"""Triage the proposals still open in every sga*/data/proposals.json.

Classification is by the *shape* of the before->after diff only — where the
edit lands (math span / html tag / prose) and what kind of token it changes.
Nothing here judges whether a proposal is right; the aligned French is never
read. Output is a report; no corpus file is touched.

Usage: proposal_triage.py [out.json]
"""
import collections
import difflib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from proposals_lib import check_replacement, check_target, load_chapter  # noqa: E402

# One pass splits a block into the four things an edit can land in.
BLOCK_TOKEN = re.compile(
    r"(?P<tag><[^>]*>)"
    r"|(?P<math>\\\(.*?\\\)|\\\[.*?\\\])"
    r"|(?P<word>[^\W\d_]+|\d+)"
    r"|(?P<space>\s+)"
    r"|(?P<punct>.)",
    re.DOTALL,
)
# Inside a math span the atoms are TeX macros, identifiers, numbers, symbols.
MATH_TOKEN = re.compile(r"\\[A-Za-z]+|[^\W\d_]+|\d+|\s+|.", re.DOTALL)

# French function words that survive into an English block (usually in \text{}).
FR_WORDS = {
    "où", "et", "ou", "avec", "dou", "d", "donc", "si", "alors", "dans", "sur",
    "pour", "par", "tout", "tous", "toute", "toutes", "soit", "les", "des",
    "une", "un", "le", "la", "de", "du", "au", "aux", "en", "que", "qui",
    "dét", "car", "ainsi", "cas", "fini", "finie", "avec", "sauf", "quel",
    "quelconque", "toujours", "est", "sont", "aussi", "ainsi", "chaque",
}
ROMAN = re.compile(r"^[IVXLCM]+$")
REF_PUNCT = set(".,;:()[]§ \n\u00a0-–—'’")
SYMBOLISH = re.compile(r"^[A-Za-z0-9'’]$")
SUBSUP = set("_^{}'’")
BRACEY = set("(){}[] \n\\|")
HYPH = re.compile(r"(\w)[-\u00ad\u2010]\n\s*(\w)")
SOFT = re.compile(r"\u00ad")


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def has_accent(s):
    return any(unicodedata.combining(c)
               for c in unicodedata.normalize("NFD", s))


def diff_ops(a, b, token_re):
    """Token-level changed regions, as (op, old_tokens, new_tokens)."""
    ta = [m.group() for m in token_re.finditer(a)]
    tb = [m.group() for m in token_re.finditer(b)]
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    return [(t, ta[i1:i2], tb[j1:j2])
            for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]


def block_ops(a, b):
    ta = [(m.lastgroup, m.group()) for m in BLOCK_TOKEN.finditer(a)]
    tb = [(m.lastgroup, m.group()) for m in BLOCK_TOKEN.finditer(b)]
    sm = difflib.SequenceMatcher(None, [t[1] for t in ta], [t[1] for t in tb],
                                 autojunk=False)
    return [(t, ta[i1:i2], tb[j1:j2])
            for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]


def fine_ops(ops):
    """Re-diff inside changed math spans so a fragment is a whole TeX atom,
    not an arbitrary character run. Non-math ops pass through."""
    out = []
    for t, old, new in ops:
        kinds = {k for k, _v in old} | {k for k, _v in new}
        a = "".join(v for _k, v in old)
        b = "".join(v for _k, v in new)
        if kinds == {"math"} and a and b:
            out.extend(diff_ops(a, b, MATH_TOKEN))
        else:
            out.append((t, [v for _k, v in old], [v for _k, v in new]))
    return out


def loci(ops):
    """Which token kinds an edit touches; whitespace alone is not a locus."""
    return {k for _t, old, new in ops for k, _v in list(old) + list(new)
            if k != "space"}


def sides(ops):
    """(old fragments, new fragments) as flat token strings. Accepts both
    block ops (kind, text) and fine ops (plain text)."""
    def flat(side):
        return [t[1] if isinstance(t, tuple) else t for t in side]
    return ([t for _o, old, _n in ops for t in flat(old)],
            [t for _o, _l, new in ops for t in flat(new)])


# ---------------------------------------------------------------- math edits

TEXT_ARG = re.compile(
    r"\\(?:text|mbox|textrm|textit|textbf|textsf|hbox)\s*\{[^{}]*\}")


def in_text_arg_only(ops):
    """True when every changed math span differs only inside a \\text{…} —
    i.e. the edit is prose that happens to sit inside a formula."""
    changed = False
    for _t, old, new in ops:
        a = "".join(v for _k, v in old)
        b = "".join(v for _k, v in new)
        if a == b:
            continue
        changed = True
        if TEXT_ARG.sub("§", a) != TEXT_ARG.sub("§", b):
            return False
    return changed


def _lost_backslash(old, new):
    r"""`log` -> `\log`, `mathbb` -> `\mathbb`, or a bare `\` put back."""
    o = [t for t in old if t.strip()]
    n = [t for t in new if t.strip()]
    if not o and n == ["\\"]:
        return True
    return len(o) == len(n) == 1 and n[0] == "\\" + o[0]


def classify_math(ops):
    old, new = sides(fine_ops(ops))
    ochars, nchars = "".join(old), "".join(new)
    if not (ochars.strip() or nchars.strip()):
        return "math-spacing"

    ow = [t for t in old if re.fullmatch(r"[^\W\d_]+", t)]
    nw = [t for t in new if re.fullmatch(r"[^\W\d_]+", t)]
    # a French connective left inside math, swapped for its English form
    if ow and all(w.lower() in FR_WORDS for w in ow) \
            and not any(w.lower() in FR_WORDS for w in nw):
        return "math-untranslated-french"
    if in_text_arg_only(ops):
        return "math-text-wording"
    # é -> e and friends: same letters, different diacritics
    if (has_accent(ochars) or has_accent(nchars)) \
            and strip_accents(ochars) == strip_accents(nchars):
        return "math-accent"
    fine = fine_ops(ops)
    if all(_lost_backslash(o, n) for _t, o, n in fine):
        return "math-lost-backslash"
    if any(t.startswith("\\") for t in old + new):
        return "math-macro"
    if all(set(t) <= BRACEY for t in old + new):
        return "math-delimiter"
    if all(set(t) <= SUBSUP or SYMBOLISH.fullmatch(t) or t.isspace()
           for t in old + new):
        return "math-symbol"
    return "math-expression"


# --------------------------------------------------------------- prose edits

def refish(tokens):
    """Tokens that make up a cross-reference: numbers, roman numerals, the
    punctuation that glues them, and the words a citation is built from."""
    words = {"cf", "exp", "exposé", "expose", "n", "no", "nº", "ch", "chap",
             "chapitre", "sga", "ega", "th", "théorème", "theorem", "prop",
             "proposition", "cor", "corollaire", "corollary", "lemme", "lemma",
             "remarque", "remark", "and", "et", "voir", "see", "loc", "cit"}
    seen_num = False
    for t in tokens:
        if t.isspace() or set(t) <= REF_PUNCT:
            continue
        if t.isdigit():
            seen_num = True
            continue
        if ROMAN.fullmatch(t):          # a volume/exposé numeral, never the whole ref
            continue
        if t.lower() in words:
            continue
        return False
    return seen_num


def classify_prose(ops, lang="en"):
    old, new = sides(ops)
    ow = [t for t in old if re.fullmatch(r"[^\W\d_]+|\d+", t)]
    nw = [t for t in new if re.fullmatch(r"[^\W\d_]+|\d+", t)]

    if not (("".join(old)).strip() or ("".join(new)).strip()):
        return "whitespace"
    # the same words, moved
    if ow and collections.Counter(ow) == collections.Counter(nw):
        return "word-order"
    if ow and nw and len(ow) == len(nw):
        if [strip_accents(w) for w in ow] == [strip_accents(w) for w in nw] \
                and ow != nw:
            return "accent"
        if [w.lower() for w in ow] == [w.lower() for w in nw] and ow != nw:
            return "capitalization"
    def content(side):
        return [t for t in side if t.strip() and set(t) - REF_PUNCT]
    if (refish(old) or refish(new)) \
            and (refish(old) or not content(old)) \
            and (refish(new) or not content(new)):
        return "reference-number"
    if not ow and not nw:
        return "punctuation"
    # every replaced word is a near-twin of the one it replaces: a misspelling
    # or an agreement/inflection fix, not a change of wording
    if ow and len(ow) == len(nw) and ow != nw and all(
            difflib.SequenceMatcher(None, x.lower(), y.lower()).ratio() >= 0.75
            for x, y in zip(ow, nw)):
        return "spelling-inflection"
    if not ow:
        return "prose-omission"
    if not nw:
        return "prose-deletion"
    if len(ow) == 1 and len(nw) == 1 and len(ops) == 1:
        # a FR->EN terminology call only exists on the English side; the same
        # shape on the French side is a wording/source fix, not terminology
        return "terminology" if lang == "en" else "french-wording"
    if len(ow) + len(nw) <= 12:
        return "phrase-rewrite"
    return "passage-rewrite"


def classify(p):
    a, b = p["before"], p["after"]
    ops = block_ops(a, b)
    if not ops:
        return "no-op", ops
    # a line-break hyphen the mechanical pass missed — the whole edit is the join
    if SOFT.sub("", HYPH.sub(r"\1\2", a)) == SOFT.sub("", b):
        return "hyphen-linebreak", ops
    where = loci(ops)
    if "tag" in where:
        return ("markup-tag" if where == {"tag"} else "markup-mixed"), ops
    if where == {"math"}:
        return classify_math(ops), ops
    if "math" in where:
        # prose that should have been math (or the reverse): every changed
        # region is plain text on one side and a whole math span on the other
        def kinds(side):
            return {k for k, _v in side if k != "space"}
        if all(kinds(old) <= {"word", "punct"} and kinds(new) == {"math"}
               for _t, old, new in ops if kinds(old) or kinds(new)) \
                or all(kinds(old) == {"math"} and kinds(new) <= {"word", "punct"}
                       for _t, old, new in ops if kinds(old) or kinds(new)):
            return "unmarked-math", ops
        return "mixed-math-prose", ops
    return classify_prose(ops, p.get("lang", "en")), ops


def summarize(ops, limit=3):
    """Short human-readable rendering; math shows the inner change only."""
    bits = []
    fine = fine_ops(ops)
    for t, old, new in fine[:limit]:
        a, b = "".join(old), "".join(new)
        a, b = (a[:57] + "…" if len(a) > 60 else a), (b[:57] + "…" if len(b) > 60 else b)
        a, b = a.replace("\n", "⏎"), b.replace("\n", "⏎")
        bits.append(f"{a!r} → {b!r}" if a and b
                    else (f"+{b!r}" if b else f"-{a!r}"))
    if len(fine) > limit:
        bits.append(f"(+{len(fine) - limit} more)")
    return "  ".join(bits)


FAMILY = {
    "math-symbol": "math", "math-macro": "math", "math-expression": "math",
    "math-text-wording": "math", "unmarked-math": "math",
    "math-lost-backslash": "math",
    "math-delimiter": "math", "math-accent": "math", "math-spacing": "math",
    "math-untranslated-french": "math", "mixed-math-prose": "math",
    "prose-omission": "prose", "prose-deletion": "prose", "terminology": "prose",
    "phrase-rewrite": "prose", "passage-rewrite": "prose", "word-order": "prose",
    "accent": "prose", "capitalization": "prose", "reference-number": "prose",
    "french-wording": "prose",
    "spelling-inflection": "prose",
    "punctuation": "prose", "hyphen-linebreak": "prose", "whitespace": "prose",
    "markup-tag": "markup", "markup-mixed": "markup", "no-op": "other",
}
# What a reviewer has to do to settle a bucket, from the diff shape alone.
CHECK = {
    "hyphen-linebreak": "none — mechanical rejoin of a hyphenated line break",
    "whitespace": "none — whitespace only",
    "math-spacing": "read the formula: spacing inside math can change parsing",
    "math-symbol": "compare the symbol against the French/original formula",
    "math-macro": "compare the TeX against the French/original formula",
    "math-lost-backslash": "a backslash the transcription dropped — renders wrong today",
    "math-delimiter": "check the formula still parses and brackets balance",
    "math-accent": "safe if the letter is an ASCII identifier, not a word",
    "math-untranslated-french": "read the \\text{}: French left in an English formula",
    "math-text-wording": "prose inside a \\text{} — read it, the formula is untouched",
    "unmarked-math": "text that should be math (or the reverse) — check it renders",
    "math-expression": "read the whole formula against the French",
    "mixed-math-prose": "read the sentence and the formula together",
    "accent": "French spelling — check the word, not the sentence",
    "capitalization": "house style / proper noun call",
    "reference-number": "verify the target exists (manifest / anchor)",
    "punctuation": "read the sentence",
    "terminology": "glossary call — check glossary/GLOSSARY.md, then scripts/glossary_check.py",
    "french-wording": "one French word swapped for another — check the source scan",
    "spelling-inflection": "typo / agreement fix — check the word, not the sentence",
    "prose-omission": "compare with the aligned French: is the phrase really absent?",
    "prose-deletion": "compare with the aligned French: is the phrase really spurious?",
    "word-order": "read the sentence; meaning-preserving in most cases",
    "phrase-rewrite": "read the sentence against the aligned French",
    "passage-rewrite": "read the whole passage against the aligned French",
    "markup-tag": "check the href/anchor resolves; run the sga-check-errors skill",
    "markup-mixed": "markup + content in one edit — read both",
    "no-op": "before == after; drop it",
}


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        ROOT / "issues" / "proposal_triage.json"
    records, runs = [], {}
    chapters = {}                       # (book, lang, id) -> chapter json
    for path in sorted(ROOT.glob("sga*/data/proposals.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        book = doc.get("book") or path.parts[-3]
        runs[book] = {"generatedAt": doc.get("generatedAt"),
                      "generator": doc.get("generator"),
                      "baseCommit": doc.get("baseCommit"),
                      "open": len(doc.get("proposals") or [])}
        for p in doc.get("proposals") or []:
            bucket, ops = classify(p)
            key = (book, p.get("lang"), p.get("chapterId"))
            if key not in chapters:
                chapters[key] = load_chapter(book, p.get("lang"), p.get("chapterId"))
            chapter = chapters[key]
            if chapter is None:
                state = "no chapter file"
            else:
                _rec, err = check_target(chapter, p)
                state = err or (check_replacement(p.get("after")) or "applicable")
            size = sum(len("".join(v for _k, v in old)) +
                       len("".join(v for _k, v in new))
                       for _t, old, new in ops)
            records.append({
                "book": book,
                "id": p["id"],
                "lang": p["lang"],
                "chapterId": p.get("chapterId"),
                "pageId": p.get("pageId"),
                "target": p.get("target"),
                "authorCategory": p.get("category"),
                "family": FAMILY.get(bucket, "other"),
                "state": "applicable" if state == "applicable" else
                         ("stale" if state.startswith("conflict") else "blocked"),
                "stateDetail": None if state == "applicable" else state,
                "bucket": bucket,
                "edits": len(ops),
                "diffChars": size,
                "diff": summarize(ops),
                "rationale": p.get("rationale"),
            })

    buckets = {}
    for r in records:
        b = buckets.setdefault(r["bucket"], {
            "family": r["family"], "n": 0, "reviewerCheck": CHECK.get(r["bucket"], ""),
            "byBook": collections.Counter(), "byLang": collections.Counter(),
            "byAuthorCategory": collections.Counter(), "_sizes": [],
            "examples": []})
        b["n"] += 1
        b["byBook"][r["book"]] += 1
        b["byLang"][r["lang"]] += 1
        b["byAuthorCategory"][r["authorCategory"]] += 1
        b["_sizes"].append(r["diffChars"])
    for b in buckets.values():
        sizes = sorted(b.pop("_sizes"))
        b["medianDiffChars"] = sizes[len(sizes) // 2]
        for key in ("byBook", "byLang", "byAuthorCategory"):
            b[key] = dict(sorted(b[key].items()))
    for r in records:
        ex = buckets[r["bucket"]]["examples"]
        if len(ex) < 5:
            ex.append({"id": r["id"], "diff": r["diff"]})

    report = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "proposal_triage.py — diff-shape classification, no source read",
        "totalOpen": len(records),
        "runs": runs,
        "byFamily": dict(collections.Counter(r["family"] for r in records)),
        "byState": dict(collections.Counter(r["state"] for r in records)),
        "buckets": dict(sorted(buckets.items(), key=lambda kv: (-kv[1]["n"], kv[0]))),
        "records": records,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")

    books = sorted(runs)
    w = max(len(b) for b in buckets) + 1
    print(f"{'bucket':<{w}} {'n':>5}  " + "  ".join(f"{b:>6}" for b in books))
    for name, b in report["buckets"].items():
        cells = "  ".join(f"{b['byBook'].get(bk, 0):>6}" for bk in books)
        print(f"{name:<{w}} {b['n']:>5}  {cells}")
    print(f"{'TOTAL':<{w}} {len(records):>5}  " +
          "  ".join(f"{runs[bk]['open']:>6}" for bk in books))
    print("\nstate: " + "  ".join(
        f"{k}={v}" for k, v in sorted(report["byState"].items())))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
