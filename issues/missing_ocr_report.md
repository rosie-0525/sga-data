# Missing OCR Report

> Investigation of `...` (ellipsis) patterns in transcribed/converted HTML
> and identification of genuinely missing content.
>
> Generated: 2026-07-07

## Executive Summary

All `...` occurrences across SGA 1, SGA 2, and SGA 3 are **legitimate** — they reflect
Grothendieck's characteristic writing style or editorial annotations (N.D.E.), not
OCR truncation artifacts. No content was lost during conversion from transcription
to HTML/JSON.

However, a significant gap was found: **SGA 3 exposés XXI–XXVI plus front matter
have not been transcribed at all**, despite source PDFs being available.

---

## 1. Ellipsis (`...`) Investigation

### Methodology

- Searched all files in `*/01-transcribed/`, `*/01-normalized_tex/`,
  and `*/02-converted_html/data/{en,fr}/chapters/` for literal `...`
- Classified each occurrence as: legitimate mathematical ellipsis, possible OCR
  truncation, or editorial note (N.D.E.)
- Cross-referenced English ↔ French versions and, where available, original TeX
  source to verify fidelity

### Results by Volume

| Volume | Files with `...` | Total occurrences | OCR truncation? |
|--------|-------------------|-------------------|-----------------|
| SGA 1  | 6 chapters        | ~20               | **None**        |
| SGA 2  | 4 chapters        | ~12               | **None**        |
| SGA 3  | 8 chapters        | ~22               | **None**        |

### Classification Breakdown

All occurrences fall into these legitimate categories:

#### a) Mathematical list continuation (`etc...`, `resp. ...`)

Standard French mathematical convention. Examples:

| Volume | Chapter | Context |
|--------|---------|---------|
| SGA 3  | I §1.7  | Section heading: `Objets Hom, Isom, ...` |
| SGA 3  | IV §4.4 | `4.4.3, 4.4.6, 4.4.9, etc...` |
| SGA 3  | VIB §2  | `d'être régulier, réduit, de Cohen-Macaulay, etc...` |
| SGA 2  | X §2.3  | `(resp. ...), there exist an open set U and a locally free coherent Module E (resp. ...)` |
| SGA 3  | XII §1.5| `rang réductif (resp. ...) de G_{k̄}` |

#### b) Grothendieck's rhetorical trailing-off

Characteristic of his expository style — deliberately open-ended thoughts:

| Volume | Chapter | Context |
|--------|---------|---------|
| SGA 1  | I §1    | `the augmentation ideal in this last one...). The sheaf` |
| SGA 1  | I §7    | `Lemmas 9 and 10 should adapt without difficulty. More generally, ...` |
| SGA 1  | I §10   | `even in the case of composite extensions of number fields...` |
| SGA 3  | I §1.7  | `un objet de C au-dessus de S, ...` (end of notation discussion) |
| SGA 3  | I §2.3.4| `on le note Norm_G(E) ...` |
| SGA 3  | VIA §2  | `d'exemplaires de G^0⊗_k K, qui est irréductible...` (proof by contradiction) |
| SGA 3  | V §8    | `possède une quasi-section... Le processus doit s'arrêter` |

#### c) N.D.E. editorial notes (SGA 3 only)

Open-ended editorial reminders in footnotes of Exposé VIII:

| Location | Note |
|----------|------|
| VIII fn.2 | `On a ajouté la numérotation 1.0, 1.0.1, ...` |
| VIII fn.7 | `considéré dans X 5.10 et 5.11 ...` |
| VIII fn.33 | `tenir compte des ajouts faits dans VI_B ...` |
| VIII fn.37 | `Mettre ceci en évidence dans les Exp. V et VI_A...` |

#### d) TeX source confirmation (SGA 1 & SGA 2)

For SGA 1 and SGA 2, the original TeX sources confirm that every `...` in the HTML
exists verbatim in the TeX. For example:

```tex
% SGA1, chapter-01.tex, line 808:
g\'en\'eralement, ...

% SGA2, chapter-01.tex, line 381:
Compte tenu du \ref{I.2.11} cela prouve encore \ref{I.2.13} (i)...

% SGA2, chapter-10.tex, line 110:
(resp. ...), tels que $L_U(E) \simeq \Ee$ (resp. ...).
```

### Conclusion on `...`

**No OCR truncation was found.** Every instance of `...` is a faithful reproduction
of the original text. The French ↔ English converted versions match exactly.

---

## 2. Actually Missing Content

### SGA 3: Missing Exposés XXI–XXVI + Front Matter

The chapter map (`sga3/chapter-map.json`) lists **28 entries** (26 exposés +
avertissement + introduction). Source PDFs exist for all of them. However, only
**22 exposés** have been transcribed and converted.

| Missing chapter | Source PDF | Status |
|-----------------|-----------|--------|
| `avertissement` | `origIntroAG.pdf` | ❌ Not transcribed |
| `introduction`  | `origIntroAG.pdf` | ❌ Not transcribed |
| `XXI`           | `origExpo21.pdf`  | ❌ Not transcribed |
| `XXII`          | `origExpo22.pdf`  | ❌ Not transcribed |
| `XXIII`         | `origExpo23.pdf`  | ❌ Not transcribed |
| `XXIV`          | `origExpo24.pdf`  | ❌ Not transcribed |
| `XXV`           | `origExpo25.pdf`  | ❌ Not transcribed |
| `XXVI`          | `origExpo26.pdf`  | ❌ Not transcribed |

These 8 entries are completely absent from both `sga3/01-transcribed/` and
`sga3/02-converted_html/data/{en,fr}/chapters/`.

### SGA 1 & SGA 2: Complete

Both SGA 1 and SGA 2 appear to have full coverage:
- SGA 1: 15 chapters in converted HTML (I–XIII + avertissement, introduction, preface)
- SGA 2: 19 chapters in converted HTML (I–XIV + I-0, index-notations,
  index-terminologie, preface, resume)

---

## 3. Recommendations

1. **No action needed on `...`** — all occurrences are intentional
2. **Transcribe SGA 3 exposés XXI–XXVI** from source PDFs (the "new edition" exposés)
3. **Transcribe SGA 3 front matter** (avertissement + introduction) from
   `origIntroAG.pdf`
