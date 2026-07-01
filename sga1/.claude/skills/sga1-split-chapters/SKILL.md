---
name: sga1-split-chapters
description: Split the post-transformation SGA1 source at \chapter boundaries into front-matter.tex, chapter-01..12.tex per exposé, and back-matter.tex. Per-chapter bibliographies stay inside their exposé. Fourth step of the normalization pipeline.
---

# sga1-split-chapters

## When to use
Fourth step of the SGA1 normalization pipeline, after [[sga1-inline-macros]]. Slices the single file into one file per exposé.

## How to run
```
python3 .claude/skills/sga1-split-chapters/split_chapters.py \
    01-normalized_tex/.staging/02-inlined.tex \
    01-normalized_tex/
```

## Output
- `front-matter.tex` — between `\frontmatter` and `\mainmatter`, with the source's own `\maketitle` and the `{…\tableofcontents}` group removed (main.tex owns those). Holds Préface / Introduction / Avertissement (`\chapter*`).
- `chapter-01.tex … chapter-12.tex` — one per exposé, in order. Exposé numbering is I–VI then **VIII–XIII**; chapter-07.tex is exposé **VIII** (VII does not exist in SGA1). The real roman numeral for each file comes from its in-source `\label{<roman>}` and drives the HTML ids in [[sga1-convert-html]].
- `back-matter.tex` — after `\backmatter` to EOF, minus `\end{document}`. Holds `\printindex` (terminological index) and the manual `theindex` notation index.

## SGA1-specific structure
- **Per-chapter bibliographies**: each exposé ends with its own `\thebibliography`; these stay *inside* the chapter files (SGA2 had one global bibliography that became the chapter/back-matter boundary — SGA1's boundary is `\backmatter`).
- **Exposé VII gap**: a `\refstepcounter{chapter}` + a "VII: n'existe pas" toc note sit between VI and VIII; they land at the tail of `chapter-06.tex`, so pdflatex's chapter counter advances 6 → (phantom 7) → 8 = VIII.
- The runtime guard expects **12** chapters.

Re-grepped chapter boundaries at runtime; not hardcoded to line numbers.
