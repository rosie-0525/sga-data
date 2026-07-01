---
name: sga1-normalize-xymatrix
description: Reference catalogue of XyJax-v3 (`\xymatrix`) parse failures observed in SGA1 and the rewrites that fix them. The rewrites are applied automatically by `rule_xymatrix_patches` in sga1-inline-macros; this catalogue is the rationale for that rule and the place to add new patterns when sga1-check-errors surfaces a new failure.
---

# sga1-normalize-xymatrix

## When to use

After `sga1-check-errors` flags one or more `mjx-merror` instances or a
console-level `xypic ExecutionError` on a page containing `\xymatrix`.
XyJax-v3 (the MathJax-3 port of xy-pic bundled in `sga1-convert-html`)
accepts a strict subset of what pdflatex's xy-pic accepts; the rewrites
catalogued below preserve the pdflatex output while moving the diagram
into XyJax-v3's accepted grammar.

These rewrites are now applied **automatically and durably** by
`rule_xymatrix_patches` in `.claude/skills/sga1-inline-macros/inline_macros.py`
(it runs last, on the fully-inlined monolithic source, so it survives the
chapter split). Do **not** hand-edit `chapter-NN.tex` — those edits are
build artifacts and get clobbered on the next pipeline run. When
`sga1-check-errors` surfaces a *new* `\xymatrix` failure, add an `(old, new)`
pair to the `_XYMATRIX_PATCHES` list using the categories below as the
rationale, then re-run the pipeline.

> History: these were originally hand-applied to `chapter-NN.tex` after the
> split, which meant any pipeline re-run silently wiped them. Encoding them as
> a pipeline rule fixed that fragility.

## XyJax-v3 incompatibilities — what fails and what works

Nine categories observed in SGA1. Each was verified by editing the
chapter source, re-running `sga1-convert-html`, then `sga1-check-errors`
and confirming the affected page's `merrors` array dropped to zero.

### (a) `\\` row separator followed by problematic next-row content

XyJax-v3 bails on `\\` when the next row begins with `\operatorname`,
`\widehat`, `\,`, `_`, `^`, `\ar` (no preceding entry), or a brace
group `{…}` whose interior is anything other than the empty `{}`
followed immediately by `\ar`.

**Plain letters and most control sequences (`\mathrm`, `\underline`,
`X`, `Y`, `E`, etc.) at row start work fine.** That gives two
families of fix:

1. If the failing row begins with `\ar`, insert `{}` so it becomes
   `{}\ar[...]` — `{}` followed by `\ar` is the one row-start brace
   form XyJax-v3 accepts.
2. If the failing row begins with anything else (`\Pic(U)` from a
   `\DeclareMathOperator` expansion, `S'_s`, etc.), rewrite the
   offending token in line with categories (e), (h), (i) so the row
   starts with a plain letter / control sequence — **do NOT add
   `{}`**; `{}` followed by a letter fails just as hard as the
   original token (verified — see "Patterns that did NOT work").

| Failing | Fix |
|---|---|
| `\\&\Pic(U)\ar[ur]&` (`\Pic` → `\operatorname{Pic}`) | `\\&{\mathrm{Pic}(U)}\ar[ur]&` (per (h)) |
| `\\\ar[r]&\underline{\mathrm{H}}…\ar[r]…` | `\\{}\ar[r]&\underline{\mathrm{H}}…\ar[r]…` |
| `\\E'^{p,q}_2=…` (apostrophe then `^`) | `\\E^{\prime p, q}_2=…` (rewrite prime; row now starts with bare `E`) |
| `\\S'_s\ar[r]&\Spec k(s)` | `\\S^{\prime}_s\ar[r]&\mathrm{Spec}\,k(s)` |
| `\\{X'}\ar[r]…` (outer braces in cell-object) | `\\X^{\prime}\ar[r]…` (drop outer braces, rewrite prime) |

### (b) `\UseTips` / `\newdir` declarations

