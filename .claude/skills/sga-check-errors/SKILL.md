---
name: sga-check-errors
description: Render every page of any sga*/ book viewer (paper.html + data/) in headless Chromium using the deliverable's own MathJax 3 + XyJax-v3 setup (via the shared translation-viewer engine), let typesetting (incl. xymatrix) run to completion, and report every problem found, categorised into three aggregate files under the repo-root issues/ (every record carries `book`; a run replaces only its own book's records). MathJax errors (mjx-merror, typeset failures, leaked `\command` tokens — e.g. `\lhook\joinrel` surviving into the frontend) go to issues/mathjax_errors.json; cross-reference errors (a `\ref`/`\eqref` surviving into math that MathJax renders as `???`, leftover `???`/`??` markers, and internal `#anchor` links that resolve to nothing via the manifest) go to issues/crossref_errors.json; other errors (equation-tag dropout, a closing guillemet `»` glued to the following word, multi-root content blocks, plus console / page-level errors) go to issues/other_errors.json; per-book run metadata and totals go to issues/summary.json. Works on every SGA book (sga1..sga7) — independent verification on top of each book's convert step; pdflatex compiling cleanly does not guarantee MathJax+XyJax can render.
---

# sga-check-errors

## When to use

After any book's convert step has produced `<book>/paper.html` + `<book>/data/`. pdflatex
(or the transcription pipeline) accepts LaTeX that MathJax + XyJax-v3 cannot
render (e.g. certain `\xymatrix` constructs, `\textup` inside `\text`,
plain-TeX arrow idioms like `\lhook\joinrel\longrightarrow` — MathJax defines
`\hookrightarrow` but not `\lhook`); this skill catches those by rendering the
actual shipped HTML in a real browser.

## How to run

```
bash .claude/skills/sga-check-errors/check.sh                 # every sga*/ book
bash .claude/skills/sga-check-errors/check.sh sga5            # one book
bash .claude/skills/sga-check-errors/check.sh sga5,sga7       # a list of books
bash .claude/skills/sga-check-errors/check.sh all fr          # every book, one language
bash .claude/skills/sga-check-errors/check.sh sga5 fr,en      # explicit languages
```

By default each book is checked in its own languages (`baseLang` +
`rightLangs` from its `data/config.json`); the second argument overrides that.

On first run it `npm install`s puppeteer into the skill directory (~150 MB,
downloads a Chromium build). Subsequent runs reuse the cache. A book takes
roughly 1–2 min per language pair. MathJax 3 (SVG) + XyJax are vendored under
the shared `translation-viewer/` submodule at the repo root (initialise it with
`git submodule update --init translation-viewer` if empty), so **rendering
needs no network** — only the one-time puppeteer/Chromium install does.

Outputs:
- live progress on stderr (one line per page, `ok` or `ISSUES …` with
  per-channel counts: `merror`, `leak`, `refMath`, `mark`, `dangling`,
  `footnote`, `tag`, `quote`, `blockShape`)
- four structured files under the repo-root `issues/`, **aggregated across all
  books**. Each category file is one flat array of failing-page records
  (a fully clean category → `[]`); every record carries `book` (e.g. `"sga5"`)
  and a book-qualified `file` (`"sga5/fr/IIIB-2"`), and a run **replaces only
  its own book's records** — checking one book never clobbers the others'
  results. Records are grouped by book, in scan order within a book:
  - `issues/mathjax_errors.json` — typeset failures, `mjx-merror`, leaked
    `\command` macros
  - `issues/crossref_errors.json` — `\ref`/`\eqref` in math, `???`/`??`
    markers, dangling `#anchor` links, footnote backref pairing
  - `issues/other_errors.json` — equation-tag dropout, closing-guillemet
    spacing (`»` glued to the following word), multi-root content blocks, plus
    `fatal` / page-level / console errors
  - `issues/summary.json` — `{ books: { <book>: { lastRun, langs,
    checkedPages, mathContainers, pagesWithIssues, pagesByCategory, counts,
    passed } } }`: per-book run metadata and per-channel issue totals, so
    pass/fail state and staleness (which book was last checked when) live in
    one place while the category files stay pure error lists.
  Each error record repeats the identity fields (`book`, `lang`, `file`,
  `pageId`, `title`, `containers`) so every error stays attributable to a page.
