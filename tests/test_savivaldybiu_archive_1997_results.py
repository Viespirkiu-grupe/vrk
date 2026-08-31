"""The 1997 municipal-council elected-status join (issue #92).

Three layers, none of them touching the network: the page parsers on
synthetic HTML shaped like VRK's `rapgpl`/`rikl` pages (including the voided
Švenčionys March pages, which print an invalidation decision instead of
winners), the per-record join that writes `isrinktas` onto the family's
kandidatavimas *dict*, and pins of the two built results files'
reconciliation stats — the numbers checked against VRK's own mandate columns
when the join shipped.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scraper.shared.savivaldybiu_archive_1997_results import (
    apply_municipal_results,
    load_municipal_results,
    municipal_results_targets,
    parse_elected_page,
    parse_list_votes_page,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SITEMAPS = REPO_ROOT / "sitemaps"

ARCHIVE = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/19970323/"


def _results(election_id: str) -> dict:
    return json.loads((SITEMAPS / f"{election_id}.results.json").read_text(encoding="utf-8"))


# One municipality's rapgpl page: the heading, the nav link to its elected
# page, the turnout block, and the six-column list table with an "Iš viso"
# totals row. A list below the threshold prints "-" in the mandate column.
VOTES_HTML = """
<html><body>
<p align="center"><font size="2"> | <a href="/statiniai/puslapiai/n/rinkimai/19970323/rikl.htm-264.htm">Apygardoje&nbsp;išrinkti&nbsp;kandidatai</a> | </font></p>
<p align="center"><font size="4"><b>Švenčionių rajono (Nr. 47) apygarda</b></font></p>
<p align="center"><font size="5"><b>Balsavimo rezultatai</b></font></p>
<p> Rinkimų apygardos rinkėjų skaičius: <b>26446</b><br />
Rinkimuose dalyvavusių apygardos rinkėjų skaičius: <b>12885</b> (<b>48.72%</b> bendro rinkėjų skaičiaus)<br />
Apygardoje negaliojančių biuletenių skaičius: <b>331</b> (<b>2.57%</b> bendro biuletenių skaičiaus)<br />
Apygardoje galiojančių biuletenių skaičius: <b>12554</b> (<b>97.43%</b> bendro biuletenių skaičiaus)</p>
<table border="1">
<tr><td rowspan="2"><b>Sąrašo<br />eilės Nr.</b></td><td rowspan="2"><b>Partijos, politinės organizacijos ar<br />koalicijos pavadinimas</b></td><td colspan="3"><b>Paduotų balsų skaičius</b></td><td rowspan="2"><b>Mandatų skaičius</b></td></tr>
<tr><td><b>balsadėžėse rastų</b></td><td><b>paštu gautų</b></td><td><b>iš viso</b></td></tr>
<tr><td>7.</td><td><a href="/statiniai/puslapiai/n/rinkimai/19970323/pkal.htm-264+28.htm">Lietuvos liberalų sąjunga</a></td><td>3755&nbsp;</td><td>1058&nbsp;</td><td>4813&nbsp;</td><td><b>10</b></td></tr>
<tr><td>1.</td><td><a href="/statiniai/puslapiai/n/rinkimai/19970323/pkal.htm-264+22.htm">Lietuvių tautininkų sąjunga</a></td><td>235&nbsp;</td><td>63&nbsp;</td><td>298&nbsp;</td><td><b>-</b></td></tr>
<tr><td>&nbsp;</td><td><b>Iš viso:</b></td><td><b>3990&nbsp;</b></td><td><b>1121&nbsp;</b></td><td><b>5111&nbsp;</b></td><td><b>10</b></td></tr>
</table>
</body></html>
"""

# The voided March Švenčionys page: VRK's decision in place of a winner set,
# an all-blank mandate column, and no elected-page link at all.
VOIDED_VOTES_HTML = """
<html><body>
<p align="center"><font size="4"><b>Švenčionių rajono (Nr. 47) apygarda</b></font></p>
<p align="center"><font size="5"><b>Balsavimo rezultatai</b></font></p>
<p>Dėl šiurkščių savivaldybių tarybų rinkimų įstatymo pažeidimų, Vyriausiosios
rinkimų komisijos 1997 m. kovo 29 d. sprendimu Nr. 149 rinkimų rezultatai šioje
apygardoje pripažinti negaliojančiais. Vyriausiosios rinkimų komisijos 1997 m.
balandžio 3 d. sprendimu Nr. 162 pakartotiniai rinkimai rengiami
1997 m. birželio 29 d.</p>
<p> Rinkimų apygardos rinkėjų skaičius: <b>26311</b><br />
Rinkimuose dalyvavusių apygardos rinkėjų skaičius: <b>14854</b> (<b>56.46%</b> bendro rinkėjų skaičiaus)</p>
<table border="1">
<tr><td rowspan="2"><b>Sąrašo eilės Nr.</b></td><td rowspan="2"><b>Partijos, politinės organizacijos ar koalicijos pavadinimas</b></td><td colspan="3"><b>Paduotų balsų skaičius</b></td><td rowspan="2"><b>Mandatų skaičius</b></td></tr>
<tr><td><b>balsadėžėse rastų</b></td><td><b>paštu gautų</b></td><td><b>iš viso</b></td></tr>
<tr><td>12.</td><td><a href="/statiniai/puslapiai/n/rinkimai/19970323/pkal.htm-190+28.htm">Lietuvos liberalų sąjunga</a></td><td>3943&nbsp;</td><td>2106&nbsp;</td><td>6049&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>&nbsp;</td><td><b>Iš viso:</b></td><td><b>14339&nbsp;</b></td><td>&nbsp;</td><td>&nbsp;</td><td><b>25</b></td></tr>
</table>
</body></html>
"""

# One municipality's rikl page: an <ol> with one <li> per seat, each linking
# the member's own candidate page (so the row carries VRK's candidate id),
# the nominating list and the pre-election position on it.
ELECTED_HTML = """
<html><body>
<p align="center"><font size="4"><b>Švenčionių rajono (Nr. 47) apygarda</b></font></p>
<p align="center"><font size="5"><b>Išrinkti kandidatai</b></font></p>
<ol>
<li>&nbsp;<a href="/statiniai/puslapiai/n/rinkimai/19970323/kandvl.htm-43469.htm">Klipčius Rimas</a><font size="2"> --- iškėlė <a href="/statiniai/puslapiai/n/rinkimai/19970323/pkal.htm-264+28.htm">Lietuvos liberalų sąjunga</a>, numeris sąraše - <b>1</b></font></li>
<li>&nbsp;<a href="/statiniai/puslapiai/n/rinkimai/19970323/kandvl.htm-43565.htm">Jurkevič Ana</a><font size="2"> --- iškėlė <a href="/statiniai/puslapiai/n/rinkimai/19970323/pkal.htm-264+34.htm">Lietuvos lenkų rinkimų akcija</a>, numeris sąraše - <b>1</b></font></li>
</ol>
</body></html>
"""


class VotesPageTests(unittest.TestCase):
    def test_lists_totals_turnout_and_elected_link(self):
        page = parse_list_votes_page(VOTES_HTML, ARCHIVE + "rapgpl.htm-264.htm")
        self.assertEqual(page["municipalityName"], "Švenčionių rajono")
        self.assertEqual(page["municipalityNumber"], 47)
        self.assertIsNone(page["invalidationNotice"])
        self.assertEqual(page["electedUrl"], ARCHIVE + "rikl.htm-264.htm")
        self.assertEqual(page["totalMandates"], 10)
        self.assertEqual(page["totalVotes"], 5111)
        self.assertEqual(
            page["turnout"],
            {
                "registeredVoters": 26446,
                "voters": 12885,
                "turnoutPercent": 48.72,
                "invalidBallots": 331,
                "validBallots": 12554,
            },
        )
        self.assertEqual(
            page["lists"],
            [
                {
                    "listNumber": 7,
                    "name": "Lietuvos liberalų sąjunga",
                    "partyId": "28",
                    "votesBallotBox": 3755,
                    "votesPostal": 1058,
                    "votes": 4813,
                    "mandates": 10,
                },
                {
                    "listNumber": 1,
                    "name": "Lietuvių tautininkų sąjunga",
                    "partyId": "22",
                    "votesBallotBox": 235,
                    "votesPostal": 63,
                    "votes": 298,
                    # "-" is below-the-threshold, a stated nothing.
                    "mandates": None,
                },
            ],
        )

    def test_the_voided_page_states_the_decision_and_links_no_elected_page(self):
        page = parse_list_votes_page(VOIDED_VOTES_HTML, ARCHIVE + "rapgpl.htm-190.htm")
        self.assertIn("pripažinti negaliojančiais", page["invalidationNotice"])
        self.assertIsNone(page["electedUrl"])
        # The votes were still published; only the mandate column is blank.
        self.assertEqual(page["lists"][0]["votes"], 6049)
        self.assertIsNone(page["lists"][0]["mandates"])


class ElectedPageTests(unittest.TestCase):
    def test_members_carry_id_nominator_and_position(self):
        page = parse_elected_page(ELECTED_HTML, ARCHIVE + "rikl.htm-264.htm")
        self.assertEqual(page["municipalityNumber"], 47)
        self.assertIsNone(page["invalidationNotice"])
        self.assertEqual(
            page["members"],
            [
                {
                    "vrkCandidateId": "43469",
                    "name": "Klipčius Rimas",
                    "nominator": "Lietuvos liberalų sąjunga",
                    "nominatorUrl": ARCHIVE + "pkal.htm-264+28.htm",
                    "listPosition": 1,
                },
                {
                    "vrkCandidateId": "43565",
                    "name": "Jurkevič Ana",
                    "nominator": "Lietuvos lenkų rinkimų akcija",
                    "nominatorUrl": ARCHIVE + "pkal.htm-264+34.htm",
                    "listPosition": 1,
                },
            ],
        )


class TargetsTests(unittest.TestCase):
    def _write(self, directory: Path, number: int, html: str) -> None:
        (directory / f"apgtl-{number}.html").write_text(html, encoding="utf-8")

    def test_targets_read_the_pages_own_results_link(self):
        # The rapgpl suffix is VRK's internal id, not the municipality
        # number — municipality 1 links rapgpl.htm-144.htm — so the target
        # list must come off the page, never be derived.
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self._write(
                directory,
                1,
                '<p><font size="5"><b>Vilniaus miesto (Nr. 1) apygarda</b></font></p>'
                '<a href="/statiniai/puslapiai/n/rinkimai/19970323/rapgpl.htm-144.htm">Balsavimo rezultatai</a>',
            )
            self.assertEqual(
                municipal_results_targets(directory),
                [
                    {
                        "municipalityName": "Vilniaus miesto",
                        "municipalityNumber": 1,
                        "resultsUrl": ARCHIVE + "rapgpl.htm-144.htm",
                    }
                ],
            )

    def test_a_page_heading_disagreeing_with_its_filename_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self._write(
                directory,
                2,
                '<p><font size="5"><b>Vilniaus miesto (Nr. 1) apygarda</b></font></p>'
                '<a href="rapgpl.htm-144.htm">Balsavimo rezultatai</a>',
            )
            with self.assertRaises(ValueError):
                municipal_results_targets(directory)


def _candidacy() -> dict:
    """One record's `kandidatavimas` — a single dict in this family."""
    return {
        "savivaldybe": "Švenčionių rajono",
        "savivaldybes-numeris": 47,
        "savivaldybes-nuoroda": ARCHIVE + "apgtl.htm-5+47.htm",
        "iskele": "Lietuvos liberalų sąjunga",
        "iskele-nuoroda": ARCHIVE + "pkal.htm-264+28.htm",
        "numeris-sarase": 1,
    }