`\UseTips` and `\newdir{ >}{!/-5pt/\dir{>}}` are xy-pic style
customisations XyJax-v3 does not implement. The default arrow tip set
is sufficient.

**Fix:** delete the `\UseTips` and `\newdir{…}{…}` calls entirely.
Visually in pdflatex this swaps a custom 5pt-offset `>` tip for the
default xy-pic tip — imperceptible at standard scale.

| Failing | Fix |
|---|---|
| `\UseTips \newdir{ >}{!/-5pt/\dir{>}} \xymatrix@=5mm{…}` | `\xymatrix@=5mm{…}` |

### (c) Custom `\dir` arrow heads with stray whitespace

`\ar@{^{ (}->}[r]` (note the **space** inside `^{ (}`) trips XyJax-v3's
direction parser even though pdflatex's xy-pic accepts it.

**Fix:** drop the space — write `\ar@{^{(}->}[r]`, the canonical xy-pic
hookrightarrow spelling. Pdflatex output is unchanged because the space
inside a math-mode group is discarded by tokenisation.

| Failing | Fix |
|---|---|
| `\ar@{^{ (}->}[r]` | `\ar@{^{(}->}[r]` |

### (d) `\xymatrix` wrapped in `\begin{equation}\begin{array}{c}…\end{array}\end{equation}`

XyJax-v3 cannot parse a nested `\begin{array}{c}…\end{array}` around an
`\xymatrix`. The wrapper is redundant — `\xymatrix` already centres its
own box inside display math.

**Fix:** unwrap. Keep the outer `equation` / `equation*` (with its
`\label` and any `\tag`), drop the inner `array{c}`.

| Failing | Fix |
|---|---|
| `\begin{equation}\label{eq:X}\begin{array}{c}\xymatrix{…}\end{array}\end{equation}` | `\begin{equation}\label{eq:X}\xymatrix{…}\end{equation}` |
| `\begin{equation*}\label{eq:Y}\tag{$*$}\begin{array}{c}\xymatrix@C=0pt{…}\end{array}\end{equation*}` | `\begin{equation*}\label{eq:Y}\tag{$*$}\xymatrix@C=0pt{…}\end{equation*}` |

### (e) ASCII `'` (prime) becoming U+2019 in the HTML converter's output

The `'` character survives pdflatex unchanged but the HTML converter's
emitter writes it as the curly U+2019 right-single-quote in two
contexts inside `\xymatrix`:

- inside an outer `{…}` group used as a cell-object (`{X'}` →
  `{X’}`), and
- inside arrow-label braces (`_-{i'}` → `_-{i’}`).

XyJax-v3 rejects U+2019 in both positions. Pdflatex output is identical
either way because `'` in math mode is literally
`\mathchardef\'=\prime`.

**Fix:** in xymatrix bodies, rewrite every prime explicitly as
`^{\prime}` (or `^{\prime\prime}` for double primes). Apply only inside
the xymatrix body; apostrophes in surrounding prose are unaffected (and
HTML's curly-quote substitution is correct there).

| Failing | Fix |
|---|---|
| `_-{i'}` | `_-{i^{\prime}}` |
| `X'\ar[d]` | `X^{\prime}\ar[d]` |
| `i'_0` | `i^{\prime}_{0}` |
| `{X'}\ar[r]…` (outer braces — see also (a), (i)) | `X^{\prime}\ar[r]…` |
| `\ar[d]_{f'}` (label-brace prime) | `\ar[d]_{f^{\prime}}` |

### (f) Cell-start `\ar` followed by an object

Inside an xymatrix cell, `\ar[…]` *before* the cell's object (e.g.
`& \ar[l] Y \ar[d] &`) is accepted by pdflatex's xy-pic — it figures
out that `Y` is the object and reorders. XyJax-v3 does not: it requires
the canonical *object-then-arrows* order.

**Fix:** put the object first, attach arrows after. Semantically identical
in xy-pic (arrows attach to the cell's object regardless of where they
appear in the entry).

