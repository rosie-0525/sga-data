#!/usr/bin/env bash
# sga2-convert-html: 01-normalized_tex/ -> 02-converted_html/
#
# 1. refresh main.aux (pdflatex) if missing/stale  — numbering & cross-references
#    are read authoritatively from the aux file;
# 2. run the LaTeX->JSON/HTML converter;
# 3. generate paper.html (the shared translation-viewer's entry page) into the
#    output, pointed at the super-repo root's translation-viewer/ checkout.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOK_ROOT="$(cd "$HERE/../../.." && pwd)"        # sga2/ — 01-normalized_tex/, 02-converted_html/ live here
SUPER_ROOT="$(cd "$HERE/../../../.." && pwd)"    # the sga/ super-repo root — translation-viewer/ lives here
SRC="$BOOK_ROOT/01-normalized_tex"
OUT="$BOOK_ROOT/02-converted_html"

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

TEMPLATE="$SUPER_ROOT/translation-viewer/paper.template.html"
if [[ ! -f "$TEMPLATE" ]]; then
  echo "[convert] error: $TEMPLATE not found — is translation-viewer/ present at the super-repo root ($SUPER_ROOT)?" >&2
  exit 1
fi

echo "[convert] generating paper.html…"
# paper.template.html assumes translation-viewer/ is a sibling of paper.html; here
# paper.html lives two levels down from translation-viewer/'s home (02-converted_html
# -> sga2 -> super-root), so rewrite the references to ../../translation-viewer/, and
# point the home link back at the multi-book landing page.
sed -e 's#"translation-viewer/#"../../translation-viewer/#g' \
    -e 's#href="index.html"#href="../../index.html"#' \
    "$TEMPLATE" > "$OUT/paper.html"

echo "[convert] done. Output in $OUT"
echo "          preview with:  (cd \"$SUPER_ROOT\" && python3 -m http.server) then open http://localhost:8000/sga2/02-converted_html/paper.html"
