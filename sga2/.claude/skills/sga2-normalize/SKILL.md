---
name: sga2-normalize
description: Run the full SGA2 normalization pipeline end-to-end — encoding, \sisi resolution, macro inlining, chapter splitting, main.tex generation, verification. Use this for the standard case; individual step skills exist for re-running a single stage during debugging.
---

# sga2-normalize

## When to use
End-to-end normalization of `00-original_tex/` into `01-normalized_tex/`. Invoke as `/sga2-normalize`. If only a single step needs to re-run (e.g., after editing macro rules), invoke that step's individual skill instead.

## Pipeline
1. **sga2-prepare-source** — convert Windows-1252 source to UTF-8.
2. **sga2-resolve-sisi** — pick the original side of every `\sisi{A}{B}`.
3. **sga2-inline-macros** — inline `\Ref`, `\sheaf`, `\rest`, `\ptbl`, `\makeschapterhead`; strip `\pageoriginale`, `\nde`, `\ndetext`, `\Footnote*`, `\alt*`/`\subjclass`/`\keywords`, English preface.
4. **sga2-split-chapters** — split into `front-matter.tex`, `chapter-00.tex` … `chapter-14.tex`, `back-matter.tex`.
5. **sga2-build-main** — emit `main.tex` (preamble + `\input` lines) and `sga2-macros.sty` (curated math/French macros).
6. **sga2-verify** — grep for leftover macros, count chapter headers, compile with pdflatex.

## How to run
Execute these commands in order from the repo root:

```
python3 .claude/skills/sga2-prepare-source/prepare_source.py
python3 .claude/skills/sga2-resolve-sisi/resolve_sisi.py \
    01-normalized_tex/.staging/00-utf8.tex \
    01-normalized_tex/.staging/01-sisi.tex \
    --side original
python3 .claude/skills/sga2-inline-macros/inline_macros.py \
    01-normalized_tex/.staging/01-sisi.tex \
    01-normalized_tex/.staging/02-inlined.tex
python3 .claude/skills/sga2-split-chapters/split_chapters.py \
    01-normalized_tex/.staging/02-inlined.tex \
    01-normalized_tex/
python3 .claude/skills/sga2-build-main/build_main.py 01-normalized_tex/
bash .claude/skills/sga2-verify/verify.sh
```

Fail-fast: stop and report at the first non-zero exit. Intermediate staging files live in `01-normalized_tex/.staging/` and can be inspected on failure.
