"""Turn a released corpus database back into `data/`.

`README.md` and `docs/DATA_GUIDE.md` offer the release as the alternative to a
27-hour scrape, and until issue #156 nothing in the repository could read one:
`grep -rn 'vrk-corpus.sqlite|candidacies.csv.gz|vrk.sqlite' scripts/ scraper/
dashboard/` named those files only in the two writers. Every other script
reads `data/`, and the dashboard fetches one record file per person. So the
download was a dead end — the assets existed, and the corpus they came from
could not be reassembled from them.

This is the return path. `vrk-corpus.sqlite` holds one row per record with
the whole envelope in it, and the `vrk-photos-N.sqlite` parts downloaded
beside it hold the portraits (issue #130), so:

    python scripts/unpack_corpus.py vrk-corpus.sqlite            # -> ./data
    python scripts/unpack_corpus.py vrk-corpus.sqlite --into /tmp/corpus
    python scripts/unpack_corpus.py vrk-corpus.sqlite 2016-seimo # one election
    python scripts/unpack_corpus.py vrk-corpus.sqlite --no-photos
    python scripts/unpack_corpus.py vrk-corpus.sqlite --photos ~/Downloads

writes `data/<election-id>/<record-file>.json`, the election's
`anomalies.jsonl`, and every portrait sidecar the records name, in the same
layout a scrape produces. After it, `scripts/build_person_index.py` and
`scripts/build_candidacy_table.py` both run against the unpacked tree.

**What comes back.** Under the `full` profile, the corpus: same records, same
key order, same bytes. Verified on a real election — a `full` build of
`2019-prezidento` unpacked into an empty directory and `diff -r` against
`data/2019-prezidento` reports nothing, records, portraits and the anomaly
file alike. (The database stores the JSON compact and `write_json` writes it
back at the scraper's own two-space indent, which is what makes the files
identical rather than merely equivalent.) An *empty* `anomalies.jsonl` —
"scraped, nothing to report" — comes back too: the elections that had one are
named in the database's `meta` table, because no anomaly row can carry that.

Under the `public` profile the redacted paths are *absent*, not nulled, which
is what `MANIFEST.json`'s `redaction` block lists; the tree is then a real
corpus minus those values, and every gate but the re-parse one runs on it.

A portrait's bytes come from the part the corpus database's `photos` row
names, looked for beside the database or under `--photos`; a release built
before issue #130 (schema 1) carried them in the database itself, and reads
the same. An election whose portraits sit in a part that is not at hand is
refused, naming the part, rather than unpacked without them -- `--no-photos`
is how to ask for the records alone. A record whose portrait was a URL the
fetch never reached has no sidecar to write, exactly as in the corpus it was
built from.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_distribution import reconstruct_record  # noqa: E402
from scraper.shared.files import PORTRAIT_KEYS, write_json  # noqa: E402

ANOMALIES_NAME = "anomalies.jsonl"
PHOTOS_DIR = "photos"


def read_meta(connection: sqlite3.Connection) -> dict[str, str]:
    """The database's own account of itself, or {} for one built before #156."""
    try:
        return {key: value for key, value in connection.execute("SELECT key, value FROM meta")}
    except sqlite3.OperationalError:
        return {}


