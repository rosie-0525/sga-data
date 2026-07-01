#!/usr/bin/env python3
"""Split the normalized SGA1 source into front-matter, per-chapter, back-matter.

Landmarks: \\frontmatter … \\mainmatter … (12 \\chapter exposés) … \\backmatter.
Unlike SGA2 (one global bibliography), SGA1 has a per-chapter \\thebibliography
embedded inside each exposé, so the chapter region runs all the way to
\\backmatter; the bibliographies stay inside their chapter files.

Exposé VII does not exist in SGA1: a `\\refstepcounter{chapter}` + toc note sits
between exposé VI and VIII (so the chapter counter skips to 8). That block lands
naturally at the tail of the VI file, keeping pdflatex numbering correct.
"""
import argparse
import re
import sys
from pathlib import Path

EXPECTED_CHAPTERS = 12  # exposés I–VI, VIII–XIII (VII omitted)


def _remove_group_containing(text: str, needle: str) -> str:
    """Remove the innermost brace group {...} that encloses `needle`.

    Used to drop the source's `{\\def\\footnotemark{}\\let\\\\\\relax …
    \\tableofcontents}` apparatus (main.tex emits its own TOC). If `needle` is
    not inside a group, only the token itself is removed.
    """
    i = text.find(needle)
    if i < 0:
        return text
    depth = 0
    opener = -1
    for k in range(i - 1, -1, -1):
        c = text[k]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                opener = k
                break
            depth -= 1
    if opener < 0:
        return text[:i] + text[i + len(needle):]
    depth = 0
    for k in range(opener, len(text)):
        c = text[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[:opener] + text[k + 1:]
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("output_dir", type=Path)
    args = ap.parse_args()

    lines = args.input.read_text(encoding="utf-8").splitlines(keepends=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    frontmatter_idx = mainmatter_idx = backmatter_idx = None
    chapter_indices: list[int] = []
    chapter_re = re.compile(r"^\\chapter\*?(?:\[|\{)")
    for i, line in enumerate(lines):
        s = line.lstrip()
        if s.startswith(r"\frontmatter"):
            frontmatter_idx = i
        elif s.startswith(r"\mainmatter"):
            mainmatter_idx = i
        elif s.startswith(r"\backmatter"):
            backmatter_idx = i
        elif chapter_re.match(s):
            chapter_indices.append(i)

    if frontmatter_idx is None:
        raise SystemExit("could not locate \\frontmatter")
    if mainmatter_idx is None:
        raise SystemExit("could not locate \\mainmatter")
    if backmatter_idx is None:
        backmatter_idx = len(lines)

    # --- front matter: between \frontmatter and \mainmatter; drop the source's
    #     own \maketitle and \tableofcontents (main.tex provides both) ---
    front_text = "".join(lines[frontmatter_idx + 1 : mainmatter_idx])
    front_text = _remove_group_containing(front_text, r"\tableofcontents")
    front_text = re.sub(r"\\maketitle(?![a-zA-Z])", "", front_text)
    _write(args.output_dir / "front-matter.tex", front_text)

    # --- chapters: only \chapter between \mainmatter and \backmatter ---
    chapter_starts = [i for i in chapter_indices if mainmatter_idx < i < backmatter_idx]
    boundaries = chapter_starts + [backmatter_idx]
    if len(chapter_starts) != EXPECTED_CHAPTERS:
        print(
            f"warning: expected {EXPECTED_CHAPTERS} chapters, found {len(chapter_starts)}",
            file=sys.stderr,
        )
    for n, start in enumerate(chapter_starts):
        end = boundaries[n + 1]
        _write(args.output_dir / f"chapter-{n + 1:02d}.tex", "".join(lines[start:end]))

    # --- back matter: after \backmatter to EOF, minus \end{document} ---
    back_lines = [
        ln for ln in lines[backmatter_idx + 1 :]
        if not ln.lstrip().startswith(r"\end{document}")
    ]
    _write(args.output_dir / "back-matter.tex", "".join(back_lines))

    print(f"front-matter.tex: {front_text.count(chr(10))} lines")
    for n, start in enumerate(chapter_starts):
        end = boundaries[n + 1]
        print(f"chapter-{n + 1:02d}.tex: {end - start} lines (from source line {start + 1})")
    print(f"back-matter.tex: {len(back_lines)} lines")
    return 0


def _write(path: Path, text: str) -> None:
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
