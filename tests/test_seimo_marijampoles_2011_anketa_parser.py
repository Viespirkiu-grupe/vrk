import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_marijampoles_2011.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    parse_anketa_sample,
)
from scraper.elections.seimo_marijampoles_2011.candidate_samples import EXPECTED_TABS
from scraper.elections.seimo_marijampoles_2011.results import RESULTS_TREE
from scraper.elections.seimo_marijampoles_2011.sitemap import (
    ELECTION_ID,
    LISTING_URL,
    build_sitemap_from_sample,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import extract_district_links

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
SITEMAPS = REPO_ROOT / "sitemaps"


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class SeimoMarijampoles2011SitemapTests(unittest.TestCase):
    def test_index_lists_the_constituencies(self) -> None:
        links = extract_district_links((SAMPLES_ROOT / "list.html").read_text(encoding="utf-8"))
        self.assertEqual([(link["number"], link["name"], link["districtId"]) for link in links], [(29, 'Marijampolės', '7192')])
        self.assertEqual(LISTING_URL, "https://www.vrk.lt/statiniai/puslapiai/rinkimai/410_lt/Kandidatai/index.html")

    def test_sitemap_walks_every_constituency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(
                sample_path=SAMPLES_ROOT,
                output_path=Path(tmp) / "sitemap.json",
            )
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        self.assertEqual(stats, {"rows": 9, "extracted": 9, "skipped": 0, "duplicate_candidate_ids": 0, "districts": 1})
        self.assertEqual(payload["electionId"], "2011-vasario-13-seimo-marijampole")
        self.assertEqual(payload["sourceUrl"], LISTING_URL)
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(sorted(by_id), ['albinas-mitrulevicius', 'algis-zvaliauskas', 'gediminas-akelaitis', 'nora-ribokiene', 'paulius-uleckas', 'ramunas-mazetis', 'rolandas-jonikaitis', 'vaida-giraityte', 'valdas-pileckas'])
        self.assertEqual(
            by_id["albinas-mitrulevicius"]["vienmandateCandidacy"],
            {"apygarda": "Marijampolės", "apygardosNumeris": 29, "apygardosId": "7192", "iskele": "Lietuvos socialdemokratų partija"},
        )
        self.assertEqual(by_id["albinas-mitrulevicius"]["vrkCandidateId"], "26312")


class SeimoMarijampoles2011ResultsTests(unittest.TestCase):
    def test_winners_resolve_from_the_constituency_pages(self) -> None:
        self.assertEqual(RESULTS_TREE, "2011_seimo_rinkimai")
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(
            payload["stats"],
            {'constituencies': 1, 'winnersResolved': 1, 'unresolved': 0, 'decidedInRoundTwo': 1, 'byRunoffPlurality': 1, 'candidatesWithVotes': 9, 'voteRowsUnresolved': 0},
        )
        self.assertEqual(payload["elected"]["26312"]["method"], "runoff-plurality")
        self.assertEqual(payload["elected"]["26312"]["round"], 2)


class SeimoMarijampoles2011AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.winner, self.winner_stats = _parse("albinas-mitrulevicius")
        self.other, _ = _parse("valdas-pileckas")

    def test_expected_tabs_are_the_era_five(self) -> None:
        self.assertEqual(
            EXPECTED_TABS,
            {"anketa", "biografija", "turto-ir-pajamu-deklaracijos", "interesu-deklaracija", "kita"},
        )

    def test_top_level_fields_and_candidacy(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        self.assertEqual(self.winner["electionId"], "2011-vasario-13-seimo-marijampole")
        self.assertEqual(self.winner_stats["anomalies"], [])
        self.assertEqual(
            self.winner["kandidatavimas"],
            {
                "vrkCandidateId": "26312",
                "roles": ["vienmandate"],
                "vienmandate": {"apygarda": "Marijampolės", "apygardosNumeris": 29, "apygardosId": "7192", "iskele": "Lietuvos socialdemokratų partija"},
                "daugiamandate": None,
                "isrinktas": True,
                "isrinktasKaip": "vienmandate",
                "rezultatuSaltinis": "https://www.vrk.lt/statiniai/puslapiai/2011_seimo_rinkimai/output_lt/rezultatai_vienmand_apygardose2/rezultatai_vienmanate_apygarda{}aktyvumasdesc2turas.html".format(self.winner["kandidatavimas"]["rezultatuSaltinis"].split("apygarda")[-1].split("aktyvumas")[0]),
                "rezultatuTuras": 2,
                "vienmandatesBalsai": {
                    "balsadezese": 1933,
                    "pastu": 272,
                    "isViso": 2205,
                    "procentai": 25.64,
                    "vieta": 1,
                    "saltinis": "https://www.vrk.lt/statiniai/puslapiai/2011_seimo_rinkimai/output_lt/rezultatai_vienmand_apygardose/rezultatai_vienmanate_apygarda7192aktyvumasdesc1turas.html",
                },
                "vienmandatesBalsai2": {
                    "balsadezese": 6174,
                    "pastu": 825,
                    "isViso": 6999,
                    "procentai": 55.52,
                    "vieta": 1,
                    "saltinis": "https://www.vrk.lt/statiniai/puslapiai/2011_seimo_rinkimai/output_lt/rezultatai_vienmand_apygardose2/rezultatai_vienmanate_apygarda7194aktyvumasdesc2turas.html",
                },
            },
        )
        self.assertIs(self.other["kandidatavimas"]["isrinktas"], False)
        self.assertEqual(
            list(self.winner["normalized"].keys()),
            ["profilis", "anketa", "biografija", "turto-ir-pajamu-deklaracijos", "privaciu-interesu-deklaracija", "politines-kampanijos-dalyvio-duomenys", "kita"],
        )

    def test_profile_card_and_anketa(self) -> None:
        kita = self.winner["normalized"]["profilis"]["kita"]
        # Apygarda, Iškėlė and the campaign link; unlike the 2013 cards, no
        # results links.
        self.assertEqual(kita["apygarda"]["reiksme"].startswith("Marijampolės"), True)
        self.assertEqual(kita["iskele"]["reiksme"], "Lietuvos socialdemokratų partija")
        self.assertNotIn("i-turas", kita)
        anketa = self.winner["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1953-03-27")
        self.assertEqual(anketa["gimimo-vieta"], "Prienų raj. Jiestrakio kaimas")
        self.assertEqual(anketa["tautybe"], "lietuvis")
        self.assertEqual(
            list(anketa["pareiskimai"].keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-susijes-priesaika-uzsienio-valstybei",
                "ar-bendradarbiavote-su-uzsienio-tarnybomis",
                "ar-buvote-pripazintas-kaltu",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo",
                "teisiniai-argumentai",
            ],
        )
        self.assertIn("mokslo-laipsnis", anketa)
        self.assertIn("pedagoginis-vardas", anketa)
        self.assertEqual(self.winner["normalized"]["kita"], {"tekstai": ["Duomenų nėra"], "nuorodos": []})

    def test_declarations_and_campaign(self) -> None:
        turto = self.winner["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turto["privalomas-registruoti-turtas"], 85052)
        self.assertEqual(turto["gautos-pajamos"], 49021)
        self.assertEqual(turto["sumoketas-pajamu-mokestis"], 6824)
        self.assertEqual(turto["valiuta"], "Lt")
        campaign = self.winner["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["izdininkas"]["vardas-pavarde"], "REGINA BRUNDZIENĖ")
        aukos = campaign["aukos-pagal-sekcija"]["gautos-ir-priimtos-aukos"]
        self.assertEqual(len(aukos["records"]), 5)
        self.assertEqual(aukos["suvestine"][0], {"label": "Iš viso", "amountEur": None, "amountLt": 21010.68, "note": None})
        self.assertEqual(len(campaign["finansavimo-ataskaitos"]), 1)


if __name__ == "__main__":
    unittest.main()
