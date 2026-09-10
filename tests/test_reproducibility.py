"""A full run from the scripts must reproduce the corpus (issue #95).

The claim "the corpus is reproduced by running the scrapers" is only worth
making while these hold:

* `write_json` is atomic — the runners resume on file existence, so a write
  that dies halfway must leave the previous file or nothing, never a
  truncated record that counts as done;
* `fetch-sample` refuses to overwrite the tracked listing fixtures unless
  told to, because a reproduction run does not need it and a silent refetch
  churns what the suite pins;
* parsing an election from its fixtures is deterministic, and byte-identical
  to the corpus records wherever the corpus is present;
* the run scripts stay parseable, drive their election list from the CLI's
  registry (not a glob that once invented phantom elections out of
  `<id>.results.json` files), and default to retaining fetched HTML.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from local_data import require

from scraper.cli import (
    FETCHABLE_ELECTION_IDS,
    _parse_anketa_samples_for_election,
    build_parser,
    listing_fixture_refusal,
)
from scraper.shared.files import write_json

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

_spec = importlib.util.spec_from_file_location(
    "fixture_record_hashes", SCRIPTS / "fixture_record_hashes.py"
)
hashes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hashes)

# Small enough to parse twice in a test, complete enough to mean something:
# all 27 candidates of the 2003 by-election are inside the tracked fixture
# subset, so this runs on a fresh clone and in CI.
ELECTION_ID = "2003-birzelio-15-seimo-nauji"
FIXTURES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID


class WriteJsonAtomicity(unittest.TestCase):
    def test_writes_content_and_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "record.json"
            write_json(path, {"a": 1})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 1})
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["record.json"])

    def test_failed_serialization_leaves_the_previous_file_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "record.json"
            write_json(path, {"a": 1})
            with self.assertRaises(TypeError):
                write_json(path, {"a": object()})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 1})
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["record.json"])


class ListingFixtureGuard(unittest.TestCase):
    def test_refuses_when_the_fixture_tree_exists(self):
        cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)
                fixture_root = Path(f"samples/html/{ELECTION_ID}")
                self.assertIsNone(listing_fixture_refusal(ELECTION_ID, False))
                fixture_root.mkdir(parents=True)
                refusal = listing_fixture_refusal(ELECTION_ID, False)
                self.assertIsNotNone(refusal)
                self.assertIn("--allow-fixture-overwrite", refusal)
                self.assertIsNone(listing_fixture_refusal(ELECTION_ID, True))
        finally:
            os.chdir(cwd)

    def test_parser_accepts_the_overwrite_flag(self):
        args = build_parser().parse_args(
            ["fetch-sample", ELECTION_ID, "--allow-fixture-overwrite"]
        )
        self.assertTrue(args.allow_fixture_overwrite)
        args = build_parser().parse_args(["fetch-sample", ELECTION_ID])
        self.assertFalse(args.allow_fixture_overwrite)


def _parse_into(output_root: Path) -> list[Path]:
    _parse_anketa_samples_for_election(
        election_id=ELECTION_ID,
        candidate_ids=None,
        samples_root=FIXTURES_ROOT,
        output_root=output_root,
    )
    return sorted(output_root.rglob("*.json"))


def _load_without_run_stamps(path: Path) -> dict:
    """The record with `provenance.parsedAt` dropped — the one field two
    honest parses of the same bytes may disagree on (issue #89)."""
    record = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(record.get("provenance"), dict):
        record["provenance"].pop("parsedAt", None)
    return record


class ReparseByteIdentity(unittest.TestCase):
    def test_two_parses_of_the_fixtures_are_identical(self):
        # Identical up to `provenance.parsedAt`, which stamps the parse run's
        # own wall clock; everything else — the parse content, the source
        # hash, the fetch time, the parser commit — must reproduce exactly.
        with tempfile.TemporaryDirectory() as tmp:
            first = _parse_into(Path(tmp) / "a")
            second = _parse_into(Path(tmp) / "b")
            self.assertEqual(len(first), 27)
            self.assertEqual(
                [p.name for p in first],
                [p.name for p in second],
            )
            for left, right in zip(first, second):
                self.assertEqual(
                    _load_without_run_stamps(left),
                    _load_without_run_stamps(right),
                    f"{left.name} is not deterministic",
                )

    def test_reparse_matches_the_corpus_records(self):
        # The whole `provenance` block is excluded here, exactly as the
        # re-parse gate excludes it: its run-stamps differ between honest
        # runs, and a fixture tree's file mtimes (its `fetchedAt`) follow the
        # git checkout rather than the fetch. The claim under test is that
        # the parse *content* reproduces the corpus byte for byte.
        corpus_root = REPO_ROOT / "data" / ELECTION_ID
        require(corpus_root)
        with tempfile.TemporaryDirectory() as tmp:
            for produced in _parse_into(Path(tmp)):
                stored = corpus_root / produced.name
                produced_record = json.loads(produced.read_text(encoding="utf-8"))
                stored_record = json.loads(stored.read_text(encoding="utf-8"))
                produced_record.pop("provenance", None)
                stored_record.pop("provenance", None)
                self.assertEqual(
                    json.dumps(produced_record, ensure_ascii=False, indent=2),
                    json.dumps(stored_record, ensure_ascii=False, indent=2),
                    f"{produced.name} re-parses to different content than the corpus holds",
                )


class FixtureRecordHashes(unittest.TestCase):
    """Every tracked fixture parses to the record the manifest holds (#157).

    The test above is the same claim against `data/`, and it skips wherever
    the corpus is absent — which is CI, `data/` being gitignored, as are all
    three of the commands that check the corpus against the parsers. So in
    CI a parser change answered only to the per-election value pins: real
    coverage, but assertions about named fields of named candidates rather
    than about the record as a whole. `tests/fixture-record-hashes.tsv` is
    73 KiB that closes it — one sha256 per tracked candidate, over the parse
    content with `provenance` dropped.

    Nine elections are outside it on a clone, and the manifest says so in its
    own `# needs` lines: their crawl plan or results file is over the 1 MiB
    limit on a tracked unit, so a clone parses their fixtures without the
    elected join and gets different records. Until issue #150 one of those
    absences raised and failed this test on every CI run, while another passed
    silently as ten changed hashes. 569 of the 649 fixtures are checked on a
    clone, all 649 where the corpus was scraped.
    """

    def test_the_manifest_is_what_the_parsers_produce(self):
        # An election whose parse reads a local-data input this checkout does
        # not carry cannot reproduce its records here, so it is skipped rather
        # than compared — the manifest's `# needs` lines say which inputs each
        # election read when it was written. Two are over the 1 MiB limit on a
        # tracked unit and so absent from every clone:
        # `sitemaps/1997-kovo-23-savivaldybiu-tarybu.json` (2.9 MB), whose
        # absence *raised* and failed this test on every CI run, and
        # `sitemaps/2000-kovo-19-savivaldybiu-tarybu.results.json` (3.5 MB),
        # whose absence was quieter and worse — the parse dropped the elected
        # join and ten fixtures hashed differently (issue #150).
        needs = hashes.read_needs(REPO_ROOT / hashes.MANIFEST)
        self.assertEqual(len(needs), len(hashes.PARSABLE_ELECTION_IDS))
        measured, errors, absent = hashes.measure(
            list(hashes.PARSABLE_ELECTION_IDS), REPO_ROOT, needs
        )
        self.assertEqual(errors, [])
        # Nine elections' crawl plans (and for five of them their results
        # files) are over the 1 MiB limit on a tracked unit, so no clone can
        # reproduce their records: the five municipal generals from 2007 on,
        # the 1997, 2000 and 2002 municipal ones, and 2012-seimo. Everything
        # else is checked wherever the suite runs — 569 of the 649 fixtures on
        # a clone, all 649 on the scraping machine.
        self.assertLessEqual(len(absent), 9, absent)
        manifest = hashes.read_manifest(REPO_ROOT / hashes.MANIFEST)
        self.assertTrue(manifest, f"{hashes.MANIFEST} is missing or empty")
        findings = hashes.compare(measured, manifest, absent)
        self.assertEqual(
            findings,
            [],
            "the tracked fixtures no longer parse to the recorded records. A"
            " deliberate parser change updates the manifest in the same commit:"
            " python scripts/fixture_record_hashes.py --update",
        )

    def test_the_manifest_covers_every_parsable_election(self):
        # A manifest missing an election proves nothing about it, and would
        # go on passing while that election's parser drifted.
        manifest = hashes.read_manifest(REPO_ROOT / hashes.MANIFEST)
        covered = {fixture.split("/", 1)[0] for fixture in manifest}
        self.assertEqual(sorted(covered), sorted(hashes.PARSABLE_ELECTION_IDS))

    def test_the_digest_ignores_the_run_stamps_and_nothing_else(self):
        base = {"candidateId": "x", "normalized": {"a": 1}, "provenance": {"parsedAt": "now"}}
        other_run = {"candidateId": "x", "normalized": {"a": 1}, "provenance": {"parsedAt": "later"}}
        changed = {"candidateId": "x", "normalized": {"a": 2}, "provenance": {"parsedAt": "now"}}
        self.assertEqual(hashes.record_digest(base), hashes.record_digest(other_run))
        self.assertNotEqual(hashes.record_digest(base), hashes.record_digest(changed))


class RunScripts(unittest.TestCase):
    def _script(self, name: str) -> Path:
        return SCRIPTS / name

    def test_scripts_parse(self):
        for name in ("run_all_elections.sh", "run_election_batches.sh"):
            with self.subTest(script=name):
                result = subprocess.run(
                    ["bash", "-n", str(self._script(name))],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_full_run_drives_the_registry_not_a_glob(self):
        text = self._script("run_all_elections.sh").read_text(encoding="utf-8")
        self.assertIn("FETCHABLE_ELECTION_IDS", text)
        # The old default list globbed sitemaps/*.json and basenamed each hit,
        # which turned every <id>.results.json into a phantom election.
        self.assertNotIn("basename", text)

    def test_runner_defaults_to_retention_and_validates_its_inputs(self):
        text = self._script("run_election_batches.sh").read_text(encoding="utf-8")
        self.assertIn('KEEP_SAMPLES="${KEEP_SAMPLES:-1}"', text)
        self.assertIn("FETCHABLE_ELECTION_IDS", text)
        self.assertIn("build-results", text)
        self.assertIn("CandidateFetchFailed", text)

    def test_the_full_run_archives_the_portraits_it_claims_to(self):
        """docs/DATASET.md calls this the reproduction entry point.

        It ran the scrape and stopped (issue #143). The portraits every era
        but 2016-2019 *links* are archived by a second pass, and only
        `scripts/backfill_url_portraits.py` writes the `portrait.json` a
        `photos/` sidecar comes from: measured over the shipped corpus,
        25,332 records carry a photoMeta naming a fetched URL and 25,294 of
        the 27,493 sidecar files exist only because that script ran. Step 1
        alone reproduces neither.
        """
        text = self._script("run_all_elections.sh").read_text(encoding="utf-8")
        self.assertIn("backfill_url_portraits.py", text)
        self.assertIn("reparse_diff.py", text)
        self.assertIn('--full --jobs "$REPARSE_JOBS" --apply', text)
        # Only over an election the runner finished, and its exit code counts.
        self.assertIn('if [[ $status -eq 0 && "$FETCH_PORTRAITS" != "0" ]]; then', text)
        self.assertIn("portraits=$portrait_status reparse=$reparse_status", text)
        # The offline escape hatch, and the warning that it leaves a gap.
        self.assertIn('FETCH_PORTRAITS="${FETCH_PORTRAITS:-1}"', text)
        self.assertIn("linked portraits not archived", text)

    def test_the_docs_do_not_promise_portraits_from_the_scrape_alone(self):
        dataset = (REPO_ROOT / "docs" / "DATASET.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("three\nsteps per election", dataset)
        self.assertIn("backfill_url_portraits.py", dataset)
        self.assertIn("archived by a second pass over\nthe finished scrape", readme)

    def test_the_fetchable_ids_match_the_election_registry(self):
        registry = json.loads(
            (REPO_ROOT / "scraper" / "elections.json").read_text(encoding="utf-8")
        )
        registry_ids = {entry["id"] for entry in registry["elections"]}
        self.assertEqual(registry_ids, set(FETCHABLE_ELECTION_IDS))


if __name__ == "__main__":
    unittest.main()
