# sga4.5/source

`../sga4.5.pdf` (Springer LNM 569, 1977; 317 scanned pages with an OCR text layer)
split page-for-page into its structural parts. `chapter-map.json` is the machine-readable
version of the table below, plus the history and gaps.

The split is lossless: pages were extracted with `pdfseparate` and reassembled with
`pdfunite`, so nothing was re-rendered, downsampled, or recompressed. (The parts total
more bytes than the original only because `pdfunite` re-embeds the OCR text layer's fonts
per file.)

| File | PDF pages | Printed pages | Chapter in `data/` |
|---|---|---|---|
| `frontmatter.pdf` | 1–5 | cover, i–iv | `introduction` (the rest is title/imprint/TOC) |
| `FilDAriane.pdf` | 6–8 | 1–3 | `fil-dariane` — Un fil d'Ariane pour SGA 4, SGA 4½ et SGA 5 (see *Gaps*) |
| `ExposeI.pdf` | 9–80 | 4–75 | `I` — Cohomologie étale : les points de départ [Arcata] |
| `ExposeII.pdf` | 81–114 | 76–109 | `II` — Rapport sur la formule des traces |
| `ExposeIII.pdf` | 115–133 | 110–128 | `III` — Fonctions L modulo ℓⁿ et modulo p |
| `ExposeIV.pdf` | 134–158 | 129–153 | `IV` — La classe de cohomologie associée à un cycle |
| `ExposeV.pdf` | 159–172 | 154–167 | `V` — Dualité |
| `ExposeVI.pdf` | 173–237 | 168–232 | `VI` — Applications … aux sommes trigonométriques |
| `ExposeVII.pdf` | 238–266 | 233–261 | `VII` — Théorèmes de finitude (incl. Illusie's appendix, 257–266) |
| `ExposeVIII.pdf` | 267–316 | 262–311 | `VIII` — Catégories dérivées, état 0 (Verdier) |
| `backmatter.pdf` | 317 | 312 | `erratum` — Erratum pour SGA 4, tome 3 |

Printed page → PDF page is a uniform **+5** throughout.

## History

The original scan was 351 pages: PDF pages 115–148 were a duplicate copy of 81–114
(the Rapport, printed pp. 76–109), verified identical page-for-page on the extracted
text layer. That duplicate has since been removed from `../sga4.5.pdf` itself
(351 → 317 pages), which is why the offset above is a flat `+5` rather than jumping
partway through.

## Gaps

- **«Un fil d'Ariane pour SGA 4, SGA 4½ et SGA 5»** (`FilDAriane.pdf`) is the first item
  in the book's Table des Matières but has no counterpart in the LaTeX source
  (`sga4.5/sga4.5/`, which contained only `sga4.5-note`, `sga4.5-intro`, `sga4.5-1..8` and
  `sga4.5-erratum`) — a gap inherited from upstream. Its chapter
  `data/*/chapters/fil-dariane.json` was therefore transcribed (and translated) directly
  from this scan on 2026-08-01, unlike the other chapters, which derive from the LaTeX
  source.
- **`data/*/chapters/bibliographie.json`** comes from the LaTeX source's
  `\bibliography{sga-sources}` and has no counterpart in the original scan, where
  references sit inside each exposé.