| Failing | Fix |
|---|---|
| `& \ar[l] Y \ar[d] &` | `& Y \ar[l] \ar[d] &` |
| `& \ar[l]_-{i^{\prime}} U^{\prime}\ar[d]^g \\` | `& U^{\prime}\ar[l]_-{i^{\prime}}\ar[d]^g \\` |
| `&\ar[l] Y^{\prime} &` | `& Y^{\prime} \ar[l] &` |

### (g) Subscript / superscript on a braced-group cell-object

`{...}_X^Y` inside a cell — i.e. a braced group followed immediately
by `_` or `^` — fails. XyJax-v3 sees the closing `}` and expects either
an arrow or the next cell separator, not a script.

**Fix:** drop the outer `{...}` so the underlying control sequence
absorbs the script naturally.

| Failing | Fix |
|---|---|
| `f^*({\underline{\mathrm{H}}}_Z^i(F))` | `f^*(\underline{\mathrm{H}}_Z^i(F))` |
| `{\underline{\mathrm{H}}}_T^i(f^*F)\ar[r]` | `\underline{\mathrm{H}}_T^i(f^*F)\ar[r]` |
| `{\underline{\mathrm{H}}}^*(\mathrm{R} k_*(…))` | `\underline{\mathrm{H}}^*(\mathrm{R} k_*(…))` |

In TeX both spellings render identically because `\underline{X}` is an
mathord; the trailing script attaches to it whether or not the brace
group is wrapped.

### (h) `\operatorname{X}` (or `\mathrm{X}`) followed by `(…)` as a cell-object

`\Pic(X)` (which expands to `\operatorname{Pic}(X)`) and similarly
`\mathrm{Spec}\,k_i` placed as a bare cell-object cause XyJax-v3 to
bail: it accepts `\operatorname{Pic}` as one object then expects an
arrow or cell separator, but sees `(`. The same happens with the
post-rewrite `\mathrm{Pic}(X)` form.

**Fix:** (1) rewrite `\operatorname{…}` and any operator macro
(`\Pic`, `\Spec`, `\Et`, …) as plain `\mathrm{…}` — XyJax-v3 does not
accept `\operatorname` inside xymatrix at all (this is the existing
`rule_xymatrix_safe` rule for `\R` and `\mathop{\underline{…}}\nolimits`
generalised). (2) Wrap the whole cell-object expression — operator,
parens, and contents — in an outer `{…}` so the cell sees a single
brace-group object.

For positional spacing inside the operator's argument that was supplied
by `\operatorname`'s `\thinmuskip` (e.g. `\Spec k(s)`), insert `\,` by
hand: `\mathrm{Spec}\,k(s)`.

| Failing | Fix |
|---|---|
| `\Pic(X)\ar[rr]\ar[dr]` | `{\mathrm{Pic}(X)}\ar[rr]\ar[dr]` |
| `\Pic(X_n)` | `{\mathrm{Pic}(X_n)}` |
| `{\Spec L}\ar[dl]_v` | `\mathrm{Spec}\,L\ar[dl]_v` |
| `{\Spec k_i} \ar[rr]^w` | `\mathrm{Spec}\,k_i \ar[rr]^w` |
| `\Spec k(s)` (as arrow target text, not cell-object) | `\mathrm{Spec}\,k(s)` (no wrap needed — `\Spec` here is the only token and is not followed by parenthesised args at cell-object position) |

Note the **first row** of the Spec/k_i diagram works without wrapping
because the cell content has no parenthesised continuation after
`\mathrm{Spec}\,L`. The Pic case needs `{…}` wrapping because `(X)`
follows directly.

### (i) `{}` followed by a non-arrow token in a cell entry

