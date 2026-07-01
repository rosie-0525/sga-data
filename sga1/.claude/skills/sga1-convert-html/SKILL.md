---
name: sga1-convert-html
description: Convert the normalized SGA1 LaTeX tree (01-normalized_tex/) into JSON-with-embedded-HTML (02-converted_html/) plus a self-contained, offline MathJax 3 (SVG) + XyJax-v3 viewer (assets vendored under vendor/). The convert step of the pipeline; run after sga1-normalize.
---

# sga1-convert-html

Converts `01-normalized_tex/` → `02-converted_html/`: a JSON manifest plus
per-chapter content with embedded HTML, and a self-contained browser viewer.
Math is kept as LaTeX in `\(...\)` / `\[...\]` for client-side **MathJax 3 +
XyJax-v3** (xy-pic diagrams); it is not pre-rendered.

## Run

```sh
bash .claude/skills/sga1-convert-html/convert.sh
```

This (1) refreshes `01-normalized_tex/main.aux` with `pdflatex` if it is
missing or older than the sources, (2) runs the converter, (3) copies the viewer
into the output. Preview:

```sh
cd 02-converted_html && python3 -m http.server   # then open http://localhost:8000/
```

Run the converter alone (e.g. one chapter while debugging):

```sh
python3 .claude/skills/sga1-convert-html/convert.py --only chapter-01 --verify
```

## How it works

- **Numbering & cross-references come from `main.aux`** (`parse_aux`): every
  chapter/section/statement/equation number and `\ref`/`\eqref`/`\cite` target
  is read from the authoritative `\newlabel` / `\@writefile{toc}` / `\bibcite`
  records rather than re-derived. **Keep `main.aux` in sync** — re-run
  `convert.sh` (or `pdflatex`) after editing the LaTeX. Chapter ids are the
  in-source roman labels (`I`–`VI`, `VIII`–`XIII`; Exposé VII does not exist).
- **Macros are expanded to plain LaTeX** (`expand_math`, tables `MATH_0ARG` /
  `MATH_1ARG` / `MATH_NARG`). These mirror `sga1-macros.sty` (`\Spec`,
  `\SheafHom`, `\ZZ`, `\to`, `\leq`→`\leqslant`, `\mathcal`/`\cal`→`\mathscr`,
  the old-font `\rm`/`\it`/`\bf` switches, …) plus chapter-local `\newcommand`s.
  Keep these in sync with `sga1-macros.sty`. This honours the project rule of
  **not** injecting `tex.macros` into the HTML head.
- **`\xymatrix` is passed through unchanged** — the XyJax-safety rewrites were
  already applied upstream by [[sga1-inline-macros]]; the viewer loads XyJax-v3.

## SGA1-specific notes
- **Per-chapter bibliographies**: each exposé's `\thebibliography` (two-arg SMF
  form) renders inline at the end of that exposé.
- **Index**: `\printindex` (the auto-generated terminological index) is dropped
  in HTML; the manual `theindex` notation index renders as a list under an
  "Index des notations" page. The page-number terminological index is omitted
  (page numbers are meaningless in reflowed HTML) — a known gap.
- The `l → ℓ` (ell) math convention of the original is not reproduced (see
  [[sga1-inline-macros]]); a bare math `l` renders as `l`.

## Output schema (`02-converted_html/`)

```
fr.json                   manifest: {toc, default_page_id, default_chapter_id, chapters, anchor_index}
fr/chapters/<id>.json     {chapter_id, title, number, pages[]}
en.json / en/chapters/    same envelope; English content is empty stubs (French is the reference)
index.html viewer.css viewer.js   self-contained viewer (MathJax 3 SVG + XyJax-v3)
vendor/mathjax/es5 vendor/XyJax-v3  vendored MathJax-SVG + XyJax — renders offline, no CDN
```

- **English non-clobber guard**: `emit()` writes the empty English stubs only while the
  English side is still untranslated (`_en_manifest_is_stub` / `_en_chapter_is_stub`); once
  filled in, a re-run preserves the translation.
- **page**: `{id, title, html, blocks[], footnotes[], bibliography[]}` with the
  invariant `html == "\n".join(b.html for b in blocks)`.
- **block**: `{id, type, label, title, html}`; `type` ∈ `heading | paragraph |
  <theorem-env> | enonce | proof | equation | displaymath | list | table |
  bibliography | anchor`.
- Ids are readable: chapters `I`…`XIII`, front/back matter
  `preface`/`introduction`/`avertissement`/`index-notations`; sections `I-1`,
  `III-2`; statement/equation anchors keep their LaTeX label. `anchor_index`
  maps every element id → its page id so the viewer can resolve cross-page links.

## Verify

`convert.py --verify` reports chapter/page/block/equation/theorem/footnote/bib
counts, **unresolved** refs/cites, **leaked** `\commands` outside math, and JSON
validity. A clean run is 0 unresolved and 0 leaks. The downstream gate
[[sga1-check-errors]] loads the viewer pages in headless Chromium and reports
`mjx-merror`s — the authoritative MathJax/XyJax render check.
