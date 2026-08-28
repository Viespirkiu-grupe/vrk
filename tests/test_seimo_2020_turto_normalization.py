import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2020.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2020-seimo"

MONEY_KEYS = ("gautos-pajamos", "sumoketas-pajamu-mokestis")


class Seimo2020TurtoNormalizationTests(unittest.TestCase):
    """The 2020 pages word the two money rows their own way (issue #81).

    2020 reuses the 2016 normalizer, whose alias table was keyed on the slug of
    VRK's whole 2016 sentence -- GPM308 field numbers and all. The 2020 pages
    say "Deklaruota apmokestinamųjų ir neapmokestinamųjų pajamų suma" instead,
    so the alias missed and every one of the election's 1,753 declaration
    records normalized to null income while the figures sat in rawData.
    """

    def _parse_candidate(self, candidate_id: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path, _ = parse_anketa_sample(
                candidate_id=candidate_id,
                samples_root=SAMPLES_ROOT,
                output_root=Path(tmp_dir),
            )
            return json.loads(output_path.read_text(encoding="utf-8"))

    def test_declaration_is_the_flat_seven_key_shape(self) -> None:
        payload = self._parse_candidate("agne-sirinskiene")

        self.assertEqual(
            payload["normalized"]["turto-ir-pajamu-deklaracijos"],
            {
                "privalomas-registruoti-turtas": 3000,
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 0,
                "pinigines-lesos": 2000,
                "suteiktos-paskolos": 0,
                "gautos-paskolos": 0,
                "gautos-pajamos": 45223.76,
                "sumoketas-pajamu-mokestis": 9044.75,
            },
        )

    def test_income_matches_the_figure_published_on_the_page(self) -> None:
        payload = self._parse_candidate("gabrielius-landsbergis")
        declaration = payload["normalized"]["turto-ir-pajamu-deklaracijos"]
        raw_items = {
            item["key"]: item["value"]
            for section in payload["rawData"]["turtoIrPajamuDeklaracijos"]["sections"]
            for item in section["items"]
        }

        self.assertEqual(raw_items["Deklaruota apmokestinamųjų ir neapmokestinamųjų pajamų suma"], "50111,96 Eur")
        self.assertEqual(declaration["gautos-pajamos"], 50111.96)
        self.assertEqual(raw_items["Deklaruota mokėtina pajamų mokesčio suma"], "10007,58 Eur")
        self.assertEqual(declaration["sumoketas-pajamu-mokestis"], 10007.58)

    def test_every_fixture_candidate_has_both_money_figures(self) -> None:
        # The regression that hid the defect: the fixtures parsed fine and no
        # test asserted the income of any of them.
        candidate_ids = sorted(path.name for path in SAMPLES_ROOT.iterdir() if path.is_dir())
        self.assertTrue(candidate_ids)

        for candidate_id in candidate_ids:
            with self.subTest(candidate=candidate_id):
                declaration = self._parse_candidate(candidate_id)["normalized"][
                    "turto-ir-pajamu-deklaracijos"
                ]
                for key in MONEY_KEYS:
                    self.assertIsInstance(declaration[key], (int, float))


if __name__ == "__main__":
    unittest.main()
