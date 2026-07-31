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
| `translation-viewer/` | Git submodule — the generic bilingual/aligned-column viewer engine shared by every volume: MathJax 3 SVG + XyJax-v3 (vendored, fully offline) for rendering, plus the in-page comment/error-flagging tool and the proposed-changes review UI. |
| `glossary/` | `glossary.json` is the FR→EN terminology source of truth; `GLOSSARY.md` is generated from it; `candidates/` holds the extraction inputs. |
| `scripts/` | Corpus-wide tooling: glossary extraction, conformance checking, Markdown rendering, and the proposed-changes applier. |
| `issues/` | Aggregated verification reports for all volumes (see *Check*). |
| `.claude/skills/sga-check-errors/` | The render-check skill (headless Chromium + the deliverable's own MathJax setup). |
| `ERRATA.md` | Anomalies printed in the source editions themselves, with the policy applied to each. |

Inside each volume directory:

| Path | What it is |
|---|---|
| `source/` | The reference the volume is checked against: the original SMF LaTeX source (sga1, sga2) or the source PDFs (sga3–sga7). sga4.5 keeps its source in the `sga4.5/sga4.5/` submodule instead. |
| `data/` | The deliverable's data: `config.json`, `{fr,en}/manifest.json` and `{fr,en}/chapters/<id>.json`. `proposals.json`, when present, is a run of proposed changes awaiting review. |
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
A page's rendered HTML is just the concatenation of its `blocks[].html`; there is
no page-level `html` field (it was dropped on 2026-07-29 — see
`translation-viewer/docs/chapter.schema.md` for the schema).

Math stays as `\(...\)` / `\[...\]` for client-side rendering — never
pre-render it, and don't inject `tex.macros` into the HTML head.

A note **this** edition adds — a transcription note, a translator's note, the
record of a correction — is not a footnote of SGA and is not presented as one.
Give the record `"kind": "editorial"` and a `number` to serve as its marker
(`*`, `†`, …), and class its in-text reference `footnote-ref ed-ref`; the viewer
then lists it apart from the printed notes, under the `ednotes` caption, so it
never renumbers the source's own apparatus. Notes printed in the source edition
— including the editor's 1976 notes in SGA 4½ VIII — carry no `kind` and stay in
the numbered list. Sites where the text itself was corrected also belong in
`ERRATA.md`.

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

When a decision does need the corpus brought into line, `glossary_sweep.py`
enforces it instead of a hand pass:

```sh
python3 scripts/glossary_sweep.py --plan               # counts + worklist, writes nothing
python3 scripts/glossary_sweep.py --emit --book sgaN   # append g-* proposals to the run
python3 scripts/glossary_sweep.py --audit-reverse      # EN target where the FR term is absent
```

`glossary/sweep_rules.json` names the *rejected* English rendering per term —
campaign state the glossary schema deliberately does not carry — and each rule's
target is cross-checked against its `glossary.json` entry at load. A rule only
fires where the **aligned French** matches, substitutes in prose only (block html
is segmented on math spans and tags first, and the segments outside prose are
asserted byte-identical afterwards), and emits a normal proposals run, so the
existing guards and the review viewer apply unchanged. Context-dependent terms
(«majorer», «au-dessus de», stalk vs fibre) are never scripted: they go to
`issues/glossary_sweep_worklist.json` for per-occurrence review.

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

## Proposed changes (agent → viewer → data)

The reverse direction: a checking agent audits a volume against its source and
proposes concrete edits; a human adjudicates each one in the viewer. Two ways to
run it: offline (below), or hosted, where the same panel writes straight to the
corpus — see [`deploy/README.md`](deploy/README.md).

```sh
# 1. the agent writes sgaN/data/proposals.json (see below)
python3 scripts/apply_proposals.py --book sgaN --validate          # sanity-check the run

# 2. review in the viewer: open sgaN/paper.html, "⇄ Changes",
#    Accept / Edit / Reject each card, then "Export decisions.json"

# 3. apply the verdicts
python3 scripts/apply_proposals.py --book sgaN --decisions ~/Downloads/decisions.json --dry-run
python3 scripts/apply_proposals.py --book sgaN --decisions ~/Downloads/decisions.json
```

Each proposal is a block-level `before`/`after` replacement, addressed the way a
comment is (`chapterId` → `pageId` → `blockIndex`). The viewer renders it as a
word-level diff inside the block it touches, in that block's own column: math is
diffed as an indivisible atom, and a change to the *markup* falls back to a split
before | after view. `before` is the block's html verbatim, so a proposal whose
block has since changed shows as **stale** and cannot be accepted. Both file
formats are specified in `translation-viewer/docs/proposals.schema.md`.

A volume with no `sgaN/data/proposals.json` shows no review UI at all, so
committing that file is what publishes a run (and deleting it takes it down).
Dropping a `proposals.json` onto the page reviews it locally without committing
anything. `decisions.json` is a local working file.

### Hosted (viewer → data, no round-trip)

`scripts/review_server.py` serves the working tree and applies each verdict as it
is made, so the export → CLI → re-read loop disappears. Readers see the books,
the proposals and the verdicts so far; only a logged-in admin gets the buttons.
Both paths go through the same guards in `scripts/proposals_lib.py`, so a
conflict or a content-losing replacement is refused identically either way.

```sh
python3 scripts/review_server.py --set-password    # once
python3 scripts/review_server.py                   # 127.0.0.1:8000
```

Nothing is committed: the applied edits show up in `git diff` for you to review
and push. Setup for the public deployment (Caddy, systemd, DNS) is in
[`deploy/README.md`](deploy/README.md).

`sga7/data/proposals.json` currently holds a sample run of 10 proposals — every
missing-backslash math defect in the volume (`\(operatorname…`, `\(mathbb…`,
`\(mathcal…`, and one `\(\ell\)` written as a bare `(ell)`), on pages `6-3` and
`22-5`, fr and en. These render cleanly and so survive the check sweep: the TeX
prints the literal control word instead of the symbol. Grep for that class with
`grep -rE '\\\((math[cbsfr]|operatorname|leq|geq)' sgaN/data`; sga5 `V-s6` has
two more (`\(geq p_0\)`).

### Writing the proposals (the checking agent's contract)

Build proposals through `scripts/proposals_lib.py` — `new_proposal()` reads
`before` off disk so the address and the baseline text can't drift, and
`write_proposals()` emits the run:

```python
import proposals_lib as pl
props = [pl.new_proposal("sga3", "en", "III", "III-4", new_html,
                         "FR « lisse » is 'smooth', not 'flat'.",
                         block_index=127, category="translation",
                         evidence="source PDF p. 214")]
pl.write_proposals("sga3", props, generator="…", generated_at="…")
```

What may be proposed: **French transcription** fixes against the source PDF or
LaTeX, **English translation** fixes against the French, and **math/markup**
fixes — always as the text of an existing block (or footnote).

What may not: adding, removing, splitting, merging or reordering blocks. FR and
EN are aligned 1:1 by block index, so a structural change on one side breaks the
other; `apply_proposals.py` refuses it. A replacement must also be a single root
element — the viewer keeps only the first and silently drops the rest.

Every write is guarded: run identity (`proposalsGeneratedAt` must match), address
resolution, conflict (the block still equals `before`), single-root, and the
fr/en block-count invariant. A proposal that trips a guard is reported and
skipped, never forced. Chapter files are rewritten with the corpus's own
serialization (`indent=1`, per-file trailing-newline state) so an edited block is
a one-line diff.

## Requirements

- **python3** — glossary and corpus tooling.
- **node** + **npm** — the check step (auto-installs Puppeteer/Chromium on first run).
- **git submodules checked out** — `translation-viewer/` (`git submodule update --init --recursive`), required by the check step and by the viewer itself.
