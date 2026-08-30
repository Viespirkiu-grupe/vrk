#!/usr/bin/env bash

# Resumable full scrape for any election module.
#
#   scripts/run_election_batches.sh <election-id>
#
# The one batch runner for every election — it replaced the per-election
# scripts that predated it. Candidate samples go to a temporary directory, so
# the test-protected fixtures under samples/html/<election-id>/ are never
# touched.
#
# Environment:
#   BATCH_SIZE         candidates per batch (default 200)
#   MAX_BATCHES        batches per invocation, 0 for "until finished" (default 0)
#   THROTTLE_SECONDS   pause between candidates (default 0.4)
#   STOP_ON_ANOMALY    1 to stop after a batch that recorded an anomaly above
#                      `info` (default 0). The per-election scripts stop by
#                      default; a full unattended run does not, because anomalies
#                      are recorded to anomalies.jsonl for review either way.
#                      `info` events do not stop a run: 8,598 of the corpus's
#                      8,949 are one archive page printing VRK's own query-error
#                      banner, and counting those made this switch unusable on
#                      every archive election (issue #85).
#   SAMPLES_ROOT       reuse a samples directory instead of the default
#                      samples-full/<election-id>
#   KEEP_SAMPLES       1 to keep every candidate's fetched HTML (the default,
#                      under samples-full/<election-id> when SAMPLES_ROOT is
#                      not given). Retained HTML is what lets a later parser
#                      fix be applied by offline re-parse instead of a full
#                      re-scrape — every record in the corpus has its source
#                      HTML today. Set 0 to fetch into a temporary directory
#                      and delete each candidate's HTML after parsing; the
#                      run warns, because that trades ~30 minutes of offline
#                      re-parse for ~27 hours of re-scrape (issue #95).
#   STATE_DIR          run-state directory (default .run-state/<election-id>)

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <election-id>" >&2
  exit 1
fi

ELECTION_ID="$1"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python executable not found or not executable: $PYTHON_BIN" >&2
  exit 1
fi

