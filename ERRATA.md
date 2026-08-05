# Errata — printed-edition anomalies noted during transcription

Sites where the **source PDFs themselves** print something suspect or wrong.
Most of this file covers the 2011 SGA 3 re-edition typesetting under
`sga3/source/`, collected during the 2026-07-24 repair/completion pass
over exposés XXI, XXII, XXIV and XXVI (each checked against the PDF text layer,
ambiguous glyphs zoomed at high resolution); a closing section covers SGA 6.

Policy applied: the transcription reproduces the print **as is** unless the
misprint is mathematically unambiguous; the handful of silent corrections made are
listed first per exposé so they can be audited. Line numbers below refer to the
intermediate transcription HTML that has since been removed from the tree (it is
in git history through `a2317a4`); the text itself now lives in
`sga3/data/fr/chapters/`, where each site is findable by the
quoted wording.

---

## Exposé XXI — Données radicielles (`XXI.html`, source `ExposeXXI.pdf`)

### Corrected (unambiguous)
- line 91, Lemme 1.1.4 — PDF prints "alors α = s" (and `s` for `β` inside its own
  proof); transcribed as `α = β`, per the proof's conclusion.
- line ~2242, Définition 6.8.1 — PDF prints "Soient ℛ = … et ℛ = …" (same letter
  twice); second occurrence transcribed `ℛ′`.
- line 1293 — PDF's doubled subscript `α_{m_m}` normalized to `α_m`.
- 7.4.6 — a stray "Â" glyph printed after the E_Δ list was omitted as a production
  artifact.

### Kept as printed (suspect — candidates for a future errata pass)
- line 538 — `ℓ(a_i)` (likely `ℓ(α_i)`).
- line 821 — "Soit w ∈ W_R, L'ordre… entier > 0 n" (likely `W_{R′}`).
- line 867 — `R ∩ (ℚ·S′)` (`S′` leftover, `Δ′` expected).
- line 923 — `w(α) − r = w′(α) − r − …` (leftover draft variable `r`).
- line 1197 — `w(u) − u = a_w r + b_w s`; line 1204 — `(u, s) > 0`
  (`r`, `s` leftovers for `α*`, `β*`).
- line 1209 — `ord_S(γ)`.
- line 1255 — `T_iT_jT_i = T_i` (should end `T_j`).
- line 1335 — `w(β₀) ∈ P` (the standard argument wants `−P`).
- line 1349 — `α_i = w₀(α₀)` (means `α₁`).
- line 1358 — `(M, M*, R, R)` (second `R` missing its `*`).
- line 1714 — roman `V(R)` where the exposé elsewhere uses script `𝒱(R)`.
- line 1804 — `ℛ₀ = (M*₀, M*₀, ∅, ∅)` (first component likely `M₀`).
- line 2079 — `long(α+β)(α+β)` (missing `*`).

---

## Exposé XXII — Groupes réductifs : déploiements, sous-groupes, groupes quotients (`XXII.html`, source `ExposeXXII.pdf`)

### Corrected (unambiguous)
- 5.5.2 proof — "X = 0" → `x = 0`.
- 5.5.4 — "f_ij(Xⁱyʲ)" → `XⁱYʲ`.
- 5.5.7 proof — "exp(−yᵢYᵢ)" → `Xᵢ`; the Q′ᵢ formula's garbled argument list
  restored.
- 5.6.1 — "où R″={r}" → "ou"; "préschémsa" → "préschémas".
- 5.6.9 proof — "h s'annule" → `g`.
- 5.9.4 proof — "Si n ∈ T(k)" → `n ∉ T(k)` (zoomed: the print really has ∈; the
  argument requires ∉).
- 5.9.5 proof — "×_{Sᵢ}" → `×_{Sᵢ′}` (second occurrence); "B_{R′}" → `B_{R′⁺}`.
- 5.10.1 proof — first "R′⁺ ∩ −R′⁺ = R′" → `∪` (zoomed: print has ∩ twice).

