# SGA — bilingual (FR/EN) corpus & review viewer

Grothendieck's *Séminaire de Géométrie Algébrique du Bois-Marie* (SGA 1–7),
published as **structured JSON with embedded HTML** — a manifest plus one JSON
per exposé, per language — and served through a shared, lightweight **viewer**
that renders French and English side by side with math typeset in-browser.
Reviewers read the rendered text, select any passage, and attach a comment
(a translation error, a transcription slip, a rendering glitch).

The build pipeline that produced this data — LaTeX normalization for SGA 1–2,
PDF transcription plus machine translation for SGA 3–7 — has been removed from
the working tree; it remains in git history through commit `a2317a4`. Work now
happens **directly on the JSON**, checked against each volume's source PDF (or
original LaTeX).

## Repository layout

| Path | What it is |
|---|---|
| `index.html` | Landing page listing every volume, linking to its `paper.html`. |
| `sga1/`, `sga2/`, … | One self-contained directory per volume (see below). |
| `translation-viewer/` | Git submodule — the generic bilingual/aligned-column viewer engine shared by every volume: MathJax 3 SVG + XyJax-v3 (vendored, fully offline) for rendering, plus the in-page comment/error-flagging tool. |
| `glossary/` | `glossary.json` is the FR→EN terminology source of truth; `GLOSSARY.md` is generated from it; `candidates/` holds the extraction inputs. |
| `scripts/` | Corpus-wide tooling: glossary extraction/conformance/rendering, `add_alias_author.py`. |
| `issues/` | Aggregated verification reports for all volumes (see *Check*). |
| `.claude/skills/sga-check-errors/` | The render-check skill (headless Chromium + the deliverable's own MathJax setup). |
| `ERRATA.md` | Anomalies printed in the source editions themselves, with the policy applied to each. |

Inside each volume directory:

| Path | What it is |
|---|---|
| `source/` | The reference the volume is checked against: the original SMF LaTeX source (sga1, sga2) or the source PDFs (sga3–sga7). sga4.5 keeps its source in the `sga4.5/sga4.5/` submodule instead. |
| `data/` | The deliverable's data: `config.json`, `{fr,en}/manifest.json` and `{fr,en}/chapters/<id>.json`. |
| `paper.html` | The entry page, rendered by `translation-viewer`. |

Volume-specific extras: `sga3/source/chapter-map.json` maps each source PDF to
its exposé; `sga4.5/sga4.5/` is a submodule holding that volume's LaTeX source
(`git submodule update --init --recursive` to populate it). Printed-edition
anomalies for every volume are recorded centrally in `ERRATA.md`; the per-book
correction logs that preceded it (`sga3/issues/ocr_corrections/`,
`sga6/typos.md`) were verified applied and removed on 2026-07-27 — they remain
in git history through `a2317a4`.

## Working on the text

Edit the JSON under each volume's `data/` directly. French is the
populated reference; English chapters are aligned to French **1:1 by block
index**, so a block added or removed on one side must be mirrored on the other.
Pages also carry an `html` field that is the concatenation of their block
`html`s — rebuild it as `"\n".join(block htmls)` after editing any block.
(A handful of pages predate that invariant, so don't assume it holds
everywhere before you edit; do restore it on pages you touch.)

Math stays as `\(...\)` / `\[...\]` for client-side rendering — never
pre-render it, and don't inject `tex.macros` into the HTML head.

Preview with `python3 -m http.server` from the repo root (so `paper.html`'s
`../translation-viewer/...` references resolve), then open
`http://localhost:8000/sgaN/paper.html`, or
`http://localhost:8000/index.html` to browse all volumes.

The data format (manifest + per-chapter JSON with embedded HTML) is
document-agnostic and specified, with machine-validatable JSON Schemas, in
`translation-viewer/docs/`.

## Check (each volume → repo-root `issues/`)

```sh
bash .claude/skills/sga-check-errors/check.sh        # every volume
bash .claude/skills/sga-check-errors/check.sh sgaN   # one volume
```

Loads `paper.html` in headless Chromium and renders every page through the
deliverable's own MathJax 3 + XyJax-v3 setup, letting typesetting (incl.
xymatrix) run to completion, then reports `mjx-merror`s, leaked `\command`
tokens, unresolved cross-references (`???`), internal links that resolve to
nothing, and content blocks whose HTML isn't a single root element (which the
viewer would silently truncate). Results for **all volumes** are aggregated
into the repo-root `issues/mathjax_errors.json`, `issues/crossref_errors.json`
and `issues/other_errors.json` (every record carries its `book`; rerunning one
volume replaces only that volume's records), with per-volume run metadata and
totals in `issues/summary.json`.

Note that some defects render cleanly and so survive this sweep — e.g. a
missing backslash in `\(mathcal O_X\)` prints the literal word. Grep for
`\(math[cbsf]`, `\(operatorname`, `\(leq` to catch that class.

## Glossary

```sh
python3 scripts/glossary_check.py                    # every volume
python3 scripts/glossary_check.py --book sgaN        # one volume
```

`glossary/glossary.json` is the FR→EN source of truth for terminology.
`glossary_check.py` reports deviations into `issues/glossary_deviations.json`
and `issues/glossary_summary.json`; `glossary_md.py` regenerates
`glossary/GLOSSARY.md`. Prefer widening a term's accepted English variants in
`glossary.json` over rewriting settled translations.

## Review workflow (the viewer)

`translation-viewer` renders each volume's `paper.html` as a two-column,
block-aligned page (source language / translation) with math typeset
in-browser. A reviewer selects any passage — French or English, prose or math —
and attaches a comment through the in-page panel (`comments.js`). Comments are
kept in the browser's `localStorage`, anchored to their block, and can be
reviewed, jumped to, or exported as a `comments.json` file at any time. That
exported file is a plain list of block-anchored comments, meant to be handed to
an agent that reads it and applies the corresponding fixes to the JSON data.
`comments.json` itself is a local working file, not checked into the repo.

## Requirements

- **python3** — glossary and corpus tooling.
- **node** + **npm** — the check step (auto-installs Puppeteer/Chromium on first run).
- **git submodules checked out** — `translation-viewer/` (`git submodule update --init --recursive`), required by the check step and by the viewer itself.
