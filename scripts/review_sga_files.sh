#!/usr/bin/env bash
# Review one SGA chapter per Codex invocation and report progress to Slack.

set -uo pipefail

repo_root=$(git -C "$(dirname "${BASH_SOURCE[0]}")/.." rev-parse --show-toplevel)
state_file=${SGA_REVIEW_STATE_FILE:-"$repo_root/.git/sga-review-completed"}
wait_seconds=${SGA_REVIEW_WAIT_SECONDS:-60}
run_once=false

usage() {
  cat <<'EOF'
Usage: scripts/review_sga_files.sh [--once]

Review unprocessed sga*/data/{fr,en}/chapters/*.json files in sorted order.
Each successful Codex run is recorded in .git/sga-review-completed. By default
the script continues until every file has been reviewed; --once reviews only
the next file.

Environment:
  SGA_REVIEW_WAIT_SECONDS  Delay before every Codex run (default: 60)
  SGA_REVIEW_STATE_FILE    Completed-file ledger
  CODEX_BIN                Codex executable (default: codex)
  SLACK_HOOK               Slack hook executable (default: ./slack_hook.py)
  CODEX_MODEL              Optional model passed as: codex exec --model MODEL
  CODEX_SANDBOX            Codex sandbox mode (default: danger-full-access)
EOF
}

case ${1:-} in
  "") ;;
  --once) run_once=true ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

if ! [[ $wait_seconds =~ ^[0-9]+$ ]]; then
  echo "SGA_REVIEW_WAIT_SECONDS must be a non-negative integer" >&2
  exit 2
fi

codex_bin=${CODEX_BIN:-codex}
codex_sandbox=${CODEX_SANDBOX:-danger-full-access}
slack_hook=${SLACK_HOOK:-"$repo_root/slack_hook.py"}
command -v "$codex_bin" >/dev/null 2>&1 || {
  echo "Codex executable not found: $codex_bin" >&2
  exit 1
}
[[ -f $slack_hook ]] || {
  echo "Slack hook not found: $slack_hook" >&2
  exit 1
}

touch "$state_file"

mapfile -t candidates < <(
  find "$repo_root" -type f -path "$repo_root/sga*/data/fr/chapters/*.json" -o \
    -type f -path "$repo_root/sga*/data/en/chapters/*.json" |
    sed "s|^$repo_root/||" |
    sort
)

total=${#candidates[@]}
if (( total == 0 )); then
  echo "No SGA chapter files found" >&2
  exit 1
fi

completed_count() {
  awk 'NF && !seen[$0]++ { count++ } END { print count + 0 }' "$state_file"
}

notify() {
  local message=$1
  if ! python3 "$slack_hook" "$message"; then
    echo "Warning: Slack notification failed" >&2
  fi
}

for target in "${candidates[@]}"; do
  grep -Fqx -- "$target" "$state_file" && continue

  language=$(cut -d/ -f3 <<<"$target")
  book=$(cut -d/ -f1 <<<"$target")
  proposals_file="$book/data/proposals.json"
  if [[ $language == fr ]]; then
    counterpart=${target/\/fr\//\/en\/}
    quality="French transcription fidelity, including omissions, typos, mathematics, and markup"
  else
    counterpart=${target/\/en\//\/fr\/}
    quality="English translation fidelity, including omissions, mistranslations, terminology, mathematics, and markup"
  fi

  echo "Waiting ${wait_seconds}s before reviewing $target"
  sleep "$wait_seconds"

  counterpart_note=$counterpart
  [[ -f $repo_root/$counterpart ]] || counterpart_note="$counterpart (not present)"

  prompt=$(cat <<EOF
Review exactly one corpus file for transcription/translation quality:

Target file: $target
Aligned counterpart: $counterpart_note
Primary focus: $quality.

Audit only the target file. When present, read the aligned counterpart, plus
the glossary, repository documentation, and available source material as
evidence. Inspect the whole target carefully, but DO NOT edit the target,
counterpart, or any other corpus JSON file.

Create or update $proposals_file and record every justified correction there, following
translation-viewer/docs/proposals.schema.md. Use scripts/proposals_lib.py to
build and validate proposals so that addresses, verbatim before values, and
single-root after values are checked. Preserve proposals for other target files
if $proposals_file already exists, and replace only any earlier proposals for
this exact target. If the target is sound, record no proposals for it. Do not
add, remove, split, merge, or reorder corpus blocks.

Before finishing, validate the proposals run and give a concise one-line
summary stating the number of errors found and the changes proposed (or that no
changes are proposed). Format that line exactly as:
SLACK_SUMMARY: <summary>
Keep the summary under 500 characters with no newline. End your final response
with the exact line REVIEW_COMPLETE only if you actually read the entire target
and validated the proposal output.
EOF
)

  result_file=$(mktemp)
  codex_args=(--ask-for-approval never --sandbox "$codex_sandbox" exec --cd "$repo_root" --output-last-message "$result_file")
  [[ -n ${CODEX_MODEL:-} ]] && codex_args+=(--model "$CODEX_MODEL")

  echo "Launching Codex for $target"
  if "$codex_bin" "${codex_args[@]}" "$prompt" &&
      grep -Fqx 'REVIEW_COMPLETE' "$result_file" &&
      grep -q '^SLACK_SUMMARY: .' "$result_file"; then
    review_summary=$(grep '^SLACK_SUMMARY: .' "$result_file" | tail -n 1)
    review_summary=${review_summary#SLACK_SUMMARY: }
    rm -f "$result_file"
    printf '%s\n' "$target" >>"$state_file"
    done_count=$(completed_count)
    notify "Complete reviewing \`$target\` ($done_count/$total files). $review_summary"
  else
    status=$?
    rm -f "$result_file"
    (( status == 0 )) && status=1
    done_count=$(completed_count)
    notify "SGA review failed: \`$target\` (Codex exit $status; $done_count/$total files complete)."
    echo "Codex failed for $target (exit $status); it was not marked complete" >&2
    exit "$status"
  fi

  $run_once && exit 0
done

done_count=$(completed_count)
echo "All $total SGA chapter files have been reviewed ($done_count ledger entries)."
notify "SGA transcription/translation review queue complete ($total/$total files)."
