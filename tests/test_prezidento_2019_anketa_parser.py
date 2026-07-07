import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.prezidento_2019.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2019-prezidento"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Prezidento2019AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.nauseda = _parse("gitanas-nauseda")
        self.andriukaitis = _parse("vytenis-povilas-andriukaitis")
        self.simonyte = _parse("ingrida-simonyte")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.nauseda["electionId"], "2019-prezidento")
        self.assertEqual(self.nauseda["candidateId"], "gitanas-nauseda")
        self.assertEqual(self.nauseda["candidateName"], "Gitanas NAUSĖDA")
        self.assertTrue(
            self.nauseda["source"]["candidateSourceUrl"].endswith(
                "preKandidatasAnketa_rkndId-2414888.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.nauseda["normalized"].keys()),
            [
                "profilis",
                "anketa",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
                "privaciu-interesu-deklaracija",
                "patiketiniai",
                "politines-kampanijos-dalyvio-duomenys",
                "kita",
            ],
        )

    def test_status_note_captured_for_winner_and_losers(self) -> None:
        # The single-cell status row is captured for every candidate, not only
        # the elected president.
        self.assertEqual(self.nauseda["normalized"]["profilis"]["pastaba"], "Išrinktas II ture")
        self.assertEqual(self.simonyte["normalized"]["profilis"]["pastaba"], "Dalyvavo II ture")
        self.assertEqual(self.andriukaitis["normalized"]["profilis"]["pastaba"], "Dalyvavo I ture")

    def test_anketa_core_answers(self) -> None:
        anketa = self.nauseda["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1964-05-19")
        self.assertEqual(anketa["gimimo-vieta"], "Klaipėda, Lietuva")
        self.assertEqual(anketa["tautybe"], "Lietuvis")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Anglų", "Rusų", "Vokiečių"])
        self.assertEqual(anketa["mokslo-laipsnis"], "Socialinių mokslų daktaras")
        self.assertEqual(anketa["seimine-padetis"], "Vedęs")
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Diana Nausėdienė")

    def test_anketa_pareiskimai_keys(self) -> None:
        pareiskimai = self.nauseda["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            set(pareiskimai.keys()),
            {
                "ar-esate-pilietis-pagal-kilme",
                "ar-gyvenate-lietuvoje-trejus-metus",
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-ar-statutine-tarnyba",
                "ar-susijes-priesaika-uzsienio-valstybei",
                "uzsienio-priesaikos-atsisakymas",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-turejote-kitos-valstybes-pilietybe",
                "sutikimas-tikrinti-pilietybes-duomenis",
            },
        )
        self.assertEqual(pareiskimai["ar-esate-pilietis-pagal-kilme"], "Taip")
        self.assertEqual(pareiskimai["ar-nebaigta-teismo-paskirta-bausme"], "Neturiu")
        # 8.3.4 has no answer for this candidate; placeholders become null.
        self.assertIsNone(pareiskimai["uzsienio-priesaikos-atsisakymas"])

    def test_education_records_attached_to_q12(self) -> None:
        irasai = self.nauseda["normalized"]["anketa"]["issilavinimas"]["irasai"]
        self.assertEqual(len(irasai), 2)
        self.assertEqual(irasai[0]["mokymo-istaigos-pavadinimas"], "Vilniaus Universitetas")
        self.assertEqual(irasai[0]["baigimo-metai"], "1987")

    def test_turto_ir_pajamu_normalized(self) -> None:
        turtas = self.nauseda["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(
            list(turtas.keys()),
            [
                "privalomas-registruoti-turtas",
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai",
                "pinigines-lesos",
                "suteiktos-paskolos",
                "gautos-paskolos",
                "gautos-pajamos",
                "sumoketas-pajamu-mokestis",
            ],
        )
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 335386)
        self.assertEqual(turtas["gautos-pajamos"], 103551.22)
        # Comma-decimal amounts parse correctly (EU Commissioner, taxed abroad).
        self.assertEqual(
            self.andriukaitis["normalized"]["turto-ir-pajamu-deklaracijos"]["gautos-pajamos"],
            32.15,
        )

    def test_patiketiniai_is_empty_list(self) -> None:
        # No 2019 presidential candidate declared trustees.
        self.assertEqual(self.nauseda["normalized"]["patiketiniai"], [])

    def test_campaign_status_parsed(self) -> None:
        campaigns = self.nauseda["normalized"]["politines-kampanijos-dalyvio-duomenys"]
        self.assertTrue(campaigns)
        self.assertEqual(campaigns[0]["statusas"], "Savarankiškas")


if __name__ == "__main__":
    unittest.main()
