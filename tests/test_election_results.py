"""The 2012-2015 elected-status join (scraper/shared/election_results.py).

Two layers: the page parsers on synthetic HTML shaped like VRK's results
pages (so a regression in a regex or a column offset fails here without any
network), and pins of the built results files' reconciliation stats — the
numbers that were checked against VRK's own counts when the join shipped.
"""

import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scraper.shared.election_results import (
    MAYOR_WINNER_PATTERN,
    PRESIDENT_WINNER_PATTERN,
    SEIMO_WINNER_PATTERN,
    first_round_elected_by_label,
    load_results_lookup,
    normalize_person_name,
    parse_composition_page,
    parse_elected_members_page,
    parse_list_ranking_page,
    parse_municipality_results_page,
    parse_seimo_district_page,
    resolve_name,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SITEMAPS = REPO_ROOT / "sitemaps"


def _results(election_id: str) -> dict:
    return json.loads((SITEMAPS / f"{election_id}.results.json").read_text(encoding="utf-8"))


class NameResolutionTests(unittest.TestCase):
    def test_name_key_folds_case_spacing_and_hyphen_spacing(self):
        self.assertEqual(normalize_person_name("Radvilė Morkūnaitė - Mikulėnienė"), "RADVILĖ MORKŪNAITĖ-MIKULĖNIENĖ")
        self.assertEqual(normalize_person_name("Algirdas\xa0\xa0BUTKEVIČIUS"), "ALGIRDAS BUTKEVIČIUS")

    def test_resolution_needs_exactly_one_match(self):
        field = [
            {"candidateName": "Silverijus Statkus", "vrkCandidateId": "1"},
            {"candidateName": "Silverijus Statkus", "vrkCandidateId": "2"},
            {"candidateName": "Elena Jurgilienė", "vrkCandidateId": "3"},
        ]
        self.assertIsNone(resolve_name("Silverijus STATKUS", field))
        self.assertEqual(resolve_name("Elena JURGILIENĖ", field)["vrkCandidateId"], "3")
        self.assertIsNone(resolve_name("Nobody", field))


class VerdictPatternTests(unittest.TestCase):
    def test_seimo_verdict_both_wordings(self):
        self.assertEqual(SEIMO_WINNER_PATTERN.search("Rinkimų rezultatas - Seimo nariu išrinktas Algirdas BUTKEVIČIUS Pastaba. x").group(1).strip(), "Algirdas BUTKEVIČIUS")
        self.assertEqual(SEIMO_WINNER_PATTERN.search("Rinkimų rezultatas: Seimo nariu išrinktas Vidas Mikalauskas. Rūšiuoti pagal").group(1).strip(), "Vidas Mikalauskas")
        self.assertIsNone(SEIMO_WINNER_PATTERN.search("Rinkimų rezultatas - reikalingas pakartotinis balsavimas"))

    def test_mayor_verdict_inflects_with_the_winner(self):
        self.assertEqual(MAYOR_WINNER_PATTERN.search("Rinkimų rezultatas: Meru išrinktas Vitalijus MITROFANOVAS. Kandidatas").group(1).strip(), "Vitalijus MITROFANOVAS")
        self.assertEqual(MAYOR_WINNER_PATTERN.search("Rinkimų rezultatas: Mere išrinkta Nijolė DIRGINČIENĖ. Kandidatas").group(1).strip(), "Nijolė DIRGINČIENĖ")

    def test_president_verdict(self):
        self.assertEqual(PRESIDENT_WINNER_PATTERN.search("Lietuvos Respublikos Prezidente išrinkta Dalia GRYBAUSKAITĖ.").group(1).strip(), "Dalia GRYBAUSKAITĖ")


SEIMO_DISTRICT_HTML = """
<html><body>
<p>Rinkimų rezultatas - Seimo nariu išrinktas Algirdas BUTKEVIČIUS</p><p>Pastaba.</p>
<table>
<tr><th>Kandidatas</th><th>apylinkėse</th><th>paštu</th><th>iš viso</th><th>%</th><th>%</th></tr>
<tr><td><a href="rezultatai_sm_kand66449_sav7277_1_1_.html">Algirdas BUTKEVIČIUS</a></td><td>9885</td><td>1484</td><td>11369</td><td>69,24%</td><td>66,03%</td></tr>
<tr><td><a href="rezultatai_sm_kand66654_sav7277_1_1_.html">Rimvydas ŽIEMYS</a></td><td>1112</td><td>247</td><td>1359</td><td>8,28%</td><td>7,89%</td></tr>
</table>
</body></html>
"""


class SeimoDistrictPageTests(unittest.TestCase):
    def test_verdict_and_rows(self):
        parsed = parse_seimo_district_page(SEIMO_DISTRICT_HTML)
        self.assertEqual(parsed["verdictName"], "Algirdas BUTKEVIČIUS")
        self.assertFalse(parsed["runoff"])
        self.assertEqual([(r["name"], r["votes"]) for r in parsed["rows"]], [("Algirdas BUTKEVIČIUS", 11369), ("Rimvydas ŽIEMYS", 1359)])

    def test_runoff_page_without_verdict(self):
        html = SEIMO_DISTRICT_HTML.replace("Rinkimų rezultatas - Seimo nariu išrinktas Algirdas BUTKEVIČIUS", "Rinkimų rezultatas - reikalingas pakartotinis balsavimas")
        parsed = parse_seimo_district_page(html)
        self.assertIsNone(parsed["verdictName"])
        self.assertTrue(parsed["runoff"])

    def test_rows_linked_with_the_presidential_template_stem(self):
        # The 2009 and 2011 by-election trees name the candidate row pages
        # "rezultatai_prezidento_kand…" instead of "rezultatai_sm_kand…".
        html = SEIMO_DISTRICT_HTML.replace("rezultatai_sm_kand", "rezultatai_prezidento_kand")
        parsed = parse_seimo_district_page(html)
        self.assertEqual([r["name"] for r in parsed["rows"]], ["Algirdas BUTKEVIČIUS", "Rimvydas ŽIEMYS"])

    def test_first_round_elected_page_keyed_by_constituency(self):
        html = """<table><tr><th>Kandidatas</th><th>Apygarda</th><th>Iškėlė</th></tr>
        <tr><td><a href="../../../rinkimai/406_lt/Kandidatai/Kandidatas26261/Kandidato26261Anketa.html">Leonard TALMONT</a></td><td>56. Vilniaus - Šalčininkų</td><td>Lietuvos lenkų rinkimų akcija</td></tr></table>"""
        with tempfile.TemporaryDirectory() as tmp, mock.patch("scraper.shared.election_results.fetch_text", return_value=html):
            by_label = first_round_elected_by_label(Path(tmp), "2009_seimo_rinkimai")
        self.assertEqual(list(by_label), ["56. Vilniaus - Šalčininkų"])
        self.assertEqual(by_label["56. Vilniaus - Šalčininkų"]["vrkCandidateId"], "26261")
        # A tree without the page (2011, 2013) is an empty map, not an error.
        with tempfile.TemporaryDirectory() as tmp, mock.patch("scraper.shared.election_results.fetch_text", side_effect=RuntimeError("404")):
            self.assertEqual(first_round_elected_by_label(Path(tmp), "2013_seimo_rinkimai"), {})


MEMBERS_HTML = """
<table>
<tr><td><a href="/statiniai/puslapiai/2012_seimo_rinkimai/output_lt/rinkimu_diena/../../../rinkimai/416_lt/Kandidatai/Kandidatas66457/Kandidato66457Anketa.html">Remigijus AČAS</a></td><td>Daugiamandatė</td><td>Partija Tvarka ir teisingumas</td></tr>
<tr><td><a href="../../../rinkimai/416_lt/Kandidatai/Kandidatas66818/Kandidato66818Anketa.html">Vytenis Povilas ANDRIUKAITIS</a></td><td>4 Žirmūnų</td><td>Lietuvos socialdemokratų partija</td></tr>
<tr><td><a href="../../../rinkimai/416_lt/Kandidatai/Kandidatas66457/Kandidato66457Anketa.html">Remigijus AČAS</a></td><td>dup</td><td>x</td></tr>
</table>
"""


class ElectedMembersPageTests(unittest.TestCase):
    def test_rows_are_keyed_by_anketa_id_once(self):
        members = parse_elected_members_page(MEMBERS_HTML, "https://www.vrk.lt/statiniai/puslapiai/2012_seimo_rinkimai/output_lt/rinkimu_diena/x.html")
        self.assertEqual([(m["vrkCandidateId"], m["cells"][1]) for m in members], [("66457", "Daugiamandatė"), ("66818", "4 Žirmūnų")])
        self.assertTrue(members[1]["anketaUrl"].endswith("Kandidatas66818/Kandidato66818Anketa.html"))


MUNICIPALITY_HTML = """
<html><body>
<p>Mandatų skirstymo kvota: 380</p>
<table>
<tr><td><b>2</b></td><td><b><a href="partijos5842_gauti_balsai_apygardoje7761.html">Lietuvos socialdemokratų partija</a></b></td><td><a href="apygardos7761_partijos5842_pirmumo_balsai.html">pirm.</a></td><td>3071</td><td>552</td><td>3623</td><td>36,32%</td><td>62,32%</td><td><b>9</b></td></tr>
<tr><td><b>26</b></td><td><b><a href="partijos5678_gauti_balsai_apygardoje7761.html">Lietuvos Respublikos liberalų sąjūdis</a></b></td><td><a href="apygardos7761_partijos5678_pirmumo_balsai.html">pirm.</a></td><td>2346</td><td>362</td><td>2708</td><td>27,15%</td><td>73,97%</td><td><b>7</b></td></tr>
<tr><td>Iš viso:</td><td></td><td></td><td>8074</td><td>1405</td><td>9479</td><td>95,04%</td><td>64,79%</td><td>24</td></tr>
</table>
<h3>Mero rinkimai</h3>
<p>Rinkimų rezultatas: Mere išrinkta Nijolė DIRGINČIENĖ.</p>
<table>
<tr><td><a href="rezultatai_sav_kand77601_sav7761_1_1.html">Nijolė DIRGINČIENĖ</a></td><td>X</td><td>3476</td></tr>
<tr><td><a href="rezultatai_sav_kand84012_sav7761_1_1.html">Apolinaras NICIUS</a></td><td>Y</td><td>2658</td></tr>
</table>
</body></html>
"""

RANKING_HTML = """
<table>
<tr><th>Porinkiminis</th><th>Vardas, pavardė</th><th>Priešrinkiminis</th><th>Pirmumo balsai</th></tr>
<tr><td>1</td><td><a href="../../../rinkimai/440_lt/Kandidatai/Kandidatas84013/Kandidato84013Anketa.html">Vitalijus MITROFANOVAS</a> <br/>išrinktas(-a) meru(-e) </td><td>1</td><td>1163</td></tr>
<tr><td>2</td><td><a href="../../../rinkimai/440_lt/Kandidatai/Kandidatas84014/Kandidato84014Anketa.html">Zofija PAULIKIENĖ</a></td><td>2</td><td>746</td></tr>
<tr><td>3</td><td><a href="../../../rinkimai/440_lt/Kandidatai/Kandidatas84015/Kandidato84015Anketa.html">Tomas MARTINAITIS</a></td><td>3</td><td>604</td></tr>
</table>
"""

COMPOSITION_HTML = """
<p>Mandatų skaičius, įskaitant merą: 25</p>
<table>
<tr><td>Lietuvos socialdemokratų partija</td><td><a href="http://www.vrk.lt/statiniai/puslapiai/rinkimai/440_lt/Kandidatai/Kandidatas84013/Kandidato84013Anketa.html">Mitrofanovas Vitalijus (MERAS)</a></td><td>2015-03-22</td></tr>
<tr><td>Lietuvos socialdemokratų partija</td><td><a href="http://www.vrk.lt/statiniai/puslapiai/rinkimai/440_lt/Kandidatai/Kandidatas84014/Kandidato84014Anketa.html">Paulikienė Zofija</a></td><td>2015-03-22</td></tr>
</table>
<table>
<tr><td>Lietuvos socialdemokratų partija</td><td><a href="http://www.vrk.lt/statiniai/puslapiai/rinkimai/440_lt/Kandidatai/Kandidatas84015/Kandidato84015Anketa.html">MARTINAITIS TOMAS</a></td><td>2015-03-22</td><td>2015-04-02</td><td>Atsisakė mandato dėl nesuderinamų pareigų</td></tr>
</table>
"""


class MunicipalPageTests(unittest.TestCase):
    def test_municipality_page_lists_mandates_and_mayor(self):
        parsed = parse_municipality_results_page(MUNICIPALITY_HTML, "https://www.vrk.lt/statiniai/puslapiai/t/output_lt/rezultatai_daugiamand_apygardose/apygardos_rezultatai7761.html")
        self.assertEqual([(l["listName"], l["listId"], l["mandates"]) for l in parsed["lists"]], [("Lietuvos socialdemokratų partija", "5842", 9), ("Lietuvos Respublikos liberalų sąjūdis", "5678", 7)])
        self.assertTrue(parsed["lists"][0]["rankingUrl"].endswith("rezultatai_daugiamand_apygardose/apygardos7761_partijos5842_pirmumo_balsai.html"))
        self.assertEqual(parsed["mayorVerdictName"], "Nijolė DIRGINČIENĖ")
        self.assertEqual(parsed["mayoralField"], ["Nijolė DIRGINČIENĖ", "Apolinaras NICIUS"])
        self.assertEqual(parsed["listMandatesTotal"], 24)

    def test_ranking_rows_carry_rank_position_id_and_mayor_marker(self):
        rows = parse_list_ranking_page(RANKING_HTML, "https://x/")
        self.assertEqual([(r["rank"], r["preElectionPosition"], r["vrkCandidateId"], r["mayorElect"]) for r in rows], [(1, 1, "84013", True), (2, 2, "84014", False), (3, 3, "84015", False)])

    def test_composition_page_reads_both_tables(self):
        parsed = parse_composition_page(COMPOSITION_HTML)
        self.assertEqual(parsed["mandates"], 25)
        self.assertEqual([(m["vrkCandidateId"], m["recognized"], m["mayor"]) for m in parsed["members"]], [("84013", "2015-03-22", True), ("84014", "2015-03-22", False), ("84015", "2015-03-22", False)])


class ResultsLookupTests(unittest.TestCase):
    def test_missing_file_means_unknown_not_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_results_lookup(Path(tmp) / "none.results.json"))
            path = Path(tmp) / "x.results.json"
            path.write_text(json.dumps({"elected": {"1": {"seat": "meras"}}}), encoding="utf-8")
            self.assertEqual(load_results_lookup(path), {"1": {"seat": "meras"}})


