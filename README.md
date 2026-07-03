# SGA — LaTeX normalization, HTML conversion & review viewer

This repo turns the raw LaTeX source of Grothendieck's *Séminaire de
Géométrie Algébrique du Bois-Marie* (SGA) into clean, structured **JSON
files with embedded HTML content** — one JSON manifest + per-chapter JSON
per volume — and serves them through a shared, lightweight **viewer**.
Reviewers use the viewer to read the rendered text/math, select any passage,
and attach a comment (e.g. a translation error or a rendering glitch). The
viewer exports all of a reviewer's comments as a `comments.json` file, which
is then handed back to an agent that reads it and makes the corresponding
fixes in the pipeline.

Each volume (SGA 1, SGA 2, …) is processed independently through the same
three-stage pipeline, from its own original 1968 LaTeX source (Windows-1252
or ASCII, publisher-specific SMF macros) to a modern, self-contained LaTeX
tree, to the final JSON/HTML deliverable. The original sources don't survive
a plain conversion to HTML — macros leak as raw `\commands`, math breaks,
cross-references render as `???`. Each volume's pipeline normalizes the
source *first*, in LaTeX, so that both `pdflatex` and the HTML converter
consume the same clean tree.

## Repository layout

| Path | What it is |
|---|---|
| `index.html` | Landing page listing every volume, linking to its `paper.html`. |
| `sga1/`, `sga2/`, … | One self-contained directory per volume (see below). Additional volumes are added the same way. |
| `translation-viewer/` | Git submodule — the generic bilingual/aligned-column viewer engine shared by every volume: MathJax 3 SVG + XyJax-v3 (vendored, fully offline) for rendering, plus the in-page comment/error-flagging tool. |

Inside each volume directory (e.g. `sga2/`):

| Path | What it is |
|---|---|
| `00-original_tex/` | The original SMF source (read-only input), e.g. `smf_doc-math_4_01.tex`. |
| `01-normalized_tex/` | The normalized modern LaTeX tree — `main.tex`, a curated macros `.sty`, and one `chapter-NN.tex` per exposé. Compiles with stock `pdflatex`. |
| `02-converted_html/` | The deliverable: `data/` (the JSON manifest + per-chapter JSON with embedded HTML) and `paper.html`, the entry page rendered by `translation-viewer`. |
| `issues/` | Verification reports from the check step, categorised into `mathjax_errors.json`, `crossref_errors.json`, and `other_errors.json`. |
| `.claude/skills/` | The volume's pipeline, implemented as `sgaN-*` skills (normalize steps, convert, check — see below). |

## Pipeline (per volume)

```
00-original_tex/  ──normalize──▶  01-normalized_tex/  ──convert──▶  02-converted_html/  ──check──▶  issues/
```

### 1. Normalize

Runnable end-to-end via each volume's `sgaN-normalize` skill, or step by
step (prepare-source, resolve macro variants, inline SGA-specific macros,
split at `\chapter` boundaries, build `main.tex`, verify) — see
`sgaN/.claude/skills/sgaN-normalize/SKILL.md` for the exact steps, which
vary slightly per volume depending on its source encoding and macro set.

### 2. Convert (`01-normalized_tex/` → `02-converted_html/`)

```sh
bash sgaN/.claude/skills/sgaN-convert-html/convert.sh
```

A custom minimal LaTeX→JSON/HTML parser. It emits a JSON manifest
(`data/fr/manifest.json`) plus per-chapter content
(`data/fr/chapters/<id>.json`) and a `paper.html` entry page for the shared
`translation-viewer`, keeping math as `\(...\)` / `\[...\]` for client-side
rendering. Numbering and cross-references are resolved authoritatively from
`main.aux`; content macros are expanded to plain LaTeX (no `tex.macros` in
the HTML head). English chapter files are empty stubs until translated —
French is the populated reference.

Preview with `python3 -m http.server` from the repo root (so `paper.html`'s
`../translation-viewer/...` references resolve), then open
`http://localhost:8000/sgaN/02-converted_html/paper.html`, or open
`http://localhost:8000/index.html` to browse all volumes.

The output format (manifest + per-chapter JSON with embedded HTML) is
document-agnostic and specified, with machine-validatable JSON Schemas, in
`translation-viewer/docs/`.

### 3. Check (`02-converted_html/` → `issues/`)

```sh
bash sgaN/.claude/skills/sgaN-check-errors/check.sh
```

Loads `paper.html` in headless Chromium and renders every page through the
deliverable's own MathJax 3 + XyJax-v3 setup, letting typesetting (incl.
xymatrix) run to completion, then reports `mjx-merror`s, leaked `\command`
tokens, unresolved cross-references (`???`), internal links that resolve to
nothing, and content blocks whose HTML isn't a single root element (which
the viewer would silently truncate). Results are categorised into
`issues/mathjax_errors.json`, `issues/crossref_errors.json`, and
`issues/other_errors.json`.

## Review workflow (the viewer)

`translation-viewer` renders each volume's `paper.html` as a two-column,
block-aligned page (source language / translation) with math typeset
in-browser. A reviewer selects any passage — French or English, prose or
math — and attaches a comment through the in-page panel (`comments.js`).
Comments are kept in the browser's `localStorage`, anchored to their block,
and can be reviewed, jumped to, or exported as a `comments.json` file at any
time. That exported file is a plain list of block-anchored comments and is
meant to be handed to an agent, which reads it and applies the corresponding
fixes upstream in the pipeline (LaTeX normalization or the converter, per
the design principle below) — `comments.json` itself is a local working
file, not checked into the repo.

## Requirements

- **python3** — normalization scripts and HTML conversion.
- **pdflatex** (a TeX distribution) — the verify step's compile check.
- **node** + **npm** — the check-errors step (auto-installs Puppeteer/Chromium on first run).
- **git submodules checked out** — `translation-viewer/` (`git submodule update --init --recursive`), required by both the convert and check steps, and by the viewer itself.

## Design principle

Fixes for MathJax rendering problems (and for issues surfaced via reviewer
comments) belong **upstream in the LaTeX normalization step**
(`sgaN-inline-macros`), not in HTML post-processing — no `tex.macros`
injected into the HTML head, no volume-specific hacks in the shared
`translation-viewer`. This keeps every fix durable across pipeline re-runs.
