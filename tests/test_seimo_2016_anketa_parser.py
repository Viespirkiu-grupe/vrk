import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2016.anketa_parser import (
    _normalize_anketa_rows,
    _question_record_rows,
    parse_anketa_sample,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2016-seimo"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class QuestionRecordRowsTests(unittest.TestCase):
    """A record table sits either inside its question's row or in the row after it."""

    def test_table_inside_the_question_row(self) -> None:
        rows = [
            {"questionNumber": "12", "prompt": "12. Išsilavinimas", "answer": [{"a": "1"}]},
            {"questionNumber": "13", "prompt": "13. Kalbos", "answer": "Anglų"},
        ]
        self.assertEqual(_question_record_rows(rows, "12"), [{"a": "1"}])

    def test_table_in_the_row_after_the_question(self) -> None:
        rows = [
            {"questionNumber": "15", "prompt": "15. Ar buvote išrinktas", "answer": ""},
            {"questionNumber": None, "prompt": "", "answer": [{"a": "1"}, {"a": "2"}]},
            {"questionNumber": "16", "prompt": "16. Darbovietė", "answer": "X"},
        ]
        self.assertEqual(_question_record_rows(rows, "15"), [{"a": "1"}, {"a": "2"}])

    def test_following_text_row_does_not_extend_the_table(self) -> None:
        rows = [
            {"questionNumber": "12", "prompt": "12. Išsilavinimas", "answer": ""},
            {"questionNumber": None, "prompt": "Jei turite, nurodykite", "answer": "Nenurodė"},
        ]
        self.assertEqual(_question_record_rows(rows, "12"), [])

    def test_missing_question_yields_nothing(self) -> None:
        self.assertEqual(_question_record_rows([], "15"), [])


class Seimo2016AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agne = _parse("agne-sirinskiene")
        self.ingrida = _parse("ingrida-simonyte")
        self.regina = _parse("regina-ablom")
        self.algirdas = _parse("algirdas-butkevicius")
        self.gabrielius = _parse("gabrielius-landsbergis")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.agne["electionId"], "2016-seimo")
        self.assertEqual(self.agne["candidateId"], "agne-sirinskiene")
        self.assertEqual(self.agne["candidateName"], "Agnė ŠIRINSKIENĖ")
        self.assertTrue(
            self.agne["source"]["candidateSourceUrl"].endswith(
                "lrsKandidatasAnketa_rkndId-1102466.html"
            )
        )

    def test_profile_card_fields(self) -> None:
        profilis = self.agne["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "AGNĖ ŠIRINSKIENĖ")
        # The embedded photo is externalized to a sidecar file; both photo
        # fields carry the relative path and photoMeta keeps the hash.
        self.assertEqual(profilis["nuotrauka"], "photos/agne-sirinskiene.jpg")
        self.assertEqual(self.agne["rawData"]["profile"]["photoSrc"], "photos/agne-sirinskiene.jpg")
        self.assertGreater(self.agne["rawData"]["profile"]["photoMeta"]["bytes"], 0)

    def test_elected_note_variants(self) -> None:
        # List seat, single-member seat won in each round, and no seat at all.
        self.assertEqual(
            self.agne["normalized"]["profilis"]["pastaba"],
            "Išrinkta pagal Lietuvos valstiečių ir žaliųjų sajungos sąrašą",
        )
        self.assertEqual(
            self.ingrida["normalized"]["profilis"]["pastaba"],
            "Išrinkta vienmandatėje Antakalnio (Nr.3) apygardoje I ture",
        )
        self.assertEqual(
            self.gabrielius["normalized"]["profilis"]["pastaba"],
            "Išrinktas vienmandatėje Centro-Žaliakalnio (Nr.13) apygardoje II ture",
        )
        self.assertIsNone(self.regina["normalized"]["profilis"]["pastaba"])

    def test_anketa_top_level_keys(self) -> None:
        # The 2016 questionnaire is the largest of the elections: the biography
        # questions (Q10-Q21) live on the anketa itself rather than on a
        # separate tab, so they are part of this section.
        self.assertEqual(
            list(self.agne["normalized"]["anketa"].keys()),
            [
                "gimimo-data",
                "adresas",
                "pareiskimai",
                "teistumo-detales",
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
        anketa = self.agne["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1975-11-09")
        self.assertEqual(anketa["adresas"], "Ignalinos r. sav., Dūkštas")
        self.assertEqual(anketa["gimimo-vieta"], "Vilnius")
        self.assertEqual(anketa["tautybe"], "Lietuvė")
        self.assertEqual(anketa["pagrindine-darboviete"], "Mykolo Romerio universitetas, docentė")
        self.assertEqual(anketa["pomegiai"], "skaitymas, siuvinėjimas, rožių auginimas")
        self.assertEqual(anketa["seimine-padetis"], "Ištekėjusi")

    def test_anketa_pareiskimai_keys(self) -> None:
        pareiskimai = self.agne["normalized"]["anketa"]["pareiskimai"]
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

    def test_declarations_are_answered(self) -> None:
        # Q8.1-Q8.4 and Q9.1-Q9.3.3 are always answered; Q9.3.4 is the free-text
        # justification, filled only when Q9.2 is "Taip".
        for payload in (self.agne, self.ingrida, self.regina, self.algirdas, self.gabrielius):
            pareiskimai = payload["normalized"]["anketa"]["pareiskimai"]
            with self.subTest(candidate=payload["candidateId"]):
                answered = {
                    key: value for key, value in pareiskimai.items() if key != "teisiniai-argumentai"
                }
                self.assertTrue(all(value == "Ne" for value in answered.values()))
                self.assertIsNone(pareiskimai["teisiniai-argumentai"])

    def test_conviction_details_are_normalized(self) -> None:
        # Q9.2's "Taip" is followed by a table itemizing each conviction, which
        # reached rawData from the start and was normalized nowhere until issue
        # #86 — the corpus could say that 38 candidates of this election were
        # found guilty and nothing about what for. No fixture candidate is a
        # declarer (five of the election's 1,417), so the shape is guarded on
        # the rows the parse produces for one.
        rows = [
            {"rowIndex": 10, "questionNumber": "9.2", "prompt": "9.2. Ar buvote ...", "answer": "Taip"},
            {
                "rowIndex": 12,
                "questionNumber": None,
                "prompt": "",
                "answer": [
                    {
                        "9.2.1. Apkaltinamojo nuosprendžio (sprendimo) data": "2008-06-04",
                        "9.2.2. Apkaltinamojo nuosprendžio (sprendimo) priėmimo valstybė (vieta)": "Lietuva",
                        "9.2.3. Nuosprendį (sprendimą) priėmusios institucijos pavadinimas": "Ukmergės rajono apylinkės teismas",
                        "9.2.4. Nusikalstama veika, už kurią buvote nuteistas (pavadinimas)": "BK 178 str. 1 d.",
                    },
                    {
                        "9.2.1. Apkaltinamojo nuosprendžio (sprendimo) data": "1999-08-25",
                        "9.2.2. Apkaltinamojo nuosprendžio (sprendimo) priėmimo valstybė (vieta)": "Lietuva",
                        "9.2.3. Nuosprendį (sprendimą) priėmusios institucijos pavadinimas": "Ukmergės rajono apylinkės teismas",
                        "9.2.4. Nusikalstama veika, už kurią buvote nuteistas (pavadinimas)": "BK 310 str. 3 d.",
                    },
                ],
            },
            {"rowIndex": 13, "questionNumber": "9.3", "prompt": "9.3. ...", "answer": ""},
        ]
        self.assertEqual(
            _normalize_anketa_rows(rows)["teistumo-detales"],
            {
                "irasai": [
                    {
                        "nuosprendzio-data": "2008-06-04",
                        "nuosprendzio-valstybe": "Lietuva",
                        "nuosprendzio-institucija": "Ukmergės rajono apylinkės teismas",
                        "nusikalstama-veika": "BK 178 str. 1 d.",
                    },
                    {
                        "nuosprendzio-data": "1999-08-25",
                        "nuosprendzio-valstybe": "Lietuva",
                        "nuosprendzio-institucija": "Ukmergės rajono apylinkės teismas",
                        "nusikalstama-veika": "BK 310 str. 3 d.",
                    },
                ]
            },
        )

    def test_every_candidate_carries_the_conviction_key(self) -> None:
        # Present on every record, as in the 2019/2021/2023 elections, so
        # "no conviction declared" and "this election does not publish the
        # block" stay distinguishable.
        for payload in (self.agne, self.ingrida, self.regina, self.algirdas, self.gabrielius):
            with self.subTest(candidate=payload["candidateId"]):
                anketa = payload["normalized"]["anketa"]
                self.assertEqual(anketa["teistumo-detales"], {"irasai": []})

    def test_education_records(self) -> None:
        issilavinimas = self.agne["normalized"]["anketa"]["issilavinimas"]
        self.assertEqual(len(issilavinimas["irasai"]), 5)
        self.assertEqual(
            issilavinimas["irasai"][0]["mokymo-istaigos-pavadinimas"],
            "Vytauto Didžiojo universitetas",
        )
        self.assertEqual(issilavinimas["irasai"][0]["baigimo-metai"], "1998")
        self.assertEqual(
            self.ingrida["normalized"]["anketa"]["issilavinimas"]["irasai"][0]["specialybe"],
            "ekonomika",
        )

    def test_prior_mandate_table_rendered_in_its_own_row(self) -> None:
        # Landsbergis's mandate table is rendered after the Q15 row rather than
        # inside it; reading only the question row drops it.
        mandates = self.gabrielius["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"]
        self.assertEqual(
            mandates,
            [
                {
                    "institucijos-pavadinimas-pareigos": "Europos Parlamentas, narys",
                    "laikotarpis": "2014 - 2016",
                }
            ],
        )
        # Candidates who answered "Nenurodė" still yield nothing.
        self.assertEqual(
            self.agne["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"], []
        )

    def test_unnumbered_rows_matched_by_prompt(self) -> None:
        # The pedagogic title and the spouse name are rendered as rows without a
        # question number, so they are matched on their prompt text instead.
        anketa = self.agne["normalized"]["anketa"]
        self.assertEqual(
            anketa["pedagoginis-vardas"],
            "docentė humanitarinių mokslų srities (02H) daktarė",
        )
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Arvydas Širinskas")
        self.assertEqual(
            self.regina["normalized"]["anketa"]["sutuoktinio-vardas-pavarde"], "Bronislav Ablom"
        )
        self.assertEqual(self.gabrielius["normalized"]["anketa"]["pedagoginis-vardas"], "magistras")

    def test_languages_split_into_list(self) -> None:
        self.assertEqual(
            self.agne["normalized"]["anketa"]["uzsienio-kalbos"],
            ["Anglų", "Rusų", "Prancūzų", "Italų", "Lotynų"],
        )
        self.assertEqual(
            self.regina["normalized"]["anketa"]["uzsienio-kalbos"], ["Rusų", "Vokiečių"]
        )

    def test_nenurode_answers_normalize_to_null(self) -> None:
        # Butkevičius answered every optional question "Nenurodė".
        anketa = self.algirdas["normalized"]["anketa"]
        self.assertEqual(anketa["adresas"], "Vilnius")
        self.assertIsNone(anketa["gimimo-vieta"])
        self.assertIsNone(anketa["tautybe"])
        self.assertIsNone(anketa["pagrindine-darboviete"])
        self.assertIsNone(anketa["seimine-padetis"])
        self.assertIsNone(anketa["kita-apie-save"])
        self.assertEqual(anketa["uzsienio-kalbos"], [])
        self.assertEqual(anketa["issilavinimas"]["irasai"], [])

    def test_raw_rows_keep_every_question(self) -> None:
        numbers = [
            row["questionNumber"]
            for row in self.agne["rawData"]["anketa"]["rows"]
            if row["questionNumber"]
        ]
        self.assertEqual(
            numbers,
            ["5", "6", "8", "8.1", "8.2", "8.3", "8.4", "9", "9.1", "9.2", "9.3",
             "9.3.1", "9.3.2", "9.3.3", "9.3.4", "10", "11", "12", "13", "14",
             "15", "16", "17", "18", "19", "20", "21"],
        )


if __name__ == "__main__":
    unittest.main()
