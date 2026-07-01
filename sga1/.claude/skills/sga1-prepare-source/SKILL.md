---
name: sga1-prepare-source
description: Stage the SGA1 body source (smf_doc-math_3_01.tex) as UTF-8. The source is plain ASCII (LaTeX-style accents), so this is a re-encode/copy, not a Windows-1252 conversion. First step of the normalization pipeline.
---

# sga1-prepare-source

## When to use
First step of the SGA1 normalization pipeline. Run this before any downstream transformation skill ([[sga1-resolve-orig]], [[sga1-inline-macros]], etc.).

## How to run
```
python3 .claude/skills/sga1-prepare-source/prepare_source.py
```

Reads `00-original_tex/smf_doc-math_3_01.tex` (ASCII) and writes
`01-normalized_tex/.staging/00-ascii.tex` (UTF-8). No content changes.

## Notes
- The real text lives in `smf_doc-math_3_01.tex`; `sga1-smf.tex` is only a
  thin master that sets `\setboolean{orig}{false}` and `\input`s the body. The
  pipeline builds its own preamble in [[sga1-build-main]], so we stage the body
  file directly.
- Unlike SGA2 (Windows-1252 / ansinew), SGA1 is ASCII with accents as control
  sequences (`\'e`, `{\^e}`), converted to Unicode later by [[sga1-inline-macros]].
