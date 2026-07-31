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

## Exposé XXI — Données radicielles (`XXI.html`, source `origExpo21.pdf`)

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

## Exposé XXII — Groupes réductifs : déploiements, sous-groupes, groupes quotients (`XXII.html`, source `origExpo22.pdf`)

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

## Exposé XXIV — Automorphismes des groupes réductifs (`XXIV.html`, source `origExpo24.pdf`)

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

## Exposé XXVI — Sous-groupes paraboliques des groupes réductifs (`XXVI.html`, source `origExpo26.pdf`)

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

# SGA 4½ — anomalies in the source text

The volume's reference is the LaTeX transcription in the `sga4.5/sga4.5/`
submodule, which reproduces the print; the sites below were checked against the
French PDF on 2026-07-31.

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

---

# SGA 6 — anomalies in the printed 1971 edition

Flagged during the English translation, checked against the scans in
`sga6/source/` on 2026-07-18. All are kept **verbatim** in both
language versions of the viewer data; this is the record of what they are and
what was almost certainly meant. (Migrated here from `sga6/typos.md` on
2026-07-27, when that file's other section — three transcription remnants in
Exposé X, fixed 2026-07-18 — was verified clean in fr and en and dropped.)

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
