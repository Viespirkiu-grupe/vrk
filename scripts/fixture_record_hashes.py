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
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.cli import PARSABLE_ELECTION_IDS, _parse_anketa_samples_for_election  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("tests/fixture-record-hashes.tsv")
COLUMNS = ("fixture", "sha256")


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


def measure(
    election_ids: list[str], repo_root: Path = REPO_ROOT
) -> tuple[dict[str, str], list[str]]:
    """(fixture path -> digest, errors). One parse per election, into a temp
    tree, exactly as `python -m scraper parse-anketa` would."""
    tracked = tracked_candidates(repo_root)
    digests: dict[str, str] = {}
    errors: list[str] = []
    for election_id in election_ids:
        candidates = tracked.get(election_id)
        if not candidates:
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
                errors.append(f"{election_id}: {type(error).__name__}: {error}")
                continue
            for path in sorted(Path(tmp).rglob("*.json")):
                record = json.loads(path.read_text(encoding="utf-8"))
                candidate_id = record.get("candidateId") or path.stem
                digests[f"{election_id}/{candidate_id}"] = record_digest(record)
    return digests, errors


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


def write_manifest(path: Path, digests: dict[str, str]) -> None:
    lines = ["\t".join(COLUMNS)]
    lines += [f"{fixture}\t{digests[fixture]}" for fixture in sorted(digests)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compare(measured: dict[str, str], manifest: dict[str, str]) -> list[str]:
    """One line per finding: a record that changed, appeared or went."""
    findings = []
    for fixture in sorted(set(manifest) | set(measured)):
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
    measured, errors = measure(election_ids, args.repo_root)
    for error in errors:
        print(error, file=sys.stderr)
    print(f"{len(measured)} tracked candidate fixture(s) parsed across {len(election_ids)} election(s)")

    if args.update:
        if subset:
            parser.error("--update needs every election, or it would drop the rest of the manifest")
        if errors:
            print("not written: the parse did not complete", file=sys.stderr)
            return 2
        write_manifest(path, measured)
        print(f"wrote {MANIFEST}")
        return 0

    manifest = read_manifest(path)
    if subset:
        manifest = {k: v for k, v in manifest.items() if k.split("/", 1)[0] in set(election_ids)}
    findings = compare(measured, manifest)
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
