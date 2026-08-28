import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2019.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2019-rugsejo-8-seimo"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Seimo2019AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.jonaitis = _parse("liudas-jonaitis")
        self.kuzmickiene = _parse("paule-kuzmickiene")
        self.janutiene = _parse("ruta-janutiene")
        self.bilkstyte = _parse("ruta-bilkstyte")
        self.paluckas = _parse("gintautas-paluckas")
        self.juraitis = _parse("kazimieras-juraitis")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.jonaitis["electionId"], "2019-rugsejo-8-seimo")
        self.assertEqual(self.jonaitis["candidateId"], "liudas-jonaitis")
        self.assertEqual(self.jonaitis["candidateName"], "Liudas JONAITIS")
        self.assertTrue(
            self.jonaitis["source"]["candidateSourceUrl"].endswith(
                "lrsKandidatasAnketa_rkndId-2415632.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.jonaitis["normalized"].keys()),
            [
                "profilis",
                "anketa",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
                "privaciu-interesu-deklaracija",
                "politines-kampanijos-dalyvio-duomenys",
                "kita",
            ],
        )

    def test_one_winner_per_constituency(self) -> None:
        # Three constituencies voted, so three candidates carry an elected note.
        self.assertEqual(
            self.jonaitis["normalized"]["profilis"]["pastaba"],
            "Išrinktas vienmandatėje Žiemgalos (Nr.46) apygardoje II ture",
        )
        self.assertTrue(
            self.kuzmickiene["normalized"]["profilis"]["pastaba"].startswith(
                "Išrinkta vienmandatėje Žirmūnų"
            )
        )
        self.assertIsNone(self.bilkstyte["normalized"]["profilis"]["pastaba"])

    def test_candidate_nominated_by_two_parties(self) -> None:
        # An extra nominator is rendered as a profile row with an empty label
        # cell. Kept as its own field it normalizes away, because a field
        # without a key has nowhere to go — so it is folded into the one above.
        self.assertEqual(
            self.janutiene["normalized"]["profilis"]["kita"]["iskele"]["reiksme"],
            "Lietuvos valstiečių ir žaliųjų sąjunga; Lietuvos centro partija",
        )
        # Single-nominator candidates are unaffected.
        self.assertEqual(
            self.bilkstyte["normalized"]["profilis"]["kita"]["iskele"]["reiksme"],
            "Išsikėlė pati",
        )

    def test_declarations(self) -> None:
        for payload in (self.jonaitis, self.kuzmickiene, self.janutiene, self.bilkstyte):
            with self.subTest(candidate=payload["candidateId"]):
                answers = payload["normalized"]["anketa"]["pareiskimai"]
                self.assertIsNone(answers["teisiniai-argumentai"])
                self.assertTrue(
                    all(v is not None for k, v in answers.items() if k != "teisiniai-argumentai")
                )

    def test_conviction_details_are_normalized(self) -> None:
        # Two of this election's 28 candidates answered Q9.2 "Taip". The detail
        # table reached rawData from the first run and was normalized nowhere
        # until issue #86, so the corpus could say they had been convicted and
        # nothing about what for.
        self.assertEqual(
            self.paluckas["normalized"]["anketa"]["teistumo-detales"],
            {
                "irasai": [
                    {
                        "nuosprendzio-data": "2012-04-03",
                        "nuosprendzio-valstybe": "Lietuva",
                        "nuosprendzio-institucija": "Lietuvos Aukščiausiasis Teismas",
                        "nusikalstama-veika": "Piktnaudžiavimas tarnybine padėtimi",
                    }
                ]
            },
        )
        self.assertEqual(
            self.juraitis["normalized"]["anketa"]["teistumo-detales"]["irasai"][0][
                "nusikalstama-veika"
            ],
            "Oficialaus dokumento suklastojimas ir panaudojimas",
        )
        # Everyone else carries the key, empty.
        for payload in (self.jonaitis, self.kuzmickiene, self.janutiene, self.bilkstyte):
            with self.subTest(candidate=payload["candidateId"]):
                anketa = payload["normalized"]["anketa"]
                self.assertEqual(anketa["pareiskimai"]["ar-buvote-pripazintas-kaltu"], "Ne")
                self.assertEqual(anketa["teistumo-detales"], {"irasai": []})

    def test_prior_mandate_records(self) -> None:
        self.assertEqual(
            len(self.jonaitis["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"]), 6
        )
        self.assertEqual(
            self.bilkstyte["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"], []
        )

    def test_turto_ir_pajamu_uses_the_modern_income_labels(self) -> None:
        turtas = self.jonaitis["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 110376)
        self.assertEqual(turtas["pinigines-lesos"], 55720)
        self.assertEqual(turtas["gautos-pajamos"], 74320)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 4538)

    def test_privaciu_interesu_sections_keyed_by_id(self) -> None:
        privaciu = self.jonaitis["normalized"]["privaciu-interesu-deklaracija"]
        self.assertTrue(privaciu["deklaruojantis-asmuo"])
        self.assertIn("id001j", privaciu)

    def test_campaign_participants(self) -> None:
        self.assertEqual(
            self.jonaitis["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Savarankiškas",
        )
        self.assertEqual(
            self.kuzmickiene["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Atstovaujamasis",
        )


if __name__ == "__main__":
    unittest.main()
