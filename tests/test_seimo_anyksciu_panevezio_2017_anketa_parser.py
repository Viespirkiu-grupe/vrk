import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_anyksciu_panevezio_2017.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2017-balandzio-23-seimo-anyksciai-panevezys"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class SeimoAnyksciuPanevezio2017AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baura = _parse("antanas-baura")
        self.sargunas = _parse("ricardas-sargunas")
        self.baltusis = _parse("egidijus-baltusis")
        self.stundys = _parse("valentinas-stundys")

    def test_top_level_fields(self) -> None:
        self.assertEqual(
            self.baura["electionId"], "2017-balandzio-23-seimo-anyksciai-panevezys"
        )
        self.assertEqual(self.baura["candidateId"], "antanas-baura")
        # The listing marks the winner "Antanas BAURA (V)"; the suffix is stripped.
        self.assertEqual(self.baura["candidateName"], "Antanas BAURA")
        self.assertTrue(
            self.baura["source"]["candidateSourceUrl"].endswith(
                "lrsKandidatasAnketa_rkndId-1106688.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.baura["normalized"].keys()),
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
        # The elected note sits inside the name cell here, so a parser that
        # takes the whole cell as the name merges the two.
        profilis = self.baura["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Antanas BAURA")
        self.assertEqual(
            profilis["pastaba"],
            "Išrinktas vienmandatėje Anykščių-Panevėžio (Nr.49) apygardoje II ture",
        )
        # The embedded photo is externalized to a sidecar file; both photo
        # fields carry the relative path.
        self.assertTrue(str(profilis["nuotrauka"]).startswith("photos/"))
        self.assertTrue(str(profilis["nuotrauka"]).endswith(".jpg"))
        self.assertIsNone(self.sargunas["normalized"]["profilis"]["pastaba"])

        kita = profilis["kita"]
        self.assertEqual(kita["vienmandate-apygarda"]["reiksme"], "Anykščių-Panevėžio")
        self.assertEqual(
            kita["iskele"]["reiksme"], "Lietuvos valstiečių ir žaliųjų sąjunga"
        )
        self.assertEqual(kita["turas"]["reiksme"], "II")

    def test_anketa_top_level_keys(self) -> None:
        # The 2016 Seimo question set, biography questions included.
        self.assertEqual(
            list(self.baura["normalized"]["anketa"].keys()),
            [
                "gimimo-data",
                "adresas",
                "pareiskimai",
                "gimimo-vieta",
                "tautybe",
                "issilavinimas",
                "pedagoginis-vardas",
                "uzsienio-kalbos",
                "politine-organizacija",
                "anksciau-isrinktas",
                "pagrindine-darboviete",
                "visuomenine-veikla",
                "pomegiai",
                "seimine-padetis",
                "sutuoktinio-vardas-pavarde",
                "vaiku-vardai-pavardes",
                "kita-apie-save",
            ],
        )

    def test_anketa_core_fields(self) -> None:
        anketa = self.baura["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1955-11-21")
        self.assertEqual(anketa["adresas"], "Anykščių r. sav., Anykščiai")
        self.assertEqual(anketa["gimimo-vieta"], "Gailiešionių kaimas, Utenos sav.")
        self.assertEqual(anketa["tautybe"], "Lietuvis")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Rusų"])
        self.assertEqual(anketa["seimine-padetis"], "Vedęs")
        self.assertEqual(
            anketa["pagrindine-darboviete"],
            "Anykščių rajono sav. administracija, Žemės ūkio skyriaus vedėjas",
        )

    def test_anketa_pareiskimai_keys(self) -> None:
        pareiskimai = self.baura["normalized"]["anketa"]["pareiskimai"]
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
        for payload in (self.baura, self.sargunas, self.baltusis, self.stundys):
            with self.subTest(candidate=payload["candidateId"]):
                answers = payload["normalized"]["anketa"]["pareiskimai"]
                self.assertIsNone(answers["teisiniai-argumentai"])
                self.assertTrue(
                    all(
                        value == "Ne"
                        for key, value in answers.items()
                        if key != "teisiniai-argumentai"
                    )
                )

    def test_record_tables_rendered_in_their_own_row(self) -> None:
        # Both the education (Q12) and prior-mandate (Q15) tables sit in a row
        # of their own on these pages, so reading only the question row drops
        # them — Baura's five mandates and Sargūnas's three.
        anketa = self.baura["normalized"]["anketa"]
        self.assertEqual(len(anketa["issilavinimas"]["irasai"]), 1)
        self.assertEqual(
            anketa["issilavinimas"]["irasai"][0]["mokymo-istaigos-pavadinimas"],
            "A. Stulginskio universitetas",
        )

        mandates = anketa["anksciau-isrinktas"]["irasai"]
        self.assertEqual(len(mandates), 5)
        self.assertEqual(
            mandates[0]["institucijos-pavadinimas-pareigos"], "Anykščių rajono taryba, narys"
        )
        self.assertEqual(mandates[0]["laikotarpis"], "2015 - 2015")
        self.assertEqual(
            len(self.sargunas["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"]), 3
        )

        # A candidate who declared neither keeps empty lists.
        self.assertEqual(self.baltusis["normalized"]["anketa"]["issilavinimas"]["irasai"], [])
        self.assertEqual(
            self.baltusis["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"], []
        )

    def test_biografija_is_free_text(self) -> None:
        self.assertTrue(
            self.baura["normalized"]["biografija"]["tekstas"].startswith("ANTANAS BAURA")
        )

    def test_turto_ir_pajamu_uses_2016_gpm308_labels(self) -> None:
        turtas = self.baura["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 51711)
        self.assertEqual(turtas["vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai"], 58)
        self.assertEqual(turtas["pinigines-lesos"], 3863)
        self.assertEqual(turtas["gautos-pajamos"], 18538.4)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 2017)

    def test_privaciu_interesu_sections_keyed_by_id(self) -> None:
        privaciu = self.baura["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "ANTANAS BAURA")
        self.assertTrue(privaciu["id001j"])

    def test_campaign_participants(self) -> None:
        self.assertEqual(
            self.baura["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Atstovaujamasis",
        )
        self.assertEqual(
            self.sargunas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Savarankiškas",
        )

    def test_kita_tab_is_empty_for_every_candidate(self) -> None:
        for payload in (self.baura, self.sargunas, self.baltusis, self.stundys):
            self.assertEqual(payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []})


if __name__ == "__main__":
    unittest.main()
