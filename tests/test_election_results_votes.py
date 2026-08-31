"""Per-candidate votes from the 2007-2015 results trees (issue #99): the
preference pages, the extended district rows, the municipal ranking votes,
and the parse-stage join that writes them into `kandidatavimas`."""

import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _apply_results,
    load_results,
)
from scraper.shared.election_results import (
    parse_list_ranking_page,
    parse_preference_page,
    parse_seimo_district_page,
)

PREFERENCE_HTML = """
<html><body><table>
<tr><td>1</td><td><a href="/statiniai/puslapiai/rinkimai/416_lt/Kandidatai/Kandidatas66814/Kandidato66814Anketa.html">Algirdas BUTKEVIČIUS</a> (V)</td><td>1</td><td>75469</td><td>75469</td></tr>
<tr><td>2</td><td><a href="/statiniai/puslapiai/rinkimai/416_lt/Kandidatai/Kandidatas66815/Kandidato66815Anketa.html">Vilija BLINKEVIČIŪTĖ</a></td><td>5</td><td>59547</td><td>59547</td></tr>
</table></body></html>
"""

# The 2008-form district page: rows link the candidate's anketa, so the id is
# on the row; two percent columns follow the three counts.
DISTRICT_HTML_2008 = """
<html><body>
<font size="5">Šiaulių kaimiškoji (Nr. 45) apygarda</font>
<table>
<tr><td><a href="/400_lt/Kandidatai/Kandidatas22482/Kandidato22482Anketa.html">Edvardas ŽAKARIS</a></td><td>7466</td><td>290</td><td>7756</td><td>50,94%</td><td>48,14%</td><td></td></tr>
<tr><td><a href="/400_lt/Kandidatai/Kandidatas19632/Kandidato19632Anketa.html">Egidijus VAREIKIS</a></td><td>1859</td><td>159</td><td>2018</td><td>13,25%</td><td>12,53%</td><td></td></tr>
</table></body></html>
"""

# The 2012-form district page: rows link the re-issued `rezultatai_sm_kand`
# pages instead, so no id rides the row and the join is by name.
DISTRICT_HTML_2012 = """
<html><body>
<table>
<tr><td><a href="rezultatai_sm_kand123_sav7209_1_1_.html">Irena DEGUTIENĖ</a></td><td>8104</td><td>4284</td><td>12388</td><td>37,95%</td><td>36,61%</td><td></td></tr>
</table></body></html>
"""

RANKING_HTML = """
<html><body><table>
<tr><td>1</td><td><a href="/statiniai/puslapiai/rinkimai/440_lt/Kandidatai/Kandidatas80152/Kandidato80152Anketa.html">Apolinaras NICIUS</a></td><td>1</td><td>1048</td></tr>
<tr><td>2</td><td><a href="/statiniai/puslapiai/rinkimai/440_lt/Kandidatai/Kandidatas80153/Kandidato80153Anketa.html">Albinas KLIMAS</a></td><td>4</td><td>626</td></tr>
</table></body></html>
"""


class ParsePreferencePageTests(unittest.TestCase):
    def test_rows_carry_id_positions_votes_and_rating(self) -> None:
        rows = parse_preference_page(PREFERENCE_HTML, "http://example/pirmumo4136.html")
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0],
            {
                "vrkCandidateId": "66814",
                "name": "Algirdas BUTKEVIČIUS",
                "porinkiminisNumerisSarase": 1,
                "numerisSarase": 1,
                "pirmumoBalsai": 75469,
                "reitingoBalai": 75469,
            },
        )
        self.assertEqual(rows[1]["numerisSarase"], 5)


