"""Regenerate scraper/shared/vietovardziai.json from the corpus.

The 1996-1997 biographies print a birthplace in the locative; the rest of the
corpus stores the nominative. Suffix rules generate candidates, and this
vocabulary is what decides whether a candidate is a real place -- see
`scraper/shared/seimo_archive_1990s.py`.

Built from `gimimo-vieta` across every non-archive election, keeping values
seen at least `--min-count` times. Run from the repo root:

    python scripts/build_place_vocabulary.py [--min-count 3]
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

DATA_ROOT = Path("data")
OUTPUT_PATH = Path("scraper/shared/vietovardziai.json")

# These publish no birth-place field; they are what the vocabulary serves.
ARCHIVE_ELECTIONS = {
    "1996-spalio-20-seimo",
    "1997-kovo-23-seimo-pakartotiniai",
    "1997-gruodzio-21-seimo-pakartotiniai",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-count", type=int, default=3)
    args = parser.parse_args()

    if not DATA_ROOT.is_dir():
        print(f"No {DATA_ROOT}/ here — run from the repo root.", file=sys.stderr)
        return 1

    counts: collections.Counter[str] = collections.Counter()
    for election_dir in sorted(p for p in DATA_ROOT.iterdir() if p.is_dir()):
        if election_dir.name in ARCHIVE_ELECTIONS:
            continue
        for path in election_dir.glob("*.json"):
            normalized = json.loads(path.read_text(encoding="utf-8")).get("normalized") or {}
            for section in ("anketa", "biografija"):
                data = normalized.get(section)
                place = data.get("gimimo-vieta") if isinstance(data, dict) else None
                if isinstance(place, str) and place.strip():
                    counts[place.strip()] += 1

    places = sorted(name for name, count in counts.items() if count >= args.min_count)
    existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    existing["places"] = places
    OUTPUT_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"{len(counts)} distinct names seen; kept {len(places)} at count>={args.min_count}")
    print(f"wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
