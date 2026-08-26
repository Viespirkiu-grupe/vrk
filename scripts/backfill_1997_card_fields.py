"""Add the card fields the 1997 municipal parser used to drop, in place.

`scraper/shared/archive_1990s_card.FIELD_LABELS` was missing "Moksliniai
laipsniai", "Moksliniai vardai", "Buvo išrinktas ..." and "Ką dar norėtų
parašyti apie save" until issue #69, so the 1997 municipal family never read
them: 156 academic degrees and 112 academic titles in the general election
alone, plus the two family-role concepts (`sutuoktinio-vardas-pavarde`,
`vaiku-vardai-pavardes`) the corpus keys separately.

The obvious fix -- re-run `parse-anketa-samples` -- is not available for the
general election: `samples-full/1997-kovo-23-savivaldybiu-tarybu/` retained
`candidate.html` for all 6,270 candidates but no `declaration.html` at all, so
a full re-parse would *drop* the income declarations of 5,471 records to gain
these fields. This script reads the retained `candidate.html` and replaces
only the two blocks that come from it -- `rawData.personal` and
`normalized.anketa` -- leaving the declaration, the candidacy and everything
else exactly as stored.

Replacing those blocks wholesale (rather than merging key by key) is what
keeps their key order identical to a fresh parse. It is safe because the
change is provably additive: re-parsing all 6,276 general-election and 110
Švenčionys records with the new parser changed zero existing values -- the
new labels sit in their own paragraphs, so the gap was "never read", not
"read wrong".

Run from the repo root:

    python scripts/backfill_1997_card_fields.py [--dry-run]

`--repo-root` points the corpus and sample lookups at another checkout, for
running this from a worktree (which has neither `data/` nor `samples-full/` --
both are gitignored, so they exist only in the primary checkout).

Idempotent: running it twice writes the same records.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.files import write_json  # noqa: E402
from scraper.shared.savivaldybiu_archive_1997 import (  # noqa: E402
    card_anketa,
    parse_candidate_detail,
)

# Where each election's retained candidate.html lives. The general election's
# six fixture candidates never reach samples-full (the batch runner skips
# them), so both roots are searched.
SAMPLE_ROOTS = {
    "1997-kovo-23-savivaldybiu-tarybu": [
        "samples-full/1997-kovo-23-savivaldybiu-tarybu",
        "samples/html/1997-kovo-23-savivaldybiu-tarybu",
    ],
    "1997-birzelio-29-svenciniu-tarybos-pakartotiniai": [
        "samples/html/1997-birzelio-29-svenciniu-tarybos-pakartotiniai",
    ],
}


def candidate_html_path(repo_root: Path, election_id: str, candidate_id: str) -> Path | None:
    for root in SAMPLE_ROOTS[election_id]:
        path = repo_root / root / candidate_id / "candidate.html"
        if path.exists():
            return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Checkout holding data/ and the retained samples. Defaults to the cwd.",
    )
    args = parser.parse_args()

    data_root = args.repo_root / "data"
    if not data_root.is_dir():
        print(f"No {data_root}/ — pass --repo-root, or run from the repo root.", file=sys.stderr)
        return 1

    exit_code = 0
    for election_id in SAMPLE_ROOTS:
        election_dir = data_root / election_id
        if not election_dir.is_dir():
            print(f"{election_id}: no data/ directory, skipped")
            continue

        updated = unchanged = missing = 0
        for record_path in sorted(election_dir.glob("*.json")):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            candidate_id = record["candidateId"]
            html_path = candidate_html_path(args.repo_root, election_id, candidate_id)
            if html_path is None:
                missing += 1
                continue

            detail = parse_candidate_detail(
                html_path.read_text(encoding="utf-8"),
                record["source"]["candidateSourceUrl"],
            )
            fresh_personal = detail["personal"]
            # Built through the same function a fresh parse uses, so this
            # script can never drift from the parser.
            fresh_anketa = card_anketa(fresh_personal)

            if (
                record["rawData"].get("personal") == fresh_personal
                and record["normalized"].get("anketa") == fresh_anketa
            ):
                unchanged += 1
                continue

            record["rawData"]["personal"] = fresh_personal
            record["normalized"]["anketa"] = fresh_anketa
            updated += 1
            if not args.dry_run:
                write_json(record_path, record)

        verb = "would update" if args.dry_run else "updated"
        print(f"{election_id}: {verb} {updated}, already current {unchanged}, no sample {missing}")
        if missing:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
