#!/usr/bin/env python3
"""Stage the SGA1 source as UTF-8.

The SGA1 body file (smf_doc-math_3_01.tex) is plain ASCII — accents are
written as LaTeX control sequences (\\'e, {\\^e}, \\c{c}), not 8-bit bytes —
so there is no Windows-1252 conversion to do (unlike SGA2). We still read it
through latin-1 (an ASCII superset that never raises on a stray high byte) and
re-emit UTF-8, so the staging step is uniform across both books.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "00-original_tex" / "smf_doc-math_3_01.tex"
DST = ROOT / "01-normalized_tex" / ".staging" / "00-ascii.tex"


def main() -> None:
    DST.parent.mkdir(parents=True, exist_ok=True)
    text = SRC.read_text(encoding="latin-1")
    DST.write_text(text, encoding="utf-8")
    print(f"wrote {DST} ({len(text):,} chars)")


if __name__ == "__main__":
    main()
