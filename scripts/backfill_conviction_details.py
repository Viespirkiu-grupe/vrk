"""Backfill `anketa.teistumo-detales` into the elections that never got it.

Issue #86: 1,614 candidates in the corpus declared that a court had found them
guilty, and 331 of them had conviction details published by VRK that the corpus
could not be asked about. Two separate losses, both recoverable offline:

* **87 records, four elections** (`2016-seimo`, `2020-seimo`, `2019-ep`,
  `2019-rugsejo-8-seimo`) whose detail table reached `rawData.anketa.rows` and
  was normalized nowhere -- those modules mapped the yes/no answer and never
  the record row that follows it. Re-normalizing `rawData` recovers them.
* **244 records, one election** (`2019-kovo-3-savivaldybiu-tarybu`) whose
  detail table reached neither layer: the 2019-era row loop dropped the row
  before it could be stored. That parser was fixed in commit `06ba601` on
  2026-08-18, hours after the election's records were written, and the fix
  never reached the data. The row is only in the retained HTML, so this
  election is re-parsed from `samples-full/` rather than from `rawData`.

Fixing the shared primitive also recovered offences the 2023 collector dropped:
a candidate with more than one offence gets one Q13.4 block per offence,
separated by an empty spacer row, and the era's own collector stopped at the
first one. `2023-kovo-5-savivaldybiu-tarybu-ir-meru` is re-normalized here for
that reason.

Every election the newly-wired modules serve is listed, including the ones with
no declarer at all: the key is emitted for every record of an election that
publishes the block, so that "declared nothing" and "this election does not
publish details" stay distinguishable. Each entry names the function that
election's own module calls, so this script cannot drift from the parser.

Additive by construction, and it says so out loud: a stored non-empty entry
list is only ever extended, never rewritten or dropped, and a record whose
other normalized anketa fields disagree with a fresh parse is left untouched
and reported as a conflict (that is corpus drift -- issue #91 -- not this
fix). The script exits non-zero if any conflict is found.

Run from the repo root:

    python scripts/backfill_conviction_details.py --dry-run
    python scripts/backfill_conviction_details.py
    python scripts/backfill_conviction_details.py --election 2016-seimo

`--repo-root` points the corpus and sample lookups at another checkout, for
running this from a worktree (which has neither `data/` nor `samples-full/` --
both are gitignored, so they exist only in the primary checkout).

Idempotent: a record whose block already equals the freshly derived one is left
untouched, so a second run writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.elections.ep_2019.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_ep_2019,
)
from scraper.elections.ep_2024.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_ep_2024,
)
from scraper.elections.kupiskio_mero_2023.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_kupiskio_2023,
)
from scraper.elections.meru_2021.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_meru_2021,
)
from scraper.elections.meru_2025.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_meru_2025,
)
from scraper.elections.prezidento_2024.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_prezidento_2024,
)
from scraper.elections.savivaldybiu_2019.anketa_parser import (  # noqa: E402
    parse_anketa_html as _parse_savivaldybiu_2019,
)
from scraper.elections.seimo_2016.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_seimo_2016,
)
from scraper.elections.seimo_2020.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_seimo_2020,
)
from scraper.elections.seimo_2024.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_seimo_2024,
)
from scraper.elections.seimo_raseiniu_kedainiu_2023.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_seimo_raseiniai_2023,
)
from scraper.elections.seimo_anyksciu_panevezio_2017.anketa_parser import (  # noqa: E402
    _normalize_anketa_rows as _normalize_seimo_2017,
)
from scraper.shared.files import write_json  # noqa: E402

CONVICTION_KEY = "teistumo-detales"

# The elections re-normalized from their own rawData, and the normalizer each
# one's module calls.
RAWDATA_NORMALIZERS: dict[str, Callable[[list[dict[str, Any]]], dict[str, Any]]] = {
    "2016-seimo": _normalize_seimo_2016,
    "2017-balandzio-23-seimo-anyksciai-panevezys": _normalize_seimo_2017,
    "2018-rugsejo-16-seimo-zanavykai": _normalize_seimo_2017,
    "2019-ep": _normalize_ep_2019,
    "2019-rugsejo-8-seimo": _normalize_seimo_2017,
    "2020-seimo": _normalize_seimo_2020,
    "2021-balandzio-11-radviliskio-mero": _normalize_meru_2021,
    "2021-spalio-10-meru": _normalize_meru_2021,
    "2023-geguzes-7-visagino-mero": _normalize_kupiskio_2023,
    "2023-kovo-5-savivaldybiu-tarybu-ir-meru": _normalize_kupiskio_2023,
    "2023-rugsejo-3-seimo-raseiniai-kedainiai": _normalize_seimo_raseiniai_2023,
    "2023-spalio-8-kupiskio-mero": _normalize_kupiskio_2023,
    "2024-ep": _normalize_ep_2024,
    "2024-prezidento": _normalize_prezidento_2024,
    "2024-seimo": _normalize_seimo_2024,
    "2025-kovo-16-meru": _normalize_meru_2025,
}

# The one election whose detail row is in neither stored layer, so its anketa
# is re-parsed from the retained page. Both sample roots are searched: the
# fixture candidates live under samples/html/, everyone else under samples-full/.
HTML_ELECTION = "2019-kovo-3-savivaldybiu-tarybu"
HTML_SAMPLE_ROOTS = (
    f"samples-full/{HTML_ELECTION}",
    f"samples/html/{HTML_ELECTION}",
)


# The judgment's own fields, as the retired skeleton named them.
JUDGMENT_FIELDS = ("nuosprendzio-data", "nuosprendzio-valstybe", "nuosprendzio-institucija")


def _judgments(block: Any) -> list[dict[str, Any]]:
    """The convictions a stored block records, in either shape.

    `{"irasai": [...]}` is the shape every module now emits. Records written
    before `conviction_entries` replaced the null-field skeleton carry the
    other one: the three judgment fields at the top level, with the offences
    nested under `nusikalstamos-veikos.irasai`.
    """
    if not isinstance(block, dict):
        return []
    if "irasai" in block:
        return [
            {key: value for key, value in entry.items() if key != "nusikalstamos-veikos"}
            for entry in block["irasai"]
            if isinstance(entry, dict)
        ]
    judgment = {field: block.get(field) for field in JUDGMENT_FIELDS}
    return [judgment] if any(judgment.values()) else []


def _offences(block: Any) -> list[Any]:
    """Every offence record the block holds, flattened across its convictions."""
    if not isinstance(block, dict):
        return []
    if "irasai" in block:
        offences: list[Any] = []
        for entry in block["irasai"]:
            veikos = entry.get("nusikalstamos-veikos") if isinstance(entry, dict) else None
            if isinstance(veikos, list):
                offences.extend(veikos)
        return offences
    nested = block.get("nusikalstamos-veikos")
    if isinstance(nested, dict) and isinstance(nested.get("irasai"), list):
        return list(nested["irasai"])
    return []


def _preserves(stored: Any, fresh: Any) -> bool:
    """True when the fresh block keeps every conviction and offence stored."""
    stored_judgments, stored_offences = _judgments(stored), _offences(stored)
    return (
        _judgments(fresh)[: len(stored_judgments)] == stored_judgments
        and _offences(fresh)[: len(stored_offences)] == stored_offences
    )


def _count_gain(counts: Counter, stored: Any, fresh: Any) -> None:
    if stored is None:
        counts["key_added"] += 1
    elif not isinstance(stored, dict) or "irasai" not in stored:
        counts["shape_migrated"] += 1
    counts["judgments_recovered"] += len(_judgments(fresh)) - len(_judgments(stored))
    counts["offences_recovered"] += len(_offences(fresh)) - len(_offences(stored))


def _anketa_html_path(repo_root: Path, candidate_id: str) -> Path | None:
    for root in HTML_SAMPLE_ROOTS:
        path = repo_root / root / candidate_id / "anketa.html"
        if path.exists():
            return path
    return None


def backfill_from_rawdata(
    election_dir: Path,
    normalize: Callable[[list[dict[str, Any]]], dict[str, Any]],
    *,
    dry_run: bool,
) -> tuple[Counter, list[str]]:
    counts: Counter = Counter()
    conflicts: list[str] = []

    for record_path in sorted(election_dir.glob("*.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        rows = ((record.get("rawData") or {}).get("anketa") or {}).get("rows")
        anketa = (record.get("normalized") or {}).get("anketa")
        if not isinstance(rows, list) or not isinstance(anketa, dict):
            counts["no_anketa"] += 1
            continue

        fresh = normalize(rows).get(CONVICTION_KEY)
        stored = anketa.get(CONVICTION_KEY)
        if stored == fresh:
            counts["unchanged"] += 1
            continue
        if not _preserves(stored, fresh):
            conflicts.append(
                f"{record_path.name}: the fresh block drops a stored conviction or offence"
            )
            continue

        _count_gain(counts, stored, fresh)
        anketa[CONVICTION_KEY] = fresh
        counts["updated"] += 1
        if not dry_run:
            write_json(record_path, record)

    return counts, conflicts


def backfill_from_html(
    election_dir: Path,
    repo_root: Path,
    *,
    dry_run: bool,
) -> tuple[Counter, list[str]]:
    counts: Counter = Counter()
    conflicts: list[str] = []

    for record_path in sorted(election_dir.glob("*.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        anketa = (record.get("normalized") or {}).get("anketa")
        if not isinstance(anketa, dict):
            counts["no_anketa"] += 1
            continue

        html_path = _anketa_html_path(repo_root, record["candidateId"])
        if html_path is None:
            counts["no_sample"] += 1
            continue

        parsed = _parse_savivaldybiu_2019(html_path.read_text(encoding="utf-8"))
        fresh_anketa = parsed["anketa"]["normalized"]
        fresh = fresh_anketa.get(CONVICTION_KEY)
        stored = anketa.get(CONVICTION_KEY)

        # Every other normalized anketa field must already agree with the page,
        # or this record is stale in ways beyond the conviction block and is
        # not this script's to heal.
        other_stored = {k: v for k, v in anketa.items() if k != CONVICTION_KEY}
        other_fresh = {k: v for k, v in fresh_anketa.items() if k != CONVICTION_KEY}
        if other_stored != other_fresh or not _preserves(stored, fresh):
            conflicts.append(f"{record_path.name}: fresh parse disagrees outside {CONVICTION_KEY}")
            continue

        # `parse_anketa_html` returns the parser's working dict -- rows,
        # normalized and stats. Only `rows` belongs in a record: the module's
        # own record assembly writes `{"rows": ...}`, and storing the whole
        # dict duplicates `normalized.anketa` inside `rawData` (issue #91
        # caught 13,666 records carrying that copy).
        fresh_raw_anketa = {"rows": parsed["anketa"]["rows"]}
        if stored == fresh and record["rawData"]["anketa"] == fresh_raw_anketa:
            counts["unchanged"] += 1
            continue

        _count_gain(counts, stored, fresh)
        # The recovered row belongs in rawData too: it is what the page said,
        # and a normalized value with no raw row behind it reads as invented.
        record["rawData"]["anketa"] = fresh_raw_anketa
        record["normalized"]["anketa"] = fresh_anketa
        counts["updated"] += 1
        if not dry_run:
            write_json(record_path, record)

    return counts, conflicts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--election",
        action="append",
        choices=sorted({*RAWDATA_NORMALIZERS, HTML_ELECTION}),
        help="Limit the run to one election; repeatable. Defaults to all of them.",
    )
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
    for election_id in args.election or sorted({*RAWDATA_NORMALIZERS, HTML_ELECTION}):
        election_dir = data_root / election_id
        if not election_dir.is_dir():
            print(f"{election_id}: no data/ directory, skipped")
            continue

        if election_id == HTML_ELECTION:
            counts, conflicts = backfill_from_html(
                election_dir, args.repo_root, dry_run=args.dry_run
            )
        else:
            counts, conflicts = backfill_from_rawdata(
                election_dir, RAWDATA_NORMALIZERS[election_id], dry_run=args.dry_run
            )

        verb = "would update" if args.dry_run else "updated"
        detail = ", ".join(
            f"{label} {counts[key]}"
            for key, label in (
                ("key_added", "key added"),
                ("shape_migrated", "shape migrated"),
                ("judgments_recovered", "convictions recovered"),
                ("offences_recovered", "offences recovered"),
                ("no_sample", "no retained page"),
                ("no_anketa", "no anketa"),
            )
            if counts[key]
        )
        print(
            f"{election_id}: {verb} {counts['updated']}, already current {counts['unchanged']}"
            + (f" — {detail}" if detail else "")
        )
        for conflict in conflicts[:10]:
            print(f"  CONFLICT (left untouched) {conflict}")
        if len(conflicts) > 10:
            print(f"  ... and {len(conflicts) - 10} more conflicts")
        if conflicts:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
