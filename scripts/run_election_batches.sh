#!/usr/bin/env bash

# Resumable full scrape for any election module.
#
#   scripts/run_election_batches.sh <election-id>
#
# Mirrors the per-election batch scripts, but takes the election id as an
# argument so the elections that never had a script of their own can be run the
# same way. Candidate samples go to a temporary directory, so the test-protected
# fixtures under samples/html/<election-id>/ are never touched.
#
# Environment:
#   BATCH_SIZE         candidates per batch (default 200)
#   MAX_BATCHES        batches per invocation, 0 for "until finished" (default 0)
#   THROTTLE_SECONDS   pause between candidates (default 0.4)
#   STOP_ON_ANOMALY    1 to stop after a batch that recorded anomalies (default 0).
#                      The per-election scripts stop by default; a full unattended
#                      run does not, because anomalies are recorded to
#                      anomalies.jsonl for review either way.
#   SAMPLES_ROOT       reuse a samples directory instead of a temporary one
#   STATE_DIR          run-state directory (default .run-state/<election-id>)

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <election-id>" >&2
  exit 1
fi

ELECTION_ID="$1"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

SITEMAP_PATH="$ROOT_DIR/sitemaps/${ELECTION_ID}.json"
OUTPUT_ROOT="$ROOT_DIR/data/${ELECTION_ID}"
ANOMALIES_PATH="$OUTPUT_ROOT/anomalies.jsonl"
STATE_DIR="${STATE_DIR:-$ROOT_DIR/.run-state/${ELECTION_ID}}"

BATCH_SIZE="${BATCH_SIZE:-200}"
THROTTLE_SECONDS="${THROTTLE_SECONDS:-0.4}"
MAX_BATCHES="${MAX_BATCHES:-0}"
STOP_ON_ANOMALY="${STOP_ON_ANOMALY:-0}"

ALL_IDS_PATH="$STATE_DIR/all_ids.txt"
DONE_IDS_PATH="$STATE_DIR/done_ids.txt"
FAILED_IDS_PATH="$STATE_DIR/failed_ids.txt"
BATCH_LOG_PATH="$STATE_DIR/batches.log"
LAST_BATCH_PATH="$STATE_DIR/last_batch_ids.txt"

CLEANUP_SAMPLES=0
if [[ -n "${SAMPLES_ROOT:-}" ]]; then
  # The per-candidate cleanup below removes each candidate directory after it
  # is parsed. Pointed at the committed fixtures that would delete them, so
  # refuse rather than eat the test corpus.
  case "$(cd "$(dirname "$SAMPLES_ROOT")" 2>/dev/null && pwd)/$(basename "$SAMPLES_ROOT")" in
    "$ROOT_DIR/samples"|"$ROOT_DIR/samples/"*)
      echo "Refusing to run with SAMPLES_ROOT inside $ROOT_DIR/samples — that is the fixture tree and this script deletes candidate directories as it goes." >&2
      exit 1
      ;;
  esac
  mkdir -p "$SAMPLES_ROOT"
else
  SAMPLES_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/vrk-${ELECTION_ID}-samples.XXXXXX")"
  CLEANUP_SAMPLES=1
fi

cleanup_temp_samples() {
  if [[ "$CLEANUP_SAMPLES" == "1" && -n "${SAMPLES_ROOT:-}" && -d "$SAMPLES_ROOT" ]]; then
    rm -rf "$SAMPLES_ROOT"
  fi
}

trap cleanup_temp_samples EXIT

mkdir -p "$STATE_DIR" "$OUTPUT_ROOT"
touch "$DONE_IDS_PATH" "$FAILED_IDS_PATH" "$BATCH_LOG_PATH"

if [[ ! -f "$SITEMAP_PATH" ]]; then
  echo "Missing sitemap: $SITEMAP_PATH" >&2
  echo "Build it first: $PYTHON_BIN -m scraper fetch-sample $ELECTION_ID && $PYTHON_BIN -m scraper sitemap $ELECTION_ID" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python executable not found or not executable: $PYTHON_BIN" >&2
  exit 1
fi

"$PYTHON_BIN" - "$SITEMAP_PATH" > "$ALL_IDS_PATH" <<'PY'
import json, sys
payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
seen = set()
for entry in payload.get("entries", []):
    candidate_id = str(entry.get("candidateId", "")).strip()
    if candidate_id and candidate_id not in seen:
        seen.add(candidate_id)
        print(candidate_id)
PY

build_pending_ids() {
  local pending_path="$1"
  local not_done="$STATE_DIR/not_done_ids.tmp"

  # One grep over the whole id list rather than one grep per candidate: at
  # 13,796 candidates the per-id loop costs ~965,000 subprocesses over a full
  # run. grep -f with an empty pattern file matches nothing, so the first
  # batch of a fresh run is handled separately.
  if [[ -s "$DONE_IDS_PATH" || -s "$FAILED_IDS_PATH" ]]; then
    cat "$DONE_IDS_PATH" "$FAILED_IDS_PATH" 2>/dev/null | awk 'NF' | sort -u > "$STATE_DIR/excluded_ids.tmp"
    if [[ -s "$STATE_DIR/excluded_ids.tmp" ]]; then
      grep -Fxv -f "$STATE_DIR/excluded_ids.tmp" "$ALL_IDS_PATH" | awk 'NF' > "$not_done" || true
    else
      awk 'NF' "$ALL_IDS_PATH" > "$not_done"
    fi
    rm -f "$STATE_DIR/excluded_ids.tmp"
  else
    awk 'NF' "$ALL_IDS_PATH" > "$not_done"
  fi

  : > "$pending_path"
  while IFS= read -r candidate_id; do
    if [[ -f "$OUTPUT_ROOT/${candidate_id}-${ELECTION_ID}.json" ]]; then
      echo "$candidate_id" >> "$DONE_IDS_PATH"
      continue
    fi
    echo "$candidate_id" >> "$pending_path"
  done < "$not_done"
  rm -f "$not_done"
}

