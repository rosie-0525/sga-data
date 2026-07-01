---
name: sga1-normalize
description: Run the full SGA1 normalization pipeline end-to-end — staging, orig-conditional resolution, macro inlining, chapter splitting, main.tex generation, verification. Use this for the standard case; individual step skills exist for re-running a single stage during debugging.
---

# sga1-normalize

## When to use
End-to-end normalization of `00-original_tex/` into `01-normalized_tex/`. Invoke as `/sga1-normalize`. If only a single step needs to re-run (e.g., after editing macro rules), invoke that step's individual skill instead.

## Pipeline
1. **[[sga1-prepare-source]]** — stage the ASCII body file `smf_doc-math_3_01.tex` as UTF-8.
2. **[[sga1-resolve-orig]]** — pick the corrected branch of every `\ifthenelse{\boolean{orig}}{…}{…}`.
3. **[[sga1-inline-macros]]** — strip `\marginpar`, `\oldindexnot`, `\kern`; map `\Ref`→`\ref`, `\makeschapterhead`→`\chapter*`, `\Subsection`→`\subsection`; MathJax-portability rewrites (`\leqno`, text accents, xymatrix-safe operators).
4. **[[sga1-split-chapters]]** — split into `front-matter.tex`, `chapter-01.tex … chapter-12.tex` (exposés I–VI, VIII–XIII), `back-matter.tex`; per-chapter bibliographies stay inside their exposé.
5. **[[sga1-build-main]]** — emit `main.tex` (preamble + `\input` lines) and `sga1-macros.sty` (curated math/French macros, corrected-edition conditional macros, two-arg `thebibliography`).
6. **[[sga1-verify]]** — grep for leftover macros, count chapter headers (12), compile cleanly with pdflatex + makeindex.

## How to run
Execute these commands in order from the repo root:

```
python3 .claude/skills/sga1-prepare-source/prepare_source.py
python3 .claude/skills/sga1-resolve-orig/resolve_orig.py \
    01-normalized_tex/.staging/00-ascii.tex \
    01-normalized_tex/.staging/01-orig.tex \
    --side corrected
python3 .claude/skills/sga1-inline-macros/inline_macros.py \
    01-normalized_tex/.staging/01-orig.tex \
    01-normalized_tex/.staging/02-inlined.tex
python3 .claude/skills/sga1-split-chapters/split_chapters.py \
    01-normalized_tex/.staging/02-inlined.tex \
    01-normalized_tex/
python3 .claude/skills/sga1-build-main/build_main.py 01-normalized_tex/
bash .claude/skills/sga1-verify/verify.sh
```

Fail-fast: stop and report at the first non-zero exit. Intermediate staging files live in `01-normalized_tex/.staging/` and can be inspected on failure.
