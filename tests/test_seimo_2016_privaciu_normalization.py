import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2016.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2016-seimo"


class Seimo2016PrivaciuNormalizationTests(unittest.TestCase):
    def _parse_candidate(self, candidate_id: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir)
            output_path, _ = parse_anketa_sample(
                candidate_id=candidate_id,
                samples_root=SAMPLES_ROOT,
                output_root=output_root,
            )
            return json.loads(output_path.read_text(encoding="utf-8"))

    def test_key_value_sections_use_flat_object(self) -> None:
        payload = self._parse_candidate("agne-sirinskiene")
        normalized = payload["normalized"]["privaciu-interesu-deklaracija"]

        self.assertEqual(normalized["deklaruojantis-asmuo"], "AGNĖ ŠIRINSKIENĖ")

    def test_matrix_sections_use_row_objects(self) -> None:
        payload = self._parse_candidate("agne-sirinskiene")
        normalized = payload["normalized"]["privaciu-interesu-deklaracija"]

        matrix_section = normalized["id001j"]
        self.assertIsInstance(matrix_section, list)
        self.assertGreater(len(matrix_section), 0)
        self.assertIsInstance(matrix_section[0], dict)
        self.assertEqual(matrix_section[0]["asmuo-kurio-rysys-nurodytas"], "Deklaruojantysis")
        self.assertEqual(matrix_section[0]["valstybe"], "Lietuvos Respublika")
        self.assertEqual(matrix_section[0]["rysys-su-juridiniu-asmeniu"], "Darbuotojas, turintis administravimo įgaliojimus")

    def test_spouse_section_is_dropped(self) -> None:
        payload = self._parse_candidate("agne-sirinskiene")
        normalized = payload["normalized"]["privaciu-interesu-deklaracija"]

        self.assertNotIn("sekcija-2", normalized)

    def test_old_wrapper_fields_are_removed(self) -> None:
        payload = self._parse_candidate("agne-sirinskiene")
        normalized = payload["normalized"]["privaciu-interesu-deklaracija"]

        for section in normalized.values():
            if isinstance(section, dict):
                self.assertNotIn("pavadinimas", section)
                self.assertNotIn("sekcijos-id", section)
                self.assertNotIn("stulpeliai", section)
                self.assertNotIn("eilutes", section)
                self.assertNotIn("items", section)
                self.assertNotIn("rows", section)


if __name__ == "__main__":
    unittest.main()