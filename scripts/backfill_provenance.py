"""Stamp `provenance` onto the records the corpus already holds (issue #89).

**Spent** (issue #159): every one of the 113,073 records carries the block,
with one key-set and `schemaVersion` 1 throughout (measured 2026-09-10). What
is still routinely absent is `parserCommit` — null on 49,586 records that were
written before provenance existed, and unknowable for them; a re-parse is the
only thing that fills it.

Newly written records get the block from `write_candidate_record`; the 113,073
records written before it existed do not have one, and re-parsing the whole
corpus just to add metadata would conflate "the envelope gained a block" with
"the parse changed". This walks `data/` once and stamps each record in place:

- ``fetchedAt`` / ``sourceSha256`` from the record's retained primary page —
  ``samples-full/<election>/<candidateId>/`` first, the tracked fixture tree as
  the fallback — exactly the fields the issue says are recoverable offline.
- ``parsedAt`` from the record file's own mtime: the parsers write each record
  once and `reparse_diff --apply` copies with timestamps, so the mtime is the
  moment the stored content was actually produced. Read before the rewrite
  destroys it, and only ever by this one-time stamp.
- ``parserCommit`` stays ``null``: which commit wrote a pre-provenance record
  is genuinely unknown, and a guessed commit would be worse than an honest
  absence. The next re-parse that changes the record fills it in.

A record that already carries `provenance` is left alone — a parser wrote a
fuller block than this backfill can (``--force`` recomputes it anyway, keeping
the fields only a parser knows). A record whose primary page is retained
nowhere is counted and left without a block; fabricating hashes would defeat
the block's purpose. Writes go through the same atomic replace as the parsers'.

    python scripts/backfill_provenance.py                 # every election
    python scripts/backfill_provenance.py 2020-seimo      # named elections
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.files import write_json  # noqa: E402
from scraper.shared.provenance import (  # noqa: E402
    PROVENANCE_SCHEMA_VERSION,
    fetched_at_for,
    utc_iso,
)

#: The one page a record is primarily parsed from, per layout family: the
#: modern eras' questionnaire tab, the 1996-2000 archives' candidate card.
PRIMARY_PAGE_NAMES = ("anketa.html", "candidate.html")


def primary_source(repo_root: Path, election_id: str, candidate_id: str) -> Path | None:
    for tree in ("samples-full", Path("samples") / "html"):
        candidate_dir = repo_root / tree / election_id / candidate_id
        for name in PRIMARY_PAGE_NAMES:
            path = candidate_dir / name
            if path.is_file():
                return path
    return None


def backfill_record(record_path: Path, repo_root: Path, election_id: str, force: bool) -> str:
    """Stamp one record; returns what happened: stamped / present / no-source."""
    record: Any = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        return "no-source"
    if isinstance(record.get("provenance"), dict) and not force:
        return "present"

    candidate_id = str(record.get("candidateId") or "")
    source_path = primary_source(repo_root, election_id, candidate_id)
    if source_path is None:
        return "no-source"

    parsed_at = utc_iso(record_path.stat().st_mtime)
    existing = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    record["provenance"] = {
        "fetchedAt": fetched_at_for(source_path),
        # A --force rerun keeps the moment the content was produced from the
        # existing block; the file's mtime by then says when the block landed.
        "parsedAt": existing.get("parsedAt") or parsed_at,
        "parserCommit": existing.get("parserCommit"),
        "sourceSha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "schemaVersion": PROVENANCE_SCHEMA_VERSION,
    }
    write_json(record_path, record)
    return "stamped"


def backfill_election(repo_root: Path, election_id: str, force: bool) -> dict[str, int]:
    counts = {"stamped": 0, "present": 0, "no-source": 0}
    for record_path in sorted((repo_root / "data" / election_id).glob("*.json")):
        counts[backfill_record(record_path, repo_root, election_id, force)] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "election_id", nargs="*", help="Elections to stamp. Defaults to every data/ directory."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute blocks that already exist (fields only a parser knows are kept).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Checkout holding data/ and the sample trees. Defaults to the cwd.",
    )
    args = parser.parse_args()

    data_root = args.repo_root / "data"
    if not data_root.is_dir():
        print(f"No {data_root}/ here — run from the repo root.", file=sys.stderr)
        return 2

    election_ids = args.election_id or sorted(
        child.name for child in data_root.iterdir() if child.is_dir()
    )

    totals = {"stamped": 0, "present": 0, "no-source": 0}
    for election_id in election_ids:
        if not (data_root / election_id).is_dir():
            print(f"{election_id}: no data/ directory, skipped", file=sys.stderr)
            return 2
        counts = backfill_election(args.repo_root, election_id, args.force)
        for key, value in counts.items():
            totals[key] += value
        note = f"{election_id}: {counts['stamped']} stamped"
        if counts["present"]:
            note += f", {counts['present']} already had provenance"
        if counts["no-source"]:
            note += f", {counts['no-source']} with no retained primary page"
        print(note)

    print(
        f"\n{len(election_ids)} election(s): {totals['stamped']} stamped,"
        f" {totals['present']} already present, {totals['no-source']} without a retained page"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
