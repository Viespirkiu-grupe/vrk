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

import requests

from scraper.shared import election_results
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
    parse_mandates_page_2007,
    parse_municipality_results_page,
    parse_municipality_results_page_2007,
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
        # A tree without the page (2011, 2013) is an empty map, not an error --
        # and "without" means VRK answered 404; any other failure propagates
        # (issue #134, OptionalPageFetchTests).
        missing = requests.Response()
        missing.status_code = 404
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "scraper.shared.election_results.fetch_text",
            side_effect=requests.HTTPError("404", response=missing),
        ):
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


# The 2011 page: no mayoral section, no "% su pirmumo" column, a
# self-nominated individual's own row (savkand) that can carry a mandate,
# and a totals row of plain numbers.
MUNICIPALITY_2011_HTML = """
<html><body>
<table>
<tr><td>VRK sut. Nr.</td><td>Kandidatų sąrašo pavadinimas, išsikėlusio kandidato vardas ir pavardė</td><td>Pirmumo balsai</td><td>apylinkėse</td><td>paštu</td><td>iš viso</td><td>% nuo dalyvavusių rinkėjų</td><td>Mandatų skaičius</td></tr>
<tr><td>2</td><td><a href="partijos3994_gauti_balsai_apygardoje7131.html">Artūro Zuoko ir Vilniaus koalicija</a></td><td><a href="apygardos7131_partijos3994_pirmumo_balsai.html">pirm.</a></td><td>33218</td><td>918</td><td>34136</td><td>17,74%</td><td>12</td></tr>
<tr><td>3</td><td><a href="savkand42302_gauti_balsai_apygardoje7131.html">Darius NORKUS</a></td><td></td><td>1300</td><td>108</td><td>1408</td><td>0,73%</td><td>0</td></tr>
<tr><td>14</td><td><a href="savkand42186_gauti_balsai_apygardoje7131.html">Juozas JAKAVIČIUS</a></td><td></td><td>2709</td><td>36</td><td>2745</td><td>1,39%</td><td>1</td></tr>
<tr><td>Iš viso:</td><td>179002</td><td>7238</td><td>186240</td><td></td><td>51</td></tr>
</table>
<h3>Balsavimo rezultatai rinkimų apylinkėse</h3>
<table><tr><td>Iš viso:</td><td>437109</td><td>192405</td><td>44,02%</td></tr></table>
</body></html>
"""

