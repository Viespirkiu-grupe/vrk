import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2016.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2016-seimo"


class Seimo2016AnomalyDetectionTests(unittest.TestCase):
    def test_real_sample_has_no_structural_anomalies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, stats = parse_anketa_sample(
                candidate_id="gabrielius-landsbergis",
                samples_root=SAMPLES_ROOT,
                output_root=Path(tmp_dir),
            )

        self.assertEqual(stats["anomalies"], [])

    def test_malformed_anketa_emits_structural_anomalies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            samples_root = Path(tmp_dir) / "samples"
            output_root = Path(tmp_dir) / "output"
            candidate_dir = samples_root / "broken-candidate"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            (candidate_dir / "anketa.html").write_text(
                "<html><body><p>broken layout</p></body></html>",
                encoding="utf-8",
            )
            # The fetch stage writes index.json beside every anketa.html --
            # 0 of the corpus's 43,664 retained candidate directories hold one
            # without the other -- and since issue #153 its absence raises
            # rather than producing a quietly degraded record. This test is
            # about the *anketa* anomalies, so the candidate gets the index a
            # real one has.
            (candidate_dir / "index.json").write_text(
                json.dumps({"candidate": {"candidateId": "broken-candidate", "url": "https://x"}}),
                encoding="utf-8",
            )

            _, stats = parse_anketa_sample(
                candidate_id="broken-candidate",
                samples_root=samples_root,
                output_root=output_root,
            )

        event_types = {event["eventType"] for event in stats["anomalies"]}
        self.assertIn("TabnavSelectorNotFound", event_types)
        self.assertIn("AnketaTableNotFound", event_types)
        self.assertIn("AnketaTableEmpty", event_types)


if __name__ == "__main__":
    unittest.main()
