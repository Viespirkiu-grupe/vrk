import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2020.anketa_parser import (
    _normalize_anketa_rows,
    parse_anketa_sample,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2020-seimo"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Seimo2020AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agne = _parse("agne-sirinskiene")
        self.gabrielius = _parse("gabrielius-landsbergis")
        self.regina = _parse("regina-ablom")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.agne["electionId"], "2020-seimo")
        self.assertEqual(self.agne["candidateId"], "agne-sirinskiene")
        self.assertEqual(self.agne["candidateName"], "Agnė ŠIRINSKIENĖ")

    def test_profile_card_fields(self) -> None:
        # 2020 pages keep the 2016-era profile card.
        profilis = self.agne["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "Agnė ŠIRINSKIENĖ")
        self.assertTrue(profilis["nuotrauka"])

    def test_anketa_top_level_keys(self) -> None:
        # The 2020 questionnaire has no birth/education/hobby questions — those
        # live on the biography tab — so the anketa must not carry the 2016
        # question set's keys.
        anketa = self.agne["normalized"]["anketa"]
        self.assertEqual(
            list(anketa.keys()),
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
        # Q6.1-Q6.3 are separate rows under the address question.
        kontaktai = self.agne["normalized"]["anketa"]["kontaktai"]
        self.assertEqual(self.agne["normalized"]["anketa"]["adresas"], "Neskelbiamas")
        self.assertEqual(kontaktai["telefonas"], "Neskelbiamas")
        self.assertEqual(kontaktai["el-pastas"], "Neskelbiamas")
        self.assertEqual(
            kontaktai["socialiniu-tinklu-paskyros"],
            "https://www.facebook.com/profile.php?id=100012505354591",
        )

    def test_position_and_membership_captured(self) -> None:
        # Q7 / Q7.1 have no 2016 counterpart under the same number.
        anketa = self.agne["normalized"]["anketa"]
        self.assertEqual(anketa["einamos-pareigos"], "Seimo narė")
        self.assertEqual(
            anketa["narystes-politinese-organizacijose"]["tekstas"],
            "Lietuvos valstiečių ir žaliųjų sąjungos narė",
        )
        self.assertEqual(
            self.gabrielius["normalized"]["anketa"]["narystes-politinese-organizacijose"]["tekstas"],
            "TS-LKD partijos pirmininkas",
        )
        self.assertEqual(
            self.regina["normalized"]["anketa"]["einamos-pareigos"],
            "Direktoriaus pavaduotoja ugdymui",
        )

    def test_anketa_pareiskimai_keys(self) -> None:
        pareiskimai = self.agne["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(
            list(pareiskimai.keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-savanoriskos-karo-tarnybos-karys",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-susijes-priesaika-uzsienio-valstybei",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis",
                "ar-buvote-pripazintas-kaltu",
                "ar-veika-dekriminalizuota",
                "ar-buvote-pripazintas-kaltu-uzsienyje",
                "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo",
            ],
        )

    def test_all_declarations_are_answered(self) -> None:
        # Q8.2.1 and Q9.3-Q9.5 are numbered differently than in 2016; looking up
        # the 2016 numbers leaves them null on every 2020 page.
        for payload in (self.agne, self.gabrielius, self.regina):
            pareiskimai = payload["normalized"]["anketa"]["pareiskimai"]
            with self.subTest(candidate=payload["candidateId"]):
                self.assertTrue(all(value is not None for value in pareiskimai.values()))

    def test_declaration_answers(self) -> None:
        pareiskimai = self.agne["normalized"]["anketa"]["pareiskimai"]
        self.assertEqual(pareiskimai["ar-nebaigta-teismo-paskirta-bausme"], "Neturiu")
        self.assertEqual(pareiskimai["ar-atliekate-karo-tarnyba"], "Nesu")
        self.assertEqual(pareiskimai["ar-savanoriskos-karo-tarnybos-karys"], "Nesu")
        self.assertEqual(pareiskimai["ar-turite-kitos-valstybes-pilietybe"], "Nesu/nebuvau")
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu"], "Ne")
        self.assertEqual(pareiskimai["ar-veika-dekriminalizuota"], "Ne")
        self.assertEqual(pareiskimai["ar-buvote-pripazintas-kaltu-uzsienyje"], "Ne")
        self.assertEqual(
            pareiskimai["ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo"], "Ne"
        )

    def test_conviction_details_are_normalized(self) -> None:
        # These pages print the block's lead-in ("Jeigu buvote pripažintas
        # kaltu, privalote nurodyti") as an unnumbered row between Q9.2 and its
        # table, so a collector that stops at the first non-table row finds
        # nothing — which is why all 41 declarers of this election had a yes/no
        # answer and no details until issue #86. No fixture candidate is a
        # declarer, so the shape is guarded on the rows the parse produces.
        rows = [
            {"rowIndex": 15, "questionNumber": "9.2", "prompt": "9.2. Ar po 1990-03-11 ...", "answer": "Taip"},
            {
                "rowIndex": 16,
                "questionNumber": None,
                "prompt": "Jeigu buvote pripažintas kaltu, privalote nurodyti (dėl kiekvieno nuosprendžio atskirai):",
                "answer": "",
            },
            {
                "rowIndex": 17,
                "questionNumber": None,
                "prompt": "",
                "answer": [
                    {
                        "9.2.1. Apkaltinamojo nuosprendžio (sprendimo) data:": "2015",
                        "9.2.2. Apkaltinamojo nuosprendžio (sprendimo) priėmimo valstybė (vieta):": "LIETUVA",
                        "9.2.3. Nuosprendį (sprendimą) priėmusios institucijos pavadinimas:": "Vilniaus apygardos teismas",
                        "9.2.4. Nusikalstama veika, už kurią buvote nuteistas (pavadinimas)": "Šmeižtas",
                    }
                ],
            },
            {"rowIndex": 18, "questionNumber": "9.3", "prompt": "9.3. ...", "answer": "Ne"},
        ]
        self.assertEqual(
            _normalize_anketa_rows(rows)["teistumo-detales"],
            {
                "irasai": [
                    {
                        "nuosprendzio-data": "2015",
                        "nuosprendzio-valstybe": "LIETUVA",
                        "nuosprendzio-institucija": "Vilniaus apygardos teismas",
                        "nusikalstama-veika": "Šmeižtas",
                    }
                ]
            },
        )

    def test_every_candidate_carries_the_conviction_key(self) -> None:
        for payload in (self.agne, self.gabrielius, self.regina):
            with self.subTest(candidate=payload["candidateId"]):
                anketa = payload["normalized"]["anketa"]
                self.assertEqual(anketa["teistumo-detales"], {"irasai": []})

    def test_raw_rows_keep_every_question(self) -> None:
        rows = self.agne["rawData"]["anketa"]["rows"]
        numbers = [row["questionNumber"] for row in rows if row["questionNumber"]]
        self.assertEqual(
            numbers,
            ["6", "6.1", "6.2", "6.3", "7", "7.1", "8", "8.1", "8.2", "8.2.1", "8.3", "8.4",
             "9", "9.1", "9.2", "9.3", "9.4", "9.5"],
        )


if __name__ == "__main__":
    unittest.main()
