# sga1/source

`../sga1.pdf` (Springer Lecture Notes in Mathematics 224, 1971; 467 scanned pages with
an OCR text layer) split page-for-page into its structural parts.

The split is lossless: page ranges were extracted with `qpdf --pages` (an
object-level copy), so nothing was re-rendered, downsampled, or recompressed, and
shared resources are carried over only where a page needs them — the parts total
about the same bytes as the original.

| File | PDF pages | Printed pages | Chapter in `data/` |
|---|---|---|---|
| `frontmatter.pdf` | 1–20 | cover, i–xxii | `introduction` (PDF 5–13, pp. v–xiii) and `avertissement` (PDF 14–16, pp. xv–xvii); the rest is the series/title/imprint pages (PDF 1–4) and the Table des matières (PDF 17–20, pp. xix–xxii) |
| `ExposeI.pdf` | 21–48 | 1–28 | `I` — Morphismes étales |
| `ExposeII.pdf` | 49–77 | 29–57 | `II` — Morphismes lisses : généralités, propriétés différentielles |
| `ExposeIII.pdf` | 78–106 | 58–86 | `III` — Morphismes lisses : propriétés de prolongement |
| `ExposeIV.pdf` | 107–124 | 87–104 | `IV` — Morphismes plats |
| `ExposeV.pdf` | 125–164 | 105–144 | `V` — Le groupe fondamental : généralités |
| `ExposeVI.pdf` | 165–214 | 145–194 | `VI` — Catégories fibrées et descente |
| `ExposeVIII.pdf` | 215–247 | 195–227 | `VIII` — Descente fidèlement plate |
| `ExposeIX.pdf` | 248–280 | 228–260 | `IX` — Descente des morphismes étales. Application au groupe fondamental |
| `ExposeX.pdf` | 281–304 | 261–284 | `X` — Théorie de la spécialisation du groupe fondamental |
| `ExposeXI.pdf` | 305–330 | 285–310 | `XI` — Exemples et compléments |
| `ExposeXII.pdf` | 331–363 | 311–343 | `XII` — Géométrie algébrique et géométrie analytique, par Mme M. Raynaud |
| `ExposeXIII.pdf` | 364–459 | 344–439 | `XIII` — Propreté cohomologique des faisceaux d'ensembles et des faisceaux de groupes non commutatifs, par Mme M. Raynaud |
| `backmatter.pdf` | 460–467 | 440–447 | Index terminologique (PDF 460–465) and Index des notations (PDF 466–467) — see *Gaps* |

Printed page → PDF page is a uniform **+20** throughout the body. "Printed pages" above
is the continuous numbering used by the Table des matières; the pages themselves carry
only a per-exposé running number that restarts at 1 in each exposé (heads like
«VIII - 26 -»), and it is this per-exposé system that the two indexes cite.

There is no Exposé VII: it was never written, and the printed Table des matières
itself lists «Exposé VII : n'existe pas» (PDF p. 18).

## Gaps

- The two indexes (`backmatter.pdf`) have no counterpart chapters in `data/`.
