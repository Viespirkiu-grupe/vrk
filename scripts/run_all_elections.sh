#!/usr/bin/env bash

# Full scrape across every election module, one at a time.
#
#   scripts/run_all_elections.sh [election-id ...]
#
# With no arguments it runs every election that has a sitemap. Each election is
# resumable on its own, so re-running this after an interruption picks up where
# it stopped: candidates whose output JSON already exists are skipped.
#
# Elections are run sequentially on purpose — the point is a complete archive,
# not the fastest possible one, and vrk.lt should see one request stream.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$ROOT_DIR/scripts/run_election_batches.sh"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/.run-state/full-run}"

mkdir -p "$LOG_DIR"

if [[ $# -gt 0 ]]; then
  ELECTIONS=("$@")
else
  ELECTIONS=()
  for sitemap in "$ROOT_DIR"/sitemaps/*.json; do
    [[ -e "$sitemap" ]] || continue
    ELECTIONS+=("$(basename "$sitemap" .json)")
  done
fi

started_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "full run started $started_at over ${#ELECTIONS[@]} election(s)"

for election_id in "${ELECTIONS[@]}"; do
  election_started=$(date +%s)
  echo "=== $election_id ==="
  "$RUNNER" "$election_id" 2>&1 | tee -a "$LOG_DIR/${election_id}.log"
  status=${PIPESTATUS[0]}
  elapsed=$(( $(date +%s) - election_started ))
  printf '%s\telection=%s\tstatus=%s\telapsed_seconds=%s\n' \
    "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$election_id" "$status" "$elapsed" >> "$LOG_DIR/summary.log"
  echo "=== $election_id finished: status=$status elapsed=${elapsed}s ==="
done

echo "full run finished $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
