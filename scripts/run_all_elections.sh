#!/usr/bin/env bash

# Full scrape across every election module, one at a time.
#
#   scripts/run_all_elections.sh [election-id ...]
#
# With no arguments it runs every election the CLI can fetch. Each election is
# resumable on its own, so re-running this after an interruption picks up where
# it stopped: candidates whose output JSON already exists are skipped.
#
# Elections are run sequentially on purpose — the point is a complete archive,
# not the fastest possible one, and vrk.lt should see one request stream.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$ROOT_DIR/scripts/run_election_batches.sh"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/.run-state/full-run}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

mkdir -p "$LOG_DIR"

if [[ $# -gt 0 ]]; then
  ELECTIONS=("$@")
else
  # The list comes from the CLI's registry, not from globbing sitemaps/*.json:
  # that directory also holds one <id>.results.json per results-joined
  # election, and the glob used to turn each of them into a phantom election
  # the runner then reported complete with zero records (issue #95).
  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python executable not found or not executable: $PYTHON_BIN" >&2
    exit 1
  fi
  ELECTIONS=()
  while IFS= read -r election_id; do
    ELECTIONS+=("$election_id")
  done < <(cd "$ROOT_DIR" && "$PYTHON_BIN" -c 'from scraper.cli import FETCHABLE_ELECTION_IDS
print("\n".join(FETCHABLE_ELECTION_IDS))')
  if [[ ${#ELECTIONS[@]} -eq 0 ]]; then
    echo "Could not read FETCHABLE_ELECTION_IDS from scraper.cli" >&2
    exit 1
  fi
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
