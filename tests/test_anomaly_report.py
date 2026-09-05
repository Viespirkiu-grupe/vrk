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
from scraper.shared import anomalies, anomaly_report
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

    def test_an_election_that_lost_most_of_its_events_collapsed(self) -> None:
        # Fewer is progress one row at a time; most of an election's events
        # gone at once is what a wiped anomalies.jsonl looks like (issue #139:
        # a one-candidate re-parse took the 1997 municipal file from 8,636
        # events to 8, and the report called it progress).
        baseline = {Key("a", "X", "info"): 8_600, Key("a", "Y", "warning"): 36, Key("b", "Z", "error"): 4}
        counts = {Key("a", "X", "info"): 6, Key("a", "Y", "warning"): 2, Key("b", "Z", "error"): 4}
        self.assertEqual(anomaly_report.collapsed(counts, baseline), [("a", 8, 8_636)])

    def test_keeping_half_or_more_of_the_events_is_still_progress(self) -> None:
        baseline = {Key("a", "X", "info"): 10, Key("a", "Y", "warning"): 10}
        self.assertEqual(anomaly_report.collapsed({Key("a", "X", "info"): 10}, baseline), [])
        self.assertEqual(anomaly_report.collapsed({Key("a", "X", "info"): 9}, baseline), [("a", 9, 20)])

    def test_an_election_the_baseline_does_not_know_cannot_collapse(self) -> None:
        self.assertEqual(anomaly_report.collapsed({Key("new", "X", "info"): 1}, {}), [])

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

    def test_a_wiped_election_file_fails_the_run(self) -> None:
        self._run(self.root, "--baseline", str(self.baseline), "--update-baseline")
        path = self.root / "1997-kovo-23-savivaldybiu-tarybu" / anomaly_report.ANOMALIES_NAME
        events = path.read_text(encoding="utf-8").splitlines()
        path.write_text(events[0] + "\n", encoding="utf-8")  # 5 -> 1: a wipe, not a fix
        code, _out, err = self._run(self.root, "--baseline", str(self.baseline))
        self.assertEqual(code, 1)
        self.assertIn("lost more than half their events", err)
        self.assertIn("1997-kovo-23-savivaldybiu-tarybu  5 -> 1", err)
        self.assertIn("--update-baseline", err)

    def test_a_drop_that_keeps_half_the_events_is_progress(self) -> None:
        self._run(self.root, "--baseline", str(self.baseline), "--update-baseline")
        path = self.root / "1997-kovo-23-savivaldybiu-tarybu" / anomaly_report.ANOMALIES_NAME
        events = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(events[:3]) + "\n", encoding="utf-8")  # 5 -> 3
        code, out, err = self._run(self.root, "--baseline", str(self.baseline))
        self.assertEqual(code, 0)
        self.assertIn("5 -> 3", out)
        self.assertNotIn("lost more than half", err)

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


class ParseAnomalyOwnershipTests(unittest.TestCase):
    """A run owns its own stage's events for the candidates it processed, and
    nothing else in the file (issue #139).

    The parse command's default `--anomalies-path` is the election's own
    `data/<id>/anomalies.jsonl` -- the file the batch runner appends to and
    the portrait backfill writes its fetch events into -- and it used to open
    that file with "w" and write only its run: the documented one-candidate
    form took the 1997 municipal election from 8,636 events to 2.
    """

    ELECTION = "2023-geguzes-7-visagino-mero"

    @staticmethod
    def _event(candidate: str, stage: str, event_type: str) -> dict:
        return {**_event("2023-geguzes-7-visagino-mero", event_type, "warning"), "candidateId": candidate, "stage": stage}

    def test_merge_replaces_only_the_runs_own_stage_and_candidates(self) -> None:
        other_parse = self._event("b", "parse", "ResidenceMissing")
        own_fetch = self._event("a", "fetch", "PortraitFetchFailed")
        own_stale = self._event("a", "parse", "Stale")
        fresh = self._event("a", "parse", "Fresh")
        merged = anomalies.merge_run([other_parse, own_fetch, own_stale], [fresh], stage="parse", candidate_ids=["a"])
        self.assertEqual(merged, [other_parse, own_fetch, fresh])

    def test_a_whole_election_run_owns_every_parse_event(self) -> None:
        # scripts/reparse_diff.py --apply: candidate_ids=None means the run
        # covered every candidate, so only the other stages survive.
        stored = [self._event("a", "parse", "X"), self._event("b", "parse", "Y"), self._event("a", "fetch", "Z")]
        fresh = [self._event("b", "parse", "Y")]
        self.assertEqual(
            anomalies.merge_run(stored, fresh, stage="parse", candidate_ids=None),
            [stored[2], fresh[0]],
        )

    def test_an_event_without_a_candidate_is_never_owned_by_a_candidate_run(self) -> None:
        stored = [{**self._event("a", "parse", "ElectionLevel"), "candidateId": None}]
        self.assertEqual(anomalies.merge_run(stored, [], stage="parse", candidate_ids=["a"]), stored)

    def test_write_run_events_round_trips_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anomalies.jsonl"
            stored = [self._event("b", "parse", "X"), self._event("a", "fetch", "F"), self._event("a", "parse", "Old")]
            anomalies.write_jsonl(path, stored)
            kept, replaced = anomalies.write_run_events(path, [self._event("a", "parse", "New")], stage="parse", candidate_ids=["a"])
            self.assertEqual((kept, replaced), (2, 1))
            self.assertEqual(
                [(e["candidateId"], e["stage"], e["eventType"]) for e in anomalies.read_jsonl(path)],
                [("b", "parse", "X"), ("a", "fetch", "F"), ("a", "parse", "New")],
            )

    def test_a_missing_file_reads_as_no_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(anomalies.read_jsonl(Path(tmp) / "none.jsonl"), [])

    def test_a_truncated_last_line_does_not_lose_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anomalies.jsonl"
            path.write_text(json.dumps(self._event("b", "parse", "X")) + "\n{\"eventType\": \"Trunc", encoding="utf-8")
            self.assertEqual(len(anomalies.read_jsonl(path)), 1)

    def test_the_documented_one_candidate_parse_keeps_the_other_lines(self) -> None:
        # The command itself, against a real tracked fixture, into a scratch
        # output root seeded the way the corpus's file is: another
        # candidate's parse events, this candidate's fetch event (a portrait
        # fetch no re-parse can regenerate) and this candidate's stale
        # parse event.
        other_parse = self._event("erlandas-galaguz", "parse", "ResidenceMissing")
        own_fetch = self._event("dalia-straupaite", "fetch", "PortraitFetchFailed")
        own_stale = self._event("dalia-straupaite", "parse", "Stale")
        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp) / "out"
            out_root.mkdir()
            path = out_root / anomaly_report.ANOMALIES_NAME
            anomalies.write_jsonl(path, [other_parse, own_fetch, own_stale])
            argv = [
                "scraper", "parse-anketa-samples", self.ELECTION,
                "--candidate-id", "dalia-straupaite", "--output-root", str(out_root),
            ]
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                code = cli.main()
            self.assertEqual(code, 0)
            left = anomalies.read_jsonl(path)
        self.assertIn(other_parse, left)
        self.assertIn(own_fetch, left)
        self.assertNotIn(own_stale, left)
        self.assertTrue(all(e["candidateId"] == "dalia-straupaite" for e in left if e not in (other_parse, own_fetch)))


if __name__ == "__main__":
    unittest.main()
