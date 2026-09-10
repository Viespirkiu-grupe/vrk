"""What each tracked candidate fixture parses to, as one hash per record.

Three commands say the corpus is what the parsers produce
(`reparse_diff.py`, `field_coverage.py`, `anomalies-report`) and none of
them can run in CI: all three read `data/`, which is gitignored. The one
test-level equivalent — `ReparseByteIdentity::test_reparse_matches_the_corpus_records`
— calls `local_data.require()` on `data/<election>/` and skips there. So a
parser change that alters what every record holds has, in CI, only the
per-election value pins to answer to: real coverage, but assertions about
named fields of named candidates, not about the record as a whole (issue
#157).

This closes that for the fixture subset git carries. One line per tracked
candidate:

    <election-id>/<candidate-id>  <sha256 of the record, provenance dropped>

`provenance` is dropped whole, exactly as the re-parse gate drops it: it
carries the parse run's own wall clock (`parsedAt`), the commit that ran it
(`parserCommit`) and a `fetchedAt` that on a fixture tree follows the git
checkout rather than the fetch. What is left is the parse *content*, and
that has to reproduce exactly.

The manifest is not a second corpus and not a second baseline: it says
nothing about whether a value is right, only that today's parsers produce
the same bytes as the parsers that wrote the checked-in hash. A deliberate
parser change updates it in the same commit, and the diff then names every
election the change reached — which is the review the fixture value pins
cannot give.

    python scripts/fixture_record_hashes.py            # measure and check
    python scripts/fixture_record_hashes.py --update   # after a deliberate change
    python scripts/fixture_record_hashes.py 2019-ep    # one election

**Not every election is measurable on a clone**, and the manifest says which
(issue #150). A fixture parse reads more than `samples/html/<id>/`: it reads
the election's crawl plan and, where the election has one, its results join —
and two of those are over the 1 MiB limit on a tracked unit, so
`scripts/tracked_fixtures.py` leaves them out of git.
`sitemaps/1997-kovo-23-savivaldybiu-tarybu.json` (2.9 MB) is one, and its
absence *raised*: the whole manifest test failed on every CI run until this
was fixed. `sitemaps/2000-kovo-19-savivaldybiu-tarybu.results.json` (3.5 MB)
is the other, and its absence was worse than a failure — the parse simply
produced `isrinktas: null` and ten fixtures hashed differently, with nothing
saying why.

So `--update` records, per election, the auxiliary inputs its parse could
read and that were present when the manifest was written (`# needs` lines at
the top of the file). A checkout that lacks one of them cannot reproduce that
election's records, and the election is reported "not measurable here" rather
than checked. On the scraping machine every election is measured; on a clone
the two above are skipped and the other 53 are checked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.cli import PARSABLE_ELECTION_IDS, _parse_anketa_samples_for_election  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("tests/fixture-record-hashes.tsv")
COLUMNS = ("fixture", "sha256")

#: `# needs <election> <path>[,<path>…]` — one per election whose parse read
#: an auxiliary local-data input.
NEEDS_PREFIX = "# needs\t"


#: Where an auxiliary input can live. `samples/html/<id>/` is the fixture tree
#: itself and is always present, by definition of a tracked fixture.
AUXILIARY_ROOTS = ("sitemaps", "samples/results")

#: Files opened during the current parse, filled by the audit hook below.
_OPENED: set[str] = set()
_HOOK_INSTALLED = False


def _watch_opens(repo_root: Path) -> None:
    """Record every file the parse opens, so `--update` can say what it read.

    Guessing from what *exists* over-skips: an election whose results tree
    happens to be on disk would be declared to need it even where the parser
    never looks. An audit hook is exact, and `open` is the only event that
    matters here.
    """
    global _HOOK_INSTALLED
    if _HOOK_INSTALLED:
        return
    base = str(repo_root.resolve())

    def hook(event: str, args: tuple) -> None:
        if event != "open" or not args:
            return
        name = args[0]
        if not isinstance(name, (str, bytes)):
            name = getattr(name, "__fspath__", lambda: None)()
        if not isinstance(name, (str, bytes)):
            return
        text = name.decode() if isinstance(name, bytes) else name
        # Not `resolve()`: `sitemaps/` and `data/` are symlink sets in a
        # worktree, and resolving takes every one of them outside the root.
        try:
            relative = str(Path(text).relative_to(base)) if Path(text).is_absolute() else text
        except ValueError:
            return
        relative = os.path.normpath(relative)
        if relative.split("/", 1)[0] in ("sitemaps",) or relative.startswith("samples/results/"):
            _OPENED.add(relative)

    sys.addaudithook(hook)
    _HOOK_INSTALLED = True


def read_inputs(election_id: str) -> list[str]:
    """The auxiliary inputs the last parse of `election_id` actually opened."""
    return sorted(path for path in _OPENED if election_id in path)


def tracked_candidates(repo_root: Path = REPO_ROOT) -> dict[str, list[str]]:
    """The candidate fixture directories git carries, by election id.

    Read from `git ls-files` rather than the filesystem: a working tree may
    hold far more than the tracked subset — the machine that scraped the
    corpus has all 1,009 candidate directories, and a worktree can have the
    untracked ones symlinked in for a full local run — and a manifest of
    those would fail on every clone.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--", "samples/html"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {}
    by_election: dict[str, set[str]] = {}
    for line in result.stdout.splitlines():
        parts = Path(line).parts
        # samples/html/<election-id>/<candidate-id>/<file>: a candidate
        # directory, not one of the listing trees (`lists/`, `districts/`)
        # or an election-level `list.html`.
        if len(parts) < 5 or parts[0] != "samples" or parts[1] != "html":
            continue
        election_id, candidate_id = parts[2], parts[3]
        if not (repo_root / "samples" / "html" / election_id / candidate_id / "index.json").exists() and not (
            repo_root / "samples" / "html" / election_id / candidate_id / "anketa.html"
        ).exists():
            continue
        by_election.setdefault(election_id, set()).add(candidate_id)
    return {election: sorted(candidates) for election, candidates in sorted(by_election.items())}


