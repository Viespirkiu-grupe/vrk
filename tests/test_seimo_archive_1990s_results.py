"""The 1996-1999 Seimas archive elected-status join (issue #79).

Three layers, none of them touching the network: the page parsers on synthetic
HTML shaped like VRK's `rapgpl` pages (so a regression in a regex, a column
offset or the mojibake repair fails here), the per-candidacy join that writes
`isrinktas` onto a record whose `kandidatavimas` is a *list*, and pins of the
six built results files' reconciliation stats — the numbers checked against
VRK's own counts when the join shipped.
"""

import json
import unittest
from pathlib import Path

from scraper.shared.seimo_archive_1990s_results import (
    apply_results,
    candidate_id_from_url,
    collect_constituency_votes,
    name_key,
    parse_constituency_results,
    parse_elected_members,
    parse_list_results,
    parse_ranking_page,
    repair_baltic_text,
    resolve_by_name,
    resolve_page_winners,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SITEMAPS = REPO_ROOT / "sitemaps"

ARCHIVE = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/"


def _results(election_id: str) -> dict:
    return json.loads((SITEMAPS / f"{election_id}.results.json").read_text(encoding="utf-8"))


# The 1996/1998/1999 page: a round heading, a verdict, the turnout block and a
# four-column table whose rows link `kandvl.htm-<ID>.htm`.
ROUND_TWO_HTML = """
<html><body>
<p align="center"><font size="5"><b>Naujamiesčio (Nr. 1) apygarda</b></font></p>
<p align="center"><font size="2"><b>2-OJO BALSAVIMO TURO REZULTATAI</b></font></p>
<p>Seimo nariu išrinktas <a href="/statiniai/puslapiai/n/rinkimai/seim96/kandvl.htm-17730.htm">Audrius&nbsp;Butkevičius</a>.<br />
Rinkimų apygardos rinkėjų skaičius: <b>33878</b><br />
Rinkimuose dalyvavusių apygardos rinkėjų skaičius: <b>15862</b> (<b>46.82%</b> bendro rinkėjų skaičiaus)<br />
Apygardoje negaliojančių biuletenių skaičius: <b>617</b> (<b>3.89%</b> bendro biuletenių skaičiaus)<br />
Apygardoje galiojančių biuletenių skaičius: <b>15245</b> (<b>96.11%</b> bendro biuletenių skaičiaus)</p>
<table>
<tr><td rowspan="2"><font size="5"><b>Kandidatas</b></font></td><td colspan="3"><b>Gautų balsų skaičius</b></td></tr>
<tr><td><b>Apygardoje</b></td><td><b>Pašte</b></td><td><b>Iš viso</b></td></tr>
<tr><td><a href="/statiniai/puslapiai/n/rinkimai/seim96/kandvl.htm-17730.htm">Audrius&nbsp;Butkevičius</a></td><td>8784&nbsp;</td><td>337&nbsp;</td><td>9121&nbsp;</td></tr>
<tr><td><a href="/statiniai/puslapiai/n/rinkimai/seim96/kandvl.htm-18083.htm">Andrius&nbsp;Kubilius</a></td><td>5916&nbsp;</td><td>208&nbsp;</td><td>6124&nbsp;</td></tr>
<tr><td align="right"><b>Iš viso:&nbsp;&nbsp;&nbsp;</b></td><td><b>14700&nbsp;</b></td><td><b>545&nbsp;</b></td><td><b>15245&nbsp;</b></td></tr>
</table>
</body></html>
"""

NOT_HELD_HTML = """
<html><body>
<p align="center"><font size="5"><b>Naujosios Vilnios (Nr. 10) apygarda</b></font></p>
<p align="center"><font size="2"><b>1-OJO BALSAVIMO TURO REZULTATAI</b></font></p>
<p>Rinkimai apygardoje <b>neįvyko</b>.<br />
Rinkimų apygardos rinkėjų skaičius: <b>40215</b><br />
Rinkimuose dalyvavusių apygardos rinkėjų skaičius: <b>7967</b> (<b>19.81%</b> bendro rinkėjų skaičiaus)<br />
Apygardoje negaliojančių biuletenių skaičius: <b>267</b> (<b>3.35%</b> bendro biuletenių skaičiaus)<br />
Apygardoje galiojančių biuletenių skaičius: <b>7700</b> (<b>96.65%</b> bendro biuletenių skaičiaus)</p>
<table>
<tr><td rowspan="2"><font size="5"><b>Kandidatas</b></font></td><td colspan="3"><b>Gautų balsų skaičius</b></td></tr>
<tr><td><b>Apygardoje</b></td><td><b>Pašte</b></td><td><b>Iš viso</b></td></tr>
<tr><td><a href="kandvl.htm-65088.htm">Eduardas&nbsp;Šablinskas</a></td><td>2685</td><td>50</td><td>2735</td></tr>
<tr><td><a href="kandvl.htm-65099.htm">Zbignev&nbsp;Balcevič</a></td><td>1665</td><td>55</td><td>1720</td></tr>
</table>
</body></html>
"""

RUNOFF_NEEDED_HTML = NOT_HELD_HTML.replace(
    "Rinkimai apygardoje <b>neįvyko</b>.",
    "Rinkimai apygardoje <b>įvyko</b>.<br />Reikalingas antras rinkimų turas. "
    "Jame dalyvauja du kandidatai, surinkę daugiausiai balsų.",
)

# The 1998-03-22 pair: the same page with no candidate id anywhere — its rows
# link hand-numbered `kandvl2.htm` pages instead.
NO_IDS_HTML = NOT_HELD_HTML.replace("kandvl.htm-65088.htm", "kandvl.htm").replace(
    "kandvl.htm-65099.htm", "kandvl2.htm"
)

# The 1997-03-23 capture: Windows-1257 re-encoded as Latin-1 HTML entities,
# the other table header, no round heading, and the verdict after the turnout
# block rather than before it.
MOJIBAKE_HTML = """
<html><body>
<p align="center"><font size="5">Vilniaus &ETH;al&egrave;inink&oslash; (Nr. 56) apygarda</font></p>
<p align="center"><font size="4">Balsavimo rezultatai</font></p>
<p> Rinkim&oslash; apygardos rink&euml;j&oslash; skai&egrave;ius: <b>39219</b><br />
Rinkimuose dalyvavusi&oslash; apygardos rink&euml;j&oslash; skai&egrave;ius: <b>18509</b> (<b>47.19%</b> bendro rink&euml;j&oslash; skai&egrave;iaus)<br />
Apygardoje negaliojan&egrave;i&oslash; biuleteni&oslash; skai&egrave;ius: <b>1067</b> (<b>7.49%</b> bendro biuleteni&oslash; skai&egrave;iaus)<br />
Apygardoje galiojan&egrave;i&oslash; biuleteni&oslash; skai&egrave;ius: <b>13184</b> (<b>92.51%</b> bendro biuleteni&oslash; skai&egrave;iaus)</p>
<p>Rinkimai apygardoje <b>&aacute;vyko</b>.<br />&Aacute; Seimo narius i&eth;rinktas
<a href="/statiniai/puslapiai/n/rinkimai/seimpk/kandvl.htm-39779.htm">Jan&nbsp;Senkevi&egrave;</a>.</p>
<table>
<tr><td rowspan="2"><font size="5"><b>Kandidatas</b></font></td><td colspan="3"><b>Paduot&oslash; bals&oslash; skai&egrave;ius</b></td></tr>
<tr><td><b>balsad&euml;&thorn;&euml;se rast&oslash;</b></td><td><b>pa&eth;tu gaut&oslash;</b></td><td><b>i&eth; viso</b></td></tr>
<tr><td><a href="/statiniai/puslapiai/n/rinkimai/seimpk/kandvl.htm-39779.htm">Jan&nbsp;Senkevi&egrave;</a></td><td>11481</td><td>4044</td><td>15525</td></tr>
<tr><td><a href="/statiniai/puslapiai/n/rinkimai/seimpk/kandvl.htm-40435.htm">Algimantas&nbsp;Rei&egrave;i&ucirc;nas</a></td><td>1703</td><td>214</td><td>1917</td></tr>
<tr><td align="right"><b>I&eth; viso:</b></td><td><b>13184</b></td><td><b>4258</b></td><td><b>18509</b></td></tr>
</table>
</body></html>
"""

MEMBERS_HTML = """
<html><body>
<p align="center"><font size="4"><b>Kandidatai, išrinkti Seimo nariais</b></font></p>
<ol>
<li><a href="/statiniai/puslapiai/n/rinkimai/seim96/kandvl.htm-17800.htm">Akstinavičius Arvydas</a> -
<font size="2">iškėlė <a href="/statiniai/puslapiai/n/rinkimai/seim96/partr2l.htm-7.htm">Lietuvos socialdemokratų partija</a>, išrinktas(-a) pagal sąrašą</font></li>
<li><a href="/statiniai/puslapiai/n/rinkimai/seim96/kandvl.htm-16882.htm">Aleknaitė Abramikienė Vilija</a> -
<font size="2">iškėlė <a href="/statiniai/puslapiai/n/rinkimai/seim96/partr2l.htm-2.htm">Tėvynės sąjunga (Lietuvos konservatoriai)</a>, išrinktas(-a) II ture</font></li>
<li><a href="/statiniai/puslapiai/n/rinkimai/seim96/kandvl.htm-17730.htm">Butkevičius Audrius</a> -
<font size="2">išsikėlė pats(-i), išrinktas(-a) II ture</font></li>
<li><a href="/statiniai/puslapiai/n/rinkimai/seim96/kandvl.htm-18093.htm">Landsbergis Vytautas</a> -
<font size="2">iškėlė <a href="/statiniai/puslapiai/n/rinkimai/seim96/partr2l.htm-2.htm">Tėvynės sąjunga (Lietuvos konservatoriai)</a>, išrinktas(-a) I ture</font></li>
</ol>
</body></html>
"""

LIST_RESULTS_HTML = """
<html><body>
<table>
<tr><td><b>Partija ar politinė organizacija</b></td><td><b>Balsai už sąrašą</b></td><td><b>%</b></td><td><b>Mandatų skaičius</b></td></tr>
<tr><td><a href="/statiniai/puslapiai/n/rinkimai/seim96/rkreitl.htm-2.htm">Tėvynės sąjunga (Lietuvos konservatoriai)</a></td><td>409585</td><td>29.80%</td><td>33</td></tr>
<tr><td><a href="/statiniai/puslapiai/n/rinkimai/seim96/rkreitl.htm-7.htm">Lietuvos socialdemokratų partija</a></td><td>90756</td><td>6.60%</td><td>7</td></tr>
<tr><td>Lietuvos lenkų rinkimų akcija</td><td>40941</td><td>2.98%</td><td>-</td></tr>
</table>
</body></html>
"""

RANKING_HTML = """
<html><body>
<table>
<tr><td><b>Nr. sąraše</b></td><td><b>Kandidatas</b></td><td><b>Gavo teigiamų balsų</b></td><td><b>Gavo neigiamų balsų</b></td><td><b>Reitingo balai</b></td></tr>
<tr><td>1.</td><td><a href="/statiniai/puslapiai/n/rinkimai/seim96/kandvl.htm-18093.htm">Landsbergis Vytautas</a></td><td>121795</td><td>7290</td><td>59746260</td></tr>
<tr><td>3.</td><td><a href="/statiniai/puslapiai/n/rinkimai/seim96/kandvl.htm-18091.htm">Vagnorius Gediminas</a></td><td>87451</td><td>9275</td><td>54629232</td></tr>
<tr><td>2.</td><td><a href="/statiniai/puslapiai/n/rinkimai/seim96/kandvl.htm-16884.htm">Kunevičienė Elvyra Janina</a></td><td>64017</td><td>8995</td><td>52500591</td></tr>
</table>
</body></html>
"""


class MojibakeRepairTests(unittest.TestCase):
    def test_recovers_the_1997_03_capture(self):
        self.assertEqual(repair_baltic_text("Me\xe8islav Va\xf0kovi\xe8"), "Mečislav Vaškovič")
        self.assertEqual(repair_baltic_text("ne\xe1vyko"), "neįvyko")

    def test_leaves_correctly_encoded_text_alone(self):
        # These carry real Lithuanian letters, which have no Latin-1
        # encoding at all, so the round trip cannot fire.
        for value in ("Rinkimai apygardoje neįvyko", "Seimo nariu išrinktas Danutė Aleksiūnienė"):
            self.assertEqual(repair_baltic_text(value), value)

    def test_leaves_ascii_and_non_lithuanian_text_alone(self):
        self.assertEqual(repair_baltic_text("Iš viso: 15245"), "Iš viso: 15245")
        self.assertEqual(repair_baltic_text("Kandidatas"), "Kandidatas")
        # A round trip that recovers no Lithuanian letter is refused, so a
        # stray Latin-1 name is not silently rewritten.
        self.assertEqual(repair_baltic_text("Ren\xe9"), "Ren\xe9")


class NameKeyTests(unittest.TestCase):
    def test_name_order_does_not_matter(self):
        self.assertEqual(name_key("Artūras Paulauskas"), name_key("Paulauskas Artūras"))
        self.assertEqual(name_key("Kazimieras\xa0Jonas Jocius"), name_key("Jocius Kazimieras Jonas"))
        self.assertNotEqual(name_key("Antanas Baskas"), name_key("Antanas Basko"))

    def test_resolution_needs_exactly_one_match(self):
        field = [
            {"candidateName": "Paulauskas Artūras", "vrkCandidateId": "1"},
            {"candidateName": "Artūras Paulauskas", "vrkCandidateId": "2"},
            {"candidateName": "Filipovič Tadeuš", "vrkCandidateId": "3"},
        ]
        self.assertIsNone(resolve_by_name("Artūras Paulauskas", field))
        self.assertEqual(resolve_by_name("Tadeuš Filipovič", field)["vrkCandidateId"], "3")
        self.assertIsNone(resolve_by_name("Nobody At All", field))


class ConstituencyPageTests(unittest.TestCase):
    def test_round_two_verdict_rows_and_turnout(self):
        page = parse_constituency_results(ROUND_TWO_HTML, ARCHIVE + "seim96/rapgpl.htm-42+2.htm")
        self.assertEqual(page["constituencyName"], "Naujamiesčio")
        self.assertEqual(page["constituencyNumber"], 1)
        self.assertEqual(page["round"], 2)
        self.assertIsNone(page["held"])
        self.assertFalse(page["runoffRequired"])
        self.assertEqual(page["winnerName"], "Audrius Butkevičius")
        self.assertEqual(page["winnerVrkCandidateId"], "17730")
        self.assertFalse(page["mojibakeRepaired"])
        self.assertEqual(
            page["turnout"],
            {
                "registeredVoters": 33878,
                "voters": 15862,
                "turnoutPercent": 46.82,
                "invalidBallots": 617,
                "validBallots": 15245,
            },
        )
        # The totals row is not a candidate.
        self.assertEqual(
            [(c["vrkCandidateId"], c["votes"], c["rank"]) for c in page["candidates"]],
            [("17730", 9121, 1), ("18083", 6124, 2)],
        )
        self.assertEqual(page["candidates"][0]["votesDistrict"], 8784)
        self.assertEqual(page["candidates"][0]["votesPostal"], 337)

    def test_election_not_held_names_nobody(self):
        page = parse_constituency_results(NOT_HELD_HTML, ARCHIVE + "19990321/rapgpl.htm-394+1.htm")
        self.assertFalse(page["held"])
        self.assertFalse(page["runoffRequired"])
        self.assertIsNone(page["winnerName"])
        self.assertIsNone(page["winnerVrkCandidateId"])
        self.assertEqual(page["turnout"]["turnoutPercent"], 19.81)

    def test_runoff_needed_names_nobody(self):
        page = parse_constituency_results(RUNOFF_NEEDED_HTML, ARCHIVE + "seim96/rapgpl.htm-42+1.htm")
        self.assertTrue(page["held"])
        self.assertTrue(page["runoffRequired"])
        self.assertIsNone(page["winnerName"])

    def test_rows_without_an_id(self):
        page = parse_constituency_results(NO_IDS_HTML, ARCHIVE + "seimpk/rapgpl.htm")
        self.assertEqual([c["vrkCandidateId"] for c in page["candidates"]], [None, None])
        self.assertEqual([c["name"] for c in page["candidates"]], ["Eduardas Šablinskas", "Zbignev Balcevič"])

    def test_mojibake_page_is_repaired_and_read(self):
        page = parse_constituency_results(MOJIBAKE_HTML, ARCHIVE + "seimpk/rapgp202.htm")
        self.assertTrue(page["mojibakeRepaired"])
        self.assertEqual(page["constituencyName"], "Vilniaus Šalčininkų")
        self.assertEqual(page["constituencyNumber"], 56)
        self.assertTrue(page["held"])
        # "Į Seimo narius išrinktas …", the wording only this capture uses.
        self.assertEqual(page["winnerName"], "Jan Senkevič")
        self.assertEqual(page["winnerVrkCandidateId"], "39779")
        # The other table header ("Paduotų balsų skaičius"), and a totals row
        # whose label is mojibake too.
        self.assertEqual(
            [(c["name"], c["votes"]) for c in page["candidates"]],
            [("Jan Senkevič", 15525), ("Algimantas Reičiūnas", 1917)],
        )
        self.assertEqual(page["turnout"]["registeredVoters"], 39219)
        # No round heading on this capture; the caller supplies it.
        self.assertIsNone(page["round"])


class ResultsPageTests(unittest.TestCase):
    def test_members_page_seat_round_and_nominator(self):
        members = parse_elected_members(MEMBERS_HTML, ARCHIVE + "seim96/rsnl.htm-1.htm")
        self.assertEqual(
            [(m["vrkCandidateId"], m["seat"], m["round"]) for m in members],
            [
                ("17800", "daugiamandate", None),
                ("16882", "vienmandate", 2),
                ("17730", "vienmandate", 2),
                ("18093", "vienmandate", 1),
            ],
        )
        self.assertEqual(members[0]["nominator"], "Lietuvos socialdemokratų partija")
        self.assertFalse(members[0]["selfNominated"])
        self.assertTrue(members[2]["selfNominated"])

    def test_list_results_page(self):
        lists = parse_list_results(LIST_RESULTS_HTML, ARCHIVE + "seim96/rdl.htm")
        self.assertEqual(
            [(row["listId"], row["mandates"], row["votes"]) for row in lists],
            [("2", 33, 409585), ("7", 7, 90756), (None, 0, 40941)],
        )
        # A list VRK did not rank has no ranking page, and "-" is zero
        # mandates rather than an unparsed cell.
        self.assertIsNone(lists[2]["rankingUrl"])
        self.assertTrue(lists[0]["rankingUrl"].endswith("rkreitl.htm-2.htm"))

    def test_ranking_page_keeps_both_orders(self):
        rows = parse_ranking_page(RANKING_HTML, ARCHIVE + "seim96/rkreitl.htm-2.htm")
        # `rank` is the printed (post-preference) order the seats follow;
        # `listPosition` is the pre-election number reprinted from the card.
        self.assertEqual(
            [(r["vrkCandidateId"], r["rank"], r["listPosition"]) for r in rows],
            [("18093", 1, 1), ("18091", 2, 3), ("16884", 3, 2)],
        )
        self.assertEqual(rows[0]["positiveVotes"], 121795)
        self.assertEqual(rows[0]["negativeVotes"], 7290)
        self.assertEqual(rows[0]["ratingPoints"], 59746260)


class VoteAndWinnerCollectionTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"vrkCandidateId": None, "candidateName": "Šablinskas Eduardas", "constituencyNumber": 10},
            {"vrkCandidateId": None, "candidateName": "Balcevič Zbignev", "constituencyNumber": 10},
        ]
        for entry, vrk_id in zip(self.entries, ("65088", "65099")):
            entry["vrkCandidateId"] = vrk_id

    def test_id_rows_join_by_id(self):
        page = parse_constituency_results(NOT_HELD_HTML, ARCHIVE + "19990321/rapgpl.htm-394+1.htm")
        page["round"] = 1
        votes, unresolved = collect_constituency_votes([page], self.entries)
        self.assertEqual(unresolved, [])
        self.assertEqual(votes["65088"][0]["balsai"], 2735)
        self.assertEqual(votes["65088"][0]["vieta"], 1)
        self.assertEqual(votes["65088"][0]["turas"], 1)
        self.assertEqual(votes["65088"][0]["apygardos-numeris"], 10)

    def test_id_less_rows_join_by_name_within_the_constituency(self):
        page = parse_constituency_results(NO_IDS_HTML, ARCHIVE + "seimpk/rapgpl.htm")
        page["round"] = 1
        votes, unresolved = collect_constituency_votes([page], self.entries)
        self.assertEqual(unresolved, [])
        self.assertEqual(sorted(votes), ["65088", "65099"])

    def test_an_unresolvable_row_is_reported_not_dropped(self):
        page = parse_constituency_results(NO_IDS_HTML, ARCHIVE + "seimpk/rapgpl.htm")
        page["round"] = 1
        votes, unresolved = collect_constituency_votes([page], self.entries[:1])
        self.assertEqual(sorted(votes), ["65088"])
        self.assertEqual([row["name"] for row in unresolved], ["Zbignev Balcevič"])

    def test_page_winner_carries_its_constituency_and_round(self):
        page = parse_constituency_results(ROUND_TWO_HTML, ARCHIVE + "seim96/rapgpl.htm-42+2.htm")
        elected, unresolved = resolve_page_winners([page], [])
        self.assertEqual(unresolved, [])
        self.assertEqual(
            elected["17730"],
            {
                "seat": "vienmandate",
                "method": "constituency-verdict",
                "sourceUrl": ARCHIVE + "seim96/rapgpl.htm-42+2.htm",
                "round": 2,
                "constituency": "Naujamiesčio",
                "constituencyNumber": 1,
            },
        )

    def test_a_page_with_no_verdict_elects_nobody(self):
        pages = [
            parse_constituency_results(NOT_HELD_HTML, ARCHIVE + "a.htm"),
            parse_constituency_results(RUNOFF_NEEDED_HTML, ARCHIVE + "b.htm"),
        ]
        self.assertEqual(resolve_page_winners(pages, []), ({}, []))


