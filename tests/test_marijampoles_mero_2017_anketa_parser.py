import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.marijampoles_mero_2017.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2017-rugsejo-10-marijampoles-mero"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class MarijampolesMero2017AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lunskiene = _parse("irena-lunskiene")
        self.zvaliauskas = _parse("algis-zvaliauskas")
        self.skamarocius = _parse("gintaras-skamarocius")
        self.sinkevicius = _parse("dobilas-sinkevicius")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.lunskiene["electionId"], "2017-rugsejo-10-marijampoles-mero")
        self.assertEqual(self.lunskiene["candidateId"], "irena-lunskiene")
        self.assertEqual(self.lunskiene["candidateName"], "Irena LUNSKIENĖ")
        self.assertTrue(
            self.lunskiene["source"]["candidateSourceUrl"].endswith(
                "savKandidatasAnketa_rkndId-2399781.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.lunskiene["normalized"].keys()),
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
        profilis = self.lunskiene["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "IRENA LUNSKIENĖ")
        self.assertTrue(profilis["nuotrauka"].startswith("data:"))

        kita = profilis["kita"]
        self.assertEqual(kita["savivaldybe"]["reiksme"], "Marijampolės (25)")
        self.assertEqual(
            kita["iskele-i-tarybos-narius-merus"]["reiksme"], "Lietuvos socialdemokratų partija"
        )
        self.assertEqual(kita["turas"]["reiksme"], "II")
        # Self-nominated candidates are recorded the same way.
        self.assertEqual(
            self.zvaliauskas["normalized"]["profilis"]["kita"][
                "iskele-i-tarybos-narius-merus"
            ]["reiksme"],
            "išsikėlė pats",
        )

    def test_elected_note_only_for_the_winner(self) -> None:
        self.assertEqual(
            self.lunskiene["normalized"]["profilis"]["pastaba"],
            "Išrinkta Marijampolės (Nr.25) savivaldybėje II ture",
        )
        self.assertIsNone(self.zvaliauskas["normalized"]["profilis"]["pastaba"])

    def test_anketa_core_fields(self) -> None:
        anketa = self.lunskiene["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1955-01-20")
        self.assertEqual(anketa["gimimo-vieta"], "Kazlų Rūda")
        self.assertEqual(anketa["tautybe"], "Lietuvė")
        self.assertEqual(anketa["pedagoginis-vardas"], "Magistras")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Rusų", "Lenkų"])
        self.assertEqual(
            anketa["pagrindine-darboviete"],
            "Marijampolės savivaldybė, Laikinai einanti mero pareigas",
        )
        self.assertEqual(anketa["vaiku-vardai-pavardes"], "Mantas, Monika")

    def test_declarations(self) -> None:
        # The Q8.x sub-questions are numbered without a trailing dot and Q9's
        # answer sits on the continuation row that quotes the statute.
        pareiskimai = self.lunskiene["normalized"]["anketa"]["pareiskimai"]
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
        self.assertTrue(all(value is not None for value in pareiskimai.values()))
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu"], "Ne")
        # Skamaročius left Q8.3 blank on the published page.
        self.assertIsNone(
            self.skamarocius["normalized"]["anketa"]["pareiskimai"]["ar-eina-nesuderinamas-pareigas"]
        )

    def test_record_tables(self) -> None:
        issilavinimas = self.lunskiene["normalized"]["anketa"]["issilavinimas"]["irasai"]
        self.assertEqual(len(issilavinimas), 2)
        self.assertEqual(
            issilavinimas[0]["mokymo-istaigos-pavadinimas"], "Kauno technologijos universitetas"
        )

        mandates = self.zvaliauskas["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"]
        self.assertEqual(len(mandates), 6)
        self.assertEqual(mandates[0]["institucijos-pavadinimas-pareigos"], "LR Seimas, Narys")
        self.assertEqual(mandates[0]["laikotarpis"], "1996 - 2000")

    def test_nenurode_answers_normalize_to_null(self) -> None:
        # Sinkevičius answered "Nenurodė" to the education and prior-mandate
        # questions, and Lunskienė to the address question.
        anketa = self.sinkevicius["normalized"]["anketa"]
        self.assertEqual(anketa["issilavinimas"]["irasai"], [])
        self.assertIsNone(anketa["issilavinimas"]["aprasas"])
        self.assertEqual(anketa["anksciau-isrinktas"]["irasai"], [])
        self.assertIsNone(self.lunskiene["normalized"]["anketa"]["adresas"])

    def test_biografija_is_free_text(self) -> None:
        self.assertTrue(
            self.lunskiene["normalized"]["biografija"]["tekstas"].startswith("IRENA LUNSKIENĖ")
        )

    def test_turto_ir_pajamu_uses_gpm308_labels(self) -> None:
        turtas = self.lunskiene["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 1120)
        self.assertEqual(turtas["pinigines-lesos"], 12000)
        self.assertEqual(turtas["gautos-paskolos"], 15800)
        self.assertEqual(turtas["gautos-pajamos"], 26282.03)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 3942)

    def test_privaciu_interesu_sections_keyed_by_id(self) -> None:
        privaciu = self.lunskiene["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "IRENA LUNSKIENĖ")
        self.assertIn("deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris", privaciu)
        self.assertTrue(privaciu["id001j"])

    def test_campaign_data(self) -> None:
        campaign = self.lunskiene["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["registravimo-data"], "2017-05-31")

        donations = campaign["aukos-pagal-sekcija"]["gautos-ir-priimtos-aukos"]
        self.assertEqual(len(donations["records"]), 7)
        self.assertEqual(donations["totals"]["is-viso"], 27153.0)

    def test_represented_participants_publish_no_campaign_tabs(self) -> None:
        # Candidates whose campaign is run by their party have a participant
        # page with no tab navigation at all, so only the participant metadata
        # is available.
        campaign = self.sinkevicius["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Atstovaujamasis")
        self.assertEqual(campaign["aukos-pagal-sekcija"], {})
        self.assertEqual(campaign["finansavimo-ataskaitos"], [])

    def test_kita_tab_is_empty_for_every_candidate(self) -> None:
        for payload in (self.lunskiene, self.zvaliauskas, self.skamarocius, self.sinkevicius):
            self.assertEqual(payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []})


if __name__ == "__main__":
    unittest.main()
