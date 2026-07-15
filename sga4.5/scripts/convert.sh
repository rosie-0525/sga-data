#!/usr/bin/env bash
# Convert the original SGA 4 1/2 LaTeX sources to translation-viewer JSON.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOK_ROOT="$(cd "$HERE/.." && pwd)"
SUPER_ROOT="$(cd "$BOOK_ROOT/.." && pwd)"
SRC="$BOOK_ROOT/sga4.5"
OUT="$BOOK_ROOT/02-converted_html"
BUILD="${TMPDIR:-/tmp}/sga45-convert-$$"
trap 'rm -rf "$BUILD"' EXIT

mkdir -p "$BUILD" "$OUT"
cp "$SRC"/*.tex "$SRC"/*.sty "$SRC"/*.bib "$BUILD"/

if command -v pdflatex >/dev/null 2>&1; then
  echo "[convert] compiling auxiliary labels and citations…"
  (
    cd "$BUILD"
    pdflatex -interaction=nonstopmode -halt-on-error sga4.5.tex >/dev/null
    # The upstream bibliography has one malformed legacy entry; BibTeX still
    # emits the usable .bbl and auxiliary citation labels before returning 2.
    bibtex sga4.5 >/dev/null || true
    pdflatex -interaction=nonstopmode -halt-on-error sga4.5.tex >/dev/null
    pdflatex -interaction=nonstopmode -halt-on-error sga4.5.tex >/dev/null
  )
else
  echo "[convert] error: pdflatex is required to resolve numbering and references" >&2
  exit 1
fi

echo "[convert] generating translation-viewer data…"
python3 "$HERE/convert.py" \
  --src "$SRC" \
  --out "$OUT" \
  --aux "$BUILD/sga4.5.aux" \
  --bbl "$BUILD/sga4.5.bbl" \
  --verify

TEMPLATE="$SUPER_ROOT/translation-viewer/paper.template.html"
if [[ ! -f "$TEMPLATE" ]]; then
  echo "[convert] error: missing $TEMPLATE" >&2
  exit 1
fi

sed -e 's#"translation-viewer/#"../../translation-viewer/#g' \
    -e 's#href="index.html"#href="../../index.html"#' \
    "$TEMPLATE" > "$OUT/paper.html"

echo "[convert] done: $OUT"