- human-readable summary on stdout per book, grouped under **MathJax** /
  **Cross-references** / **Other** headings, with the per-token leak rollup
  under MathJax and the per-label "refs in math" rollup under Cross-references
  (the upstream fix lists), ending in `CHECK PASSED` / `CHECK FAILED`

## Architecture this skill targets

Every book's deliverable is the same single-page viewer, driven by the shared
`translation-viewer/` engine at the repo root:

- `<book>/paper.html` — shell that bootstraps
  `translation-viewer/viewer-bootstrap.js`, which fetches `data/config.json`,
  configures MathJax 3 (SVG) + XyJax-v3 from it (`startup.typeset:false`,
  `tags:'none'`, packages incl. `xypic`, plus any per-book
  `config.mathjax.packages` override), and injects the vendored assets.
- `translation-viewer/viewer.js` — fetches `data/<baseLang>/manifest.json`
  (once — it drives navigation for every language column) and
  `data/<lang>/chapters/<id>.json`, rendering each page's `blocks[].html` in
  aligned rows (`blockEl()` keeps only each block's first top-level element).
- The math (incl. the xymatrix commutative diagrams) lives **inside the JSON
  block `html` strings**, not on disk as HTML.

So the checker loads `paper.html` **once per book** (to obtain the
deliverable's exact MathJax + XyJax environment), then in Node reads every
page's blocks from the JSON and typesets their concatenated html directly into
an offscreen scratch container, scanning the rendered DOM. This is preferred
over driving the viewer's hash navigation, which chains every typeset onto
`MathJax.startup.promise` (a stale-promise race) and grows the `document.math`
list unboundedly. Rendering each page's string ourselves gives a deterministic
completion signal (the promise returned by our own `typesetPromise([root])`)
while keeping full XyJax fidelity.

## What it checks

Each check below is routed to one of the three output files by category:
**MathJax** (`mathjax_errors.json`) — checks 1, 2 + `typesetError`;
**Cross-references** (`crossref_errors.json`) — checks 3, 4, 5, 5b;
**Other** (`other_errors.json`) — checks 6, 7, 8 + `fatal` / page / console errors.

Per-page DOM passes (scoped to the scratch container so the static viewer chrome
isn't re-scanned per page):

1. **`mjx-merror`** — MathJax 3 wraps each failed TeX expression in
   `<mjx-merror title="…">` rather than throwing; static source inspection
   misses it because the math is still `\(…\)` on disk. xypic runs inside
   MathJax, so `\xymatrix` errors only appear here, after `typesetPromise`
   resolves. Undefined plain-TeX control sequences (`\lhook` etc.) land here
   as "Undefined control sequence".
2. **Leaked `\word` macros** — some commands survive into the DOM as visible
   text without firing `mjx-merror` (the unknown-macro-rendered-as-text case).
   A tree walk over post-typeset text nodes catches both raw leaks and
   MathJax-internal leaks (the latter live in the hidden `mjx-assistive-mml`
   mirror). Deduped by container; the summary ends with a per-token rollup.
3. **`???` / `??` markers** — an unresolved `\ref` consumed by MathJax renders
   as `???`, which is neither an `mjx-merror` nor a `\word` leak. The tree
   walker reaches the literal `???` in the assistive mirror.

Static passes (over the JSON block html, in Node):

4. **`\ref`/`\eqref` surviving into math** — references are pre-resolved by the
   converter, so any literal `\ref{…}`/`\eqref{…}` left in the HTML leaked into
   a math environment; reported by label as a regression guard.
5. **Internal-link integrity** — every `<a href="#frag">` whose fragment
   resolves to nothing. In the SPA the viewer resolves a fragment
   (`viewer.js` `resolveHash`) if it is a page id, a same-page element id, an
   `anchor_index` key, or a `toc-anchor-<X>` fallback; anything else would
   404 in the viewer.
5b. **Footnote backref pairing** — check 5 passes a fragment that resolves to a
   same-page id, which is correct for a click (the viewer looks the id up in the
   live DOM before consulting the index) but hides an index that never learned
   about the anchor. Each footnote is therefore checked as a pair in its own
   right: `[fn-noref]` — the note has no `id="<id>ref"` marker on its page, so
   its ↩ has nothing to return to; `[fn-unindexed]` — the note or its marker is
   missing from `anchor_index`, so deep links (`paper.html#<id>ref`) and
   cross-page jumps fail even though same-page clicks work; `[fn-misindexed]` —
   `anchor_index` maps it to a different page than the one holding it, which in
   practice means one marker id was emitted on two pages. Editorial notes
   (`kind: "editorial"`) are where this recurs, since they are added after the
   convert step built the index. `scripts/repair_anchor_index.py` rebuilds the
   index from the pages and fixes the indexing cases.
6. **Equation-tag dropout** — a numbered display-math block carries one `\label`
   (hence one number) per row; the converter emits the first label as the
   `<div class="equation">` id and the rest as `label-anchor` spans, and
   injects an explicit `\tag{…}` per numbered row (MathJax runs `tags:'none'`,
   and multi-row envs are forced to their starred form, so **only** a `\tag`
   produces a visible number). If a block has more `eq:` labels than `\tag{…}`s
   (`\tag*{…}` also counts), a labeled row renders with **no number** — the
   `(21)`/`(21 bis)` case. Reported per block as `[tag-missing]`;
   `\notag`/`\nonumber` in the body is noted so a legitimately-unnumbered row
   isn't mistaken for the bug. The fix belongs upstream in the book's converter.
7. **Closing-guillemet spacing** — a closing `»` glued to the word that follows
   it (`point-base »dans`). The source uses `\og … \fg`, and a converter that
   maps `\fg → ␯»` then applies TeX's control-word rule swallows the single
   ASCII space after it, so `\fg word` renders as `»word`. Only a letter/digit,
   an opening paren `(`, or inline math `\(` right after `»` is flagged
   (`[quote-space]`); punctuation, closing brackets, HTML tags and entities
   legitimately abut `»` and are not. A superscript-only inline math (`»\(^…`)
   is also exempt — that is a footnote/editorial mark hugging the quote, which
   is correct typography. The fix belongs upstream in the book's converter.
8. **Multi-root content blocks** — `translation-viewer`'s `blockEl()` keeps only
   the **first** top-level element of a block's html, so a block whose html has
   more than one root (or stray top-level text) silently drops content in the
   shipped viewer, with no merror/leak/`???` to show for it. Mirrored exactly
   in a browser-side pass (`[multi-root-block]`).

Plus a per-language **titles pass** (chapter + toc titles can carry math) and
**console / page-level error** capture, with benign noise filtered (favicon
404s and XyJax's `No version information available for component` warning).

### MathJax 3 source-TeX recovery
The source TeX of an `mjx-merror`/leak is recovered from MathJax 3's
`MathJax.startup.document.math` list (each `MathItem` exposes `.math` source and
`.typesetRoot` DOM node), matched to the offending `mjx-container` by node
identity. There is **no** `<script type="math/tex">` in MathJax 3 output — that
was a MathJax 2 artifact.

## Design principle

Fixes for what this skill surfaces belong **upstream in each book's LaTeX
normalization / transcription / convert step**, not in HTML post-processing —
see the repo README. The per-token leak rollup and per-label ref rollup in the
summary are the fix list.

## Files

- `SKILL.md` — this file
- `check.sh` — launcher: installs puppeteer if missing, starts one local HTTP
  server at the repo root, runs `check.js` per book into the shared repo-root
  `issues/`, tears the server down. Args: book list (`all`, `sga5`,
  `sga5,sga7`; default `all`) and an optional comma-separated language list
  (default: each book's own config languages).
- `check.js` — Puppeteer driver: loads the book's paper.html, renders each
  page's JSON block html into an offscreen container, scans the DOM, runs the
  static passes.
- `package.json` — declares the puppeteer dependency

## Related

- `issues/mathjax_errors.json`, `issues/crossref_errors.json`,
  `issues/other_errors.json`, `issues/summary.json` (repo root) — the
  categorised, book-aggregated results of the last run(s).
- `translation-viewer/` (repo-root git submodule) — the shared viewer engine
  every book's deliverable loads; vendored MathJax 3 + XyJax-v3 live under
  `translation-viewer/vendor/`.
- Superseded per-book copies: this skill replaces the old per-book
  `sgaN-check-errors` skills, all of which were removed with the rest of the
  build pipeline on 2026-07-27 (in git history through `a2317a4`). It is now
  the only render check in the repo, and it checks each book's `paper.html` + `data/` —
  the sole remaining deliverable — for every book.
