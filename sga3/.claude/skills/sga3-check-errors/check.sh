#!/usr/bin/env bash
# Drive a headless Chromium over 01-transcribed/ and report rendering and
# cross-reference errors (categorised into issues/*_errors.json).
set -u

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOK_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"        # sga3/ — issues/ and 01-transcribed/ live here
SUPER_ROOT="$(cd "$SKILL_DIR/../../../.." && pwd)"    # the sga/ super-repo root — translation-viewer/ lives here
HTML_DIR="$BOOK_ROOT/01-transcribed"
OUT_DIR="$BOOK_ROOT/issues"
CHAPTER_MAP="$BOOK_ROOT/chapter-map.json"
# HTML_DIR's path relative to SUPER_ROOT (the dir the http server below is
# rooted at), e.g. "sga3/01-transcribed" — check.js needs this to build each
# file's URL, since the server root sits one level above every book.
HTML_DIR_REL="$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$HTML_DIR" "$SUPER_ROOT")"
# Chapter ids to check (comma-separated). Default: every file in 01-transcribed/.
IDS="${1:-}"
mkdir -p "$OUT_DIR"

if ! ls "$HTML_DIR"/*.html >/dev/null 2>&1; then
  echo "error: no .html files in $HTML_DIR — run sga3-transcribe first" >&2
  exit 2
fi

if [ ! -f "$SUPER_ROOT/translation-viewer/vendor/mathjax/tex-svg-full.js" ]; then
  echo "error: $SUPER_ROOT/translation-viewer/vendor/mathjax/ is missing — translation-viewer/ is a plain shared folder at the super-repo root; check it is present there" >&2
  exit 2
fi

if ! command -v node >/dev/null 2>&1; then
  echo "error: node is required (https://nodejs.org)" >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required (used for the static file server)" >&2
  exit 2
fi

# Puppeteer: reuse the vendored install from sga1's check-errors skill when it
# is present (same super-repo, same Chromium cache), otherwise install locally.
SGA1_MODULES="$SUPER_ROOT/sga1/.claude/skills/sga1-check-errors/node_modules"
if [ -d "$SGA1_MODULES/puppeteer" ]; then
  PUPPETEER_MODULES="$SGA1_MODULES"
else
  if [ ! -d "$SKILL_DIR/node_modules/puppeteer" ]; then
    echo "installing puppeteer (one-time, ~150 MB) ..." >&2
    (cd "$SKILL_DIR" && npm install --no-audit --no-fund) || {
      echo "error: npm install failed" >&2
      exit 2
    }
  fi
  PUPPETEER_MODULES="$SKILL_DIR/node_modules"
fi

# Ensure the bundled Chrome build is actually present and not partially
# extracted. puppeteer-browsers 2.13's installer silently produces a
# directory missing Contents/Frameworks on at least some macOS+arm64
# combinations, then claims success. Detect that and repair with the
# system `unzip`, which handles the .app symlinks correctly.
chrome_rev() {
  node -e "console.log(require('$PUPPETEER_MODULES/puppeteer-core/lib/cjs/puppeteer/revisions.js').PUPPETEER_REVISIONS.chrome)"
}
REV="$(chrome_rev)"

# Best-effort: let puppeteer try first (it may already work).
(cd "$(dirname "$PUPPETEER_MODULES")" && npx --no-install puppeteer browsers install chrome >/dev/null 2>&1) || true

case "$(uname -s)/$(uname -m)" in
  Darwin/arm64) PLAT='mac_arm'; ZIP_SUFFIX='mac-arm64'; APP_REL="chrome-mac-arm64/Google Chrome for Testing.app" ;;
  Darwin/x86_64) PLAT='mac'; ZIP_SUFFIX='mac-x64'; APP_REL="chrome-mac-x64/Google Chrome for Testing.app" ;;
  Linux/x86_64) PLAT='linux'; ZIP_SUFFIX='linux64'; APP_REL='' ;;
  *) PLAT=''; ZIP_SUFFIX=''; APP_REL='' ;;
esac

if [ -n "$APP_REL" ]; then
  CHROME_DIR="$HOME/.cache/puppeteer/chrome/${PLAT}-${REV}"
  NEEDED="${CHROME_DIR}/${APP_REL}/Contents/Frameworks"
  if [ ! -d "$NEEDED" ]; then
    echo "puppeteer's Chrome install is incomplete — repairing with system unzip ..." >&2
    rm -rf "$CHROME_DIR"
    mkdir -p "$CHROME_DIR"
    TMP_ZIP="$(mktemp -t puppeteer-chrome.XXXXXX.zip)"
    URL="https://storage.googleapis.com/chrome-for-testing-public/${REV}/${ZIP_SUFFIX}/chrome-${ZIP_SUFFIX}.zip"
    curl -fSL "$URL" -o "$TMP_ZIP" || { echo "error: failed to download $URL" >&2; rm -f "$TMP_ZIP"; exit 2; }
    (cd "$CHROME_DIR" && unzip -q "$TMP_ZIP") || { echo "error: unzip failed" >&2; rm -f "$TMP_ZIP"; exit 2; }
    rm -f "$TMP_ZIP"
  fi
fi

# Pick an unused localhost port (fall back to 8765 if /dev/tcp probes fail).
PORT=""
for p in 8765 8766 8767 8768 8769 9123 9456; do
  if ! (echo > "/dev/tcp/127.0.0.1/$p") >/dev/null 2>&1; then
    PORT=$p
    break
  fi
done
PORT="${PORT:-8765}"

(cd "$SUPER_ROOT" && python3 -m http.server "$PORT" >/dev/null 2>&1) &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

# Wait briefly for the server to come up.
for _ in $(seq 1 20); do
  if (echo > "/dev/tcp/127.0.0.1/$PORT") >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

NODE_PATH="$PUPPETEER_MODULES" node "$SKILL_DIR/check.js" "$HTML_DIR" "http://localhost:$PORT" "$OUT_DIR" "$HTML_DIR_REL" "$CHAPTER_MAP" "$IDS"
rc=$?

exit $rc