def _candidacies() -> list[dict]:
    """One 1996 record's `kandidatavimas`: a constituency candidacy and a list
    one, the shape 717 of the 879 records have."""
    return [
        {
            "apygarda": "Žirmūnų",
            "apygardos-numeris": 4,
            "iskele": "Lietuvos socialdemokratų partija",
            "iskele-nuoroda": ARCHIVE + "seim96/partr2l.htm-7.htm",
            "numeris-sarase": None,
        },
        {
            "apygarda": "Daugiamandatė",
            "apygardos-numeris": None,
            "iskele": "Lietuvos socialdemokratų partija",
            "iskele-nuoroda": ARCHIVE + "seim96/partr2l.htm-7.htm",
            "numeris-sarase": 17,
        },
    ]


RANKING_ROW = {
    "listId": "7",
    "list": "Lietuvos socialdemokratų partija",
    "rank": 12,
    "listPosition": 17,
    "positiveVotes": 1739,
    "negativeVotes": 104,
    "ratingPoints": 7298889,
    "sourceUrl": ARCHIVE + "seim96/rkreitl.htm-7.htm",
}
VOTE_ROWS = [
    {"turas": 1, "apygardos-numeris": 4, "balsai-apygardoje": 4793, "balsai-pastu": 74, "balsai": 4867, "vieta": 2, "saltinis": "x"},
    {"turas": 2, "apygardos-numeris": 4, "balsai-apygardoje": 10590, "balsai-pastu": 156, "balsai": 10746, "vieta": 1, "saltinis": "y"},
]


