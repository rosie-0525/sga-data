---
name: sga1-inline-macros
description: Strip SGA1 editorial/presentation commands (page markers, no-op index markers) and apply MathJax-portability rewrites to plain LaTeX. Content math macros are left intact (defined in sga1-macros.sty / convert.py). Third step of the normalization pipeline.
---

# sga1-inline-macros

## When to use
Third step of the SGA1 normalization pipeline, after [[sga1-resolve-orig]]. Drops editorial apparatus and rewrites the few constructs MathJax/XyJax can't host. It deliberately does **not** expand content math macros (`\Hom`, `\Pic`, `\SheafHom`, …) — those stay as-is and are defined in `sga1-macros.sty` ([[sga1-build-main]]) for pdflatex and in convert.py's macro tables ([[sga1-convert-html]]) for HTML.

## How to run
```
python3 .claude/skills/sga1-inline-macros/inline_macros.py \
    01-normalized_tex/.staging/01-orig.tex \
    01-normalized_tex/.staging/02-inlined.tex
```

## Transformations applied (in order)
| Macro / construct | Action |
|---|---|
| `\marginpar{NNN}` | removed (439 original-page-number margin notes) |
| `\oldindexnot{...}` | removed (disabled notation-index marker; `\def\oldindexnot#1{}`) |
| `\begin{altabstract}…\end{altabstract}` | block removed |
| `\begin{abstract}…\end{abstract}` | → `\begin{quote}\textbf{Résumé.} …\end{quote}` |
| `\alttitle`, `\altkeywords`, `\subjclass`, `\keywords`, `\title`, `\author`, `\date` | removed (main.tex provides its own metadata) |
| `\makeschapterhead{T}` | → `\chapter*{T}` (Préface / Introduction / Avertissement) |
| `\sfootnote{...}` | → `\footnote{...}` |
| `\Ref{x}` | → `\ref{x}` (SGA1 cross-refs all use `\Ref`; drops the `\textup` wrapper) |
| `\ptbl` | → `.\,` |
| `\smaller` / `\larger` | → `\small` / `\large` |
| `\stepcounter{...}` | removed |
| `\kern<dim>` / `\mkern<dim>` (text) | removed (cosmetic `\kern1pt\footnote` spacers; HTML would leak the dimension) |
| `\protect`, `\nobreak` | removed (leak into HTML math) |
| Inside `\xymatrix{...}` bodies | `\operatorname`-class macros → plain forms: `\Hom`→`\mathrm{Hom}`, `\SheafHom`→`\mathbf{Hom}`, also `\SheafAut`,`\SheafIsom`,`\Ouv`,`\Quot`,`\Fer`,`\Ext` — XyJax-v3 can't host `\operatorname` in diagram cells |
| `\leqno{...}` | → `\tag*{...}` (and `$$…\leqno(..)$$` → `equation*`) |
| Text-accent macros (`\'e`, `` \`u ``, `\^{o}`, …) inside `\text`/`\textXX`/`\emph`/`\hbox`/`\mbox`/`\tag*` args | → precomposed Unicode (é, ù, ô) so MathJax renders one correctly-placed glyph |
| Corpus-specific `\xymatrix` patches | applied last (catalogue in [[sga1-normalize-xymatrix]]; starts empty, grows as [[sga1-check-errors]] surfaces XyJax failures) |

## Notes
- The `l → ℓ` (ell) `\mathcode` trick from `sga1-smf.sty` is **not** applied
  here. pdflatex via `sga1-macros.sty` may reinstate it; in HTML a bare math `l`
  currently renders as `l`, not `ℓ` — a known fidelity gap to revisit.
