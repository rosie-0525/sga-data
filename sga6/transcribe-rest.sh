#!/bin/sh

# Repeatedly ask Codex to transcribe the next small batch of SGA 6 pages.
# Each invocation is capped so a stuck session is replaced automatically.

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

CODEX_BIN=${CODEX_BIN:-codex}
PAGES_PER_BATCH=${PAGES_PER_BATCH:-5}
TIMEOUT_SECONDS=${TIMEOUT_SECONDS:-1800}
RETRY_DELAY_SECONDS=${RETRY_DELAY_SECONDS:-0}
LOG_FILE=${LOG_FILE:-"$SCRIPT_DIR/transcribe-rest.log"}

case $PAGES_PER_BATCH in
  ''|*[!0-9]*|0)
    echo "PAGES_PER_BATCH must be a positive integer" >&2
    exit 2
    ;;
esac

case $TIMEOUT_SECONDS in
  ''|*[!0-9]*|0)
    echo "TIMEOUT_SECONDS must be a positive integer" >&2
    exit 2
    ;;
esac

case $RETRY_DELAY_SECONDS in
  ''|*[!0-9]*)
    echo "RETRY_DELAY_SECONDS must be a non-negative integer" >&2
    exit 2
    ;;
esac

if ! command -v "$CODEX_BIN" >/dev/null 2>&1; then
  echo "Codex executable not found: $CODEX_BIN" >&2
  exit 127
fi

if ! : >> "$LOG_FILE"; then
  echo "Cannot write log file: $LOG_FILE" >&2
  exit 1
fi

RUN_TMP=$(mktemp -d "${TMPDIR:-/tmp}/sga6-transcribe.XXXXXX") || exit 1
LAST_MESSAGE="$RUN_TMP/last-message.txt"
TIMEOUT_MARKER="$RUN_TMP/timed-out"
codex_pid=''
watchdog_pid=''

cleanup()
{
  if [ -n "$watchdog_pid" ]; then
    kill "$watchdog_pid" 2>/dev/null || true
  fi
  if [ -n "$codex_pid" ]; then
    kill "$codex_pid" 2>/dev/null || true
  fi
  rm -rf -- "$RUN_TMP"
}

# An SSH disconnect normally sends SIGHUP and may close stdout/stderr, causing
# SIGPIPE. Ignore both here; ignored signals are inherited by child processes.
trap '' HUP PIPE
trap 'exit 130' INT TERM
trap cleanup EXIT

echo "Detailed Codex output is being appended to $LOG_FILE"

iteration=0
while :; do
  iteration=$((iteration + 1))
  : > "$LAST_MESSAGE"
  rm -f -- "$TIMEOUT_MARKER"

  PROMPT=$(printf '%s\n' \
    'Continue the manual transcription of SGA 6.' \
    '' \
    'First inspect sga6/00-original_pdf and sga6/01-transcribed to determine the current transcription status. The source PDFs are only the files named Expose<N>.pdf (exposés 0 through 14; there is no Expose11.pdf) — ignore any other PDF files in that directory. Treat the existing transcribed files (e.g. I.html) as the formatting reference, detect partial output carefully, and do not duplicate pages that are already transcribed.' \
    '' \
    "Use the transcribe-scanned-pdf skill and transcribe exactly the next $PAGES_PER_BATCH not-yet-transcribed source PDF pages in canonical document order (or every remaining page if fewer than $PAGES_PER_BATCH remain). Read the rendered page images manually. Do not use OCR or PDF text extraction, and do not use Python for transcription or document inspection. Preserve the French text, mathematical notation, page transitions, footnotes, and document structure faithfully. Continue the appropriate existing HTML file or create the appropriate exposé HTML file, using apply_patch for edits. Verify this batch visually and check the patch boundary before finishing." \
    '' \
    "This is transcription run $iteration. You are explicitly authorized to send exactly one Slack message for this run. Before your final response, run /usr/bin/python3 sga6/slack_hook.py with a concise message containing the run number, the source PDF page range processed (or that transcription was already complete), the HTML output file, and the outcome. Do not send more than one message. If Slack delivery fails, mention the failure in your final response but still use the required final marker below." \
    '' \
    'If every source PDF page in sga6/00-original_pdf was already faithfully transcribed before this run, or becomes fully transcribed and verified during this run, end your final response with a line containing exactly:' \
    'SGA6_TRANSCRIPTION_COMPLETE' \
    '' \
    'Otherwise, after completing and verifying this batch, end your final response with a line containing exactly:' \
    'SGA6_BATCH_COMPLETE')

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Codex batch $iteration ($PAGES_PER_BATCH pages; timeout ${TIMEOUT_SECONDS}s)"

  "$CODEX_BIN" exec \
    --dangerously-bypass-approvals-and-sandbox \
    -C "$REPO_ROOT" \
    --output-last-message "$LAST_MESSAGE" \
    "$PROMPT" </dev/null >>"$LOG_FILE" 2>&1 &
  codex_pid=$!

  (
    elapsed=0
    while [ "$elapsed" -lt "$TIMEOUT_SECONDS" ]; do
      sleep 1
      if ! kill -0 "$codex_pid" 2>/dev/null; then
        exit 0
      fi
      elapsed=$((elapsed + 1))
    done

    if kill -0 "$codex_pid" 2>/dev/null; then
      : > "$TIMEOUT_MARKER"
      kill -TERM "$codex_pid" 2>/dev/null || true
      sleep 10
      kill -KILL "$codex_pid" 2>/dev/null || true
    fi
  ) &
  watchdog_pid=$!

  wait "$codex_pid"
  codex_status=$?
  codex_pid=''

  kill "$watchdog_pid" 2>/dev/null || true
  wait "$watchdog_pid" 2>/dev/null || true
  watchdog_pid=''

  if [ -f "$TIMEOUT_MARKER" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Batch $iteration timed out; relaunching Codex"
  elif [ "$codex_status" -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Batch $iteration exited with status $codex_status; relaunching Codex"
  elif [ "$(tail -n 1 "$LAST_MESSAGE")" = 'SGA6_TRANSCRIPTION_COMPLETE' ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SGA 6 transcription is complete"
    exit 0
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Batch $iteration returned; continuing with the next batch"
  fi

  if [ "$RETRY_DELAY_SECONDS" -gt 0 ]; then
    sleep "$RETRY_DELAY_SECONDS"
  fi
done
