---
name: transcribe-scanned-pdf
description: Manually transcribe scanned PDFs or page images into faithful minimal HTML or plain text by rendering and visually reading every page, preserving document structure, formulas, footnotes, and bibliography entries, following a supplied output example, and verifying the result page by page. Use when the user asks Codex to transcribe a scan manually, perform the OCR itself, avoid automated OCR, or create an HTML transcription from a PDF. Do not use Python.
---

# Transcribe a scanned PDF manually

## Non-negotiable constraints

- Do not use Python, including Python one-liners, scripts, libraries, or Python-based OCR.
- Do not use OCR engines or text-extraction tools to produce the transcription. This includes Tesseract, OCRmyPDF, `pdftotext`, cloud OCR, and similar tools.
- Read the page images visually and transcribe the content yourself.
- Use `apply_patch` for output-file edits.
- Preserve uncertainty honestly. If text is unclear, rerender or crop it at higher resolution; do not silently guess.

## Prepare the source

1. Inspect the requested output example completely before writing. Reuse its HTML skeleton, MathJax configuration, CSS conventions, theorem markup, and identifier style, but not its document content.
2. Inspect the PDF with `pdfinfo` to record the page count, dimensions, and scan characteristics.
3. Render every page without OCR. Prefer a command such as:

   ```sh
   mkdir -p tmp/pdfs/<document>-pages
   pdftoppm -jpeg -r 180 input.pdf tmp/pdfs/<document>-pages/page
   ```

4. For small or indistinct text, rerender only the affected page at 300 DPI, or crop the rendered image with a native image utility such as `sips`.
5. Confirm that the rendered-image count equals the PDF page count.

If the PDF skill is available, also follow its rendering and visual-QA requirements. This skill controls the transcription method: it remains manual and Python-free.

## Transcribe

1. Work in small page batches, normally three to five pages.
2. View each page at original or high detail.
3. Transcribe prose faithfully, retaining spelling, accents, capitalization, punctuation, quotation marks, references, numbering, and intentional typographical oddities in the source.
4. Preserve the complete logical structure:

   - title and author;
   - parts, sections, and numbered subsections;
   - theorems, propositions, lemmas, corollaries, and proofs;
   - enumerated conditions and cases;
   - displayed formulas and diagrams;
   - footnotes and their markers;
   - appendices and bibliography entries.

5. For HTML output:

   - keep the markup minimal and valid;
   - use semantic headings and paragraphs;
   - follow the reference file's theorem containers and classes;
   - encode formulas in the reference file's MathJax delimiters;
   - escape HTML-sensitive characters, including `&amp;` in aligned MathJax source and `&lt;`/`&gt;` where needed;
   - assign stable, unique IDs consistent with the reference file.

6. Append each completed batch with `apply_patch`. Reopen the file around every patch boundary to ensure no sentence, formula, or footnote was skipped or duplicated.

## Resolve difficult passages

- Compare the unclear glyph with the same typewriter font elsewhere in the scan.
- Use the mathematical or grammatical context only to choose among visually plausible readings.
- Crop the exact line and inspect it at original resolution.
- Check running section and equation numbering for continuity.
- Preserve a source typo when the scan clearly contains it; do not silently modernize or correct the document.

## Verify

Perform a separate verification pass after transcription, not merely while typing.

1. Reinspect every rendered page from first to last against the output.
2. Check that all page transitions are represented and that the first and last visible content on each page appears in the transcription.
3. Check the sequences of headings, theorem numbers, equation numbers, footnote markers, appendices, and bibliography numbers.
4. Search for placeholders or uncertainty markers such as `TODO`, `TBD`, `???`, `illegible`, or `illisible`; resolve them visually.
5. For HTML, run non-Python structural checks:

   ```sh
   xmllint --html --noout output.html
   rg -o 'id="[^"]+"' output.html | sort | uniq -d
   ```

6. Confirm that inline and display MathJax delimiters are balanced. Also compare opening and closing brace counts as a quick diagnostic; investigate any mismatch rather than assuming it is harmless.
7. If a local browser is available, inspect the rendered HTML for MathJax failures, overflow, and malformed hierarchy. If it is unavailable, report that limitation and rely on page-image comparison plus source-level validation.

## Handoff

Report the output path, source-page count, and verification performed. Do not claim browser-render verification if only structural validation was possible.
