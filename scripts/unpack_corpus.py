"""Turn a released corpus database back into `data/`.

`README.md` and `docs/DATA_GUIDE.md` offer the release as the alternative to a
27-hour scrape, and until issue #156 nothing in the repository could read one:
`grep -rn 'vrk-corpus.sqlite|candidacies.csv.gz|vrk.sqlite' scripts/ scraper/
dashboard/` named those files only in the two writers. Every other script
reads `data/`, and the dashboard fetches one record file per person. So the
download was a dead end — the assets existed, and the corpus they came from
could not be reassembled from them.

This is the return path. `vrk-corpus.sqlite` holds one row per record with
the whole envelope in it, so:

    python scripts/unpack_corpus.py vrk-corpus.sqlite            # -> ./data
    python scripts/unpack_corpus.py vrk-corpus.sqlite --into /tmp/corpus
    python scripts/unpack_corpus.py vrk-corpus.sqlite 2016-seimo # one election

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

A portrait's bytes come back only if the database carries them (the corpus
database does; the candidacy one has no photos at all). A record whose
portrait was a URL the fetch never reached has no sidecar to write, exactly
as in the corpus it was built from.
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
    database: Path, into: Path, election_ids: list[str] | None = None
) -> tuple[Counter[str], list[str]]:
    """Write the database's records under `into`. Returns (counts, problems)."""
    counts: Counter[str] = Counter()
    problems: list[str] = []
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
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

        for election_id in wanted:
            election_dir = into / election_id
            election_dir.mkdir(parents=True, exist_ok=True)
            for row in connection.execute(
                "SELECT * FROM records WHERE election_id = ? ORDER BY candidate_id", (election_id,)
            ):
                record = reconstruct_record(row)
                write_json(election_dir / row["record_file"], record)
                counts["records"] += 1

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
                blob = connection.execute(
                    "SELECT data, stripped, stripped_sha256 FROM photos WHERE sha256 = ?", (digest,)
                ).fetchone()
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

    counts, problems = unpack(args.database, args.into, args.election_id or None)
    print(
        f"wrote {counts['records']} record(s) across {counts['elections']} election(s)"
        f" into {args.into}/"
        + (f", {counts['photos']} portrait(s)" if counts["photos"] else "")
        + (f" ({counts['photos_stripped']} with metadata stripped)" if counts["photos_stripped"] else "")
        + (f", {counts['anomalies']} anomaly event(s)" if counts["anomalies"] else "")
    )
    for problem in problems[:20]:
        print(f"    {problem}", file=sys.stderr)
    if len(problems) > 20:
        print(f"    ... and {len(problems) - 20} more", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
