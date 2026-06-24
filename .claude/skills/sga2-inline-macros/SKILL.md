---
name: sga2-inline-macros
description: Inline SGA2-specific custom macros to plain LaTeX and strip editorial/presentation commands. Third step of the normalization pipeline.
---

# sga2-inline-macros

## When to use
Third step of the SGA2 normalization pipeline, after `sga2-resolve-sisi`. Replaces custom semantic macros with plain LaTeX equivalents and drops editorial apparatus (margin notes, editor footnotes, bilingual variants).

## How to run
```
python3 .claude/skills/sga2-inline-macros/inline_macros.py \
    01-normalized_tex/.staging/01-sisi.tex \
    01-normalized_tex/.staging/02-inlined.tex
```

## Transformations applied (in order)
| Macro | Action |
|---|---|
| `\Ref{x}` | → `\ref{x}` |
| `\ptbl` | → `.\,` |
| `\sheaf{X}` | → `\underline{X}` (sheafified functors are underlined, per original `\def\sheaf#1{\underline{#1}}`) |
| `\rest{X}` | → `|_{X}` |
| `\makeschapterhead{T}` | → `\chapter*{T}` |
| `\pageoriginale` | removed |
| `\nde{...}`, `\ndetext{...}` | removed (brace-balanced) |
| `\sfootnote{...}` | → `\footnote{...}` |
| `\Footnotemark[...]`, `\Footnotetext[...]{...}` | removed |
| `\alttitle{...}`, `\altkeywords{...}`, `\subjclass{...}`, `\keywords{...}` | removed |
| `\begin{altabstract}...\end{altabstract}` | block removed |
| Second (English) `\chapter*{Preface}` block | removed up to `\tableofcontents` |
| `\hto`, `\mfrom`, `\mlto{x}` | → `\hookrightarrow`, `\leftarrowtail`, `\overset{x}{\mapsto}` (so the staged source no longer relies on `\joinrel` / `\mapstochar`, which MathJax 3 doesn't recognize) |
| `\h`, `\SheafH`, `\SheafHom`, `\SheafExt` | → `\mathop{\underline{\mathrm{H}}}\nolimits`, `\mathop{\underline{\mathrm{Hom}}}\nolimits`, `\mathop{\underline{\mathrm{Ext}}}\nolimits` (originals expand via `\DeclareMathOperator` to `\operatorname{\underline{...}}`, which XyJax-v3 cannot reparse inside `\xymatrix` cells; the `\mathop{...}\nolimits` form is identical at pdflatex output) |
| Inside `\xymatrix{...}` bodies only | `\mathop{\underline{\mathrm{X}}}\nolimits` → `\underline{\mathrm{X}}`; `\R` → `\mathrm{R}` (XyJax-v3 inside diagram cells parses only plain math primitives — no `\mathop`/`\nolimits`/`\operatorname`; outside xymatrix the originals stay so operator-class spacing is preserved everywhere else) |
| `\stepcounter{...}` | removed (brace-balanced) — would otherwise be passed through into displaymath where MathJax renders it as literal text |
| `\et` | → `{\textup{ét}}` (precomposed é). The `.sty` defines `\et` as `{\textup{\'et}}`; the HTML converter expands it inside math (`X_{\et}`, `\prof \et(X)`), where MathJax's textmacros renders `\'e` as a detached floating acute. Byte-identical upright "ét" under pdflatex |
| Text-accent macros (`\'e`, `` \`u ``, `\^{o}`, …) inside `\text`/`\textXX`/`\emph`/`\hbox`/`\mbox`/`\tag*` arguments | → precomposed Unicode (é, ù, ô, …). MathJax's textmacros mis-renders `` \` `` inside `\text{}` as a floating U+2035 glyph with a literal backtick leaking into the a11y text; precomposed Unicode is one correctly-placed glyph. Output-identical under pdflatex (utf8) and the HTML converter, which already converts these accents in running text — so the breakage was confined to accents inside math-mode text containers |
