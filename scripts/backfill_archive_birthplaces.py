"""Recover birthplaces from the 1996-1997 biographies already in the corpus.

Historical: written when these cards were thought to publish no birth-place
field at all. They do -- "Gimimo vieta" sits inside the malformed
`<!--sql format>` comment alongside the residence, invisible to a DOM parser,
and issue #69 taught `scraper/shared/seimo_archive_1990s.py` to read it. The
card now supplies 852 of the family's 906 records; the biography's opening
sentence is the fallback for the rest (7 of the 9 it reaches are people born
outside Lithuania, whose card leaves the field blank).

The parser applies that fallback inline on a fresh parse, so a re-parsed
corpus leaves this script with nothing to do. It stays because it is the only
way to apply the fallback to records that cannot be re-parsed, and because it
records how the corpus got its prose-derived places. It is a pure offline
pass -- no page is fetched, and nothing but `anketa.gimimo-vieta` (plus its
source marker) is touched. Both paths go through
`extract_biography_birth_place`, so there is one implementation.

Run from the repo root:

    python scripts/backfill_archive_birthplaces.py [--dry-run]

Idempotent: a record that already has `anketa.gimimo-vieta` is left alone.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.seimo_archive_1990s import extract_biography_birth_place  # noqa: E402
from scraper.shared.files import write_json

DATA_ROOT = Path("data")
ELECTIONS = [
    "1996-spalio-20-seimo",
    "1997-kovo-23-seimo-pakartotiniai",
    "1997-gruodzio-21-seimo-pakartotiniai",
    "1998-kovo-22-seimo-pakartotiniai",
    "1998-lapkricio-15-seimo-pakartotiniai",
    "1999-kovo-21-seimo-pakartotiniai",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not DATA_ROOT.is_dir():
        print(f"No {DATA_ROOT}/ here — run from the repo root.", file=sys.stderr)
        return 1

    totals = {"records": 0, "no biography": 0, "already set": 0,
              "recovered": 0, "unresolved": 0}
    for election_id in ELECTIONS:
        election_dir = DATA_ROOT / election_id
        if not election_dir.is_dir():
            print(f"  {election_id}: no data directory, skipping", file=sys.stderr)
            continue
        counts = dict.fromkeys(totals, 0)
        for path in sorted(election_dir.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            counts["records"] += 1
            normalized = record.get("normalized") or {}
            text = (normalized.get("biografija") or {}).get("tekstas")
            if not (text and text.strip()):
                counts["no biography"] += 1
                continue
            anketa = normalized.setdefault("anketa", {})
            if anketa.get("gimimo-vieta"):
                counts["already set"] += 1
                continue
            place = extract_biography_birth_place(text)
            if not place:
                counts["unresolved"] += 1
                continue
            anketa["gimimo-vieta"] = place
            anketa["gimimo-vietos-saltinis"] = "biografijos-tekstas"
            # rawData mirrors what the parser produced, as on a fresh scrape.
            biography = (record.get("rawData") or {}).get("biography")
            if isinstance(biography, dict):
                biography["birthPlace"] = place
            counts["recovered"] += 1
            if not args.dry_run:
                write_json(path, record)
        print(f"  {election_id}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
        for key, value in counts.items():
            totals[key] += value
    print("\ntotals: " + ", ".join(f"{k}={v}" for k, v in totals.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
