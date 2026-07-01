---
name: sga2-check-errors
description: Render every page of the 02-converted_html/ + translation-viewer deliverable in headless Chromium using the deliverable's own MathJax 3 + XyJax-v3 setup, let typesetting (incl. xymatrix) run to completion, and report every problem found, categorised into three files. MathJax errors (mjx-merror, typeset failures, leaked `\command` tokens) go to issues/mathjax_errors.json; cross-reference errors (a `\ref`/`\eqref` surviving into math that MathJax renders as `???`, leftover `???`/`??` markers, and internal `#anchor` links that resolve to nothing via the manifest) go to issues/crossref_errors.json; other errors (equation-tag dropout, a closing guillemet `»` glued to the following word — missing space after the quote, blocks whose HTML isn't a single root element, plus console / page-level errors) go to issues/other_errors.json. Independent verification step on top of sga2-convert-html — pdflatex compiling cleanly does not guarantee MathJax+XyJax can render.
---

# sga2-check-errors

## When to use

After `sga2-convert-html` has produced `02-converted_html/`. pdflatex accepts
LaTeX that MathJax + XyJax-v3 cannot render (e.g. certain `\xymatrix`
constructs, `\textup` inside `\text`, a stray macro corrupting a diagram); this
skill catches those by rendering the actual shipped HTML in a real browser.

## How to run

```
bash .claude/skills/sga2-check-errors/check.sh          # both fr and en (default)
bash .claude/skills/sga2-check-errors/check.sh fr       # one language
bash .claude/skills/sga2-check-errors/check.sh fr,en    # explicit
```

On first run it `npm install`s puppeteer into the skill directory (~150 MB,
downloads a Chromium build). Subsequent runs reuse the cache. The full
two-language tree (66 pages × 2 + one shared titles pass) takes roughly 1–2 min.
MathJax 3 (SVG) + XyJax are vendored under the sibling `translation-viewer/`
submodule, so **rendering needs no network** — only the one-time
puppeteer/Chromium install does.

Outputs:
- live progress on stderr (one line per page, `ok` or `ISSUES …` with
  per-channel counts: `merror`, `leak`, `refMath`, `mark`, `dangling`, `tag`,
  `quote`, `blockShape`)
- three structured files under `issues/`, each an array of **only the pages
  that have an error in that category** (a clean category → `[]`):
  - `issues/mathjax_errors.json` — typeset failures, `mjx-merror`, leaked
    `\command` macros
  - `issues/crossref_errors.json` — `\ref`/`\eqref` in math, `???`/`??`
    markers, dangling `#anchor` links
  - `issues/other_errors.json` — equation-tag dropout, closing-guillemet
    spacing (`»` glued to the following word), multi-root content blocks,
    plus `fatal` / page-level / console errors
  Each record repeats the identity fields (`lang`, `file`, `pageId`, `title`,
  `containers`) so every error stays attributable to a page.
- human-readable summary on stdout, grouped under **MathJax** /
  **Cross-references** / **Other** headings, with the per-token leak rollup
  under MathJax and the per-label "refs in math" rollup under Cross-references
  (the upstream fix lists), ending in `CHECK PASSED` / `CHECK FAILED`

## Architecture this skill targets

The deliverable is **not** a tree of standalone HTML files — it is a single
page (`paper.html`) driven by the generic `translation-viewer` submodule
(mounted as a sibling of `02-converted_html/` at the repo root):

- `02-converted_html/paper.html` — the entry page; its `<head>` loads
  `translation-viewer/viewer-bootstrap.js`, which fetches
  `02-converted_html/data/config.json` and configures MathJax 3 + XyJax-v3 from
  it (`tags:'none'`, packages incl. `xypic`), injecting the submodule's own
  vendored assets.
