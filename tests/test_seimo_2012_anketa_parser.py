import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2012.anketa_parser import parse_anketa_sample
from scraper.elections.seimo_2012.candidate_samples import EXPECTED_TABS
from scraper.elections.seimo_2012.sitemap import (
    DISTRICTS_URL,
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
    extract_side_links,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class Seimo2012SitemapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, cls.stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT,
                output_path=Path(tmp) / "sitemap.json",
            )
            cls.payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        cls.by_vrk_id = {entry["vrkCandidateId"]: entry for entry in cls.payload["entries"]}

    def test_index_side_rows_are_recognised_and_not_treated_as_lists(self) -> None:
        side = extract_side_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
        kinds = {}
        for link in side:
            kinds.setdefault(link["kind"], []).append(link)
        self.assertEqual(len(kinds["koalicijos-nare"]), 4)
        self.assertEqual({link["coalitionListNumber"] for link in kinds["koalicijos-nare"]}, {10})
        self.assertEqual(sum(link["declaredCount"] for link in kinds["koalicijos-nare"]), 135)
        self.assertEqual(len(kinds["tik-vienmandatese"]), 7)
        self.assertEqual(kinds["tik-vienmandatese"][-1]["listKey"], "issikele")
        self.assertEqual(kinds["tik-vienmandatese"][-1]["declaredCount"], 36)
        self.assertEqual(self.stats["lists"], 18)

    def test_two_structures_merge_on_the_vrk_candidate_id(self) -> None:
        stats = self.stats
        self.assertEqual(stats["districts"], 71)
        self.assertEqual(stats["list_candidacies"], 1878)
        self.assertEqual(stats["declared_list_candidates"], 1878)
        self.assertEqual(stats["list_count_mismatches"], 0)
        self.assertEqual(stats["district_candidacies"], 978)
        self.assertEqual(stats["extracted"], 1927)
        self.assertEqual(stats["dual_candidates"], 929)
        self.assertEqual(stats["list_only_candidates"], 949)
        self.assertEqual(stats["district_only_candidates"], 49)
        self.assertEqual(stats["dual_candidates"] + stats["list_only_candidates"] + stats["district_only_candidates"], 1927)
        self.assertEqual(stats["duplicate_list_rows"], 0)
        self.assertEqual(stats["duplicate_district_rows"], 0)
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(self.payload["sourceUrl"], LISTING_URL)
        self.assertEqual(self.payload["districtsUrl"], DISTRICTS_URL)

    def test_cross_checks_reconcile(self) -> None:
        stats = self.stats
        # The list pages name each candidate's constituency; the coalition
        # list page alone has no such column (135 rows), and every row that
        # has one agrees with the constituency pages.
        self.assertEqual(stats["list_rows_without_district_column"], 135)
        self.assertEqual(stats["list_district_join_mismatch"], 0)
        # VRK's "tik vienmandatėse" pages list 52 distinct people; three of
        # them also hold a list seat, leaving the 49 the merge found. The
        # index declares 58 because the self-nominated page still counts
        # five withdrawn candidates it no longer lists.
        self.assertEqual(stats["side_page_district_only_ids"], 52)
        self.assertEqual(stats["side_page_ids_also_on_lists"], 3)
        self.assertEqual(stats["side_page_ids_not_on_district_pages"], 0)
        self.assertEqual(stats["side_page_district_only_declared"], 58)
        self.assertEqual(stats["district_only_reconciled"], 1)

    def test_entry_shapes(self) -> None:
        butkevicius = self.by_vrk_id["66814"]
        self.assertEqual(butkevicius["candidateId"], "algirdas-butkevicius")
        self.assertEqual(butkevicius["roles"], ["daugiamandate", "vienmandate"])
        self.assertEqual(
            butkevicius["daugiamandateCandidacy"],
            {"sarasas": "Lietuvos socialdemokratų partija", "sarasoNumeris": 8, "sarasoId": "4136-1", "numerisSarase": 1},
        )
        self.assertEqual(
            butkevicius["vienmandateCandidacy"],
            {"apygarda": "Vilkaviškio", "apygardosNumeris": 68, "apygardosId": "7277", "iskele": "Lietuvos socialdemokratų partija"},
        )
        # A coalition list row names the member party that nominated.
        medalinskas = self.by_vrk_id["68029"]
        self.assertEqual(medalinskas["daugiamandateCandidacy"]["sarasoNumeris"], 10)
        self.assertEqual(medalinskas["daugiamandateCandidacy"]["koalicijosPartija"], "Lietuvos centro partija")
        self.assertNotIn("koalicijosPartija", butkevicius["daugiamandateCandidacy"])
        # List-only and constituency-only entries carry one candidacy.
        self.assertEqual(self.by_vrk_id["66815"]["roles"], ["daugiamandate"])
        self.assertNotIn("vienmandateCandidacy", self.by_vrk_id["66815"])
        self.assertEqual(self.by_vrk_id["67514"]["roles"], ["vienmandate"])
        self.assertEqual(self.by_vrk_id["67514"]["vienmandateCandidacy"]["iskele"], "Išsikėlė pats")
        # A party can nominate in the constituency someone who also
        # self-nominated; the listing says so in one cell.
        self.assertEqual(
            self.by_vrk_id["67312"]["vienmandateCandidacy"]["iskele"],
            "Tėvynės sąjunga - Lietuvos krikščionys demokratai, išsikėlė pats",
        )

    def test_name_collisions_get_positional_suffixes(self) -> None:
        self.assertEqual(self.stats["duplicate_candidate_ids"], 1)
        markunai = [entry for entry in self.payload["entries"] if entry["candidateName"] == "Arūnas MARKŪNAS"]
        self.assertEqual([entry["candidateId"] for entry in markunai], ["arunas-markunas", "arunas-markunas-2"])
        self.assertNotEqual(markunai[0]["vrkCandidateId"], markunai[1]["vrkCandidateId"])