### Kept as printed (suspect)
- 5.5.2 — "α(t)ⁱβ(t)ʲ − γ(t) = 1" (checked: actually correct, matches Exp. XIX 4.13).
- 5.8.3 proof — citation "5.12" resolves to nothing (probably 5.1.2); left as
  plain text, unlinked.
- 5.9.3 proof — "D'après qui précède"; "isomorphisme Bᵘ ≃ Opp(G)" (the diagram
  shows Opp(B)).
- 5.10.6 proof — "(R)" and "(H_{R′}) est le tore maximal…" (zoomed; probably
  rad(H_{R′})).
- 5.11.5 proof — "H ∈ ℋ₀(S′)" (zoomed; probably ℋ_c).
- 6.1.2 proof — "rad(T) → T/T′" (probably rad(G)).
- 6.1.5 — the display's second "=" (arguably ⊂).
- 6.2.6 — "système de racines de G par rapport à T" (arguably dér(G)/T′).
- 6.3.3 — "sous-tores de corad(H)" (probably corad(G)).
- 6.3.4 — "tore maximal de G" (probably de H).
- 5.7.14 and 5.8.1 — unbalanced parentheses reproduced as printed.
- §4 (pre-existing text) — "(cf. 1.19)" cites an item that does not exist (§1
  ends at 1.17 in the print too); kept as printed, unlinked.

---

## Exposé XXIII — Groupes réductifs : unicité des groupes épinglés (`XXIII.html`)

### Corrected (unambiguous)
- Corollaire 5.2 — the print cites "de même type (Exp. XII, 2.6)", but Exp. XII
  §2 (Le groupe de Weyl) has no 2.6; the intended target is **Exp. XXII 2.6**
  (unicity of the radicielle data underlying the "type"). Text and link
  corrected to "Exp. XXII, 2.6".

---

## Exposé XXIV — Automorphismes des groupes réductifs (`XXIV.html`, source `ExposeXXIV.pdf`)

### Corrected (unambiguous)
- line 200 — print reads "éléments de H³(G, ℒie(G/k)) V)" with a dropped symbol
  and unbalanced paren; `⊗ V` supplied (the object per Exp. III 3.8). This is
  the only place a glyph the print doesn't clearly show was inserted.

### Kept as printed (suspect)
- line 304, Cor. 2.3 — `Isom_{S-gr.}(G, B; B′, B′)` (print really has B′,B′;
  G′,B′ expected).
- line 637, Rem. 3.16.7 — "On détermine explicitement a_G" (s_G is meant).
- line 743, 4.3.1 — `rev(G) = P/ad(Ép_S(G))` (print has G; ℛ expected).
- line 1091, 7.1.3 — `q_{i,i+p} = c_{q,i}` (likely a_{i,i+q}).
- line 1114, 7.1.4 — final term `f_α(α(t)u_α + α(t)α(t)v_α)` (text layer
  confirms; the argument suggests α(t′)u_α).
- line 1287, 7.4.3 — `α*(sⁿ)⁻¹` (print has s; z expected).
- lines 259 and 1324 — Prop. 1.21 proof / Prop. 8.1(i) use
  `Fib(S, H) ≃ H¹_ét(S, H)` with H as printed.

---

## Exposé XXVI — Sous-groupes paraboliques des groupes réductifs (`XXVI.html`, source `ExposeXXVI.pdf`)

### Kept as printed (suspect)
- line 45 — "théorème de conjugaison (5.14)" (no 5.14 exists in the exposé);
  line 47 — "telle qu'elle est exposés".
- line 99, Prop. 1.4 proof — "−α = s + (−(α+β))" and "contenant α et s"
  (β expected, the print has "s" twice).
- line 159, Prop. 1.12 — "un épinglage de ℰ adapté à P" (presumably de G).
- line 516, 3.15 — "triplets P ⊃ L ⊂ T" (presumably P ⊃ L ⊃ T).
- line 687, 4.2.4 — "morphisme canonique Lie(P) ⊕ Lie(G) → Lie(G)"
  (Lie(Q) expected).