report_failures() {
  local failed_count
  failed_count=$(awk 'NF' "$FAILED_IDS_PATH" 2>/dev/null | sort -u | wc -l | tr -d ' ')
  if [[ "$failed_count" != "0" ]]; then
    echo "[$ELECTION_ID] $failed_count candidate(s) failed and were not retried; see $FAILED_IDS_PATH"
    echo "[$ELECTION_ID] retry them by emptying that file and re-running"
    return 1
  fi
  return 0
}

fetch_candidate() {
  "$PYTHON_BIN" -m scraper fetch-candidate-samples "$ELECTION_ID" \
    --sitemap "$SITEMAP_PATH" \
    --samples-root "$SAMPLES_ROOT" \
    --allow-new-samples \
    --candidate-id "$1" >/dev/null
}

parse_candidate() {
  local candidate_id="$1"
  local candidate_anomalies_path="$STATE_DIR/anomalies-${candidate_id}.jsonl"

  "$PYTHON_BIN" -m scraper parse-anketa-samples "$ELECTION_ID" \
    --samples-root "$SAMPLES_ROOT" \
    --output-root "$OUTPUT_ROOT" \
    --anomalies-path "$candidate_anomalies_path" \
    --candidate-id "$candidate_id" >/dev/null

  if [[ -s "$candidate_anomalies_path" ]]; then
    cat "$candidate_anomalies_path" >> "$ANOMALIES_PATH"
  fi
  rm -f "$candidate_anomalies_path"
}

batch_counter=0

while (( MAX_BATCHES == 0 || batch_counter < MAX_BATCHES )); do
  tmp_pending="$STATE_DIR/pending_ids.tmp"
  build_pending_ids "$tmp_pending"

  pending_count=$(wc -l < "$tmp_pending" | tr -d ' ')
  if [[ "$pending_count" == "0" ]]; then
    echo "[$ELECTION_ID] no pending candidates; scrape complete"
    rm -f "$tmp_pending"
    report_failures
    exit $?
  fi

  tmp_batch="$STATE_DIR/current_batch_ids.tmp"
  head -n "$BATCH_SIZE" "$tmp_pending" > "$tmp_batch"
  rm -f "$tmp_pending"

  batch_count=$(wc -l < "$tmp_batch" | tr -d ' ')
  batch_counter=$((batch_counter + 1))
  batch_started_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "[$ELECTION_ID] batch $batch_counter: $batch_count candidates ($pending_count pending)"

  cp "$tmp_batch" "$LAST_BATCH_PATH"

  anomalies_before=0
  if [[ -f "$ANOMALIES_PATH" ]]; then
    anomalies_before=$(wc -l < "$ANOMALIES_PATH" | tr -d ' ')
  fi

  while IFS= read -r candidate_id; do
    if fetch_candidate "$candidate_id" && parse_candidate "$candidate_id" \
        && [[ -f "$OUTPUT_ROOT/${candidate_id}-${ELECTION_ID}.json" ]]; then
      echo "$candidate_id" >> "$DONE_IDS_PATH"
    else
      echo "$candidate_id" >> "$FAILED_IDS_PATH"
      echo "[$ELECTION_ID] FAILED $candidate_id"
    fi
    # Keep the temporary samples directory from growing to the size of the
    # whole election while a long run is in flight.
    rm -rf "${SAMPLES_ROOT:?}/${candidate_id}"
    sleep "$THROTTLE_SECONDS"
  done < "$tmp_batch"

  sort -u -o "$DONE_IDS_PATH" "$DONE_IDS_PATH"
  sort -u -o "$FAILED_IDS_PATH" "$FAILED_IDS_PATH"

  anomalies_after=0
  if [[ -f "$ANOMALIES_PATH" ]]; then
    anomalies_after=$(wc -l < "$ANOMALIES_PATH" | tr -d ' ')
  fi
  new_anomalies=$((anomalies_after - anomalies_before))

  batch_finished_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  printf '%s\tbatch=%s\tsize=%s\tnew_anomalies=%s\tfinished=%s\n' \
    "$batch_started_at" "$batch_counter" "$batch_count" "$new_anomalies" "$batch_finished_at" >> "$BATCH_LOG_PATH"

  done_count=$(wc -l < "$DONE_IDS_PATH" | tr -d ' ')
  total_count=$(wc -l < "$ALL_IDS_PATH" | tr -d ' ')
  echo "[$ELECTION_ID] batch $batch_counter done: $done_count/$total_count parsed, new anomalies=$new_anomalies"
  rm -f "$tmp_batch"

  if (( new_anomalies > 0 )) && [[ "$STOP_ON_ANOMALY" == "1" ]]; then
    echo "[$ELECTION_ID] anomalies recorded in this batch; stopping for review: $ANOMALIES_PATH"
    exit 2
  fi
done

echo "[$ELECTION_ID] completed $batch_counter batch(es)"
report_failures
