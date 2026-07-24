#!/usr/bin/env bash
# Drive a headless Chromium over one or every book's 02-converted_html/ and
# report rendering, cross-reference, and other errors (categorised into the
# repo-root issues/*_errors.json, aggregated across books, plus
# issues/summary.json).
#
# usage:
#   bash check.sh                 # every sga*/ book, each in its own languages
#   bash check.sh sga5            # one book
#   bash check.sh sga5,sga7       # a comma-separated list
#   bash check.sh all fr          # every book, French column only
#   bash check.sh sga5 fr,en      # one book, explicit languages
set -u

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"   # sga-data/ — the sga*/ books and translation-viewer/ live here

BOOKS_ARG="${1:-all}"
LANGS="${2:-}"   # empty → check.js derives each book's languages from its data/config.json

if [ "$BOOKS_ARG" = "all" ]; then
  BOOKS=""
  for d in "$REPO_ROOT"/sga*/; do
    b="$(basename "$d")"
    [ -f "$d/02-converted_html/paper.html" ] && BOOKS="$BOOKS $b"
  done
else
  BOOKS="$(echo "$BOOKS_ARG" | tr ',' ' ')"
fi

if [ -z "${BOOKS// /}" ]; then
  echo "error: no books with 02-converted_html/paper.html found under $REPO_ROOT" >&2
  exit 2
fi

for b in $BOOKS; do
  if [ ! -f "$REPO_ROOT/$b/02-converted_html/paper.html" ]; then
    echo "error: $REPO_ROOT/$b/02-converted_html/paper.html does not exist — run that book's convert step first" >&2
    exit 2
  fi
done

if [ ! -f "$REPO_ROOT/translation-viewer/viewer.js" ]; then
  echo "error: $REPO_ROOT/translation-viewer/viewer.js does not exist — initialise the submodule: git submodule update --init translation-viewer" >&2
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

# One server at the repo root covers every book (paper.html reaches the shared
# translation-viewer/ via ../../translation-viewer/). Bind port 0 so the OS
# hands us a genuinely free port — probing a hardcoded list can race a stale
# preview server holding the port while serving the WRONG root — and pin the
# served directory explicitly so the server never inherits a surprising cwd.
PORT_LOG="$(mktemp -t sga-check-server.XXXXXX)"
python3 -u -c '
import http.server, sys
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=sys.argv[1], **kw)
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
print(srv.server_address[1], flush=True)
srv.serve_forever()
' "$REPO_ROOT" > "$PORT_LOG" &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null; rm -f "$PORT_LOG"' EXIT

# Wait for the server to report its port.
PORT=""
for _ in $(seq 1 50); do
  PORT="$(head -n1 "$PORT_LOG" 2>/dev/null)"
  [ -n "$PORT" ] && break
  sleep 0.1
done
if [ -z "$PORT" ]; then
  echo "error: local http server failed to start" >&2
  exit 2
fi

# Sanity check: the served tree must actually be the repo root, or every page
# scan would silently 404 (e.g. if the port probe raced a stale server).
probe="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PORT/translation-viewer/viewer.js" 2>/dev/null)"
if [ "$probe" != "200" ]; then
  echo "error: http://localhost:$PORT/ is not serving $REPO_ROOT (translation-viewer/viewer.js → HTTP $probe) — is a stale server holding the port?" >&2
  exit 2
fi

# All books share one output dir at the repo root; check.js merges by book, so
# a single-book run only replaces that book's records.
OUT_DIR="$REPO_ROOT/issues"
mkdir -p "$OUT_DIR"

rc=0
for b in $BOOKS; do
  HTML_DIR="$REPO_ROOT/$b/02-converted_html"
  echo "===== $b ====="
  node "$SKILL_DIR/check.js" "$HTML_DIR" "http://localhost:$PORT" "$OUT_DIR" "$LANGS" "$b/02-converted_html" "$b"
  brc=$?
  [ "$brc" -ne 0 ] && rc=1
done

exit $rc
