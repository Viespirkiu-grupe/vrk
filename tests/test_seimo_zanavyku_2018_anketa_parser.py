import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_zanavyku_2018.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2018-rugsejo-16-seimo-zanavykai"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class SeimoZanavyku2018AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.haase = _parse("irena-haase")
        self.bastys = _parse("mindaugas-bastys")
        self.jukna = _parse("vigilijus-jukna")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.haase["electionId"], "2018-rugsejo-16-seimo-zanavykai")
        self.assertEqual(self.haase["candidateId"], "irena-haase")
        # The listing marks the winner "Irena HAASE (V)"; the suffix is stripped.
        self.assertEqual(self.haase["candidateName"], "Irena HAASE")
        self.assertTrue(
            self.haase["source"]["candidateSourceUrl"].endswith(
                "lrsKandidatasAnketa_rkndId-2399846.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.haase["normalized"].keys()),
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

    def test_profile_card_fields(self) -> None:
        profilis = self.haase["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Irena HAASE")
        # The embedded photo is externalized to a sidecar file; both photo
        # fields carry the relative path.
        self.assertTrue(str(profilis["nuotrauka"]).startswith("photos/"))
        self.assertTrue(str(profilis["nuotrauka"]).endswith(".jpg"))
        self.assertEqual(
            profilis["pastaba"], "Išrinkta vienmandatėje Zanavykų (Nr.64) apygardoje II ture"
        )
        self.assertIsNone(self.jukna["normalized"]["profilis"]["pastaba"])

        kita = profilis["kita"]
        self.assertEqual(kita["vienmandate-apygarda"]["reiksme"], "Zanavykų")
        self.assertEqual(
            kita["iskele"]["reiksme"], "Tėvynės sąjunga-Lietuvos krikščionys demokratai"
        )
        self.assertEqual(kita["turas"]["reiksme"], "II")
        # Self-nomination is recorded in the same field.
        self.assertEqual(
            self.bastys["normalized"]["profilis"]["kita"]["iskele"]["reiksme"], "Išsikėlė pats"
        )

    def test_anketa_core_fields(self) -> None:
        anketa = self.haase["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1960-08-10")
        self.assertEqual(anketa["adresas"], "Šakių r. sav.")
        self.assertEqual(anketa["tautybe"], "Lietuvė")
        self.assertEqual(anketa["seimine-padetis"], "Ištekėjusi")

    def test_declarations(self) -> None:
        pareiskimai = self.haase["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            list(pareiskimai.keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-susijes-priesaika-uzsienio-valstybei",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis",
                "ar-buvote-pripazintas-kaltu",
                "ar-veika-dekriminalizuota",
                "ar-buvote-pripazintas-kaltu-uzsienyje",
                "ar-buvote-pripazintas-kaltu-uzsienyje-del-politinio-persekiojimo",
                "teisiniai-argumentai",
            ],
        )
        # Q9.3.4 is the free-text justification, filled only on a "Taip" answer.
        for payload in (self.haase, self.bastys, self.jukna):
            with self.subTest(candidate=payload["candidateId"]):
                answers = payload["normalized"]["anketa"]["pareiskimai"]
                self.assertIsNone(answers["teisiniai-argumentai"])
                self.assertTrue(
                    all(v is not None for k, v in answers.items() if k != "teisiniai-argumentai")
                )

    def test_prior_mandate_records(self) -> None:
        mandates = self.haase["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"]
        self.assertEqual(len(mandates), 3)
        self.assertEqual(
            mandates[0]["institucijos-pavadinimas-pareigos"],
            "Šakių rajono savivaldybės taryba, Tarybos narė",
        )
        self.assertEqual(mandates[0]["laikotarpis"], "2015 - 2019")
        self.assertEqual(
            len(self.bastys["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"]), 5
        )

    def test_turto_ir_pajamu_uses_the_modern_income_labels(self) -> None:
        # The section is still headed GPM308, but the income rows switched to
        # the modern wording between the April 2017 by-election and this one.
        # With the 2016 aliases every income figure comes out null.
        turtas = self.haase["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 9078)
        self.assertEqual(turtas["pinigines-lesos"], 12590)
        self.assertEqual(turtas["gautos-pajamos"], 25382.16)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 2461)

    def test_biografija_is_free_text(self) -> None:
        self.assertTrue(self.haase["normalized"]["biografija"]["tekstas"])

    def test_privaciu_interesu_and_campaign(self) -> None:
        privaciu = self.haase["normalized"]["privaciu-interesu-deklaracija"]
        self.assertTrue(privaciu["deklaruojantis-asmuo"])
        campaigns = self.haase["normalized"]["politines-kampanijos-dalyvio-duomenys"]
        self.assertEqual(campaigns[0]["statusas"], "Savarankiškas")


if __name__ == "__main__":
    unittest.main()
