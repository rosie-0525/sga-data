#!/usr/bin/env python3
"""Repair mixed/nested math-delimiter transcription bugs in sga6/01-transcribed.

Three mechanical bug classes (run BEFORE fix_bare_math.py):

A. "Swapped" groups: a bare-paren math group whose *printed* parens were
   transcribed as \\( \\) delimiters — e.g. `(a_i\\(p\\))` for \\(a_i(p)\\),
   `(\\operatorname{Spec}\\(K\\))` for \\(\\operatorname{Spec}(K)\\). The tell is
   an identifier char directly before an inner `\\(` (prose like
   `(resp. \\(E'\\))` always has a space). Fix: outer parens -> \\( \\),
   inner \\( \\) -> plain parens.

B. Nested delimiters: `\\(\\mathcal O_Y\\(1\\)\\)` — an inner \\( \\) pair inside
   an already-delimited span. Fix: inner pair -> plain parens.

C. Point typos (hardcoded): doubled `\\\\(S\\\\)` in XIII 3.8; `\\(geq2\\)`
   missing backslash in XIII; crossed `(lambda_{-1}\\(N)=0\\)` in X.

Usage: python3 scripts/fix_mixed_math.py [--write]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "01-transcribed"
FILES = ["0", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX",
         "X", "XII", "XIII", "XIV"]

STOP = {"le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "où",
        "si", "on", "en", "par", "pour", "avec", "sans", "sur", "sous",
        "dans", "est", "sont", "cas", "resp", "voir", "cf", "loc", "cit",
        "donc", "alors", "comme", "que", "qui", "ne", "pas", "plus", "tout",
        "i.e", "ie"}
WORD_RE = re.compile(r"[a-zàâçéèêëîïôûùüÿœ]{2,}")

# masked regions: comments, tags, display math (no mixed bugs expected there)
MASK_RE = re.compile(r"(?s)<!--.*?-->|(?<!\\)\\\[.*?(?<!\\)\\\]|<[^>]+>")

# chars that, directly before an inner \(, mark a swapped group (never prose)
ADJ = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
          "}=_^|/+-'′")

POINT_FIXES = {
    "XIII": [
        ("\\\\(S\\\\) un schéma noethérien, \\\\(Y\\\\) un \\\\(S\\\\)-schéma",
         "\\(S\\) un schéma noethérien, \\(Y\\) un \\(S\\)-schéma"),
        ("\\\\(X\\\\) le schéma des zéros d'une section \\\\(\\varphi\\\\)",
         "\\(X\\) le schéma des zéros d'une section \\(\\varphi\\)"),
        ("\\(geq2\\)", "\\(\\geq2\\)"),
        ("\\(geq3\\)", "\\(\\geq3\\)"),
    ],
    "X": [
        ("(lambda_{-1}\\(N)=0\\)", "\\(\\lambda_{-1}(N)=0\\)"),
    ],
}


def stopwords(s):
    s = re.sub(r"\\[a-zA-Z]+", " ", s)
    return [w for w in WORD_RE.findall(s) if w in STOP]


def find_groups(masked, start, end):
    """Outermost balanced groups counting every paren (escaped or not);
    only unescaped-open groups are yielded as candidates."""
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
                if i == 0 or masked[i - 1] != "\\":
                    yield (i, j - 1)
                    i = j
                    continue
                # escaped-open span: still recurse inside it
                yield from find_groups(masked, i + 1, j - 1)
                i = j
                continue
        i += 1


def swap_group(content):
    """inner \\( \\) -> plain parens (for a group being re-wrapped)."""
    return content.replace("\\(", "(").replace("\\)", ")")


def fix_swapped(body, log):
    masked = MASK_RE.sub(lambda m: "\x00" * len(m.group(0)), body)
    repl = []
    for oi, ci in find_groups(masked, 0, len(masked)):
        content = masked[oi + 1:ci]
        if "\x00" in content or "\\(" not in content:
            continue
        outside = re.sub(r"(?s)\\\(.*?\\\)", " ", content)
        adjacent = any(m.start() > 0 and content[m.start() - 1] in ADJ
                       for m in re.finditer(r"\\\(", content))
        # `(\(f^*\)^{-1}(\mathfrak L))`: TeX residue outside the inner spans
        # would render as literal prose — also a swapped group. A group that is
        # *only* prose parens around whole math spans renders fine; skip it.
        residue = bool(re.search(r"[\^_]|\\[a-zA-Z]{2,}", outside))
        if (adjacent or residue) and not stopwords(outside):
            repl.append((oi, ci))
    out = body
    for oi, ci in sorted(repl, reverse=True):
        new = "\\(" + swap_group(body[oi + 1:ci]) + "\\)"
        log.append(("SWAP", body[oi:ci + 1], new))
        out = out[:oi] + new + out[ci + 1:]
    return out


def fix_nested(body, log):
    """Inline delimiters must strictly alternate \\( \\) \\( \\) …. Fix the
    one local pattern we understand — a whole pair nested directly inside a
    span, `\\( … \\( … \\) … \\)` with nothing else between (variant b) — and
    *report* any other anomaly (stray open/close) for manual repair instead of
    guessing, so one typo can't cascade down the file."""
    masked = MASK_RE.sub(lambda m: "\x00" * len(m.group(0)), body)
    toks = [(m.start(), m.group(0)) for m in re.finditer(r"\\[()]", masked)]
    drop = []          # positions whose backslash must be removed
    i, n = 0, len(toks)
    while i < n:
        pos, tok = toks[i]
        ctx = masked[max(0, pos - 60):pos + 60].replace("\x00", "·")
        if tok != "\\(":
            log.append(("STRAY-CLOSE", ctx, ""))
            i += 1
            continue
        # inside a span; expect its close next
        if i + 1 < n and toks[i + 1][1] == "\\)":
            i += 2
            continue
        # nested pair? \( \( \) \)
        if (i + 3 < n and toks[i + 1][1] == "\\(" and toks[i + 2][1] == "\\)"
                and toks[i + 3][1] == "\\)"):
            drop += [toks[i + 1][0], toks[i + 2][0]]
            log.append(("NEST", ctx, ""))
            i += 4
            continue
        log.append(("STRAY-OPEN", ctx, ""))
        i += 1
    out = body
    for pos in sorted(drop, reverse=True):
        out = out[:pos] + out[pos + 1:]   # remove the backslash
    return out


def main():
    write = "--write" in sys.argv
    for name in FILES:
        path = SRC / f"{name}.html"
        src = path.read_text(encoding="utf-8")
        head, body = src.split("<body>", 1)
        log = []
        for old, new in POINT_FIXES.get(name, []):
            n = body.count(old)
            if n:
                body = body.replace(old, new)
                log.append((f"POINT x{n}", old[:70], new[:70]))
            else:
                log.append(("POINT-MISS", old[:70], ""))
        body = fix_swapped(body, log)
        body = fix_nested(body, log)
        if log:
            print(f"== {name}: {len(log)} changes")
            for tag, old, new in log:
                o = old.replace("\n", "¶")[:100]
                n = str(new).replace("\n", "¶")[:100]
                print(f"   {tag:12s} {o!r}\n   {'':12s}-> {n!r}")
        if write:
            path.write_text(head + "<body>" + body, encoding="utf-8")
    print("WROTE" if write else "DRY RUN")


if __name__ == "__main__":
    main()
