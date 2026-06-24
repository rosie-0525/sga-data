# SGA 2 — LaTeX normalization & HTML conversion

A reproducible pipeline that takes the original 1968 LaTeX source of

> **Cohomologie locale des faisceaux cohérents et théorèmes de Lefschetz
> locaux et globaux (SGA 2)** — Séminaire de Géométrie Algébrique du
> Bois-Marie 1962, by A. Grothendieck *et al.*

and turns it into (1) clean, modern, self-contained LaTeX and (2) HTML that
renders correctly in the browser through MathJax 3 + XyJax-v3 (including the
xy-pic commutative diagrams).

The original source uses Windows-1252 encoding and a large stack of
publisher-specific SMF macros (`smfbook.cls`, `sga2-smf.sty`, …). Those don't
survive a plain conversion to HTML — macros leak as raw `\commands`, math
breaks, cross-references render as `???`. This repo normalizes the source
*first*, in LaTeX, so that both `pdflatex` and the HTML converter consume the
same clean tree.

## Repository layout

| Path | What it is |
|---|---|
| `00-original_tex/` | The original SMF source (read-only input). Master file: `smf_doc-math_4_01.tex`, Windows-1252. |
| `01-normalized_tex/` | The normalized modern LaTeX tree — `main.tex`, `sga2-macros.sty`, and one `chapter-NN.tex` per exposé, plus `front-matter.tex` / `back-matter.tex`. Compiles with stock `pdflatex`. |
| `02-converted_html/` | The HTML deliverable, produced by the HTML converter. |
| `03-converted_html_orig/` + `comparison.html` | A rough baseline: raw conversion of the *original* source (macros leak, for before/after comparison). |
| `issues/` | Verification reports — `mathjax_errors.json` (full structured result) and `mathjax_errors.md` (categorised summary + fixes). |
| `.claude/skills/` | The pipeline, implemented as scripts (see below). |

## Pipeline

```
00-original_tex/  ──normalize──▶  01-normalized_tex/  ──convert──▶  02-converted_html/  ──check──▶  issues/
```

### 1. Normalize (`00-original_tex/` → `01-normalized_tex/`)

Six steps, runnable end-to-end via the `sga2-normalize` skill or individually
(see `.claude/skills/sga2-normalize/SKILL.md`):

1. **prepare-source** — convert the Windows-1252 master to UTF-8.
2. **resolve-sisi** — pick a side of every `\sisi{original}{corrected}`.
3. **inline-macros** — inline SGA2-specific macros to plain LaTeX and strip
   editorial/presentation commands.
4. **split-chapters** — split the monolith at `\chapter` boundaries.
5. **build-main** — emit `main.tex` and the curated `sga2-macros.sty`.
6. **verify** — grep for leftover macros, check chapter counts, compile with
   `pdflatex`.

### 2. Convert (`01-normalized_tex/` → `02-converted_html/`)

```sh
bash .claude/skills/sga2-convert-html/convert.sh
```

A custom minimal LaTeX→JSON/HTML parser (`sga2-convert-html`). It emits a JSON
manifest (`fr.json`) plus per-chapter content (`fr/chapters/<id>.json`) and a
self-contained viewer (`index.html` + MathJax 3 + XyJax-v3), keeping math as
`\(...\)` / `\[...\]` for client-side rendering. Numbering and cross-references
(chapter/section/theorem/equation numbers, `\ref`/`\eqref`/`\cite`) are resolved
authoritatively from `main.aux`; the ~120 content macros from `sga2-macros.sty`
are expanded to plain LaTeX (no `tex.macros` in the HTML head). English chapter
files are empty stubs — French is the populated reference. See
`.claude/skills/sga2-convert-html/SKILL.md`. Preview with
`cd 02-converted_html && python3 -m http.server`.

### 3. Check (`02-converted_html/` → `issues/`)

```sh
bash .claude/skills/sga2-check-mathjax/check.sh
```

Loads the viewer in headless Chromium and renders every page through the
deliverable's own MathJax 3 + XyJax-v3 setup, letting typesetting (incl.
xymatrix) run to completion, then reports `mjx-merror`s, leaked `\command`
tokens, unresolved cross-references (`???`), and internal links that resolve to
nothing. Defaults to both `fr` and `en` (pass e.g. `fr` to limit). Results →
`issues/mathjax_errors.json`.

## Requirements

- **python3** — normalization scripts and HTML conversion.
- **pdflatex** (a TeX distribution) — `sga2-verify` compile check.
- **node** + **npm** — `sga2-check-mathjax` (auto-installs Puppeteer/Chromium on first run).

## Design principle

Fixes for MathJax rendering problems belong **upstream in the LaTeX
normalization step** (`sga2-inline-macros`), not in HTML post-processing — no
`tex.macros` injected into the HTML head, no edits to `sga2-macros.sty` for
downstream-only issues. This keeps every fix durable across pipeline re-runs.
