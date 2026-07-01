#!/usr/bin/env python3
"""Resolve \\sisi{A}{B} to either A (original) or B (corrected), brace-balanced."""
import argparse
import re
import sys
from pathlib import Path

SISI = re.compile(r"\\sisi(?![a-zA-Z])")


def find_matching_brace(text: str, start: int) -> int:
    """Given text[start] == '{', return index of matching '}'.

    Honors TeX escapes: '\\{' and '\\}' do not change depth.
    """
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


def _consume_arg(text: str, start: int) -> tuple[str, int]:
    """Consume a single TeX argument starting at `start` (after whitespace skip).

    Returns (arg_content, index_after_arg). Honors LaTeX's rule that an
    unbraced argument is the next single token: a control sequence
    (\\name) or a single character.
    """
    n = len(text)
    i = start
    while i < n and text[i].isspace():
        i += 1
    if i >= n:
        raise ValueError(f"expected argument at {start}, got EOF")
    if text[i] == "{":
        end = find_matching_brace(text, i)
        return text[i + 1 : end], end + 1
    if text[i] == "\\":
        # control sequence: \ + letters, or \ + single non-letter
        j = i + 1
        if j < n and text[j].isalpha():
            while j < n and text[j].isalpha():
                j += 1
        else:
            j = min(j + 1, n)
        return text[i:j], j
    # single character
    return text[i], i + 1


_TRAILING_CS = re.compile(r"\\[a-zA-Z]+$")


def resolve(text: str, side: str) -> str:
    """Replace every \\sisi A B with A (side='original') or B (side='corrected').

    Each argument is either a brace group or a single token (TeX rule).
    Recurses into the chosen argument so nested \\sisi calls are handled.

    If the text just before a \\sisi call ends with a control-sequence
    name (\\foo) and the chosen replacement begins with a letter, inserts
    a space separator so the two don't merge into one extended command.
    """
    out: list[str] = []
    tail = ""  # last ~32 chars of combined output, for CS-boundary check
    i = 0
    n = len(text)
    while i < n:
        m = SISI.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        prefix = text[i : m.start()]
        out.append(prefix)
        tail = (tail + prefix)[-32:]
        a, pos = _consume_arg(text, m.end())
        b, pos = _consume_arg(text, pos)
        chosen = resolve(a if side == "original" else b, side)
        if chosen and chosen[0].isalpha() and _TRAILING_CS.search(tail):
            chosen = " " + chosen
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
        default="original",
        help="which side of \\sisi{A}{B} to keep (default: original)",
    )
    args = ap.parse_args()

    text = args.input.read_text(encoding="utf-8")
    before = text.count(r"\sisi")
    result = resolve(text, args.side)
    after = result.count(r"\sisi")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    print(
        f"resolved {before} \\sisi occurrences "
        f"({after} remaining) → {args.output} (side={args.side})"
    )
    return 0 if after == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
