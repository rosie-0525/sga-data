#!/usr/bin/env bash
# Drive a headless Chromium over 02-converted_html/ and report MathJax errors.
set -u

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
HTML_DIR="$ROOT/02-converted_html"
OUT_JSON="$ROOT/issues/mathjax_errors.json"
# Languages to render+scan (comma-separated). Override as the first CLI arg.
LANGS="${1:-fr,en}"
mkdir -p "$ROOT/issues"

if [ ! -f "$HTML_DIR/index.html" ]; then
  echo "error: $HTML_DIR/index.html does not exist — run sga2-convert-html first" >&2
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

if [ ! -d "$SKILL_DIR/node_modules/puppeteer" ]; then
  echo "installing puppeteer (one-time, ~150 MB) ..." >&2
  (cd "$SKILL_DIR" && npm install --no-audit --no-fund) || {
    echo "error: npm install failed" >&2
    exit 2
  }
fi

# Ensure the bundled Chrome build is actually present and not partially
# extracted. puppeteer-browsers 2.13's installer silently produces a
# directory missing Contents/Frameworks on at least some macOS+arm64
# combinations, then claims success. Detect that and repair with the
# system `unzip`, which handles the .app symlinks correctly.
chrome_rev() {
  node -e "console.log(require('$SKILL_DIR/node_modules/puppeteer-core/lib/cjs/puppeteer/revisions.js').PUPPETEER_REVISIONS.chrome)"
}
REV="$(chrome_rev)"

# Best-effort: let puppeteer try first (it may already work).
(cd "$SKILL_DIR" && npx --no-install puppeteer browsers install chrome >/dev/null 2>&1) || true

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

(cd "$HTML_DIR" && python3 -m http.server "$PORT" >/dev/null 2>&1) &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

# Wait briefly for the server to come up.
for _ in $(seq 1 20); do
  if (echo > "/dev/tcp/127.0.0.1/$PORT") >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

node "$SKILL_DIR/check.js" "$HTML_DIR" "http://localhost:$PORT" "$OUT_JSON" "$LANGS"
rc=$?

exit $rc
