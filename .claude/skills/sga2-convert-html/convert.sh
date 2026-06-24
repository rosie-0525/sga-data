#!/usr/bin/env bash
# sga2-convert-html: 01-normalized_tex/ -> 02-converted_html/
#
# 1. refresh main.aux (pdflatex) if missing/stale  — numbering & cross-references
#    are read authoritatively from the aux file;
# 2. run the LaTeX->JSON/HTML converter;
# 3. copy the self-contained viewer (MathJax 3 + XyJax-v3) into the output.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
SRC="$REPO/01-normalized_tex"
OUT="$REPO/02-converted_html"

AUX="$SRC/main.aux"
need_aux=0
if [[ ! -f "$AUX" ]]; then
  need_aux=1
else
  # rebuild if any source file is newer than the aux
  while IFS= read -r f; do
    if [[ "$f" -nt "$AUX" ]]; then need_aux=1; break; fi
  done < <(find "$SRC" -maxdepth 1 -name '*.tex' -o -name '*.sty')
fi

if [[ "$need_aux" -eq 1 ]]; then
  if command -v pdflatex >/dev/null 2>&1; then
    echo "[convert] refreshing main.aux with pdflatex (2 passes)…"
    ( cd "$SRC" && pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null 2>&1 || true
      pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null 2>&1 || true )
  else
    echo "[convert] WARNING: pdflatex not found and main.aux is missing/stale;" >&2
    echo "          numbering and cross-references may be incomplete." >&2
  fi
fi

echo "[convert] running converter…"
python3 "$HERE/convert.py" --src "$SRC" --out "$OUT" --verify

echo "[convert] copying viewer assets…"
cp "$HERE/viewer/index.html" "$HERE/viewer/viewer.css" "$HERE/viewer/viewer.js" "$OUT/"

echo "[convert] done. Output in $OUT"
echo "          preview with:  (cd \"$OUT\" && python3 -m http.server) then open http://localhost:8000/"
