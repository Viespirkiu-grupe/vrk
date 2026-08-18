import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.elections.prezidento_2019.anketa_parser import (
    _parse_anketa_content,
    parse_anketa_sample,
)


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


# VRK renders detail tables (with their own <th> headers) inside the anketa
# table on other 2019-era pages, e.g. the conviction-detail table for anyone
# answering the conviction question "Taip". A recursive <th> lookup in
# _is_records_table classified the whole anketa as a records table, so every
# question was dropped without an anomaly. None of the nine 2019 presidential
# candidates has such a page, so the shape is guarded synthetically here.
NESTED_DETAIL_TABLE_CONTENT = """
<div>
  <table border="0">
    <tr><td>5. Gimimo data <b>1964-05-19</b></td></tr>
    <tr><td>8.1 Ar esate Lietuvos Respublikos pilietis pagal kilmę? <b>Taip</b></td></tr>
    <tr><td>
      <table class="partydata">
        <thead><tr><th>Nuosprendžio data</th><th>Institucija</th></tr></thead>
        <tbody><tr><td>2010-01-06</td><td>Vilniaus apygardos teismas</td></tr></tbody>
      </table>
    </td></tr>
    <tr><td>11. Tautybė <b>Lietuvis</b></td></tr>
  </table>
</div>
"""


class AnketaNestedTableTests(unittest.TestCase):
    def test_a_nested_table_does_not_erase_the_anketa(self) -> None:
        content = BeautifulSoup(NESTED_DETAIL_TABLE_CONTENT, "lxml").find("div")
        parsed = _parse_anketa_content(content)

        rows_by_number = {
            row["questionNumber"]: row for row in parsed["rows"] if row["questionNumber"]
        }
        self.assertEqual(list(rows_by_number), ["5", "8.1", "11"])
        self.assertEqual(rows_by_number["8.1"]["answer"], "Taip")
        self.assertEqual(parsed["normalized"]["gimimo-data"], "1964-05-19")
        self.assertEqual(
            parsed["normalized"]["pareiskimai"]["ar-esate-pilietis-pagal-kilme"], "Taip"
        )
        self.assertEqual(parsed["normalized"]["tautybe"], "Lietuvis")

    def test_a_nested_table_is_captured_as_records(self) -> None:
        # Beyond not erasing the questionnaire, the nested detail table's own
        # content must survive: it used to die on the empty-row skip because
        # its cells carry no <b> text. It parses into a prompt-less records
        # row now, exactly as a standalone records table would.
        content = BeautifulSoup(NESTED_DETAIL_TABLE_CONTENT, "lxml").find("div")
        parsed = _parse_anketa_content(content)

        record_rows = [
            row for row in parsed["rows"] if isinstance(row["answer"], list)
        ]
        self.assertEqual(len(record_rows), 1)
        self.assertEqual(
            record_rows[0]["answer"],
            [
                {
                    "nuosprendzio-data": "2010-01-06",
                    "institucija": "Vilniaus apygardos teismas",
                }
            ],
        )


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
