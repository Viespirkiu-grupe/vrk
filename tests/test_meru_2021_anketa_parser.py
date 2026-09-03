import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.elections.meru_2021.anketa_parser import parse_anketa_sample
from scraper.elections.seimo_2016.anketa_parser import _parse_anketa_table


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2021-spalio-10-meru"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


# An outer table with no <tbody> of its own, holding a nested detail table that
# has one. A recursive <tbody> lookup finds the nested body and collapses the
# whole anketa to that table's rows.
NESTED_DETAIL_TABLE = """
<table border="0">
  <tr><td>6. Nuolatinės gyvenamosios vietos adresas <b>Neskelbiamas</b></td></tr>
  <tr><td>9. Ar buvote pripažintas kaltu? <b>Taip</b></td></tr>
  <tr><td>9.1. Jei buvote pripažintas kaltu, privalote nurodyti:</td></tr>
  <tr><td>
    <table class="partydata tableKand">
      <thead><tr><th>9.1.1. Data:</th></tr></thead>
      <tbody><tr><td>2010-01-06</td></tr></tbody>
    </table>
  </td></tr>
  <tr><td>10. Ar bendradarbiavote? <b>Nesu</b></td></tr>
</table>
"""


class AnketaTableNestedBodyTests(unittest.TestCase):
    def test_nested_table_body_does_not_replace_the_anketa(self) -> None:
        table = BeautifulSoup(NESTED_DETAIL_TABLE, "lxml").find("table")
        parsed = _parse_anketa_table(table)

        numbers = [row["questionNumber"] for row in parsed["rows"] if row["questionNumber"]]
        self.assertEqual(numbers, ["6", "9", "9.1", "10"])


