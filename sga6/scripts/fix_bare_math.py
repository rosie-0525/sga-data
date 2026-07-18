#!/usr/bin/env python3
"""Wrap bare-parenthesis inline math in \\( \\) delimiters.

Several SGA 6 transcription batches wrote inline math as plain parenthesized
TeX — e.g. `(X\\longrightarrow S)`, `(a_2^{-1}(y)=s)`, `(X)` — instead of
`\\(...\\)`. MathJax never sees those, so they display as literal TeX source.
This script finds balanced paren groups outside tags/comments/existing math
and wraps the ones that are recognizably math.

Classification (conservative — prose is left alone):
  math  = contains a TeX command with no French stop-word left after
          stripping commands; or contains ^ _ = &lt; &gt; / or nested parens
          over an identifier-ish charset with no stop-word; or is a single
          letter (except "i", which is almost always an enumeration marker
          here, like the multi-letter roman numerals).
  prose = roman-numeral markers (i), (ii)…; ALL-CAPS acronyms (ML), (MLAR);
          pure numbers/refs (2.2.4), (1965); anything containing a French
          stop word or an unknown shape.

Usage: python3 scripts/fix_bare_math.py [--write] [files...]
Default files: III IIIB V VI XII XV (the affected exposés). Without --write,
prints the would-be conversions (dry run). A review log of every decision on
TeX-containing groups goes to stdout.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "01-transcribed"

DEFAULT_FILES = ["0", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XII", "XIII", "XIV"]

ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"}
# single letters that are math even though they collide with roman numerals
SINGLE_MATH_OK = set("abcdefghjklmnopqrstuvwxyz") | set("ABCDEFGHIJKLMNPQRSTUVWXYZ")
SINGLE_MATH_OK -= {"i"}   # (i) is an enumeration marker; capital (I) is math
# XIV writes some math with literal Greek glyphs (φ, ξ, ℓ …)
GREEK = set("αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩ") | {"ℓ", "·"}
SINGLE_MATH_OK |= GREEK - {"·"}

STOP = {"le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "où",
        "si", "on", "en", "par", "pour", "avec", "sans", "sur", "sous",
        "dans", "est", "sont", "cas", "resp", "voir", "cf", "loc", "cit",
        "exemple", "ex", "chap", "exp", "sga", "ega", "page", "pages",
        "ibid", "donc", "alors", "comme", "que", "qui", "ne", "pas", "plus",
        "tout", "tous", "toute", "notations", "notation", "the", "of", "and",
        "see", "dire", "être", "avoir", "aussi", "ici", "après", "avant"}

MASK_RE = re.compile(
    r"(?s)<!--.*?-->"
    r"|(?<!\\)\\\[.*?(?<!\\)\\\]"
    r"|(?<!\\)\\\(.*?(?<!\\)\\\)"
    r"|<[^>]+>")

WORD_RE = re.compile(r"[a-zàâçéèêëîïôûùüÿœ]{2,}")
CHARSET_RE = re.compile(
    r"^[A-Za-z0-9À-ÿ'′,;:=+\-*/|!.\s(){}\[\]\\^_&#"
    r"Ͱ-Ͽℓ·]+$")   # + Greek glyphs, ℓ, · (XIV)


def french_words(s):
    s = s.replace("\\acute et", " ")            # "ét" accent, not the word "et"
    s = re.sub(r"\\[a-zA-Z]+", " ", s)          # drop TeX commands
    s = re.sub(r"&[a-z]+;", " ", s)             # drop entities
    return [w for w in WORD_RE.findall(s) if w in STOP]


def is_math(content):
    c = content.strip()
    if not c or "\x00" in c:
        return False
    low = c.lower()
    if low in ROMAN:
        return len(c) == 1 and c in SINGLE_MATH_OK
    if len(c) == 1:
        return c in SINGLE_MATH_OK
    if re.fullmatch(r"[A-Za-z]['′]+", c):       # primed letter: (X'), (i′)
        return True
    if re.fullmatch(r"[A-Z]{2,}", c):           # acronym condition names
        return False
    if re.fullmatch(r"[\d.,;\s\-–]+", c):       # numbers, refs, ranges
        return False
    if re.search(r"(^|\s)\[\d+\]", c):          # citation: ([12] 1.3.6 (ii) c)
        return False                            # (but not a shift: (-)(1)[2])
    if re.search(r"\((?:i|ii|iii|iv|vi|vii|viii|ix)\)", c):
        return False                            # contains a roman marker
    if french_words(c):
        return False
    if not CHARSET_RE.match(c):
        return False
    if re.search(r"\\[a-zA-Z]{2,}", c):         # TeX command
        return True
    if re.search(r"[\^_=/]|&lt;|&gt;", c):      # scripts, relations
        return True
    if "(" in c:                                # nested parens: f(x), s(W)
        return True
    if re.fullmatch(r"[A-Za-z]['′]*([,;:][ ]?[A-Za-z]['′]*)+", c):
        return True                             # letter lists: (u,v,w)
    return False


def find_groups(masked, start=0, end=None):
    """Yield (open_idx, close_idx, content) for balanced outermost groups."""
    if end is None:
        end = len(masked)
    i = start
    while i < end:
        if masked[i] == "(":
            depth, j = 1, i + 1
            while j < end and depth:
                if masked[j] == "(":
                    depth += 1
                elif masked[j] == ")":
                    depth -= 1
                j += 1
            if depth == 0:
                yield (i, j - 1, masked[i + 1:j - 1])
                i = j
                continue
        i += 1


def convert(name, write):
    path = SRC / f"{name}.html"
    src = path.read_text(encoding="utf-8")
    head, body = src.split("<body>", 1)
    masked = MASK_RE.sub(lambda m: "\x00" * len(m.group(0)), body)

    repl = []          # (open_idx, close_idx)
    review = []

    def walk(a, b):
        for oi, ci, content in find_groups(masked, a, b):
            if is_math(content):
                repl.append((oi, ci))
            else:
                if re.search(r"\\[a-zA-Z]{2,}|[\^_]", content):
                    review.append((oi, "SKIP", content))
                walk(oi + 1, ci)               # recurse: (resp. (b/a))

    walk(0, len(masked))

    out = list(body)
    for oi, ci in sorted(repl, reverse=True):
        out[ci] = "\\)"
        out[oi] = "\\("
    new_body = "".join(out)

    def ln(pos):
        return head.count("\n") + body[:pos].count("\n") + 1

    print(f"== {name}: {len(repl)} conversions, {len(review)} skipped-with-TeX")
    for oi, ci in sorted(repl)[:2000]:
        print(f"   {ln(oi):5d}  ({body[oi+1:ci][:90]})")
    for oi, tag, content in review:
        print(f"   {ln(oi):5d}  {tag} ({content[:90]})")

    if write:
        path.write_text(head + "<body>" + new_body, encoding="utf-8")


def main():
    write = "--write" in sys.argv
    files = [a for a in sys.argv[1:] if not a.startswith("--")] or DEFAULT_FILES
    for name in files:
        convert(name, write)
    print("WROTE" if write else "DRY RUN")


if __name__ == "__main__":
    main()
