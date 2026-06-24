---
name: sga2-resolve-sisi
description: Resolve every \sisi{A}{B} in the staged SGA2 source to either the original (A) or corrected (B) side, brace-balanced. Second step of the normalization pipeline.
---

# sga2-resolve-sisi

## When to use
Second step of the SGA2 normalization pipeline, after `sga2-prepare-source`. Drops the dual-edition machinery by picking one side of every `\sisi{A}{B}`.

## How to run
```
python3 .claude/skills/sga2-resolve-sisi/resolve_sisi.py \
    01-normalized_tex/.staging/00-utf8.tex \
    01-normalized_tex/.staging/01-sisi.tex \
    --side original
```

Use `--side original` for the 1962 first-edition text (project default) or
`--side corrected` for the 2007 SMF annotated version.

Handles nested braces, nested `\sisi` calls, and the edge cases
`\sisi{}{B}` (drops to empty when side=original) and `\sisi{A}{}` (drops to
empty when side=corrected).