COMPOSITION_2011_HTML = """
<p>Mandatų skaičius: 51</p>
<table>
<tr><td>Artūro Zuoko ir Vilniaus koalicija</td><td><a href="/statiniai/puslapiai/rinkimai/409_lt/Kandidatai/Kandidatas42680/Kandidato42680Anketa.html">ZUOKAS ARTŪRAS</a></td><td></td></tr>
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

    def test_2011_page_has_individuals_plain_totals_and_no_mayor(self):
        parsed = parse_municipality_results_page(MUNICIPALITY_2011_HTML, "https://www.vrk.lt/statiniai/puslapiai/t/output_lt/rezultatai_daugiamand_apygardose/apygardos_rezultatai7131.html")
        self.assertEqual([(l["listId"], l["mandates"]) for l in parsed["lists"]], [("3994", 12)])
        self.assertEqual(
            [(i["vrkCandidateId"], i["name"], i["mandates"]) for i in parsed["individuals"]],
            [("42302", "Darius NORKUS", 0), ("42186", "Juozas JAKAVIČIUS", 1)],
        )
        # The totals row has no percentage columns here; the seat total is
        # still its last cell, read from the table rather than a regex over
        # the page text — which would otherwise pick up the turnout table.
        self.assertEqual(parsed["listMandatesTotal"], 51)
        self.assertEqual(parsed["mayoralField"], [])
        self.assertIsNone(parsed["mayorVerdictName"])
        # The 2015 page still reads the same way.
        parsed_2015 = parse_municipality_results_page(MUNICIPALITY_HTML, "https://x/apygardos_rezultatai7761.html")
        self.assertEqual(parsed_2015["individuals"], [])
        self.assertEqual(parsed_2015["listMandatesTotal"], 24)

    def test_composition_page_without_a_mayor(self):
        parsed = parse_composition_page(COMPOSITION_2011_HTML)
        self.assertEqual(parsed["mandates"], 51)
        self.assertEqual([(m["vrkCandidateId"], m["recognized"], m["mayor"]) for m in parsed["members"]], [("42680", None, False)])

    def test_ranking_rows_carry_rank_position_id_and_mayor_marker(self):
        rows = parse_list_ranking_page(RANKING_HTML, "https://x/")
        self.assertEqual([(r["rank"], r["preElectionPosition"], r["vrkCandidateId"], r["mayorElect"]) for r in rows], [(1, 1, "84013", True), (2, 2, "84014", False), (3, 3, "84015", False)])

    def test_composition_page_reads_both_tables(self):
        parsed = parse_composition_page(COMPOSITION_HTML)
        self.assertEqual(parsed["mandates"], 25)
        self.assertEqual([(m["vrkCandidateId"], m["recognized"], m["mayor"]) for m in parsed["members"]], [("84013", "2015-03-22", True), ("84014", "2015-03-22", False), ("84015", "2015-03-22", False)])


MUNICIPALITY_2007_HTML = """
<table>
<tr><th>Sąrašo numeris</th><th>Pavadinimas</th><th>balsadėžėse</th><th>paštu</th><th>iš viso</th><th>Mandatų skaičius</th></tr>
<tr><td>3.</td><td><a href="../rorg_kand_rapg/rapg_kand6783_2300.html">Koalicija "Už Neringos ateitį"</a></td><td>455</td><td>30</td><td>485</td><td>7</td></tr>
<tr><td>24.</td><td><a href="../rorg_kand_rapg/rapg_kand6783_2278.html">Naujoji sąjunga (socialliberalai)</a></td><td>308</td><td>31</td><td>339</td><td>5</td></tr>
<tr><th>&nbsp;</th><th align="right"><b>Iš viso:</b></th><th><b>1436</b></th><th><b>138</b></th><th><b>1574</b></th><th><b>12</b></th></tr>
</table>
<a href="../kand_mandatai_rapyg/kand_mand_rapyg6783.html">Mandatus gavę kandidatai</a>
"""

MANDATES_2007_HTML = """
<table>
<tr><th>Pavardė, vardas</th><th>Iškėlė</th><th>Porinkiminis numeris sąraše</th></tr>
<tr><td><a href="/statiniai/puslapiai/rinkimai/3/Kandidatai/Kandidatas2544/Kandidato2544Anketa.html">GIEDRAITIS VIGANTAS</a></td><td>Koalicija "Už Neringos ateitį"</td><td>1</td></tr>
<tr><td><a href="/statiniai/puslapiai/rinkimai/3/Kandidatai/Kandidatas6014/Kandidato6014Anketa.html">PUKELIS ALGIMANTAS</a></td><td>Lietuvos socialdemokratų partija</td><td>1</td></tr>
</table>
"""


class Municipal2007PageTests(unittest.TestCase):
    def test_results_page_reads_lists_th_total_and_mandates_link(self):
        url = "https://www.vrk.lt/statiniai/puslapiai/2007_savivaldybiu_tarybu_rinkimai/balsu_uz_partijas_skaiciavimas/rinkimu_apygardos/rapgpl_6783.html"
        parsed = parse_municipality_results_page_2007(MUNICIPALITY_2007_HTML, url)
        self.assertEqual([(l["listName"], l["listId"], l["mandates"]) for l in parsed["lists"]], [('Koalicija "Už Neringos ateitį"', "2300", 7), ("Naujoji sąjunga (socialliberalai)", "2278", 5)])
        # The total row is <th> cells with a blank first cell.
        self.assertEqual(parsed["listMandatesTotal"], 12)
        self.assertEqual(parsed["mandatesPageUrl"], "https://www.vrk.lt/statiniai/puslapiai/2007_savivaldybiu_tarybu_rinkimai/balsu_uz_partijas_skaiciavimas/kand_mandatai_rapyg/kand_mand_rapyg6783.html")

    def test_mandates_page_rows_carry_id_list_and_rank(self):
        rows = parse_mandates_page_2007(MANDATES_2007_HTML)
        self.assertEqual(
            [(r["vrkCandidateId"], r["name"], r["listName"], r["rank"]) for r in rows],
            [("2544", "GIEDRAITIS VIGANTAS", 'Koalicija "Už Neringos ateitį"', 1), ("6014", "PUKELIS ALGIMANTAS", "Lietuvos socialdemokratų partija", 1)],
        )


class ResultsLookupTests(unittest.TestCase):
    def test_missing_file_means_unknown_not_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_results_lookup(Path(tmp) / "none.results.json"))
            path = Path(tmp) / "x.results.json"
            path.write_text(json.dumps({"elected": {"1": {"seat": "meras"}}}), encoding="utf-8")
            self.assertEqual(load_results_lookup(path), {"1": {"seat": "meras"}})

    def test_an_empty_map_without_the_statement_is_unknown_not_lost(self):
        # An empty join used to read as "everyone lost" -- worse than no file
        # at all, which at least left isrinktas unknown (issue #134).
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.results.json"
            path.write_text(json.dumps({"elected": {}, "sources": [], "stats": {}}), encoding="utf-8")
            self.assertIsNone(load_results_lookup(path))

    def test_an_empty_map_the_builder_vouched_for_is_a_known_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.results.json"
            path.write_text(json.dumps({"elected": {}, election_results.NOBODY_ELECTED_KEY: True}), encoding="utf-8")
            self.assertEqual(load_results_lookup(path), {})


class WriteResultsTests(unittest.TestCase):
    """A results file with nobody in it has to say so, or it is not written."""

    def test_an_unexplained_empty_map_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.results.json"
            with self.assertRaises(ValueError):
                election_results.write_results(path, "e", {}, {"winnersResolved": 0}, [])
            self.assertFalse(path.exists())

    def test_nobody_elected_is_written_into_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.results.json"
            election_results.write_results(path, "e", {}, {}, ["https://x"], nobody_elected=True)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIs(payload[election_results.NOBODY_ELECTED_KEY], True)
            self.assertEqual(load_results_lookup(path), {})

    def test_winners_and_nobody_elected_contradict(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                election_results.write_results(Path(tmp) / "x.json", "e", {"1": {"seat": "meras"}}, {}, [], nobody_elected=True)

    def test_a_results_file_with_winners_needs_no_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.results.json"
            election_results.write_results(path, "e", {"1": {"seat": "meras"}}, {}, [])
            self.assertNotIn(election_results.NOBODY_ELECTED_KEY, json.loads(path.read_text(encoding="utf-8")))


class OptionalPageFetchTests(unittest.TestCase):
    """The page families a tree may not publish: absent means 404 and nothing
    else. Every other failure used to be swallowed into an empty result, so a
    build with the network down wrote a file marking everyone `false`."""

    @staticmethod
    def _http_error(status: int) -> requests.HTTPError:
        response = requests.Response()
        response.status_code = status
        return requests.HTTPError(f"{status}", response=response)

    def test_a_404_is_an_absent_page_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(election_results, "fetch_text", side_effect=self._http_error(404)):
                self.assertEqual(election_results.seimo_district_pages(Path(tmp), "2013_seimo_rinkimai", 2), [])
                self.assertEqual(election_results.first_round_elected_by_label(Path(tmp), "2013_seimo_rinkimai"), {})
                self.assertEqual(election_results.municipal_index_pages(Path(tmp), "2015_savivaldybiu_tarybu_rinkimai", 2), [])

    def test_a_connection_error_propagates(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(election_results, "fetch_text", side_effect=requests.ConnectionError("down")):
                with self.assertRaises(requests.ConnectionError):
                    election_results.seimo_district_pages(Path(tmp), "2013_seimo_rinkimai", 1)
                with self.assertRaises(requests.ConnectionError):
                    election_results.first_round_elected_by_label(Path(tmp), "2013_seimo_rinkimai")
                with self.assertRaises(requests.ConnectionError):
                    election_results.municipal_index_pages(Path(tmp), "2015_savivaldybiu_tarybu_rinkimai", 1)

    def test_a_server_error_propagates_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(election_results, "fetch_text", side_effect=self._http_error(503)):
                with self.assertRaises(requests.HTTPError):
                    election_results.fetch_optional_page(Path(tmp), "https://www.vrk.lt/x.html")

    def test_a_build_with_the_network_down_raises_rather_than_writing(self):
        # The issue's reproduction: build_results() for a Seimas by-election
        # with fetch_text raising returned normally after four failed fetches
        # and wrote elected={}, sources=[].
        with tempfile.TemporaryDirectory() as tmp:
            sitemap = Path(tmp) / "sitemap.json"
            sitemap.write_text(json.dumps({"entries": []}), encoding="utf-8")
            output = Path(tmp) / "out.results.json"
            with mock.patch.object(election_results, "fetch_text", side_effect=requests.ConnectionError("down")):
                with self.assertRaises(requests.ConnectionError):
                    election_results.build_seimo_constituency_results(
                        "2013-kovo-3-seimo-birzai-zarasai-ukmerge", "2013_seimo_rinkimai", sitemap, Path(tmp) / "pages", output
                    )
            self.assertFalse(output.exists())

    def test_the_four_elections_nobody_won_say_so(self):
        for election_id in (
            "1998-kovo-22-seimo-pakartotiniai",
            "1998-lapkricio-15-seimo-pakartotiniai",
            "1999-kovo-21-seimo-pakartotiniai",
            "2003-birzelio-15-seimo-nauji",
        ):
            with self.subTest(election_id):
                payload = _results(election_id)
                self.assertEqual(payload["elected"], {})
                self.assertIs(payload.get(election_results.NOBODY_ELECTED_KEY), True)
                self.assertEqual(payload["stats"]["constituenciesNotHeld"], payload["stats"]["constituencies"])


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

    def test_2011_municipal_general(self):
        payload = _results("2011-vasario-27-savivaldybiu")
        stats = payload["stats"]
        self.assertEqual(stats["municipalities"], 60)
        # No mayor was elected directly in 2011.
        self.assertEqual(stats["mayorsResolved"], 0)
        self.assertEqual(stats["mayorsUnresolved"], 0)
        self.assertEqual(stats["seats"], {"tarybos-narys": 1526})
        # Eighteen self-nominated individuals won a seat on their own row of
        # the results table; everyone else through a list's ranking.
        self.assertEqual(stats["councilSelfNominated"], 18)
        self.assertEqual(stats["councilNotInSitemap"], 0)
        self.assertEqual(stats["councilResolvedByNameAndList"], 0)
        self.assertEqual(stats["seatCountMismatches"], 0)
        self.assertEqual(stats["annulledWinners"], 0)
        # Every derived winner is on VRK's own composition page of their
        # council, in all sixty municipalities.
        self.assertEqual(stats["compositionPagesChecked"], 60)
        self.assertEqual(stats["compositionFullyContainsDerived"], 60)
        self.assertEqual(stats["derivedNotInComposition"], 0)
        individual = [v for v in payload["elected"].values() if v["method"] == "self-nominated"]
        self.assertEqual(len(individual), 18)
        self.assertTrue(all("listName" not in v for v in individual))
        self.assertEqual(payload["elected"]["42680"]["municipality"], "57. Vilniaus miesto")

    def test_2007_municipal_general(self):
        payload = _results("2007-vasario-25-savivaldybiu")
        stats = payload["stats"]
        self.assertEqual(stats["municipalities"], 60)
        self.assertEqual(stats["seats"], {"tarybos-narys": 1550})
        # Every winner is on the municipality's mandates page with an
        # anketa link, so every one is joined by id, none by name.
        self.assertEqual(stats["winnersOnPages"], 1550)
        self.assertEqual(stats["councilNotInSitemap"], 0)
        self.assertEqual(stats["municipalityMismatches"], 0)
        # Per municipality, the winners equal the results table's "Iš viso"
        # mandate total and the sum of the lists' mandates, and the
        # composition page (a 2010 snapshot) states the same council size.
        self.assertEqual(stats["seatCountMismatches"], 0)
        self.assertEqual(stats["compositionPagesChecked"], 60)
        self.assertEqual(stats["compositionMandateMismatches"], 0)
        self.assertTrue(all(v["method"] == "mandates-page" for v in payload["elected"].values()))
        self.assertEqual(payload["elected"]["12711"]["municipality"], "57. Vilniaus miesto")
        self.assertEqual((payload["elected"]["9852"]["listName"], payload["elected"]["9852"]["rank"]), ("Darbo partija", 3))
        self.assertEqual(len(payload["sources"]), 60)

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
