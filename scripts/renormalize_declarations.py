"""Rebuild the asset-and-income declaration block from each record's rawData.

`scripts/reparse_diff.py --full --apply` is the primary route for a parser fix:
it re-parses the retained HTML and writes what the parsers now produce. This
script is the shorter one, for the records that route cannot reach — it starts
from `rawData` rather than from HTML, so it works on a record whose page was
never retained. Across the corpus that is 93 records in ten elections (the
`samples-full/` trees are complete but for a handful per election), plus any
election with no retained tree at all.

It was written for issue #81, where `2020-seimo` had no retained HTML at all
and normalized `gautos-pajamos` and `sumoketas-pajamu-mokestis` to `null` on
all 1,753 of its records while the figures sat in `rawData`. Issue #98 widened
it: the declaration block gained the four GPM lines nothing normalized, the
year, form and scope of the extract, and a per-declaration list, and the
2007 municipal election's spouse declarations stopped being reported as the
candidate's.

Equivalence to the real pipeline is measured, not assumed — see
`tests/test_renormalize_declarations.py`, which re-parses retained fixtures
from their HTML and asserts the record this script produces is identical to the
one `parse_anketa_sample` writes, key for key.

Each election resolves to the normalizer its own module calls, found by
following the module's `parse_anketa_sample` back to whichever module defines
the era's page reading, so this script cannot drift from the parser.
A record whose `normalized` has no declaration block is left alone: the block's
absence is the parser's own statement that the page published nothing.

Run from the repo root:

    python scripts/renormalize_declarations.py --dry-run
    python scripts/renormalize_declarations.py
    python scripts/renormalize_declarations.py --election 2020-seimo

`--repo-root` points the corpus lookup at another checkout, for running this
from a worktree (which has no `data/` of its own — it is gitignored, so it
exists only in the primary checkout).

Idempotent: a record whose block already equals the freshly normalized one is
left untouched, so a second run writes nothing. What a run would change is a
histogram of JSON paths rather than a record count, so `--dry-run` says which
keys move and how far before anything is written.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.files import write_json  # noqa: E402

DECLARATION_KEY = "turto-ir-pajamu-deklaracijos"

#: Where an era keeps the declaration in `rawData`, tried in this order.
RAW_DECLARATION_KEYS = ("turtoIrPajamuDeklaracijos", "deklaracija")

#: The normalizer names the eras give the same job, newest first. Every module
#: from 2003 on has one of them, or reaches one through the module whose page
#: reading it reuses.
NORMALIZER_NAMES = (
    "_normalize_turto_ir_pajamu_data",
    "_normalize_deklaracijos_data",
    "_normalize_deklaracija_data",
)

#: How a module that defines none of the above reaches the one that does: it
#: reuses another era's page reading, and the normalizer belongs to that era.
REUSE_NAMES = (
    "parse_anketa_sample",
    "_parse_anketa_sample",
    "parse_anketa_samples",
    "_parse_anketa_samples",
)

ELECTIONS_PACKAGE = Path(__file__).resolve().parents[1] / "scraper" / "elections"


def _resolve_normalizer(module, seen: tuple[str, ...] = ()) -> Callable | None:
    for name in NORMALIZER_NAMES:
        function = getattr(module, name, None)
        if function is not None:
            return function
    for name in REUSE_NAMES:
        function = getattr(module, name, None)
        if function is None:
            continue
        owner = function.__module__
        if owner in seen or owner == module.__name__:
            continue
        found = _resolve_normalizer(
            importlib.import_module(owner), seen + (module.__name__,)
        )
        if found is not None:
            return found
    return None


def election_normalizers() -> dict[str, Callable]:
    """Every election id whose module normalizes a declaration block.

    The 1996-2002 elections are absent: the two 1990s archive families parse
    their declaration straight into `rawData.declaration`, so `rawData` is the
    parse output and there is nothing to re-normalize from, and the 2002
    municipal election reaches its normalizer through a name of its own
    (`normalize_deklaracija`, which returns the unmapped prompts alongside the
    block) — it is wired in below.
    """
    normalizers: dict[str, Callable] = {}
    for package in sorted(p.name for p in ELECTIONS_PACKAGE.iterdir() if p.is_dir()):
        if package.startswith("_"):
            continue
        sitemap = importlib.import_module(f"scraper.elections.{package}.sitemap")
        election_id = getattr(sitemap, "ELECTION_ID", None)
        if not election_id:
            continue
        parser = importlib.import_module(f"scraper.elections.{package}.anketa_parser")
        normalizer = _resolve_normalizer(parser)
        if normalizer is not None:
            normalizers[election_id] = normalizer

    from scraper.elections.savivaldybiu_2002.anketa_parser import (  # noqa: E402
        DEKLARACIJA_OUTPUT_ORDER,
        ELECTION_ID as SAVIVALDYBIU_2002_ELECTION_ID,
        normalize_deklaracija,
    )
    from scraper.elections.seimo_2016.anketa_parser import _order_dict_keys  # noqa: E402

    normalizers[SAVIVALDYBIU_2002_ELECTION_ID] = lambda raw: _order_dict_keys(
        normalize_deklaracija(raw)[0], DEKLARACIJA_OUTPUT_ORDER
    )
    return normalizers


def _stored_raw(record: dict[str, Any]) -> dict[str, Any] | None:
    raw_data = record.get("rawData") or {}
    for key in RAW_DECLARATION_KEYS:
        raw = raw_data.get(key)
        if isinstance(raw, dict):
            return raw
    return None


def _changed_paths(stored: Any, fresh: Any, prefix: str = "") -> list[str]:
    """Every key whose value the fresh block states differently, as a path.

    The report is a histogram of these rather than a record count: "13,795
    records gained `deklaracijos-metai`" is the finding, and "13,795 records
    differ" is not.
    """
    if isinstance(stored, dict) and isinstance(fresh, dict):
        paths: list[str] = []
        for key in sorted(set(stored) | set(fresh)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in stored:
                paths.append(f"+ {path}")
            elif key not in fresh:
                paths.append(f"- {path}")
            else:
                paths.extend(_changed_paths(stored[key], fresh[key], path))
        return paths
    if isinstance(stored, list) and isinstance(fresh, list):
        if len(stored) != len(fresh):
            return [f"~ {prefix or '.'}[] (length)"]
        paths = []
        for item_stored, item_fresh in zip(stored, fresh):
            paths.extend(_changed_paths(item_stored, item_fresh, f"{prefix}[]"))
        return paths
    return [] if stored == fresh else [f"~ {prefix or '.'}"]


def renormalize_election(
    election_dir: Path,
    normalize: Callable,
    *,
    dry_run: bool,
) -> tuple[int, int, Counter]:
    updated = unchanged = 0
    changes: Counter = Counter()

    for record_path in sorted(election_dir.glob("*.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        raw = _stored_raw(record)
        stored = (record.get("normalized") or {}).get(DECLARATION_KEY)
        if raw is None or not isinstance(stored, dict):
            # No declaration in rawData, or a record whose parser published no
            # block at all — the absence is a statement, not a gap to fill.
            continue

        fresh = normalize(raw)
        if stored == fresh:
            unchanged += 1
            continue

        changes.update(_changed_paths(stored, fresh))
        record["normalized"][DECLARATION_KEY] = fresh
        updated += 1
        if not dry_run:
            write_json(record_path, record)

    return updated, unchanged, changes


def main() -> int:
    normalizers = election_normalizers()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--election",
        action="append",
        choices=sorted(normalizers),
        metavar="ELECTION_ID",
        help="Limit the run to one election; repeatable. Defaults to all of them.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Checkout holding data/. Defaults to the cwd.",
    )
    parser.add_argument(
        "--top", type=int, default=10, help="Changed paths to list per election (default 10)."
    )
    args = parser.parse_args()

    data_root = args.repo_root / "data"
    if not data_root.is_dir():
        print(f"No {data_root}/ — pass --repo-root, or run from the repo root.", file=sys.stderr)
        return 1

    total_updated = 0
    for election_id in args.election or sorted(normalizers):
        election_dir = data_root / election_id
        if not election_dir.is_dir():
            continue

        updated, unchanged, changes = renormalize_election(
            election_dir, normalizers[election_id], dry_run=args.dry_run
        )
        total_updated += updated
        if not updated and not unchanged:
            continue

        verb = "would update" if args.dry_run else "updated"
        print(f"{election_id}: {verb} {updated}, already current {unchanged}")
        for path, count in changes.most_common(args.top):
            print(f"    {count:>7}  {path}")
        if len(changes) > args.top:
            print(f"    ... and {len(changes) - args.top} more changed path(s)")

    print(f"\n{total_updated} record(s) {'would be ' if args.dry_run else ''}rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
