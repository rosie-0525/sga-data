---
name: sga1-verify
description: Verify the normalized SGA1 tree — grep for leftover macros and unresolved orig conditionals, count \chapter headers (expect 12), compile cleanly with pdflatex + makeindex. Sixth (final) step of the normalization pipeline.
---

# sga1-verify

## When to use
Final step of the SGA1 normalization pipeline, after [[sga1-build-main]]. Confirms the output is well-formed and compiles.

## How to run
```
bash .claude/skills/sga1-verify/verify.sh
```

## Checks
1. **No leftover editorial macros** — `\marginpar`, `\oldindexnot`, `\makeschapterhead`, `\Ref`, `\ptbl`, `\sfootnote`, `\Subsection`, `\Subsubsection`, `\smaller`, `\larger`, `\pageoriginale` must not appear in any chapter or front/back-matter file (they may appear in `sga1-macros.sty` as fallback definitions). Also flags any unresolved `\boolean{orig}` conditional.
2. **One header per chapter file, 12 files** — exactly 12 `chapter-NN.tex`, each with exactly one `\chapter`/`\chapter*` (exposés I–VI, VIII–XIII).
3. **pdflatex compiles cleanly** — `pdflatex` → `makeindex main.idx` → `pdflatex` → `pdflatex`, final pass exits 0 and writes `main.pdf`.
