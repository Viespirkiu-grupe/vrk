import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.radviliskio_mero_2021.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2021-balandzio-11-radviliskio-mero"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class RadviliskioMero2021AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.simelis = _parse("vytautas-simelis")
        self.lipnevicius = _parse("gediminas-lipnevicius")
        self.margaitiene = _parse("jolanta-margaitiene")
        self.reutas = _parse("mantas-reutas")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.simelis["electionId"], "2021-balandzio-11-radviliskio-mero")
        self.assertEqual(self.simelis["candidateId"], "vytautas-simelis")
        self.assertEqual(self.simelis["candidateName"], "Vytautas SIMELIS")
        self.assertTrue(
            self.simelis["source"]["candidateSourceUrl"].endswith(
                "savKandidatasAnketa_rkndId-2420390.html"
            )
        )

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.simelis["normalized"].keys()),
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
        profilis = self.simelis["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "VYTAUTAS SIMELIS")
        self.assertIn("kandImg", profilis["nuotrauka"])

        kita = profilis["kita"]
        self.assertEqual(kita["savivaldybe"]["reiksme"], "Radviliškio rajono (37)")
        self.assertEqual(
            kita["iskele-i-tarybos-narius-merus"]["reiksme"], "Lietuvos žaliųjų partija"
        )
        self.assertEqual(kita["turas"]["reiksme"], "II")
        self.assertEqual(
            self.lipnevicius["normalized"]["profilis"]["kita"][
                "iskele-i-tarybos-narius-merus"
            ]["reiksme"],
            "išsikėlė pats",
        )

    def test_elected_note_only_for_the_winner(self) -> None:
        self.assertEqual(
            self.simelis["normalized"]["profilis"]["pastaba"],
            "Išrinktas Radviliškio rajono (Nr.37) savivaldybėje II ture",
        )
        self.assertIsNone(self.reutas["normalized"]["profilis"]["pastaba"])

    def test_anketa_top_level_keys(self) -> None:
        self.assertEqual(
            list(self.simelis["normalized"]["anketa"].keys()),
            [
                "adresas",
                "kontaktai",
                "einamos-pareigos",
                "narystes-politinese-organizacijose",
                "pareiskimai",
                "teistumo-detales",
            ],
        )

    def test_contact_and_membership_questions(self) -> None:
        # Q7.1 carries no dot after its number; the strict pattern reads it as
        # the position question and the membership answer is lost.
        anketa = self.lipnevicius["normalized"]["anketa"]
        self.assertEqual(anketa["einamos-pareigos"], "Direktorius")
        self.assertTrue(
            anketa["narystes-politinese-organizacijose"]["tekstas"].startswith(
                "Radviliškio krašto bendruomenės pirmininkas"
            )
        )
        self.assertEqual(
            anketa["kontaktai"]["socialiniu-tinklu-paskyros"], "Gediminas Lipnevičius"
        )

    def test_declarations(self) -> None:
        pareiskimai = self.simelis["normalized"]["anketa"]["pareiskimai"]
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
        # Every candidate answered "Nenurodė" to Q10, which normalizes to null;
        # the rest are answered.
        for payload in (self.simelis, self.lipnevicius, self.margaitiene, self.reutas):
            with self.subTest(candidate=payload["candidateId"]):
                answers = payload["normalized"]["anketa"]["pareiskimai"]
                self.assertIsNone(answers["ar-bendradarbiavote-su-ssrs-tarnybomis"])
                self.assertTrue(
                    all(
                        value is not None
                        for key, value in answers.items()
                        if key != "ar-bendradarbiavote-su-ssrs-tarnybomis"
                    )
                )

    def test_conviction_record(self) -> None:
        # Lipnevičius is the only candidate who answered Q9 "Taip". His record
        # lives in a nested table, which is only reachable because the anketa
        # parser takes the outer table's own <tbody>.
        anketa = self.lipnevicius["normalized"]["anketa"]
        self.assertEqual(anketa["pareiskimai"]["ar-buvote-pripazintas-kaltu"], "Taip")
        self.assertEqual(
            anketa["teistumo-detales"]["irasai"],
            [
                {
                    "nuosprendzio-data": "1993-05-31",
                    "nuosprendzio-valstybe": "Lietuva",
                    "nuosprendzio-institucija": "Radviliškio rajono apylinkės teismas",
                    "nusikalstama-veika": "Pagal LR baudžiamojo kodekso (1961 m. redakcija) 90 str. 2 d.",
                }
            ],
        )
        self.assertEqual(self.simelis["normalized"]["anketa"]["teistumo-detales"]["irasai"], [])

    def test_biografija(self) -> None:
        bio = self.simelis["normalized"]["biografija"]
        self.assertEqual(bio["gimimo-data"], "1957-09-28")
        self.assertEqual(bio["gimimo-vieta"], "Radviliškis, Lietuva")
        self.assertEqual(bio["tautybe"], "Lietuvis")
        self.assertEqual(bio["uzsienio-kalbos"], ["Anglų", "Rusų"])
        self.assertEqual(
            bio["issilavinimas"]["irasai"][0]["mokymo-istaigos-pavadinimas"],
            "Šiaulių universitetas",
        )
        self.assertEqual(len(bio["darbo-patirtis"]["irasai"]), 15)

    def test_turto_ir_pajamu_normalized(self) -> None:
        turtas = self.margaitiene["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 88303)
        self.assertEqual(turtas["pinigines-lesos"], 6422)
        self.assertEqual(turtas["gautos-paskolos"], 62408)
        self.assertEqual(turtas["gautos-pajamos"], 47285.16)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 9340.37)

    def test_privaciu_interesu_sections(self) -> None:
        privaciu = self.margaitiene["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "Jolanta MARGAITIENĖ")
        self.assertTrue(privaciu["deklaruojancio-darbovietes"])
        self.assertIn("rysiai-sudarius-sandorius", privaciu)

    def test_campaign_data(self) -> None:
        campaign = self.margaitiene["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["registravimo-data"], "2021-01-14")

        donations = campaign["aukos-pagal-sekcija"]["gautos-ir-priimtos-aukos"]
        self.assertEqual(len(donations["records"]), 10)
        self.assertEqual(donations["totals"]["is-viso"], 13414.8)

        # Party-represented participants publish no donations of their own.
        self.assertEqual(
            self.reutas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Atstovaujamasis",
        )

    def test_kita_tab_documents(self) -> None:
        # The first election in the repository whose "Kita" tab carries a
        # document: Lipnevičius published a signed pledge not to bribe voters.
        kita = self.lipnevicius["normalized"]["kita"]
        self.assertEqual(
            kita["tekstai"], ["Pasižadėjimas laikytis draudimo papirkti rinkėjus.jpg"]
        )
        self.assertEqual(len(kita["nuorodos"]), 1)
        self.assertIn("kpdFileDownload", kita["nuorodos"][0])

        # Everyone else published nothing there.
        for payload in (self.simelis, self.margaitiene, self.reutas):
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []}
                )


if __name__ == "__main__":
    unittest.main()
