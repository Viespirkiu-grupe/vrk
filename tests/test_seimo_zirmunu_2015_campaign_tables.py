"""The 2012-2015 era's campaign tables on synthetic HTML.

Pins the two shapes the donation and report tables come in — <th> headings
from 2012 on, <td><strong> headings on the 2009 presidential pages — and
the header-keyed totals that replaced a positional read which filed every
litas-only total (2012 Seimo, 2013, 2014 EP, 2014 presidential) under
`amountEur`.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scraper.elections.seimo_zirmunu_2015.anketa_parser import (
    _parse_aukos_html,
    _parse_campaign_person_html,
    _parse_finansavimo_ataskaitos_html,
)
from scraper.elections.seimo_zirmunu_2015.candidate_samples import _fetch_candidate_tabs


def _page(body: str) -> str:
    return f'<html><body><ul id="tabnav"><li><a href="x.html">Tab</a></li></ul>{body}</body></html>'


LT_ONLY_2014 = _page(
    """
<h3>Gautos ir priimtos aukos:</h3>
<table class="partydata">
<tr><th>Eil. nr.</th><th>Aukotojas(fizinio asmens vardas ir pavardė, juridinio asmens pavadinimas)</th>
<th>Savivaldybės pavadinimas</th><th>Data</th><th>Aukos suma, Lt</th><th>PastabosNepiniginė auka, auka grynais, kita</th></tr>
<tr><td>1.</td><td>ZINAIDA PAGIRSKIENĖ</td><td>Vilniaus miesto</td><td>2013-12-30</td><td>100,00</td><td></td></tr>
<tr><td align="right" colspan="4"><b>Iš viso:</b></td><td><b>100,00</b></td><td></td></tr>
<tr><td align="right" colspan="4">juridinių asmenų:</td><td>0,00</td><td>Nuo 2012-01-01 draudžiamos</td></tr>
</table>
"""
)

EUR_AND_LT_2015 = _page(
    """
<h3>Gautos ir priimtos aukos:</h3>
<table class="partydata">
<tr><th>Eil. nr.</th><th>Aukotojas(fizinio asmens vardas ir pavardė, juridinio asmens pavadinimas)</th>
<th>Savivaldybės pavadinimas</th><th>Data</th><th>Aukos suma, Eur</th><th>Aukos suma, Lt</th><th>PastabosNepiniginė auka, auka grynais, kita</th></tr>
<tr><td>1.</td><td>JONAS JONAITIS</td><td>Vilniaus miesto</td><td>2015-01-30</td><td>1050,00</td><td>3625,44</td><td></td></tr>
<tr><td align="right" colspan="4"><b>Iš viso:</b></td><td><b>1050,00</b></td><td><b>3625,44</b></td><td></td></tr>
</table>
"""
)

EUR_ONLY_2015 = _page(
    """
<h3>Gautos ir priimtos aukos:</h3>
<table class="partydata">
<tr><th>Eil. nr.</th><th>Aukotojas(fizinio asmens vardas ir pavardė, juridinio asmens pavadinimas)</th>
<th>Savivaldybės pavadinimas</th><th>Data</th><th>Aukos suma, Eur</th><th>PastabosNepiniginė auka, auka grynais, kita</th></tr>
<tr><td>1.</td><td>ONA ONAITĖ</td><td>Telšių rajono</td><td>2015-10-30</td><td>5000,00</td><td></td></tr>
<tr><td align="right" colspan="4"><b>Iš viso:</b></td><td><b>5000,00</b></td><td></td></tr>
</table>
"""
)

STRONG_HEADED_2009 = _page(
    """
<h3>Aukotojų sąrašas</h3>
<table class="partydata">
<tr><td><strong>Eil. nr.</strong></td><td><strong>Aukotojas</strong></td><td><strong>Savivaldybė</strong></td>
<td><strong>Aukos suma, Lt</strong></td><td><strong>Aukos data</strong></td></tr>
<tr><td>1</td><td> DALIA GRYBAUSKAITĖ </td><td>Vilniaus miesto </td><td> 11600,00</td><td>2009-02-26</td></tr>
<tr><td>2</td><td>RAJINDER KUMAR CHAUDHARY, nepriimtina auka</td><td>Vilniaus miesto</td><td>750,00</td><td>2009-04-07</td></tr>
<tr><td>3</td><td>JUOZAS JURGINIS, nepriintina auka</td><td>Vilniaus miesto</td><td>100,00</td><td>2009-04-30</td></tr>
<tr><td>4</td><td>Neviešinamas, jo paties prašymu</td><td>Vilniaus miesto</td><td>99,00</td><td>2009-04-02</td></tr>
<tr><td> </td><td> </td><td><b>Iš viso:</b></td><td><b> 12549,00</b></td><td> </td></tr>
</table>
"""
)

REPORTS_2014 = _page(
    """