class Seimo2012AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.butkevicius, self.butkevicius_stats = _parse("algirdas-butkevicius")
        self.medalinskas, _ = _parse("alvydas-medalinskas")
        self.balsys, _ = _parse("linas-balsys")
        self.blinkeviciute, _ = _parse("vilija-blinkeviciute")

    def test_expected_tabs_are_the_era_five(self) -> None:
        self.assertEqual(
            EXPECTED_TABS,
            {"anketa", "biografija", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija", "kita"},
        )

    def test_top_level_fields_and_candidacy(self) -> None:
        self.assertEqual(self.butkevicius["electionId"], "2012-seimo")
        self.assertEqual(self.butkevicius["candidateName"], "Algirdas BUTKEVIČIUS")
        self.assertEqual(self.butkevicius_stats["anomalies"], [])
        self.assertEqual(
            self.butkevicius["kandidatavimas"],
            {
                "vrkCandidateId": "66814",
                "roles": ["daugiamandate", "vienmandate"],
                "vienmandate": {
                    "apygarda": "Vilkaviškio",
                    "apygardosNumeris": 68,
                    "apygardosId": "7277",
                    "iskele": "Lietuvos socialdemokratų partija",
                },
                "daugiamandate": {
                    "sarasas": "Lietuvos socialdemokratų partija",
                    "sarasoNumeris": 8,
                    "sarasoId": "4136-1",
                    "numerisSarase": 1,
                },
                "isrinktas": True,
                "isrinktasKaip": "vienmandate",
                "rezultatuSaltinis": "https://www.vrk.lt/statiniai/puslapiai/2012_seimo_rinkimai/output_lt/rinkimu_diena/isrinkti_seimo_nariai_kadencijaik.html",
            },
        )
        self.assertEqual(self.balsys["kandidatavimas"]["roles"], ["vienmandate"])
        self.assertIs(self.balsys["kandidatavimas"]["isrinktas"], True)
        self.assertEqual(self.blinkeviciute["kandidatavimas"]["isrinktasKaip"], "daugiamandate")
        self.assertIs(self.medalinskas["kandidatavimas"]["isrinktas"], False)
        self.assertIsNone(self.balsys["kandidatavimas"]["daugiamandate"])
        self.assertEqual(self.blinkeviciute["kandidatavimas"]["roles"], ["daugiamandate"])
        self.assertIsNone(self.blinkeviciute["kandidatavimas"]["vienmandate"])

    def test_dual_candidacy_profile_card_keeps_both_blocks(self) -> None:
        kita = self.butkevicius["normalized"]["profilis"]["kita"]
        self.assertEqual(
            list(kita.keys()),
            [
                "apygarda",
                "iskele",
                "savarankisko-politines-kampanijos-dalyvio-duomenys",
                "apygarda-2",
                "iskele-2",
                "numeris-sarase",
                "daugiamandateje-apygardoje",
                "i-turas",
            ],
        )
        self.assertEqual(kita["apygarda"]["reiksme"], "Vilkaviškio (Nr.68)")
        self.assertEqual(kita["iskele"]["reiksme"], "Lietuvos socialdemokratų partija")
        self.assertEqual(kita["apygarda-2"]["reiksme"], "Daugiamandatė")
        self.assertEqual(kita["numeris-sarase"]["reiksme"], "1")
        self.assertTrue(kita["iskele-2"]["nuorodos"][0].endswith("RinkimuOrganizacija4136_1.html"))
        # Results links, one per candidacy; no page marks the winner.
        self.assertTrue(kita["daugiamandateje-apygardoje"]["nuorodos"][0].endswith("partijos_pirmumo_balsai4136.html"))
        self.assertTrue(kita["i-turas"]["nuorodos"][0].endswith("apygarda7277aktyvumasdesc1turas.html"))
        self.assertIsNone(self.butkevicius["normalized"]["profilis"]["pastaba"])

        # A coalition nominee's multi-member block repeats Iškėlė for the
        # member party in parentheses — third occurrence on the card.
        kita = self.medalinskas["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["iskele"]["reiksme"], "Lietuvos centro partija")
        self.assertTrue(kita["iskele-2"]["reiksme"].startswith("Nacionalinis susivienijimas"))
        self.assertEqual(kita["iskele-3"]["pavadinimas"], "(Iškėlė")
        self.assertEqual(kita["iskele-3"]["reiksme"], "Lietuvos centro partija")

        # A constituency-only card has one block and, here, both rounds.
        kita = self.balsys["normalized"]["profilis"]["kita"]
        self.assertEqual(
            list(kita.keys()),
            ["apygarda", "iskele", "savarankisko-politines-kampanijos-dalyvio-duomenys", "i-turas", "ii-turas"],
        )
        self.assertEqual(kita["iskele"]["reiksme"], "Išsikėlė pats")

    def test_anketa_uses_the_seimo_2012_mapping(self) -> None:
        anketa = self.butkevicius["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1958-11-19")
        self.assertEqual(
            anketa["pareiskimai"],
            {
                "ar-nebaigta-teismo-paskirta-bausme": "Neturiu",
                "ar-atliekate-karo-tarnyba": "Nesu",
                "ar-turite-kitos-valstybes-pilietybe": "Neturiu",
                "ar-susijes-priesaika-uzsienio-valstybei": "Nesu",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis": "Ne",
                "ar-buvote-pripazintas-kaltu": "Ne",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Ne",
                "teisiniai-argumentai": None,
            },
        )
        self.assertEqual(anketa["gimimo-vieta"], "Radviliškio rajonas")
        self.assertEqual(len(anketa["issilavinimas"]["irasai"]), 2)
        self.assertEqual(anketa["uzsienio-kalbos"], ["anglų", "rusų"])
        self.assertEqual(anketa["politine-organizacija"], "LSDP")
        self.assertEqual(len(anketa["anksciau-isrinktas"]["irasai"]), 5)
        # Q16 and Q17 share a text run; the split lands "LR Seimas,Seimo
        # narys" under Q16 and the next answer under Q17 as published.
        self.assertEqual(anketa["pagrindine-darboviete"], "LR Seimas,Seimo narys")
        self.assertEqual(anketa["visuomenine-veikla"], "knygos, sportas")
        self.assertIsNone(anketa["pomegiai"])
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Janina")

    def test_declarations_and_campaign(self) -> None:
        turto = self.butkevicius["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 52000)
        self.assertEqual(turto["pinigines-lesos"], 530000)
        self.assertEqual(turto["gautos-pajamos"], 826222.63)
        self.assertEqual(turto["valiuta"], "Lt")
        self.assertIn("nuo 2011-01-01 iki 2011-12-31", turto["pastaba"])
        campaign = self.butkevicius["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["izdininkas"]["vardas-pavarde"], "EDITA JAKIMAVIČIENĖ")
        self.assertEqual(list(campaign["aukos-pagal-sekcija"]), ["gautos-ir-priimtos-aukos"])
        self.assertEqual(
            self.medalinskas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Atstovaujamasis",
        )


if __name__ == "__main__":
    unittest.main()
