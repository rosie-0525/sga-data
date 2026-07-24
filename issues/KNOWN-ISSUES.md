# Known issues

## Dropped display math in SGA 4 (and SGA 3 VIA) viewer data

**Status: fixed 2026-07-17.**

`sga3/scripts/build_viewer_data.py` and `sga4/scripts/build_viewer_data.py`
walked only the *element* children of `<body>` when turning
`01-transcribed/*.html` into viewer JSON. Bare text sitting between top-level
tags — which lxml parses as the `.tail` of the preceding element or comment —
was silently discarded. The transcriptions use exactly that shape for display
math (`\[ … \]` blocks between paragraphs) and for paragraph text that
continues after a page-break comment.

Measured impact (against the `01-transcribed/` sources):

| Corpus | Dropped runs | Characters | Notes |
| --- | --- | --- | --- |
| sga4 | 593 | ~92,000 | exposés VI, VII, XI, XII, XIV, XV, XVI, XVII |
| sga3 | 2 | ~800 | exposé VIA only: two `\[\xymatrix{…}\]` diagrams |
| sga4.5 | 0 | — | clean |
| sga5 | 0 | — | fixed at conversion time |

### How it was fixed

The viewer pairs French and translation blocks **by index** per page
(`renderAligned`), and SGA 4's English chapters are fully translated
(7,092 blocks) with real English in most of SGA 3 too — so simply
regenerating the French would have misaligned every affected page. The
repair therefore had three parts:

1. `promote_stray_text()` (ported from `sga5/scripts/build_viewer_data.py`)
   added to both build scripts, wrapping each stray run in its own `<p>`
   block; French data regenerated with it.
2. `sga4/scripts/patch_en_tail_blocks.py` (kept for reference) computed the
   per-page insertion-only diff of each French chapter against its git HEAD
   version and inserted the same blocks (language-neutral display math) into
   the English chapters at the same positions.
3. Verified: every stray run in the sources now appears in the data; every
   inserted block is byte-identical in fr and en at the same index; fr/en
   block counts match on every page (sga4 7,685 = 7,685); all 31 affected
   viewer pages render in headless Chrome with 0 `mjx-merror` and no leaked
   raw TeX.

The render sweep caught one latent bug in the restored content: a diagram in
`sga4/01-transcribed/XVII.html` (§1.2.2 (ii)) had a trailing `\, ,` inside
the last `\xymatrix` cell, which is fatal to XyJax's parser (a known pattern
from the SGA 4/5 transcription checklists). The punctuation was moved outside
the closing brace in the source and in both fr/en XVII data.
