# Errata — printed-edition anomalies noted during transcription

Sites where the **source PDFs themselves** (the 2011 SGA 3 re-edition typesetting
under `sga3/00-source_pdf/`) print something suspect or wrong. They were collected
during the 2026-07-24 repair/completion pass over exposés XXI, XXII, XXIV and XXVI
(each checked against the PDF text layer, ambiguous glyphs zoomed at high
resolution).

Policy applied: the transcription reproduces the print **as is** unless the
misprint is mathematically unambiguous; the handful of silent corrections made are
listed first per exposé so they can be audited. Line numbers refer to the current
files under `sga3/01-transcribed/`.

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