def record_digest(record: dict) -> str:
    """The hash of one record's parse content.

    `provenance` goes whole: two honest parses of the same bytes disagree on
    its run-stamps. The rest is serialized the way the record writer does —
    UTF-8, two-space indent, keys in insertion order — so the digest is of
    the bytes a scrape would have written.
    """
    content = {key: value for key, value in record.items() if key != "provenance"}
    payload = json.dumps(content, ensure_ascii=False, indent=2, sort_keys=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


#: The gitignored trees a clone does not carry (`tests/local_data.py` holds
#: the same list). A parse that cannot find one of these is not measurable
#: *here*, which is a different thing from a parse that failed.
LOCAL_DATA_ROOTS = ("data", "samples", "samples-full", "sitemaps")


def _absent_local_data(error: BaseException) -> str | None:
    """The local-data path this error is about, or None if it is a real error.

    The 1997 municipal general's sitemap is 2.9 MB — over the 1 MiB limit on a
    tracked unit — so `scripts/tracked_fixtures.py` leaves it out of git and
    its fixtures cannot be parsed on a clone. That used to come back as an
    error and fail this manifest on every CI run (issue #150); it is an
    absence, and it is reported as one.
    """
    if not isinstance(error, (FileNotFoundError, NotADirectoryError)):
        return None
    name = getattr(error, "filename", None) or (error.args[1] if len(error.args) > 1 else "")
    text = str(name)
    first = Path(text).parts[0] if text and not Path(text).is_absolute() else ""
    if first in LOCAL_DATA_ROOTS:
        return text
    for root in LOCAL_DATA_ROOTS:
        if f"/{root}/" in text:
            return text
    return None


def measure(
    election_ids: list[str],
    repo_root: Path = REPO_ROOT,
    needs: dict[str, list[str]] | None = None,
) -> tuple[dict[str, str], list[str], list[str]]:
    """(fixture path -> digest, errors, absences).

    One parse per election, into a temp tree, exactly as
    `python -m scraper parse-anketa` would. An election whose parse wants a
    gitignored tree this checkout does not carry is an *absence*: not
    measurable here, and not a finding.
    """
    tracked = tracked_candidates(repo_root)
    _watch_opens(repo_root)
    digests: dict[str, str] = {}
    errors: list[str] = []
    absent: list[str] = []
    for election_id in election_ids:
        candidates = tracked.get(election_id)
        if not candidates:
            continue
        missing_inputs = [
            path for path in (needs or {}).get(election_id, []) if not (repo_root / path).exists()
        ]
        if missing_inputs:
            # Declared by --update as an input this election's parse read.
            # Without it the parse does not fail — it silently drops the
            # results join — so the election is skipped, not compared.
            absent.append(f"{election_id}: needs {', '.join(missing_inputs)}, absent here")
            continue
        samples_root = repo_root / "samples" / "html" / election_id
        with tempfile.TemporaryDirectory() as tmp:
            try:
                _parse_anketa_samples_for_election(
                    election_id,
                    candidate_ids=candidates,
                    samples_root=samples_root,
                    output_root=Path(tmp),
                )
            except Exception as error:  # noqa: BLE001 -- reported, not raised
                missing = _absent_local_data(error)
                if missing is not None:
                    absent.append(f"{election_id}: needs {missing}, which this checkout does not carry")
                else:
                    errors.append(f"{election_id}: {type(error).__name__}: {error}")
                continue
            for path in sorted(Path(tmp).rglob("*.json")):
                record = json.loads(path.read_text(encoding="utf-8"))
                candidate_id = record.get("candidateId") or path.stem
                digests[f"{election_id}/{candidate_id}"] = record_digest(record)
    return digests, errors, absent


def read_needs(path: Path) -> dict[str, list[str]]:
    """The `# needs` declarations at the top of the manifest."""
    if not path.exists():
        return {}
    needs: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(NEEDS_PREFIX):
            continue
        election, _, paths = line[len(NEEDS_PREFIX) :].partition("\t")
        needs[election] = [p for p in paths.split(",") if p]
    return needs


def read_manifest(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    manifest: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fixture, _, digest = line.partition("\t")
        if fixture == COLUMNS[0]:
            continue
        manifest[fixture] = digest.strip()
    return manifest


def write_manifest(path: Path, digests: dict[str, str], needs: dict[str, list[str]]) -> None:
    lines = [
        "# One sha256 per tracked candidate fixture, over the parse content with",
        "# `provenance` dropped. scripts/fixture_record_hashes.py writes it.",
        "# The `needs` lines name the auxiliary local-data inputs each election's",
        "# parse read: a checkout without one of them cannot reproduce that",
        "# election's records and is told so rather than checked (issue #150).",
    ]
    lines += [
        f"{NEEDS_PREFIX}{election}\t{','.join(paths)}"
        for election, paths in sorted(needs.items())
        if paths
    ]
    lines.append("\t".join(COLUMNS))
    lines += [f"{fixture}\t{digests[fixture]}" for fixture in sorted(digests)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compare(
    measured: dict[str, str], manifest: dict[str, str], absent: list[str] | None = None
) -> list[str]:
    """One line per finding: a record that changed, appeared or went.

    An election named in `absent` is skipped on both sides: its fixtures were
    not parsed because this checkout lacks a gitignored tree they need, and
    "in the manifest and not parsed" would be a false finding.
    """
    unmeasurable = {line.split(":", 1)[0] for line in (absent or [])}
    findings = []
    for fixture in sorted(set(manifest) | set(measured)):
        if fixture.split("/", 1)[0] in unmeasurable:
            continue
        was, now = manifest.get(fixture), measured.get(fixture)
        if was == now:
            continue
        if was is None:
            findings.append(f"{fixture}\tnot in the manifest (a new fixture? run --update)")
        elif now is None:
            findings.append(f"{fixture}\tin the manifest and not parsed (a fixture went, or the parse raised)")
        else:
            findings.append(f"{fixture}\tparses to {now[:12]}…, manifest says {was[:12]}…")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("election_id", nargs="*", help="Subset to measure. Defaults to all.")
    parser.add_argument("--update", action="store_true", help="Rewrite the manifest.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()

    unknown = [eid for eid in args.election_id if eid not in PARSABLE_ELECTION_IDS]
    if unknown:
        parser.error("not a parsable election id: " + ", ".join(unknown))
    election_ids = args.election_id or list(PARSABLE_ELECTION_IDS)
    subset = bool(args.election_id)

    path = args.repo_root / MANIFEST
    needs = read_needs(args.repo_root / MANIFEST)
    measured, errors, absent = measure(election_ids, args.repo_root, needs)
    for error in errors:
        print(error, file=sys.stderr)
    for line in absent:
        print(f"not measurable here — {line}", file=sys.stderr)
    print(f"{len(measured)} tracked candidate fixture(s) parsed across {len(election_ids)} election(s)")

    if args.update:
        if subset:
            parser.error("--update needs every election, or it would drop the rest of the manifest")
        if errors:
            print("not written: the parse did not complete", file=sys.stderr)
            return 2
        if absent:
            # Rewriting the manifest here would delete the rows for an
            # election this checkout cannot parse.
            print(
                "not written: " + str(len(absent)) + " election(s) are not measurable here;"
                " run --update on a checkout that carries them",
                file=sys.stderr,
            )
            return 2
        write_manifest(path, measured, {eid: read_inputs(eid) for eid in election_ids})
        print(f"wrote {MANIFEST}")
        return 0

    manifest = read_manifest(path)
    if subset:
        manifest = {k: v for k, v in manifest.items() if k.split("/", 1)[0] in set(election_ids)}
    findings = compare(measured, manifest, absent)
    if errors:
        return 2
    if not findings:
        print("Every tracked fixture parses to the record the manifest holds.")
        return 0
    print(f"\n{len(findings)} finding(s):", file=sys.stderr)
    for finding in findings[:40]:
        print(f"    {finding}", file=sys.stderr)
    if len(findings) > 40:
        print(f"    ... and {len(findings) - 40} more", file=sys.stderr)
    print(
        "\nA deliberate parser change updates the manifest in the same commit:"
        "\n    python scripts/fixture_record_hashes.py --update",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
