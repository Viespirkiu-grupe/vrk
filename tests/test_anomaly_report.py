"""Reading the corpus's anomaly events back, and the two ways the fetch stage lost them.

Issue #85 measured three separate silences in the anomaly machinery:

* every one of the corpus's 8,949 events was a `parse` event, because
  `fetch-candidate-samples` counted its events and dropped them;
* no command read `anomalies.jsonl` at all, so a new failure could not be told
  from the 8,598 known ones;
* those 8,598 were `warning`, which made `STOP_ON_ANOMALY=1` unusable on every
  archive election.

The first two are pinned here. The third is pinned where the severity is
decided, in `tests/test_deklaracija_archive_1990s.py`.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scraper import cli
from scraper.shared import anomaly_report
from scraper.shared.anomaly_report import Key

REPO_ROOT = Path(__file__).resolve().parents[1]


def _event(election: str, event_type: str, severity: str, **detail: object) -> dict:
    return {
        "timestamp": "2026-08-29T00:00:00+00:00",
        "eventType": event_type,
        "severity": severity,
        "stage": "parse",
        "electionId": election,
        "candidateId": "someone",
        "sourceUrl": None,
        "detail": detail,
    }


def _corpus(root: Path, events_by_election: dict[str, list[dict]]) -> None:
    for election, events in events_by_election.items():
        directory = root / election
        directory.mkdir(parents=True)
        (directory / anomaly_report.ANOMALIES_NAME).write_text(
            "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
            encoding="utf-8",
        )


class ReadEventsTests(unittest.TestCase):
    def test_every_election_is_read_and_tallied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _corpus(
                root,
                {
                    "2016-seimo": [_event("2016-seimo", "AnketaTableEmpty", "warning")] * 3,
                    "2020-seimo": [_event("2020-seimo", "TabDownloadFailed", "error")],
                },
            )
            counts = anomaly_report.tally(anomaly_report.read_events(root))
        self.assertEqual(
            counts,
            {
                Key("2016-seimo", "AnketaTableEmpty", "warning"): 3,
                Key("2020-seimo", "TabDownloadFailed", "error"): 1,
            },
        )

    def test_an_election_with_no_anomalies_file_is_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "2024-seimo").mkdir()
            self.assertEqual(list(anomaly_report.read_events(root)), [])

    def test_a_truncated_last_line_does_not_stop_the_report(self) -> None:
        # This file is appended to by a shell loop over an unattended scrape.
        # A half-written line is exactly when you want the report to work.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _corpus(root, {"2016-seimo": [_event("2016-seimo", "AnketaTableEmpty", "warning")]})
            path = root / "2016-seimo" / anomaly_report.ANOMALIES_NAME
            with path.open("a", encoding="utf-8") as handle:
                handle.write('{"eventType": "Tab')
            self.assertEqual(len(list(anomaly_report.read_events(root))), 1)


class DiffTests(unittest.TestCase):
    KNOWN = {Key("1997-kovo-23-savivaldybiu-tarybu", "DeclarationTotalBelowItsOwnRow", "info"): 8597}

    def test_an_unchanged_corpus_has_no_findings(self) -> None:
        new, regressed, improved = anomaly_report.diff(dict(self.KNOWN), self.KNOWN)
        self.assertEqual((new, regressed, improved), ([], [], []))

    def test_an_event_type_the_baseline_does_not_name_is_new(self) -> None:
        counts = dict(self.KNOWN)
        counts[Key("2020-seimo", "TabDownloadFailed", "error")] = 4
        new, regressed, _ = anomaly_report.diff(counts, self.KNOWN)
        self.assertEqual(new, [(Key("2020-seimo", "TabDownloadFailed", "error"), 4)])
        self.assertEqual(regressed, [])

    def test_more_of_a_known_type_is_a_regression(self) -> None:
        key = next(iter(self.KNOWN))
        new, regressed, _ = anomaly_report.diff({key: 8600}, self.KNOWN)
        self.assertEqual(new, [])
        self.assertEqual(regressed, [(key, 8600, 8597)])

    def test_fewer_is_progress_not_a_finding(self) -> None:
        key = next(iter(self.KNOWN))
        new, regressed, improved = anomaly_report.diff({key: 10}, self.KNOWN)
        self.assertEqual((new, regressed), ([], []))
        self.assertEqual(improved, [(key, 10, 8597)])

    def test_a_reclassified_severity_is_visible_on_both_sides(self) -> None:
        # Reclassifying changes what stops an unattended run, so it may not
        # pass as "the same 8,597 events".
        was = {Key("1997-kovo-23-savivaldybiu-tarybu", "DeclarationTotalBelowItsOwnRow", "warning"): 8597}
        new, regressed, improved = anomaly_report.diff(dict(self.KNOWN), was)
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0][0].severity, "info")
        self.assertEqual(len(improved), 1)
        self.assertEqual(improved[0][0].severity, "warning")


class BaselineFileTests(unittest.TestCase):
    def test_a_baseline_round_trips(self) -> None:
        counts = {
            Key("2016-seimo", "AnketaTableEmpty", "warning"): 3,
            Key("2020-seimo", "TabDownloadFailed", "error"): 1,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.tsv"
            anomaly_report.write_baseline(path, counts)
            self.assertEqual(anomaly_report.read_baseline(path), counts)

    def test_a_missing_baseline_reads_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(anomaly_report.read_baseline(Path(tmp) / "nope.tsv"), {})


class CheckedInBaselineTests(unittest.TestCase):
    def test_the_committed_baseline_parses(self) -> None:
        baseline = anomaly_report.read_baseline(REPO_ROOT / anomaly_report.BASELINE)
        self.assertTrue(baseline, "docs/anomaly-baseline.tsv is missing or empty")
        for key, count in baseline.items():
            self.assertIn(key.severity, anomaly_report.SEVERITY_ORDER, key)
            self.assertGreater(count, 0, key)

    def test_the_banner_events_are_info_so_stop_on_anomaly_is_usable(self) -> None:
        # 8,598 of 8,949. At `warning` they drowned the other 351 and stopped
        # every archive run on its first batch.
        baseline = anomaly_report.read_baseline(REPO_ROOT / anomaly_report.BASELINE)
        info = sum(count for key, count in baseline.items() if key.severity == "info")
        actionable = sum(count for key, count in baseline.items() if key.severity != "info")
        self.assertGreater(info, actionable * 10)


class ReportCommandTests(unittest.TestCase):
    """The command itself, on a throwaway corpus."""

    def _run(self, root: Path, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["scraper", "anomalies-report", "--data-root", str(root), *argv]):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main()
        return code, out.getvalue(), err.getvalue()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "data"
        _corpus(
            self.root,
            {
                "1997-kovo-23-savivaldybiu-tarybu": [
                    _event("1997-kovo-23-savivaldybiu-tarybu", "DeclarationTotalBelowItsOwnRow", "info")
                ]
                * 5,
                "2020-seimo": [_event("2020-seimo", "TabDownloadFailed", "error")],
            },
        )
        self.baseline = Path(self._tmp.name) / "baseline.tsv"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_a_run_with_no_baseline_reports_and_succeeds(self) -> None:
        code, out, err = self._run(self.root, "--baseline", str(self.baseline))
        self.assertEqual(code, 0)
        self.assertIn("6 event(s) across 2 election(s)", out)
        self.assertIn("info=5", out)
        self.assertIn("error=1", out)
        self.assertIn("No baseline", err)

    def test_writing_then_checking_the_baseline_is_clean(self) -> None:
        self.assertEqual(self._run(self.root, "--baseline", str(self.baseline), "--update-baseline")[0], 0)
        code, out, _ = self._run(self.root, "--baseline", str(self.baseline))
        self.assertEqual(code, 0)
        self.assertIn("Nothing new against the baseline", out)

    def test_a_new_event_type_fails_the_run(self) -> None:
        self._run(self.root, "--baseline", str(self.baseline), "--update-baseline")
        path = self.root / "2020-seimo" / anomaly_report.ANOMALIES_NAME
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_event("2020-seimo", "AnketaTableEmpty", "warning")) + "\n")

        code, _, err = self._run(self.root, "--baseline", str(self.baseline))
        self.assertEqual(code, 1)
        self.assertIn("AnketaTableEmpty", err)
        self.assertIn("the baseline does not name", err)

    def test_more_of_a_known_type_fails_the_run(self) -> None:
        self._run(self.root, "--baseline", str(self.baseline), "--update-baseline")
        path = self.root / "2020-seimo" / anomaly_report.ANOMALIES_NAME
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_event("2020-seimo", "TabDownloadFailed", "error")) + "\n")

        code, _, err = self._run(self.root, "--baseline", str(self.baseline))
        self.assertEqual(code, 1)
        self.assertIn("1 -> 2 (+1)", err)

    def test_errors_only_hides_the_archive_noise(self) -> None:
        code, out, _ = self._run(self.root, "--baseline", str(self.baseline), "--errors-only")
        self.assertEqual(code, 0)
        self.assertNotIn("DeclarationTotalBelowItsOwnRow", out)
        self.assertIn("TabDownloadFailed", out)

    def test_one_election_compares_against_that_election_only(self) -> None:
        # Otherwise every unvisited baseline row reads as resolved.
        self._run(self.root, "--baseline", str(self.baseline), "--update-baseline")
        code, out, _ = self._run(self.root, "--baseline", str(self.baseline), "2020-seimo")
        self.assertEqual(code, 0)
        self.assertNotIn("below the baseline", out)

    def test_an_unknown_election_is_refused_rather_than_reported_empty(self) -> None:
        code, _, err = self._run(self.root, "--baseline", str(self.baseline), "2019-ep")
        self.assertEqual(code, 2)
        self.assertIn("2019-ep", err)

    def test_a_narrowed_run_may_not_rewrite_the_whole_baseline(self) -> None:
        code, _, err = self._run(
            self.root, "--baseline", str(self.baseline), "--update-baseline", "2020-seimo"
        )
        self.assertEqual(code, 2)
        self.assertIn("cannot be narrowed", err)
        self.assertFalse(self.baseline.exists())


class FetchAnomalyPlumbingTests(unittest.TestCase):
    """`fetch-candidate-samples` used to compute its events and drop them."""

    ANOMALY = {
        "timestamp": "2026-08-29T00:00:00+00:00",
        "eventType": "TabDownloadFailed",
        "severity": "error",
        "stage": "fetch",
        "electionId": "2020-seimo",
        "candidateId": "someone",
        "sourceUrl": "https://www.vrk.lt/...",
        "detail": {"tab": "turto-ir-pajamu-deklaracijos"},
    }

    def _payload(self) -> dict:
        return {
            "count": 1,
            "results": [
                {
                    "candidate": {"candidateName": "Someone", "candidateId": "someone"},
                    "tabs_saved": 3,
                    "tab_count": 4,
                    "missing_expected_tabs": ["turto-ir-pajamu-deklaracijos"],
                    "index_path": "samples/html/2020-seimo/someone/index.json",
                    "anomalies": [self.ANOMALY],
                }
            ],
        }

    def _fetch(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with mock.patch.object(
            cli, "_fetch_candidates_with_tabs_for_election", return_value=self._payload()
        ):
            with mock.patch.object(
                sys,
                "argv",
                ["scraper", "fetch-candidate-samples", "2020-seimo", "--candidate-id", "someone", *argv],
            ):
                with contextlib.redirect_stdout(out):
                    code = cli.main()
        return code, out.getvalue()

    def test_the_events_reach_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fetch-anomalies.jsonl"
            code, out = self._fetch("--anomalies-path", str(path))
            self.assertEqual(code, 0)
            written = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(written, [self.ANOMALY])
        self.assertIn("Total anomalies: 1", out)
        self.assertIn("By severity: error=1", out)

    def test_the_stage_recorded_is_fetch(self) -> None:
        # The corpus held 8,949 events and not one of them said `fetch`.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fetch-anomalies.jsonl"
            self._fetch("--anomalies-path", str(path))
            written = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(written["stage"], "fetch")

    def test_without_the_flag_the_events_are_at_least_named(self) -> None:
        code, out = self._fetch()
        self.assertEqual(code, 0)
        self.assertIn("TabDownloadFailed=1", out)
        self.assertIn("--anomalies-path", out)

    def test_an_empty_run_still_writes_the_file(self) -> None:
        # The batch runner appends this file per candidate; a missing file and
        # an empty one have to mean the same thing to it.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fetch-anomalies.jsonl"
            payload = self._payload()
            payload["results"][0]["anomalies"] = []
            with mock.patch.object(cli, "_fetch_candidates_with_tabs_for_election", return_value=payload):
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "scraper",
                        "fetch-candidate-samples",
                        "2020-seimo",
                        "--candidate-id",
                        "someone",
                        "--anomalies-path",
                        str(path),
                    ],
                ):
                    with contextlib.redirect_stdout(io.StringIO()):
                        cli.main()
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
