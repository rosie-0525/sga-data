---
name: sga2-convert-html
description: Convert the normalized SGA2 LaTeX tree (01-normalized_tex/) into JSON-with-embedded-HTML (02-converted_html/) plus a self-contained MathJax 3 + XyJax-v3 viewer. The convert step of the pipeline; run after sga2-normalize.
---

# sga2-convert-html

Converts `01-normalized_tex/` → `02-converted_html/`: a JSON manifest plus
per-chapter content with embedded HTML, and a self-contained browser viewer.
Math is kept as LaTeX in `\(...\)` / `\[...\]` for client-side **MathJax 3 +
XyJax-v3** (xy-pic diagrams); it is not pre-rendered.

## Run

```sh
bash .claude/skills/sga2-convert-html/convert.sh
```

This (1) refreshes `01-normalized_tex/main.aux` with `pdflatex` if it is
missing or older than the sources, (2) runs the converter, (3) copies the viewer
into the output. Preview:

```sh
cd 02-converted_html && python3 -m http.server   # then open http://localhost:8000/
```

Run the converter alone (e.g. one chapter while debugging):

```sh
python3 .claude/skills/sga2-convert-html/convert.py --only chapter-01 --verify
```

## How it works

- **Numbering & cross-references come from `main.aux`** (`parse_aux`). The
  source uses custom counters (`\steco`, `enonce*` hand-numbers, `\tag`,
  `\setcounter`), so chapter/section/statement/equation numbers and every
  `\ref`/`\eqref`/`\cite` target are read from the authoritative `\newlabel` /
  `\@writefile{toc}` / `\bibcite` records rather than re-derived. **Keep
  `main.aux` in sync** — re-run `convert.sh` (or `pdflatex`) after editing the
  LaTeX.
- **Macros are expanded to plain LaTeX** (`expand_math`, tables `MATH_0ARG` /
  `MATH_1ARG` / `MATH_NARG`). The ~120 content macros from `sga2-macros.sty`
  (`\Spec`, `\ccat`, `\ZZ`, `\to`, `\leq`→`\leqslant`, `\mathcal`→`\mathscr`, …)
  plus chapter-local `\newcommand`s (e.g. `\Ib`,`\Jb` in chapter IX) become
  standard MathJax-renderable LaTeX. This honours the project rule of **not**
  injecting `tex.macros` into the HTML head.
- **`\xymatrix` is passed through unchanged** — the XyJax-safety rewrites were
  already applied upstream by `sga2-inline-macros`; the viewer loads XyJax-v3.

## Output schema (`02-converted_html/`)

```
fr.json                   manifest: {toc, default_page_id, default_chapter_id, chapters, anchor_index}
fr/chapters/<id>.json     {chapter_id, title, number, pages[]}
en.json / en/chapters/    same envelope; English content is empty stubs (French is the reference)
index.html viewer.css viewer.js   self-contained viewer
```

- **page**: `{id, title, html, blocks[], footnotes[], bibliography[]}` with the
  invariant `html == "\n".join(b.html for b in blocks)`.
- **block**: `{id, type, label, title, html}`; `type` ∈ `heading | paragraph |
  <theorem-env> | enonce | proof | equation | displaymath | list | table |
  bibliography | anchor`.
- Ids are readable: chapters `I`…`XIV`, `I-0` (Introduction), front/back matter
  `resume`/`preface`/`index-notations`/`index-terminologie`; sections `I-1`,
  `III-2`; statement/equation anchors keep their LaTeX label (`I.1.1`, `eq:I.1`).
  `anchor_index` maps every element id → its page id so the viewer can resolve
  cross-page links.

## Verify

`convert.py --verify` reports chapter/page/block/equation/theorem/footnote/bib
counts, **unresolved** refs/cites, **leaked** `\commands` outside math, and JSON
validity. A clean run is 0 unresolved and 0 leaks. To catch macros that slip
through *inside* math, scan the `\(...\)` / `\[...\]` regions for backslash
commands that are neither standard MathJax nor expected XyJax (`\ar`,
`\xymatrix`); see the converter's macro tables when adding new ones.

The headless MathJax/XyJax render check (`sga2-check-mathjax`) is the downstream
gate that loads the viewer pages in Chromium and reports `mjx-merror`s.

A full headless pass (66 pages) renders **9 489** math expressions with **no
plain-math errors** and no unrendered `\(`/`\[`. The only ~20 `mjx-merror`s are
complex `\xymatrix` cells (e.g. `\underline{\mathrm{H}}_T^i(f^*F)` on pages
IV-1, IV-3, XIV-1/2/3) that exceed XyJax-v3's parser. These reproduce on the
**raw source** diagram with the converter bypassed, so per the project design
principle the fix belongs upstream in `sga2-inline-macros`
(`rule_xymatrix_patches`) / `sga2-normalize-xymatrix`, not here. The page still
renders — XyJax shows an inline error only for the offending diagram.