- line 743, 4.2.7 — "A₂ = R₀ ∩ R₁" (A₂ = R₀ ∩ R₂ expected).
- line 787, 4.3.2 — "On doit prouver R′₁ = −R₂" (R₁ expected).
- line 1016, 5.1.10 — the second épingle prints "et  = (matrix)" with the u_β
  label visibly missing in the edition; reproduced as printed.
- line 1095, Déf. 5.6 — "chaque fois que G est un sous-groupe parabolique… on a
  Q = P" (the print's G/Q mix-up kept).
- line 1155, 5.11 — "rad^u(P′)(S′) ≠ e" (the unexplained S′ kept).
- line 1324, 6.18 — "si T est un tore maximal P, T_dép est un tore maximal…".
- line 1377, 7.4.2 — "s_α ∈ Norm_{L_α}(Q)(S)/L(S) ∈ W".
- line 1429, 7.8 — "Notons t_α(H)" (genuinely prints t_α twice here, though
  7.9/7.13 use t_r; both kept exactly as printed).
- line 1513, 7.15 — "corps résiduel de s₀".

---

# SGA 2 — sites corrected in the 2026-08-02 reader review

The volume's reference is the SMF re-edition source
`sga2/source/smf_doc-math_4_01.tex`, whose `\sisi{a}{b}` macro records both
readings at each annotated site (`a` = the original 1968 print, `b` = the SMF
correction). Each correction below carries an **editorial note**
(`kind: "editorial"`, markers `*`, `†` per page) on the French page recording
the print reading; the English page follows the corrected French.

| Page | Print reads | Correction | Evidence |
|---|---|---|---|
| II (block 18) | «(EGA III 1.4.3.2)» also for the case i ⩾ 2 | «EGA III 1.4.3.1» | `\sisi{2}{1}` |
| II (Prop. 9 proof) | `t_{n'} = 0` | `t_{n', n} = 0` | `\sisi{t_{n'}}{t_{n', n}}` |
| III-2 (proof after 2.4) | `Ext_A^{i-1}(N, M)=0 si i ⩽ n−1` | `Ext_A^{i-1}(N, M/f₁M)=0 si i ⩽ n` | the print's own slip (no `\sisi`); the induction runs on `M/f₁M` and the next sentence uses `i ⩽ n` |
| III-3 (proof of 3.3) | `(H_Y(X, F))^{p+q}` | `H_Y^{p+q}(X, F)` | `\sisi` |

Note on the first site: the reviewer's comment stated the direction as
"original was 1.4.3.1, corrected to 1.4.3.2", but both the `\sisi{2}{1}`
annotation and the applied proposal history show the print read **1.4.3.2**
and the re-edition corrects the second citation to **1.4.3.1**; the note
records the direction supported by the source.

Translation/transcription repairs made in the same pass (not print anomalies):
Remarque 30 in I-2 (fr «sur x» → «sur X», comma after «faisceau», en sentence
retranslated "is a sheaf, an extension to X …"); the equation tags
(7.2)–(7.5) of Exposé II section 7 renumbered (7.3)–(7.6) in the English page
(the French had already been aligned with the SMF numbering) together with all
in-text `eqref`s and the blocks' `label` fields; the dangling
«note (1), page )» after "SERRE, op. cit." in III.2.8 trimmed in both
languages (the print resolves the note and page by reference; the transcription
had lost the numbers); an in-body translator's note (N.d.T.) added in both
languages to Lemme III.2.1 (v), noting that 𝔪_𝔭 denotes 𝔭A_𝔭.

---

# SGA 4½ — anomalies in the source text

The volume's reference is the source PDFs under `sga4.5/source/`
(`ExposeI.pdf` … `ExposeVIII.pdf`). The introduction sites below were checked
against the French PDF on 2026-07-31, when the volume's reference was still the
LaTeX transcription in the `sga4.5/sga4.5/` submodule (removed since; the file
names quoted in that section refer to it). The exposé sites in the last section
come from the 2026-08-01 reader review.

## Introduction, 3rd paragraph — three grammatical slips

