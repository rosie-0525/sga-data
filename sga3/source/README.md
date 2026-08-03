# sga3/source

The three tomes of «Schémas en groupes (SGA 3)» — `../sga3-1.pdf`, `../sga3-2.pdf`,
`../sga3-3.pdf` (Springer Lecture Notes in Mathematics 151, 152, 153; 1970; scans with
an OCR text layer) — split page-for-page into their structural parts.

The split is lossless: page ranges were extracted with `qpdf --pages` (an
object-level copy), so nothing was re-rendered, downsampled, or recompressed, and
shared resources are carried over only where a page needs them — the parts total
about the same bytes as the original.

Printed page → PDF page is uniform within each tome: **+16** in tome 1, **+10** in
tome 2, **+9** in tome 3 (verified against the printed running numbers on every
numbered page; exposé title pages are unnumbered but counted).

## Tome 1 (`../sga3-1.pdf`, LNM 151, 580 pages)

| File | PDF pages | Printed pages | Chapter in `data/` |
|---|---|---|---|
| `frontmatterTome1.pdf` | 1–16 | cover, i–xv | `avertissement` (PDF 5–6, pp. iv–v) and `introduction` (PDF 7–11, pp. vi–x); the rest is the series/imprint/title pages (PDF 1–4) and the Table des matières of the tome (PDF 12–16, pp. xi–xv) |
| `ExposeI.pdf` | 17–58 | 1–42 | `I` — Structures algébriques. Cohomologie des groupes, par M. Demazure |
| `ExposeII.pdf` | 59–98 | 43–82 | `II` — Fibrés tangents – Algèbres de Lie, par M. Demazure |
| `ExposeIII.pdf` | 99–175 | 83–159 | `III` — Extensions infinitésimales, par M. Demazure |
| `ExposeIV.pdf` | 176–266 | 160–250 | `IV` — Topologies et faisceaux, par M. Demazure |
| `ExposeV.pdf` | 267–302 | 251–286 | `V` — Construction de préschémas quotient, par P. Gabriel |
| `ExposeVIA.pdf` | 303–333 | 287–317 | `VIA` — Généralités sur les groupes algébriques, par P. Gabriel |
| `ExposeVIB.pdf` | 334–426 | 318–410 | `VIB` — Généralités sur les préschémas en groupes, par J.E. Bertin |
| `ExposeVIIA.pdf` | 427–491 | 411–475 | `VIIA` — Étude infinitésimale des schémas en groupes, par P. Gabriel |
| `ExposeVIIB.pdf` | 492–578 | 476–562 | `VIIB` — Étude infinitésimale des schémas en groupes : groupes formels, par P. Gabriel |
| `backmatterTome1.pdf` | 579–580 | 563–564 | Index des notations du tome I — see *Gaps* |

## Tome 2 (`../sga3-2.pdf`, LNM 152, 664 pages)

| File | PDF pages | Printed pages | Chapter in `data/` |
|---|---|---|---|
| `frontmatterTome2.pdf` | 1–10 | cover, i–ix | series/imprint/title pages (PDF 1–4) and the Table des matières of the tome (PDF 5–10) |
| `ExposeVIII.pdf` | 11–46 | 1–36 | `VIII` — Groupes diagonalisables, par A. Grothendieck |
| `ExposeIX.pdf` | 47–86 | 37–76 | `IX` — Groupes de type multiplicatif : homomorphismes dans un schéma en groupes, par A. Grothendieck |
| `ExposeX.pdf` | 87–136 | 77–126 | `X` — Caractérisation et classification des groupes de type multiplicatif, par A. Grothendieck |
| `ExposeXI.pdf` | 137–189 | 127–179 | `XI` — Critères de représentabilité. Applications aux sous-groupes de type multiplicatif des schémas en groupes affines, par A. Grothendieck |
| `ExposeXII.pdf` | 190–258 | 180–248 | `XII` — Tores maximaux, groupe de Weyl, sous-groupes de Cartan, centre réductif des schémas en groupes lisses et affines, par A. Grothendieck |
| `ExposeXIII.pdf` | 259–305 | 249–295 | `XIII` — Éléments réguliers des groupes algébriques et des algèbres de Lie, par A. Grothendieck |
| `ExposeXIV.pdf` | 306–358 | 296–348 | `XIV` — Éléments réguliers : suite, application aux groupes algébriques, par A. Grothendieck |
| `ExposeXV.pdf` | 359–493 | 349–483 | `XV` — Compléments sur les sous-tores d'un préschéma en groupes. Application aux groupes lisses, par M. Raynaud |
| `ExposeXVI.pdf` | 494–541 | 484–531 | `XVI` — Groupes de rang unipotent nul, par M. Raynaud |
| `ExposeXVII.pdf` | 542–641 | 532–631 | `XVII` — Groupes algébriques unipotents. Extensions entre groupes unipotents et groupes de type multiplicatif, par M. Raynaud |
| `ExposeXVIII.pdf` | 642–663 | 632–653 | `XVIII` — Théorème de Weil sur la construction d'un groupe à partir d'une loi rationnelle, par M. Artin |
| `backmatterTome2.pdf` | 664 | 654 | Index des notations (tome 2) — see *Gaps* |

## Tome 3 (`../sga3-3.pdf`, LNM 153, 538 pages)

| File | PDF pages | Printed pages | Chapter in `data/` |
|---|---|---|---|
| `frontmatterTome3.pdf` | 1–9 | cover, i–viii | series/imprint/title pages (PDF 1–4) and the Table des matières of the tome (PDF 5–9) |
| `ExposeXIX.pdf` | 10–43 | 1–34 | `XIX` — Groupes réductifs — généralités, par M. Demazure |
| `ExposeXX.pdf` | 44–93 | 35–84 | `XX` — Groupes réductifs de rang semi-simple 1, par M. Demazure |
| `ExposeXXI.pdf` | 94–164 | 85–155 | `XXI` — Données radicielles, par M. Demazure |
| `ExposeXXII.pdf` | 165–271 | 156–262 | `XXII` — Groupes réductifs : déploiements, sous-groupes, groupes quotients, par M. Demazure |
| `ExposeXXIII.pdf` | 272–331 | 263–322 | `XXIII` — Groupes réductifs : unicité des groupes épinglés, par M. Demazure |
| `ExposeXXIV.pdf` | 332–418 | 323–409 | `XXIV` — Automorphismes des groupes réductifs, par M. Demazure |
| `ExposeXXV.pdf` | 419–434 | 410–425 | `XXV` — Le théorème d'existence, par M. Demazure |
| `ExposeXXVI.pdf` | 435–526 | 426–517 | `XXVI` — Sous-groupes paraboliques des groupes réductifs, par M. Demazure |
| `backmatterTome3.pdf` | 527–538 | 518–529 | Index des notations (PDF 527–528) and Index terminologique of the whole seminar (PDF 529–538) — see *Gaps* |

## Gaps

- The indexes (`backmatterTome*.pdf`) have no counterpart chapters in `data/`.
- The `avertissement` and `introduction` chapters (in `frontmatterTome1.pdf`) cover
  the whole seminar; tomes 2 and 3 open with only their own Table des matières.
