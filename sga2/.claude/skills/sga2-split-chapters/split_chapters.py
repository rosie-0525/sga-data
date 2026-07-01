#!/usr/bin/env python3
"""Split the normalized SGA2 source into front-matter, per-chapter, and back-matter files."""
import argparse
import re
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("output_dir", type=Path)
    args = ap.parse_args()

    lines = args.input.read_text(encoding="utf-8").splitlines(keepends=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Index landmarks
    frontmatter_idx = None
    mainmatter_idx = None
    tableofcontents_idx = None
    bibliography_idx = None
    backmatter_idx = None
    chapter_indices: list[tuple[int, str]] = []  # (line index, header)

    # Matches \chapter, \chapter*, \chapter[, \chapter{
    chapter_re = re.compile(r"^\\chapter\*?(?:\[|\{)")
    for i, line in enumerate(lines):
        s = line.lstrip()
        if s.startswith(r"\frontmatter"):
            frontmatter_idx = i
        elif s.startswith(r"\mainmatter"):
            mainmatter_idx = i
        elif r"\tableofcontents" in line and tableofcontents_idx is None:
            tableofcontents_idx = i
        elif s.startswith(r"\begin{thebibliography}"):
            bibliography_idx = i
        elif s.startswith(r"\backmatter"):
            backmatter_idx = i
        elif chapter_re.match(s):
            chapter_indices.append((i, s.rstrip()))

    end_idx = len(lines)
    if backmatter_idx is None:
        backmatter_idx = end_idx
    if bibliography_idx is None:
        raise SystemExit("could not locate \\begin{thebibliography}")
    if mainmatter_idx is None:
        raise SystemExit("could not locate \\mainmatter")
    if frontmatter_idx is None:
        raise SystemExit("could not locate \\frontmatter")
    if not chapter_indices:
        raise SystemExit("no \\chapter found")

    # Front matter: lines (frontmatter+1) ... (mainmatter-1), skipping
    # \maketitle, \tableofcontents (and the bilingual tableofcontents
    # wrapper block, which spans one line).
    skip_substrings = (r"\maketitle", r"\tableofcontents")
    front_lines = [
        ln
        for ln in lines[frontmatter_idx + 1 : mainmatter_idx]
        if not any(s in ln for s in skip_substrings)
    ]
    _write(args.output_dir / "front-matter.tex", front_lines)

    # Only chapters between \mainmatter and \begin{thebibliography} are
    # real exposés. The front matter contains \chapter*{Préface} (kept
    # there) and the back matter contains \chapter*{Index ...} entries.
    chapter_starts = [
        idx for idx, _ in chapter_indices
        if mainmatter_idx < idx < bibliography_idx
    ]
    chapter_boundaries = chapter_starts + [bibliography_idx]
    if len(chapter_starts) != 15:  # 1 Introduction + 14 exposés
        print(
            f"warning: expected 15 chapters, found {len(chapter_starts)}",
            file=sys.stderr,
        )
    for n, start in enumerate(chapter_starts):
        end = chapter_boundaries[n + 1]
        out = args.output_dir / f"chapter-{n:02d}.tex"
        _write(out, lines[start:end])

    # Back matter: bibliography through end (excluding \backmatter, which
    # main.tex emits, and the trailing \end{document}).
    back_lines = []
    for ln in lines[bibliography_idx:backmatter_idx]:
        if ln.lstrip().startswith(r"\end{document}"):
            continue
        back_lines.append(ln)
    _write(args.output_dir / "back-matter.tex", back_lines)

    # Report
    print(f"front-matter.tex: {len(front_lines)} lines")
    for n, start in enumerate(chapter_starts):
        end = chapter_boundaries[n + 1]
        print(f"chapter-{n:02d}.tex: {end - start} lines (from source line {start+1})")
    print(f"back-matter.tex: {len(back_lines)} lines")
    return 0


def _write(path: Path, lines: list[str]) -> None:
    # Ensure trailing newline
    text = "".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