WINNER = {
    "seat": "tarybos-narys",
    "method": "elected-page",
    "sourceUrl": ARCHIVE + "rikl.htm-264.htm",
    "municipality": "Švenčionių rajono",
    "municipalityNumber": 47,
    "nominator": "Lietuvos liberalų sąjunga",
    "listPosition": 1,
}


class ApplyResultsTests(unittest.TestCase):
    def test_no_results_file_leaves_the_candidacy_untouched(self):
        candidacy = _candidacy()
        self.assertEqual(apply_municipal_results(candidacy, "43469", {}), [])
        self.assertEqual(candidacy, _candidacy())

    def test_a_win_writes_the_three_keys(self):
        candidacy = _candidacy()
        results = {"elected": {"43469": WINNER}, "invalidated": {}}
        self.assertEqual(apply_municipal_results(candidacy, "43469", results), [])
        self.assertIs(candidacy["isrinktas"], True)
        self.assertEqual(candidacy["isrinktas-kaip"], "tarybos-narys")
        self.assertEqual(candidacy["rezultatu-saltinis"], ARCHIVE + "rikl.htm-264.htm")

    def test_a_non_winner_is_a_known_false_not_a_missing_key(self):
        candidacy = _candidacy()
        results = {"elected": {"43469": WINNER}, "invalidated": {}}
        self.assertEqual(apply_municipal_results(candidacy, "99999", results), [])
        self.assertIs(candidacy["isrinktas"], False)
        self.assertNotIn("isrinktas-kaip", candidacy)
        self.assertNotIn("rezultatu-saltinis", candidacy)

    def test_the_voided_municipality_carries_the_decision(self):
        candidacy = _candidacy()
        results = {
            "elected": {},
            "invalidated": {
                47: {
                    "municipalityNumber": 47,
                    "notice": "… pripažinti negaliojančiais …",
                    "sourceUrl": ARCHIVE + "rapgpl.htm-190.htm",
                }
            },
        }
        self.assertEqual(apply_municipal_results(candidacy, "39000", results), [])
        self.assertIs(candidacy["isrinktas"], False)
        self.assertEqual(
            candidacy["rezultatai-negalioja"],
            {
                "pastaba": "… pripažinti negaliojančiais …",
                "saltinis": ARCHIVE + "rapgpl.htm-190.htm",
            },
        )

    def test_a_winner_row_disagreeing_with_the_card_is_reported(self):
        # The elected page renumbers a list after a withdrawal on 31 of the
        # general election's 1,459 rows, so the card's position and the
        # page's can genuinely differ — reported, never silently preferred.
        candidacy = _candidacy()
        results = {
            "elected": {"43469": {**WINNER, "listPosition": 2}},
            "invalidated": {},
        }
        problems = apply_municipal_results(candidacy, "43469", results)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["eventType"], "ElectedCandidacyMismatch")
        self.assertEqual(
            problems[0]["detail"], {"listPosition": {"card": 1, "results": 2}}
        )
        # The disagreement does not unmake the win — the join keys on id.
        self.assertIs(candidacy["isrinktas"], True)

    def test_load_returns_empty_for_a_missing_file(self):
        self.assertEqual(load_municipal_results(None), {})
        self.assertEqual(load_municipal_results(Path("no/such/file.json")), {})


