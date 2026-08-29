"""Apply the corpus-wide value rules to the records a re-parse cannot reach.

`scripts/reparse_diff.py --full --apply` is the route for a parser fix: it
re-parses the retained HTML and writes what the parsers now produce. Issue
#101's rules went in that way and reached all but 38 of the corpus's 113,073
records. What it cannot reach is the record whose page exists in neither
sample tree -- 4 in `2018-rugsejo-16-seimo-zanavykai`, 8 in `2019-prezidento`
and 26 in `2019-rugsejo-8-seimo`, measured 2026-08-29 -- and those kept the
shapes the rules exist to remove: a money column that is `int` where the rest
of its election is `float`, a transaction sum still stored as the string
`"22000 EUR"`, a value ending in a separator that separates nothing.

Left alone, 38 records are worse than 38 stale records: they are 38 records
that make an otherwise-uniform column non-uniform, which is exactly the thing
#94's typed export cannot have.

So this walks `normalized` and applies the same primitives the parsers call
(`scraper/shared/values.py`) to what is already stored:

* every string through `clean_value`;
* every private-interest row column through `interest_row_columns`, which is
  what splits `sandorio-suma` into a figure and a currency and the
  comma-headed `Dovana, data` cell into the pair it names;
* every `int` at a path its own election stores as `float` elsewhere, cast to
  float.

That last rule is the only one that needs the corpus rather than the record:
whether a column is decimal is a fact about the column, and the election's own
re-parsed records are what state it. A column that is `int` on every record of
its election is left alone -- vote counts, list positions and years are ints
and stay ints.

`rawData` is not touched. It is the page as fetched, and these rules are about
what `normalized` says.

Run from the repo root:

    python scripts/backfill_value_hygiene.py --dry-run
    python scripts/backfill_value_hygiene.py
    python scripts/backfill_value_hygiene.py --election 2019-rugsejo-8-seimo

`--repo-root` points the corpus lookup at another checkout, for running this
from a worktree (`data/` is gitignored, so it exists only where the scrape
ran).

Idempotent: a record already in the right shape is left untouched, so a second
run writes nothing. What a run would change is a histogram of JSON paths
rather than a record count, so `--dry-run` says what moves before anything is
written.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.files import write_json  # noqa: E402
from scraper.shared.values import (  # noqa: E402
    clean_value,
    interest_row_columns,
)

INTEREST_KEY = "privaciu-interesu-deklaracija"


def _numeric_columns(election_dir: Path) -> set[str]:
    """The paths this election stores as `float` on at least one record.

    An `int` at one of these is a record that missed the re-parse; an `int`
    anywhere else is a count.
    """
    float_paths: set[str] = set()

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for value in node:
                walk(value, f"{path}[]")
        elif isinstance(node, float):
            float_paths.add(path)

    for record_path in election_dir.glob("*.json"):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        walk(record.get("normalized"), "")
    return float_paths


def _clean_rows(node: Any, path: str, in_interest: bool, is_row: bool, changes: Counter) -> Any:
    """One `normalized` subtree with the string and row-column rules applied.

    `is_row` is true exactly where the parsers apply `interest_row_columns`:
    on a dict that is an element of a list inside the private-interest block,
    which is what a declaration table's row is. Applying it anywhere else
    would make this script disagree with the parser it exists to catch up
    with, and `reparse_diff.py` would report the difference forever.
    """
    if isinstance(node, dict):
        rebuilt: dict[str, Any] = {}
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else key
            cleaned = _clean_rows(
                value,
                child_path,
                in_interest or key == INTEREST_KEY,
                False,
                changes,
            )
            if is_row and not isinstance(cleaned, (dict, list)):
                produced = interest_row_columns(key, cleaned)
                if produced != {key: cleaned}:
                    changes[child_path] += 1
                rebuilt.update(produced)
            else:
                rebuilt[key] = cleaned
        return rebuilt
    if isinstance(node, list):
        return [
            _clean_rows(value, f"{path}[]", in_interest, in_interest, changes)
            for value in node
        ]
    if isinstance(node, str):
        cleaned = clean_value(node)
        if cleaned != node:
            changes[path] += 1
        return cleaned
    return node


def _float_ints(node: Any, path: str, float_paths: set[str], changes: Counter) -> Any:
    if isinstance(node, dict):
        return {
            key: _float_ints(value, f"{path}.{key}" if path else key, float_paths, changes)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_float_ints(value, f"{path}[]", float_paths, changes) for value in node]
    if isinstance(node, int) and not isinstance(node, bool) and path in float_paths:
        changes[path] += 1
        return float(node)
    return node


def rewrite(normalized: Any, float_paths: set[str], changes: Counter) -> Any:
    """`normalized` with every value rule applied, and what moved counted."""
    cleaned = _clean_rows(normalized, "", False, False, changes)
    # The float cast runs second, over the paths the row rules may have just
    # created (`sandorio-suma` is a float only after `interest_row_columns`).
    return _float_ints(cleaned, "", float_paths, changes)


def run(data_root: Path, elections: list[str] | None, dry_run: bool) -> int:
    election_dirs = sorted(p for p in data_root.iterdir() if p.is_dir())
    if elections:
        wanted = set(elections)
        election_dirs = [p for p in election_dirs if p.name in wanted]
        missing = wanted - {p.name for p in election_dirs}
        if missing:
            print(f"no such election under {data_root}: {', '.join(sorted(missing))}")
            return 2

    total_records = 0
    total_changes: Counter = Counter()
    per_election: dict[str, int] = {}
    touched: dict[str, list[str]] = defaultdict(list)

    for election_dir in election_dirs:
        float_paths = _numeric_columns(election_dir)
        changed_here = 0
        for record_path in sorted(election_dir.glob("*.json")):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            normalized = record.get("normalized")
            if normalized is None:
                continue
            changes: Counter = Counter()
            rewritten = rewrite(normalized, float_paths, changes)
            # `changes`, not equality: `1.0 == 1` in Python, so comparing the
            # trees would miss exactly the int-to-float cast this exists for.
            if not changes:
                continue
            changed_here += 1
            total_changes.update(changes)
            touched[election_dir.name].append(record_path.stem)
            if not dry_run:
                record["normalized"] = rewritten
                write_json(record_path, record)
        if changed_here:
            per_election[election_dir.name] = changed_here
            total_records += changed_here

    verb = "would change" if dry_run else "changed"
    print(f"{verb} {total_records} record(s) across {len(per_election)} election(s)")
    for election, count in sorted(per_election.items()):
        names = touched[election]
        shown = ", ".join(names[:4]) + (", …" if len(names) > 4 else "")
        print(f"  {election}: {count} — {shown}")
    if total_changes:
        print("paths:")
        for path, count in total_changes.most_common(20):
            print(f"  {count:6d}  {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--election", action="append", help="Limit to one election id (repeatable).")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change; write nothing.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Checkout holding data/ (default: this script's repository).",
    )
    args = parser.parse_args()

    data_root = args.repo_root / "data"
    if not data_root.is_dir():
        print(f"no corpus at {data_root}")
        return 2
    return run(data_root, args.election, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
