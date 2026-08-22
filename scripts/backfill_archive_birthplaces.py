"""Recover birthplaces from the 1996-1997 biographies already in the corpus.

Those pages publish no birth-place field; the only source is the biography's
opening sentence, whose text is already stored as `biografija.tekstas`. So
this is a pure offline pass -- no page is fetched, and nothing but
`anketa.gimimo-vieta` (plus its source marker) is touched.

`scraper/shared/seimo_archive_1990s.py` does the same on a fresh scrape; this
applies it to records built before the extractor existed. Both go through
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

DATA_ROOT = Path("data")
ELECTIONS = [
    "1996-spalio-20-seimo",
    "1997-kovo-23-seimo-pakartotiniai",
    "1997-gruodzio-21-seimo-pakartotiniai",
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
                path.write_text(
                    json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
        print(f"  {election_id}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
        for key, value in counts.items():
            totals[key] += value
    print("\ntotals: " + ", ".join(f"{k}={v}" for k, v in totals.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
