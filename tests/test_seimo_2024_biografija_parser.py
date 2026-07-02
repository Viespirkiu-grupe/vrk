import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2024.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2024-seimo"
CANDIDATE_IDS = [
    "algirdas-butkevicius",
    "gabrielius-landsbergis",
    "ingrida-simonyte",
    "saulius-skvernelis",
    "vilma-aasrum",
]
DROPPED_2016_ERA_KEYS = {
    "tautybe",
    "sutuoktinio-vardas-pavarde",
    "vaiku-vardai-pavardes",
    "kita-apie-save",
    "moksline-pedagogine-visuomenine-veikla",
}


def _parse_candidate(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Seimo2024BiografijaParserTests(unittest.TestCase):
    def test_biografija_rows_use_2024_question_numbering(self) -> None:
        payload = _parse_candidate("saulius-skvernelis")

        raw_rows = payload["rawData"]["biografija"]["rows"]
        self.assertGreaterEqual(len(raw_rows), 9)
        self.assertEqual(raw_rows[0]["questionNumber"], "1")
        self.assertEqual(raw_rows[0]["answer"], "1970-07-23, Kaunas")

        by_question = {row["questionNumber"]: row["answer"] for row in raw_rows}
        self.assertIsInstance(by_question["2"], list)
        self.assertIsInstance(by_question["4"], list)
        for question in ("2.1", "2.2", "3", "5", "6", "7"):
            self.assertIsInstance(by_question[question], str)

    def test_biografija_normalizes_skvernelis_fields(self) -> None:
        payload = _parse_candidate("saulius-skvernelis")

        biografija = payload["normalized"]["biografija"]
        self.assertEqual(biografija["gimimo-data"], "1970-07-23")
        self.assertEqual(biografija["gimimo-vieta"], "Kaunas")
        self.assertEqual(biografija["mokslo-laipsnis"], "Neturiu")
        self.assertEqual(biografija["pedagoginis-vardas"], "Neturiu")
        self.assertEqual(
            biografija["uzsienio-kalbos"],
            ["Anglų (Pradedantis)", "Lenkų (Įgudęs)", "Rusų (Įgudęs)"],
        )
        self.assertEqual(len(biografija["issilavinimas"]["irasai"]), 3)
        self.assertEqual(
            biografija["issilavinimas"]["irasai"][0]["mokymo-istaigos-pavadinimas"],
            "Mykolo Romerio universitetas",
        )
        self.assertEqual(len(biografija["darbo-patirtis"]["irasai"]), 12)
        self.assertEqual(biografija["darbo-patirtis"]["irasai"][0]["darbo-pradzia"], "2020")
        self.assertEqual(biografija["visuomenine-veikla"], "Nėra")
        self.assertEqual(biografija["seimine-padetis"], "Vedęs")
        self.assertTrue(biografija["pomegiai"])

    def test_biografija_drops_questions_absent_from_2024_form(self) -> None:
        payload = _parse_candidate("saulius-skvernelis")

        biografija = payload["normalized"]["biografija"]
        self.assertEqual(DROPPED_2016_ERA_KEYS & set(biografija), set())

    def test_biografija_is_populated_for_every_fixture_candidate(self) -> None:
        for candidate_id in CANDIDATE_IDS:
            with self.subTest(candidate=candidate_id):
                payload = _parse_candidate(candidate_id)
                biografija = payload["normalized"]["biografija"]

                self.assertIsNotNone(biografija["gimimo-data"])
                self.assertGreaterEqual(len(biografija["issilavinimas"]["irasai"]), 1)
                self.assertGreaterEqual(len(biografija["darbo-patirtis"]["irasai"]), 1)
                self.assertGreaterEqual(len(biografija["uzsienio-kalbos"]), 1)
                self.assertIsNotNone(biografija["seimine-padetis"])


if __name__ == "__main__":
    unittest.main()