class ApplyResultsTests(unittest.TestCase):
    def test_no_results_file_leaves_the_candidacies_untouched(self):
        candidacies = _candidacies()
        self.assertEqual(apply_results(candidacies, "66818", {}), [])
        self.assertEqual(candidacies, _candidacies())

    def test_constituency_win_marks_only_the_constituency_candidacy(self):
        candidacies = _candidacies()
        results = {
            "elected": {
                "66818": {
                    "seat": "vienmandate",
                    "sourceUrl": ARCHIVE + "seim96/rsnl.htm-1.htm",
                    "round": 2,
                    "constituencyNumber": 4,
                }
            },
            "constituencyVotes": {"66818": VOTE_ROWS},
            "ranking": {"66818": {"7": RANKING_ROW}},
        }
        self.assertEqual(apply_results(candidacies, "66818", results), [])
        self.assertTrue(candidacies[0]["isrinktas"])
        self.assertEqual(candidacies[0]["isrinktas-kaip"], "vienmandate")
        self.assertEqual(candidacies[0]["rezultatu-turas"], 2)
        self.assertEqual(candidacies[0]["turai"], VOTE_ROWS)
        # The list seat they did not win is a known false, and carries the
        # preference figures rather than the constituency's votes.
        self.assertFalse(candidacies[1]["isrinktas"])
        self.assertNotIn("turai", candidacies[1])
        self.assertEqual(candidacies[1]["porinkiminis-numeris-sarase"], 12)
        self.assertEqual(candidacies[1]["teigiami-balsai"], 1739)
        self.assertEqual(candidacies[1]["reitingo-balai"], 7298889)

    def test_list_win_marks_only_the_list_candidacy(self):
        candidacies = _candidacies()
        results = {
            "elected": {"1": {"seat": "daugiamandate", "sourceUrl": "s"}},
            "constituencyVotes": {},
            "ranking": {},
        }
        self.assertEqual(apply_results(candidacies, "1", results), [])
        self.assertFalse(candidacies[0]["isrinktas"])
        self.assertTrue(candidacies[1]["isrinktas"])
        self.assertEqual(candidacies[1]["isrinktas-kaip"], "daugiamandate")
        self.assertNotIn("rezultatu-turas", candidacies[1])

    def test_a_double_nomination_marks_both_rows_of_the_won_seat(self):
        # 51 of the 879 1996 candidates were nominated by a coalition *and*
        # one of its member parties, so the card prints the same constituency
        # twice. Both rows describe the seat that was won.
        candidacies = [
            {"apygarda": "Jonavos", "apygardos-numeris": 60, "iskele": "koalicija", "iskele-nuoroda": None, "numeris-sarase": None},
            {"apygarda": "Jonavos", "apygardos-numeris": 60, "iskele": "partija", "iskele-nuoroda": None, "numeris-sarase": None},
            {"apygarda": "Daugiamandatė", "apygardos-numeris": None, "iskele": "koalicija", "iskele-nuoroda": None, "numeris-sarase": 57},
            {"apygarda": "Daugiamandatė", "apygardos-numeris": None, "iskele": "partija", "iskele-nuoroda": None, "numeris-sarase": 20},
        ]
        results = {
            "elected": {"17933": {"seat": "vienmandate", "sourceUrl": "s", "round": 2, "constituencyNumber": 60}},
            "constituencyVotes": {},
            "ranking": {},
        }
        self.assertEqual(apply_results(candidacies, "17933", results), [])
        self.assertEqual([c["isrinktas"] for c in candidacies], [True, True, False, False])

    def test_a_win_in_another_constituency_is_reported(self):
        candidacies = _candidacies()
        results = {
            "elected": {"66818": {"seat": "vienmandate", "sourceUrl": "s", "round": 2, "constituencyNumber": 99}},
            "constituencyVotes": {},
            "ranking": {},
        }
        problems = apply_results(candidacies, "66818", results)
        self.assertEqual([p["eventType"] for p in problems], ["ElectedCandidacyUnmatched"])
        self.assertEqual([c["isrinktas"] for c in candidacies], [False, False])

    def test_a_disagreeing_list_position_is_reported(self):
        candidacies = _candidacies()
        results = {
            "elected": {},
            "constituencyVotes": {},
            "ranking": {"66818": {"7": {**RANKING_ROW, "listPosition": 18}}},
        }
        problems = apply_results(candidacies, "66818", results)
        self.assertEqual([p["eventType"] for p in problems], ["ListPositionMismatch"])
        self.assertEqual(problems[0]["detail"]["card"], 17)
        self.assertEqual(problems[0]["detail"]["ranking"], 18)

    def test_candidate_id_comes_off_the_card_url(self):
        self.assertEqual(candidate_id_from_url(ARCHIVE + "seim96/kandvl.htm-17109.htm"), "17109")
        self.assertIsNone(candidate_id_from_url(ARCHIVE + "seimpk/kandvl2.htm"))
        self.assertIsNone(candidate_id_from_url(""))