> Le "Rapport sur la formule des traces" contient une démonstration
> **complété** de la formule des traces … Ce Rapport devrait permettre à
> **utilisateur** d'oublier SGA 5, qu'on pourra considérer comme une série de
> **digression**, certaines très intéressantes.

All three are **corrected** in `sga4.5/data/fr/chapters/introduction.json`
(block 3) and in `sga4.5/sga4.5/sga4.5-intro.tex`:

- `complété` → `complète` — agreement with the feminine *démonstration*.
- `à utilisateur` → `à l'utilisateur` — the elided article is missing.
- `digression` → `digressions` — *une série de* takes a plural count noun, and
  the apposition *certaines très intéressantes* (feminine plural) has no
  antecedent without it. The English side already read "a series of
  digressions".

The last of these is signalled to the reader: the French page carries the
editorial note `fn-introduction-1` (`kind: "editorial"`, marker `*`) recording
the printed singular, listed apart from the volume's own footnotes — including
the editor's 1976 notes in Exposé VIII, which are part of the print. The first
two are silent, being plain typography.

## Introduction, 4th paragraph — one more agreement slip

> L'exposé "La classe de cohomologie associée à un cycle" définit **cette
> classes** dans divers contextes …

`cette classes` → `cette classe`, **corrected** in
`sga4.5/data/fr/chapters/introduction.json` (block 4) and in
`sga4.5/sga4.5/sga4.5-intro.tex`. The demonstrative resumes the singular *la
classe de cohomologie* of the exposé's title just quoted, so the noun, not the
demonstrative, carries the slip. The English "defines these classes" is
corrected to "defines this class" to match.

The correction is silent, being plain typography.

Not an anomaly, though a proposal flagged it: the next paragraph's *je renvoie
à leur introduction respective* is the original wording and is idiomatic French
— the distributive singular after *respectif*. It stands; the English renders
it "their respective introductions".

## Fil d'Ariane, 2nd paragraph — one agreement slip

The chapter `fil-dariane` («Un fil d'Ariane pour SGA 4, SGA 4½ et SGA 5»,
printed pp. 1–3) has no counterpart in the LaTeX source and was transcribed
directly from `FilDAriane.pdf` on 2026-08-01. One site is corrected:

> Elle est commencée par Artin dans l'exposé IX de SGA 4 ; des conséquences,
> quant à la dimension **cohomologiques**, sont données dans X.

`cohomologiques` → `cohomologique` — agreement with the singular *la
dimension*. Signalled to the reader by the editorial note `fn-fil-dariane-1`
(`kind: "editorial"`, marker `*`) in
`sga4.5/data/fr/chapters/fil-dariane.json`.

Kept as printed: the odd reference punctuation «Publ. Math. IHES 36 (1969)
p. 23-58-§3» in the 3rd paragraph. Silent, being plain typography: typewriter
quotes and dashes set as “…” and –, and «Math.349» spaced as «Math. 349» in
bibliography entry [2].

## Exposés II–VIII — sites corrected in the 2026-08-01 reader review

