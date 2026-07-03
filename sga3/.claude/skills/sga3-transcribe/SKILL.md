---
name: sga3-transcribe
description: Transcribe an SGA 3 exposé PDF (00-source_pdf/) into a minimal, semantic HTML file in 01-transcribed/. SGA 3 has no recoverable original LaTeX — only mimeographed-era PDFs — so every exposé is transcribed by hand. Use when starting work on a new exposé, or when asked to transcribe/proofread a specific exposé.
---

# sga3-transcribe

## When to use
Whenever asked to transcribe, draft, or proofread an exposé that doesn't have
a finished file in `01-transcribed/` yet. SGA 3 has no recoverable original
LaTeX — `00-source_pdf/` holds only the mimeographed-era PDFs — so each exposé
is transcribed into one self-contained `<chapter_id>.html` file in
`01-transcribed/`, hand-verified against the source PDF. That minimal HTML is
the deliverable of this skill.

## How to run

1. Generate the rough draft:
   ```
   python3 .claude/skills/sga3-transcribe/transcribe.py <pdf-filename-or-chapter_id>
   ```
   e.g. `transcribe.py origExp2.pdf` or `transcribe.py II` — both resolve
   through `chapter-map.json`. Use `--all` to draft every exposé that doesn't
   already have a file in `01-transcribed/` (never overwrites existing work
   unless `--force` is also given — a finished transcription is expensive to
   redo, so don't clobber it by accident).

2. **The draft is not the deliverable.** `pdftotext` extracts prose
   reasonably but mangles every formula, commutative diagram, and heading/
   theorem structure beyond use (hatted categories become `Cb`, arrows become
   `−→` or garbled Unicode box-drawing art, subscripts/superscripts flatten).
   The actual transcription is a full manual rewrite of the draft's content,
   checked paragraph-by-paragraph against the source PDF — read it with the
   `pages` parameter (e.g. `pages: "1-20"`), don't rely on the extracted text.

   Rewrite the draft into semantic HTML using the house style established in
   `01-transcribed/I.html` (the reference example — read it before starting a
   new exposé):
   - `\(...\)` inline math, `\[...\]` display math — the file loads the
     offline-vendored MathJax 3 + XyJax-v3, so open it in a browser to check
     rendering directly.
   - Commutative diagrams as `\xymatrix{…}` inside `\[...\]`.
   - `<h1>` for the exposé title, `<h2 id="{id}.N">` for numbered sections,
     `<h3 id="{id}.N.M">` for numbered paragraph markers (titled or bare —
     Demazure-style expository numbering like `1.1.`, `4.3.1.` is pervasive
     and cross-referenced throughout, so every one needs its own anchor).
   - `<div class="thm thm-plain|thm-remark <kind>">` with `thm-head`
     (`thm-name` + `thm-num`) / `thm-body` for Définition / Proposition /
     Théorème / Corollaire / Lemme / Remarque — `thm-plain` (italic body) for
     Proposition/Théorème/Corollaire/Lemme, `thm-remark` (roman body) for
     Définition/Remarque, matching the source's own typography.
   - `<a class="ref" href="#...">` for cross-references (internal, e.g. `cf.
     1.6`, and to other exposés, e.g. `Exp. VIII`).
   - Don't reproduce the source's page numbers (neither the per-exposé page
     headers nor the small marginal numbers) — page tracking is not kept in
     the transcription.