class BuiltResultsFileTests(unittest.TestCase):
    """Pins of the reconciliation the six builds reported (2026-08-27)."""

    def test_1996_general(self):
        payload = _results("1996-spalio-20-seimo")
        stats = payload["stats"]
        # 141 seats, but only 137 were filled on election night: the four
        # constituencies below the turnout threshold went to the 1997-03-23
        # repeat, and those four are exactly its constituencies.
        self.assertEqual(stats["seats"], 141)
        self.assertEqual(stats["membersListed"], 137)
        self.assertEqual(stats["listSeats"], 70)
        self.assertEqual(stats["constituencySeats"], 67)
        self.assertEqual(stats["constituencySeatsFirstRound"], 2)
        self.assertEqual(stats["constituencySeatsRunoff"], 65)
        self.assertEqual(stats["constituenciesNotHeld"], 4)
        self.assertEqual(
            sorted(c["constituencyNumber"] for c in payload["details"]["constituenciesNotHeld"]),
            [10, 56, 57, 58],
        )
        # The corpus is built from the constituency listings, so the 17
        # members elected on a list alone have no record to carry the flag.
        self.assertEqual(stats["membersInSitemap"], 120)
        self.assertEqual(stats["membersNotInSitemap"], 17)
        self.assertEqual(stats["seatsByType"], {"daugiamandate": 53, "vienmandate": 67})
        # Every cross-check clean: the constituency pages' own verdicts are
        # exactly the members page's constituency half, the list results
        # page's mandate column matches its list half, and striking the
        # constituency winners from each ranked list and taking the top M
        # reproduces the published list winners for all five lists.
        self.assertEqual(stats["constituencyPageDiff"], 0)
        self.assertEqual(stats["seatMismatches"], 0)
        self.assertEqual(stats["mandatesDeclared"], 70)
        self.assertEqual(stats["listMandateMismatches"], 0)
        self.assertEqual(stats["allocationsChecked"], 5)
        self.assertEqual(stats["allocationMismatches"], 0)
        # All 879 records appear on a results page, none by name.
        self.assertEqual(stats["candidatesWithVotes"], 879)
        self.assertEqual(stats["candidatesWithoutVotes"], 0)
        self.assertEqual(stats["unresolvedRows"], 0)
        self.assertEqual(stats["unresolvedWinners"], 0)
        self.assertEqual(stats["constituencyPages"], 136)
        self.assertEqual(stats["roundMismatches"], 0)
        self.assertEqual(stats["rankingPages"], 19)
        self.assertTrue(all(v["method"] == "members-list" for v in payload["elected"].values()))

    def test_1997_march_repeat_elected_two(self):
        payload = _results("1997-kovo-23-seimo-pakartotiniai")
        stats = payload["stats"]
        self.assertEqual(stats["candidates"], 23)
        self.assertEqual(stats["candidatesWithVotes"], 23)
        self.assertEqual(stats["unresolvedRows"], 0)
        self.assertEqual(stats["constituenciesNotHeld"], 2)
        # All four first-round pages of this election are the mojibake
        # capture; the 1997-04-13 runoff page is not.
        self.assertEqual(stats["mojibakePages"], 4)
        self.assertEqual(stats["elected"], 2)
        self.assertEqual(payload["elected"]["39779"]["constituencyNumber"], 56)
        self.assertEqual(payload["elected"]["39779"]["round"], 1)
        self.assertEqual(payload["elected"]["39429"]["constituencyNumber"], 58)
        self.assertEqual(payload["elected"]["39429"]["round"], 2)

    def test_1997_december_repeat_elected_one_in_the_runoff(self):
        payload = _results("1997-gruodzio-21-seimo-pakartotiniai")
        self.assertEqual(payload["stats"]["candidates"], 4)
        self.assertEqual(payload["stats"]["elected"], 1)
        self.assertEqual(payload["stats"]["constituenciesNotHeld"], 0)
        self.assertEqual(payload["elected"]["61675"]["round"], 2)

    def test_the_three_failed_repeats_elect_nobody(self):
        for election_id, candidates, constituencies in (
            ("1998-kovo-22-seimo-pakartotiniai", 11, 2),
            ("1998-lapkricio-15-seimo-pakartotiniai", 11, 1),
            ("1999-kovo-21-seimo-pakartotiniai", 22, 3),
        ):
            with self.subTest(election_id):
                stats = _results(election_id)["stats"]
                self.assertEqual(stats["candidates"], candidates)
                self.assertEqual(stats["candidatesWithVotes"], candidates)
                self.assertEqual(stats["unresolvedRows"], 0)
                self.assertEqual(stats["elected"], 0)
                # Every constituency states "Rinkimai apygardoje neįvyko",
                # which is what makes `isrinktas` a known false here.
                self.assertEqual(stats["constituenciesNotHeld"], constituencies)


if __name__ == "__main__":
    unittest.main()
