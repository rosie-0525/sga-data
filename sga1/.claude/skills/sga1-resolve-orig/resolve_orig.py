#!/usr/bin/env python3
r"""Resolve \ifthenelse{\boolean{orig}}{ORIG}{CORR} to one branch, brace-balanced.

SGA1's dual edition is driven by a boolean flag, not SGA2's \sisi{A}{B} macro.
The master sga1-smf.tex sets `\setboolean{orig}{false}`, selecting the
*corrected* edition (the one SMF published). Every place the two editions differ
the body file writes:

    \ifthenelse{\boolean{orig}}{<original text>}{<corrected text>}

(whitespace, newlines, and LaTeX comments may sit between \ifthenelse, the
condition, and each arg). This step picks one branch per `--side` (default:
corrected) and splices it in, recursing so nested conditionals resolve too.

Two source quirks are handled:
  * LaTeX comments (`%...`) anywhere between the pieces — stripped up front so
    brace counting matches TeX (some comments contain unbalanced braces);
  * an "argument-crossing" stray `}` between the two branches, e.g.
    `\emph{... \ifthenelse{\boolean{orig}}{A}}{B}` — TeX closes \emph then feeds
    `{B}` to \ifthenelse as its false branch. We keep such trailing `}` after
    the chosen branch so the enclosing group still closes.

Only \ifthenelse whose condition is exactly `\boolean{orig}` is touched; any
other \ifthenelse (different condition) is left intact and its arguments are
still scanned for nested orig-conditionals.
"""
import argparse
import re
import sys
from pathlib import Path

IFTHEN = re.compile(r"\\ifthenelse(?![a-zA-Z])")
# the condition group, ignoring internal whitespace, must be exactly \boolean{orig}
_COND_ORIG = re.compile(r"\\boolean\s*\{\s*orig\s*\}\s*\Z")


def strip_comments(text: str) -> str:
    r"""Remove LaTeX line comments, honoring escaped \%.

    A `%` comment eats through the line's terminating newline (TeX joins the
    next line), so a `%`-only line vanishes entirely rather than leaving a blank
    line — critical inside `$$…$$` displays, where a blank line would break math
    mode. Lines with no comment keep their newline.
    """
    out = []
    for line in text.split("\n"):
        res = []
        k = 0
        m = len(line)
        had_comment = False
        while k < m:
            ch = line[k]
            if ch == "\\" and k + 1 < m:
                res.append(line[k : k + 2])
                k += 2
                continue
            if ch == "%":
                had_comment = True
                break
            res.append(ch)
            k += 1
        kept = "".join(res)
        if not had_comment:
            out.append(kept + "\n")
        else:
            # A `%` terminates any control word before it, so the next line must
            # not glue onto it (\ptbl%\nSerre -> \ptbl Serre, never \ptblSerre).
            if re.search(r"\\[a-zA-Z]+$", kept):
                kept += " "
            out.append(kept)
    return "".join(out)


def find_matching_brace(text: str, start: int) -> int:
    """Given text[start] == '{', return index of matching '}'. Honors \\{ \\}."""
    if text[start] != "{":
        raise ValueError(f"expected '{{' at {start}, got {text[start]!r}")
    depth = 1
    i = start + 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"unmatched '{{' starting at {start}")


def _skip_ws(text: str, i: int) -> int:
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    return i


def _read_group(text: str, start: int) -> tuple[str, int]:
    """Read a brace group beginning at the next non-space char from `start`.

    Returns (inner_content, index_after_close). Raises if the next non-space
    char is not '{'.
    """
    i = _skip_ws(text, start)
    if i >= len(text) or text[i] != "{":
        raise ValueError(f"expected '{{' near {start}")
    end = find_matching_brace(text, i)
    return text[i + 1 : end], end + 1


_TRAILING_CS = re.compile(r"\\[a-zA-Z]+$")


def resolve(text: str, side: str) -> str:
    r"""Replace every \ifthenelse{\boolean{orig}}{A}{B} with A (side='original')
    or B (side='corrected'). Recurses into the chosen branch for nesting.
    """
    out: list[str] = []
    tail = ""
    i = 0
    n = len(text)
    while i < n:
        m = IFTHEN.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        try:
            cond, pos = _read_group(text, m.end())
        except ValueError:
            seg = text[i : m.end()]
            out.append(seg)
            tail = (tail + seg)[-32:]
            i = m.end()
            continue

        if _COND_ORIG.search(cond.strip()) is None:
            # not an orig conditional — keep verbatim through the condition
            seg = text[i:pos]
            out.append(seg)
            tail = (tail + seg)[-32:]
            i = pos
            continue

        try:
            arg_orig, pos = _read_group(text, pos)
            # collect any "argument-crossing" stray closing braces before arg2
            stray = ""
            k = _skip_ws(text, pos)
            while k < n and text[k] == "}":
                stray += "}"
                k = _skip_ws(text, k + 1)
            arg_corr, pos = _read_group(text, k)
        except ValueError:
            # malformed — emit through the condition and continue
            seg = text[i:pos]
            out.append(seg)
            tail = (tail + seg)[-32:]
            i = pos
            continue

        prefix = text[i : m.start()]
        out.append(prefix)
        tail = (tail + prefix)[-32:]
        chosen = resolve(arg_orig if side == "original" else arg_corr, side)
        if chosen and chosen[0].isalpha() and _TRAILING_CS.search(tail):
            chosen = " " + chosen
        # Mirror boundary: the branch's braces terminated a trailing control word
        # (e.g. {J-P\ptbl}Serre); without them \ptbl would absorb the next letters.
        nxt = text[pos] if pos < n else ""
        if not stray and nxt.isalpha() and _TRAILING_CS.search(chosen):
            chosen = chosen + " "
        chosen += stray
        out.append(chosen)
        tail = (tail + chosen)[-32:]
        i = pos
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument(
        "--side",
        choices=["original", "corrected"],
        default="corrected",
        help="which branch to keep (default: corrected, matching "
        "\\setboolean{orig}{false})",
    )
    args = ap.parse_args()

    text = strip_comments(args.input.read_text(encoding="utf-8"))
    before = len(IFTHEN.findall(text))
    result = resolve(text, args.side)
    after = len(IFTHEN.findall(result))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    print(
        f"resolved orig conditionals: {before} \\ifthenelse → {after} remaining "
        f"→ {args.output} (side={args.side})"
    )
    if after:
        print(f"  note: {after} non-orig \\ifthenelse left intact", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
