---
name: sga2-split-chapters
description: Split the post-transformation monolithic SGA2 source at \chapter boundaries into front-matter.tex, chapter-NN.tex per exposé, and back-matter.tex. Fourth step of the normalization pipeline.
---

# sga2-split-chapters

## When to use
Fourth step of the SGA2 normalization pipeline, after `sga2-inline-macros`. Slices the single file into one file per exposé.

## How to run
```
python3 .claude/skills/sga2-split-chapters/split_chapters.py \
    01-normalized_tex/.staging/02-inlined.tex \
    01-normalized_tex/
```

## Output
- `front-matter.tex` — between `\frontmatter` and `\mainmatter`, excluding `\maketitle`/`\tableofcontents` (`main.tex` owns those).
- `chapter-00.tex` — the `\chapter*{Introduction}` block.
- `chapter-01.tex` ... `chapter-14.tex` — one per exposé.
- `back-matter.tex` — `\thebibliography` through end of file (includes the two `\chapter*` index entries).

Re-grepped chapter boundaries at runtime; not hardcoded to line numbers.
