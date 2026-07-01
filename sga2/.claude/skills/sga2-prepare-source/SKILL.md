---
name: sga2-prepare-source
description: Convert the SGA2 monolithic source file from Windows-1252 (ansinew) to UTF-8 and write it to the staging area. First step of the normalization pipeline.
---

# sga2-prepare-source

## When to use
First step of the SGA2 normalization pipeline. Run this before any downstream transformation skill (`sga2-resolve-sisi`, `sga2-inline-macros`, etc.).

## How to run
```
python3 .claude/skills/sga2-prepare-source/prepare_source.py
```

Reads `00-original_tex/smf_doc-math_4_01.tex` (cp1252) and writes
`01-normalized_tex/.staging/00-utf8.tex` (utf-8). No content changes.
