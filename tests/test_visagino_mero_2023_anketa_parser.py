import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.visagino_mero_2023.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2023-geguzes-7-visagino-mero"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class VisaginoMero2023AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.galaguz = _parse("erlandas-galaguz")
        self.straupaite = _parse("dalia-straupaite")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.galaguz["electionId"], "2023-geguzes-7-visagino-mero")
        self.assertEqual(self.galaguz["candidateId"], "erlandas-galaguz")
        self.assertEqual(self.galaguz["candidateName"], "Erlandas GALAGUZ")
        self.assertTrue(
            self.galaguz["source"]["candidateSourceUrl"].endswith(
                "savKandidatasAnketa_2023_rkndId-2435245.html"
            )
        )
        self.assertEqual(self.straupaite["candidateName"], "Dalia ŠTRAUPAITĖ")

    def test_normalized_section_order_has_no_campaign_section(self) -> None:
        # The repeat vote re-runs the March 2023 mayoral runoff, so neither
        # candidate page publishes a campaign tab — unlike the Kupiškis pages
        # this module otherwise mirrors.
        for payload in (self.galaguz, self.straupaite):
            self.assertEqual(
                list(payload["normalized"].keys()),
                [
                    "profilis",
                    "anketa",
                    "biografija",
                    "turto-ir-pajamu-deklaracijos",
                    "privaciu-interesu-deklaracija",
                    "kita",
                ],
            )
            self.assertNotIn("politinesKampanijosDalyvioDuomenys", payload["rawData"])

    def test_profile_municipal_fields(self) -> None:
        kita = self.galaguz["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["savivaldybe"]["reiksme"], "Visagino (59)")
        self.assertEqual(
            kita["iskele-i-savivaldybes-merus"]["reiksme"],
            "Lietuvos valstiečių ir žaliųjų sąjunga",
        )
        self.assertEqual(
            self.straupaite["normalized"]["profilis"]["kita"]["iskele-i-savivaldybes-merus"]["reiksme"],
            'Partija "Laisvė ir teisingumas"',
        )
        # Both candidates carry round II — the repeat vote is only the runoff.
        for payload in (self.galaguz, self.straupaite):
            self.assertEqual(payload["normalized"]["profilis"]["kita"]["turas"]["reiksme"], "II")
            # Mayoral-only candidacies: the list fields are published empty.
            self.assertIsNone(payload["normalized"]["profilis"]["kita"]["sarasas"]["reiksme"])
            self.assertIsNone(payload["normalized"]["profilis"]["kita"]["numeris-sarase"]["reiksme"])

    def test_elected_note_only_for_winner(self) -> None:
        self.assertEqual(
            self.galaguz["normalized"]["profilis"]["pastaba"],
            "Išrinktas Visagino (Nr.59) savivaldybėje II ture",
        )
        self.assertIsNone(self.straupaite["normalized"]["profilis"]["pastaba"])

    def test_photo_src_is_url(self) -> None:
        photo = self.galaguz["normalized"]["profilis"]["nuotrauka"]
        self.assertIn("kandImg", photo)
        self.assertTrue(photo.startswith("https://"))

    def test_anketa_core_fields(self) -> None:
        self.assertEqual(self.galaguz["normalized"]["anketa"]["adresas"], "Visaginas")
        self.assertEqual(self.galaguz["normalized"]["anketa"]["einamos-pareigos"], "Meras")
        self.assertEqual(
            self.straupaite["normalized"]["anketa"]["einamos-pareigos"],
            "Visagino savivaldybės tarybos narė, socialinių reikalų ir sveikatos komiteto pirmininkė",
        )

    def test_anketa_membership_answer_is_inline_text(self) -> None:
        # Q8 asks for a single membership and is answered inline, so the text is
        # kept next to the (empty) record list the shared shape expects.
        naryste = self.galaguz["normalized"]["anketa"]["narystes-politinese-organizacijose"]
        self.assertEqual(naryste["tekstas"], "Visagino savivaldybės meras")
        self.assertEqual(naryste["irasai"], [])
        self.assertEqual(
            self.straupaite["normalized"]["anketa"]["narystes-politinese-organizacijose"]["tekstas"],
            '"Laisve ir Teisingumas" narė',
        )

    def test_anketa_pareiskimai_keys(self) -> None:
        pareiskimai = self.galaguz["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            list(pareiskimai.keys()),
            [
                "ar-kitos-valstybes-institucijos-narys",
                "ar-eina-nesuderinamas-pareigas",
                "ar-bendradarbiavote-su-ssrs-tarnybomis",
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-buvote-pripazintas-kaltu",
                "ar-veika-dekriminalizuota",
                "ar-buvote-pripazintas-kaltu-uzsienyje",
                "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo",
                "ar-neteko-mandato-uz-pazeidimus",
            ],
        )

    def test_spaced_question_numbers_are_answered(self) -> None:
        # Q10-Q12 are numbered "10 ." on these pages; without the tolerant
        # question-number repair their answers are dropped silently.
        for payload in (self.galaguz, self.straupaite):
            pareiskimai = payload["normalized"]["anketa"]["pareiskimai"]
            self.assertEqual(pareiskimai["ar-eina-nesuderinamas-pareigas"], "Ne")
            self.assertEqual(pareiskimai["ar-bendradarbiavote-su-ssrs-tarnybomis"], "Ne")
            self.assertEqual(pareiskimai["ar-nebaigta-teismo-paskirta-bausme"], "Ne")

    def test_no_conviction_or_mandate_loss_details(self) -> None:
        # Both candidates answered Q13 and Q14 "Ne", so the conditional blocks
        # keep the uniform empty shape.
        for payload in (self.galaguz, self.straupaite):
            self.assertEqual(
                payload["normalized"]["anketa"]["teistumo-detales"],
                {"irasai": []},
            )
            self.assertIsNone(payload["normalized"]["anketa"]["mandato-netekimo-detales"])

    def test_biografija_uses_2020_question_numbering(self) -> None:
        # Nationality is Q2 here, so education (Q3) and work history (Q5) are
        # shifted by one against the 2024 modules.
        bio = self.straupaite["normalized"]["biografija"]
        self.assertEqual(bio["gimimo-data"], "1959-02-06")
        self.assertEqual(bio["gimimo-vieta"], "Ignalinos rajonas, Dūkštas")
        self.assertEqual(bio["tautybe"], "Lietuvė")
        self.assertEqual(bio["uzsienio-kalbos"], ["Rusų", "Vokiečių"])
        self.assertEqual(bio["seimine-padetis"], "Išsiskyrusi")

    def test_biografija_blank_fields_are_blank_upstream(self) -> None:
        # Galaguz published a bare birth date (no place) and "Nenurodė" for
        # nationality; Štraupaitė answered work history with "Nenurodė".
        bio = self.galaguz["normalized"]["biografija"]
        self.assertEqual(bio["gimimo-data"], "1970-09-25")
        self.assertIsNone(bio["gimimo-vieta"])
        self.assertIsNone(bio["tautybe"])
        self.assertEqual(self.straupaite["normalized"]["biografija"]["darbo-patirtis"]["irasai"], [])

    def test_biografija_record_tables(self) -> None:
        bio = self.galaguz["normalized"]["biografija"]
        self.assertEqual(len(bio["issilavinimas"]["irasai"]), 3)
        self.assertEqual(
            bio["issilavinimas"]["irasai"][0]["mokymo-istaigos-pavadinimas"],
            "Obninsko atominės energetikos institutas",
        )
        self.assertEqual(len(bio["darbo-patirtis"]["irasai"]), 7)
        self.assertEqual(bio["darbo-patirtis"]["irasai"][0]["pareigos"], "Direktorius")

    def test_turto_ir_pajamu_normalized(self) -> None:
        # Guards the tab-body shim: these tables sit inside a <div> instead of
        # being siblings of the tab navigation.
        turtas = self.galaguz["normalized"]["turto-ir-pajamu-deklaracijos"]
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
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 218567)
        self.assertEqual(turtas["pinigines-lesos"], 18000)
        self.assertEqual(turtas["gautos-paskolos"], 52754)
        # Comma-decimal amounts parse to floats.
        self.assertEqual(turtas["gautos-pajamos"], 45856.37)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 8564.02)
        # Štraupaitė's 2021 extract declares no income at all.
        straupaite_turtas = self.straupaite["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(straupaite_turtas["privalomas-registruoti-turtas"], 35285)
        self.assertEqual(straupaite_turtas["gautos-pajamos"], 0)
        self.assertEqual(straupaite_turtas["sumoketas-pajamu-mokestis"], 0)

    def test_privaciu_interesu_declarant_hoisted(self) -> None:
        privaciu = self.galaguz["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "Erlandas GALAGUZ")
        self.assertEqual(privaciu["pateikimo-data"], "2022-12-12")
        self.assertEqual(privaciu["sutuoktinis-sugyventinis-ar-partneris"], "Viktorija GALAGUZIENĖ")
        self.assertEqual(len(privaciu["deklaruojancio-darbovietes"]), 1)
        self.assertEqual(
            privaciu["deklaruojancio-darbovietes"][0]["pavadinimas"],
            "Visagino savivaldybės administracija",
        )
        # Extra sections are keyed by their slugified title.
        self.assertEqual(len(privaciu["rysiai-su-juridiniais-asmenimis"]), 6)
        self.assertEqual(len(privaciu["rysiai-sudarius-sandorius"]), 2)
        straupaite_privaciu = self.straupaite["normalized"]["privaciu-interesu-deklaracija"]
        self.assertIsNone(straupaite_privaciu["sutuoktinis-sugyventinis-ar-partneris"])
        self.assertEqual(len(straupaite_privaciu["rysiai-su-juridiniais-asmenimis"]), 4)

    def test_kita_tab_is_empty_for_every_candidate(self) -> None:
        # Neither candidate published programme documents on the "Kita" tab.
        for payload in (self.galaguz, self.straupaite):
            self.assertEqual(payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []})


if __name__ == "__main__":
    unittest.main()
