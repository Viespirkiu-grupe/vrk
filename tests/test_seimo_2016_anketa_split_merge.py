import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2016.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2016-seimo"


class Seimo2016AnketaSplitMergeTests(unittest.TestCase):
    def _parse_candidate(self, candidate_id: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir)
            output_path, _ = parse_anketa_sample(
                candidate_id=candidate_id,
                samples_root=SAMPLES_ROOT,
                output_root=output_root,
            )
            return json.loads(output_path.read_text(encoding="utf-8"))

    def test_q9_2_continuation_is_merged_into_single_row_and_normalized(self) -> None:
        payload = self._parse_candidate("agne-sirinskiene")

        rows = payload["rawData"]["anketa"]["rows"]
        q9_2_rows = [row for row in rows if row.get("questionNumber") == "9.2"]
        self.assertEqual(len(q9_2_rows), 1)

        q9_2 = q9_2_rows[0]
        self.assertIn("Tai nurodoma šioje anketoje", q9_2["prompt"])
        self.assertEqual(q9_2["answer"], "Ne")

        self.assertFalse(
            any(row.get("prompt", "").startswith("Tai nurodoma šioje anketoje") for row in rows),
            "Continuation row should be merged and removed from raw rows",
        )

        pareiskimai = payload["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu"], "Ne")
        self.assertNotIn("teistumo-paaiskinimas", pareiskimai)


if __name__ == "__main__":
    unittest.main()
