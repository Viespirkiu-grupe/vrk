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

Run from the repo root:

    python scripts/backfill_archive_declarations.py            # all five
    python scripts/backfill_archive_declarations.py --election 1996-spalio-20-seimo
    python scripts/backfill_archive_declarations.py --dry-run

Resumable: a record that already carries `turto-ir-pajamu-deklaracijos` is
skipped, so an interrupted run can simply be restarted.
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
DECLARATION_KEY = "turto-ir-pajamu-deklaracijos"

ARCHIVE_ELECTIONS = [
    "1996-spalio-20-seimo",
    "1997-kovo-23-savivaldybiu-tarybu",
    "1997-kovo-23-seimo-pakartotiniai",
    "1997-birzelio-29-svenciniu-tarybos-pakartotiniai",
    "1997-gruodzio-21-seimo-pakartotiniai",
]

THROTTLE_SECONDS = 0.25


def declaration_url(record: dict) -> str | None:
    profile = (record.get("normalized") or {}).get("profilis")
    return profile.get("pajamu-deklaracijos-nuoroda") if isinstance(profile, dict) else None


def backfill_election(election_id: str, dry_run: bool) -> dict[str, int]:
    election_dir = DATA_ROOT / election_id
    counts = {"records": 0, "skipped_done": 0, "no_link": 0, "fetched": 0, "failed": 0, "anomalies": 0}
    if not election_dir.is_dir():
        print(f"  {election_id}: no data directory, skipping", file=sys.stderr)
        return counts

    anomalies_path = election_dir / "anomalies.jsonl"
    pending: list[tuple[Path, dict, str]] = []
    for path in sorted(election_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        counts["records"] += 1
        if (record.get("normalized") or {}).get(DECLARATION_KEY) is not None:
            counts["skipped_done"] += 1
            continue
        url = declaration_url(record)
        if not url:
            counts["no_link"] += 1
            continue
        pending.append((path, record, url))

    print(f"  {election_id}: {counts['records']} records, {len(pending)} to fetch "
          f"({counts['skipped_done']} already done, {counts['no_link']} link none)")
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

        sample_dir = SAMPLES_ROOT / election_id / candidate_id
        sample_dir.mkdir(parents=True, exist_ok=True)
        (sample_dir / "declaration.html").write_text(html, encoding="utf-8")

        parsed = parse_declaration(html)
        # Appended last, which is where build_candidate_record puts it.
        record.setdefault("rawData", {})["declaration"] = parsed["declaration"]
        record["normalized"][DECLARATION_KEY] = parsed["declaration"]
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        counts["fetched"] += 1

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
    args = parser.parse_args()

    if not DATA_ROOT.is_dir():
        print(f"No {DATA_ROOT}/ here — run from the repo root.", file=sys.stderr)
        return 1

    totals: dict[str, int] = {}
    for election_id in (args.election or ARCHIVE_ELECTIONS):
        for key, value in backfill_election(election_id, args.dry_run).items():
            totals[key] = totals.get(key, 0) + value
    print("\ntotals: " + ", ".join(f"{k}={v}" for k, v in totals.items()))
    return 1 if totals.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
