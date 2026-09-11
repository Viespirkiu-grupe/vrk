import unittest

from bs4 import BeautifulSoup

from scraper.shared.anketa_tabs import _parse_donations_table


def _parse(html: str) -> dict:
    table = BeautifulSoup(html, "lxml").find("table")
    return _parse_donations_table(table)


# 2016 layout: every column present.
SEVEN_COLUMN_TABLE = """
<table class="partydata">
<tr>
  <th>Eil. nr.</th>
  <th>Aukotojas<br>(fizinio asmens vardas ir pavardė juridinio asmens pavadinimas)</th>
  <th>Savivaldybės pavadinimas</th>
  <th>Data</th>
  <th>Pajamų šaltinis</th>
  <th>Aukos suma, Eur</th>
  <th>Pastabos</th>
</tr>
<tr>
  <td>1.</td><td>VARDENIS PAVARDENIS</td><td>Kupiškio r.</td>
  <td>2016-06-28</td><td>KL</td><td align="right">1000,00&nbsp;</td><td>Piniginės lėšos, Priimta</td>
</tr>
<tr><td colspan="5" align="right"><b>Iš viso:</b></td><td align="right"><b>1000,00&nbsp;</b></td><td>&nbsp;</td></tr>
</table>
"""

# Later layout without the income-source column (2019 EP).
NO_INCOME_SOURCE_TABLE = """
<table class="partydata">
<tr>
  <th>Eil. nr.</th>
  <th>Aukotojas<br>(fizinio asmens vardas ir pavardė juridinio asmens pavadinimas)</th>
  <th>Savivaldybės pavadinimas</th>
  <th>Data</th>
  <th>Aukos suma, Eur</th>
  <th>Pastabos</th>
</tr>
<tr>
  <td>1.</td><td>JŪRATĖ KURLIANSKIENĖ</td><td></td>
  <td>2019-03-21</td><td align="right">100,00&nbsp;</td><td>Grąžinta aukotojui 2019-07-08</td>
</tr>
</table>
"""

# Later layout without the municipality column (2023 mayoral, 2024 Seimo).
NO_MUNICIPALITY_TABLE = """
<table class="partydata">
<tr>
  <th>Eil. nr.</th>
  <th>Aukotojas<br>(fizinio asmens vardas ir pavardė juridinio asmens pavadinimas)</th>
  <th>Data</th>
  <th>Pajamų šaltinis</th>
  <th>Aukos suma, Eur</th>
  <th>Pastabos</th>
</tr>
<tr>
  <td>1.</td><td>LIETUVOS SOCIALDEMOKRATŲ PARTIJA</td>
  <td>2023-07-25</td><td align="center">PL</td><td align="right">2500,00&nbsp;</td><td>Piniginės lėšos, Priimtas</td>
</tr>
<tr>
  <td>2.</td><td>ŽILVINAS AUKŠTIKALNIS</td>
  <td>2023-09-02</td><td align="center">KL</td><td align="right">4,96&nbsp;</td><td>Piniginės lėšos, Priimtas</td>
</tr>
</table>
"""

# The VRK-decision variant renames the notes column (2019 presidential).
VRK_DECISION_NOTES_TABLE = """
<table class="partydata">
<tr>
  <th>Eil. nr.</th>
  <th>Aukotojas<br>(fizinio asmens vardas ir pavardė juridinio asmens pavadinimas)</th>
  <th>Data</th>
  <th>Pajamų šaltinis</th>
  <th>Aukos suma, Eur</th>
  <th>VRK sprendimas, pastabos</th>
</tr>
<tr>
  <td>1.</td><td>ARVYDAS JUOZAITIS</td>
  <td>2019-05-10</td><td align="center">KL</td><td align="right">167,30&nbsp;</td>
  <td>Sp-427, Piniginės lėšos, Neapsispręsta dėl priėmimo</td>
</tr>
</table>
"""