class PhotoSource:
    """Where a portrait's bytes are.

    In the `vrk-photos-N.sqlite` part the corpus database's `photos` row
    names (schema 2, issue #130), or in that row's own `data` column for a
    release built before the parts existed (schema 1, `corpus-2026-08-30`).
    """

    def __init__(self, connection: sqlite3.Connection, directory: Path) -> None:
        self.connection = connection
        self.directory = directory
        columns = {row[1] for row in connection.execute("PRAGMA table_info(photos)")}
        self.inline = "data" in columns
        self._parts: dict[str, sqlite3.Connection] = {}

    def missing_parts(self, election_ids: list[str]) -> list[str]:
        """The parts these elections' portraits need that are not at hand."""
        if self.inline or not election_ids:
            return []
        marks = ", ".join("?" * len(election_ids))
        needed = [
            row[0]
            for row in self.connection.execute(
                "SELECT DISTINCT p.part FROM records r JOIN photos p ON p.sha256 = r.photo_sha256"
                f" WHERE r.election_id IN ({marks}) ORDER BY p.part",
                election_ids,
            )
        ]
        return [name for name in needed if not (self.directory / name).is_file()]

    def fetch(self, digest: str) -> sqlite3.Row | None:
        """(data, stripped, stripped_sha256) of one image, or None."""
        query = "SELECT data, stripped, stripped_sha256 FROM photos WHERE sha256 = ?"
        if self.inline:
            return self.connection.execute(query, (digest,)).fetchone()
        located = self.connection.execute("SELECT part FROM photos WHERE sha256 = ?", (digest,)).fetchone()
        if located is None:
            return None
        return self._part(located[0]).execute(query, (digest,)).fetchone()

    def _part(self, name: str) -> sqlite3.Connection:
        if name not in self._parts:
            part = sqlite3.connect(self.directory / name)
            part.row_factory = sqlite3.Row
            self._parts[name] = part
        return self._parts[name]

    def close(self) -> None:
        for part in self._parts.values():
            part.close()
        self._parts = {}


def photo_reference(record: dict) -> str | None:
    """The `photos/<name>` the record points at, or None.

    Both spellings the corpus uses (`photoSrc` everywhere,
    `photoUrl` in the 1996-1999 archive family) and both places it can sit:
    `rawData.profile` and `normalized.profilis.nuotrauka`.
    """
    profile = (record.get("rawData") or {}).get("profile") or {}
    for key in PORTRAIT_KEYS:
        value = profile.get(key)
        if isinstance(value, str) and value.startswith(f"{PHOTOS_DIR}/"):
            return value
    value = ((record.get("normalized") or {}).get("profilis") or {}).get("nuotrauka")
    if isinstance(value, str) and value.startswith(f"{PHOTOS_DIR}/"):
        return value
    return None


