"""Reshape the 1997 municipal archive's `issilavinimas` into the corpus shape.

Every election from 2007 on publishes `anketa.issilavinimas` (or
`biografija.issilavinimas` from 2020) as `{"aprasas", "irasai": [...]}`. The
two 1997 municipal archive elections published it as a bare string -- one
level from a controlled list -- which left `issilavinimas` the only concept in
the corpus with two shapes, and made anything reading it branch.

`scraper/shared/savivaldybiu_archive_1997.py` now emits the corpus shape. This
applies the same change to records already on disk. It is a pure local
reshape of a value already present -- no page is fetched and nothing else in
the record is touched -- so it needs neither retained HTML nor a re-scrape.

Run from the repo root:

    python scripts/reshape_1997_education.py [--dry-run]

Resumable and idempotent: a record whose `issilavinimas` is already a dict
(or absent) is left alone.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.savivaldybiu_archive_1997 import education_record  # noqa: E402
from scraper.shared.files import write_json

DATA_ROOT = Path("data")
ELECTIONS = [
    "1997-kovo-23-savivaldybiu-tarybu",
    "1997-birzelio-29-svenciniu-tarybos-pakartotiniai",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    totals = {"records": 0, "reshaped": 0, "already": 0, "absent": 0}
    for election_id in ELECTIONS:
        election_dir = DATA_ROOT / election_id
        if not election_dir.is_dir():
            print(f"  {election_id}: no data directory, skipping", file=sys.stderr)
            continue
        counts = {"records": 0, "reshaped": 0, "already": 0, "absent": 0}
        for path in sorted(election_dir.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            counts["records"] += 1
            anketa = (record.get("normalized") or {}).get("anketa")
            if not isinstance(anketa, dict):
                counts["absent"] += 1
                continue
            value = anketa.get("issilavinimas")
            if value is None:
                counts["absent"] += 1
                continue
            if isinstance(value, dict):
                counts["already"] += 1
                continue
            anketa["issilavinimas"] = education_record(value)
            counts["reshaped"] += 1
            if not args.dry_run:
                write_json(path, record)
        print(f"  {election_id}: {counts['records']} records — reshaped "
              f"{counts['reshaped']}, already shaped {counts['already']}, "
              f"no value {counts['absent']}")
        for key, value in counts.items():
            totals[key] += value
    print("\ntotals: " + ", ".join(f"{k}={v}" for k, v in totals.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
