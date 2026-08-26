"""Fetch and merge the 1996-1997 archive income declarations into the corpus.

The five archive elections were scraped before their `kpdl.htm` declarations
were parsed, so their records carry `profilis.pajamu-deklaracijos-nuoroda` and
no figures. The candidate pages themselves have not changed -- only the
declaration is new -- so this fetches that one page per candidate and merges
the parsed block into the existing record, leaving every other field exactly
as it was. That is the same shape of operation as the offline re-parses in
docs/DATASET.md, and much cheaper than a full re-scrape: 6,469 fetches rather
than roughly 20,000, and no window where the corpus is missing records.

`scripts/run_election_batches.sh` cannot do this. It skips any candidate whose
output record already exists, by design -- it is a resumable *initial* scrape,
not a re-scrape -- so using it would mean moving the corpus aside first.

Equivalence to the real pipeline was measured, not assumed: over the 124
archive fixture candidates that have both a candidate page and a declaration
locally, the record this merge produces is identical to the one
`build_candidate_record` writes, key for key.

The fetched HTML is kept under `samples-full/<election-id>/<candidate-id>/`
so a later parser fix can be applied offline instead of re-fetching.

`--retain-only` covers the case where that did not happen. The 1997 municipal
general election's declarations were merged before this script kept its HTML,
so 5,471 of its records were parsed from pages that exist nowhere locally --
which is why issue #69 had to patch that election in place instead of
re-parsing it. This mode fetches exactly the pages whose `declaration.html` is
missing from `samples-full/` and writes **only** that file: records are left
untouched, and the freshly parsed block is compared against the stored one so
a silent disagreement is reported rather than merged. Records parsed before
the parser gained a key count as `stale_keys`, not as a mismatch -- re-parse
those from the now-retained HTML to heal them.

Run from the repo root:

    python scripts/backfill_archive_declarations.py            # all five
    python scripts/backfill_archive_declarations.py --election 1996-spalio-20-seimo
    python scripts/backfill_archive_declarations.py --dry-run
    python scripts/backfill_archive_declarations.py --retain-only

`--repo-root` points the corpus and sample lookups at another checkout, for
running this from a worktree (which has neither `data/` nor `samples-full/` --
both are gitignored, so they exist only in the primary checkout).

Resumable in both modes: the default skips a record that already carries
`turto-ir-pajamu-deklaracijos`, `--retain-only` skips one whose sample file is
already on disk, so an interrupted run can simply be restarted.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.anomalies import build_anomaly_event  # noqa: E402
from scraper.shared.deklaracija_archive_1990s import parse_declaration  # noqa: E402
from scraper.shared.http import fetch_text  # noqa: E402

DATA_ROOT = Path("data")
SAMPLES_ROOT = Path("samples-full")
# The handful of candidates kept as test fixtures live here instead of (or as
# well as) samples-full -- the batch runner skips them, so six of the 1997
# municipal general election's never reach samples-full at all. See
# `sample_paths` for why a page has to be written to every root a candidate
# has a directory in.
FIXTURE_ROOT = Path("samples/html")
DECLARATION_KEY = "turto-ir-pajamu-deklaracijos"

ARCHIVE_ELECTIONS = [
    "1996-spalio-20-seimo",
    "1997-kovo-23-savivaldybiu-tarybu",
    "1997-kovo-23-seimo-pakartotiniai",
    "1997-birzelio-29-svenciniu-tarybos-pakartotiniai",
    "1997-gruodzio-21-seimo-pakartotiniai",
    "1998-kovo-22-seimo-pakartotiniai",
    "1998-lapkricio-15-seimo-pakartotiniai",
]

THROTTLE_SECONDS = 0.25


def declaration_url(record: dict) -> str | None:
    profile = (record.get("normalized") or {}).get("profilis")
    return profile.get("pajamu-deklaracijos-nuoroda") if isinstance(profile, dict) else None


def compare_declaration(stored: dict | None, fresh: dict | None) -> tuple[list[str], list[str]]:
    """`(differing_keys, keys_only_in_fresh)` between a stored declaration and
    a freshly parsed one.

    Compare shared keys only. A record parsed before the parser gained a key is
    *stale*, not wrong -- the 1997 municipal records predate `darboviete`,
    `pareigos`, `nepagrindines-darbovietes` and
    `pareigos-nepagrindinese-darbovietese`, so a whole-dict comparison flags
    all 5,471 of them and says nothing. Only a shared key whose value moved
    means the page and the corpus actually disagree; a key the corpus never
    had means the record wants re-parsing from the now-retained HTML.
    """
    stored = stored or {}
    fresh = fresh or {}
    differing = sorted(k for k in stored if k in fresh and stored[k] != fresh[k])
    added = sorted(set(fresh) - set(stored))
    return differing, added


def sample_paths(election_id: str, candidate_id: str) -> list[Path]:
    """Every directory this candidate's retained pages should land in.

    A candidate can exist under *both* roots -- `samples/html/` for the handful
    kept as test fixtures, `samples-full/` for the batch run. Writing to only
    one of them silently breaks a re-parse driven from the other: doing that to
    `abariunas-bronius` dropped his declaration on the very next re-parse,
    because the page had gone to the fixture directory and `parse-anketa-samples`
    was reading `samples-full/`. So write to all of them, and fall back to
    creating one under `samples-full/` for a candidate with no directory yet.
    """
    existing = [
        root / election_id / candidate_id
        for root in (SAMPLES_ROOT, FIXTURE_ROOT)
        if (root / election_id / candidate_id).is_dir()
    ]
    return existing or [SAMPLES_ROOT / election_id / candidate_id]


def backfill_election(election_id: str, dry_run: bool, retain_only: bool) -> dict[str, int]:
    election_dir = DATA_ROOT / election_id
    counts = {"records": 0, "skipped_done": 0, "no_link": 0, "fetched": 0, "failed": 0,
              "anomalies": 0, "mismatched": 0, "stale_keys": 0}
    if not election_dir.is_dir():
        print(f"  {election_id}: no data directory, skipping", file=sys.stderr)
        return counts

    anomalies_path = election_dir / "anomalies.jsonl"
    pending: list[tuple[Path, dict, str]] = []
    for path in sorted(election_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        counts["records"] += 1
        url = declaration_url(record)
        if not url:
            counts["no_link"] += 1
            continue
        if retain_only:
            candidate_id = record.get("candidateId") or path.stem
            if all((d / "declaration.html").exists()
                   for d in sample_paths(election_id, candidate_id)):
                counts["skipped_done"] += 1
                continue
        elif (record.get("normalized") or {}).get(DECLARATION_KEY) is not None:
            counts["skipped_done"] += 1
            continue
        pending.append((path, record, url))

    done_label = "already retained" if retain_only else "already done"
    print(f"  {election_id}: {counts['records']} records, {len(pending)} to fetch "
          f"({counts['skipped_done']} {done_label}, {counts['no_link']} link none)")
    if dry_run:
        return counts

    for index, (path, record, url) in enumerate(pending, start=1):
        candidate_id = record.get("candidateId") or path.stem
        try:
            html = fetch_text(url)
        except Exception as exc:  # noqa: BLE001 - reported, run continues
            counts["failed"] += 1
            print(f"    FETCH FAILED {candidate_id}: {exc}", file=sys.stderr)
            time.sleep(THROTTLE_SECONDS)
            continue

        for sample_dir in sample_paths(election_id, candidate_id):
            sample_dir.mkdir(parents=True, exist_ok=True)
            (sample_dir / "declaration.html").write_text(html, encoding="utf-8")
        counts["fetched"] += 1

        parsed = parse_declaration(html)
        if retain_only:
            # The record was parsed from this same page already. Writing the
            # file is the whole job; parsing again is only to prove the page
            # still says what the corpus recorded.
            differing, added = compare_declaration(
                (record.get("normalized") or {}).get(DECLARATION_KEY),
                parsed["declaration"],
            )
            if differing:
                counts["mismatched"] += 1
                print(f"    MISMATCH {candidate_id}: {', '.join(differing)}", file=sys.stderr)
            elif added:
                counts["stale_keys"] += 1
            time.sleep(THROTTLE_SECONDS)
            if index % 250 == 0 or index == len(pending):
                print(f"    {election_id}: {index}/{len(pending)} (failed "
                      f"{counts['failed']}, mismatched {counts['mismatched']}, "
                      f"stale {counts['stale_keys']})", flush=True)
            continue

        # Appended last, which is where build_candidate_record puts it.
        record.setdefault("rawData", {})["declaration"] = parsed["declaration"]
        record["normalized"][DECLARATION_KEY] = parsed["declaration"]
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        if parsed["anomalies"]:
            with anomalies_path.open("a", encoding="utf-8") as handle:
                for event in parsed["anomalies"]:
                    handle.write(json.dumps(build_anomaly_event(
                        event_type=event["eventType"],
                        severity=event["severity"],
                        stage="parse",
                        election_id=election_id,
                        candidate_id=candidate_id,
                        source_url=url,
                        detail=event["detail"],
                    ), ensure_ascii=False) + "\n")
                    counts["anomalies"] += 1

        if index % 250 == 0 or index == len(pending):
            print(f"    {election_id}: {index}/{len(pending)} "
                  f"(failed {counts['failed']}, anomalies {counts['anomalies']})", flush=True)
        time.sleep(THROTTLE_SECONDS)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--election", action="append", choices=ARCHIVE_ELECTIONS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--retain-only",
        action="store_true",
        help="Fetch only the pages missing from samples-full/ and write nothing but "
             "the HTML; verify the fetched page still matches the stored record.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Checkout holding data/ and the retained samples. Defaults to the cwd.",
    )
    args = parser.parse_args()

    global DATA_ROOT, SAMPLES_ROOT, FIXTURE_ROOT
    DATA_ROOT = args.repo_root / DATA_ROOT
    SAMPLES_ROOT = args.repo_root / SAMPLES_ROOT
    FIXTURE_ROOT = args.repo_root / FIXTURE_ROOT

    if not DATA_ROOT.is_dir():
        print(f"No {DATA_ROOT}/ — pass --repo-root, or run from the repo root.", file=sys.stderr)
        return 1

    totals: dict[str, int] = {}
    for election_id in (args.election or ARCHIVE_ELECTIONS):
        for key, value in backfill_election(election_id, args.dry_run, args.retain_only).items():
            totals[key] = totals.get(key, 0) + value
    print("\ntotals: " + ", ".join(f"{k}={v}" for k, v in totals.items()))
    return 1 if totals.get("failed") or totals.get("mismatched") else 0


if __name__ == "__main__":
    raise SystemExit(main())