class Meru2021AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.jokubauskas = _parse("stasys-jokubauskas")
        self.petkevicius = _parse("ildefonsas-petkevicius")
        self.satevicius = _parse("andrius-satevicius")
        self.narkevicius = _parse("dainius-narkevicius")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.jokubauskas["electionId"], "2021-spalio-10-meru")
        self.assertEqual(self.jokubauskas["candidateId"], "stasys-jokubauskas")
        self.assertEqual(self.jokubauskas["candidateName"], "Stasys JOKUBAUSKAS")
        self.assertTrue(
            self.jokubauskas["source"]["candidateSourceUrl"].endswith(
                "savKandidatasAnketa_rkndId-2420406.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.jokubauskas["normalized"].keys()),
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
        profilis = self.jokubauskas["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "STASYS JOKUBAUSKAS")
        # The page links the portrait (a kandImg URL, unlike the base64 data
        # URIs of the 2017 pages); the record carries the archived sidecar and
        # photoMeta remembers the URL it came from (issue #118).
        self.assertEqual(profilis["nuotrauka"], f"photos/{self.jokubauskas['candidateId']}.jpg")
        self.assertIn("kandImg", self.jokubauskas["rawData"]["profile"]["photoMeta"]["url"])

        kita = profilis["kita"]
        self.assertEqual(kita["savivaldybe"]["reiksme"], "Kelmės rajono (18)")
        self.assertEqual(
            kita["iskele-i-tarybos-narius-merus"]["reiksme"], "Lietuvos socialdemokratų partija"
        )
        self.assertEqual(kita["turas"]["reiksme"], "II")
        self.assertEqual(
            self.petkevicius["normalized"]["profilis"]["kita"][
                "iskele-i-tarybos-narius-merus"
            ]["reiksme"],
            "išsikėlė pats",
        )

    def test_elected_notes(self) -> None:
        # One mayor elected in each of the two municipalities.
        self.assertEqual(
            self.petkevicius["normalized"]["profilis"]["pastaba"],
            "Išrinktas Kelmės rajono (Nr.18) savivaldybėje II ture",
        )
        self.assertEqual(
            self.satevicius["normalized"]["profilis"]["pastaba"],
            "Išrinktas Trakų rajono (Nr.52) savivaldybėje II ture",
        )
        self.assertIsNone(self.jokubauskas["normalized"]["profilis"]["pastaba"])

    def test_anketa_top_level_keys(self) -> None:
        self.assertEqual(
            list(self.jokubauskas["normalized"]["anketa"].keys()),
            [
                "adresas",
                "kontaktai",
                "einamos-pareigos",
                "narystes-politinese-organizacijose",
                "pareiskimai",
                "teistumo-detales",
            ],
        )

    def test_contact_questions_captured(self) -> None:
        anketa = self.jokubauskas["normalized"]["anketa"]
        self.assertEqual(anketa["adresas"], "Neskelbiamas")
        self.assertEqual(
            anketa["kontaktai"],
            {
                "telefonas": "Neskelbiamas",
                "el-pastas": "Neskelbiamas",
                "socialiniu-tinklu-paskyros": "Facebook",
            },
        )

    def test_membership_question_survives_its_missing_dot(self) -> None:
        # "7.1 Narystė partijoje, asociacijose" has no dot after the number, so
        # the strict pattern reads it as question "7" — the position question —
        # and the membership answer is lost.
        anketa = self.jokubauskas["normalized"]["anketa"]
        self.assertEqual(
            anketa["einamos-pareigos"], "Kelmės r. savivaldybės administracijos direktorius"
        )
        self.assertEqual(
            anketa["narystes-politinese-organizacijose"]["tekstas"],
            "LSDP Kelmės skyriaus pirmininkas",
        )

    def test_anketa_pareiskimai_keys(self) -> None:
        pareiskimai = self.jokubauskas["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            list(pareiskimai.keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-eina-nesuderinamas-pareigas",
                "ar-kitos-valstybes-institucijos-narys",
                "ar-buvote-pripazintas-kaltu",
                "ar-veika-dekriminalizuota",
                "ar-buvote-pripazintas-kaltu-uzsienyje",
                "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo",
                "ar-bendradarbiavote-su-ssrs-tarnybomis",
            ],
        )
        for payload in (self.jokubauskas, self.petkevicius, self.satevicius, self.narkevicius):
            with self.subTest(candidate=payload["candidateId"]):
                values = payload["normalized"]["anketa"]["pareiskimai"].values()
                self.assertTrue(all(value is not None for value in values))

    def test_conviction_record(self) -> None:
        # Narkevičius is the only candidate who answered Q9 "Taip"; his
        # conviction table is the nested one that used to swallow the anketa.
        anketa = self.narkevicius["normalized"]["anketa"]
        self.assertEqual(anketa["pareiskimai"]["ar-buvote-pripazintas-kaltu"], "Taip")
        self.assertEqual(
            anketa["teistumo-detales"]["irasai"],
            [
                {
                    "nuosprendzio-data": "2010-01-06",
                    "nuosprendzio-valstybe": "Lietuva",
                    "nuosprendzio-institucija": "Vilniaus apygardos teismas",
                    "nusikalstama-veika": "LR BK 228 str. 1 d.",
                }
            ],
        )
        self.assertEqual(self.jokubauskas["normalized"]["anketa"]["teistumo-detales"]["irasai"], [])

    def test_biografija_uses_2023_question_numbering(self) -> None:
        bio = self.jokubauskas["normalized"]["biografija"]
        self.assertEqual(bio["gimimo-data"], "1962-04-26")
        self.assertEqual(bio["tautybe"], "Lietuvis")
        self.assertEqual(bio["uzsienio-kalbos"], ["Rusų", "Vokiečių"])
        self.assertEqual(len(bio["issilavinimas"]["irasai"]), 3)
        self.assertEqual(
            bio["issilavinimas"]["irasai"][0]["mokymo-istaigos-pavadinimas"],
            "Šiaulių K. Preikšo pedagoginis institutas",
        )

    def test_turto_ir_pajamu_normalized(self) -> None:
        turtas = self.jokubauskas["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 41300)
        self.assertEqual(turtas["pinigines-lesos"], 4876)
        self.assertEqual(turtas["gautos-paskolos"], 1000)
        self.assertEqual(turtas["gautos-pajamos"], 39429.3)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 7885.86)

    def test_privaciu_interesu_declarant_hoisted(self) -> None:
        privaciu = self.jokubauskas["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "Stasys JOKUBAUSKAS")
        self.assertEqual(privaciu["pateikimo-data"], "2021-07-15")
        self.assertTrue(privaciu["deklaruojancio-darbovietes"])

    def test_campaign_data(self) -> None:
        campaign = self.jokubauskas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["registravimo-data"], "2021-07-15")

        donations = campaign["aukos-pagal-sekcija"]["gautos-ir-priimtos-aukos"]
        self.assertEqual(len(donations["records"]), 4)
        self.assertEqual(donations["totals"]["is-viso"], 7049.05)

    def test_kita_tab_is_empty_for_every_candidate(self) -> None:
        for payload in (self.jokubauskas, self.petkevicius, self.satevicius, self.narkevicius):
            self.assertEqual(payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []})


if __name__ == "__main__":
    unittest.main()
