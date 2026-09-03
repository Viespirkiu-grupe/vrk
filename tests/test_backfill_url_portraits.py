"""`scripts/backfill_url_portraits.py` on a synthetic corpus, with the network faked.

The script's contract (issue #118): a URL-form portrait is fetched once and
landed beside the candidate's pages in every tree that holds them, a
directory another tree already serves gets a copy rather than a request, a
re-run costs nothing, a failed fetch is recorded where the parsers will read
it *and* as a `PortraitFetchFailed` event the anomaly report sees — replaced
per candidate on every run, never doubled — and what the script leaves
behind is exactly what `write_candidate_record` turns into the sidecar form.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import requests

from scraper.shared.files import externalize_record_photo

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "backfill_url_portraits", REPO_ROOT / "scripts" / "backfill_url_portraits.py"
)
script = importlib.util.module_from_spec(_spec)
# Registered before execution: the script's dataclasses resolve their
# annotations through sys.modules[<module>], which a bare exec_module leaves unset.
sys.modules[_spec.name] = script
_spec.loader.exec_module(script)

ELECTION = "2020-seimo"
JPEG = b"\xff\xd8\xff\xe0" + b"portrait-bytes"
URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/1104/rnk1424/kandidatai/kandImg/photo_%s.jpeg"


class FakeResponse:
    def __init__(self, status_code: int, content: bytes, content_type: str) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = {"Content-Type": content_type}


class FakeSession:
    """Answers each URL from a table; records every request it saw."""

    def __init__(self, answers: dict[str, object]) -> None:
        self.answers = answers
        self.calls: list[str] = []

    def get(self, url: str, timeout: float | None = None) -> FakeResponse:
        self.calls.append(url)
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


def image(content: bytes = JPEG) -> FakeResponse:
    return FakeResponse(200, content, "image/jpeg")


class BackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "data" / ELECTION).mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- fixture builders ---------------------------------------------------

    def record(self, candidate_id: str, url: str | None, key: str = "photoSrc") -> dict:
        record = {
            "electionId": ELECTION,
            "candidateId": candidate_id,
            "candidateName": candidate_id,
            "source": {"candidateSourceUrl": f"https://www.vrk.lt/{candidate_id}.html"},
            "rawData": {"profile": {"candidateDisplayName": candidate_id, key: url or ""}},
            "normalized": {"profilis": {"vardas-pavarde": candidate_id, "nuotrauka": url}},
        }
        path = self.root / "data" / ELECTION / f"{candidate_id}-{ELECTION}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return record

    def candidate_dir(self, tree: str, candidate_id: str) -> Path:
        directory = self.root / tree / ELECTION / candidate_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "anketa.html").write_text("<html></html>", encoding="utf-8")
        (directory / "index.json").write_text("{}", encoding="utf-8")
        return directory

    def anomalies_path(self) -> Path:
        return self.root / "data" / ELECTION / "anomalies.jsonl"

    def run_backfill(self, session, **options) -> script.ElectionStats:
        stats = script.backfill_election(self.root, ELECTION, session, pause=0, **options)
        if not options.get("dry_run"):
            # What main() does after each election.
            script.rewrite_failure_events(
                self.anomalies_path(), ELECTION, stats.processed, stats.failures
            )
        return stats

    def events(self) -> list[dict]:
        path = self.anomalies_path()
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # -- the contract -------------------------------------------------------

    def test_a_portrait_is_fetched_once_and_landed_in_both_trees(self) -> None:
        url = URL % 1
        self.record("jonas", url)
        retained = self.candidate_dir("samples-full", "jonas")
        fixture = self.candidate_dir("samples/html", "jonas")
        session = FakeSession({url: image()})

        stats = self.run_backfill(session)

        self.assertEqual(session.calls, [url])
        self.assertEqual((stats.records, stats.fetched, stats.failed, stats.bytes), (1, 1, 0, len(JPEG)))
        for directory in (retained, fixture):
            self.assertEqual((directory / "portrait.jpg").read_bytes(), JPEG)
            meta = json.loads((directory / "portrait.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["url"], url)
            self.assertEqual(meta["file"], "portrait.jpg")
            self.assertEqual(meta["mime"], "image/jpeg")
            self.assertEqual(meta["bytes"], len(JPEG))
            self.assertEqual(meta["sha256"], hashlib.sha256(JPEG).hexdigest())
            self.assertTrue(meta["fetchedAt"].endswith("+00:00"))
        self.assertEqual(self.events(), [])

    def test_a_second_run_asks_the_network_nothing(self) -> None:
        url = URL % 1
        self.record("jonas", url)
        self.candidate_dir("samples-full", "jonas")
        session = FakeSession({url: image()})
        self.run_backfill(session)

        again = FakeSession({})
        stats = self.run_backfill(again)
        self.assertEqual(again.calls, [])
        self.assertEqual((stats.retained, stats.fetched), (1, 0))

    def test_dry_run_touches_nothing(self) -> None:
        url = URL % 1
        self.record("jonas", url)
        retained = self.candidate_dir("samples-full", "jonas")
        stats = self.run_backfill(None, dry_run=True)
        self.assertEqual((stats.records, stats.fetched), (1, 1))
        self.assertEqual(sorted(p.name for p in retained.iterdir()), ["anketa.html", "index.json"])
        self.assertFalse(self.anomalies_path().exists())

    def test_a_failed_fetch_is_recorded_reported_and_retried_only_on_request(self) -> None:
        url = URL % 1
        self.record("jonas", url)
        retained = self.candidate_dir("samples-full", "jonas")
        session = FakeSession({url: FakeResponse(404, b"<html>gone</html>", "text/html")})

        stats = self.run_backfill(session)
        self.assertEqual((stats.fetched, stats.failed), (0, 1))
        meta = json.loads((retained / "portrait.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["url"], url)
        self.assertEqual(meta["error"], "HTTP 404")
        self.assertNotIn("file", meta)
        self.assertFalse((retained / "portrait.jpg").exists())

        events = self.events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["eventType"], "PortraitFetchFailed")
        self.assertEqual(event["stage"], "fetch")
        self.assertEqual(event["severity"], "warning")
        self.assertEqual(event["candidateId"], "jonas")
        self.assertEqual(event["sourceUrl"], url)
        self.assertEqual(event["detail"]["error"], "HTTP 404")
        self.assertEqual(event["timestamp"], meta["fetchedAt"])

        # Without --retry-failed the failure stands, unasked and undoubled.
        untouched = FakeSession({})
        stats = self.run_backfill(untouched)
        self.assertEqual(untouched.calls, [])
        self.assertEqual(stats.failed_before, 1)
        self.assertEqual(len(self.events()), 1)

        # With it, the URL is tried again; success clears the event.
        retry = FakeSession({url: image()})
        stats = self.run_backfill(retry, retry_failed=True)
        self.assertEqual(retry.calls, [url])
        self.assertEqual((stats.fetched, stats.failed), (1, 0))
        self.assertEqual((retained / "portrait.jpg").read_bytes(), JPEG)
        self.assertEqual(self.events(), [])

    def test_a_transport_error_is_a_failure_too(self) -> None:
        url = URL % 1
        self.record("jonas", url)
        retained = self.candidate_dir("samples-full", "jonas")
        session = FakeSession({url: requests.ConnectionError("connection reset")})
        stats = self.run_backfill(session)
        self.assertEqual(stats.failed, 1)
        meta = json.loads((retained / "portrait.json").read_text(encoding="utf-8"))
        self.assertTrue(meta["error"].startswith("ConnectionError:"))

    def test_an_html_page_served_with_200_is_not_a_portrait(self) -> None:
        url = URL % 1
        self.record("jonas", url)
        retained = self.candidate_dir("samples-full", "jonas")
        session = FakeSession({url: FakeResponse(200, b"<!DOCTYPE html><html>", "text/html; charset=UTF-8")})
        stats = self.run_backfill(session)
        self.assertEqual(stats.failed, 1)
        meta = json.loads((retained / "portrait.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["error"], "not an image: text/html; charset=UTF-8, 21 bytes")
        self.assertFalse(any(retained.glob("portrait.*[!n]")))

    def test_a_tree_without_the_portrait_copies_from_the_one_that_has_it(self) -> None:
        url = URL % 1
        self.record("jonas", url)
        retained = self.candidate_dir("samples-full", "jonas")
        script.write_retained_portrait(retained, url, "2026-09-02T20:00:00+00:00", JPEG, None)
        fixture = self.candidate_dir("samples/html", "jonas")

        session = FakeSession({})
        stats = self.run_backfill(session)
        self.assertEqual(session.calls, [])
        self.assertEqual((stats.retained, stats.copied), (1, 1))
        self.assertEqual((fixture / "portrait.jpg").read_bytes(), JPEG)
        self.assertEqual(
            json.loads((fixture / "portrait.json").read_text(encoding="utf-8")),
            json.loads((retained / "portrait.json").read_text(encoding="utf-8")),
        )

    def test_only_fixtures_leaves_the_retained_only_candidates_alone(self) -> None:
        self.record("jonas", URL % 1)
        self.record("petras", URL % 2)
        self.candidate_dir("samples-full", "jonas")
        self.candidate_dir("samples/html", "jonas")
        self.candidate_dir("samples-full", "petras")
        session = FakeSession({URL % 1: image()})
        stats = self.run_backfill(session, only_fixtures=True)
        self.assertEqual(session.calls, [URL % 1])
        self.assertEqual((stats.fetched, stats.skipped), (1, 1))

    def test_a_record_retained_nowhere_is_counted_not_fetched(self) -> None:
        self.record("jonas", URL % 1)
        session = FakeSession({})
        stats = self.run_backfill(session)
        self.assertEqual(session.calls, [])
        self.assertEqual((stats.records, stats.without_dir), (1, 1))

    def test_sidecar_and_empty_values_are_not_targets(self) -> None:
        self.record("ona", "photos/ona.jpg")
        self.record("kazys", "")
        self.record("jonas", None)
        self.assertEqual(script.election_targets(self.root, ELECTION), [])

    def test_the_archive_family_photo_url_is_a_target(self) -> None:
        url = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seim96/ld1.jpg"
        self.record("alvydas", url, key="photoUrl")
        self.candidate_dir("samples-full", "alvydas")
        session = FakeSession({url: image()})
        stats = self.run_backfill(session)
        self.assertEqual((stats.fetched, session.calls), (1, [url]))

    def test_what_the_script_leaves_is_what_the_parsers_externalize(self) -> None:
        # The round trip the design rests on: a re-parse from the retained
        # tree must produce the sidecar form, with no data/ write by the script.
        url = URL % 1
        record = self.record("jonas", url)
        retained = self.candidate_dir("samples-full", "jonas")
        self.run_backfill(FakeSession({url: image()}))

        output_path = self.root / "fresh" / f"jonas-{ELECTION}.json"
        output_path.parent.mkdir()
        externalize_record_photo(record, output_path, retained / "anketa.html")
        self.assertEqual(record["rawData"]["profile"]["photoSrc"], "photos/jonas.jpg")
        self.assertEqual(record["normalized"]["profilis"]["nuotrauka"], "photos/jonas.jpg")
        self.assertEqual(record["rawData"]["profile"]["photoMeta"]["url"], url)
        self.assertEqual((output_path.parent / "photos" / "jonas.jpg").read_bytes(), JPEG)

    def test_the_event_rewrite_keeps_everything_that_is_not_its_own(self) -> None:
        path = self.anomalies_path()
        parse_event = {"stage": "parse", "eventType": "ResidenceMissing", "candidateId": "ona"}
        other = script.failure_event(ELECTION, "other", {"url": URL % 9, "error": "HTTP 404", "fetchedAt": "2026-09-01T00:00:00+00:00"})
        mine = script.failure_event(ELECTION, "jonas", {"url": URL % 1, "error": "HTTP 404", "fetchedAt": "2026-09-01T00:00:00+00:00"})
        path.write_text(
            "".join(json.dumps(e) + "\n" for e in (parse_event, other, mine)) + "not json\n",
            encoding="utf-8",
        )
        removed, written = script.rewrite_failure_events(path, ELECTION, {"jonas"}, {})
        self.assertEqual((removed, written), (1, 0))
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], json.dumps(parse_event))
        self.assertEqual(json.loads(lines[1])["candidateId"], "other")
        self.assertEqual(lines[2], "not json")
        self.assertEqual(len(lines), 3)

        # Nothing to remove and nothing to write: the file is not rewritten.
        before = path.stat().st_mtime_ns
        self.assertEqual(script.rewrite_failure_events(path, ELECTION, {"jonas"}, {}), (0, 0))
        self.assertEqual(path.stat().st_mtime_ns, before)


if __name__ == "__main__":
    unittest.main()