Each of the sites below prints something the French page now corrects, and each
carries its own **editorial note** (`kind: "editorial"`) on that page recording
what the print reads — so the list is a finding aid, not the record itself. The
notes are marked `*`, `†`, `‡`, `§` per page and listed apart from the volume's
own footnotes (including the editor's 1976 notes in Exposé VIII).

| Page | Print reads | Correction |
|---|---|---|
| II:6 | «aux deux **particuliers** 5.1 et 5.2» | «aux deux **cas** particuliers» |
| III:1 | `\Gamma_ext(𝒢)` in Lemme 1.3 | `\Gamma_ext^n(𝒢)`, per the definition recalled in 1.2 |
| III:1 | `Γ^iK′ ⊗ Γ^iK″` after 1.9, in the simple and in the double complex alike | second exponent `j`, as `i+j=n` and the trace formula that follows require |
| III:2 | «à **degré** positifs» in 2.8 | «degrés» |
| III:3 | «une section **de** *x* de Ker(Φ−1)» in 3.3 b) | the spurious «de» dropped |
| III:3 | «les faisceaux **correspondant** sur S̄_ét» in 3.3 c) | «correspondants» |
| III:4 | `Σ_{x∈𝔸¹ᶠ} tr(F*, π_*ℤ/2)` | subscripts `x` added, as the trace formula requires |
| IV:2 | «génériques de Y **nour** ramène» | «nous ramène» |
| IV:2 | «D'après **(iv)**» | «(iii)» — the only assertion giving the formula that follows |
| V:3 | «par **(2.2.1)**» | (3.2.1) |
| V:3 | `R pr_{2*}𝒢` in the last two terms of (3.2.2) | `R pr_{1*}𝒢` |
| V:3 | `{ℬ'}¹ = ker(d)` | `ℬ¹` — ℬ′ is the complex thereby obtained |
| VI:1 | «les **objects**» | «objets» |
| VI:1 | «d'**ambiguité**» | «ambiguïté» |
| VI:1 | `ℱ(χ, f)` in 1.8(iii) | `ℱ(χ, f₀)`, per the notations of 1.7 d) |
| VI:1 | «**ques** divers types» | «que divers types» |
| VI:2 | «n'était pas **exclus**» | «exclu» (agreement with `J = ∅`) |
| VI:3 | «à *n* **variable**» | «variables» |
| VI:3 | «le nombre d'hyperplans **rationnel**» | «rationnels» |
| VI:4 | «est **envoyé** isomorphiquement» | «envoyée» (la droite *D*) |
| VI:4 | «modérée **a** l'infini» | «à l'infini» |
| VI:5 | «diverses **façon** équivalentes» | «façons» |
| VI:5 | «un corps de **nombre**» | «nombres» |
| VI:5 | «celles **telle que**» | «telles que» |
| VII:1 | «**à** l'avantage de remplacer» | «a l'avantage» (the verb *avoir*) |
| VII:2 | closing parenthesis missing | added |
| VII:3 | «On suppose que X ⟨⟩ de type fini» | «est» added |
| VII:3 | `R^iΨ_η(ℱ)` in the Leray sequence (1) | `R^qΨ_η(ℱ)` |
| VII:5 | «l'image inverse D̃ de D dans **Y**» | «dans Ỹ» |
| VII:5 | `f_i : Y∖D_i → **D**` | `→ Y` |
| VII:5 | `sp(u′) sp(u″) = sp(u u′)` | `sp(u′) sp(u) = sp(u u′)` |
| VII:5 | «image de **s** (resp. **t**) dans S» | `s′`, `t′` |
| VIII:1 | `β∘α = β∘T^i(α)` | `T^i(β)∘α` — α takes values in `T^i(Y)` |
| VIII:1 | `d_{Y•}` in the lower-right corner of the matrix | `d_{Z•}` |
| VIII:1 | `F^{i+-}(X)` | `F^{i+1}(X)` |
| erratum | «**Arpès** l'énoncé» | «Après» |

### Kept as printed

- **II 4.4** — the description of `DF_parf(Λ)` reads «tels que les **Gr^p_F(Λ)**
  soient dans D_parf(Λ) et presque tous nuls» (`ExposeII.pdf` p. 22). The
  argument wants `gr^p_F(K)` — Λ carries no filtration — but the print has Λ,
  and it stands on both sides. (This clause had been lost from the French page
  altogether in transcription; it is restored here as printed.)
- **VI 4.4** — «τ(χ,ψ)·τ(χ⁻¹,ψ⁻¹) = q, i.e. |τ(χ,ψ)| **= q**». The second
  equality wants `q^{1/2}`; the print has `q` (checked at high resolution,
  `ExposeVI.pdf` p. 30). Transcribed as printed on both sides.
- **VI 7.19** — «**Il s'agit** donc sur `H_c^{n-1}(V_a, ℱ(ψσ))`» for *Il agit*.
  Kept in French; the English renders it "It therefore acts on".