# No headings at all: the 2016 column order is the fallback.
HEADERLESS_TABLE = """
<table class="partydata">
<tr>
  <td>1.</td><td>VARDENIS PAVARDENIS</td><td>Kupiškio r.</td>
  <td>2016-06-28</td><td>KL</td><td align="right">1000,00&nbsp;</td><td>Piniginės lėšos, Priimta</td>
</tr>
</table>
"""

RECORD_KEYS = [
    "rowNumber",
    "donor",
    "municipality",
    "date",
    "incomeSourceCode",
    "amount",
    "notes",
]


class CampaignDonationsTableTests(unittest.TestCase):
    def test_seven_column_table(self) -> None:
        parsed = _parse(SEVEN_COLUMN_TABLE)

        self.assertEqual(len(parsed["records"]), 1)
        self.assertEqual(
            parsed["records"][0],
            {
                "rowNumber": "1.",
                "donor": "VARDENIS PAVARDENIS",
                "municipality": "Kupiškio r.",
                "date": "2016-06-28",
                "incomeSourceCode": "KL",
                "amount": 1000.0,
                "notes": "Piniginės lėšos, Priimta",
            },
        )
        # The summary row is a total, not a donation.
        self.assertEqual(parsed["totals"]["is-viso"], 1000.0)

    def test_table_without_income_source_column(self) -> None:
        parsed = _parse(NO_INCOME_SOURCE_TABLE)

        self.assertEqual(len(parsed["records"]), 1)
        record = parsed["records"][0]
        self.assertEqual(record["donor"], "JŪRATĖ KURLIANSKIENĖ")
        self.assertEqual(record["date"], "2019-03-21")
        self.assertEqual(record["amount"], 100.0)
        self.assertEqual(record["notes"], "Grąžinta aukotojui 2019-07-08")
        # The missing column is kept as an empty value so the shape is stable.
        self.assertEqual(record["incomeSourceCode"], "")

    def test_table_without_municipality_column(self) -> None:
        parsed = _parse(NO_MUNICIPALITY_TABLE)

        self.assertEqual(len(parsed["records"]), 2)
        first, second = parsed["records"]
        self.assertEqual(first["donor"], "LIETUVOS SOCIALDEMOKRATŲ PARTIJA")
        self.assertEqual(first["date"], "2023-07-25")
        self.assertEqual(first["incomeSourceCode"], "PL")
        self.assertEqual(first["amount"], 2500.0)
        self.assertEqual(first["notes"], "Piniginės lėšos, Priimtas")
        self.assertEqual(first["municipality"], "")
        self.assertEqual(second["amount"], 4.96)

    def test_table_with_vrk_decision_notes_column(self) -> None:
        parsed = _parse(VRK_DECISION_NOTES_TABLE)

        self.assertEqual(len(parsed["records"]), 1)
        record = parsed["records"][0]
        self.assertEqual(record["incomeSourceCode"], "KL")
        self.assertEqual(record["amount"], 167.3)
        self.assertEqual(record["notes"], "Sp-427, Piniginės lėšos, Neapsispręsta dėl priėmimo")

    def test_headerless_table_falls_back_to_2016_column_order(self) -> None:
        parsed = _parse(HEADERLESS_TABLE)

        self.assertEqual(len(parsed["records"]), 1)
        self.assertEqual(parsed["records"][0]["municipality"], "Kupiškio r.")
        self.assertEqual(parsed["records"][0]["incomeSourceCode"], "KL")
        self.assertEqual(parsed["records"][0]["amount"], 1000.0)

    def test_every_variant_yields_the_same_record_keys(self) -> None:
        for label, html in (
            ("seven-column", SEVEN_COLUMN_TABLE),
            ("no-income-source", NO_INCOME_SOURCE_TABLE),
            ("no-municipality", NO_MUNICIPALITY_TABLE),
            ("vrk-decision-notes", VRK_DECISION_NOTES_TABLE),
            ("headerless", HEADERLESS_TABLE),
        ):
            with self.subTest(layout=label):
                for record in _parse(html)["records"]:
                    self.assertEqual(list(record.keys()), RECORD_KEYS)


if __name__ == "__main__":
    unittest.main()
