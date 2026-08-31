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

    def test_the_fetchable_ids_match_the_election_registry(self):
        registry = json.loads(
            (REPO_ROOT / "scraper" / "elections.json").read_text(encoding="utf-8")
        )
        registry_ids = {entry["id"] for entry in registry["elections"]}
        self.assertEqual(registry_ids, set(FETCHABLE_ELECTION_IDS))


if __name__ == "__main__":
    unittest.main()
