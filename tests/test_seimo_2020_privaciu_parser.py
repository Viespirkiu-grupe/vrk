import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = REPO_ROOT / "data" / "2020-seimo" / "agne-sirinskiene-2020-seimo.json"

SPOUSE_KEY = "deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris"


class Seimo2020PrivaciuParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
        self.raw = self.payload["rawData"]["privaciuInteresuDeklaracija"]
        self.normalized = self.payload["normalized"]["privaciu-interesu-deklaracija"]

    def test_declarant_name_is_at_top_level(self) -> None:
        self.assertEqual(self.normalized["deklaruojantis-asmuo"], "AGNĖ ŠIRINSKIENĖ")

    def test_spouse_section_is_present(self) -> None:
        self.assertIn(SPOUSE_KEY, self.normalized)

    def test_spouse_section_has_vardas_and_pavarde(self) -> None:
        spouse = self.normalized[SPOUSE_KEY]
        self.assertIsInstance(spouse, dict)
        self.assertEqual(spouse["vardas"], "ARVYDAS")
        self.assertEqual(spouse["pavarde"], "ŠIRINSKAS")

    def test_no_sekcija_fallback_keys(self) -> None:
        for key in self.normalized:
            self.assertFalse(key.startswith("sekcija-"), f"Unexpected fallback key: {key!r}")

    def test_raw_spouse_section_title_is_non_empty(self) -> None:
        sections = self.raw["sections"]
        spouse_section = next(
            (s for s in sections if s.get("title", "").startswith("Deklaruojančio asmens sutuoktinis")),
            None,
        )
        self.assertIsNotNone(spouse_section, "Spouse section not found in rawData sections")
        self.assertNotEqual(spouse_section["title"], "")

    def test_raw_spouse_section_items_exclude_colspan_header(self) -> None:
        sections = self.raw["sections"]
        spouse_section = next(
            (s for s in sections if s.get("title", "").startswith("Deklaruojančio asmens sutuoktinis")),
            None,
        )
        self.assertIsNotNone(spouse_section, "Spouse section not found in rawData sections")
        items = spouse_section.get("items", [])
        for item in items:
            self.assertNotEqual(
                item["key"],
                "Deklaruojančio asmens sutuoktinis, sugyventinis, partneris",
                "Redundant colspan header row must not appear in items",
            )


if __name__ == "__main__":
    unittest.main()
