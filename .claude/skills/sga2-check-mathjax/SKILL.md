---
name: sga2-check-mathjax
description: Render every page of the 02-converted_html/ viewer in headless Chromium using the deliverable's own MathJax 3 + XyJax-v3 setup, let typesetting (incl. xymatrix) run to completion, and report every mjx-merror, every leaked `\command` token still visible in the rendered DOM, every unresolved cross-reference (a `\ref`/`\eqref` surviving into math that MathJax renders as `???`, plus leftover `???`/`??` markers and internal `#anchor` links that resolve to nothing via the manifest), plus any console / page-level TeX errors. Independent verification step on top of sga2-convert-html — pdflatex compiling cleanly does not guarantee MathJax+XyJax can render.
---

# sga2-check-mathjax

## When to use

After `sga2-convert-html` has produced `02-converted_html/`. pdflatex accepts
LaTeX that MathJax + XyJax-v3 cannot render (e.g. certain `\xymatrix`
constructs, `\textup` inside `\text`, a stray macro corrupting a diagram); this
skill catches those by rendering the actual shipped HTML in a real browser.

## How to run

```
bash .claude/skills/sga2-check-mathjax/check.sh          # both fr and en (default)
bash .claude/skills/sga2-check-mathjax/check.sh fr       # one language
bash .claude/skills/sga2-check-mathjax/check.sh fr,en    # explicit
```

On first run it `npm install`s puppeteer into the skill directory (~150 MB,
downloads a Chromium build). Subsequent runs reuse the cache. The full
two-language tree (66 pages × 2 + a titles pass each) takes roughly 1–2 min.
MathJax + XyJax load from jsdelivr, so **network is required**.

Outputs:
- live progress on stderr (one line per page, `ok` or `ISSUES …` with
  per-category counts: `merror`, `leak`, `refMath`, `mark`, `dangling`)
- `issues/mathjax_errors.json` — full structured result for every page
- human-readable summary on stdout, grouped by error category, ending with a
  per-token leak rollup and a per-label "refs in math" rollup (the upstream fix
  list), and `CHECK PASSED` / `CHECK FAILED`

## Architecture this skill targets

The deliverable is **not** a tree of standalone HTML files — it is a single-page
viewer:

- `02-converted_html/index.html` — shell that loads MathJax 3 + XyJax-v3
  (`startup.typeset:false`, `tags:'none'`, packages incl. `xypic`).
- `02-converted_html/viewer.js` — fetches a JSON manifest (`<lang>.json`) and
  per-chapter content (`<lang>/chapters/<id>.json`), renders one page at a time
  into `#page`, and calls `MathJax.typesetPromise`.
- The math (incl. the xymatrix commutative diagrams) lives **inside the JSON
  `page.html` strings**, not on disk as HTML.

So the checker loads `index.html` **once** (to obtain the deliverable's exact
MathJax + XyJax environment), then in Node reads every `page.html` from the JSON
and typesets it directly into an offscreen scratch container, scanning the
rendered DOM. This is preferred over driving the viewer's hash navigation, which
chains every typeset onto `MathJax.startup.promise` (a stale-promise race) and
grows the `document.math` list unboundedly. Rendering each page's string
ourselves gives a deterministic completion signal (the promise returned by our
own `typesetPromise([root])`) while keeping full XyJax fidelity.

## What it checks

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

Plus a per-language **titles pass** (chapter + toc titles can carry math) and
**console / page-level error** capture, with benign noise filtered (favicon
404s and XyJax's `No version information available for component` warning).

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
  server over `02-converted_html/`, runs `check.js`, tears the server down.
  Takes an optional comma-separated language list (default `fr,en`).
- `check.js` — Puppeteer driver: loads `index.html`, renders each page's JSON
  HTML into an offscreen container, scans the DOM, runs the static passes.
- `package.json` — declares the puppeteer dependency

## Related

- `issues/mathjax_errors.json` — full structured result of the last run.
- `.claude/skills/sga2-convert-html/` — produces the viewer this skill checks.