`{}` as an explicit empty xy-pic object works *only* when followed
immediately by `\ar` (so the cell reads "empty object with attached
arrow"). `{} S^{\prime}_s` or `{}E^{\prime p,q}_2` fail because XyJax
parses `{}` and then expects an arrow or `&`/`\\`, not raw content.

**Fix:** simply drop the `{}` when the next token is a letter or other
content — the row will start with that token directly, which (per (a))
is fine for letters and most control sequences.

| Failing | Fix |
|---|---|
| `\\{}E^{\prime p, q}_2=…` | `\\E^{\prime p, q}_2=…` |
| `\\{} S^{\prime}_s\ar[r]&…` | `\\S^{\prime}_s\ar[r]&…` |

Keep `{}` only in the `{}\ar[…]` shape (e.g. `\\{}\ar[r]&…`).

### (j) Script- or `\,`-bearing cell-object → wrap the whole object in `{…}`

The general, robust fix that **supersedes the per-token tweaks in (e)/(g)/(h)
for cell-objects that carry a sub/superscript or a `\,`.** XyJax-v3's cell
parser mis-handles a cell-object that, as written, ends up *not* a single token
once it reaches a `^`, `_` or `\,`:

- a bare `\underline{\mathrm{C}}^{\circ}_{Y}` (both `^` and `_`),
- a leading-superscript object like `\mathrm{R}^1j_*(…)`,
- `E^{\prime p,q}_2=…` (sup then sub),
- `\mathrm{Spec}\,L` (a `\,` right after the operator),
- `\underline{\mathrm{Ab}}\,.` (a `\,` after the object).

Wrapping the **entire** cell-object — base, scripts, parenthesised arguments
and any trailing `\,`/`.` — in one `{…}` makes XyJax take it as a single opaque
math object and hand the interior to MathJax core, which parses all of the
above fine. In TeX `{X}` and `X` are the same mathord, so pdflatex output is
unchanged.

| Failing | Fix |
|---|---|
| `\underline{\mathrm{C}}^{\circ}_{Y}\ar[dr]` | `{\underline{\mathrm{C}}^{\circ}_{Y}}\ar[dr]` |
| `…&\underline{\mathrm{Ab}}\,.\\` | `…&{\underline{\mathrm{Ab}}\,.}\\` |
| `\underline{\mathrm{H}}_T^i(f^*F)\ar[r]` | `{\underline{\mathrm{H}}_T^i(f^*F)}\ar[r]` |
| `E^{\prime p, q}_2=\mathrm{R}^pk_*(…)\ar@{=>}[r]` | `{E^{\prime p, q}_2=\mathrm{R}^pk_*(…)}\ar@{=>}[r]` |
| `\mathrm{R}^1j_*(g^*F) \ar[r]` | `{\mathrm{R}^1j_*(g^*F)} \ar[r]` |
| `\mathrm{Spec}\,L\ar[dl]_v` | `{\mathrm{Spec}\,L}\ar[dl]_v` |

Note this *reverses* the earlier (g) advice ("drop the outer braces on
`{\underline{\mathrm{H}}}`"): dropping the braces around the operator is still
right, but the **whole cell-object** (operator + scripts + args) must then be
re-wrapped as one group. `{…}` followed by `\ar` (or `&`/`\\`) is always
accepted — the failures in "Patterns that did NOT work" are about `{…}`
followed by a *script* or by a *bare letter at row start*, not by an arrow.

### (k) Converter `\\` mis-tokenisation (not an XyJax issue) — `\\S' → \§'`

A row break `\\` immediately followed by a macro letter (`\\S`, `\\et`, …) was
mis-tokenised by the HTML converter's `expand_math`: it emitted the first `\`,
then read `\S` as the section macro and expanded it to `§`, yielding `\§'` —
which XyJax then rejects. This is a **converter bug**, fixed in
`sga1-convert-html/convert.py` (`expand_math` now consumes `\\` atomically); it
is *not* fixed by a `_XYMATRIX_PATCHES` entry. With the converter fixed, a
diagram may keep its `\\S^{\prime}` row break verbatim. (A `\\` followed by a
newline or space — as in a multi-line diagram body — never tripped this.)

## Patterns that did NOT work

Recorded so a future pass doesn't repeat them.

- **`\\{}<letter>`** (empty brace group at row start followed by a
  raw letter or identifier). Verified to fail just as hard as the
  bare letter — the issue is XyJax's per-token row-start dispatch,
  not strictly a `\\\<letter>` problem. Drop the `{}` instead. (See
  category (i).)

- **`\\<braced group>`** at row start (e.g. `\\{\operatorname{Spec}k_i}`).
  Fails. Drop the outer braces and rewrite the inner operator per (h).

- **`\\\ar`** (row immediately starting with `\ar`). Fails. Must
  prefix with `{}` to give `\\{}\ar[…]`.

- **`\ar@{^{ (}->}`** (custom `\dir` form with internal whitespace).
  Fails. Drop the space; the canonical xypic hookrightarrow
  `\ar@{^{(}->}` is accepted.

- **Bare `\operatorname{…}` inside an `\xymatrix` cell.** Fails on any
  following `(`. Rewriting to `\mathrm{…}` alone is not enough — the
  whole cell-object must additionally be wrapped in `{…}` (category
  (h)) when followed by parenthesised content.

- **`{...}_X^Y` cell-object** with sub/superscript on a braced group.
  Fails at the script. Drop the outer braces (category (g)).

## SGA1 occurrences fixed

`_XYMATRIX_PATCHES` starts **empty** for SGA1. As [[sga1-check-errors]] surfaces
`\xymatrix` `mjx-merror`s, add an `(old, new)` pair to `_XYMATRIX_PATCHES` in
[[sga1-inline-macros]] using the categories above as the rationale, then re-run
the pipeline. Record each fixed diagram here (file:line, HTML id, category,
spelling adopted) as it is resolved.

SGA1 has 118 `\xymatrix` invocations; the generic xymatrix-safety rewrite
(`rule_xymatrix_safe`, which turns `\operatorname`-class operators — `\Hom`,
`\SheafHom`, `\Ouv`, `\Quot`, `\Fer`, `\Ext` — into plain `\mathrm`/`\mathbf`
inside diagram cells) handles the common operator-in-cell case automatically;
only diagrams that still error after that need an entry below.

| File:line | HTML | Category | Spelling adopted |
|---|---|---|---|
| _(none yet — populate from sga1-check-errors)_ | | | |

## Verification

```
.claude/skills/sga1-convert-html/convert.sh
bash .claude/skills/sga1-check-errors/check.sh
```

Final clean state: `issues/mathjax_errors.json`, `issues/crossref_errors.json`,
and `issues/other_errors.json` are all `[]` — no page has a `merror`, leaked
macro, dangling anchor, or page/console error across all pages in
`fr`+`en`; the check script prints `CHECK PASSED`. `sga1-verify` also passes
(two-pass pdflatex still compiles cleanly). Note the XIV-2 diagrams also depend on the converter's
`\\`-tokenisation fix (category (k)) — re-running only `inline_macros.py`
without that convert.py fix would re-introduce the `\§` corruption.

## Related

- [[sga1-inline-macros]] — hosts both `rule_xymatrix_safe` (regex rewrites
  of `\mathop{…}\nolimits` and `\R` inside xymatrix bodies) and
  `rule_xymatrix_patches` (the targeted `(old, new)` rewrites catalogued
  here — cell-object wrapping, prime → `\prime`, operator handling,
  row-start dispatch, `array{c}` unwrap, etc., which the regex-rule shape
  can't safely capture). New failures go into `_XYMATRIX_PATCHES`.
- [[sga1-check-errors]] — the verification step that surfaces the
  failures this skill addresses.
- [[sga1-convert-html]] — vendors `xypic.js` (XyJax-v3) and the MathJax 3
  SVG bundle under `vendor/` and wires the loader, so diagrams render offline.
- [[feedback-normalize-in-latex-not-html]] — design constraint: fix in
  LaTeX, not in the MathJax config.
- [[feedback-no-sty-changes]] — design constraint: don't change
  `sga1-macros.sty`.
