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
#
# Three steps per election, not one (issue #143). docs/DATASET.md calls this
# the reproduction entry point, and it used to fetch no portrait at all: the
# portraits a page *links* — every era but 2016-2019, which embed them — are
# archived by a second pass over the finished scrape, and only
# scripts/backfill_url_portraits.py writes the portrait.json that a `photos/`
# sidecar comes from. Measured over the shipped corpus: 25,332 records carry a
# photoMeta naming a fetched URL and 25,294 of the 27,493 sidecar files (92 %,
# 5.2 of the 5.5 GB) exist only because that script ran. Without it a
# from-scratch run differs from the shipped corpus on every one of those
# records, in three paths each, and 25,294 files are simply absent. So:
#
#   1. the runner scrapes and joins results (scripts/run_election_batches.sh);
#   2. backfill_url_portraits.py fetches each linked portrait and lands it
#      beside the candidate's retained pages — it reads data/ to find the
#      URLs, so it genuinely needs the scrape to have finished;
#   3. reparse_diff.py --full --apply turns those URLs into `photos/`
#      sidecars, the same form the embedded eras already have (issue #118).
#
# FETCH_PORTRAITS=0 stops after step 1, for an offline or network-limited run;
# it leaves the corpus 92 % short of its portraits and says so.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$ROOT_DIR/scripts/run_election_batches.sh"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/.run-state/full-run}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
BACKFILL="$ROOT_DIR/scripts/backfill_url_portraits.py"
REPARSE="$ROOT_DIR/scripts/reparse_diff.py"
FETCH_PORTRAITS="${FETCH_PORTRAITS:-1}"
REPARSE_JOBS="${REPARSE_JOBS:-8}"

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
  # Steps 2 and 3, only over an election the runner finished: the backfill
  # walks the records it wrote, and applying a re-parse to a half-scraped
  # election would bake the gap in. Their exit codes join the election's, so
  # a portrait pass that fails is not reported as a complete election.
  if [[ $status -eq 0 && "$FETCH_PORTRAITS" != "0" ]]; then
    echo "--- $election_id: portraits ---"
    "$PYTHON_BIN" "$BACKFILL" "$election_id" 2>&1 | tee -a "$LOG_DIR/${election_id}.log"
    portrait_status=${PIPESTATUS[0]}
    "$PYTHON_BIN" "$REPARSE" --full --jobs "$REPARSE_JOBS" --apply "$election_id" 2>&1 \
      | tee -a "$LOG_DIR/${election_id}.log"
    reparse_status=${PIPESTATUS[0]}
    if [[ $portrait_status -ne 0 || $reparse_status -ne 0 ]]; then
      echo "!!! $election_id: portraits=$portrait_status reparse=$reparse_status" >&2
      status=1
    fi
  elif [[ $status -eq 0 ]]; then
    echo "--- $election_id: FETCH_PORTRAITS=0, linked portraits not archived ---"
  fi
  elapsed=$(( $(date +%s) - election_started ))
  printf '%s\telection=%s\tstatus=%s\telapsed_seconds=%s\n' \
    "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$election_id" "$status" "$elapsed" >> "$LOG_DIR/summary.log"
  echo "=== $election_id finished: status=$status elapsed=${elapsed}s ==="
done

echo "full run finished $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
if [[ "$FETCH_PORTRAITS" == "0" ]]; then
  echo "FETCH_PORTRAITS=0 was set: the linked portraits (92 % of the corpus's" \
       "sidecars) are not archived. Run scripts/backfill_url_portraits.py and" \
       "then scripts/reparse_diff.py --full --apply to finish the corpus." >&2
fi
