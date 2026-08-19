import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.elections.ep_2019.anketa_parser import (
    _parse_anketa_content,
    parse_anketa_sample,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2019-ep"


# The conviction-detail table as the 2019 EP pages render it for anyone
# answering the conviction question "Taip" (six candidates in the full
# corpus): nested inside a row of its own, cell values wrapped in <strong>,
# columns numbered 9.2.1-9.2.4. Its cells carry no <b> text, so the bold-only
# answer extraction read nothing and the row died on the empty-row skip —
# the details reached neither rawData nor normalized. The committed fixture
# set has no declarer, so the shape is guarded synthetically.
NESTED_CONVICTION_TABLE_CONTENT = """
<div>
  <table border="0">
    <tr><td>9. Ar buvote pripažintas kaltu? <b>Taip</b></td></tr>
    <tr><td>
      <table border="1" class="partydata tableKand" id="table_apkalta">
        <thead><tr>
          <th>9.2.1 Apkaltinamojo nuosprendžio (sprendimo) data</th>
          <th>9.2.2 Apkaltinamojo nuosprendžio (sprendimo) priėmimo valstybė (vieta)</th>
        </tr></thead>
        <tbody><tr>
          <td><strong>2008</strong></td>
          <td><strong>LIETUVA</strong></td>
        </tr></tbody>
      </table>
    </td></tr>
    <tr><td>10. Tautybė <b>Lietuvis</b></td></tr>
  </table>
</div>
"""


class AnketaNestedConvictionTableTests(unittest.TestCase):
    def test_nested_conviction_table_is_captured_as_records(self) -> None:
        content = BeautifulSoup(NESTED_CONVICTION_TABLE_CONTENT, "lxml").find("div")
        parsed = _parse_anketa_content(content)

        record_rows = [
            row for row in parsed["rows"] if isinstance(row["answer"], list)
        ]
        self.assertEqual(len(record_rows), 1)
        self.assertEqual(
            record_rows[0]["answer"],
            [
                {
                    "9-2-1-apkaltinamojo-nuosprendzio-sprendimo-data": "2008",
                    "9-2-2-apkaltinamojo-nuosprendzio-sprendimo-priemimo-valstybe-vieta": "LIETUVA",
                }
            ],
        )
        # The surrounding questionnaire is intact.
        answers = {
            row["questionNumber"]: row["answer"]
            for row in parsed["rows"]
            if row["questionNumber"]
        }
        self.assertEqual(answers["9"], "Taip")
        self.assertEqual(answers["10"], "Lietuvis")


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Ep2019AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.daiva = _parse("daiva-adutaviciene")
        self.petras = _parse("petras-austrevicius")
        self.laima = _parse("laima-liucija-andrikiene")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.daiva["electionId"], "2019-ep")
        self.assertEqual(self.daiva["candidateId"], "daiva-adutaviciene")
        self.assertEqual(self.daiva["candidateName"], "Daiva ADUTAVIČIENĖ")
        self.assertTrue(
            self.daiva["source"]["candidateSourceUrl"].endswith("epKandidatasAnketa_rkndId-2415191.html")
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.daiva["normalized"].keys()),
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

    def test_profile_fields(self) -> None:
        profilis = self.daiva["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Daiva ADUTAVIČIENĖ")
        self.assertIsNone(profilis["pastaba"])
        # Base64 photos stay in rawData only (this era embeds ~1 MB each);
        # normalized keeps URL-form references, so the field is null here.
        self.assertIsNone(profilis["nuotrauka"])
        self.assertTrue(self.daiva["rawData"]["profile"]["photoSrc"].startswith("data:"))
        self.assertEqual(profilis["kita"]["sarasas"]["reiksme"], "Lietuvos žaliųjų partija")
        self.assertEqual(profilis["kita"]["numeris-sarase"]["reiksme"], "15")

    def test_elected_note_present_for_elected_mep(self) -> None:
        self.assertTrue(
            self.petras["normalized"]["profilis"]["pastaba"].startswith("Išrinktas")
        )

    def test_anketa_core_answers(self) -> None:
        anketa = self.daiva["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1964-05-26")
        self.assertEqual(anketa["gimimo-vieta"], "Vilnius")
        self.assertEqual(anketa["tautybe"], "Lietuvė")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Anglų", "Rusų"])

    def test_anketa_pareiskimai_keys(self) -> None:
        pareiskimai = self.daiva["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            set(pareiskimai.keys()),
            {
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis",
                "ar-buvote-pripazintas-kaltu",
                "ar-veika-dekriminalizuota",
                "ar-buvote-pripazintas-kaltu-uzsienyje",
                "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo",
            },
        )
        self.assertEqual(pareiskimai["ar-nebaigta-teismo-paskirta-bausme"], "Neturiu")

    def test_question_9x_answers_are_not_dropped(self) -> None:
        # EP numbers 9.1-9.5 without a trailing dot ("9.1 " not "9.1. "); the
        # question-number parser must still capture them so their answers survive
        # normalization (regression guard for silent data loss).
        pareiskimai = self.daiva["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(pareiskimai["ar-bendradarbiavote-su-uzsienio-tarnybomis"], "Ne")
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu"], "Ne")
        self.assertEqual(pareiskimai["ar-veika-dekriminalizuota"], "Ne")
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu-uzsienyje"], "Ne")
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo"], "Ne")

    def test_academic_degree_and_pedagogic_title_captured(self) -> None:
        # Q12.1 / Q12.2 are also written without a trailing dot; a candidate who
        # holds a degree must surface it rather than losing it to null.
        anketa = self.laima["normalized"]["anketa"]
        self.assertEqual(anketa["mokslo-laipsnis"], "Mokslų daktarė")
        self.assertEqual(anketa["pedagoginis-vardas"], "Docentė")

    def test_spouse_block_is_retained(self) -> None:
        # Follows the 2020 model: the declarant's spouse block stays in the
        # normalized private-interest output instead of being dropped.
        privaciu = self.daiva["normalized"]["privaciu-interesu-deklaracija"]
        spouse_key = "deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris"
        self.assertIn(spouse_key, privaciu)
        self.assertEqual(privaciu[spouse_key]["vardas"], "VIRGINIJUS")
        self.assertEqual(privaciu[spouse_key]["pavarde"], "ADUTAVIČIUS")

    def test_q19_splits_marital_status_and_spouse(self) -> None:
        anketa = self.daiva["normalized"]["anketa"]
        self.assertEqual(anketa["seimine-padetis"], "Ištekėjusi")
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Virginijus")

    def test_education_records_attached_to_question_12(self) -> None:
        irasai = self.daiva["normalized"]["anketa"]["issilavinimas"]["irasai"]
        self.assertEqual(len(irasai), 1)
        self.assertEqual(irasai[0]["mokymo-istaigos-pavadinimas"], "Vilniaus pedagoginis universitetas")
        self.assertEqual(irasai[0]["baigimo-metai"], "1987")

    def test_previously_elected_records_for_returning_mep(self) -> None:
        anksciau = self.petras["normalized"]["anketa"]["anksciau-isrinktas"]
        self.assertGreaterEqual(len(anksciau["irasai"]), 2)
        self.assertIn("institucijos-pavadinimas-pareigos", anksciau["irasai"][0])

    def test_turto_amounts(self) -> None:
        turto = self.daiva["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 100000)
        self.assertEqual(turto["gautos-pajamos"], 6570.22)
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], 578)

    def test_privaciu_declarant_and_id001j(self) -> None:
        privaciu = self.daiva["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "DAIVA ADUTAVIČIENĖ")
        self.assertEqual(len(privaciu["id001j"]), 2)
        first = privaciu["id001j"][0]
        self.assertEqual(first["juridinio-asmens-pavadinimas"], "UAB VERITAS ANA")
        self.assertEqual(first["juridinio-asmens-kodas"], "126297314")

    def test_privaciu_has_no_sekcija_fallback_keys(self) -> None:
        privaciu = self.daiva["normalized"]["privaciu-interesu-deklaracija"]
        for key in privaciu:
            self.assertFalse(key.startswith("sekcija-"), f"Unexpected fallback key: {key!r}")

    def test_biografija_is_free_text(self) -> None:
        biografija = self.daiva["normalized"]["biografija"]
        self.assertIn("tekstas", biografija)
        self.assertTrue(biografija["tekstas"].startswith("Gimė"))

    def test_campaign_section_parsed(self) -> None:
        campaigns = self.petras["normalized"]["politines-kampanijos-dalyvio-duomenys"]
        self.assertIsInstance(campaigns, list)
        self.assertGreaterEqual(len(campaigns), 1)
        self.assertEqual(campaigns[0]["statusas"], "Savarankiškas")
        self.assertIn("aukos-pagal-sekcija", campaigns[0])


if __name__ == "__main__":
    unittest.main()
