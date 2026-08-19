"""Pins for the tier-1 normalization cleanups of 2026-08-19.

Four defects surfaced by the corpus-wide review, all in shared seimo_2016
code, all guarded here on synthetic payloads so they cannot drift back:

- ID001P records fell back to stulpelis-N keys because the 2019-era pages
  publish six of the seven column headers empty; the canonical 2016 column
  names are now supplied by position.
- ID001A KITI DUOMENYS rendered as a one-column table normalized into a list
  keyed by a 140-character sentence slug; it now folds to the same
  ``{"tekstas": ...}`` shape the 2016-era free-text form produces.
- A nested record-table row with an empty cell lost its column alignment
  (the empties were filtered before pairing with headers) and fell through
  to a bare value array — the only mixed-type list in the corpus.
- Mixed unicode normalization forms survived into normalized values; an NFD
  "ė" would not string-match its NFC form.
"""

from __future__ import annotations

import unicodedata
import unittest

from bs4 import BeautifulSoup

from scraper.elections.seimo_2016.anketa_parser import (
    ID001P_COLUMN_KEYS,
    _normalize_privaciu_interesu_data,
    _normalize_text_value,
    _parse_nested_table,
)


class Id001pCanonicalColumnsTests(unittest.TestCase):
    def test_headerless_columns_get_the_canonical_keys(self) -> None:
        # The 2019-era table publishes only the first column heading.
        payload = {
            "sections": [
                {
                    "title": "ID001P DUOMENYS APIE RYŠIUS",
                    "sectionId": "id001p",
                    "columns": ["Asmuo, kurio ryšys toliau bus nurodomas"],
                    "rows": [
                        [
                            "Deklaruojantysis",
                            "Lietuvos Respublika",
                            "KIT",
                            "2018-09-13",
                            "168976371",
                            "GYVENTOJŲ BENDRUOMENĖS CENTRAS",
                            "BENDRUOMENĖS PIRMININKĖ",
                        ]
                    ],
                }
            ]
        }
        normalized = _normalize_privaciu_interesu_data(payload)
        record = normalized["id001p"][0]
        self.assertEqual(list(record.keys()), ID001P_COLUMN_KEYS)
        self.assertEqual(record["valstybe"], "Lietuvos Respublika")
        self.assertEqual(record["rysio-data"], "2018-09-13")
        self.assertNotIn("stulpelis-2", record)

    def test_other_sections_keep_the_stulpelis_fallback(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "ID001X",
                    "sectionId": "id001x",
                    "columns": [],
                    "rows": [["a", "b"]],
                }
            ]
        }
        record = _normalize_privaciu_interesu_data(payload)["id001x"][0]
        self.assertEqual(list(record.keys()), ["stulpelis-1", "stulpelis-2"])


class Id001aFoldTests(unittest.TestCase):
    def test_one_column_table_folds_to_tekstas(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "ID001A KITI DUOMENYS",
                    "sectionId": "id001a",
                    "columns": [
                        "Kiti duomenys, dėl kurių gali kilti interesų konfliktas"
                    ],
                    "rows": [["Pirmas sakinys."], ["Antras sakinys."]],
                }
            ]
        }
        normalized = _normalize_privaciu_interesu_data(payload)
        self.assertEqual(
            normalized["id001a"], {"tekstas": "Pirmas sakinys. Antras sakinys."}
        )


class NestedTableAlignmentTests(unittest.TestCase):
    def test_row_with_an_empty_cell_keeps_column_alignment(self) -> None:
        html = """
        <table border="1">
          <thead><tr>
            <th>Išsilavinimas</th><th>Mokymo įstaigos pavadinimas</th>
            <th>Specialybė</th><th>Baigimo metai</th>
          </tr></thead>
          <tr>
            <td></td><td>Vilniaus pedagoginis institutas</td>
            <td>Istorijos ir teisės mokytojas</td><td>1985</td>
          </tr>
        </table>
        """
        table = BeautifulSoup(html, "lxml").find("table")
        parsed = _parse_nested_table(table)
        self.assertEqual(
            parsed["rows"],
            [
                {
                    "Išsilavinimas": None,
                    "Mokymo įstaigos pavadinimas": "Vilniaus pedagoginis institutas",
                    "Specialybė": "Istorijos ir teisės mokytojas",
                    "Baigimo metai": "1985",
                }
            ],
        )

    def test_full_rows_parse_exactly_as_before(self) -> None:
        html = """
        <table border="1">
          <thead><tr><th>A</th><th>B</th></tr></thead>
          <tr><td>1</td><td>2</td></tr>
        </table>
        """
        table = BeautifulSoup(html, "lxml").find("table")
        self.assertEqual(_parse_nested_table(table)["rows"], [{"A": "1", "B": "2"}])


class NfcNormalizationTests(unittest.TestCase):
    def test_nfd_input_folds_to_nfc(self) -> None:
        nfd = unicodedata.normalize("NFD", "Šimonytė ė")
        self.assertNotEqual(nfd, "Šimonytė ė")
        self.assertEqual(_normalize_text_value(nfd), "Šimonytė ė")




class ConvictionEntriesTests(unittest.TestCase):
    def test_empty_block_is_an_empty_list(self) -> None:
        from scraper.elections.ep_2024.anketa_parser import _conviction_entries

        self.assertEqual(_conviction_entries(None, None, None, []), [])

    def test_populated_block_is_one_entry(self) -> None:
        from scraper.elections.ep_2024.anketa_parser import _conviction_entries

        entries = _conviction_entries(
            "2022-06-30", "Lietuva", "TEISMAS", [{"kaltes-forma": "Tyčinis"}]
        )
        self.assertEqual(
            entries,
            [
                {
                    "nuosprendzio-data": "2022-06-30",
                    "nuosprendzio-valstybe": "Lietuva",
                    "nuosprendzio-institucija": "TEISMAS",
                    "nusikalstamos-veikos": [{"kaltes-forma": "Tyčinis"}],
                }
            ],
        )


class DeadColumnSkipTests(unittest.TestCase):
    def test_id001f_personal_code_skipped_only_when_empty(self) -> None:
        payload = {
            "sections": [
                {
                    "title": "ID001F",
                    "sectionId": "id001f",
                    "columns": ["Vardas ir pavardė", "Asmens kodas"],
                    "rows": [["JONAS JONAITIS", ""]],
                }
            ]
        }
        record = _normalize_privaciu_interesu_data(payload)["id001f"][0]
        self.assertNotIn("asmens-kodas", record)
        self.assertEqual(record["vardas-ir-pavarde"], "JONAS JONAITIS")

    def test_2024_era_dead_columns_skipped_only_when_empty(self) -> None:
        from scraper.elections.ep_2024.anketa_parser import (
            _normalize_privaciu_interesu_data as normalize_2024,
        )

        payload = {
            "sections": [
                {
                    "title": "Ryšiai su juridiniais asmenimis",
                    "records": [
                        {
                            "items": [
                                {"key": "Ryšys", "value": ""},
                                {"key": "Ryšio pobūdis", "value": "Narys"},
                            ]
                        }
                    ],
                }
            ]
        }
        section = normalize_2024(payload)["rysiai-su-juridiniais-asmenimis"][0]
        self.assertNotIn("rysys", section)
        self.assertEqual(section["rysio-pobudis"], "Narys")


if __name__ == "__main__":
    unittest.main()
