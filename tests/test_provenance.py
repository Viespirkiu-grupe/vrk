"""The provenance block (issue #89): stamped on write, well-formed, and
excluded from the re-parse gate's diff without blinding the gate to a changed
source page."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scraper.shared.files import write_candidate_record
from scraper.shared.provenance import (
    PROVENANCE_SCHEMA_VERSION,
    build_provenance,
    comparable_provenance,
    parser_commit,
    utc_iso,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

PROVENANCE_KEYS = ["fetchedAt", "parsedAt", "parserCommit", "sourceSha256", "schemaVersion"]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildProvenanceTests(unittest.TestCase):
    def test_block_is_well_formed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "anketa.html"
            source.write_text("<html>page</html>", encoding="utf-8")

            block = build_provenance(source)

            self.assertEqual(list(block.keys()), PROVENANCE_KEYS)
            self.assertEqual(block["schemaVersion"], PROVENANCE_SCHEMA_VERSION)
            self.assertEqual(
                block["sourceSha256"], hashlib.sha256(source.read_bytes()).hexdigest()
            )
            self.assertEqual(block["fetchedAt"], utc_iso(source.stat().st_mtime))
            # Both timestamps parse as aware UTC ISO-8601.
            for key in ("fetchedAt", "parsedAt"):
                parsed = datetime.fromisoformat(block[key])
                self.assertEqual(parsed.utcoffset().total_seconds(), 0)
            self.assertEqual(block["parserCommit"], parser_commit())

    def test_parser_commit_in_a_checkout_is_a_short_hash(self) -> None:
        # In this repository the commit must resolve; outside one it may be
        # None, which build_provenance records honestly rather than raising.
        commit = parser_commit()
        self.assertIsNotNone(commit)
        self.assertRegex(commit, r"^[0-9a-f]{7,}(-dirty)?$")

    def test_comparable_provenance_drops_the_run_stamps(self) -> None:
        block = {
            "fetchedAt": "2026-08-18T11:09:45+00:00",
            "parsedAt": "2026-08-31T20:00:00+00:00",
            "parserCommit": "abc1234",
            "sourceSha256": "aa",
            "schemaVersion": 1,
        }
        self.assertEqual(
            comparable_provenance(block),
            {"fetchedAt": "2026-08-18T11:09:45+00:00", "sourceSha256": "aa", "schemaVersion": 1},
        )


class WriteCandidateRecordTests(unittest.TestCase):
    def test_write_stamps_provenance_from_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "anketa.html"
            source.write_text("<html>page</html>", encoding="utf-8")
            output_path = Path(tmp) / "out" / "record.json"

            write_candidate_record(output_path, {"candidateId": "x"}, source_path=source)

            record = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(list(record["provenance"].keys()), PROVENANCE_KEYS)
            self.assertEqual(
                record["provenance"]["sourceSha256"],
                hashlib.sha256(source.read_bytes()).hexdigest(),
            )
            # The block lands last, after the payload the parser built.
            self.assertEqual(list(record.keys()), ["candidateId", "provenance"])

    def test_write_without_source_path_stays_honest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "record.json"
            write_candidate_record(output_path, {"candidateId": "x"})
            record = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertNotIn("provenance", record)


class ReparseDiffProvenanceTests(unittest.TestCase):
    """compare() must not gate on the block, and must attribute drift."""

    def setUp(self) -> None:
        self.reparse_diff = _load_script("reparse_diff")

    def _compare(self, stored: dict, fresh: dict):
        with tempfile.TemporaryDirectory() as tmp:
            stored_root = Path(tmp) / "stored"
            fresh_root = Path(tmp) / "fresh"
            stored_root.mkdir()
            fresh_root.mkdir()
            (stored_root / "a.json").write_text(json.dumps(stored), encoding="utf-8")
            (fresh_root / "a.json").write_text(json.dumps(fresh), encoding="utf-8")
            return self.reparse_diff.compare(fresh_root, stored_root)

    @staticmethod
    def _record(value: str, parsed_at: str, sha: str) -> dict:
        return {
            "candidateId": "a",
            "normalized": {"field": value},
            "provenance": {
                "fetchedAt": "2026-08-18T11:09:45+00:00",
                "parsedAt": parsed_at,
                "parserCommit": "abc1234",
                "sourceSha256": sha,
                "schemaVersion": 1,
            },
        }

    def test_records_differing_only_in_provenance_do_not_differ(self) -> None:
        stored = self._record("same", "2026-08-20T00:00:00+00:00", "aa")
        fresh = self._record("same", "2026-08-31T00:00:00+00:00", "bb")
        compared, differing, missing, histogram, names, source_changed = self._compare(
            stored, fresh
        )
        self.assertEqual((compared, differing, missing, source_changed), (1, 0, 0, 0))
        self.assertEqual(dict(histogram), {})

    def test_missing_stored_block_is_not_drift(self) -> None:
        stored = self._record("same", "2026-08-20T00:00:00+00:00", "aa")
        del stored["provenance"]
        fresh = self._record("same", "2026-08-31T00:00:00+00:00", "aa")
        _, differing, _, _, _, _ = self._compare(stored, fresh)
        self.assertEqual(differing, 0)

    def test_content_drift_is_attributed_to_a_changed_page(self) -> None:
        stored = self._record("old", "2026-08-20T00:00:00+00:00", "aa")
        fresh = self._record("new", "2026-08-31T00:00:00+00:00", "bb")
        _, differing, _, _, _, source_changed = self._compare(stored, fresh)
        self.assertEqual((differing, source_changed), (1, 1))

    def test_content_drift_with_same_page_is_the_parsers(self) -> None:
        stored = self._record("old", "2026-08-20T00:00:00+00:00", "aa")
        fresh = self._record("new", "2026-08-31T00:00:00+00:00", "aa")
        _, differing, _, _, _, source_changed = self._compare(stored, fresh)
        self.assertEqual((differing, source_changed), (1, 0))


class BackfillProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backfill = _load_script("backfill_provenance")

    def _repo(self, tmp: str) -> Path:
        repo = Path(tmp)
        source = repo / "samples-full" / "test-el" / "cand"
        source.mkdir(parents=True)
        (source / "anketa.html").write_text("<html>page</html>", encoding="utf-8")
        data = repo / "data" / "test-el"
        data.mkdir(parents=True)
        (data / "cand-test-el.json").write_text(
            json.dumps({"electionId": "test-el", "candidateId": "cand"}), encoding="utf-8"
        )
        return repo

    def test_backfill_stamps_and_reruns_leave_it_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            counts = self.backfill.backfill_election(repo, "test-el", force=False)
            self.assertEqual(counts, {"stamped": 1, "present": 0, "no-source": 0})

            record = json.loads(
                (repo / "data" / "test-el" / "cand-test-el.json").read_text(encoding="utf-8")
            )
            block = record["provenance"]
            self.assertEqual(list(block.keys()), PROVENANCE_KEYS)
            # A pre-provenance record's parser commit is unknown, not guessed.
            self.assertIsNone(block["parserCommit"])
            self.assertEqual(
                block["sourceSha256"], hashlib.sha256(b"<html>page</html>").hexdigest()
            )

            counts = self.backfill.backfill_election(repo, "test-el", force=False)
            self.assertEqual(counts, {"stamped": 0, "present": 1, "no-source": 0})

    def test_record_without_a_retained_page_is_left_without_a_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            data = repo / "data" / "test-el"
            (data / "ghost-test-el.json").write_text(
                json.dumps({"electionId": "test-el", "candidateId": "ghost"}), encoding="utf-8"
            )
            counts = self.backfill.backfill_election(repo, "test-el", force=False)
            self.assertEqual(counts, {"stamped": 1, "present": 0, "no-source": 1})
            record = json.loads((data / "ghost-test-el.json").read_text(encoding="utf-8"))
            self.assertNotIn("provenance", record)


class ParsersStampProvenanceTests(unittest.TestCase):
    """A record parsed from the fixture tree carries the block end to end —
    one election per layout family: the modern tabs, the pre-2016 pages and
    the 1996 archive cards."""

    def _assert_provenance(self, record: dict, source: Path) -> None:
        block = record.get("provenance")
        self.assertIsInstance(block, dict)
        self.assertEqual(list(block.keys()), PROVENANCE_KEYS)
        self.assertEqual(
            block["sourceSha256"], hashlib.sha256(source.read_bytes()).hexdigest()
        )

    def test_modern_family(self) -> None:
        from scraper.elections.seimo_2024.anketa_parser import parse_anketa_sample

        samples_root = REPO_ROOT / "samples" / "html" / "2024-seimo"
        candidate = "algirdas-butkevicius"
        if not (samples_root / candidate / "anketa.html").exists():
            self.skipTest("fixture not present; scrape 2024-seimo samples first")
        with tempfile.TemporaryDirectory() as tmp:
            output_path, _ = parse_anketa_sample(
                candidate_id=candidate, samples_root=samples_root, output_root=Path(tmp)
            )
            record = json.loads(output_path.read_text(encoding="utf-8"))
        self._assert_provenance(record, samples_root / candidate / "anketa.html")

    def test_pre2016_family(self) -> None:
        from scraper.elections.seimo_2012.anketa_parser import parse_anketa_sample

        samples_root = REPO_ROOT / "samples" / "html" / "2012-seimo"
        candidates = sorted(
            child.name for child in samples_root.iterdir() if (child / "anketa.html").exists()
        ) if samples_root.is_dir() else []
        if not candidates:
            self.skipTest("fixture not present; scrape 2012-seimo samples first")
        with tempfile.TemporaryDirectory() as tmp:
            output_path, _ = parse_anketa_sample(
                candidate_id=candidates[0], samples_root=samples_root, output_root=Path(tmp)
            )
            record = json.loads(output_path.read_text(encoding="utf-8"))
        self._assert_provenance(record, samples_root / candidates[0] / "anketa.html")

    def test_archive_family(self) -> None:
        from scraper.elections.seimo_1996.anketa_parser import parse_anketa_samples

        samples_root = REPO_ROOT / "samples" / "html" / "1996-spalio-20-seimo"
        sitemap_path = REPO_ROOT / "sitemaps" / "1996-spalio-20-seimo.json"
        candidates = sorted(
            child.name for child in samples_root.iterdir() if (child / "candidate.html").exists()
        ) if samples_root.is_dir() else []
        if not candidates or not sitemap_path.exists():
            self.skipTest("fixture or sitemap not present; scrape 1996-spalio-20-seimo first")
        with tempfile.TemporaryDirectory() as tmp:
            results = parse_anketa_samples(
                candidate_ids=[candidates[0]],
                samples_root=samples_root,
                output_root=Path(tmp),
            )
            record = json.loads(
                Path(results[0]["outputPath"]).read_text(encoding="utf-8")
            )
        self._assert_provenance(record, samples_root / candidates[0] / "candidate.html")


if __name__ == "__main__":
    unittest.main()