class BuiltResultsFileTests(unittest.TestCase):
    """Pins of the two built files' reconciliation stats.

    1997-03-23 seated 1,459 councillors across 55 municipalities; the 56th —
    Švenčionių rajono (Nr. 47), 25 seats — was voided by VRK decision Nr. 149
    and re-run on 1997-06-29, which seated its 25. Every member is in its
    election's sitemap and every municipality's member count equals its own
    mandate column and totals row.
    """

    def test_the_general_election(self):
        payload = _results("1997-kovo-23-savivaldybiu-tarybu")
        self.assertEqual(
            payload["stats"],
            {
                "municipalities": 56,
                "invalidatedMunicipalities": 1,
                "candidates": 6276,
                "elected": 1459,
                "electedNotInSitemap": 0,
                # 31 elected rows print a list position 1-3 below the
                # listing's — a renumbering after withdrawals, all in the
                # page's favour of the smaller number. Recorded, and the
                # same 31 records carry an ElectedCandidacyMismatch warning.
                "memberMismatches": 31,
                "seatCountMismatches": 0,
                "candidatesNotElected": 4817,
                "seats": {"tarybos-narys": 1459},
            },
        )
        voided = payload["details"]["invalidated"]
        self.assertEqual(len(voided), 1)
        self.assertEqual(voided[0]["municipalityNumber"], 47)
        self.assertIn("pripažinti negaliojančiais", voided[0]["notice"])
        mismatches = payload["details"]["memberMismatches"]
        self.assertTrue(
            all(set(row["diffs"]) == {"listPosition"} for row in mismatches)
        )

    def test_the_svencionys_repeat(self):
        payload = _results("1997-birzelio-29-svenciniu-tarybos-pakartotiniai")
        self.assertEqual(
            payload["stats"],
            {
                "municipalities": 1,
                "invalidatedMunicipalities": 0,
                "candidates": 110,
                "elected": 25,
                "electedNotInSitemap": 0,
                "memberMismatches": 0,
                "seatCountMismatches": 0,
                "candidatesNotElected": 85,
                "seats": {"tarybos-narys": 25},
            },
        )


if __name__ == "__main__":
    unittest.main()
