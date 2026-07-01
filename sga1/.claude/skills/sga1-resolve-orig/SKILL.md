---
name: sga1-resolve-orig
description: Resolve every \ifthenelse{\boolean{orig}}{ORIG}{CORR} in the staged SGA1 source to one branch (default corrected), brace-balanced. SGA1's dual-edition equivalent of SGA2's \sisi. Second step of the normalization pipeline.
---

# sga1-resolve-orig

## When to use
Second step of the SGA1 normalization pipeline, after [[sga1-prepare-source]]. Drops the dual-edition machinery by picking one branch of every `\ifthenelse{\boolean{orig}}{...}{...}`.

SGA1 has no `\sisi` macro (that was SGA2). Instead a boolean flag `orig` selects the edition; the master `sga1-smf.tex` sets `\setboolean{orig}{false}`, choosing the **corrected** (SMF-published) text. ~490 such conditionals appear in the body.

## How to run
```
python3 .claude/skills/sga1-resolve-orig/resolve_orig.py \
    01-normalized_tex/.staging/00-ascii.tex \
    01-normalized_tex/.staging/01-orig.tex \
    --side corrected
```

Use `--side corrected` (default) for the SMF annotated edition, or
`--side original` for the 1971 first-edition text.

## Notes
- Only `\ifthenelse` whose condition is exactly `\boolean{orig}` is resolved;
  any other `\ifthenelse` (e.g. `\equal{}{}` page tests) is left intact, with
  its arguments still scanned for nested orig-conditionals.
- Handles nested braces, nested orig-conditionals, and empty branches
  (`\ifthenelse{\boolean{orig}}{}{CORR}` → `CORR`).
- The orig-conditional **macros** defined in `sga1-smf.sty` (`\fets`, `\sss`,
  `\pieme`, `\nieme`/`\niemes`, `\Nieme`/`\Niemes`, and the `\Gl`/`\GL`
  operator pair) live in the style file, not the body, so they are NOT resolved
  here — their corrected forms are baked into the macro tables in
  [[sga1-build-main]] and [[sga1-convert-html]].