class BuiltResultsPins(unittest.TestCase):
    """The reconciliation each results file was shipped with."""

    def test_2012_seimo(self):
        stats = _results("2012-seimo")["stats"]
        self.assertEqual(stats["membersListed"], 139)
        self.assertEqual(stats["membersInSitemap"], 139)
        self.assertEqual(stats["seats"], {"daugiamandate": 70, "vienmandate": 69})
        # 71 constituency pages: 69 agree with the members list; the two
        # annulled constituencies (re-run in 2013) are the disagreement and
        # the unresolved one.
        self.assertEqual(stats["constituencyWinnersAgree"], 69)
        self.assertEqual(stats["constituencyWinnersDisagree"] + stats["constituencyWinnersUnresolved"], 2)

    def test_2013_and_2015_seimo_by_elections(self):
        for election_id, plurality in [("2013-kovo-3-seimo-birzai-zarasai-ukmerge", 0), ("2015-kovo-1-seimo-zirmunai", 1), ("2015-birzelio-7-seimo-varena-eisiskes", 0), ("2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai", 1), ("2011-vasario-13-seimo-marijampole", 1)]:
            stats = _results(election_id)["stats"]
            self.assertEqual(stats["unresolved"], 0, election_id)
            self.assertEqual(stats["winnersResolved"], stats["constituencies"], election_id)
            self.assertEqual(stats["byRunoffPlurality"], plurality, election_id)
        self.assertEqual(_results("2013-kovo-3-seimo-birzai-zarasai-ukmerge")["stats"]["constituencies"], 3)

    def test_2014_ep_and_presidential(self):
        self.assertEqual(_results("2014-ep")["stats"], {"membersListed": 11, "membersInSitemap": 11, "membersNotInSitemap": 0})
        stats = _results("2014-prezidento")["stats"]
        self.assertEqual(stats["winnerName"], "Dalia GRYBAUSKAITĖ")
        self.assertEqual(stats["winnersResolved"], 1)

    def test_2015_municipal_general(self):
        payload = _results("2015-kovo-1-savivaldybiu")
        stats = payload["stats"]
        self.assertEqual(stats["municipalities"], 60)
        self.assertEqual(stats["mayorsResolved"], 57)
        self.assertEqual(stats["mayorsUnresolved"], 0)
        self.assertEqual(stats["councilMembers"], 1464)
        self.assertEqual(stats["councilNotInSitemap"], 0)
        # Dual mayor+council candidates hold two VRK ids; the ranking pages
        # use the one the listings do not.
        self.assertEqual(stats["councilResolvedByNameAndList"], 249)
        # Šilutė and Trakai (councils annulled, re-run in June) and Širvintos
        # (mayoral race annulled) are the only municipalities short a seat.
        self.assertEqual(stats["seatCountMismatches"], 3)
        self.assertEqual(stats["annulledWinners"], 48)
        self.assertEqual(stats["compositionPagesChecked"], 60)
        self.assertGreaterEqual(stats["compositionFullyContainsDerived"], 58)
        annulled = {v["municipality"] for v in payload["elected"].values() if v.get("annulled")}
        self.assertEqual(annulled, {"47. Šilutės rajono", "52. Trakų rajono"})
        # Telšiai's March mayor (Kleiva) was elected and died in office; his
        # win stands, the November vote being a new election.
        telsiai = [v for v in payload["elected"].values() if v.get("municipality") == "51. Telšių rajono" and v["seat"] == "meras"]
        self.assertEqual(len(telsiai), 1)
        self.assertNotIn("annulled", telsiai[0])

    def test_2015_repeat_elections_and_telsiai(self):
        self.assertEqual(_results("2015-birzelio-7-pakartotiniai-sirvintos-trakai")["stats"]["seats"], {"meras": 2, "tarybos-narys": 24})
        self.assertEqual(_results("2015-birzelio-21-pakartotiniai-silutes")["stats"]["seats"], {"meras": 1, "tarybos-narys": 24})
        self.assertEqual(_results("2015-lapkricio-8-telsiu-mero")["stats"]["seats"], {"meras": 1})
        for election_id in ["2015-birzelio-7-pakartotiniai-sirvintos-trakai", "2015-birzelio-21-pakartotiniai-silutes", "2015-lapkricio-8-telsiu-mero"]:
            stats = _results(election_id)["stats"]
            self.assertEqual(stats["mayorsUnresolved"], 0)
            self.assertEqual(stats["seatCountMismatches"], 0)
            self.assertEqual(stats["councilNotInSitemap"], 0)


if __name__ == "__main__":
    unittest.main()