class ParseSeimoDistrictPageTests(unittest.TestCase):
    def test_2008_rows_carry_the_anketa_id_and_the_breakdown(self) -> None:
        parsed = parse_seimo_district_page(DISTRICT_HTML_2008)
        self.assertEqual(parsed["number"], 45)
        first = parsed["rows"][0]
        self.assertEqual(first["vrkCandidateId"], "22482")
        self.assertEqual(
            (first["votesPrecinct"], first["votesPostal"], first["votes"]),
            (7466, 290, 7756),
        )
        self.assertEqual(first["percentValid"], 50.94)
        # vieta comes from the totals, not the page's sort variant.
        self.assertEqual([row["vieta"] for row in parsed["rows"]], [1, 2])

    def test_2012_rows_have_no_id_and_join_by_name(self) -> None:
        parsed = parse_seimo_district_page(DISTRICT_HTML_2012)
        row = parsed["rows"][0]
        self.assertIsNone(row["vrkCandidateId"])
        self.assertEqual(row["name"], "Irena DEGUTIENĖ")
        self.assertEqual(row["votes"], 12388)


class ParseListRankingPageTests(unittest.TestCase):
    def test_ranking_rows_carry_the_preference_votes(self) -> None:
        rows = parse_list_ranking_page(RANKING_HTML, "http://example/ranking.html")
        self.assertEqual(
            [(row["rank"], row["vrkCandidateId"], row["preferenceVotes"]) for row in rows],
            [(1, "80152", 1048), (2, "80153", 626)],
        )
        self.assertEqual(rows[1]["preElectionPosition"], 4)


class ApplyResultsVotesTests(unittest.TestCase):
    def _results_file(self, tmp: Path) -> Path:
        path = tmp / "x.results.json"
        path.write_text(
            json.dumps(
                {
                    "electionId": "x",
                    "elected": {"66814": {"seat": "daugiamandate", "sourceUrl": "http://e"}},
                    "details": {
                        "votes": {
                            "66814": {
                                "porinkiminisNumerisSarase": 1,
                                "pirmumoBalsai": 75469,
                                "reitingoBalai": 75469,
                                "pirmumoBalsuSaltinis": "http://pref",
                            },
                            "22482": {
                                "vienmandate": [
                                    {
                                        "turas": 1,
                                        "balsadezese": 7466,
                                        "pastu": 290,
                                        "isViso": 7756,
                                        "procentai": 50.94,
                                        "vieta": 1,
                                        "saltinis": "http://d1",
                                    },
                                    {
                                        "turas": 2,
                                        "balsadezese": 9000,
                                        "pastu": 400,
                                        "isViso": 9400,
                                        "procentai": 61.0,
                                        "vieta": 1,
                                        "saltinis": "http://d2",
                                    },
                                ]
                            },
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_load_results_returns_elected_and_votes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_results(self._results_file(Path(tmp)))
        self.assertEqual(set(loaded), {"elected", "votes"})
        self.assertIn("66814", loaded["elected"])
        self.assertIn("22482", loaded["votes"])

    def test_votes_join_onto_winners_and_losers_alike(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_results(self._results_file(Path(tmp)))

        winner: dict = {}
        _apply_results(winner, {"vrkCandidateId": "66814"}, None, loaded)
        self.assertEqual(winner["kandidatavimas"]["isrinktas"], True)
        self.assertEqual(winner["kandidatavimas"]["pirmumoBalsai"], 75469)
        self.assertEqual(winner["kandidatavimas"]["porinkiminisNumerisSarase"], 1)

        loser: dict = {}
        _apply_results(loser, {"vrkCandidateId": "22482"}, None, loaded)
        candidacy = loser["kandidatavimas"]
        self.assertEqual(candidacy["isrinktas"], False)
        # Two rounds land as the pre-2005-shaped pair of blocks.
        self.assertEqual(candidacy["vienmandatesBalsai"]["isViso"], 7756)
        self.assertEqual(candidacy["vienmandatesBalsai"]["procentai"], 50.94)
        self.assertEqual(candidacy["vienmandatesBalsai2"]["isViso"], 9400)
        self.assertNotIn("pirmumoBalsai", candidacy)

    def test_a_bare_elected_map_still_joins(self) -> None:
        payload: dict = {}
        _apply_results(
            payload,
            {"vrkCandidateId": "9"},
            None,
            {"9": {"seat": "vienmandate", "sourceUrl": "http://e"}},
        )
        self.assertEqual(payload["kandidatavimas"]["isrinktas"], True)


if __name__ == "__main__":
    unittest.main()
