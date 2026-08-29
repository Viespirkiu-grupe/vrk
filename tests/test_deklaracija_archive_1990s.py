"""Parsing the 1996-1997 archive declaration page (`kpdl.htm`).

Fixtures here are inline rather than files under `samples/`, because `samples/`
is gitignored and this parser is a pure function over page text. Both are
reproductions of real pages, keeping the markup quirks that matter: the 1996
family prints its figures bare and puts the issue line inside an HTML comment
with Latin-1 entities over CP1257 text; the 1997 family suffixes every figure
with " Lt", splits section numerals into their own <b> tags, and carries VRK's
"Klaida užklausoje." banner.

The behaviour worth pinning is the treatment of section III's total. See
GitHub issue #63 and the module docstring for the measurement behind it.
"""

from __future__ import annotations

import unittest

from scraper.shared.deklaracija_archive_1990s import parse_declaration

# Reproduction of 1996-spalio-20-seimo / zuoza-rolandas. The issue date sits in
# a commented-out paragraph whose Baltic characters are mojibaked -- which is
# how VRK shipped it, and the same reason the candidate pages in this family
# need their residence recovered by regex rather than through the DOM.
SEIMAS_1996 = """<body>
 <center><font size="4">Lietuvos Respublikos gyventojų turto ir pajamų deklaracijos<br /> pagrindinių duomenų išrašas</font>
  <!--p>I&eth;ra&eth;&agrave; i&eth;dav&euml; <b></b><br>1996 09 05-->
 <br />&nbsp;</center>
 <p><b>I. Bendrieji duomenys</b></p>
 <blockquote>
  <p>Vardas, pavardė: <b>Rolandas Zuoza</b></p>
  <p>Šeimos narių skaičius: <b>1</b>, tarp jų išlaikytinių: <b>0</b>, iš jų iki 18 metų: <b>0</b>.</p>
 </blockquote>
 <p><b>II. Turtas ir piniginės lėšos atitinkamų metų pradžioje (įskaitant nepilnamečių šeimos narių turtą ir pinigines lėšas). </b>Bendra suma pagal šios deklaracijos dalies 1, 2, 3 ir 4 punktus: <b>12000 Lt</b>.</p>
 <p><b>III. Kalendoriniais metais gautos pajamos ir sumokėti mokesčiai.</b> Sumos nurodytos šios deklaracijos dalies 1 ir 20 punktuose:</p>
 <table>
  <tr><td><b>Gautos&nbsp;pajamos</b></td><td><b>Gauta&nbsp;pajamų&nbsp;(be&nbsp;mokesčių)&nbsp;suma,&nbsp;Lt</b></td><td><b>Sumokėta&nbsp;mokesčių&nbsp;suma,&nbsp;Lt</b></td></tr>
  <tr><td>1. Susijusios su darbo santykiais pajamos (pinigais, natūra ar lengvatinėmis paslaugomis)</td><td><b>6703</b></td><td><b>2363</b></td></tr>
  <tr><td>20. Iš viso:</td><td><b>6703</b></td><td><b>2363</b></td></tr>
 </table>
 <table><tr><td><b>IV. Kalendoriniais metais įsigytas turtas ir paskolintos piniginės lėšos (įskaitant nepilnamečių šeimos narių turtą ir pinigines lėšas). </b>Bendra suma pagal šios deklaracijos dalies 1, 2, 3 ir 4 punktus: <b>500 Lt</b></td></tr></table>
 <table><tr><td><b>V. Turtas ir piniginės lėšos metų pabaigoje (įskaitant nepilnamečių šeimos narių turtą ir pinigines lėšas). </b>Bendra suma pagal šios deklaracijos dalies 1, 2, 3 ir 4 punktus: <b>12500 Lt</b></td></tr></table>
 <p>Mokesčių nepriemoka už praėjusius kalendorinius metus: <b>0 Lt</b>.</p>
 <p>Privaloma sumokėti mokesčių ir sankcijų suma (įskaitant nepriemoką): <b>0 Lt</b>.</p>
</body>"""

