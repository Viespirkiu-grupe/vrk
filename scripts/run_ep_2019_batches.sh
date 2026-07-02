#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

SITEMAP_PATH="$ROOT_DIR/sitemaps/2019-ep.json"
OUTPUT_ROOT="$ROOT_DIR/data/2019-ep"
ANOMALIES_PATH="$OUTPUT_ROOT/anomalies.jsonl"
STATE_DIR="${STATE_DIR:-$ROOT_DIR/.run-state/ep-2019}"

BATCH_SIZE="${BATCH_SIZE:-200}"
THROTTLE_SECONDS="${THROTTLE_SECONDS:-0.4}"
MAX_BATCHES="${MAX_BATCHES:-1}"

ALL_IDS_PATH="$STATE_DIR/all_ids.txt"
DONE_IDS_PATH="$STATE_DIR/done_ids.txt"
FAILED_IDS_PATH="$STATE_DIR/failed_ids.txt"
BATCH_LOG_PATH="$STATE_DIR/batches.log"
LAST_BATCH_PATH="$STATE_DIR/last_batch_ids.txt"

CLEANUP_SAMPLES=0
if [[ -n "${SAMPLES_ROOT:-}" ]]; then
  mkdir -p "$SAMPLES_ROOT"
else
  SAMPLES_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/vrk-ep2019-samples.XXXXXX")"
  CLEANUP_SAMPLES=1
fi

cleanup_temp_samples() {
  if [[ "$CLEANUP_SAMPLES" == "1" && -n "${SAMPLES_ROOT:-}" && -d "$SAMPLES_ROOT" ]]; then
    rm -rf "$SAMPLES_ROOT"
  fi
}

trap cleanup_temp_samples EXIT

mkdir -p "$STATE_DIR"
touch "$DONE_IDS_PATH" "$FAILED_IDS_PATH" "$BATCH_LOG_PATH"

if [[ ! -f "$SITEMAP_PATH" ]]; then
  echo "Missing sitemap: $SITEMAP_PATH"
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python executable not found or not executable: $PYTHON_BIN"
  exit 1
fi

jq -r '.entries[].candidateId' "$SITEMAP_PATH" | awk 'NF' | awk '!seen[$0]++' > "$ALL_IDS_PATH"

build_pending_ids() {
  local pending_path
  pending_path="$1"

  awk 'NF' "$ALL_IDS_PATH" | while IFS= read -r candidate_id; do
    if grep -qx "$candidate_id" "$DONE_IDS_PATH"; then
      continue
    fi

    if [[ -f "$OUTPUT_ROOT/${candidate_id}-2019-ep.json" ]]; then
      if ! grep -qx "$candidate_id" "$DONE_IDS_PATH"; then
        echo "$candidate_id" >> "$DONE_IDS_PATH"
      fi
      continue
    fi

    echo "$candidate_id"
  done > "$pending_path"
}

fetch_candidate() {
  local candidate_id
  candidate_id="$1"

  "$PYTHON_BIN" -m scraper fetch-candidate-samples 2019-ep \
    --sitemap "$SITEMAP_PATH" \
    --samples-root "$SAMPLES_ROOT" \
    --allow-new-samples \
    --candidate-id "$candidate_id"
}

parse_candidate() {
  local candidate_id
  candidate_id="$1"

  local candidate_anomalies_path
  candidate_anomalies_path="$STATE_DIR/anomalies-${candidate_id}.jsonl"

  "$PYTHON_BIN" -m scraper parse-anketa-samples 2019-ep \
    --samples-root "$SAMPLES_ROOT" \
    --output-root "$OUTPUT_ROOT" \
    --anomalies-path "$candidate_anomalies_path" \
    --candidate-id "$candidate_id"

  if [[ -s "$candidate_anomalies_path" ]]; then
    cat "$candidate_anomalies_path" >> "$ANOMALIES_PATH"
  fi
  rm -f "$candidate_anomalies_path"
}

batch_counter=0

while (( batch_counter < MAX_BATCHES )); do
  tmp_pending="$STATE_DIR/pending_ids.tmp"
  build_pending_ids "$tmp_pending"

  pending_count=$(wc -l < "$tmp_pending" | tr -d ' ')
  if [[ "$pending_count" == "0" ]]; then
    echo "No pending candidates. Scrape queue is complete."
    rm -f "$tmp_pending"
    exit 0
  fi

  tmp_batch="$STATE_DIR/current_batch_ids.tmp"
  head -n "$BATCH_SIZE" "$tmp_pending" > "$tmp_batch"
  rm -f "$tmp_pending"

  batch_count=$(wc -l < "$tmp_batch" | tr -d ' ')
  if [[ "$batch_count" == "0" ]]; then
    echo "No candidate IDs selected for batch."
    rm -f "$tmp_batch"
    exit 1
  fi

  batch_counter=$((batch_counter + 1))
  batch_started_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "Starting batch $batch_counter with $batch_count candidates"

  cp "$tmp_batch" "$LAST_BATCH_PATH"

  anomalies_before=0
  if [[ -f "$ANOMALIES_PATH" ]]; then
    anomalies_before=$(wc -l < "$ANOMALIES_PATH" | tr -d ' ')
  fi

  while IFS= read -r candidate_id; do
    if fetch_candidate "$candidate_id"; then
      echo "fetched $candidate_id"
      if parse_candidate "$candidate_id"; then
        if [[ -f "$OUTPUT_ROOT/${candidate_id}-2019-ep.json" ]]; then
          echo "$candidate_id" >> "$DONE_IDS_PATH"
          echo "parsed $candidate_id"
        else
          echo "$candidate_id" >> "$FAILED_IDS_PATH"
          echo "parse produced no json $candidate_id"
        fi
      else
        echo "$candidate_id" >> "$FAILED_IDS_PATH"
        echo "failed parse $candidate_id"
      fi
    else
      echo "$candidate_id" >> "$FAILED_IDS_PATH"
      echo "failed fetch $candidate_id"
    fi
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

  echo "Batch $batch_counter finished: size=$batch_count new_anomalies=$new_anomalies"
  rm -f "$tmp_batch"

  if (( new_anomalies > 0 )); then
    echo "New anomalies detected in this batch. Stop and inspect: $ANOMALIES_PATH"
    exit 2
  fi
done

echo "Completed $batch_counter batch(es)."