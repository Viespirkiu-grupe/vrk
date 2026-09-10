"""Re-parse an election from its retained HTML and diff the result against `data/`.

Parser fixes land in this repository; the corpus is written once, by the scrape
that happened to run before them. Nothing re-parsed `data/`, so a fix reached
only the elections scraped after it. Issue #91 measured the gap and this script
closed it: on 2026-08-29, 20,534 records across 15 elections no longer parsed
to what was stored -- 18% of the corpus, holding un-externalized base64
portraits, a private-interest section in two shapes, three columns VRK never
fills and a block of `rawData` that duplicated `normalized`.

Run it after any parser change. Exit 0 means the corpus is still what the
parsers say it is.

    python scripts/reparse_diff.py                       # every election, fixtures
    python scripts/reparse_diff.py 2019-ep 2020-seimo    # named elections
    python scripts/reparse_diff.py --full --jobs 8 2019-ep
    python scripts/reparse_diff.py --full --jobs 8 --apply 2019-ep

Two sample roots, and the difference matters:

* **fixtures** (`samples/html/<election-id>/`) -- the default. A handful of
  candidates per election, chosen to cover that module's shapes, so a sweep of
  all 55 elections costs about ten seconds. For the small elections the fixture
  tree *is* the whole election, and the two are the same run. It is only as
  good as the fixtures, which is why `tests/test_fixture_sitemap_agreement.py`
  pins each one to its sitemap entry.
* **retained** (`samples-full/<election-id>/`, `--full`) -- every candidate's
  HTML as fetched. This is what `--apply` regenerates the corpus from. An
  election with no `samples-full/` tree falls back to its fixtures, which for
  the archive families holds every candidate anyway; so does any *candidate*
  the retained tree lacks but the fixture tree has -- 96 of them across
  ten elections, which `--apply` used to be unable to reach at all while
  the fixture run went on reporting them as drifted (issue #101). The
  coverage line says how many of the stored records the run actually reached.

The comparison is structural, not textual: both records are walked in parallel
and every differing JSON path is classified `added` / `removed` / `changed` /
`type` / `length`, with list indices collapsed to `[]`. That is what turns "10
records differ" into "77 records gained `rawData.profile.photoMeta`" -- the
histogram is the finding, not the record count. The `provenance` block is not
diffed -- its run-stamps (`parsedAt`, `parserCommit`) differ between any two
honest runs -- but its `sourceSha256` is read, so a drifted record is
attributed to "the page changed" or "the parser changed" (issue #89).

`--apply` copies the freshly parsed records over `data/<election-id>/`, along
with any `photos/` sidecars the parse externalized -- the base64 era's, and
the URL era's from the `portrait.json` retained beside each page (issue #118).
It requires `--full`, because applying a fixture run would rewrite five
records and leave the other 13,661 stale. `anomalies.jsonl` is replaced only
when the run covered every stored record, and only its `parse`-stage events
are: what the fetch stage recorded (a candidate page the runner could not
land, a portrait URL that answered 404) describes fetches a re-parse never
made, and stays. A partial run leaves the stored file alone rather than
truncating it to the subset it saw.

Exit status is the gate: 0 when nothing differs, 1 when something does, 2 when
the run could not be made (a missing sample tree, a parser that raised).

Coverage is part of that (issue #157). The gate's claim is that exit 0 means
the corpus is what the parsers produce, and it cannot mean that over records
the run never read: a checkout whose `data/2000-seimo` holds all 1,271 records
but whose retained tree holds two candidate directories used to print
`2 of 1271 stored records re-parsed from retained, 0 differ` and exit 0, with
nothing on stderr. `compared` and `stored_total` were printed and thrown away.
So a `--full` run whose sources do not cover every stored record now names the
shortfall and exits 1, and `--apply` does the same rather than leaving half the
corpus at the old parser's output while reporting the other half clean. A
default (fixture) run is partial by design and is not gated on coverage --
that is what `--full` is for.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.cli import (  # noqa: E402
    PARSABLE_ELECTION_IDS,
    _parse_anketa_samples_for_election,
)
from scraper.shared.anomalies import merge_run, read_jsonl, write_jsonl  # noqa: E402

ANOMALIES_NAME = "anomalies.jsonl"
PHOTOS_DIR = "photos"

# Candidates per parse call. Each call re-reads the election's results lookup,
# so a chunk wants to be big enough to amortise that and small enough that
# every worker gets several -- a 301-candidate election split into two chunks
# leaves six of eight processes idle.
MAX_CHUNK_SIZE = 200
MIN_CHUNK_SIZE = 10


def chunk_size(candidates: int, jobs: int) -> int:
    return max(MIN_CHUNK_SIZE, min(MAX_CHUNK_SIZE, -(-candidates // (jobs * 4))))


def candidate_dirs(samples_root: Path) -> list[str]:
    """Every candidate directory in a sample tree, in parse order.

    Sample trees are flat -- one directory per candidate, holding that
    candidate's pages -- across every layout family from the 1996 archive
    cards (`candidate.html`) to the 2023 municipal tabs (`anketa.html`). What
    makes a directory a candidate is the `index.json` the fetcher writes
    beside the pages: the sample roots also hold listing scaffolding
    (`constituencies/`, `districts/`) that is full of HTML and is not a
    candidate, and feeding those to a parser raises `Candidate id not found
    in sitemap`.

    This is only needed to split the work across processes; a single-process
    run lets each module enumerate its own tree, and `reparse` cross-checks
    the two so a family whose fetcher lays its samples out differently
    surfaces as a mismatch rather than as a silently short run.
    """
    return sorted(
        child.name
        for child in samples_root.iterdir()
        if child.is_dir() and (child / "index.json").is_file() and any(child.glob("*.html"))
    )


def _parse_chunk(args: tuple[str, list[str] | None, str, str]) -> tuple[int, list[dict[str, Any]], str | None]:
    election_id, candidate_ids, samples_root, output_root = args
    try:
        results = _parse_anketa_samples_for_election(
            election_id=election_id,
            candidate_ids=candidate_ids,
            samples_root=Path(samples_root),
            output_root=Path(output_root),
        )
    except Exception:  # noqa: BLE001 - a raising parser is a finding, not a crash
        return 0, [], traceback.format_exc()
    anomalies = [event for result in results for event in result.get("anomalies", [])]
    return len(results), anomalies, None


def _reparse_source(
    election_id: str,
    samples_root: Path,
    candidate_ids: list[str] | None,
    output_root: Path,
    jobs: int,
) -> tuple[int, list[dict[str, Any]], list[str]]:
    """Parse one sample tree, or a named subset of it, into `output_root`."""
    if jobs <= 1:
        parsed, anomalies, error = _parse_chunk(
            (election_id, candidate_ids, str(samples_root), str(output_root))
        )
        return parsed, anomalies, [error] if error else []

    ids = candidate_ids if candidate_ids is not None else candidate_dirs(samples_root)
    size = chunk_size(len(ids), jobs)
    chunks = [
        (election_id, ids[start : start + size], str(samples_root), str(output_root))
        for start in range(0, len(ids), size)
    ]
    parsed = 0
    anomalies: list[dict[str, Any]] = []
    errors: list[str] = []
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for chunk_parsed, chunk_anomalies, error in pool.map(_parse_chunk, chunks):
            parsed += chunk_parsed
            anomalies.extend(chunk_anomalies)
            if error:
                errors.append(error)
    if not errors and parsed != len(ids):
        errors.append(
            f"enumeration mismatch: {len(ids)} candidate directories, {parsed} parsed."
            " Re-run with --jobs 1, which lets the module enumerate its own tree."
        )
    return parsed, anomalies, errors


def reparse(
    election_id: str,
    sources: list[tuple[Path, list[str] | None]],
    output_root: Path,
    jobs: int,
) -> tuple[int, list[dict[str, Any]], list[str]]:
    """Parse every sample source into `output_root`. Returns (parsed, anomalies, errors)."""
    output_root.mkdir(parents=True, exist_ok=True)
    parsed = 0
    anomalies: list[dict[str, Any]] = []
    errors: list[str] = []
    for samples_root, candidate_ids in sources:
        source_parsed, source_anomalies, source_errors = _reparse_source(
            election_id, samples_root, candidate_ids, output_root, jobs
        )
        parsed += source_parsed
        anomalies.extend(source_anomalies)
        errors.extend(source_errors)
    return parsed, anomalies, errors


def diff_paths(stored: Any, fresh: Any, prefix: str = "") -> list[tuple[str, str]]:
    """Every JSON path at which two records differ, with how.

    List indices collapse to `[]` so that "one candidate's third
    private-interest row gained a field" and "every row gained it" report the
    same path, which is what makes the histogram readable. A length change is
    reported once, at the list itself, rather than as N phantom additions.
    """
    if isinstance(stored, dict) and isinstance(fresh, dict):
        differences: list[tuple[str, str]] = []
        for key in sorted(fresh.keys() - stored.keys()):
            differences.append((f"{prefix}.{key}".lstrip("."), "added"))
        for key in sorted(stored.keys() - fresh.keys()):
            differences.append((f"{prefix}.{key}".lstrip("."), "removed"))
        for key in sorted(stored.keys() & fresh.keys()):
            differences.extend(diff_paths(stored[key], fresh[key], f"{prefix}.{key}".lstrip(".")))
        return differences

    if isinstance(stored, list) and isinstance(fresh, list):
        differences = []
        if len(stored) != len(fresh):
            differences.append((f"{prefix}[]", "length"))
        for stored_item, fresh_item in zip(stored, fresh):
            differences.extend(diff_paths(stored_item, fresh_item, f"{prefix}[]"))
        return differences

    # Type before value: `0 == 0.0` and `False == 0` in Python, but a record
    # that stores one where it used to store the other is a different file on
    # disk, and this gate's whole claim is that the corpus is what the parsers
    # write.
    if type(stored) is not type(fresh):
        return [(prefix or ".", "type")]
    if stored == fresh:
        return []
    return [(prefix or ".", "changed")]


def compare(
    fresh_root: Path,
    stored_root: Path,
) -> tuple[int, int, int, Counter, list[str], int]:
    """Diff every freshly parsed record against its stored counterpart.

    The `provenance` block is excluded from the diff: `parsedAt` and
    `parserCommit` describe the parse *run* and differ between two honest runs
    of the same code, and `fetchedAt` follows file mtimes a git checkout of the
    fixture trees rewrites. It is read instead of compared — a differing record
    whose stored and fresh `sourceSha256` disagree drifted because *the page
    changed*, not the parser, and the two causes are counted apart (issue #89).
    """
    compared = differing = missing = 0
    source_changed = 0
    histogram: Counter = Counter()
    differing_records: list[str] = []

    for fresh_path in sorted(fresh_root.glob("*.json")):
        stored_path = stored_root / fresh_path.name
        if not stored_path.exists():
            missing += 1
            continue
        compared += 1
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        fresh = json.loads(fresh_path.read_text(encoding="utf-8"))
        stored_provenance = stored.pop("provenance", None) if isinstance(stored, dict) else None
        fresh_provenance = fresh.pop("provenance", None) if isinstance(fresh, dict) else None
        differences = diff_paths(stored, fresh)
        if differences:
            differing += 1
            differing_records.append(fresh_path.name)
            histogram.update(differences)
            if (
                isinstance(stored_provenance, dict)
                and isinstance(fresh_provenance, dict)
                and stored_provenance.get("sourceSha256")
                and fresh_provenance.get("sourceSha256")
                and stored_provenance["sourceSha256"] != fresh_provenance["sourceSha256"]
            ):
                source_changed += 1

    return compared, differing, missing, histogram, differing_records, source_changed


def apply_records(fresh_root: Path, stored_root: Path, record_names: list[str]) -> tuple[int, int]:
    """Copy the records that differ, and any new photo sidecars, into `data/`.

    Only the differing records are written -- so a record rewritten here gets
    the fresh parse's `provenance` (its content really is this run's product),
    while an unchanged record keeps the block saying when its content was
    actually produced.
    """
    stored_root.mkdir(parents=True, exist_ok=True)
    records = 0
    for name in record_names:
        shutil.copy2(fresh_root / name, stored_root / name)
        records += 1

    photos = 0
    fresh_photos = fresh_root / PHOTOS_DIR
    if fresh_photos.is_dir():
        (stored_root / PHOTOS_DIR).mkdir(exist_ok=True)
        for photo_path in sorted(fresh_photos.iterdir()):
            if not photo_path.is_file():
                continue
            stored_photo = stored_root / PHOTOS_DIR / photo_path.name
            if stored_photo.exists() and stored_photo.read_bytes() == photo_path.read_bytes():
                continue
            shutil.copy2(photo_path, stored_photo)
            photos += 1
    return records, photos


def write_anomalies(path: Path, anomalies: list[dict[str, Any]]) -> bool:
    """Rewrite an election's parse-stage anomalies, if the re-parse changed them.

    A complete re-parse reproduces every `parse`-stage event, and only those
    -- which is why the caller checks coverage first. Events of any other
    stage are kept as they are: a `CandidateFetchFailed` from the runner or a
    `PortraitFetchFailed` from scripts/backfill_url_portraits.py describes a
    fetch this run did not make, and dropping it would turn a recorded
    failure back into "never tried". Neither order nor `timestamp` is
    compared: the stored files are in scrape order and a re-parse emits
    candidate order, every fresh event is stamped with the re-parse's own
    clock, and the file is a set of findings either way. Unchanged findings
    are left alone -- with the timestamps of when they were first recorded --
    so the file's mtime keeps meaning "when this election last changed".
    """
    fresh = sorted(_comparable_event(event) for event in anomalies)
    stored_events = read_jsonl(path)
    if stored_events:
        stored = sorted(
            _comparable_event(event) for event in stored_events if event.get("stage") == "parse"
        )
        if stored == fresh:
            return False
    # The whole election was re-parsed, so the run owns every parse-stage
    # event; the ownership rule itself lives in scraper/shared/anomalies.py,
    # where the parse command applies it per candidate (issue #139).
    write_jsonl(path, merge_run(stored_events, anomalies, stage="parse", candidate_ids=None))
    return True


def _comparable_event(event: dict[str, Any]) -> str:
    return json.dumps(
        {key: value for key, value in event.items() if key != "timestamp"},
        ensure_ascii=False,
        sort_keys=True,
    )


def resolve_sample_sources(
    repo_root: Path, election_id: str, full: bool
) -> list[tuple[Path, list[str] | None]]:
    """Where this election's candidates are read from, in parse order.

    A `--full` run reads `samples-full/`, and the fixture tree fills in the
    candidates it does not hold. That fallback is per *candidate*, not per
    election: a handful of candidates per election have a tracked fixture and
    no retained page (96 of them across ten elections, measured 2026-08-29),
    and reading only `samples-full/` left exactly those records
    behind on every `--apply` while the fixture run kept reporting them as
    drifted -- a gate that fails and an apply that cannot fix it.

    A `None` id list means "whatever the module enumerates in this tree",
    which is how a single-process run cross-checks the enumeration.
    """
    retained = repo_root / "samples-full" / election_id
    fixtures = repo_root / "samples" / "html" / election_id
    if not (full and retained.is_dir()):
        return [(fixtures, None)] if fixtures.is_dir() else []

    sources: list[tuple[Path, list[str] | None]] = [(retained, None)]
    if fixtures.is_dir():
        only_in_fixtures = sorted(set(candidate_dirs(fixtures)) - set(candidate_dirs(retained)))
        if only_in_fixtures:
            sources.append((fixtures, only_in_fixtures))
    return sources


def stored_record_count(stored_root: Path) -> int:
    return sum(1 for path in stored_root.glob("*.json"))


def run_election(
    election_id: str,
    repo_root: Path,
    work_root: Path,
    *,
    full: bool,
    apply: bool,
    jobs: int,
    top: int,
) -> tuple[bool, int, Counter, int]:
    """Re-parse and diff one election.

    Returns (ok, differing, histogram, unreached) -- the last being the
    stored records the run never re-parsed, which only `--full` treats as a
    finding (issue #157: a fixture run is partial by design).
    """
    stored_root = repo_root / "data" / election_id
    if not stored_root.is_dir():
        print(f"{election_id}: no data/ directory, skipped")
        return True, 0, Counter(), 0

    sources = resolve_sample_sources(repo_root, election_id, full)
    if not sources:
        print(f"{election_id}: no sample tree, skipped", file=sys.stderr)
        return False, 0, Counter(), 0

    fresh_root = work_root / election_id
    if fresh_root.exists():
        shutil.rmtree(fresh_root)

    parsed, anomalies, errors = reparse(election_id, sources, fresh_root, jobs)
    for error in errors:
        print(f"{election_id}: parse failed\n{error}", file=sys.stderr)

    compared, differing, unknown, histogram, differing_records, source_changed = compare(
        fresh_root, stored_root
    )
    stored_total = stored_record_count(stored_root)

    kind = "retained" if sources[0][0].parent.name == "samples-full" else "fixtures"
    if len(sources) > 1:
        kind += f" + {len(sources[1][1] or [])} from fixtures"
    print(
        f"{election_id}: {compared} of {stored_total} stored records re-parsed"
        f" from {kind}, {differing} differ"
        + (f" ({source_changed} from changed source HTML)" if source_changed else "")
        + (f", {unknown} not in data/" if unknown else "")
        + (f", {len(anomalies)} anomalies" if anomalies else "")
    )
    for path, count in histogram.most_common(top):
        print(f"    {count:>6}  {path[0]:<62} {path[1]}")
    if differing and differing <= 5:
        print("    records: " + ", ".join(name.removesuffix(".json") for name in differing_records))

    # What a `--full` run claims is every stored record; `unknown` is a fresh
    # record data/ does not hold, which is a different thing and not a
    # shortfall. A fixture run is partial by design and reports 0 here.
    unreached = max(stored_total - compared - unknown, 0) if full else 0
    if unreached:
        print(
            f"    {unreached} stored record(s) had no retained HTML and were not"
            " re-parsed: this run does not cover them",
            file=sys.stderr,
        )

    if apply:
        if parsed == 0 or errors:
            print("    NOT applied — the re-parse did not complete", file=sys.stderr)
            return False, differing, histogram, unreached
        records, photos = apply_records(fresh_root, stored_root, differing_records)
        rewrote = compared + unknown >= stored_total and write_anomalies(
            stored_root / ANOMALIES_NAME, anomalies
        )
        if records or photos or rewrote:
            note = f"    applied {records} record(s)" + (f", {photos} photo(s)" if photos else "")
            if rewrote:
                note += f", rewrote {ANOMALIES_NAME} ({len(anomalies)} event(s))"
            elif compared + unknown < stored_total:
                note += (
                    f", left {ANOMALIES_NAME} alone"
                    f" ({stored_total - compared} record(s) had no retained HTML)"
                )
            print(note)

    if not apply:
        shutil.rmtree(fresh_root, ignore_errors=True)

    return not errors, differing, histogram, unreached


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "election_id",
        nargs="*",
        help="Elections to check. Defaults to every parsable election.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Parse every retained candidate (samples-full/) rather than the fixtures.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy the freshly parsed records over data/. Requires --full.",
    )
    parser.add_argument("--jobs", type=int, default=1, help="Parser processes (default 1).")
    parser.add_argument("--top", type=int, default=15, help="Differing paths to list per election.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Checkout holding data/ and the sample trees. Defaults to the cwd.",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=None,
        help="Where re-parsed trees are written. Defaults to <repo-root>/.run-state/reparse-diff.",
    )
    args = parser.parse_args()

    if args.apply and not args.full:
        parser.error("--apply requires --full: applying a fixture run would rewrite a handful of records and leave the rest stale")

    repo_root = args.repo_root
    work_root = args.work_root or (repo_root / ".run-state" / "reparse-diff")
    work_root.mkdir(parents=True, exist_ok=True)

    unknown_ids = [eid for eid in args.election_id if eid not in PARSABLE_ELECTION_IDS]
    if unknown_ids:
        parser.error("not a parsable election id: " + ", ".join(unknown_ids))

    election_ids = args.election_id or PARSABLE_ELECTION_IDS
    ok = True
    total_differing = 0
    total_unreached = 0
    totals: Counter = Counter()
    drifted: list[str] = []
    uncovered: list[str] = []

    for election_id in election_ids:
        election_ok, differing, histogram, unreached = run_election(
            election_id,
            repo_root,
            work_root,
            full=args.full,
            apply=args.apply,
            jobs=args.jobs,
            top=args.top,
        )
        ok = ok and election_ok
        total_differing += differing
        total_unreached += unreached
        totals.update(histogram)
        if differing:
            drifted.append(election_id)
        if unreached:
            uncovered.append(f"{election_id} ({unreached})")

    if len(election_ids) > 1:
        print(
            f"\n{len(election_ids)} election(s): {total_differing} record(s) differ"
            f" across {len(drifted)} election(s)"
        )
        for path, count in totals.most_common(args.top):
            print(f"    {count:>6}  {path[0]:<62} {path[1]}")
        if drifted:
            print("    drifted: " + " ".join(drifted))

    if total_unreached:
        # Issue #157: coverage never reached the exit status, so a run that
        # re-parsed 2 of 1,271 records said "0 differ" and exited 0 -- and
        # the gate's whole claim is that exit 0 means the corpus is what the
        # parsers produce. It cannot mean that over records it never read.
        print(
            f"\n{total_unreached} stored record(s) across {len(uncovered)} election(s) were"
            " not covered by this run:",
            file=sys.stderr,
        )
        for entry in uncovered[:20]:
            print(f"    {entry}", file=sys.stderr)
        if len(uncovered) > 20:
            print(f"    ... and {len(uncovered) - 20} more", file=sys.stderr)
        print(
            "    Their retained HTML is absent, so nothing here says whether they still"
            "\n    parse to what data/ holds. Re-fetch with retention, or name the"
            "\n    elections whose coverage you accept.",
            file=sys.stderr,
        )

    if not ok:
        return 2
    if total_unreached and args.apply:
        # A partial --apply leaves part of the corpus at the old parser's
        # output while reporting the elections it did rewrite as clean.
        print(
            "    --apply did not reach every stored record; the corpus is now mixed.",
            file=sys.stderr,
        )
        return 1
    return 1 if total_differing or total_unreached else 0


if __name__ == "__main__":
    raise SystemExit(main())
