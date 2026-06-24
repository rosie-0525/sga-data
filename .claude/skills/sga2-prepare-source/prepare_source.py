#!/usr/bin/env python3
"""Convert SGA2 source from Windows-1252 to UTF-8."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "00-original_tex" / "smf_doc-math_4_01.tex"
DST = ROOT / "01-normalized_tex" / ".staging" / "00-utf8.tex"


def main() -> None:
    DST.parent.mkdir(parents=True, exist_ok=True)
    text = SRC.read_text(encoding="cp1252")
    DST.write_text(text, encoding="utf-8")
    print(f"wrote {DST} ({len(text):,} chars)")


if __name__ == "__main__":
    main()
