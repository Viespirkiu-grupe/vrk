import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_kedainiu_2005.anketa_parser import parse_anketa_sample
from scraper.elections.seimo_kedainiu_2005.candidate_samples import EXPECTED_TABS
from scraper.elections.seimo_kedainiu_2005.results import MEMBERS_PAGE, RESULTS_ROOT, build_results
from scraper.elections.seimo_kedainiu_2005.sitemap import (
    DISTRICTS_URL,
    ELECTION_ID,
    PARTIES_URL,
    build_sitemap_from_sample,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
RESULTS_DIR = REPO_ROOT / "samples" / "results" / ELECTION_ID
SITEMAPS = REPO_ROOT / "sitemaps"
CANDIDATES = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2005/seimas/kandidatai/"


def _parse(candidate_id: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, stats = parse_anketa_sample(candidate_id=candidate_id, samples_root=SAMPLES_ROOT, output_root=Path(tmp))
        return json.loads(output_path.read_text(encoding="utf-8")), stats


class SeimoKedainiu2005SitemapTests(unittest.TestCase):
    def test_one_constituency_five_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_sitemap_from_sample(sample_path=SAMPLES_ROOT, output_path=Path(tmp) / "sitemap.json")
            payload = json.loads((Path(tmp) / "sitemap.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["stats"], {"rows": 5, "extracted": 5, "duplicateCandidateIds": 0, "districts": 1, "partyNomineesDeclared": 5, "selfNominated": 0})
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(payload["sourceUrl"], DISTRICTS_URL)
        self.assertEqual(payload["partiesUrl"], PARTIES_URL)
        self.assertEqual(payload["districtUrls"], [CANDIDATES + "apg_kand_l_1675.htm"])
        by_id = {entry["candidateId"]: entry for entry in payload["entries"]}
        self.assertEqual(
            by_id["virginija-baltraitiene"],
            {
                "candidateName": "Virginija BALTRAITIENĖ",
                "candidateId": "virginija-baltraitiene",
                "url": CANDIDATES + "kand_anketa_l_315628.htm",
                "vrkCandidateId": "315628",
                "roles": ["vienmandate"],
                "vienmandateCandidacy": {"apygarda": "Kėdainių", "apygardosNumeris": 43, "apygardosId": "1675", "iskele": "Darbo partija"},
            },
        )
        self.assertEqual(sorted(by_id), ["stasys-sedbaras", "steponas-navajauskas", "tomas-bakucionis", "virginija-baltraitiene", "vytautas-valaitis"])


class SeimoKedainiu2005ResultsTests(unittest.TestCase):
    def test_runoff_winner(self) -> None:
        self.assertEqual(MEMBERS_PAGE, "rez_isrinkti_l_21_1.htm")
        payload = json.loads((SITEMAPS / f"{ELECTION_ID}.results.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["stats"], {"seats": 1, "membersListed": 1, "membersInSitemap": 1, "membersNotInSitemap": 0, "districtMismatches": 0, "roundWinnersPageDiff": 0, "decidedInRound": [2]})
        self.assertEqual(
            payload["elected"],
            {"315628": {"seat": "vienmandate", "method": "members-list", "sourceUrl": RESULTS_ROOT + MEMBERS_PAGE, "party": "Darbo partija", "round": 2, "districtId": "1675", "districtNumber": 43, "districtName": "Kėdainių"}},
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, stats = build_results(sitemap_path=SITEMAPS / f"{ELECTION_ID}.json", results_dir=RESULTS_DIR, output_path=Path(tmp) / "r.json")
        self.assertEqual(stats, payload["stats"])


class SeimoKedainiu2005AnketaParserTests(unittest.TestCase):
    def test_expected_tabs(self) -> None:
        self.assertEqual(EXPECTED_TABS, {"anketa", "biografija", "turto-ir-pajamu-deklaracijos"})

    def test_winner_record(self) -> None:
        record, stats = _parse("virginija-baltraitiene")
        self.assertEqual(record["electionId"], ELECTION_ID)
        self.assertEqual(stats["anomalies"], [])
        self.assertEqual(
            record["kandidatavimas"],
            {
                "vrkCandidateId": "315628",
                "roles": ["vienmandate"],
                "vienmandate": {"apygarda": "Kėdainių", "apygardosNumeris": 43, "apygardosId": "1675", "iskele": "Darbo partija"},
                "daugiamandate": None,
                "isrinktas": True,
                "isrinktasKaip": "vienmandate",
                "rezultatuSaltinis": RESULTS_ROOT + MEMBERS_PAGE,
                "rezultatuTuras": 2,
                "savarankiskasKampanijosDalyvis": {"sprendimas": "Nr.475, 2005.10.25", "nuoroda": CANDIDATES + "pazym_l_601.pdf"},
            },
        )
        anketa = record["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1958-03-04")
        self.assertEqual(anketa["pareiskimai"]["ar-susijes-priesaika-uzsienio-valstybei"], "Nėra")
        self.assertEqual(anketa["anksciau-isrinktas"]["irasai"][0]["laikotarpis"], "2003 - 2007")
        self.assertEqual(list(record["normalized"]["profilis"]["kita"].keys()), ["apygarda", "iskele", "kandidatas-registruotas-savarankisku-politines-kampanijos-dalyviu-sprendimas"])
        self.assertEqual(record["normalized"]["profilis"]["kita"]["apygarda"]["reiksme"], "Kėdainių (Nr.43)")
        self.assertEqual(record["normalized"]["turto-ir-pajamu-deklaracijos"]["gautos-pajamos"], 49373)
        self.assertTrue(record["normalized"]["biografija"]["tekstas"].startswith("Virginija BALTRAITIENĖ gimė 1958 m."))

    def test_losers_and_the_one_without_a_campaign_line(self) -> None:
        valaitis, _ = _parse("vytautas-valaitis")
        self.assertFalse(valaitis["kandidatavimas"]["isrinktas"])
        self.assertNotIn("savarankiskasKampanijosDalyvis", valaitis["kandidatavimas"])
        self.assertEqual(list(valaitis["normalized"]["profilis"]["kita"].keys()), ["apygarda", "iskele"])
        self.assertEqual(valaitis["normalized"]["anketa"]["seimine-padetis"], "Našlys")
        sedbaras, _ = _parse("stasys-sedbaras")
        self.assertEqual(sedbaras["normalized"]["anketa"]["mokslo-laipsnis"], "Socialinių mokslų (teisės krypties) daktaras")
        self.assertFalse(sedbaras["kandidatavimas"]["isrinktas"])


if __name__ == "__main__":
    unittest.main()