- `translation-viewer/viewer.js` — fetches the **base-language manifest only**
  (`data/fr/manifest.json` — ids are shared across languages, so one manifest
  drives navigation for every column) and per-language chapter content
  (`data/<lang>/chapters/<id>.json`), rendering blocks in aligned rows and
  calling `MathJax.typesetPromise`.
- The math (incl. the xymatrix commutative diagrams) lives **inside the JSON
  block `html` strings**, not on disk as HTML.

So the checker loads `paper.html` **once** (to obtain the deliverable's exact
MathJax + XyJax environment), then in Node reads every page's assembled HTML
from the JSON and typesets it directly into an offscreen scratch container,
scanning the rendered DOM. This is preferred over driving the viewer's hash
navigation, which chains every typeset onto `MathJax.startup.promise` (a
stale-promise race) and grows the `document.math` list unboundedly. Rendering
each page's string ourselves gives a deterministic completion signal (the
promise returned by our own `typesetPromise([root])`) while keeping full XyJax
fidelity. `check.sh` serves from the **repo root** (not `02-converted_html/`)
so `paper.html`'s `../translation-viewer/...` references resolve.

## What it checks

Each check below is routed to one of the three output files by category:
**MathJax** (`mathjax_errors.json`) — checks 1, 2 + `typesetError`;
**Cross-references** (`crossref_errors.json`) — checks 3, 4, 5;
**Other** (`other_errors.json`) — checks 6, 7, 8 + `fatal` / page / console errors.

