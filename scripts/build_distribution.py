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
  everywhere plus two optional, and #89 itself then added a third optional
  one, the `provenance` block (on every record but the 0.4 % with no
  retained page) — which this script did not know, so no distribution could
  be built from the corpus between 2026-09-01 and 2026-09-03. A key this
  script does not know means the schema moved, and the build fails rather
  than dropping it.
* Photos are stored once and verified. Every `photos/…` sidecar a record
  points at must exist and hash to the record's own `photoMeta.sha256`;
  the bytes land in `photos(sha256, …, data)` and `records.photo_sha256`
  is the join. A portrait still in URL form is one whose fetch failed or
  was never attempted (scripts/backfill_url_portraits.py, issue #118) — the
  record keeps the URL and, if it was tried, a `photoMeta` saying how the
  fetch failed; there are no bytes to store. An inline base64 portrait is a
  build error: the 2026-08-29 re-parse (issue #91) externalized the last
  487, and shipping one again would mean an election regressed.

* The release is a profile of the archive, not the archive (issue #142).
  `--profile public`, the default, drops the campaign treasurer's and
  auditor's phone and e-mail from every record -- 790 people who never
  stood for election, on personal accounts and mobiles -- and the
  campaign's own contact line where it repeats one of those values
  (`scripts/pii_inventory.py` holds the list and the inventory behind it),
  and passes every portrait through `scraper/shared/image_metadata.py`, so
  the `photos` table carries the picture without the Exif GPS position,
  camera serial, `Artist` and IPTC blocks 9,889 of the sidecars hold. The
  bytes are stored under the *original* sha256 -- the join key and what the
  record's `photoMeta.sha256` names -- with the stored bytes' own hash
  beside them, so the archive stays verifiable. `--profile full` ships
  everything verbatim, for a mirror of the archive; `MANIFEST.json` says
  which profile built the assets and how many values were removed.

Run from the repo root:

    python scripts/build_distribution.py                    # full corpus + gate, public profile
    python scripts/build_distribution.py 2019-prezidento    # subset, no gate
    python scripts/build_distribution.py --profile full     # the archive verbatim
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
from pii_inventory import PUBLIC_PROFILE_CONDITIONAL, PUBLIC_PROFILE_DROPS  # noqa: E402
from scraper.shared.files import PORTRAIT_KEYS  # noqa: E402
from scraper.shared.image_metadata import strip_metadata  # noqa: E402

#: What a build ships of the archive (issue #142): `public` redacts the
#: third-party contact paths and strips portrait metadata, `full` is the
#: archive verbatim.
PROFILES = ("public", "full")
DEFAULT_PROFILE = "public"

#: The record envelope, as issue #89's census measured it over the whole
#: corpus: six keys on every record, two optional. Closed on purpose.
ENVELOPE = frozenset(
    {"electionId", "candidateId", "candidateName", "source", "rawData", "normalized"}
)
OPTIONAL_ENVELOPE = frozenset({"kandidatavimas", "candidateNote", "provenance"})

#: The terms every release carries (issue #138): the code's licence, the
#: compilation's licence, the attribution it requires and where the full
#: terms live. DATA_TERMS.md is the human-readable statement of the same
#: four facts and tests/test_data_terms.py holds the two together, so a
#: release cannot ship saying one thing while the repository says another.
CODE_LICENSE = "MIT"
DATA_LICENSE = "CC-BY-4.0"
DATA_LICENSE_NAME = "CC BY 4.0"
SOURCE_URL = "https://www.vrk.lt"
TERMS_URL = "https://github.com/Viespirkiu-grupe/vrk/blob/main/DATA_TERMS.md"
ATTRIBUTION = (
    "VRK election corpus by Viešpirkiai (https://github.com/Viespirkiu-grupe/vrk),"
    " CC BY 4.0. Source: Lietuvos Respublikos vyriausioji rinkimų komisija (vrk.lt)."
)

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
    "provenance_json",
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
    The reference sits under `photoSrc` in every family but the 1996-1999
    Seimas archive, whose profile calls it `photoUrl`.
    """
    profile = (record.get("rawData") or {}).get("profile")
    if not isinstance(profile, dict):
        return None
    key = next((name for name in PORTRAIT_KEYS if name in profile), None)
    source = profile.get(key) if key else None
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


def _path_segments(path: str) -> list[tuple[str, bool]]:
    """`a.b[].c` -> [("a", False), ("b", True), ("c", False)]: each segment's
    key and whether a list is fanned out under it."""
    return [(segment[:-2], True) if segment.endswith("[]") else (segment, False) for segment in path.split(".")]


def _delete_path(value: Any, segments: list[tuple[str, bool]], keep: Any) -> int:
    """Remove the leaf `segments` names from `value`, fanning out over lists,
    unless `keep(leaf)` says the value stays. Returns how many leaves went."""
    if not isinstance(value, dict):
        return 0
    key, is_list = segments[0]
    if key not in value:
        return 0
    if len(segments) == 1:
        if keep(value[key]):
            return 0
        del value[key]
        return 1
    child = value[key]
    if is_list:
        return sum(_delete_path(entry, segments[1:], keep) for entry in child) if isinstance(child, list) else 0
    return _delete_path(child, segments[1:], keep)


def _collect(value: Any, segments: list[tuple[str, bool]], out: set[str]) -> None:
    if not isinstance(value, dict):
        return
    key, is_list = segments[0]
    if key not in value:
        return
    if len(segments) == 1:
        leaf = value[key]
        if isinstance(leaf, str) and leaf.strip():
            out.add(leaf.strip())
        return
    child = value[key]
    if is_list:
        if isinstance(child, list):
            for entry in child:
                _collect(entry, segments[1:], out)
    else:
        _collect(child, segments[1:], out)


def redact_record(record: dict[str, Any]) -> int:
    """The public profile, applied in place: the treasurer's and auditor's
    phone and e-mail go (PUBLIC_PROFILE_DROPS, both layers), and the
    campaign's own contact line goes where its value is one of those --
    on 93 of 105 sampled 2016 records it is the treasurer's own number and
    address again. Returns the number of values removed."""
    third_party: set[str] = set()
    for path in PUBLIC_PROFILE_DROPS:
        _collect(record, _path_segments(path), third_party)
    removed = 0
    for path in PUBLIC_PROFILE_DROPS:
        removed += _delete_path(record, _path_segments(path), keep=lambda leaf: False)
    for path in PUBLIC_PROFILE_CONDITIONAL:
        removed += _delete_path(
            record,
            _path_segments(path),
            keep=lambda leaf: not (isinstance(leaf, str) and leaf.strip() in third_party),
        )
    return removed


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
    profile: str = DEFAULT_PROFILE,
) -> dict[str, Any]:
    """Copy the analysis database and extend it into the full corpus.

    Returns counts: records, per_election, photos (unique), photo_records,
    photo_bytes (as stored), anomalies, redacted_values, photos_stripped,
    photos_untouched (containers the stripper leaves alone), photos_malformed.
    """
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; one of {PROFILES}")
    public = profile == "public"
    shutil.copyfile(base_path, corpus_path)
    connection = sqlite3.connect(corpus_path)
    counts: dict[str, Any] = {
        "records": 0,
        "per_election": {},
        "photos": 0,
        "photo_records": 0,
        "photo_bytes": 0,
        "anomalies": 0,
        "redacted_values": 0,
        "photos_stripped": 0,
        "photos_untouched": 0,
        "photos_malformed": 0,
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
                provenance_json TEXT,
                PRIMARY KEY (election_id, candidate_id)
            )"""
        )
        # `sha256` is the archive's hash -- what the record's photoMeta names
        # and what records.photo_sha256 joins on -- whatever was done to the
        # bytes on the way out; `stripped_sha256` hashes what is stored.
        connection.execute(
            """CREATE TABLE photos (
                sha256 TEXT PRIMARY KEY,
                mime TEXT,
                bytes INTEGER NOT NULL,
                stripped INTEGER NOT NULL,
                stripped_sha256 TEXT NOT NULL,
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
                        stored = raw
                        stripped = False
                        if public:
                            result = strip_metadata(raw)
                            stored, stripped = result.data, result.stripped
                            counts["photos_stripped"] += stripped
                            counts["photos_untouched"] += result.container == "other"
                            counts["photos_malformed"] += result.malformed
                        connection.execute(
                            "INSERT INTO photos VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                digest,
                                mime,
                                len(stored),
                                int(stripped),
                                hashlib.sha256(stored).hexdigest(),
                                stored,
                            ),
                        )
                        counts["photos"] += 1
                        counts["photo_bytes"] += len(stored)

                if public:
                    counts["redacted_values"] += redact_record(record)

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
                            _compact(record["provenance"]) if "provenance" in record else None,
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

    Under `--profile full`, structurally identical to the
    `data/<election-id>/<record_file>` JSON it was built from; only the
    serialization differs (the files are pretty-printed, the table is
    compact). Under the public profile it is that record less the values
    `redact_record` removed -- the keys are absent, not nulled. Both are
    pinned by tests/test_build_distribution.py.
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
    if row["provenance_json"] is not None:
        record["provenance"] = json.loads(row["provenance_json"])
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
    profile: str = DEFAULT_PROFILE,
) -> dict[str, Any]:
    built = datetime.now(timezone.utc)
    manifest: dict[str, Any] = {
        "version": "corpus-" + built.strftime("%Y-%m-%d"),
        "builtAt": built.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parserCommit": parser_commit(),
        # The terms travel with the assets (issue #138): a downloaded
        # directory of gzips says what may be done with it and whom to
        # write to, without the repository at hand.
        "license": CODE_LICENSE,
        "dataLicense": DATA_LICENSE,
        "attribution": ATTRIBUTION,
        "terms": TERMS_URL,
        "source": SOURCE_URL,
        # Which profile of the archive this is (issue #142): what was
        # removed from the records and what was stripped from the portraits.
        "profile": profile,
        "redaction": {
            "paths": list(PUBLIC_PROFILE_DROPS) if profile == "public" else [],
            "conditionalPaths": list(PUBLIC_PROFILE_CONDITIONAL) if profile == "public" else [],
            "valuesRemoved": corpus_counts["redacted_values"],
        },
        "counts": {
            "records": corpus_counts["records"],
            "elections": stats["elections"],
            "persons": stats["persons"],
            "campaigns": stats["campaigns"],
            "photos": corpus_counts["photos"],
            "photoBytes": corpus_counts["photo_bytes"],
            "photosStripped": corpus_counts["photos_stripped"],
            "photosMetadataUntouched": corpus_counts["photos_untouched"],
            "photosMalformed": corpus_counts["photos_malformed"],
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
    profile: str = DEFAULT_PROFILE,
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
        profile,
    )
    if corpus_counts["records"] != stats["records"]:
        raise SystemExit(
            f"the two passes disagree: the candidacy table projected {stats['records']}"
            f" rows, the records table holds {corpus_counts['records']}"
        )

    gzip_file(dist / "vrk.sqlite", dist / "vrk.sqlite.gz", 9)
    gzip_file(dist / "vrk-corpus.sqlite", dist / "vrk-corpus.sqlite.gz", CORPUS_GZIP_LEVEL)
    manifest = write_manifest(dist, stats, corpus_counts, subset, profile)

    print(f"profile:      {profile}" + (f" — {corpus_counts['redacted_values']} value(s) removed" if profile == "public" else " (the archive verbatim)"))
    print(f"candidacies:  {stats['records']} rows / {stats['elections']} election(s)")
    print(f"persons:      {stats['persons']}, campaigns: {stats['campaigns']}")
    print(
        f"photos:       {corpus_counts['photos']} unique"
        f" ({corpus_counts['photo_bytes'] / 1e6:.1f} MB)"
        f" across {corpus_counts['photo_records']} record(s)"
        + (
            f"; metadata stripped from {corpus_counts['photos_stripped']},"
            f" {corpus_counts['photos_untouched']} in containers left alone,"
            f" {corpus_counts['photos_malformed']} unparseable"
            if profile == "public"
            else ""
        )
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
            " --notes-file <notes>"
        )
        print("\nthe notes end with these lines (issue #138):\n")
        print(release_notes_footer(manifest["version"]))
    return 0


def release_notes_footer(version: str) -> str:
    """The closing lines of every release's notes: source, licence, the
    attribution a reuser owes, and the address for a removal request. The
    same four facts sit in MANIFEST.json and DATA_TERMS.md."""
    return (
        f"Source: the public candidate pages of the Lithuanian Central Electoral"
        f" Commission ({SOURCE_URL}). Code {CODE_LICENSE}-licensed; the corpus is"
        f" published under {DATA_LICENSE_NAME}"
        f" — reuse it with the attribution below, and see {TERMS_URL} for the"
        f" terms and for how to ask that a person's record be removed or corrected.\n\n"
        f"> {ATTRIBUTION} Release {version}."
    )


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
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default=DEFAULT_PROFILE,
        help="public (default): drop third-party contacts, strip portrait metadata; full: the archive verbatim.",
    )
    args = parser.parse_args()
    return build_distribution(
        args.repo_root,
        args.dist or (args.repo_root / "dist"),
        args.election_id or None,
        args.max_drop,
        args.profile,
    )


if __name__ == "__main__":
    raise SystemExit(main())
