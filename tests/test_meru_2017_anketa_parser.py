import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.meru_2017.anketa_parser import parse_anketa_sample
from scraper.elections.meru_2017.candidate_samples import _campaign_url_variants


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2017-balandzio-23-meru"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Meru2017CampaignUrlFallbackTests(unittest.TestCase):
    def test_treasurer_url_falls_back_to_the_represented_participant(self) -> None:
        # Candidate pages link every participant through the treasurer page, but
        # party-represented participants have none and that link 404s upstream.
        base = "https://www.vrk.lt/statiniai/puslapiai/politKamp/804/dalyviai/"
        self.assertEqual(
            _campaign_url_variants(base + "savarankiskasIzdininkas_pkdId-1628.html"),
            [
                base + "savarankiskasIzdininkas_pkdId-1628.html",
                base + "atstovaujamasis_pkdId-1628.html",
            ],
        )
        # Already-correct URLs are left alone.
        self.assertEqual(
            _campaign_url_variants(base + "atstovaujamasis_pkdId-1628.html"),
            [base + "atstovaujamasis_pkdId-1628.html"],
        )


class Meru2017AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sabutis = _parse("eugenijus-sabutis")
        self.pilypaitis = _parse("edgaras-pilypaitis")
        self.mockus = _parse("darius-mockus")
        self.cikana = _parse("vidas-cikana")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.sabutis["electionId"], "2017-balandzio-23-meru")
        self.assertEqual(self.sabutis["candidateId"], "eugenijus-sabutis")
        self.assertEqual(self.sabutis["candidateName"], "Eugenijus SABUTIS")
        self.assertTrue(
            self.sabutis["source"]["candidateSourceUrl"].endswith(
                "savKandidatasAnketa_rkndId-1106692.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.sabutis["normalized"].keys()),
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
        profilis = self.sabutis["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "EUGENIJUS SABUTIS")
        # These pages embed the photo rather than linking it.
        # The embedded photo is externalized to a sidecar file; both photo
        # fields carry the relative path.
        self.assertTrue(str(profilis["nuotrauka"]).startswith("photos/"))
        self.assertTrue(str(profilis["nuotrauka"]).endswith(".jpg"))

        kita = profilis["kita"]
        self.assertEqual(kita["savivaldybe"]["reiksme"], "Jonavos rajono (10)")
        self.assertEqual(
            kita["iskele-i-tarybos-narius-merus"]["reiksme"], "Lietuvos socialdemokratų partija"
        )
        self.assertEqual(kita["turas"]["reiksme"], "II")

    def test_elected_notes(self) -> None:
        # One mayor elected in each of the two municipalities.
        self.assertEqual(
            self.sabutis["normalized"]["profilis"]["pastaba"],
            "Išrinktas Jonavos rajono (Nr.10) savivaldybėje II ture",
        )
        self.assertEqual(
            self.pilypaitis["normalized"]["profilis"]["pastaba"],
            "Išrinktas Šakių rajono (Nr.42) savivaldybėje II ture",
        )
        self.assertIsNone(self.mockus["normalized"]["profilis"]["pastaba"])

    def test_anketa_top_level_keys(self) -> None:
        # The biography questions are part of the anketa, as in 2016 Seimo.
        self.assertEqual(
            list(self.sabutis["normalized"]["anketa"].keys()),
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
        anketa = self.sabutis["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1975-09-10")
        self.assertEqual(anketa["adresas"], "Jonava")
        self.assertEqual(anketa["gimimo-vieta"], "Jonava")
        self.assertEqual(anketa["tautybe"], "Lietuvis")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Rusų"])
        self.assertEqual(anketa["politine-organizacija"], "Lietuvos socialdemokratų partija")
        self.assertEqual(anketa["seimine-padetis"], "Vedęs")

    def test_sub_questions_numbered_without_a_dot(self) -> None:
        # "8.2 Ar nesate ..." has no dot after the number, which the strict
        # question-number pattern reads as question "8" — collapsing all four
        # declarations onto the section heading and losing their answers.
        pareiskimai = self.sabutis["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            list(pareiskimai.keys()),
            [
                "ar-atliekate-karo-tarnyba",
                "ar-eina-nesuderinamas-pareigas",
                "ar-kitos-valstybes-institucijos-narys",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-buvote-pripazintas-kaltu",
            ],
        )
        self.assertEqual(pareiskimai["ar-atliekate-karo-tarnyba"], "Nesu")
        self.assertEqual(pareiskimai["ar-eina-nesuderinamas-pareigas"], "Neinu")
        self.assertEqual(pareiskimai["ar-kitos-valstybes-institucijos-narys"], "Nesu")
        self.assertEqual(pareiskimai["ar-turite-kitos-valstybes-pilietybe"], "Nesu")

    def test_q9_answer_comes_from_the_continuation_row(self) -> None:
        # Q9 quotes the statute in a row of its own and the answer is rendered
        # there, so reading the question row alone yields nothing.
        for payload in (self.sabutis, self.pilypaitis, self.mockus, self.cikana):
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    payload["normalized"]["anketa"]["pareiskimai"]["ar-buvote-pripazintas-kaltu"],
                    "Ne",
                )

    def test_unanswered_declaration_stays_null(self) -> None:
        # Mockus left Q8.3 blank on the published page.
        self.assertIsNone(
            self.mockus["normalized"]["anketa"]["pareiskimai"]["ar-eina-nesuderinamas-pareigas"]
        )

    def test_record_tables_attached_to_their_questions(self) -> None:
        anketa = self.sabutis["normalized"]["anketa"]
        issilavinimas = anketa["issilavinimas"]["irasai"]
        self.assertEqual(len(issilavinimas), 2)
        self.assertEqual(
            issilavinimas[0]["mokymo-istaigos-pavadinimas"], "Vytauto Didžiojo universitetas"
        )
        self.assertEqual(issilavinimas[0]["baigimo-metai"], "1999")

        mandates = anketa["anksciau-isrinktas"]["irasai"]
        self.assertEqual(len(mandates), 1)
        self.assertEqual(
            mandates[0]["institucijos-pavadinimas-pareigos"],
            "Jonavos rajono savivaldybė, Tarybos narys",
        )
        self.assertEqual(mandates[0]["laikotarpis"], "2015 - 2019")
        self.assertEqual(len(self.cikana["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"]), 3)

    def test_unnumbered_rows_matched_by_prompt(self) -> None:
        # The pedagogic title, the spouse name and Q21 (whose number is written
        # in brackets at the end) carry no leading question number.
        anketa = self.sabutis["normalized"]["anketa"]
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Rasa")
        self.assertEqual(anketa["vaiku-vardai-pavardes"], "Tomas")
        # "Nenurodė" normalizes to null for all three of these on this page.
        self.assertIsNone(anketa["pedagoginis-vardas"])
        self.assertIsNone(anketa["kita-apie-save"])

    def test_biografija_is_free_text(self) -> None:
        tekstas = self.sabutis["normalized"]["biografija"]["tekstas"]
        self.assertTrue(tekstas.startswith("EUGENIJUS SABUTIS"))

    def test_turto_ir_pajamu_uses_gpm308_labels(self) -> None:
        # The income rows name GPM308 form fields, so the alias table differs
        # from both the 2016 Seimo and the 2019 EP one.
        turtas = self.sabutis["normalized"]["turto-ir-pajamu-deklaracijos"]
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
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 17900)
        self.assertEqual(turtas["gautos-pajamos"], 21571.64)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 3182)

    def test_privaciu_interesu_sections_keyed_by_id(self) -> None:
        privaciu = self.sabutis["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "EUGENIJUS SABUTIS")
        sutuoktinis = privaciu["deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris"]
        self.assertEqual(sutuoktinis["vardas"], "RASA")
        self.assertEqual(sutuoktinis["pavarde"], "SABUTIENĖ")
        self.assertTrue(privaciu["id001j"])

    def test_campaign_data(self) -> None:
        campaign = self.sabutis["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["registravimo-data"], "2017-01-17")
        self.assertEqual(
            len(campaign["aukos-pagal-sekcija"]["gautos-ir-priimtos-aukos"]["records"]), 7
        )
        # Cikana's campaign is only reachable through the fallback URL.
        self.assertEqual(
            self.cikana["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Atstovaujamasis",
        )

    def test_kita_tab_is_empty_for_every_candidate(self) -> None:
        for payload in (self.sabutis, self.pilypaitis, self.mockus, self.cikana):
            self.assertEqual(payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []})


if __name__ == "__main__":
    unittest.main()
