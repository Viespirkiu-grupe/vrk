"""The skip predicate, held to its claim (issue #145).

A skip is a test that did not run, and the root conftest decides which
failures become skips. It used to convert any `OSError` under `samples/`,
`samples-full/`, `sitemaps/` or `data/` -- which is where every path a parser
builds lives -- so a one-character parser bug ("anketa.htm") read as 18 skips
and a green suite. The rule is now per *unit*: the candidate directory, the
election's results tree, the retained candidate, the sitemap file, the
election's data directory. Absent unit, skip; present unit and a missing path
inside it, failure. These tests pin that on a throwaway repository root and
on this checkout's own fixture tree.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import requests

import conftest
import local_data
from local_data import REPO_ROOT, describe, unit_of

FIXTURE_ELECTION = "2020-seimo"


def _tracked_candidate() -> Path:
    root = REPO_ROOT / "samples" / "html" / FIXTURE_ELECTION
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "anketa.html").exists():
            return child
    raise unittest.SkipTest(f"no candidate fixture under {root}")


class UnitTests(unittest.TestCase):
    def test_the_unit_is_the_granularity_a_scrape_produces_whole(self):
        cases = {
            "samples/html/2020-seimo/agne/anketa.html": "samples/html/2020-seimo/agne",
            "samples/html/2020-seimo/agne/campaign/tab.html": "samples/html/2020-seimo/agne",
            "samples/html/2020-seimo/lists/page1.html": "samples/html/2020-seimo/lists",
            "samples/html/2020-seimo/list.html": "samples/html/2020-seimo/list.html",
            "samples/html/2020-seimo": "samples/html/2020-seimo",
            "samples/results/2012-seimo/x/y.html": "samples/results/2012-seimo",
            "samples-full/2019-ep/jonas/anketa.html": "samples-full/2019-ep/jonas",
            "samples-full/2019-ep": "samples-full/2019-ep",
            "sitemaps/2012-seimo.results.json": "sitemaps/2012-seimo.results.json",
            "data/2020-seimo/someone-2020-seimo.json": "data/2020-seimo",
            "data/2020-seimo": "data/2020-seimo",
            "data": "data",
        }
        for path, unit in cases.items():
            with self.subTest(path):
                self.assertEqual(unit_of(Path(path)).as_posix(), unit)


class DescribeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "samples" / "html" / "e" / "here").mkdir(parents=True)
        (self.root / "samples" / "html" / "e" / "here" / "anketa.html").write_text("<html/>", encoding="utf-8")
        (self.root / "samples" / "results" / "e").mkdir(parents=True)
        (self.root / "data" / "e").mkdir(parents=True)
        (self.root / "sitemaps").mkdir()
        (self.root / "sitemaps" / "e.json").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_an_absent_unit_is_a_skip_that_names_the_unit(self):
        reason = describe(self.root / "samples" / "html" / "e" / "gone" / "anketa.html", self.root)
        self.assertIsNotNone(reason)
        self.assertTrue(reason.startswith("samples/html/e/gone is not in this checkout"), reason)
        self.assertIn("fetch-candidate-samples e", reason)
        self.assertIsNotNone(describe(self.root / "samples" / "results" / "other" / "x.html", self.root))
        self.assertIsNotNone(describe(self.root / "sitemaps" / "other.json", self.root))
        self.assertIsNotNone(describe(self.root / "data" / "other" / "x.json", self.root))
        self.assertIsNotNone(describe(self.root / "samples-full" / "e" / "jonas" / "anketa.html", self.root))

    def test_a_missing_path_inside_a_present_unit_is_not_a_skip(self):
        # The injected parser bug of issue #145: 'anketa.html' -> 'anketa.htm'
        # in a candidate directory the checkout has.
        self.assertIsNone(describe(self.root / "samples" / "html" / "e" / "here" / "anketa.htm", self.root))
        self.assertIsNone(describe(self.root / "samples" / "results" / "e" / "missing.html", self.root))
        self.assertIsNone(describe(self.root / "data" / "e" / "missing.json", self.root))

    def test_a_path_outside_the_local_data_roots_is_never_a_skip(self):
        self.assertIsNone(describe(self.root / "scraper" / "missing.py", self.root))
        self.assertIsNone(describe("/etc/nothing-here", self.root))

    def test_this_checkouts_own_fixtures_read_the_same_way(self):
        candidate = _tracked_candidate()
        self.assertIsNone(describe(candidate / "anketa.htm"))
        self.assertIsNotNone(describe(candidate.parent / "no-such-candidate" / "anketa.html"))


class ConftestPredicateTests(unittest.TestCase):
    """What the hook turns into a skip: a FileNotFoundError for an absent
    unit, through however many causes it was wrapped in, and nothing else."""

    def test_a_file_not_found_for_an_absent_unit_skips(self):
        error = FileNotFoundError(2, "No such file", str(REPO_ROOT / "samples" / "html" / FIXTURE_ELECTION / "no-such" / "anketa.html"))
        self.assertIsNotNone(conftest._missing_local_data(error))

    def test_a_file_not_found_inside_a_present_unit_fails(self):
        candidate = _tracked_candidate()
        error = FileNotFoundError(2, "No such file", str(candidate / "anketa.htm"))
        self.assertIsNone(conftest._missing_local_data(error))

    def test_other_os_errors_are_never_skips(self):
        path = str(REPO_ROOT / "samples" / "html" / FIXTURE_ELECTION / "no-such" / "anketa.html")
        self.assertIsNone(conftest._missing_local_data(PermissionError(13, "denied", path)))
        self.assertIsNone(conftest._missing_local_data(IsADirectoryError(21, "dir", path)))

    def test_the_cause_chain_is_walked(self):
        inner = FileNotFoundError(2, "No such file", str(REPO_ROOT / "sitemaps" / "no-such.json"))
        outer = ValueError("wrapped")
        outer.__cause__ = inner
        self.assertIsNotNone(conftest._missing_local_data(outer))

    def test_the_suite_refuses_the_network_and_names_the_url(self):
        # A results-rebuild test fetched 89 pages from vrk.lt on the laptop
        # and passed, then met a 403 on the runner (issue #145).
        with self.assertRaises(RuntimeError) as caught:
            requests.get("https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/20001008/ril.htm-13+2.htm", timeout=5)
        self.assertIn("reached the network", str(caught.exception))
        self.assertIn("ril.htm-13+2.htm", str(caught.exception))
        self.assertIn("VRK_TESTS_ALLOW_NETWORK", str(caught.exception))

    def test_the_scrapers_shared_session_is_refused_too(self):
        from scraper.shared.http import fetch_text

        with self.assertRaises(RuntimeError):
            fetch_text("https://www.vrk.lt/")

    def test_loopback_is_not_the_network(self):
        # tests/test_shared_http.py serves from 127.0.0.1; the refusal must
        # let that through, and a connection refused there is the proof.
        with self.assertRaises(requests.ConnectionError):
            requests.get("http://127.0.0.1:9/", timeout=1)

    def test_ci_refuses_to_run_without_node(self):
        source = (REPO_ROOT / "conftest.py").read_text(encoding="utf-8")
        self.assertIn("def pytest_sessionstart", source)
        self.assertIn('os.environ.get("CI")', source)
        self.assertIn('shutil.which("node")', source)


class RequireCorpusTests(unittest.TestCase):
    def _root(self, elections: dict[str, int], registry: list[str]) -> Path:
        root = Path(self._tmp.name)
        (root / "scraper").mkdir(exist_ok=True)
        (root / "scraper" / "elections.json").write_text(
            json.dumps({"elections": [{"id": eid} for eid in registry]}), encoding="utf-8"
        )
        for eid, records in elections.items():
            (root / "data" / eid).mkdir(parents=True)
            for i in range(records):
                (root / "data" / eid / f"c{i}-{eid}.json").write_text("{}", encoding="utf-8")
        return root

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_data_directory_skips(self):
        root = self._root({}, ["a"])
        with self.assertRaises(unittest.SkipTest):
            local_data.require_corpus(repo_root=root)

    def test_a_data_directory_holding_no_records_is_not_a_corpus(self):
        # field_coverage.py used to leave data/coverage.tsv behind on a clone.
        root = self._root({}, ["a"])
        (root / "data").mkdir()
        (root / "data" / "coverage.tsv").write_text("concept\n", encoding="utf-8")
        (root / "data" / "a").mkdir()
        (root / "data" / "a" / "anomalies.jsonl").write_text("", encoding="utf-8")
        with self.assertRaises(unittest.SkipTest):
            local_data.require_corpus(repo_root=root)

    def test_one_election_is_a_corpus_but_not_a_complete_one(self):
        root = self._root({"a": 3}, ["a", "b", "c"])
        local_data.require_corpus(repo_root=root)
        with self.assertRaises(unittest.SkipTest) as caught:
            local_data.require_corpus(complete=True, repo_root=root)
        self.assertIn("1 of 3", str(caught.exception))
        self.assertIn("b, c", str(caught.exception))

    def test_every_registered_election_present_is_complete(self):
        root = self._root({"a": 1, "b": 1}, ["a", "b"])
        local_data.require_corpus(complete=True, repo_root=root)


if __name__ == "__main__":
    unittest.main()