# sitemaps/ holds one <id>.json and one <id>.results.json per results-joined
# election; a basename glob over it once yielded ids like "2012-seimo.results",
# and the runner took the phantom to a clean "complete" with zero records
# (issue #95). Only ids the CLI can actually fetch get past here.
if ! (cd "$ROOT_DIR" && "$PYTHON_BIN" -c 'import sys
from scraper.cli import FETCHABLE_ELECTION_IDS
sys.exit(0 if sys.argv[1] in FETCHABLE_ELECTION_IDS else 1)' "$ELECTION_ID"); then
  echo "Unknown election id: $ELECTION_ID — not in scraper.cli.FETCHABLE_ELECTION_IDS" >&2
  exit 1
fi

SITEMAP_PATH="$ROOT_DIR/sitemaps/${ELECTION_ID}.json"
RESULTS_PATH="$ROOT_DIR/sitemaps/${ELECTION_ID}.results.json"
OUTPUT_ROOT="$ROOT_DIR/data/${ELECTION_ID}"
ANOMALIES_PATH="$OUTPUT_ROOT/anomalies.jsonl"
STATE_DIR="${STATE_DIR:-$ROOT_DIR/.run-state/${ELECTION_ID}}"

BATCH_SIZE="${BATCH_SIZE:-200}"
THROTTLE_SECONDS="${THROTTLE_SECONDS:-0.4}"
MAX_BATCHES="${MAX_BATCHES:-0}"
STOP_ON_ANOMALY="${STOP_ON_ANOMALY:-0}"
KEEP_SAMPLES="${KEEP_SAMPLES:-1}"

if [[ "$KEEP_SAMPLES" != "1" ]]; then
  echo "[$ELECTION_ID] KEEP_SAMPLES=$KEEP_SAMPLES: fetched HTML will be DELETED after parsing — the next parser fix will cost a full re-scrape instead of an offline re-parse" >&2
fi

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
elif [[ "$KEEP_SAMPLES" == "1" ]]; then
  # Retained HTML has to outlive the run, so it cannot live in a mktemp dir.
  SAMPLES_ROOT="$ROOT_DIR/samples-full/${ELECTION_ID}"
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
  echo "Build it first: $PYTHON_BIN -m scraper sitemap $ELECTION_ID" >&2
  echo "(offline when the tracked listing fixtures cover the election; run" >&2
  echo " $PYTHON_BIN -m scraper fetch-sample $ELECTION_ID --allow-fixture-overwrite first when they do not)" >&2
  exit 1
fi

# 32 elections' candidate pages mark no winner: their `isrinktas` joins in at
# parse time from sitemaps/<id>.results.json, and load_results_lookup leaves it
# silently unknown when that file is absent. A full run used to skip this stage
# entirely — two thirds of the corpus without winners (issue #95).
if (cd "$ROOT_DIR" && "$PYTHON_BIN" -c 'import sys
from scraper.cli import RESULTS_ELECTION_IDS
sys.exit(0 if sys.argv[1] in RESULTS_ELECTION_IDS else 1)' "$ELECTION_ID"); then
  if [[ -f "$RESULTS_PATH" ]]; then
    echo "[$ELECTION_ID] election results present, reusing: $RESULTS_PATH"
  else
    echo "[$ELECTION_ID] building election results (the isrinktas source): $RESULTS_PATH"
    if ! (cd "$ROOT_DIR" && "$PYTHON_BIN" -m scraper build-results "$ELECTION_ID"); then
      echo "[$ELECTION_ID] build-results failed; refusing to parse without it — every record would leave isrinktas unknown" >&2
      exit 1
    fi
  fi
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

# A candidate whose fetch or parse failed used to leave no trace inside the
# corpus: the id went to .run-state/<id>/failed_ids.txt — untracked, excluded
# from every later pending set — and data/ said nothing, which is how three
# candidates went permanently absent unnoticed (issue #95). The failure now
# also lands in anomalies.jsonl, where the anomaly report can see it.
record_candidate_failure() {
  local candidate_id="$1"
  local stage="$2"
  echo "$candidate_id" >> "$FAILED_IDS_PATH"
  echo "[$ELECTION_ID] FAILED $candidate_id ($stage)"
  (cd "$ROOT_DIR" && "$PYTHON_BIN" - "$ELECTION_ID" "$candidate_id" "$stage" <<'PY'
import json, sys
from scraper.shared.anomalies import build_anomaly_event
election_id, candidate_id, stage = sys.argv[1:4]
event = build_anomaly_event(
    event_type="CandidateFetchFailed" if stage == "fetch" else "CandidateParseFailed",
    severity="error",
    stage=stage,
    election_id=election_id,
    candidate_id=candidate_id,
    detail={
        "recordedBy": "run_election_batches.sh",
        "retry": "empty .run-state/<election-id>/failed_ids.txt and re-run",
    },
)
print(json.dumps(event, ensure_ascii=False))
PY
  ) >> "$ANOMALIES_PATH" \
    || echo "[$ELECTION_ID] warning: could not record the failure anomaly for $candidate_id" >&2
}

# "Complete" used to mean "no pending candidates", which counted the failed
# ones as settled. The final report diffs the sitemap's ids against the record
# files actually on disk, so it cannot say complete while candidates are
# missing (issue #95).
final_report() {
  local missing_path="$STATE_DIR/missing_ids.txt"
  : > "$missing_path"
  local candidate_id
  while IFS= read -r candidate_id; do
    if [[ ! -f "$OUTPUT_ROOT/${candidate_id}-${ELECTION_ID}.json" ]]; then
      echo "$candidate_id" >> "$missing_path"
    fi
  done < "$ALL_IDS_PATH"
  local total missing
  total=$(awk 'NF' "$ALL_IDS_PATH" | wc -l | tr -d ' ')
  missing=$(wc -l < "$missing_path" | tr -d ' ')
  if [[ "$missing" == "0" ]]; then
    echo "[$ELECTION_ID] complete: all $total sitemap candidates have records in $OUTPUT_ROOT"
    rm -f "$missing_path"
    return 0
  fi
  echo "[$ELECTION_ID] INCOMPLETE: $missing of $total sitemap candidates have no record; ids in $missing_path"
  echo "[$ELECTION_ID] retry them by emptying $FAILED_IDS_PATH and re-running"
  return 1
}

# What STOP_ON_ANOMALY counts: the events somebody has to look at. `info` is
# for a problem the source has already confessed to -- a page carrying VRK's
# own "Klaida uzklausoje" banner -- and there are 8,598 of those in the corpus
# against 351 of everything else (issue #85).
count_actionable_anomalies() {
  if [[ ! -f "$ANOMALIES_PATH" ]]; then
    echo 0
    return
  fi
  "$PYTHON_BIN" - "$ANOMALIES_PATH" <<'COUNT_PY'
import json, sys
count = 0
with open(sys.argv[1], encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if line and json.loads(line).get("severity") != "info":
            count += 1
print(count)
COUNT_PY
}

# Both stages write their events to a per-candidate file; this appends it to
# the election's and clears it.
collect_anomalies() {
  local candidate_anomalies_path="$1"
  if [[ -s "$candidate_anomalies_path" ]]; then
    cat "$candidate_anomalies_path" >> "$ANOMALIES_PATH"
  fi
  rm -f "$candidate_anomalies_path"
}

# A failed tab download means a whole record section is missing, so the fetch
# stage's anomalies go into the same file the parse stage's do. Until issue #85
# this call sent its output to /dev/null and the events with it.
#
# Both this and parse_candidate capture the command's exit status first and
# return it last: they are called as `if fetch_candidate ... && parse_candidate
# ...`, and ending on the `rm` inside collect_anomalies would report every
# failure as a success.
fetch_candidate() {
  local candidate_id="$1"
  local candidate_anomalies_path="$STATE_DIR/fetch-anomalies-${candidate_id}.jsonl"
  local status=0

  "$PYTHON_BIN" -m scraper fetch-candidate-samples "$ELECTION_ID" \
    --sitemap "$SITEMAP_PATH" \
    --samples-root "$SAMPLES_ROOT" \
    --allow-new-samples \
    --anomalies-path "$candidate_anomalies_path" \
    --candidate-id "$candidate_id" >/dev/null || status=$?

  collect_anomalies "$candidate_anomalies_path"
  return $status
}

parse_candidate() {
  local candidate_id="$1"
  local candidate_anomalies_path="$STATE_DIR/anomalies-${candidate_id}.jsonl"
  local status=0

  "$PYTHON_BIN" -m scraper parse-anketa-samples "$ELECTION_ID" \
    --samples-root "$SAMPLES_ROOT" \
    --output-root "$OUTPUT_ROOT" \
    --anomalies-path "$candidate_anomalies_path" \
    --candidate-id "$candidate_id" >/dev/null || status=$?

  collect_anomalies "$candidate_anomalies_path"
  return $status
}

batch_counter=0

while (( MAX_BATCHES == 0 || batch_counter < MAX_BATCHES )); do
  tmp_pending="$STATE_DIR/pending_ids.tmp"
  build_pending_ids "$tmp_pending"

  pending_count=$(wc -l < "$tmp_pending" | tr -d ' ')
  if [[ "$pending_count" == "0" ]]; then
    echo "[$ELECTION_ID] no pending candidates"
    rm -f "$tmp_pending"
    final_report
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

  anomalies_before=$(count_actionable_anomalies)

  while IFS= read -r candidate_id; do
    if ! fetch_candidate "$candidate_id"; then
      record_candidate_failure "$candidate_id" fetch
    elif ! parse_candidate "$candidate_id" \
        || [[ ! -f "$OUTPUT_ROOT/${candidate_id}-${ELECTION_ID}.json" ]]; then
      record_candidate_failure "$candidate_id" parse
    else
      echo "$candidate_id" >> "$DONE_IDS_PATH"
    fi
    if [[ "$KEEP_SAMPLES" != "1" ]]; then
      # Keep the temporary samples directory from growing to the size of the
      # whole election while a long run is in flight.
      rm -rf "${SAMPLES_ROOT:?}/${candidate_id}"
    fi
    sleep "$THROTTLE_SECONDS"
  done < "$tmp_batch"

  sort -u -o "$DONE_IDS_PATH" "$DONE_IDS_PATH"
  sort -u -o "$FAILED_IDS_PATH" "$FAILED_IDS_PATH"

  anomalies_after=$(count_actionable_anomalies)
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
final_report
