# sga2/source

`../sga2.pdf` («Cohomologie locale des faisceaux cohérents et théorèmes de Lefschetz
locaux et globaux (SGA 2)», Advanced Studies in Pure Mathematics 2, North-Holland,
Amsterdam, 1968; Internet Archive scan with an OCR text layer) split into its
structural parts.

**The scan is 2-up**: it has 148 landscape *sheets*, each holding **two consecutive
book pages** side by side. From sheet 6 onward, sheet *s* holds book pages
(2s−10, 2s−9); book p. 1 is the right half of sheet 5. All "PDF sheets" below refer
to sheets of `../sga2.pdf`.

Because parts can begin or end mid-sheet, a sheet that carries the last page of one
part and the first page of the next is included in **both** files. The ten shared
sheets are 5, 14, 18, 26, 35, 43, 54, 60, 106 and 147. Apart from this deliberate
duplication the split is lossless: sheet ranges were extracted with `qpdf --pages`
(an object-level copy), so nothing was re-rendered, downsampled, or recompressed.

| File | PDF sheets | Printed pages | Chapter in `data/` |
|---|---|---|---|
| `frontmatter.pdf` | 1–5 | cover–[v] | series/title pages (sheet 1), imprint + editorial note (sheet 2), Table des matières (sheets 3–5 left) |
| `Introduction.pdf` | 5–7 | 1–5 | `I-0` — Introduction (starts on the right half of sheet 5) |
| `ExposeI.pdf` | 8–14 | 6–18 | `I` — Les invariants cohomologiques globaux et locaux relatifs à un sous-espace fermé |
| `ExposeII.pdf` | 14–18 | 19–26 | `II` — Application aux faisceaux quasi-cohérents sur les préschémas |
| `ExposeIII.pdf` | 18–26 | 27–42 | `III` — Invariants cohomologiques et profondeur |
| `ExposeIV.pdf` | 26–35 | 43–60 | `IV` — Modules et foncteurs dualisants |
| `ExposeV.pdf` | 35–40 | 61–71 | `V` — Dualité locale et structure des Hⁱ_Y(M) |
| `ExposeVI.pdf` | 41–43 | 72–76 | `VI` — Les foncteurs Ext•_Y(X ; F, G) et Ext•_Y(F, G) |
| `ExposeVII.pdf` | 43–46 | 77–83 | `VII` — Critères de nullité, conditions de cohérence des faisceaux Ext |
| `ExposeVIII.pdf` | 47–54 | 84–98 | `VIII` — Le théorème de finitude |
| `ExposeIX.pdf` | 54–60 | 99–110 | `IX` — Géométrie algébrique et géométrie formelle |
| `ExposeX.pdf` | 60–66 | 111–123 | `X` — Application au groupe fondamental |
| `ExposeXI.pdf` | 67–72 | 124–135 | `XI` — Application au groupe de Picard |
| `ExposeXII.pdf` | 73–90 | 136–171 | `XII` — Application aux schémas algébriques projectifs |
| `ExposeXIII.pdf` | 91–106 | 172–202 | `XIII` — Problèmes et conjectures |
| `ExposeXIV.pdf` | 106–147 | 203–284 | `XIV` — Profondeur et théorèmes de Lefschetz en cohomologie étale, par Mme M. Raynaud |
| `backmatter.pdf` | 147–148 | 285–287 | `index-notations` (p. 285), `index-terminologie` (pp. 286–287) |

Each printed page also carries a per-exposé running head («Exp. IV, p. 18») beside
the continuous number used above and in the Table des matières.

## Gaps

- **`preface.json` and `resume.json`** come from the 2005 SMF re-edition (Documents
  Mathématiques 4, ed. Y. Laszlo) and have no counterpart in this 1968 print; their
  ground truth is the SMF LaTeX source, not this scan.
