"""`scripts/reparse_diff.py` is the gate; this is what makes it trustworthy.

Issue #91: a quarter of the corpus no longer re-parsed to what was stored,
because nothing checked. A gate that under-reports is worse than none, so the
classification is pinned on synthetic records -- every kind of divergence the
corpus actually showed -- and the round trip is pinned on a real election:
parse `2019-prezidento` from its fixtures, break one record the way the corpus
was broken, and assert the script sees it, then repairs it.
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
ELECTION_ID = "2019-prezidento"
FIXTURES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID


def _load_script():
    path = REPO_ROOT / "scripts" / "reparse_diff.py"
    spec = importlib.util.spec_from_file_location("reparse_diff", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()


class DiffPathsTests(unittest.TestCase):
    def test_identical_records_have_no_differences(self) -> None:
        record = {"a": 1, "b": {"c": ["x", "y"]}, "d": None}
        self.assertEqual(script.diff_paths(record, json.loads(json.dumps(record))), [])

    def test_a_key_only_the_fresh_parse_emits_is_added(self) -> None:
        # rawData.profile.photoMeta, in 77 fixture records.
        self.assertEqual(
            script.diff_paths({"profile": {}}, {"profile": {"photoMeta": {"bytes": 1}}}),
            [("profile.photoMeta", "added")],
        )

    def test_a_key_only_the_stored_record_carries_is_removed(self) -> None:
        # The always-null columns dropped in fdd9e59, e.g. id001f asmens-kodas.
        self.assertEqual(
            script.diff_paths({"id001f": {"asmens-kodas": None}}, {"id001f": {}}),
            [("id001f.asmens-kodas", "removed")],
        )

    def test_a_changed_scalar_is_changed(self) -> None:
        self.assertEqual(
            script.diff_paths({"nuotrauka": "data:;base64,AAA"}, {"nuotrauka": "photos/x.jpg"}),
            [("nuotrauka", "changed")],
        )

    def test_a_dict_becoming_a_list_is_a_type_change(self) -> None:
        # normalized.privaciu-interesu-deklaracija.id001a, both shapes.
        self.assertEqual(
            script.diff_paths({"id001a": {"tekstas": "x"}}, {"id001a": [{"tekstas": "x"}]}),
            [("id001a", "type")],
        )

    def test_list_indices_collapse_so_the_histogram_names_one_path(self) -> None:
        stored = {"rysiai": [{"rysys": None, "vardas": "A"}, {"rysys": None, "vardas": "B"}]}
        fresh = {"rysiai": [{"vardas": "A"}, {"vardas": "B"}]}
        self.assertEqual(
            script.diff_paths(stored, fresh),
            [("rysiai[].rysys", "removed"), ("rysiai[].rysys", "removed")],
        )

    def test_a_length_change_is_reported_once_at_the_list(self) -> None:
        self.assertEqual(
            script.diff_paths({"irasai": []}, {"irasai": [{"nuosprendzio-data": "1995-04-15"}]}),
            [("irasai[]", "length")],
        )

    def test_an_int_that_became_a_float_is_a_type_change(self) -> None:
        # `0 == 0.0` in Python, but the two are different files on disk.
        self.assertEqual(script.diff_paths({"suteiktos-paskolos": 0}, {"suteiktos-paskolos": 0.0}),
                         [("suteiktos-paskolos", "type")])
        self.assertEqual(script.diff_paths({"isrinktas": False}, {"isrinktas": 0}),
                         [("isrinktas", "type")])

    def test_none_and_missing_are_different_findings(self) -> None:
        self.assertEqual(script.diff_paths({"a": None}, {"a": 1}), [("a", "type")])
        self.assertEqual(script.diff_paths({}, {"a": None}), [("a", "added")])


class ChunkSizeTests(unittest.TestCase):
    def test_a_small_election_still_fills_every_worker(self) -> None:
        # 301 candidates in chunks of 200 leaves six of eight processes idle.
        self.assertLessEqual(script.chunk_size(301, 8) * 8, 301)

    def test_a_large_election_is_capped_so_progress_is_not_lumpy(self) -> None:
        self.assertEqual(script.chunk_size(13_666, 8), script.MAX_CHUNK_SIZE)

    def test_a_tiny_election_is_one_chunk(self) -> None:
        self.assertEqual(script.chunk_size(5, 8), script.MIN_CHUNK_SIZE)


class RoundTripTests(unittest.TestCase):
    """Re-parse, diff and apply against a real election in a throwaway root."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "samples").mkdir()
        (self.root / "samples" / "html").mkdir()
        (self.root / "samples" / "html" / ELECTION_ID).symlink_to(FIXTURES_ROOT)
        self.data_dir = self.root / "data" / ELECTION_ID
        self.data_dir.mkdir(parents=True)
        self.work_root = self.root / "work"

        # The corpus as a re-parse would write it, so the only divergence in
        # this fixture is the one the test introduces.
        self._reparse_into(self.data_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _reparse_into(self, output_root: Path) -> None:
        parsed, _, errors = script.reparse(ELECTION_ID, FIXTURES_ROOT, output_root, jobs=1)
        self.assertEqual(errors, [])
        self.assertGreater(parsed, 0)

    def _run(self, **kwargs) -> tuple[bool, int, object]:
        options = dict(full=False, apply=False, jobs=1, top=5)
        options.update(kwargs)
        return script.run_election(ELECTION_ID, self.root, self.work_root, **options)

    def _records(self) -> list[Path]:
        return sorted(self.data_dir.glob("*.json"))

    def test_an_untouched_corpus_reports_no_drift(self) -> None:
        ok, differing, histogram = self._run()
        self.assertTrue(ok)
        self.assertEqual(differing, 0)
        self.assertEqual(histogram, {})

    def test_a_stale_record_is_found_and_named(self) -> None:
        target = self._records()[0]
        record = json.loads(target.read_text(encoding="utf-8"))
        record["normalized"]["profilis"]["nuotrauka"] = "data:;base64,AAAA"
        record["normalized"]["anketa"].pop("pedagoginis-vardas", None)
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        ok, differing, histogram = self._run()
        self.assertTrue(ok)
        self.assertEqual(differing, 1)
        self.assertEqual(histogram[("normalized.profilis.nuotrauka", "changed")], 1)

    def test_apply_repairs_only_the_record_that_drifted(self) -> None:
        records = self._records()
        if len(records) < 2:
            raise unittest.SkipTest(
                f"only one {ELECTION_ID} fixture candidate is in this checkout; "
                "showing that the other records are untouched needs two"
            )
        target, untouched = records[0], records[1]
        before = {path: path.stat().st_mtime_ns for path in self._records()}

        record = json.loads(target.read_text(encoding="utf-8"))
        record["normalized"]["profilis"]["nuotrauka"] = "data:;base64,AAAA"
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        ok, differing, _ = script.run_election(
            ELECTION_ID, self.root, self.work_root, full=True, apply=True, jobs=1, top=5
        )
        self.assertTrue(ok)
        self.assertEqual(differing, 1)

        ok, differing, _ = self._run()
        self.assertTrue(ok)
        self.assertEqual(differing, 0, "a second pass must be clean")
        self.assertEqual(
            untouched.stat().st_mtime_ns,
            before[untouched],
            "records that did not drift must not be rewritten",
        )

    def test_apply_refuses_a_fixture_run(self) -> None:
        # Applying a fixture run would rewrite a handful of records and leave
        # the other 13,661 stale, which is how the corpus got here.
        with mock.patch.object(sys, "argv", ["reparse_diff.py", "--apply", ELECTION_ID]):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit):
                    script.main()
        self.assertIn("--apply requires --full", stderr.getvalue())


class SamplesRootTests(unittest.TestCase):
    def test_full_prefers_retained_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "samples" / "html" / ELECTION_ID).mkdir(parents=True)
            (root / "samples-full" / ELECTION_ID).mkdir(parents=True)
            self.assertEqual(
                script.resolve_samples_root(root, ELECTION_ID, full=True),
                root / "samples-full" / ELECTION_ID,
            )
            self.assertEqual(
                script.resolve_samples_root(root, ELECTION_ID, full=False),
                root / "samples" / "html" / ELECTION_ID,
            )

    def test_full_falls_back_to_fixtures_when_nothing_was_retained(self) -> None:
        # For the archive families the fixture tree *is* every candidate.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "samples" / "html" / ELECTION_ID).mkdir(parents=True)
            self.assertEqual(
                script.resolve_samples_root(root, ELECTION_ID, full=True),
                root / "samples" / "html" / ELECTION_ID,
            )

    def test_an_election_with_no_sample_tree_at_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(script.resolve_samples_root(Path(tmp), ELECTION_ID, full=True))


if __name__ == "__main__":
    unittest.main()
