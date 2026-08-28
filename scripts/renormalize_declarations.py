"""Rebuild the asset-and-income declaration block from each record's rawData.

Issue #81: `2020-seimo` normalized `gautos-pajamos` and
`sumoketas-pajamu-mokestis` to `null` on all 1,753 of its declaration records.
Nothing was lost in the fetch -- the figures are in
`rawData.turtoIrPajamuDeklaracijos` -- so the repair is a re-normalization of
what is already on disk, with no re-fetch and no HTML re-parse.

That matters because `2020-seimo` has no retained HTML: `samples-full/` holds
only the 2002 municipal election, and `samples/html/2020-seimo/` holds six
fixture candidates. `parse-anketa-samples` therefore cannot re-parse the
election, and `scripts/run_election_batches.sh` skips candidates whose record
already exists, by design. This script is the offline route the other backfills
take, one step shorter: it starts from `rawData` rather than from HTML.

Equivalence to the real pipeline is measured, not assumed -- see
`tests/test_renormalize_declarations.py`, which re-parses each retained
2020 fixture from its HTML and asserts the record this script produces is
identical to the one `parse_anketa_sample` writes, key for key.

Two parser fixes make records change here:

* the label fix (issue #81) -- the two money rows now match on their opening
  words rather than on the slug of VRK's whole sentence, which is what
  `2020-seimo`'s 2018-era wording missed;
* the sub-euro fix -- VRK prints an amount below one euro without its leading
  zero ("<b>,53 Eur</b>" in the page source), which `_parse_eur_amount` used to
  drop. That one is shared by every modern module, so the elections below are
  every election in the corpus holding such a value.

Both are additive by construction: a value that is already non-null is never
overwritten. The script refuses to write such a record and exits non-zero, so
an unrelated parser drift shows up as a failure rather than as a silent
rewrite.

Run from the repo root:

    python scripts/renormalize_declarations.py --dry-run
    python scripts/renormalize_declarations.py
    python scripts/renormalize_declarations.py --election 2020-seimo

`--repo-root` points the corpus lookup at another checkout, for running this
from a worktree (which has no `data/` of its own -- it is gitignored, so it
exists only in the primary checkout).

Idempotent: a record whose block already equals the freshly normalized one is
left untouched, so a second run writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.elections.ep_2024.anketa_parser import (  # noqa: E402
    _normalize_turto_ir_pajamu_data as _normalize_ep_2024,
)
from scraper.elections.savivaldybiu_2019.anketa_parser import (  # noqa: E402
    _normalize_turto_ir_pajamu_data as _normalize_savivaldybiu_2019,
)
from scraper.elections.seimo_2016.anketa_parser import (  # noqa: E402
    _normalize_turto_ir_pajamu_data as _normalize_seimo_2016,
)
from scraper.elections.seimo_2024.anketa_parser import (  # noqa: E402
    _normalize_turto_ir_pajamu_data as _normalize_seimo_2024,
)
from scraper.shared.files import write_json  # noqa: E402

DECLARATION_KEY = "turto-ir-pajamu-deklaracijos"
RAW_DECLARATION_KEY = "turtoIrPajamuDeklaracijos"

# Every election whose stored declaration block the two fixes can change: the
# three served by the `seimo_2016` normalizer (the label fix) and the four that
# hold a sub-euro amount (the `_parse_eur_amount` fix). Each entry names the
# normalizer that election's own module calls, so this script cannot drift from
# the parser. Elections absent from this table are unaffected -- measured, not
# assumed: no other election has a declaration row whose label the fix newly
# matches, or a value written without its leading zero.
ELECTION_NORMALIZERS = {
    "2016-seimo": _normalize_seimo_2016,
    "2017-balandzio-23-seimo-anyksciai-panevezys": _normalize_seimo_2016,
    "2019-kovo-3-savivaldybiu-tarybu": _normalize_savivaldybiu_2019,
    "2020-seimo": _normalize_seimo_2016,
    "2023-kovo-5-savivaldybiu-tarybu-ir-meru": _normalize_ep_2024,
    "2024-ep": _normalize_ep_2024,
    "2024-seimo": _normalize_seimo_2024,
}


def renormalize_election(
    election_dir: Path,
    normalize,
    *,
    dry_run: bool,
) -> tuple[int, int, Counter, list[str]]:
    updated = unchanged = 0
    recovered: Counter = Counter()
    conflicts: list[str] = []

    for record_path in sorted(election_dir.glob("*.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        raw = (record.get("rawData") or {}).get(RAW_DECLARATION_KEY)
        if not isinstance(raw, dict):
            continue

        stored = record.get("normalized", {}).get(DECLARATION_KEY)
        fresh = normalize(raw)
        if stored == fresh:
            unchanged += 1
            continue

        record_conflicts = [
            f"{record_path.name}: {key} {stored.get(key)!r} -> {fresh.get(key)!r}"
            for key in fresh
            if isinstance(stored, dict)
            and stored.get(key) is not None
            and stored.get(key) != fresh.get(key)
        ]
        if record_conflicts:
            conflicts.extend(record_conflicts)
            continue

        for key, value in fresh.items():
            if value is not None and (not isinstance(stored, dict) or stored.get(key) is None):
                recovered[key] += 1

        record["normalized"][DECLARATION_KEY] = fresh
        updated += 1
        if not dry_run:
            write_json(record_path, record)

    return updated, unchanged, recovered, conflicts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--election",
        action="append",
        choices=sorted(ELECTION_NORMALIZERS),
        help="Limit the run to one election; repeatable. Defaults to all of them.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Checkout holding data/. Defaults to the cwd.",
    )
    args = parser.parse_args()

    data_root = args.repo_root / "data"
    if not data_root.is_dir():
        print(f"No {data_root}/ — pass --repo-root, or run from the repo root.", file=sys.stderr)
        return 1

    exit_code = 0
    for election_id in args.election or sorted(ELECTION_NORMALIZERS):
        election_dir = data_root / election_id
        if not election_dir.is_dir():
            print(f"{election_id}: no data/ directory, skipped")
            continue

        updated, unchanged, recovered, conflicts = renormalize_election(
            election_dir,
            ELECTION_NORMALIZERS[election_id],
            dry_run=args.dry_run,
        )

        verb = "would update" if args.dry_run else "updated"
        summary = ", ".join(f"{key} +{count}" for key, count in sorted(recovered.items()))
        print(
            f"{election_id}: {verb} {updated}, already current {unchanged}"
            + (f" — recovered {summary}" if summary else "")
        )
        for conflict in conflicts:
            print(f"  CONFLICT (left untouched) {conflict}")
        if conflicts:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