<table class="partydata">
<tr><th>Eil. Nr.</th><th>Patvirtinimo data</th><th>Statusas</th><th>Ataskaita</th><th>Priedas dėl politinės reklamos</th></tr>
<tr><td>1.</td><td>2014-08-25</td><td>Patikrinta. Yra pastabų</td><td><a href="/a.pdf">Peržiūrėti</a></td><td><a href="/b.pdf">Peržiūrėti</a></td></tr>
</table>
"""
)

REPORTS_2009 = _page(
    """
<table class="partydata">
<tr><td colspan="4"><h3>Politinės kampanijos dalyvio finansavimo ataskaitas</h3></td></tr>
<tr><td><strong>Eil. Nr.</strong></td><td><strong>Patvirtinimo data</strong></td><td><strong>Ataskaitos tipas</strong></td><td><strong>Ataskaita</strong></td></tr>
<tr><td>1</td><td>2009-05-06</td><td> Pradinė </td><td><a href="/c.pdf">Peržiūrėti</a></td></tr>
</table>
"""
)

COMPANY_AUDITOR_2009 = _page(
    """
<table class="partydata">
<tr><td colspan="2"><h3>Savarankiško politinės kampanijos dalyvio auditorius</h3></td></tr>
<tr><td><strong>Pavadinimas:</strong></td><td>UAB "ZITAUDA"</td></tr>
<tr><td><strong>Kodas:</strong></td><td>125790998</td></tr>
<tr><td><strong>Telefonas:</strong></td><td>852742726</td></tr>
<tr><td><strong>El. paštas:</strong></td><td>m.zita@b4net.lt</td></tr>
</table>
"""
)


class DonationTotalsAreKeyedByHeaderTests(unittest.TestCase):
    def test_litas_only_total_lands_under_amount_lt(self) -> None:
        section = _parse_aukos_html(LT_ONLY_2014)["sections"][0]
        self.assertEqual(section["title"], "Gautos ir priimtos aukos")
        self.assertEqual(section["records"][0]["amountLt"], 100)
        self.assertNotIn("amountEur", section["records"][0])
        self.assertEqual(
            section["summary"],
            [
                {"label": "Iš viso", "amountEur": None, "amountLt": 100, "note": None},
                {"label": "juridinių asmenų", "amountEur": None, "amountLt": 0, "note": "Nuo 2012-01-01 draudžiamos"},
            ],
        )

    def test_dual_currency_total_keeps_both(self) -> None:
        section = _parse_aukos_html(EUR_AND_LT_2015)["sections"][0]
        self.assertEqual(section["summary"], [{"label": "Iš viso", "amountEur": 1050, "amountLt": 3625.44, "note": None}])

    def test_euro_only_total_lands_under_amount_eur(self) -> None:
        section = _parse_aukos_html(EUR_ONLY_2015)["sections"][0]
        self.assertEqual(section["summary"], [{"label": "Iš viso", "amountEur": 5000, "amountLt": None, "note": None}])


class StrongHeadedTablesTests(unittest.TestCase):
    def test_2009_donor_list(self) -> None:
        section = _parse_aukos_html(STRONG_HEADED_2009)["sections"][0]
        self.assertEqual(section["title"], "Aukotojų sąrašas")
        # The heading row is not a record; the full-width totals row is a
        # summary; the inline flag becomes the notes column.
        self.assertEqual(len(section["records"]), 4)
        self.assertEqual(
            section["records"][0],
            {"rowNumber": "1", "donor": "DALIA GRYBAUSKAITĖ", "municipality": "Vilniaus miesto", "amountLt": 11600, "date": "2009-02-26"},
        )
        self.assertEqual(section["records"][1]["donor"], "RAJINDER KUMAR CHAUDHARY")
        self.assertEqual(section["records"][1]["notes"], "nepriimtina auka")
        self.assertEqual(section["records"][2]["notes"], "nepriintina auka")
        self.assertEqual(section["records"][3]["donor"], "Neviešinamas, jo paties prašymu")
        self.assertNotIn("notes", section["records"][3])
        self.assertEqual(section["summary"], [{"label": "Iš viso", "amountEur": None, "amountLt": 12549, "note": None}])

    def test_reports_map_columns_by_heading(self) -> None:
        self.assertEqual(
            _parse_finansavimo_ataskaitos_html(REPORTS_2014),
            [
                {
                    "rowNumber": "1.",
                    "approvedDate": "2014-08-25",
                    "status": "Patikrinta. Yra pastabų",
                    "reportUrls": ["https://www.vrk.lt/a.pdf"],
                    "advertisingAppendixUrls": ["https://www.vrk.lt/b.pdf"],
                }
            ],
        )
        self.assertEqual(
            _parse_finansavimo_ataskaitos_html(REPORTS_2009),
            [
                {
                    "rowNumber": "1",
                    "approvedDate": "2009-05-06",
                    "status": None,
                    "reportUrls": ["https://www.vrk.lt/c.pdf"],
                    "advertisingAppendixUrls": [],
                    "reportType": "Pradinė",
                }
            ],
        )

    def test_company_auditor_without_the_imones_qualifier(self) -> None:
        person = _parse_campaign_person_html(COMPANY_AUDITOR_2009)["person"]
        self.assertEqual(
            person,
            {
                "vardas-pavarde": None,
                "telefonas": "852742726",
                "el-pastas": "m.zita@b4net.lt",
                "imones-pavadinimas": 'UAB "ZITAUDA"',
                "imones-kodas": "125790998",
            },
        )


ANKETA_WITH_DEAD_TAB = """
<html><body>
<ul id="tabnav">
<li><a href="/r/403_lt/Kandidatai/Kandidatas1/Kandidato1Anketa.html">Anketa</a></li>
<li><a href="/r/403_lt/Kandidatai/Kandidatas1/Kandidato1Patiketiniai.html">Patikėtiniai</a></li>
</ul>
</body></html>
"""


class UnpublishedTabTests(unittest.TestCase):
    def test_unpublished_tab_is_recorded_not_fetched(self) -> None:
        fetched: list[str] = []

        def fake_fetch(url: str) -> str:
            fetched.append(url)
            return ANKETA_WITH_DEAD_TAB

        entry = {"candidateId": "x", "candidateName": "X", "url": "https://www.vrk.lt/r/403_lt/Kandidatai/Kandidatas1/Kandidato1Anketa.html"}
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "scraper.elections.seimo_zirmunu_2015.candidate_samples.fetch_text", side_effect=fake_fetch
        ):
            result = _fetch_candidate_tabs(
                entry=entry,
                samples_root=Path(tmp),
                allow_new_candidate_dir=True,
                election_id="t",
                expected_tabs={"anketa"},
                unpublished_tabs={"patiketiniai"},
            )
            index = json.loads(Path(result["index_path"]).read_text(encoding="utf-8"))

        self.assertEqual(fetched, [entry["url"]])
        self.assertEqual(result["tab_count"], 1)
        self.assertEqual(result["anomalies"], [])
        self.assertEqual([tab["slug"] for tab in index["unpublishedTabs"]], ["patiketiniai"])
        self.assertEqual(index["missingExpectedTabs"], [])

    def test_without_the_option_the_dead_tab_is_fetched_and_fails_loudly(self) -> None:
        def fake_fetch(url: str) -> str:
            if url.endswith("Patiketiniai.html"):
                raise RuntimeError("404")
            return ANKETA_WITH_DEAD_TAB

        entry = {"candidateId": "x", "candidateName": "X", "url": "https://www.vrk.lt/r/403_lt/Kandidatai/Kandidatas1/Kandidato1Anketa.html"}
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "scraper.elections.seimo_zirmunu_2015.candidate_samples.fetch_text", side_effect=fake_fetch
        ):
            result = _fetch_candidate_tabs(
                entry=entry,
                samples_root=Path(tmp),
                allow_new_candidate_dir=True,
                election_id="t",
                expected_tabs={"anketa", "patiketiniai"},
            )
        self.assertEqual({event["eventType"] for event in result["anomalies"]}, {"TabDownloadFailed", "TabDownloadPartial"})
        self.assertEqual(result["unpublished_tabs"], [])


if __name__ == "__main__":
    unittest.main()
