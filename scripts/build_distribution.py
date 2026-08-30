"""Publish the corpus: build the distribution artifacts of issue #94.

The corpus is 113,073 records across 55 elections, and until this script
existed there was no way to get it: `data/` is gitignored, no script
exported anything, and `docs/DATASET.md` offered "re-run the scrapers" —
490,896 GETs and ~27 hours. This writes the gitignored `dist/` that a
GitHub release ships:

    candidacies.csv.gz      the flat comparison table (issue #93's
                            build_candidacy_table, re-used verbatim)
    campaigns.csv.gz        one row per campaign-finance participant
    vrk.sqlite(.gz)         the analysis database: those two as tables,
                            plus elections / persons / parties, indexed
    vrk-corpus.sqlite(.gz)  everything: the analysis database plus a
                            `records` table carrying each record's full
                            rawData / normalized JSON, a `photos` table
                            deduplicated by content hash, and the
                            per-election anomaly log
    MANIFEST.json           per-election record counts, the build date,
                            the parser commit, and a sha256 + byte size
                            for each release artifact

The corpus is then versioned by release tag (`corpus-YYYY-MM-DD`), not by
whatever happens to be on one disk; a full build prints the `gh release
create` line, filled in.

What makes the artifact trustworthy:

* A full build runs `build_candidacy_table`'s fill gate before writing
  anything — a table whose columns silently stopped arriving does not ship.
* The `records` table is lossless: `reconstruct_record` reassembles the
  original record JSON from a row (compact serialization is the only
  difference from the file — 34.5 % of `data/` is pretty-print whitespace),
  and both passes must agree on the record count.
* The record envelope is closed. Issue #89's census measured it at six keys
  everywhere plus two optional; a key this script does not know means the
  schema moved, and the build fails rather than dropping it.
* Photos are stored once and verified. Every `photos/…` sidecar a record
  points at must exist and hash to the record's own `photoMeta.sha256`;
  the bytes land in `photos(sha256, …, data)` and `records.photo_sha256`
  is the join. URL-form portraits (25,305 records) stay URLs — VRK never
  served this scraper those bytes, and archiving them is issue #94's
  separate network job, not a build step. An inline base64 portrait is a
  build error: the 2026-08-29 re-parse (issue #91) externalized the last
  487, and shipping one again would mean an election regressed.

Run from the repo root:

    python scripts/build_distribution.py                    # full corpus + gate
    python scripts/build_distribution.py 2019-prezidento    # subset, no gate
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_candidacy_table as table  # noqa: E402
import build_person_index as identity  # noqa: E402

#: The record envelope, as issue #89's census measured it over the whole
#: corpus: six keys on every record, two optional. Closed on purpose.
ENVELOPE = frozenset(
    {"electionId", "candidateId", "candidateName", "source", "rawData", "normalized"}
)
OPTIONAL_ENVELOPE = frozenset({"kandidatavimas", "candidateNote"})

#: What a release ships, beside MANIFEST.json (which checksums these four).
RELEASE_ARTIFACTS = (
    "candidacies.csv.gz",
    "campaigns.csv.gz",
    "vrk.sqlite.gz",
    "vrk-corpus.sqlite.gz",
)

#: Level 6 for the ~1 GB corpus database — minutes faster than 9 for a few
#: per-cent of size; the small artifacts can afford 9.
CORPUS_GZIP_LEVEL = 6

RECORD_COLUMNS = (
    "election_id",
    "candidate_id",
    "candidate_name",
    "record_file",
    "source_json",
    "kandidatavimas_json",
    "candidate_note",
    "photo_sha256",
    "raw_json",
    "norm_json",
)


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def record_photo(record: dict[str, Any], record_path: Path) -> tuple[str, str | None, bytes] | None:
    """(sha256, mime, bytes) of the record's sidecar portrait, or None.

    Only the `photos/…` sidecar form carries bytes. A URL-form portrait is
    None (nothing to store), and an inline `data:` URI is a build error —
    zero remain since the 2026-08-29 re-parse, so one reappearing means an
    election was rewritten by a pre-migration parser and should be healed
    with `scripts/reparse_diff.py --full --apply`, not shipped as base64.
    """
    profile = (record.get("rawData") or {}).get("profile")
    if not isinstance(profile, dict):
        return None
    source = profile.get("photoSrc")
    if not isinstance(source, str):
        return None
    if source.startswith("data:"):
        raise SystemExit(
            f"{record_path}: inline base64 portrait; re-parse this election"
            " (scripts/reparse_diff.py --full --apply) before building a distribution"
        )
    if not source.startswith("photos/"):
        return None
    photo_path = record_path.parent / source
    if not photo_path.is_file():
        raise SystemExit(f"{record_path}: photoSrc names {source}, and no such sidecar exists")
    raw = photo_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    meta = profile.get("photoMeta")
    declared = meta.get("sha256") if isinstance(meta, dict) else None
    if declared is not None and declared != digest:
        raise SystemExit(
            f"{record_path}: {source} hashes to {digest}, but the record's"
            f" photoMeta.sha256 says {declared} — the sidecar no longer holds"
            " what VRK served"
        )
    mime = meta.get("mime") if isinstance(meta, dict) else None
    return digest, mime, raw


def _envelope_string(record: dict[str, Any], key: str, record_path: Path) -> str | None:
    value = record.get(key)
    if value is None or isinstance(value, str):
        return value
    raise SystemExit(f"{record_path}: envelope key {key} is {type(value).__name__}, not a string")


def write_corpus_sqlite(
    corpus_path: Path,
    base_path: Path,
    data_root: Path,
    election_ids: list[str],
) -> dict[str, Any]:
    """Copy the analysis database and extend it into the full corpus.

    Returns counts: records, per_election, photos (unique), photo_records,
    photo_bytes, anomalies.
    """
    shutil.copyfile(base_path, corpus_path)
    connection = sqlite3.connect(corpus_path)
    counts: dict[str, Any] = {
        "records": 0,
        "per_election": {},
        "photos": 0,
        "photo_records": 0,
        "photo_bytes": 0,
        "anomalies": 0,
    }
    try:
        # A throwaway build: a crash mid-write is answered by rebuilding,
        # so durability buys nothing here and the journal only costs time.
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute(
            """CREATE TABLE records (
                election_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                candidate_name TEXT,
                record_file TEXT NOT NULL,
                source_json TEXT,
                kandidatavimas_json TEXT,
                candidate_note TEXT,
                photo_sha256 TEXT REFERENCES photos(sha256),
                raw_json TEXT,
                norm_json TEXT,
                PRIMARY KEY (election_id, candidate_id)
            )"""
        )
        connection.execute(
            """CREATE TABLE photos (
                sha256 TEXT PRIMARY KEY,
                mime TEXT,
                bytes INTEGER NOT NULL,
                data BLOB NOT NULL
            )"""
        )
        connection.execute(
            "CREATE TABLE anomalies (election_id TEXT NOT NULL, event_json TEXT NOT NULL)"
        )

        seen_photos: set[str] = set()
        for eid in election_ids:
            written = 0
            for record_path in sorted((data_root / eid).glob("*.json")):
                record = json.loads(record_path.read_text(encoding="utf-8"))
                unknown = sorted(set(record) - ENVELOPE - OPTIONAL_ENVELOPE)
                if unknown:
                    raise SystemExit(
                        f"{record_path}: unknown envelope key(s) {unknown} —"
                        " the record schema moved; teach build_distribution.py"
                        " the new key before shipping"
                    )
                missing = sorted(ENVELOPE - set(record))
                if missing:
                    raise SystemExit(f"{record_path}: envelope key(s) missing: {missing}")
                if record["electionId"] != eid:
                    raise SystemExit(
                        f"{record_path}: electionId {record['electionId']!r}"
                        f" does not match its directory {eid!r}"
                    )

                photo = record_photo(record, record_path)
                digest: str | None = None
                if photo is not None:
                    digest, mime, raw = photo
                    counts["photo_records"] += 1
                    if digest not in seen_photos:
                        seen_photos.add(digest)
                        connection.execute(
                            "INSERT INTO photos VALUES (?, ?, ?, ?)",
                            (digest, mime, len(raw), raw),
                        )
                        counts["photos"] += 1
                        counts["photo_bytes"] += len(raw)

                try:
                    connection.execute(
                        f"INSERT INTO records VALUES ({', '.join('?' * len(RECORD_COLUMNS))})",
                        (
                            eid,
                            record["candidateId"],
                            _envelope_string(record, "candidateName", record_path),
                            record_path.name,
                            _compact(record["source"]),
                            _compact(record["kandidatavimas"])
                            if "kandidatavimas" in record
                            else None,
                            _envelope_string(record, "candidateNote", record_path),
                            digest,
                            _compact(record["rawData"]),
                            _compact(record["normalized"]),
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    raise SystemExit(
                        f"{record_path}: two records share (election_id, candidate_id) — {error}"
                    ) from error
                written += 1

            counts["per_election"][eid] = written
            counts["records"] += written

            anomalies_path = data_root / eid / "anomalies.jsonl"
            if anomalies_path.is_file():
                for line in anomalies_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    connection.execute(
                        "INSERT INTO anomalies VALUES (?, ?)",
                        (eid, _compact(json.loads(line))),
                    )
                    counts["anomalies"] += 1

        connection.commit()
    finally:
        connection.close()
    return counts


def reconstruct_record(row: sqlite3.Row) -> dict[str, Any]:
    """The original record, reassembled from a `records` row.

    Structurally identical to the `data/<election-id>/<record_file>` JSON it
    was built from; only the serialization differs (the files are
    pretty-printed, the table is compact). The round trip is pinned by
    tests/test_build_distribution.py.
    """
    record: dict[str, Any] = {
        "electionId": row["election_id"],
        "candidateId": row["candidate_id"],
        "candidateName": row["candidate_name"],
        "source": json.loads(row["source_json"]),
        "rawData": json.loads(row["raw_json"]),
        "normalized": json.loads(row["norm_json"]),
    }
    if row["kandidatavimas_json"] is not None:
        record["kandidatavimas"] = json.loads(row["kandidatavimas_json"])
    if row["candidate_note"] is not None:
        record["candidateNote"] = row["candidate_note"]
    return record


def gzip_file(source: Path, target: Path, level: int) -> None:
    """Gzip a file, streaming; mtime=0 keeps the output byte-stable."""
    with open(source, "rb") as raw, open(target, "wb") as out:
        with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, compresslevel=level) as handle:
            shutil.copyfileobj(raw, handle, length=1024 * 1024)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def parser_commit() -> str | None:
    """The commit the parsers are at — read where the code lives, not at
    --repo-root, which may be a bare data tree."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write_manifest(
    dist: Path,
    stats: dict[str, Any],
    corpus_counts: dict[str, Any],
    subset: list[str] | None,
) -> dict[str, Any]:
    built = datetime.now(timezone.utc)
    manifest: dict[str, Any] = {
        "version": "corpus-" + built.strftime("%Y-%m-%d"),
        "builtAt": built.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parserCommit": parser_commit(),
        "counts": {
            "records": corpus_counts["records"],
            "elections": stats["elections"],
            "persons": stats["persons"],
            "campaigns": stats["campaigns"],
            "photos": corpus_counts["photos"],
            "photoBytes": corpus_counts["photo_bytes"],
            "anomalies": corpus_counts["anomalies"],
        },
        "recordsPerElection": corpus_counts["per_election"],
        "artifacts": {
            name: {"bytes": (dist / name).stat().st_size, "sha256": sha256_file(dist / name)}
            for name in RELEASE_ARTIFACTS
        },
    }
    if subset:
        manifest["subset"] = sorted(subset)
    (dist / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def build_distribution(
    repo_root: Path,
    dist: Path,
    subset: list[str] | None,
    max_drop: float = 5.0,
) -> int:
    rows, campaigns, elections_table, stats = table.build(repo_root, subset)
    persons = stats.pop("persons_rows")

    if subset is None:
        registry_by_id = {
            entry["id"]: entry
            for entry in identity.load_registry(repo_root / "scraper" / "elections.json")
        }
        cells = table.measure_cells(rows)
        gate = table.gate(cells, repo_root / table.BASELINE, registry_by_id, False, max_drop)
        if gate:
            print(
                "fill gate failed — not building distribution artifacts from"
                " a table that lost columns",
                file=sys.stderr,
            )
            return gate
    else:
        print("(subset build: fill gate skipped)")

    table.write_csv_gz(dist / "candidacies.csv.gz", table.COLUMNS, rows)
    table.write_csv_gz(
        dist / "campaigns.csv.gz",
        table.CAMPAIGN_COLUMNS,
        sorted(campaigns.values(), key=lambda c: (c["election_id"], c["campaign_key"])),
    )
    table.write_sqlite(
        dist / "vrk.sqlite",
        rows,
        campaigns,
        elections_table,
        persons,
        repo_root / "scraper" / "parties.json",
    )

    corpus_counts = write_corpus_sqlite(
        dist / "vrk-corpus.sqlite",
        dist / "vrk.sqlite",
        repo_root / "data",
        stats["elections_present"],
    )
    if corpus_counts["records"] != stats["records"]:
        raise SystemExit(
            f"the two passes disagree: the candidacy table projected {stats['records']}"
            f" rows, the records table holds {corpus_counts['records']}"
        )

    gzip_file(dist / "vrk.sqlite", dist / "vrk.sqlite.gz", 9)
    gzip_file(dist / "vrk-corpus.sqlite", dist / "vrk-corpus.sqlite.gz", CORPUS_GZIP_LEVEL)
    manifest = write_manifest(dist, stats, corpus_counts, subset)

    print(f"candidacies:  {stats['records']} rows / {stats['elections']} election(s)")
    print(f"persons:      {stats['persons']}, campaigns: {stats['campaigns']}")
    print(
        f"photos:       {corpus_counts['photos']} unique"
        f" ({corpus_counts['photo_bytes'] / 1e6:.1f} MB)"
        f" across {corpus_counts['photo_records']} record(s)"
    )
    print(f"anomalies:    {corpus_counts['anomalies']} event(s)")
    for name in RELEASE_ARTIFACTS + ("vrk.sqlite", "vrk-corpus.sqlite", "MANIFEST.json"):
        size = (dist / name).stat().st_size
        print(f"wrote {dist / name} ({size / 1024 / 1024:.1f} MB)")

    if subset is None:
        assets = " ".join(f"{dist / name}" for name in RELEASE_ARTIFACTS + ("MANIFEST.json",))
        print(
            f"\npublish:\n  gh release create {manifest['version']} {assets}"
            f" --title 'VRK corpus {manifest['version'].removeprefix('corpus-')}'"
            " --notes '<what changed since the last corpus release>'"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "election_id", nargs="*", help="Subset to build; skips the fill gate."
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--dist", type=Path, default=None, help="Output directory (default <repo-root>/dist).")
    parser.add_argument("--max-drop", type=float, default=5.0)
    args = parser.parse_args()
    return build_distribution(
        args.repo_root,
        args.dist or (args.repo_root / "dist"),
        args.election_id or None,
        args.max_drop,
    )


if __name__ == "__main__":
    raise SystemExit(main())