- **VI 7.19** — the print writes the symmetric group `S_m` in 7.19 and `S_n` in
  7.20; the transcription uses `S_n` throughout.
- **VII 5.1.3(i)** and **VI 7.19** aside, the review's remaining corrections were
  to *this edition's* transcription and translation (leaked `\sf`, `G+m^I` for
  `𝔾_m^I`, `X-0` for `X_0`, a doubled clause, four English headings printing
  their number twice, and the `\label`/`\ref` leakage repaired in Exposé VIII
  §§1–2), not to the print, and so are not errata.

---

# SGA 5 — anomalies in the printed typescript

## Exposé V, p. 234 — "fonctions" for "foncteurs"

Below Définition 5.1.3:

> Il est alors clair que les **fonctions** canoniques P_AR^n, P_AR^f …

The typescript prints "fonctions" — verified on the page image, not just the
OCR layer. The objects are functors between categories, and the sentence
concludes «… sont des équivalences de catégories». **Corrected** to
«foncteurs» in `sga5/data/fr/chapters/V.json` (page V-s6) on 2026-08-05
under the policy above; the English side already reads "the canonical
functors". Surfaced by `glossary_check.py` (FR «fonction» with no accepted
rendering in the EN block).

---

# SGA 6 — anomalies in the printed 1971 edition

Flagged during the English translation, checked against the scans in
`sga6/source/` on 2026-07-18. All are kept **verbatim** in both
language versions of the viewer data; this is the record of what they are and
what was almost certainly meant. (Migrated here from `sga6/typos.md` on
2026-07-27, when that file's other section — three transcription remnants in
Exposé X, fixed 2026-07-18 — was verified clean in fr and en and dropped.)

## Sites corrected in the 2026-08-02 reader review

Unlike the kept-verbatim list above, each site below is now **corrected** in
the data, and (where the print itself is at fault) carries an **editorial
note** (`kind: "editorial"`, markers `*`–`¶` per page) on the French page
recording the print reading; the English page follows the corrected French.

| Page | Print reads | Correction |
|---|---|---|
| I-3 (Cor. 3.7.2) | «SGAA VIII 7.8» | «SGA 4 VIII 7.8» |
| V-5 (5.5) | «Ses opérations sont donc **définie** par» | «définies» |
| V-5 (5.5.2) | `x ·_N y` in the second line | `x ·_N x′` |
| V-5 (after 5.5.3) | `λ^i(N,x)` in the γ^p formula | `λ^{p−i}(N,x)` (binomial `\binom{p-1}{i}` requires it) |
| V-6 (Prop. 6.6.1 i) | `λ^i(x)=0 pour i ⩾ n` | `i > n` (λⁿ(x) ≠ 0 by ii) |
| V-6 (Prop. 6.6.1 iii) | `= 0,1−(n−1)!aₙ+⋯)` | opening parenthesis restored: `= (0,1−(n−1)!aₙ+⋯)` |
| V-6 (proof of 6.10) | `z_{α,j}` | `x_{α,j}` (the formula and relations use x) |
| V-7 (7.1, 7.2) | «polynomes» (twice), transposed accent in «nécessaire» | accents fixed |
| V-7 (7.4, 7.5) | `1/1+t`, `X/1+Xt` | denominators parenthesized for clarity |
| VI-6 (Th. 6.9) | «et **à** fortiori» | «a fortiori» |
| VIII-4 (after VII 3.4) | `g^*(y)` | `g^*(x)` |
| XIII-4 (proof) | `Φ(G′^τ) ⊃ G^τ` | `Φ^{-1}(G′^τ) ⊃ G^τ` (as the sentence that follows argues) |

