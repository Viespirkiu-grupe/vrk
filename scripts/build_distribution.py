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
    vrk-corpus.sqlite(.gz)  everything but the image bytes: the analysis
                            database plus a `records` table carrying each
                            record's full rawData / normalized JSON, a
                            `photos` table (one row per unique portrait,
                            naming the part that holds it), and the
                            per-election anomaly log
    vrk-photos-N.sqlite     the portraits themselves, deduplicated by
                            content hash, in as many parts as keep every
                            asset under GitHub's 2 GiB cap (issue #130)
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
  the bytes land in a part's `photos(sha256, …, data)`, the corpus
  database's own `photos` row names that part, and `records.photo_sha256`
  is the join. A portrait still in URL form is one whose fetch failed or
  was never attempted (scripts/backfill_url_portraits.py, issue #118) — the
  record keeps the URL and, if it was tried, a `photoMeta` saying how the
  fetch failed; there are no bytes to store. An inline base64 portrait is a
  build error: the 2026-08-29 re-parse (issue #91) externalized the last
  487, and shipping one again would mean an election regressed.
* No asset is larger than GitHub will take (issue #130). The portrait
  archive of issue #118 put 5.5 GB of JPEG and PNG -- which gzip cannot
  shrink -- into the corpus database, and GitHub refuses a release asset
  over 2 GiB, so the first full build after it could not have been
  uploaded. The images now fill `vrk-photos-1.sqlite`,
  `vrk-photos-2.sqlite`, … in build order, each closed before the next
  image would take it past PHOTO_PART_BUDGET, and every asset is measured
  against the cap before anything reaches dist/.

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
import os
import shlex
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_candidacy_table as table  # noqa: E402
import build_person_index as identity  # noqa: E402
from pii_inventory import PUBLIC_PROFILE_CONDITIONAL, PUBLIC_PROFILE_DROPS  # noqa: E402
from scraper.shared import provenance  # noqa: E402
from scraper.shared.files import PORTRAIT_KEYS, write_json  # noqa: E402
from scraper.shared.image_metadata import strip_metadata  # noqa: E402

#: The shape of what a release ships. Bumped when a column, table or manifest
#: key changes meaning; a consumer reads it from `MANIFEST.json`, from the
#: `meta` table of every database, and from `PRAGMA user_version`. Before
#: issue #156 a 602 MB download said nothing at all about what it was.
#: 2 (issue #130): the image bytes moved out of `vrk-corpus.sqlite` into the
#: `vrk-photos-N.sqlite` parts, and its `photos.data` column became `part`.
SCHEMA_VERSION = 2

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

#: What every release ships beside MANIFEST.json, ahead of the photo parts
#: the build fills (`release_assets` lists both; the manifest checksums all).
RELEASE_ARTIFACTS = (
    "candidacies.csv.gz",
    "campaigns.csv.gz",
    "vrk.sqlite.gz",
    "vrk-corpus.sqlite.gz",
)

#: Level 6 for the ~1 GB corpus database — minutes faster than 9 for a few
#: per-cent of size; the small artifacts can afford 9.
CORPUS_GZIP_LEVEL = 6

#: GitHub refuses a release asset larger than this.
RELEASE_ASSET_LIMIT = 2 * 1024**3

#: The portraits ship beside the corpus database, not inside it (issue #130):
#: 27,493 sidecars are 5.5 GB of JPEG and PNG that gzip cannot shrink, and in
#: one database they made a ~6 GB asset. The unique images fill numbered parts
#: in build order -- election by election, record file by record file -- and
#: a part is closed before the next image would take its image bytes past the
#: budget, which leaves 247 MB of the cap for SQLite's own pages. The parts
#: are not gzipped: there is nothing in them for gzip to take out, and an
#: uncompressed part can be ATTACHed where it lands.
PHOTO_PART_NAME = "vrk-photos-{index}.sqlite"
PHOTO_PART_GLOB = "vrk-photos-*.sqlite"
PHOTO_PART_BUDGET = 1_900_000_000

RECORD_COLUMNS = (
    "election_id",
    "candidate_id",
    "candidate_name",
    "record_file",
    "source_json",
    "kandidatavimas_json",
    # JSON, not TEXT: `candidateNote` is present *and null* on 27,472 of the
    # 27,478 records that have it, and a TEXT column cannot tell that from
    # absent — so the round trip dropped the key on all 27,472 while three
    # places called it lossless (issue #156).
    "candidate_note_json",
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


PART_PHOTOS_TABLE = """CREATE TABLE photos (
    sha256 TEXT PRIMARY KEY,
    mime TEXT,
    bytes INTEGER NOT NULL,
    stripped INTEGER NOT NULL,
    stripped_sha256 TEXT NOT NULL,
    data BLOB NOT NULL
)"""


class PhotoParts:
    """The portraits' bytes, packed into release-sized SQLite files (issue #130).

    Images arrive in build order -- election by election, record file by
    record file, each unique image once -- and fill `vrk-photos-1.sqlite`
    until the next one would take its image bytes past the budget, then
    `vrk-photos-2.sqlite`, and so on. The split is therefore the same on
    every build of the same corpus, and an election's portraits sit together
    except where one straddles a boundary. Each part is a slice of what used
    to be one `photos` table, columns and all, so it reads on its own; its
    `meta` says which slice it is.
    """

    def __init__(self, directory: Path, budget: int) -> None:
        self.directory = directory
        self.budget = budget
        self.parts: list[dict[str, Any]] = []
        self._connections: list[sqlite3.Connection] = []

    def add(self, election_id: str, row: tuple[str, str | None, int, int, str, bytes]) -> str:
        """Store one image row; returns the name of the part holding it.

        A part takes at least one image, so a single image bigger than the
        budget still lands somewhere -- and `check_asset_sizes` then says so.
        """
        size = len(row[5])
        current = self.parts[-1] if self.parts else None
        if current is None or (current["photos"] and current["photoBytes"] + size > self.budget):
            current = self._open()
        self._connections[-1].execute("INSERT INTO photos VALUES (?, ?, ?, ?, ?, ?)", row)
        current["photos"] += 1
        current["photoBytes"] += size
        if election_id not in current["elections"]:
            current["elections"].append(election_id)
        return current["name"]

    def _open(self) -> dict[str, Any]:
        name = PHOTO_PART_NAME.format(index=len(self.parts) + 1)
        path = self.directory / name
        path.unlink(missing_ok=True)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute(PART_PHOTOS_TABLE)
        self._connections.append(connection)
        self.parts.append({"name": name, "photos": 0, "photoBytes": 0, "elections": []})
        return self.parts[-1]

    def close(self, meta: dict[str, str] | None) -> None:
        """Close every part, writing its `meta` first when the build finished."""
        for index, (connection, part) in enumerate(zip(self._connections, self.parts), start=1):
            try:
                if meta is not None:
                    write_meta(connection, meta | {
                        "part": str(index),
                        "parts": str(len(self.parts)),
                        "photos": str(part["photos"]),
                        "elections": ",".join(part["elections"]),
                    })
                    connection.commit()
            finally:
                connection.close()
        self._connections = []


def release_assets(corpus_counts: dict[str, Any]) -> tuple[str, ...]:
    """Every file a release uploads beside MANIFEST.json: the four fixed
    artifacts, then the photo parts this build filled."""
    return RELEASE_ARTIFACTS + tuple(part["name"] for part in corpus_counts["photo_parts"])


def check_asset_sizes(directory: Path, names: tuple[str, ...]) -> None:
    """Refuse a build holding an asset GitHub would refuse (issue #130).

    Measured, not predicted: the budget keeps a photo part under the cap and
    the corpus database gzips to a fraction of it, but a corpus that grows is
    exactly how the last estimate went stale.
    """
    oversized = [
        (name, (directory / name).stat().st_size)
        for name in names
        if (directory / name).stat().st_size > RELEASE_ASSET_LIMIT
    ]
    if oversized:
        listed = "\n".join(f"    {name}: {size:,} bytes" for name, size in oversized)
        raise SystemExit(
            f"{len(oversized)} asset(s) over the {RELEASE_ASSET_LIMIT:,}-byte limit GitHub"
            f" puts on a release asset:\n{listed}\nNothing was promoted to dist/; lower"
            " PHOTO_PART_BUDGET, or split whatever grew."
        )


def write_corpus_sqlite(
    corpus_path: Path,
    base_path: Path,
    data_root: Path,
    election_ids: list[str],
    profile: str = DEFAULT_PROFILE,
    part_budget: int | None = None,
) -> dict[str, Any]:
    """Copy the analysis database and extend it into the full corpus.

    The portraits' bytes go into `vrk-photos-N.sqlite` parts beside
    `corpus_path` (issue #130); the corpus database's `photos` table keeps
    one row per image -- its hashes, type and size -- and the part holding it.

    Returns counts: records, per_election, photos (unique), photo_records,
    photo_bytes (as stored), anomalies, redacted_values, photos_stripped,
    photos_untouched (containers the stripper leaves alone), photos_malformed,
    and photo_parts -- one {name, photos, photoBytes, elections} per part.
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
        "parser_commits": {},
    }
    parser_commits: Counter[str] = Counter()
    anomaly_files: list[str] = []
    parts = PhotoParts(corpus_path.parent, PHOTO_PART_BUDGET if part_budget is None else part_budget)
    part_meta: dict[str, str] | None = None
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
                candidate_note_json TEXT,
                photo_sha256 TEXT REFERENCES photos(sha256),
                raw_json TEXT,
                norm_json TEXT,
                provenance_json TEXT,
                PRIMARY KEY (election_id, candidate_id)
            )"""
        )
        # `sha256` is the archive's hash -- what the record's photoMeta names
        # and what records.photo_sha256 joins on -- whatever was done to the
        # bytes on the way out; `stripped_sha256` hashes what is stored. The
        # bytes themselves are in the part `part` names (issue #130).
        connection.execute(
            """CREATE TABLE photos (
                sha256 TEXT PRIMARY KEY,
                mime TEXT,
                bytes INTEGER NOT NULL,
                stripped INTEGER NOT NULL,
                stripped_sha256 TEXT NOT NULL,
                part TEXT NOT NULL
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
                        row = (
                            digest,
                            mime,
                            len(stored),
                            int(stripped),
                            hashlib.sha256(stored).hexdigest(),
                        )
                        part = parts.add(eid, row + (stored,))
                        connection.execute(
                            "INSERT INTO photos VALUES (?, ?, ?, ?, ?, ?)", row + (part,)
                        )
                        counts["photos"] += 1
                        counts["photo_bytes"] += len(stored)

                stamp = (record.get("provenance") or {}).get("parserCommit")
                parser_commits[stamp or "none"] += 1

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
                            _compact(record["candidateNote"])
                            if "candidateNote" in record
                            else None,
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
                # An *empty* anomalies.jsonl says "scraped, nothing to
                # report", which is not the same as no file at all — and with
                # no row to carry it, the unpacked tree lost that distinction
                # (issue #156). The election ids are recorded in `meta`.
                anomaly_files.append(eid)
                for line in anomalies_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    connection.execute(
                        "INSERT INTO anomalies VALUES (?, ?)",
                        (eid, _compact(json.loads(line))),
                    )
                    counts["anomalies"] += 1

        terms = {
            "schemaVersion": str(SCHEMA_VERSION),
            "profile": profile,
            "builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "buildCommit": build_commit() or "",
            "source": SOURCE_URL,
            "dataLicense": DATA_LICENSE,
            "attribution": ATTRIBUTION,
            "terms": TERMS_URL,
        }
        write_meta(connection, terms | {
            "records": str(counts["records"]),
            "elections": str(len(election_ids)),
            "photos": str(counts["photos"]),
            # The parts holding the image bytes, in order (issue #130):
            # what unpack_corpus.py looks for beside this file.
            "photoParts": ",".join(part["name"] for part in parts.parts),
            "anomalyFiles": ",".join(anomaly_files),
        })
        connection.commit()
        part_meta = terms
    finally:
        parts.close(part_meta)
        connection.close()
    counts["parser_commits"] = dict(parser_commits.most_common())
    counts["photo_parts"] = parts.parts
    return counts


def write_meta(connection: sqlite3.Connection, entries: dict[str, str]) -> None:
    """`meta(key, value)` plus `PRAGMA user_version`, in both databases.

    A consumer who downloads the 602 MB "Everything" asset had an anonymous
    2.5 GB file: no meta table, no user_version, no schemaVersion anywhere
    (issue #156). Both are cheap and both are readable without this
    repository — `SELECT * FROM meta` and `PRAGMA user_version`.
    """
    connection.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    connection.executemany(
        "INSERT OR REPLACE INTO meta VALUES (?, ?)", sorted(entries.items())
    )
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def reconstruct_record(row: sqlite3.Row) -> dict[str, Any]:
    """The original record, reassembled from a `records` row.

    Under `--profile full`, structurally identical to the
    `data/<election-id>/<record_file>` JSON it was built from; only the
    serialization differs (the files are pretty-printed, the table is
    compact). Under the public profile it is that record less the values
    `redact_record` removed -- the keys are absent, not nulled. Both are
    pinned by tests/test_build_distribution.py.
    """
    # Built in the order the record files use --
    # electionId, candidateId, candidateName, [candidateNote],
    # [kandidatavimas], source, rawData, normalized, [provenance] -- so an
    # unpacked corpus is byte-comparable with the one it was built from and
    # not merely equal as JSON (issue #156).
    record: dict[str, Any] = {
        "electionId": row["election_id"],
        "candidateId": row["candidate_id"],
        "candidateName": row["candidate_name"],
    }
    if row["candidate_note_json"] is not None:
        record["candidateNote"] = json.loads(row["candidate_note_json"])
    if row["kandidatavimas_json"] is not None:
        record["kandidatavimas"] = json.loads(row["kandidatavimas_json"])
    record["source"] = json.loads(row["source_json"])
    record["rawData"] = json.loads(row["raw_json"])
    record["normalized"] = json.loads(row["norm_json"])
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


def build_commit() -> str | None:
    """The commit this build ran at, `-dirty` when the checkout was not clean.

    `scraper.shared.provenance.parser_commit` already reads it that way and
    caches it; this used to be a bare `git rev-parse --short HEAD` with no
    dirty check, which stamped a release built from a modified checkout as
    though it came from the commit (issue #156). It is also *this build's*
    commit and not the corpus's: the records carry their own
    `provenance.parserCommit`, and the manifest reports the spread of those
    separately.
    """
    return provenance.parser_commit()


def write_manifest(
    dist: Path,
    stats: dict[str, Any],
    corpus_counts: dict[str, Any],
    subset: list[str] | None,
    profile: str = DEFAULT_PROFILE,
    registered: int = 0,
) -> dict[str, Any]:
    built = datetime.now(timezone.utc)
    manifest: dict[str, Any] = {
        "version": "corpus-" + built.strftime("%Y-%m-%d"),
        "builtAt": built.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schemaVersion": SCHEMA_VERSION,
        "buildCommit": build_commit(),
        # The corpus is not from one commit, and a single string implied it
        # was: 49,586 of the 113,073 records carry no `parserCommit` at all
        # (they predate provenance) and the rest carry several. The counter
        # says so, most records first (issue #156).
        "corpusParserCommits": corpus_counts["parser_commits"],
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
            # What the registry says a complete corpus holds (issue #132).
            # Without it a manifest over 2 elections was byte-for-byte
            # indistinguishable in shape from one over 55, so a consumer had
            # no way to ask whether a release was the whole archive.
            "electionsRegistered": registered,
            "persons": stats["persons"],
            "campaigns": stats["campaigns"],
            "photos": corpus_counts["photos"],
            # Unique images against the records that carry one: the same
            # portrait can be the newest on two candidacies of one person.
            "photoRecords": corpus_counts["photo_records"],
            "photoBytes": corpus_counts["photo_bytes"],
            "photosStripped": corpus_counts["photos_stripped"],
            "photosMetadataUntouched": corpus_counts["photos_untouched"],
            "photosMalformed": corpus_counts["photos_malformed"],
            "photoParts": len(corpus_counts["photo_parts"]),
            "anomalies": corpus_counts["anomalies"],
        },
        "recordsPerElection": corpus_counts["per_election"],
        # Which part holds which elections' portraits (issue #130), so a
        # consumer after one era's pictures downloads one part, not all.
        "photoParts": corpus_counts["photo_parts"],
        "artifacts": {
            name: {"bytes": (dist / name).stat().st_size, "sha256": sha256_file(dist / name)}
            for name in release_assets(corpus_counts)
        },
    }
    if subset:
        manifest["subset"] = sorted(subset)
    # Through the atomic writer: this is the file whose presence means the
    # assets beside it are described, and a half-written one would say so
    # falsely (issues #132, #153).
    write_json(dist / "MANIFEST.json", manifest)
    return manifest


#: Everything a build writes but its photo parts, in promotion order.
#: MANIFEST.json is last on purpose, and is removed from dist/ before the
#: first asset moves: it checksums the other assets, so a manifest that
#: outlives the assets it describes is worse than no manifest at all. The
#: invariant a consumer can rely on is that MANIFEST.json is present only
#: while it matches what sits beside it.
BUILD_OUTPUTS = RELEASE_ARTIFACTS + ("vrk.sqlite", "vrk-corpus.sqlite")


def promote(staging: Path, dist: Path) -> None:
    """Move a finished build into `dist/`, manifest last.

    `os.replace` is atomic per file and the loop is not, so the window in
    which dist/ is mixed shrinks from the whole build -- minutes, over 2.5 GB
    -- to a handful of renames on the same filesystem. Removing the old
    manifest first is what closes the rest: until the new one lands there is
    no manifest, which is a state a reader can recognise.
    """
    (dist / "MANIFEST.json").unlink(missing_ok=True)
    # A part the previous build filled and this one did not -- fewer
    # portraits, a smaller budget -- would sit beside a manifest that does
    # not name it, and an upload of dist/* would ship it.
    parts = sorted(path.name for path in staging.glob(PHOTO_PART_GLOB))
    for stale in dist.glob(PHOTO_PART_GLOB):
        if stale.name not in parts:
            stale.unlink()
    for name in BUILD_OUTPUTS + tuple(parts):
        os.replace(staging / name, dist / name)
    os.replace(staging / "MANIFEST.json", dist / "MANIFEST.json")


def build_distribution(
    repo_root: Path,
    dist: Path,
    subset: list[str] | None,
    max_drop: float = 5.0,
    profile: str = DEFAULT_PROFILE,
) -> int:
    registry = identity.load_registry(repo_root / "scraper" / "elections.json")
    registry_by_id = {entry["id"]: entry for entry in registry}

    rows, campaigns, elections_table, stats = table.build(repo_root, subset)
    persons = stats.pop("persons_rows")

    if subset is None:
        # Issue #132: a full build over a data/ holding 2 of the 55
        # registered elections exited 0, said "Fill gate: no findings", wrote
        # all five assets and printed the ready-to-run `gh release create`
        # line. Nothing could see it: `elections_present` is whatever is
        # under data/, and only an *unregistered* directory raised; the fill
        # gate iterates cells, and a wholly absent election has none; and the
        # two-pass record count compares two passes over the same truncated
        # list. This is not hypothetical -- data/ in a worktree is a symlink
        # set, and this project's history records corpus directories dying
        # with one (#92's results files).
        #
        # A partial build is what naming elections is for: that path marks
        # the manifest `subset` and skips the gate. A build that names none
        # claims the whole archive, so it has to hold it.
        missing = sorted(set(registry_by_id) - set(stats["elections_present"]))
        if missing:
            named = "\n".join(f"    {eid}" for eid in missing[:20])
            if len(missing) > 20:
                named += f"\n    ... and {len(missing) - 20} more"
            raise SystemExit(
                f"the corpus under {repo_root / 'data'} holds"
                f" {len(stats['elections_present'])} of the {len(registry_by_id)} registered"
                " elections.\nA build that names no election claims to be the whole archive,"
                " and nothing downstream would say otherwise: the manifest of a 10-record"
                f" build is the same shape as one of 113,073.\n\n{len(missing)} missing:\n{named}"
                "\n\nScrape them, or name the ones you mean —"
                " `build_distribution.py <election-id> …` marks the manifest a subset."
            )
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

    # Everything is written into a staging directory beside dist/ and moved
    # into place only once the manifest exists (issue #132). A build that
    # dies partway -- a record whose envelope moved, a Ctrl-C, a full disk
    # during the 2.5 GB corpus write -- used to leave dist/ mixed: MANIFEST
    # describing the previous build, candidacies.csv.gz from this one, three
    # assets from the old, `gzip.decompress(vrk.sqlite.gz) != vrk.sqlite`,
    # and `SELECT COUNT(*) FROM records` = 0 on a database whose
    # integrity_check said ok. Nothing in the error mentioned dist/.
    dist.mkdir(parents=True, exist_ok=True)
    staging = dist / f".staging-{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        table.write_csv_gz(staging / "candidacies.csv.gz", table.COLUMNS, rows)
        table.write_csv_gz(
            staging / "campaigns.csv.gz",
            table.CAMPAIGN_COLUMNS,
            sorted(campaigns.values(), key=lambda c: (c["election_id"], c["campaign_key"])),
        )
        table.write_sqlite(
            staging / "vrk.sqlite",
            rows,
            campaigns,
            elections_table,
            persons,
            repo_root / "scraper" / "parties.json",
            meta={
                "schemaVersion": str(SCHEMA_VERSION),
                "profile": profile,
                "builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "buildCommit": build_commit() or "",
                "candidacies": str(len(rows)),
                "elections": str(len(elections_table)),
                "source": SOURCE_URL,
                "dataLicense": DATA_LICENSE,
                "attribution": ATTRIBUTION,
                "terms": TERMS_URL,
            },
        )

        corpus_counts = write_corpus_sqlite(
            staging / "vrk-corpus.sqlite",
            staging / "vrk.sqlite",
            repo_root / "data",
            stats["elections_present"],
            profile,
        )
        if corpus_counts["records"] != stats["records"]:
            raise SystemExit(
                f"the two passes disagree: the candidacy table projected {stats['records']}"
                f" rows, the records table holds {corpus_counts['records']}"
            )

        gzip_file(staging / "vrk.sqlite", staging / "vrk.sqlite.gz", 9)
        gzip_file(staging / "vrk-corpus.sqlite", staging / "vrk-corpus.sqlite.gz", CORPUS_GZIP_LEVEL)
        check_asset_sizes(staging, release_assets(corpus_counts))
        manifest = write_manifest(
            staging, stats, corpus_counts, subset, profile, registered=len(registry_by_id)
        )
        promote(staging, dist)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

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
    for part in corpus_counts["photo_parts"]:
        print(
            f"photo part:   {part['name']}: {part['photos']} portrait(s),"
            f" {part['photoBytes'] / 1e6:.1f} MB, {len(part['elections'])} election(s)"
        )
    for name in release_assets(corpus_counts) + ("vrk.sqlite", "vrk-corpus.sqlite", "MANIFEST.json"):
        size = (dist / name).stat().st_size
        print(f"wrote {dist / name} ({size / 1024 / 1024:.1f} MB)")

    if subset is None:
        assets = " ".join(
            shlex.quote(str(dist / name)) for name in release_assets(corpus_counts) + ("MANIFEST.json",)
        )
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
