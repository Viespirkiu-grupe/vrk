import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2016.anketa_parser import parse_anketa_sample
from scraper.shared.anketa_tabs import parse_eur_amount
from scraper.shared.deklaracijos import DECLARATION_VALUE_KEYS


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
            {key: normalized_turto[key] for key in DECLARATION_VALUE_KEYS},
            {
                "privalomas-registruoti-turtas": 3000,
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 0,
                "pinigines-lesos": 5600,
                "suteiktos-paskolos": 0,
                "gautos-paskolos": 3832,
                "gautos-pajamos": 16611.73,
                "sumoketas-pajamu-mokestis": 1382,
                # The 2016 pages print the two-row income extract; the four
                # further GPM lines arrive with the 2018 rewording.
                "individualios-veiklos-pajamos": None,
                "individualios-veiklos-atskaitymai": None,
                "turto-pardavimo-pajamos": None,
                "turto-isigijimo-kaina": None,
            },
        )

    def test_turto_normalized_says_what_the_extract_is(self) -> None:
        payload = self._parse_candidate("agne-sirinskiene")
        normalized_turto = payload["normalized"]["turto-ir-pajamu-deklaracijos"]

        # The 2016 heading names the form but not the year: "METINĖS PAJAMŲ
        # MOKESČIO DEKLARACIJOS GPM308 FORMOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS",
        # with no "(2015 m.)" as the 2019-and-later pages carry.
        self.assertEqual(normalized_turto["deklaracijos-forma"], "GPM308")
        self.assertIsNone(normalized_turto["deklaracijos-metai"])
        self.assertEqual(normalized_turto["deklaracijos-apimtis"], "gyventojo-seimos")

        self.assertEqual(
            [(section["rusis"], section["apimtis"]) for section in normalized_turto["deklaracijos"]],
            [("turto", "gyventojo-seimos"), ("pajamu", None)],
        )

    def test_turto_normalized_drops_descriptive_layers(self) -> None:
        payload = self._parse_candidate("agne-sirinskiene")
        normalized_turto = payload["normalized"]["turto-ir-pajamu-deklaracijos"]

        self.assertNotIn("sekcijos", normalized_turto)
        self.assertNotIn("irasai", normalized_turto)

    def test_turto_values_are_numeric_or_null(self) -> None:
        payload = self._parse_candidate("ingrida-simonyte")
        normalized_turto = payload["normalized"]["turto-ir-pajamu-deklaracijos"]

        self.assertEqual(
            set(normalized_turto),
            set(DECLARATION_VALUE_KEYS)
            | {"deklaracijos-metai", "deklaracijos-forma", "deklaracijos-apimtis", "deklaracijos"},
        )

        for key in DECLARATION_VALUE_KEYS:
            with self.subTest(key=key):
                value = normalized_turto[key]
                self.assertTrue(isinstance(value, (int, float)) or value is None)


class EurAmountParsingTests(unittest.TestCase):
    def test_amount_below_one_euro_keeps_its_value(self) -> None:
        # VRK renders such an amount without its leading zero -- the page
        # source reads "<b>,53 Eur</b>" -- which used to normalize to null and
        # lost 102 published figures across six elections.
        self.assertEqual(parse_eur_amount(",53 Eur"), 0.53)
        self.assertEqual(parse_eur_amount(",6 Eur"), 0.6)
        self.assertEqual(parse_eur_amount("-,5 Eur"), -0.5)

    def test_ordinary_amounts_are_unchanged(self) -> None:
        self.assertEqual(parse_eur_amount("0 Eur"), 0)
        self.assertEqual(parse_eur_amount("43202,09 Eur"), 43202.09)
        self.assertEqual(parse_eur_amount("1 325 940 Eur"), 1325940)
        self.assertEqual(parse_eur_amount("EUR 1234"), 1234)

    def test_a_unit_glued_to_the_figure_is_still_a_unit(self) -> None:
        # A word-boundary strip leaves the unit on "25565Eur" and the figure
        # normalizes to null: the key is present, the value is plausible, and
        # nothing fails -- the shape of issues #81 and #98. No 2016-on page
        # glues its unit today; the 2002 pages glued their litas (issue #90).
        self.assertEqual(parse_eur_amount("25565Eur"), 25565)
        self.assertEqual(parse_eur_amount("25565EUR"), 25565)
        self.assertEqual(parse_eur_amount("1 234,56Eur"), 1234.56)
        self.assertEqual(parse_eur_amount(",53Eur"), 0.53)

    def test_a_unit_closed_with_a_full_stop_is_still_a_unit(self) -> None:
        # The litas-era parsers accept "Lt." for the same reason.
        self.assertEqual(parse_eur_amount("25565 Eur."), 25565)
        self.assertEqual(parse_eur_amount("25565Eur."), 25565)

    def test_the_letters_are_a_unit_only_where_a_unit_stands(self) -> None:
        # Before the figure, after it or glued to its end -- never inside a
        # run of digits, where taking them out would invent a number.
        self.assertIsNone(parse_eur_amount("1eur2"))

    def test_non_amounts_stay_null(self) -> None:
        for value in ("", ",", "Eur", "Eur.", "nenurodė", None):
            with self.subTest(value=value):
                self.assertIsNone(parse_eur_amount(value))


if __name__ == "__main__":
    unittest.main()