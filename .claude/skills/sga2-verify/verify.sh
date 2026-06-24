#!/usr/bin/env bash
# Verify the normalized SGA2 tree.
set -u

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$ROOT/01-normalized_tex"

echo "verifying tree at $OUT"
fail=0

# 1. No leftover editorial macros in content files (sga2-macros.sty is excluded).
echo "--- check 1: leftover editorial macros in content ---"
content_files=("$OUT"/front-matter.tex "$OUT"/chapter-*.tex "$OUT"/back-matter.tex)
hits=$(grep -nE '\\(sisi|pageoriginale|nde|ndetext|sfootnote|Footnotemark|Footnotetext|alttitle|altabstract|altkeywords|subjclass|keywords|makeschapterhead)\b' "${content_files[@]}" 2>/dev/null || true)
if [ -n "$hits" ]; then
  echo "FAIL: leftover macros found:"
  echo "$hits" | head -20
  fail=1
else
  echo "ok"
fi

# 2. One \chapter per chapter-NN.tex.
echo "--- check 2: one chapter header per chapter file ---"
for f in "$OUT"/chapter-*.tex; do
  n=$(grep -cE '^\\chapter\*?(\[|\{)' "$f" || true)
  if [ "$n" -ne 1 ]; then
    echo "FAIL: $f has $n \\chapter headers"
    fail=1
  fi
done
echo "${fail:+}ok"

# 3. pdflatex compiles (two passes).
echo "--- check 3: pdflatex (two passes) ---"
if command -v pdflatex >/dev/null 2>&1; then
  (cd "$OUT" && pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1)
  if (cd "$OUT" && pdflatex -interaction=nonstopmode main.tex >/dev/null); then
    echo "ok"
  else
    echo "FAIL: pdflatex returned non-zero on second pass"
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
