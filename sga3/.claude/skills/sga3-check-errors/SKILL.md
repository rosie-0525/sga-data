---
name: sga3-check-errors
description: Render every transcription in 01-transcribed/ in headless Chromium using the files' own MathJax 3 + XyJax-v3 setup, let typesetting (incl. xymatrix) run to completion, and report every problem found, categorised into three files. MathJax errors (mjx-merror, typeset failures, leaked `\command` tokens) go to issues/mathjax_errors.json; cross-reference errors (`???`/`??` markers, and `#anchor` links that resolve to no id in any transcribed file) go to issues/crossref_errors.json; other errors (console / page-level) go to issues/other_errors.json. Verification step on top of sga3-transcribe — run it whenever a transcription is finished or edited.
---

# sga3-check-errors

## When to use

After `sga3-transcribe` has produced or updated a file in `01-transcribed/`.
The transcriptions are hand-written HTML with hand-typed TeX; a typo in a
formula, a `\xymatrix` construct XyJax can't handle, or a mistyped anchor
only shows up when the actual file is rendered in a real browser.

## How to run

```
bash .claude/skills/sga3-check-errors/check.sh          # every file in 01-transcribed/
bash .claude/skills/sga3-check-errors/check.sh II       # one chapter
bash .claude/skills/sga3-check-errors/check.sh II,VIB   # several
```

Puppeteer is reused from sga1's check-errors skill
(`sga1/.claude/skills/sga1-check-errors/node_modules`) when that install
exists; otherwise the first run `npm install`s it into this skill's directory
(~150 MB, downloads a Chromium build) and subsequent runs reuse the cache.
MathJax 3 (SVG) + XyJax are vendored under `translation-viewer/vendor/`, so
**rendering needs no network** — only a one-time puppeteer/Chromium install does.

Even when only some chapters are rendered, the anchor pass always reads every
file in `01-transcribed/` so cross-exposé links resolve against the full set.

Outputs:
- live progress on stderr (one line per file, `ok` or `ISSUES …` with
  per-channel counts: `merror`, `leak`, `mark`, `dangling`)
- three structured files under `issues/`, each an array of **only the files
  that have an error in that category** (a clean category → `[]`):
  - `issues/mathjax_errors.json` — typeset failures, `mjx-merror`, leaked
    `\command` macros
  - `issues/crossref_errors.json` — `???`/`??` markers, dangling `#anchor` links
  - `issues/other_errors.json` — `fatal` / page-level / console errors
  Each record repeats the identity fields (`file`, `chapterId`, `containers`)
  so every error stays attributable to a file.
- human-readable summary on stdout, grouped under **MathJax** /
  **Cross-references** / **Other** headings, with a per-token leak rollup
  under MathJax, ending in `CHECK PASSED` / `CHECK FAILED`

## Architecture this skill targets

Unlike sga1/sga2 (whose deliverable is a JSON-manifest single-page viewer that
their check-errors skills must typeset piecewise), SGA 3's `01-transcribed/`
is a tree of **standalone, self-contained HTML files**. Each file carries its
own MathJax 3 + XyJax-v3 config (`startup.typeset:false`) and loads the
vendored engine via `../../translation-viewer/...` relative paths — which is
why `check.sh` serves the `sga/` super-repo root over a local HTTP server.

So the checker simply navigates headless Chromium to every file's URL, awaits
`MathJax.startup.promise`, runs an explicit `MathJax.typesetPromise()`, and
scans the rendered DOM. No offscreen-container machinery is needed.

## What it checks

Per-file DOM passes (after typesetting completes):

1. **`mjx-merror`** — MathJax 3 wraps each failed TeX expression in
   `<mjx-merror title="…">` rather than throwing; static source inspection
   misses it because the math is still `\(…\)` on disk. xypic runs inside
   MathJax, so `\xymatrix` errors only appear here, after `typesetPromise`
   resolves. The source TeX of each error is recovered from MathJax 3's
   `MathJax.startup.document.math` list (each `MathItem` exposes `.math` and
   `.typesetRoot`), matched to the offending `mjx-container` by node identity.
2. **Leaked `\word` macros** — some commands survive into the DOM as visible
   text without firing `mjx-merror` (the unknown-macro-rendered-as-text case).
   A tree walk over post-typeset text nodes catches both raw leaks and
   MathJax-internal leaks (the latter live in the hidden `mjx-assistive-mml`
   mirror). Deduped by container; the summary ends with a per-token rollup.
3. **`???` / `??` markers** — leftover placeholder markers, whether typed into
   the transcription or produced by MathJax consuming a stray `\ref`.

Static pass (over the HTML files, in Node):

4. **Internal-link integrity** — every `<a href="#frag">` whose fragment
   matches no element id **in any transcribed file**. SGA 3's anchors are
   chapter-prefixed (`id="VIB.7.2"`) and exposés freely cross-link, so
   resolution is global, and misses are labelled `same-file` vs `cross-file`.
   A fragment whose chapter prefix (per `chapter-map.json`) names an exposé
   that has **no file in `01-transcribed/` yet** is reported separately as
   informational ("refs into not-yet-transcribed exposés") and does **not**
   fail the check — references legitimately run ahead of the transcription
   effort.

Plus **console / page-level error** capture, with benign noise filtered
(favicon 404s and XyJax's `No version information available for component`
warning).

## What it cannot check

A diagram can typeset without error and still differ from the source. After a
new transcription passes this check, screenshot its commutative diagrams and
compare them against the source PDF pages by eye — that visual comparison is
part of finishing a transcription and no script does it.

## Files

- `SKILL.md` — this file
- `check.sh` — launcher: resolves puppeteer (sga1's install or a local one),
  starts a local HTTP server over the `sga/` super-repo root, runs `check.js`,
  tears the server down. Takes an optional comma-separated chapter-id list
  (default: every file).
- `check.js` — Puppeteer driver: navigates to each transcription, typesets,
  scans the DOM, runs the static anchor pass.
- `package.json` — declares the puppeteer dependency (used only when sga1's
  vendored install is absent)

## Related

- `issues/mathjax_errors.json`, `issues/crossref_errors.json`,
  `issues/other_errors.json` — the categorised results of the last run (each
  lists only the files with an error in that category).
- `.claude/skills/sga3-transcribe/` — produces the files this skill checks.
