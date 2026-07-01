#!/usr/bin/env bash
# Verify the normalized SGA1 tree.
set -u

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$ROOT/01-normalized_tex"

echo "verifying tree at $OUT"
fail=0

# 1. No leftover editorial/presentation macros in content files
#    (sga1-macros.sty is excluded — it legitimately defines content macros).
echo "--- check 1: leftover editorial macros in content ---"
content_files=("$OUT"/front-matter.tex "$OUT"/chapter-*.tex "$OUT"/back-matter.tex)
hits=$(grep -nE '\\(marginpar|oldindexnot|makeschapterhead|Ref|ptbl|sfootnote|Subsection|Subsubsection|smaller|larger|pageoriginale)\b' "${content_files[@]}" 2>/dev/null || true)
if [ -n "$hits" ]; then
  echo "FAIL: leftover macros found:"
  echo "$hits" | head -20
  fail=1
else
  echo "ok"
fi

# 1b. No unresolved orig conditionals.
orig=$(grep -nE 'boolean\{orig\}' "${content_files[@]}" 2>/dev/null || true)
if [ -n "$orig" ]; then
  echo "FAIL: unresolved \\boolean{orig} conditionals:"
  echo "$orig" | head
  fail=1
fi

# 2. One \chapter per chapter-NN.tex, and exactly 12 chapter files.
echo "--- check 2: one chapter header per chapter file (expect 12 files) ---"
nfiles=$(ls "$OUT"/chapter-*.tex 2>/dev/null | wc -l | tr -d ' ')
if [ "$nfiles" -ne 12 ]; then
  echo "FAIL: expected 12 chapter files, found $nfiles"
  fail=1
fi
for f in "$OUT"/chapter-*.tex; do
  n=$(grep -cE '^\\chapter\*?(\[|\{)' "$f" || true)
  if [ "$n" -ne 1 ]; then
    echo "FAIL: $f has $n \\chapter headers"
    fail=1
  fi
done
[ "$fail" -eq 0 ] && echo "ok"

# 3. pdflatex compiles cleanly (pdflatex, makeindex, pdflatex, pdflatex).
echo "--- check 3: pdflatex + makeindex (clean compile) ---"
if command -v pdflatex >/dev/null 2>&1; then
  (
    cd "$OUT" || exit 1
    pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null 2>&1
    makeindex main.idx >/dev/null 2>&1 || true
    pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null 2>&1
  )
  if (cd "$OUT" && pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null 2>&1); then
    echo "ok (main.pdf written)"
  else
    echo "FAIL: pdflatex returned non-zero on final pass"
    fail=1
  fi
else
  echo "SKIP: pdflatex not installed"
fi

echo
if [ $fail -eq 0 ]; then
  echo "VERIFY PASSED"
  exit 0
else
  echo "VERIFY FAILED"
  exit 1
fi
