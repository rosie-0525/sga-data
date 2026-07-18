# SGA 6 — source typos and errata

Oddities flagged during the English translation, checked against the scanned
originals in `00-original_pdf/` on 2026-07-18. Typos that are in the 1971
printed text are kept **verbatim** in the transcription (`01-transcribed/`) and
in both language versions of the viewer data; this file is the record of what
they are and what was almost certainly meant.

## Errata in the printed original (kept verbatim)

### Exposé XII, p. 19 (vol. p. 613) — "restreindre" for "restreinte"

> donc la donnée de descente sur L **restreindre** au-dessus de V=f⁻¹(V) est
> isomorphe à la donnée de descente triviale sur O_X|V.

Ungrammatical past participle; "restreinte" is meant. In the proof following
the conditions 1)–5) for effectivity of the descent datum (§4).

### Exposé XIII, pp. 3–4 (vol. pp. 618–619) — "2.3" cited for "1.3" (twice)

In the proof of Proposition 1.4:

> les deux groupes extrêmes sont 0 pour q ≥ 2 et n ≥ m−(q−1) par **2.3** (i).

> Si n ≥ m, alors β_n est surjectif par **2.3** (ii) ;

Both should read **1.3**: Proposition 1.3(i) (an m-regular sheaf is n-regular
for n ≥ m) gives the vanishing of the extreme groups, and 1.3(ii) is exactly
the surjectivity of β_n : H⁰(G(n))⊗H⁰(O_X(1)) → H⁰(G(n+1)). Lemma 2.3, on the
Hilbert-polynomial coefficients (a_r = e_r = d(H)), is unrelated.

### Exposé XIV, p. 23 (vol. p. 689) — "sans hyperplan quasi-projectif"

In the "Notes pour la page 11", footnote (∗) on Mumford/Jouanolou:

> le résultat cohomologique est prouvé par J. P. JOUANOLOU sous des conditions
> plus générales (**sans hyperplan quasi-projectif**, et dans le cas lisse
> relatif sur une base quelconque).

Printed as such; possibly shorthand for (or a slip for) "sans hypothèse
quasi-projective". Kept as printed.

### Exposé X, p. 25 (vol. p. 543) — "a_d!" for "α_d!"

In the displayed coefficient formula after (4.3.2), the original prints
`(1/(α₁! ⋯ a_d!))` where `α_d!` is clearly meant. The transcription
silently normalizes this to `\alpha_d!`.

## Transcription remnants (ours, fixed 2026-07-18)

Not source typos — listed here because they were flagged alongside the above.
All were in Exposé X §4–5 and are fixed in `01-transcribed/X.html` and in
`02-converted_html/data/{fr,en}/chapters/X.json`:

- literal `([F])` for `\([F]\)` (p. 25, statement of Prop 4.3.1);
- literal `(leq d)` for `\(\leq d\)` (p. 26, property 4);
- 8 spans `\(mathcal O_X\)` / `\(mathcal O_Y\)` missing the backslash on
  `\mathcal` — these render as the literal word "mathcal" with **no**
  mjx-merror, so render sweeps cannot catch this class; grep sources for
  `\(math[cbsf]`, `\(operatorname`, `\(leq` instead.

(The translator flag also mentioned a literal `(i)` on X p. 4; no such remnant
exists — the nearby `\((i=1,\ldots,d)\)` is properly protected math.)