# Reproduction of 1997-kovo-23-savivaldybiu-tarybu / urbelis-andriejus: the
# family whose "20. Iš viso" row renders 0 against a non-zero row 1.
MUNICIPAL_1997 = """<body>
 <p align="center"><b><font size="5">Lietuvos Respublikos gyventojų turto ir pajamų deklaracijos <br /> pagrindinių duomenų išrašas</font></b></p>
 <p>Kandidato pajamų deklaracijos išrašas Klaida užklausoje.</p>
 <p align="left"><br /> Išrašą <b>1997 02 10</b> išdavė <b>Alytaus rajono mokesčių inspek</b></p>
 <p><b>I.</b> Bendrieji duomenys</p>
 <blockquote><ol>
  <li>Vardas, pavardė: <b>Andriejus Urbelis</b></li>
  <li>Šeimos narių skaičius: <b>2</b>, tarp jų išlaikytinių: <b>0</b>, iš jų iki 18 metų: <b>0</b>.</li>
 </ol></blockquote>
 <table><tr>
  <td><b>II. </b>Turtas ir piniginės lėšos atitinkamų metų pradžioje (įskaitant nepilnamečių šeimos narių turtą ir pinigines lėšas). Bendra suma pagal šios deklaracijos dalies 1, 2, 3 ir 4 punktus:</td>
  <td align="center"><b>30051 Lt</b>.</td>
 </tr><tr><td><b>III. </b>Kalendoriniais metais gautos pajamos ir sumokėti mokesčiai. Sumos nurodytos šios deklaracijos dalies 1 ir 20 punktuose:</td></tr></table>
 <table>
  <tr><td>Gautos pajamos</td><td>Gauta pajamų (be mokesčių) suma</td><td>Sumokėta mokesčių suma</td></tr>
  <tr><td>1. Susijusios su darbo santykiais pajamos (pinigais, natūra ar lengvatinėmis paslaugomis)</td><td><b>153 Lt</b></td><td><b>0 Lt</b></td></tr>
  <tr><td>20. Iš viso:</td><td><b>0 Lt</b></td><td><b>0 Lt</b></td></tr>
 </table>
 <table><tr>
  <td><b>&nbsp;<br /> IV.</b> Kalendoriniais metais įsigytas turtas ir paskolintos piniginės lėšos (įskaitant nepilnamečių šeimos narių turtą ir pinigines lėšas). Bendra suma pagal šios deklaracijos dalies 1, 2, 3 ir 4 punktus:</td>
  <td align="center">&nbsp;<b>0 Lt</b></td>
 </tr><tr>
  <td><b>V.</b> Turtas ir piniginės lėšos metų pabaigoje (įskaitant nepilnamečių šeimos narių turtą ir pinigines lėšas). Bendra suma pagal šios deklaracijos dalies 1, 2, 3 ir 4 punktus:</td>
  <td align="center">&nbsp;<b>30204 Lt</b></td>
 </tr></table>
 <p>Mokesčių nepriemoka už praėjusius kalendorinius metus: <b>0 Lt</b></p>
 <p>Privaloma sumokėti mokesčių ir sankcijų suma (įskaitant nepriemoką): <b>0 Lt</b>.</p>
</body>"""


class SeimasLayoutTests(unittest.TestCase):
    def setUp(self):
        self.result = parse_declaration(SEIMAS_1996)
        self.d = self.result["declaration"]

    def test_the_three_combined_section_totals_are_read(self):
        self.assertEqual(self.d["turtas-ir-pinigines-lesos-metu-pradzioje"], 12000)
        self.assertEqual(self.d["kalendoriniais-metais-isigytas-turtas"], 500)
        self.assertEqual(self.d["turtas-ir-pinigines-lesos-metu-pabaigoje"], 12500)

    def test_the_modern_split_keys_stay_null_because_the_form_sums_them(self):
        # The 1990s form publishes one figure for turtas + piniginės lėšos;
        # the split the modern pages make is not recoverable from it.
        self.assertIsNone(self.d["privalomas-registruoti-turtas"])
        self.assertIsNone(self.d["pinigines-lesos"])

    def test_income_and_tax_come_from_the_total_row(self):
        self.assertEqual(self.d["gautos-pajamos"], 6703)
        self.assertEqual(self.d["sumoketas-pajamu-mokestis"], 2363)
        self.assertEqual(self.d["gautos-pajamos-darbo-santykiu"], 6703)
        self.assertEqual(self.d["sumoketas-pajamu-mokestis-darbo-santykiu"], 2363)

    def test_figures_are_litas_so_the_corpus_conversion_applies(self):
        self.assertEqual(self.d["valiuta"], "Lt")

    def test_the_issue_date_is_recovered_from_the_commented_out_line(self):
        self.assertEqual(self.d["israso-data"], "1996-09-05")

    def test_this_family_publishes_no_issuer(self):
        # "Išrašą išdavė" arrives as "Iðraðà iðdavë", and carries no name
        # after it on any of the 49 pages sampled.
        self.assertIsNone(self.d.get("israsa-isdave"))

    def test_family_member_counts_are_read(self):
        self.assertEqual(self.d["seimos-nariu-skaicius"], 1)
        self.assertEqual(self.d["islaikytiniu-skaicius"], 0)
        self.assertEqual(self.d["seimos-nariu-iki-18-metu"], 0)

    def test_a_consistent_page_raises_no_anomaly(self):
        self.assertEqual(self.result["anomalies"], [])


