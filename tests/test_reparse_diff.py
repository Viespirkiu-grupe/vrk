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
        parsed, _, errors = script.reparse(
            ELECTION_ID, [(FIXTURES_ROOT, None)], output_root, jobs=1
        )
        self.assertEqual(errors, [])
        self.assertGreater(parsed, 0)

    def _run(self, **kwargs) -> tuple[bool, int, object, int]:
        options = dict(full=False, apply=False, jobs=1, top=5)
        options.update(kwargs)
        return script.run_election(ELECTION_ID, self.root, self.work_root, **options)

    def _records(self) -> list[Path]:
        return sorted(self.data_dir.glob("*.json"))

    def test_an_untouched_corpus_reports_no_drift(self) -> None:
        ok, differing, histogram, unreached = self._run()
        self.assertEqual(unreached, 0)
        self.assertTrue(ok)
        self.assertEqual(differing, 0)
        self.assertEqual(histogram, {})

    def test_a_stale_record_is_found_and_named(self) -> None:
        target = self._records()[0]
        record = json.loads(target.read_text(encoding="utf-8"))
        record["normalized"]["profilis"]["nuotrauka"] = "data:;base64,AAAA"
        record["normalized"]["anketa"].pop("pedagoginis-vardas", None)
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        ok, differing, histogram, _ = self._run()
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

        ok, differing, _, _ = script.run_election(
            ELECTION_ID, self.root, self.work_root, full=True, apply=True, jobs=1, top=5
        )
        self.assertTrue(ok)
        self.assertEqual(differing, 1)

        ok, differing, _, _ = self._run()
        self.assertTrue(ok)
        self.assertEqual(differing, 0, "a second pass must be clean")
        self.assertEqual(
            untouched.stat().st_mtime_ns,
            before[untouched],
            "records that did not drift must not be rewritten",
        )

    def test_a_full_run_that_reached_only_some_records_says_so(self) -> None:
        # Issue #157: the gate's claim is that exit 0 means the corpus is
        # what the parsers produce, and it cannot mean that over records the
        # run never read. `compared` and `stored_total` were printed and
        # thrown away, so 2 of 1,271 re-parsed read as "0 differ", exit 0.
        stored = self._records()
        extra = self.data_dir / "somebody-else-2003-birzelio-15-seimo-nauji.json"
        extra.write_text(
            json.dumps({"candidateId": "somebody-else"}, ensure_ascii=False), encoding="utf-8"
        )
        ok, differing, _, unreached = self._run(full=True)
        self.assertTrue(ok)
        self.assertEqual(differing, 0, "the record the run could not reach is not 'drifted'")
        self.assertEqual(unreached, 1)
        self.assertEqual(len(self._records()), len(stored) + 1)

    def test_a_fixture_run_is_partial_by_design_and_is_not_gated_on_coverage(self) -> None:
        extra = self.data_dir / "somebody-else-2003-birzelio-15-seimo-nauji.json"
        extra.write_text(json.dumps({"candidateId": "x"}, ensure_ascii=False), encoding="utf-8")
        _, _, _, unreached = self._run(full=False)
        self.assertEqual(unreached, 0)

    def test_a_short_full_run_exits_one(self) -> None:
        extra = self.data_dir / "somebody-else-2003-birzelio-15-seimo-nauji.json"
        extra.write_text(json.dumps({"candidateId": "x"}, ensure_ascii=False), encoding="utf-8")
        argv = [
            "reparse_diff.py", "--full",
            "--repo-root", str(self.root),
            "--work-root", str(self.work_root),
            ELECTION_ID,
        ]
        with mock.patch.object(sys, "argv", argv):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()) as stderr:
                    code = script.main()
        self.assertEqual(code, 1)
        self.assertIn("not covered by this run", stderr.getvalue())
        self.assertIn(f"{ELECTION_ID} (1)", stderr.getvalue())

    def test_a_full_run_that_reached_everything_exits_zero(self) -> None:
        argv = [
            "reparse_diff.py", "--full",
            "--repo-root", str(self.root),
            "--work-root", str(self.work_root),
            ELECTION_ID,
        ]
        with mock.patch.object(sys, "argv", argv):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()) as stderr:
                    code = script.main()
        self.assertEqual(code, 0, stderr.getvalue())

    def test_a_short_apply_says_the_corpus_is_now_mixed(self) -> None:
        # --apply was half-protected: it used the coverage number to decide
        # whether to rewrite anomalies.jsonl, and neither for the record copy
        # nor for the exit code. A run that reached part of an election left
        # the rest at the old parser's output and reported success.
        extra = self.data_dir / "somebody-else-2003-birzelio-15-seimo-nauji.json"
        extra.write_text(json.dumps({"candidateId": "x"}, ensure_ascii=False), encoding="utf-8")
        argv = [
            "reparse_diff.py", "--full", "--apply",
            "--repo-root", str(self.root),
            "--work-root", str(self.work_root),
            ELECTION_ID,
        ]
        with mock.patch.object(sys, "argv", argv):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()) as stderr:
                    code = script.main()
        self.assertEqual(code, 1)
        self.assertIn("the corpus is now mixed", stderr.getvalue())

    def test_apply_refuses_a_fixture_run(self) -> None:
        # Applying a fixture run would rewrite a handful of records and leave
        # the other 13,661 stale, which is how the corpus got here.
        with mock.patch.object(sys, "argv", ["reparse_diff.py", "--apply", ELECTION_ID]):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit):
                    script.main()
        self.assertIn("--apply requires --full", stderr.getvalue())