**Exposé XIV, notation `Gr˙` (raised dot).** The typescript writes the graded
rings with a raised dot — `Gr˙(X)`, `Gr˙_top(X)` — which the transcription had
rendered as a prime (`Gr′`). Checked against the scan page by page
(`ExposeXIV.pdf`, printed pp. XIV-3…21): every such site in Exposé XIV
(sections 3–8, 43 fields per language, including the section-5 title and the
manifest TOC entry) now reads `\operatorname{Gr}^{\bullet}`; the graded pieces
`Gr^i_top`, `Gr^2_top`, `Gr^1_top` (plain numeric superscripts in print, no
dot) had their spurious primes removed. **Follow-up:** chapters 0 and X still
transcribe the raised dot as an apostrophe (`K′`, `Gr′`, alongside `K_•`,
`Gr_•` for the lower dot), and `K′` keeps that convention throughout the book —
left untouched pending a decision on the book-wide convention.

Transcription repairs made in the same pass (not print anomalies): EN V-1
("regard H(K[X₁,…,Xₙ]) as contained in H(K[X_i]_{i⩾1})" — the first group was
duplicated); EN X-1/X-3 exposé reference "(V)" had been set as math italic
\(V\); EN X-4 (4.4.2) `K.(Y)` → `K_\bullet(Y)`; FR X-7 (7.7.2) missing
backslash in `{\scriptstyle i^*}`; X-7 §7.18.1 page-break paragraph split
merged in both languages (the EN even split mid-word "cri-/teria"); EN XIV-1
citation `[6]` → `[3]` (Bott–Samelson, as in the French); EN XIV-4 (4.1)
arrow label `χ` → `γ` (as in the French and the print).

## Exposé XII, p. 19 (vol. p. 613) — "restreindre" for "restreinte"

> donc la donnée de descente sur L **restreindre** au-dessus de V=f⁻¹(V) est
> isomorphe à la donnée de descente triviale sur O_X|V.

Ungrammatical past participle; "restreinte" is meant. In the proof following
the conditions 1)–5) for effectivity of the descent datum (§4).

## Exposé XIII, pp. 3–4 (vol. pp. 618–619) — "2.3" cited for "1.3" (twice)

In the proof of Proposition 1.4:

> les deux groupes extrêmes sont 0 pour q ≥ 2 et n ≥ m−(q−1) par **2.3** (i).

> Si n ≥ m, alors β_n est surjectif par **2.3** (ii) ;

Both should read **1.3**: Proposition 1.3(i) (an m-regular sheaf is n-regular
for n ≥ m) gives the vanishing of the extreme groups, and 1.3(ii) is exactly
the surjectivity of β_n : H⁰(G(n))⊗H⁰(O_X(1)) → H⁰(G(n+1)). Lemma 2.3, on the
Hilbert-polynomial coefficients (a_r = e_r = d(H)), is unrelated.

## Exposé XIV, p. 23 (vol. p. 689) — "sans hyperplan quasi-projectif"

In the "Notes pour la page 11", footnote (∗) on Mumford/Jouanolou:

> le résultat cohomologique est prouvé par J. P. JOUANOLOU sous des conditions
> plus générales (**sans hyperplan quasi-projectif**, et dans le cas lisse
> relatif sur une base quelconque).

Printed as such; possibly shorthand for (or a slip for) "sans hypothèse
quasi-projective". Kept as printed.

## Exposé X, p. 25 (vol. p. 543) — "a_d!" for "α_d!"

In the displayed coefficient formula after (4.3.2), the original prints
`(1/(α₁! ⋯ a_d!))` where `α_d!` is clearly meant. The transcription silently
normalizes this to `\alpha_d!`.

---

# SGA 7 — anomalies in the printed typescript

## Exposé XX, p. 6 (vol. p. 346) — "S annexe" for "S connexe"

Proposition 1.5.3, hypothesis line:

> Supposons f, g propres, S **annexe**, et soit q ∈ ℤ.

The typescript prints "annexe" — verified on the page image at 200 dpi, not just
in the PDF's (noisy) OCR layer, so this is the source's own misprint and not a
transcription artifact. "Annexe" is not a French mathematical adjective; the
hypothesis wanted is *S connexe* (S connected), as in the neighbouring statements
of §1. **Corrected** in `sga7/data/fr/chapters/20.json` (block 40) on 2026-07-29
under the policy above, the English rendering "S connected" agreeing with it.