class MunicipalLayoutTests(unittest.TestCase):
    def setUp(self):
        self.result = parse_declaration(MUNICIPAL_1997)
        self.d = self.result["declaration"]

    def test_the_lt_suffixed_section_totals_are_read(self):
        self.assertEqual(self.d["turtas-ir-pinigines-lesos-metu-pradzioje"], 30051)
        self.assertEqual(self.d["kalendoriniais-metais-isigytas-turtas"], 0)
        self.assertEqual(self.d["turtas-ir-pinigines-lesos-metu-pabaigoje"], 30204)

    def test_the_issue_date_and_issuer_are_read(self):
        self.assertEqual(self.d["israso-data"], "1997-02-10")
        self.assertEqual(self.d["israsa-isdave"], "Alytaus rajono mokesčių inspek")

    def test_employment_row_is_published_as_it_stands(self):
        self.assertEqual(self.d["gautos-pajamos-darbo-santykiu"], 153)
        self.assertEqual(self.d["sumoketas-pajamu-mokestis-darbo-santykiu"], 0)

    def test_a_total_below_its_own_row_is_refused_not_published(self):
        # 72 of 84 sampled pages in this election print 0 here against a
        # non-zero row 1. Publishing that would assert an income of zero.
        self.assertIsNone(self.d["gautos-pajamos"])

    def test_refusing_the_total_is_recorded_as_an_anomaly(self):
        events = [a for a in self.result["anomalies"]
                  if a["eventType"] == "DeclarationTotalBelowItsOwnRow"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["detail"]["column"], "gautos-pajamos")
        self.assertEqual(events[0]["detail"]["row20Total"], 0)
        self.assertEqual(events[0]["detail"]["row1Employment"], 153)
        self.assertTrue(events[0]["detail"]["queryErrorBanner"])

    def test_a_page_that_says_its_own_query_failed_reports_at_info(self):
        # Issue #85: 8,598 of the corpus's 8,949 anomaly events are this one,
        # from pages carrying VRK's own "Klaida užklausoje." banner. They are
        # honest reports of source corruption, and at `warning` they drowned
        # the other 24 events and made STOP_ON_ANOMALY useless here.
        events = [a for a in self.result["anomalies"]
                  if a["eventType"] == "DeclarationTotalBelowItsOwnRow"]
        self.assertEqual(events[0]["severity"], "info")

    def test_a_tax_total_equal_to_its_row_is_still_trusted(self):
        # Both are 0 here, so the page does not contradict itself.
        self.assertEqual(self.d["sumoketas-pajamu-mokestis"], 0)


class TotalTrustRuleTests(unittest.TestCase):
    """The rule is >=, the weakest check that catches a self-contradiction."""

    def _parse(self, row1: int, row20: int):
        page = f"""<body>
 <table>
  <tr><td>1. Susijusios su darbo santykiais pajamos (pinigais, natūra ar lengvatinėmis paslaugomis)</td><td><b>{row1} Lt</b></td><td><b>0 Lt</b></td></tr>
  <tr><td>20. Iš viso:</td><td><b>{row20} Lt</b></td><td><b>0 Lt</b></td></tr>
 </table>
 <table><tr><td><b>IV.</b> Kalendoriniais metais įsigytas turtas ir paskolintos piniginės lėšos. Bendra suma pagal šios deklaracijos dalies 1, 2, 3 ir 4 punktus: <b>0 Lt</b></td></tr></table>
</body>"""
        return parse_declaration(page)

    def _income(self, row1: int, row20: int):
        return self._parse(row1, row20)["declaration"]["gautos-pajamos"]

    def test_a_total_larger_than_its_row_is_kept(self):
        # Other income categories exist; rows 2-19 are simply not printed.
        self.assertEqual(self._income(6791, 169391), 169391)

    def test_a_total_equal_to_its_row_is_kept(self):
        self.assertEqual(self._income(5715, 5715), 5715)

    def test_a_total_below_its_row_is_dropped(self):
        self.assertIsNone(self._income(861, 0))

    def test_a_page_that_did_not_say_its_query_failed_still_warns(self):
        # The other 327 of them: a readable page that contradicts itself is a
        # finding, and stays at `warning`.
        events = [a for a in self._parse(861, 0)["anomalies"]
                  if a["eventType"] == "DeclarationTotalBelowItsOwnRow"]
        self.assertEqual([e["severity"] for e in events], ["warning"])
        self.assertFalse(events[0]["detail"]["queryErrorBanner"])


class UnreadablePageTests(unittest.TestCase):
    def test_a_page_with_no_figures_is_flagged(self):
        result = parse_declaration("<body><p>Klaida užklausoje.</p></body>")
        self.assertIn(
            "DeclarationPageUnreadable",
            [a["eventType"] for a in result["anomalies"]],
        )

    def test_an_empty_page_does_not_raise(self):
        self.assertIsInstance(parse_declaration("")["declaration"], dict)


if __name__ == "__main__":
    unittest.main()