def _candidate_dir(root: Path, candidate_id: str) -> None:
    """The shape `candidate_dirs` looks for: an index.json beside a page."""
    directory = root / candidate_id
    directory.mkdir(parents=True)
    (directory / "index.json").write_text("{}", encoding="utf-8")
    (directory / "anketa.html").write_text("<html></html>", encoding="utf-8")


class SampleSourceTests(unittest.TestCase):
    def test_full_prefers_retained_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = root / "samples" / "html" / ELECTION_ID
            retained = root / "samples-full" / ELECTION_ID
            _candidate_dir(fixtures, "jonas-jonaitis")
            _candidate_dir(retained, "jonas-jonaitis")
            self.assertEqual(
                script.resolve_sample_sources(root, ELECTION_ID, full=True),
                [(retained, None)],
            )
            self.assertEqual(
                script.resolve_sample_sources(root, ELECTION_ID, full=False),
                [(fixtures, None)],
            )

    def test_a_candidate_with_a_fixture_and_no_retained_page_is_parsed_too(self) -> None:
        # The gap issue #101 found: `--apply` could not reach these records
        # while the fixture run kept reporting them as drifted.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = root / "samples" / "html" / ELECTION_ID
            retained = root / "samples-full" / ELECTION_ID
            _candidate_dir(fixtures, "jonas-jonaitis")
            _candidate_dir(fixtures, "petras-petraitis")
            _candidate_dir(retained, "jonas-jonaitis")
            self.assertEqual(
                script.resolve_sample_sources(root, ELECTION_ID, full=True),
                [(retained, None), (fixtures, ["petras-petraitis"])],
            )

    def test_full_falls_back_to_fixtures_when_nothing_was_retained(self) -> None:
        # For the archive families the fixture tree *is* every candidate.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = root / "samples" / "html" / ELECTION_ID
            _candidate_dir(fixtures, "jonas-jonaitis")
            self.assertEqual(
                script.resolve_sample_sources(root, ELECTION_ID, full=True),
                [(fixtures, None)],
            )

    def test_an_election_with_no_sample_tree_at_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(script.resolve_sample_sources(Path(tmp), ELECTION_ID, full=True), [])



class AnomalyFileTests(unittest.TestCase):
    """`--apply` owns the parse-stage events and nothing else."""

    PARSE_A = {"stage": "parse", "eventType": "ResidenceMissing", "candidateId": "a"}
    PARSE_B = {"stage": "parse", "eventType": "ResidenceMissing", "candidateId": "b"}
    FETCH = {"stage": "fetch", "eventType": "PortraitFetchFailed", "candidateId": "a"}

    def _write(self, path: Path, events: list[dict]) -> None:
        path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")

    def _read(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def test_fetch_stage_events_survive_a_rewrite(self) -> None:
        # A portrait URL that answered 404 is a fetch the re-parse never made;
        # replacing the file wholesale would turn it back into "never tried".
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anomalies.jsonl"
            self._write(path, [self.FETCH, self.PARSE_A])
            self.assertTrue(script.write_anomalies(path, [self.PARSE_B]))
            self.assertEqual(self._read(path), [self.FETCH, self.PARSE_B])

    def test_unchanged_parse_events_leave_the_file_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anomalies.jsonl"
            self._write(path, [self.PARSE_A, self.FETCH])
            before = path.read_text(encoding="utf-8")
            self.assertFalse(script.write_anomalies(path, [self.PARSE_A]))
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_a_fresh_timestamp_on_the_same_finding_is_not_a_change(self) -> None:
        # Every re-parse stamps its events with its own clock; a file whose
        # findings did not change keeps the timestamps of when they were found.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anomalies.jsonl"
            self._write(path, [{**self.PARSE_A, "timestamp": "2026-08-29T00:00:00+00:00"}])
            self.assertFalse(
                script.write_anomalies(path, [{**self.PARSE_A, "timestamp": "2026-09-03T00:00:00+00:00"}])
            )
            self.assertEqual(self._read(path)[0]["timestamp"], "2026-08-29T00:00:00+00:00")

    def test_a_file_of_only_fetch_events_gains_the_parse_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anomalies.jsonl"
            self._write(path, [self.FETCH])
            self.assertTrue(script.write_anomalies(path, [self.PARSE_A]))
            self.assertEqual(self._read(path), [self.FETCH, self.PARSE_A])

if __name__ == "__main__":
    unittest.main()
