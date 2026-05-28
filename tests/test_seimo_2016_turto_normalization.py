import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2016.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2016-seimo"


class Seimo2016TurtoNormalizationTests(unittest.TestCase):
    def _parse_candidate(self, candidate_id: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = Path(tmp_dir)
            output_path, _ = parse_anketa_sample(
                candidate_id=candidate_id,
                samples_root=SAMPLES_ROOT,
                output_root=output_root,
            )
            return json.loads(output_path.read_text(encoding="utf-8"))

    def test_turto_normalized_is_flat_data_only_shape(self) -> None:
        payload = self._parse_candidate("agne-sirinskiene")

        normalized_turto = payload["normalized"]["turto-ir-pajamu-deklaracijos"]

        self.assertEqual(
            normalized_turto,
            {
                "privalomas-registruoti-turtas": 3000,
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 0,
                "pinigines-lesos": 5600,
                "suteiktos-paskolos": 0,
                "gautos-paskolos": 3832,
                "gautos-pajamos": 16611.73,
                "sumoketas-pajamu-mokestis": 1382,
            },
        )

    def test_turto_normalized_drops_descriptive_layers(self) -> None:
        payload = self._parse_candidate("agne-sirinskiene")
        normalized_turto = payload["normalized"]["turto-ir-pajamu-deklaracijos"]

        self.assertNotIn("sekcijos", normalized_turto)
        self.assertNotIn("irasai", normalized_turto)

    def test_turto_values_are_numeric_or_null(self) -> None:
        payload = self._parse_candidate("ingrida-simonyte")
        normalized_turto = payload["normalized"]["turto-ir-pajamu-deklaracijos"]

        expected_keys = {
            "privalomas-registruoti-turtas",
            "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
            "pinigines-lesos",
            "suteiktos-paskolos",
            "gautos-paskolos",
            "gautos-pajamos",
            "sumoketas-pajamu-mokestis",
        }
        self.assertEqual(set(normalized_turto.keys()), expected_keys)

        for value in normalized_turto.values():
            self.assertTrue(isinstance(value, (int, float)) or value is None)


if __name__ == "__main__":
    unittest.main()