def unpack(
    database: Path,
    into: Path,
    election_ids: list[str] | None = None,
    *,
    photos_dir: Path | None = None,
    with_photos: bool = True,
) -> tuple[Counter[str], list[str]]:
    """Write the database's records under `into`. Returns (counts, problems).

    Portraits are read from the parts in `photos_dir`, by default the
    database's own directory; `with_photos=False` writes the records alone.
    """
    counts: Counter[str] = Counter()
    problems: list[str] = []
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    photos = PhotoSource(connection, photos_dir or database.parent)
    try:
        # Which elections had an `anomalies.jsonl` at build time, empty or
        # not: an empty one says "scraped, nothing to report" and no file at
        # all says nothing, so the two are kept apart.
        had_anomaly_file = set(filter(None, read_meta(connection).get("anomalyFiles", "").split(",")))
        try:
            connection.execute("SELECT 1 FROM records LIMIT 1")
        except sqlite3.OperationalError as error:
            raise SystemExit(
                f"{database}: no `records` table — this is not a corpus database."
                " The release's `vrk-corpus.sqlite` is the one that carries the"
                f" records ({error})"
            ) from error

        available = [row[0] for row in connection.execute("SELECT DISTINCT election_id FROM records ORDER BY 1")]
        wanted = election_ids or available
        unknown = sorted(set(wanted) - set(available))
        if unknown:
            raise SystemExit(
                f"{database} holds no records for: {', '.join(unknown)}."
                f" It carries {len(available)} election(s)."
            )

        if with_photos:
            missing = photos.missing_parts(wanted)
            if missing:
                raise SystemExit(
                    f"the portraits of these elections are in {', '.join(missing)},"
                    f" which {'is' if len(missing) == 1 else 'are'} not in {photos.directory}."
                    " Download the part(s) beside the database, name their directory with"
                    " --photos, or pass --no-photos to unpack the records alone."
                )

        for election_id in wanted:
            election_dir = into / election_id
            election_dir.mkdir(parents=True, exist_ok=True)
            for row in connection.execute(
                "SELECT * FROM records WHERE election_id = ? ORDER BY candidate_id", (election_id,)
            ):
                record = reconstruct_record(row)
                write_json(election_dir / row["record_file"], record)
                counts["records"] += 1

                if not with_photos:
                    counts["photos_skipped"] += bool(row["photo_sha256"])
                    continue
                reference = photo_reference(record)
                digest = row["photo_sha256"]
                if reference is None:
                    if digest:
                        problems.append(
                            f"{election_id}/{row['candidate_id']}: a photo row with no"
                            " `photos/…` reference in the record"
                        )
                    continue
                if not digest:
                    problems.append(
                        f"{election_id}/{row['candidate_id']}: names {reference} and the"
                        " database holds no photo for it"
                    )
                    continue
                blob = photos.fetch(digest)
                if blob is None:
                    problems.append(f"{election_id}/{row['candidate_id']}: photo {digest[:12]}… is not in the database")
                    continue
                actual = hashlib.sha256(blob["data"]).hexdigest()
                if actual != blob["stripped_sha256"]:
                    problems.append(
                        f"{election_id}/{row['candidate_id']}: photo bytes hash {actual[:12]}…,"
                        f" the row says {blob['stripped_sha256'][:12]}…"
                    )
                    continue
                target = election_dir / reference
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob["data"])
                counts["photos"] += 1
                counts["photos_stripped"] += int(blob["stripped"])

            events = [
                row[0]
                for row in connection.execute(
                    "SELECT event_json FROM anomalies WHERE election_id = ?", (election_id,)
                )
            ]
            if events or election_id in had_anomaly_file:
                (election_dir / ANOMALIES_NAME).write_text(
                    "\n".join(events) + "\n" if events else "", encoding="utf-8"
                )
                counts["anomalies"] += len(events)
                counts["anomaly_files"] += 1
            counts["elections"] += 1
    finally:
        photos.close()
        connection.close()
    return counts, problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("database", type=Path, help="vrk-corpus.sqlite from a release")
    parser.add_argument(
        "election_id", nargs="*", help="Elections to write. Defaults to every one the database holds."
    )
    parser.add_argument(
        "--into",
        type=Path,
        default=Path("data"),
        help="Where the election directories go. Defaults to ./data.",
    )
    parser.add_argument(
        "--photos",
        type=Path,
        default=None,
        help="Directory holding the vrk-photos-N.sqlite parts. Defaults to the database's own.",
    )
    parser.add_argument(
        "--no-photos",
        action="store_true",
        help="Unpack the records and anomaly logs only; write no portrait sidecars.",
    )
    args = parser.parse_args()

    if not args.database.is_file():
        print(f"No such file: {args.database}", file=sys.stderr)
        return 2

    connection = sqlite3.connect(args.database)
    try:
        meta = read_meta(connection)
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        connection.close()
    if meta:
        print(
            f"{args.database.name}: schema {meta.get('schemaVersion', version or '?')},"
            f" profile {meta.get('profile', '?')}, built {meta.get('builtAt', '?')}"
            f" at {meta.get('buildCommit', '?')}"
        )
    else:
        print(
            f"{args.database.name}: no `meta` table — a build from before issue #156,"
            " so what profile it is and what it was built from are not recorded",
            file=sys.stderr,
        )
    if meta.get("profile") == "public":
        print(
            "  the public profile: the redacted paths are absent from these records,"
            " so this tree is the archive less those values (MANIFEST.json lists them)"
        )

    counts, problems = unpack(
        args.database,
        args.into,
        args.election_id or None,
        photos_dir=args.photos,
        with_photos=not args.no_photos,
    )
    print(
        f"wrote {counts['records']} record(s) across {counts['elections']} election(s)"
        f" into {args.into}/"
        + (f", {counts['photos']} portrait(s)" if counts["photos"] else "")
        + (f" ({counts['photos_stripped']} with metadata stripped)" if counts["photos_stripped"] else "")
        + (f", {counts['photos_skipped']} portrait(s) not written (--no-photos)" if counts["photos_skipped"] else "")
        + (f", {counts['anomalies']} anomaly event(s)" if counts["anomalies"] else "")
    )
    for problem in problems[:20]:
        print(f"    {problem}", file=sys.stderr)
    if len(problems) > 20:
        print(f"    ... and {len(problems) - 20} more", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
