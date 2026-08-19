import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.meru_2025.anketa_parser import parse_anketa_sample
from scraper.elections.meru_2025.sitemap import clean_candidate_name, extract_candidate_note


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2025-kovo-16-meru"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Meru2025SitemapNameTests(unittest.TestCase):
    def test_status_note_is_split_from_the_name(self) -> None:
        for raw, name, note in (
            ("Povilas BEIŠYS(išbrauktas - Seimo nutarimu)", "Povilas BEIŠYS", "išbrauktas - Seimo nutarimu"),
            ("Jolita PELECKIENĖ(išbraukta - Seimo nutarimu)", "Jolita PELECKIENĖ", "išbraukta - Seimo nutarimu"),
            ("Gediminas ČEPULIS", "Gediminas ČEPULIS", ""),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(clean_candidate_name(raw), name)
                self.assertEqual(extract_candidate_note(raw), note)


class Meru2025AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cepulis = _parse("gediminas-cepulis")
        self.masiliuniene = _parse("loreta-masiliuniene")
        self.beisys = _parse("povilas-beisys")
        self.gaiziunas = _parse("ignas-gaiziunas")

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.cepulis["electionId"], "2025-kovo-16-meru")
        self.assertEqual(self.cepulis["candidateId"], "gediminas-cepulis")
        self.assertEqual(self.cepulis["candidateName"], "Gediminas ČEPULIS")
        self.assertTrue(
            self.cepulis["source"]["candidateSourceUrl"].endswith(
                "KandidatasAnketa_rkndId-2437791.html"
            )
        )

    def test_struck_off_candidates_keep_their_status_note(self) -> None:
        # Only the listing records this; the candidate page leaves the line of
        # the profile card that would carry it blank.
        self.assertEqual(self.beisys["candidateNote"], "išbrauktas - Seimo nutarimu")
        self.assertEqual(self.beisys["candidateName"], "Povilas BEIŠYS")
        self.assertIsNone(self.cepulis["candidateNote"])

    def test_normalized_section_order(self) -> None:
        self.assertEqual(
            list(self.cepulis["normalized"].keys()),
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

    def test_struck_off_candidates_have_no_campaign_section(self) -> None:
        # Struck-off candidates publish five tabs instead of six.
        self.assertEqual(
            list(self.beisys["normalized"].keys()),
            [
                "profilis",
                "anketa",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
                "privaciu-interesu-deklaracija",
                "kita",
            ],
        )
        self.assertNotIn("politinesKampanijosDalyvioDuomenys", self.beisys["rawData"])

    def test_profile_municipal_fields(self) -> None:
        profilis = self.cepulis["normalized"]["profilis"]
        self.assertEqual(profilis["vardas-pavarde"], "GEDIMINAS ČEPULIS")
        self.assertIn("kandImg", profilis["nuotrauka"])

        kita = profilis["kita"]
        self.assertEqual(kita["savivaldybe"]["reiksme"], "Joniškio rajono (11)")
        self.assertEqual(kita["iskele-i-savivaldybes-merus"]["reiksme"], "Liberalų sąjūdis")
        self.assertEqual(kita["turas"]["reiksme"], "II")
        self.assertEqual(
            self.beisys["normalized"]["profilis"]["kita"]["savivaldybe"]["reiksme"],
            "Jonavos rajono (10)",
        )

    def test_elected_notes(self) -> None:
        # One mayor elected in each of the two municipalities that voted; the
        # Jonava race had every candidate struck off.
        self.assertEqual(
            self.cepulis["normalized"]["profilis"]["pastaba"],
            "Išrinktas Joniškio rajono (Nr.11) savivaldybėje II ture",
        )
        self.assertEqual(
            self.masiliuniene["normalized"]["profilis"]["pastaba"],
            "Išrinkta Panevėžio miesto (Nr.32) savivaldybėje II ture",
        )
        self.assertIsNone(self.beisys["normalized"]["profilis"]["pastaba"])

    def test_anketa_core_fields(self) -> None:
        anketa = self.cepulis["normalized"]["anketa"]
        self.assertEqual(anketa["adresas"], "Joniškio r. sav.")
        self.assertEqual(
            anketa["einamos-pareigos"],
            "Laikinai einantis mero pareigas tarybos narys, Joniškio rajono savivaldybė",
        )

    def test_anketa_membership_is_a_record_table(self) -> None:
        # Unlike the 2023 mayoral pages, Q8 is answered with the 2024-style
        # membership table rather than inline text.
        naryste = self.cepulis["normalized"]["anketa"]["narystes-politinese-organizacijose"]
        self.assertEqual(list(naryste.keys()), ["irasai"])
        self.assertEqual(len(naryste["irasai"]), 1)
        self.assertEqual(naryste["irasai"][0]["politine-organizacija"], "Liberalų sąjūdis")
        self.assertEqual(naryste["irasai"][0]["nuo"], "2006")
        self.assertEqual(naryste["irasai"][0]["iki"], "Iki dabar")

    def test_anketa_pareiskimai_keys(self) -> None:
        # The mayoral questionnaire stops at Q14 — no EP or presidential
        # eligibility questions.
        pareiskimai = self.cepulis["normalized"]["anketa"]["pareiskimai"]
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
        for payload in (self.cepulis, self.masiliuniene, self.beisys, self.gaiziunas):
            with self.subTest(candidate=payload["candidateId"]):
                values = payload["normalized"]["anketa"]["pareiskimai"].values()
                self.assertTrue(all(value is not None for value in values))

    def test_conditional_blocks_absent(self) -> None:
        anketa = self.cepulis["normalized"]["anketa"]
        # Uniform shape: no conviction block means an empty entry list.
        self.assertEqual(anketa["teistumo-detales"], {"irasai": []})
        self.assertIsNone(anketa["mandato-netekimo-detales"])

    def test_biografija_uses_2024_question_numbering(self) -> None:
        # These pages have no nationality question, so education is Q2 and work
        # history Q4 — the 2024 EP numbering, not the 2023 mayoral one.
        bio = self.cepulis["normalized"]["biografija"]
        self.assertNotIn("tautybe", bio)
        self.assertEqual(bio["gimimo-data"], "1963-08-08")
        self.assertEqual(bio["gimimo-vieta"], "Joniškis")
        self.assertEqual(bio["mokslo-laipsnis"], "Neturiu")
        self.assertEqual(bio["uzsienio-kalbos"], ["Rusų (Įgudęs)"])
        self.assertEqual(bio["seimine-padetis"], "Vedęs")
        self.assertEqual(
            bio["issilavinimas"]["irasai"][0]["mokymo-istaigos-pavadinimas"],
            "Vilniaus inžinerinis statybos institutas (VISI - VGTU)",
        )
        self.assertEqual(len(bio["darbo-patirtis"]["irasai"]), 9)

    def test_turto_ir_pajamu_normalized(self) -> None:
        # These asset rows put the label and the amount in one cell, unlike the
        # two-cell 2024 EP layout.
        turtas = self.cepulis["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 46155)
        self.assertEqual(turtas["pinigines-lesos"], 3000)
        self.assertEqual(turtas["gautos-pajamos"], 28534.21)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 5490.07)

    def test_privaciu_interesu_declarant_hoisted(self) -> None:
        privaciu = self.cepulis["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "Gediminas ČEPULIS")
        self.assertEqual(privaciu["pateikimo-data"], "2025-01-02")
        self.assertEqual(privaciu["sutuoktinis-sugyventinis-ar-partneris"], "Reda ČEPULIENĖ")
        self.assertTrue(privaciu["deklaruojancio-darbovietes"])

    def test_campaign_participants_and_donations(self) -> None:
        campaign = self.cepulis["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Atstovaujamasis")
        self.assertEqual(campaign["registravimo-data"], "2025-01-24")

        donations = campaign["aukos-pagal-sekcija"]["gautos-ir-priimtos-aukos"]
        self.assertEqual(len(donations["records"]), 20)
        self.assertEqual(
            donations["records"][0],
            {
                "rowNumber": "1.",
                "donor": "LINAS ČESNULIS",
                "municipality": None,
                "date": "2025-01-22",
                "incomeSourceCode": "FAA",
                "amount": 100.0,
                "notes": "Priimtas",
            },
        )
        self.assertEqual(donations["totals"]["is-viso"], 3640.0)

        # Self-standing participants appear too.
        self.assertEqual(
            self.gaiziunas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Savarankiškas",
        )

    def test_kita_tab_is_empty_for_every_candidate(self) -> None:
        for payload in (self.cepulis, self.masiliuniene, self.beisys, self.gaiziunas):
            self.assertEqual(payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []})


if __name__ == "__main__":
    unittest.main()
