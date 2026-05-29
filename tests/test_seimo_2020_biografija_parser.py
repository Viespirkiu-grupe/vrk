import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BIOGRAFIJA_PATH = REPO_ROOT / "data" / "2020-seimo" / "agne-sirinskiene-2020-seimo.json"


class Seimo2020BiografijaParserTests(unittest.TestCase):
    def test_biografija_keeps_structured_sections(self) -> None:
        payload = json.loads(BIOGRAFIJA_PATH.read_text(encoding="utf-8"))

        raw_biografija = payload["rawData"]["biografija"]
        self.assertNotIn("text", raw_biografija)
        self.assertNotIn("html", raw_biografija)
        self.assertNotIn("sections", raw_biografija)

        raw_rows = raw_biografija["rows"]

        self.assertGreaterEqual(len(raw_rows), 10)
        self.assertEqual(raw_rows[0]["questionNumber"], "1")
        self.assertEqual(raw_rows[0]["answer"], "1975-11-09, Vilnius")
        self.assertTrue(
            any(
                row.get("questionNumber") == "3" and isinstance(row.get("answer"), list)
                for row in raw_rows
            )
        )
        self.assertTrue(
            any(
                row.get("questionNumber") == "5" and isinstance(row.get("answer"), list)
                for row in raw_rows
            )
        )

        normalized_biografija = payload["normalized"]["biografija"]
        self.assertNotIn("tekstas", normalized_biografija)
        self.assertNotIn("sekcijos", normalized_biografija)
        self.assertEqual(normalized_biografija["gimimo-data"], "1975-11-09")
        self.assertEqual(normalized_biografija["gimimo-vieta"], "Vilnius")
        self.assertEqual(normalized_biografija["tautybe"], "Lietuvė")
        self.assertEqual(normalized_biografija["uzsienio-kalbos"], ["Anglų", "Italų", "Lotynų", "Prancūzų", "Rusų"])
        self.assertEqual(len(normalized_biografija["issilavinimas"]["irasai"]), 6)
        self.assertEqual(len(normalized_biografija["darbo-patirtis"]["irasai"]), 6)


if __name__ == "__main__":
    unittest.main()