Per-page DOM passes (scoped to the scratch container so the static viewer chrome
isn't re-scanned 66×):

1. **`mjx-merror`** — MathJax 3 wraps each failed TeX expression in
   `<mjx-merror title="…">` rather than throwing; static source inspection
   misses it because the math is still `\(…\)` on disk. xypic runs inside
   MathJax, so `\xymatrix` errors only appear here, after `typesetPromise`
   resolves.
2. **Leaked `\word` macros** — some commands survive into the DOM as visible
   text without firing `mjx-merror` (the unknown-macro-rendered-as-text case).
   A tree walk over post-typeset text nodes catches both raw leaks and
   MathJax-internal leaks (the latter live in the hidden `mjx-assistive-mml`
   mirror). Deduped by container; the summary ends with a per-token rollup.
3. **`???` / `??` markers** — an unresolved `\ref` consumed by MathJax renders
   as `???`, which is neither an `mjx-merror` nor a `\word` leak. The tree
   walker reaches the literal `???` in the assistive mirror.

Static passes (over the JSON `page.html`, in Node):

4. **`\ref`/`\eqref` surviving into math** — references are pre-resolved from
   `main.aux`, so any literal `\ref{…}`/`\eqref{…}` left in the HTML leaked into
   a math environment; reported by label as a regression guard.
5. **Internal-link integrity** — every `<a href="#frag">` whose fragment
   resolves to nothing. In the SPA the viewer resolves a fragment
   (`viewer.js` `resolveHash`) if it is a page id, an `anchor_index` key, a
   same-page element id, or a `toc-anchor-<X>` fallback; anything else would
   404 in the viewer. (This replaces the old same-file `getElementById`
   dangling check, which is meaningless in a manifest-driven SPA.)
6. **Equation-tag dropout** — a numbered display-math block carries one `\label`
   (hence one number) per row; the converter emits the first label as the
   `<div class="equation">` id and the rest as `label-anchor` spans nested
   inside that div (not preceding siblings — see check 8), and injects an
   explicit `\tag{…}` per numbered row (MathJax runs `tags:'none'`,
   and multi-row envs are forced to their starred form, so **only** a `\tag`
   produces a visible number). If a block has more `eq:` labels than `\tag{…}`s,
   a labeled row renders with **no number** — the `(21)`/`(21 bis)` case, where
   the `(21)` row silently lost its tag because the converter's block-global
   `has_tag` flag suppressed injection once the `21 bis` row supplied a `\tag`.
   Reported per block as `[tag-missing]`; `\notag`/`\nonumber` in the body is
   noted so a legitimately-unnumbered row isn't mistaken for the bug. The fix
   belongs upstream in the converter (`convert.py` `render_mathblock`).
7. **Closing-guillemet spacing** — a closing `»` glued to the word that follows
   it (`point-base »dans`, `parafactoriel »signifie`). The source uses
   `\og … \fg`, and the converter maps `\fg → ␯»` then applies TeX's
   control-word rule that swallows the single ASCII space after a letter-named
   control word, so `\fg word` renders as `»word` (the opening `« word` is fine
   — `«` is followed by a U+202F narrow space). Only a letter/digit, an opening
   paren `(`, or inline math `\(` right after `»` is flagged (`[quote-space]`);
   punctuation, closing brackets, HTML tags and entities (`».`, `»,`, `»)`,
   `»]`, `»<`) legitimately abut `»` and are not. A superscript-only inline math
   (`»\(^…`) is also exempt — that is a footnote/editorial mark hugging the quote
   (`…affine »\(^{(**)}\)`), which is correct typography with no space wanted. The
   fix belongs upstream in the converter (`convert.py` — `\fg` should not eat the
   following space).
8. **Multi-root content blocks** (`checkBlockShapes`, DOM pass) — translation-viewer's
   `blockEl()` builds a `<template>` from a block's `html` and keeps only
   `tpl.content.firstElementChild`. A block whose `html` is more than one
   top-level element (e.g. a stray sibling before the real content) has
   everything after the first element **silently dropped** — no `mjx-merror`,
   leak, or `???` results, so nothing else here would catch it. This check
   mirrors that exact parse per block and flags any block with `!= 1` root
   element or stray top-level text, reported as `[multi-root-block]`. Caught
   and fixed at the source once already (`convert.py` `render_mathblock` used
   to prepend multi-label `label-anchor` spans as siblings instead of nesting
   them inside the div — see check 6); this check guards against the same
   mistake recurring.

Plus a shared **titles pass** (chapter + toc titles can carry math; the
manifest is base-language only, so titles are checked once, not per language)
and **console / page-level error** capture, with benign noise filtered
(favicon 404s and XyJax's `No version information available for component`
warning).

### MathJax 3 source-TeX recovery
The source TeX of an `mjx-merror`/leak is recovered from MathJax 3's
`MathJax.startup.document.math` list (each `MathItem` exposes `.math` source and
`.typesetRoot` DOM node), matched to the offending `mjx-container` by node
identity. There is **no** `<script type="math/tex">` in MathJax 3 output — that
was a MathJax 2 artifact and the reason the previous (plasTeX-era) version of
this skill recovered no source here.

## Design principle

Fixes for what this skill surfaces belong **upstream in the LaTeX normalization
step** (`sga2-inline-macros` / the converter), not in HTML post-processing — see
the repo README. The per-token leak rollup and per-label ref rollup in the
summary are the fix list.

## Files

- `SKILL.md` — this file
- `check.sh` — launcher: installs puppeteer if missing, starts a local HTTP
  server over the **repo root** (so `translation-viewer/` resolves as a
  sibling of `02-converted_html/`), runs `check.js`, tears the server down.
  Takes an optional comma-separated language list (default `fr,en`).
- `check.js` — Puppeteer driver: loads `paper.html`, renders each page's JSON
  HTML into an offscreen container, scans the DOM, runs the static passes.
- `package.json` — declares the puppeteer dependency

## Related

- `issues/mathjax_errors.json`, `issues/crossref_errors.json`,
  `issues/other_errors.json` — the categorised results of the last run (each
  lists only the pages with an error in that category).
- `.claude/skills/sga2-convert-html/` — produces the content and `paper.html`
  this skill checks.
- `translation-viewer/` (sibling submodule) — the generic viewer engine this
  skill's checks are modeled after (`blockEl()`, `footnotesEl()`).
