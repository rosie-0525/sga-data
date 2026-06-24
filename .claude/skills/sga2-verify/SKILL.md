---
name: sga2-verify
description: Verify the normalized SGA2 tree — grep for leftover macros, count \chapter headers, compile with pdflatex. Sixth (final) step of the normalization pipeline.
---

# sga2-verify

## When to use
Final step of the SGA2 normalization pipeline, after `sga2-build-main`. Confirms the output is well-formed.

## How to run
```
bash .claude/skills/sga2-verify/verify.sh
```

## Checks
1. **No leftover editorial macros** — `\sisi`, `\pageoriginale`, `\nde`, `\ndetext`, `\sfootnote`, `\Footnotemark`, `\Footnotetext`, `\alttitle`, `\altabstract`, `\altkeywords`, `\subjclass`, `\keywords`, `\makeschapterhead` must not appear in any chapter or front/back-matter file (they may appear in `sga2-macros.sty` as fallback definitions).
2. **One header per chapter file** — `chapter-NN.tex` files each contain exactly one `\chapter` or `\chapter*`.
3. **pdflatex compiles** — two passes, exit 0.
