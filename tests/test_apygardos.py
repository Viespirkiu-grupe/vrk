"""The constituency normaliser (issue #133): four label eras, one name per district.

315 raw labels over 9,309 candidacies -- "Akmenės - Joniškio", "Akmenės
Joniškio", "Aukštaitijos (Nr. 28)", "Aukštaitijos Nr. 33", "33. Aukštaitijos"
-- and 2,980 rows that said "Daugiamandatė" where the candidate stood on the
list alone. `docs/constituency-forms.tsv` is the measured table of every
published form; on a clone it holds the corpus's spellings to the rule.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import local_data

from scraper.shared.apygardos import DASHLESS_ARCHIVE, apygarda, is_multi_mandate, normalize_name, number_of

REPO_ROOT = Path(__file__).resolve().parents[1]
FORMS_TABLE = REPO_ROOT / "docs" / "constituency-forms.tsv"


def forms_table_rows() -> list[tuple[str, int, str, str, str]]:
    rows = []
    for line in FORMS_TABLE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("form\t"):
            continue
        form, records, name, number, elections = (line.split("\t") + [""] * 5)[:5]
        rows.append((form, int(records), name, number, elections))
    return rows


class NameTests(unittest.TestCase):
    def test_every_era_of_one_district_is_one_name(self):
        for label in ("Aukštaitijos", "Aukštaitijos (Nr. 28)", "Aukštaitijos Nr. 33", "33. Aukštaitijos", "Aukštaitijos apygarda"):
            with self.subTest(label):
                self.assertEqual(normalize_name(label), "Aukštaitijos")

    def test_every_dash_form_is_the_en_dash(self):
        for label in ("Akmenės - Joniškio", "Akmenės-Joniškio", "Akmenės–Joniškio", "Akmenės — Joniškio", "Akmenės Joniškio"):
            with self.subTest(label):
                self.assertEqual(normalize_name(label), "Akmenės–Joniškio")

    def test_a_two_word_district_is_not_joined(self):
        self.assertEqual(normalize_name("Šiaulių kaimiškoji"), "Šiaulių kaimiškoji")
        self.assertEqual(normalize_name("Naujosios Vilnios (Nr. 10)"), "Naujosios Vilnios")
        self.assertEqual(normalize_name("27. Panevėžio vakarinė"), "Panevėžio vakarinė")

    def test_vrks_own_typos_resolve(self):
        self.assertEqual(normalize_name("Raseinių–Kėdainių( 42)"), "Raseinių–Kėdainių")
        self.assertEqual(normalize_name("Varėnos - Eišiškių (Nr.70)"), "Varėnos–Eišiškių")
        self.assertEqual(normalize_name("Žirmūnų (Nr.4)"), "Žirmūnų")

    def test_the_multi_mandate_marker_is_not_a_district(self):
        for label in ("Daugiamandatė", "Daugiamandatė, šioje apygardoje išrinktas Seimo nariu."):
            with self.subTest(label):
                self.assertTrue(is_multi_mandate(label))
                self.assertIsNone(normalize_name(label))
        self.assertFalse(is_multi_mandate("Dainavos"))

    def test_nothing_is_none(self):
        for value in (None, "", "   ", 42):
            self.assertIsNone(normalize_name(value))

    def test_the_dashless_aliases_map_to_themselves_dashed(self):
        for dashless, dashed in DASHLESS_ARCHIVE.items():
            with self.subTest(dashless):
                self.assertEqual(normalize_name(dashed), dashed)
                self.assertEqual(normalize_name(dashless), dashed)
                self.assertIn("–", dashed)


class NumberTests(unittest.TestCase):
    def test_the_number_is_read_from_any_position(self):
        self.assertEqual(number_of("4. Žirmūnų"), 4)
        self.assertEqual(number_of("Žirmūnų (Nr. 4)"), 4)
        self.assertEqual(number_of("Žirmūnų Nr. 4"), 4)
        self.assertEqual(number_of("Raseinių–Kėdainių( 42)"), 42)
        self.assertIsNone(number_of("Žirmūnų"))
        self.assertIsNone(number_of(None))


class DerivedTests(unittest.TestCase):
    def test_the_records_own_number_wins_over_the_label(self):
        self.assertEqual(
            apygarda("Šiaulių kaimiškoji", 45),
            {"apygarda": "Šiaulių kaimiškoji", "apygardos-numeris": 45, "apygarda-raw": "Šiaulių kaimiškoji"},
        )
        self.assertEqual(apygarda("Dzūkijos (Nr. 69)"), {"apygarda": "Dzūkijos", "apygardos-numeris": 69, "apygarda-raw": "Dzūkijos (Nr. 69)"})
        self.assertEqual(apygarda("Dzūkijos (Nr. 69)", "70")["apygardos-numeris"], 70)

    def test_a_list_only_row_has_no_constituency_and_no_number(self):
        self.assertEqual(apygarda("Daugiamandatė", 3), {"apygarda": None, "apygardos-numeris": None, "apygarda-raw": "Daugiamandatė"})
        self.assertEqual(apygarda(None), {"apygarda": None, "apygardos-numeris": None, "apygarda-raw": None})


class FormsTableTests(unittest.TestCase):
    def test_every_measured_form_resolves_as_the_table_says(self):
        rows = forms_table_rows()
        self.assertGreater(len(rows), 200)
        for form, _records, name, number, _elections in rows:
            with self.subTest(form):
                self.assertEqual(normalize_name(form) or "", name)
                self.assertEqual(str(number_of(form) or ""), number)

    def test_the_multi_mandate_forms_resolve_to_no_district(self):
        rows = forms_table_rows()
        self.assertTrue(any(form.startswith("Daugiamandat") and name == "" for form, _, name, _, _ in rows))

    def test_every_dashless_alias_is_a_published_form(self):
        forms = {form for form, *_ in forms_table_rows()}
        self.assertEqual(sorted(set(DASHLESS_ARCHIVE) - forms), [])

    def test_the_corpus_holds_no_form_the_table_lacks(self):
        # A sample of every Seimas election's records against the table.
        local_data.require_corpus()
        import json

        from scraper.shared.kandidatura import kandidatura

        forms = {form for form, *_ in forms_table_rows()}
        registry = {e["id"]: e for e in json.loads((REPO_ROOT / "scraper" / "elections.json").read_text(encoding="utf-8"))["elections"]}
        unknown = set()
        for eid, entry in registry.items():
            if entry["kind"] != "seimo" or not (REPO_ROOT / "data" / eid).is_dir():
                continue
            paths = sorted(p for p in (REPO_ROOT / "data" / eid).glob("*.json") if p.name != "anomalies.jsonl")
            for path in paths[:: max(1, len(paths) // 60)]:
                raw = kandidatura(json.loads(path.read_text(encoding="utf-8")), "seimo")["apygarda-raw"]
                if raw and raw not in forms:
                    unknown.add(raw)
        self.assertEqual(sorted(unknown), [], "run scripts/constituency_report.py --update")


if __name__ == "__main__":
    unittest.main()
