"""The plausibility gate, on the shapes the corpus actually held (issue #152).

Three commands check the corpus and none of them asked whether a value is
*possible*: `reparse_diff` asks whether the corpus is what the parsers
produce (a faithfully parsed impossibility still is), `field_coverage` asks
whether a field arrived (`gimimo-data` arrives on 99.8 % of records, and one
says a candidate was 1.4 years old), and `anomalies-report` reads back what
the scrapers recorded going wrong — 9,018 events of ten types, none about
plausibility.

Every example below is a value the corpus held, and each of the 42 was traced
verbatim to its own record's `rawData`, so they are VRK's typing carried
faithfully rather than parse damage.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "value_plausibility", REPO_ROOT / "scripts" / "value_plausibility.py"
)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

SEIMAS_2024 = {"id": "2024-seimo", "date": "2024-10-13", "kind": "seimo"}
SEIMAS_1996 = {"id": "1996-spalio-20-seimo", "date": "1996-10-20", "kind": "seimo"}
MUNICIPAL_2023 = {"id": "2023-kovo-5", "date": "2023-03-05", "kind": "savivaldybiu"}
PRESIDENTIAL = {"id": "2024-prezidento", "date": "2024-05-12", "kind": "prezidento"}


def record(**normalized):
    return {"normalized": normalized}


class DateRangeTests(unittest.TestCase):
    def test_the_years_the_corpus_held(self):
        # 1111-11-11 five times, 9999-12-31, 0005-07-12, 3003-05-20, and the
        # `0204.05.04` a 2004 declaration prints as its Pildymo data.
        for value in ("1111-11-11", "9999-12-31", "0005-07-12", "3003-05-20",
                      "0204-05-04", "2914-08-01", "1010-11-09", "2998-01-01"):
            with self.subTest(value):
                found = gate.check_record(
                    record(anketa={"pildymo-data": value}), MUNICIPAL_2023, "x"
                )
                self.assertEqual([f.rule for f in found], ["date-out-of-range"])

    def test_a_date_inside_the_range_is_not_a_finding(self):
        for value in ("1900-01-01", "2100-12-31", "1932-10-18", "2026-09-10"):
            with self.subTest(value):
                self.assertEqual(
                    gate.check_record(record(anketa={"data": value}), MUNICIPAL_2023, "x"), []
                )

    def test_the_path_of_the_offending_value_is_named(self):
        found = gate.check_record(
            record(privaciu={"v-turtines-prievoles": [{"isipareigojimo-data": "9999-12-31"}]}),
            MUNICIPAL_2023,
            "x",
        )
        self.assertEqual(found[0].path, "normalized.privaciu.v-turtines-prievoles[].isipareigojimo-data")

    def test_a_non_date_string_is_not_scanned(self):
        for value in ("2024", "2024-10", "not a date", "1111-11-11-11", ""):
            with self.subTest(value):
                self.assertEqual(
                    gate.check_record(record(anketa={"x": value}), MUNICIPAL_2023, "x"), []
                )


class StatutoryAgeTests(unittest.TestCase):
    """This rule fires once on the whole corpus, and that is the point.

    The youngest candidate of every large election sits on the statutory
    floor to within a tenth of a year — Seimas 25.0–25.2 before Lithuania's
    2022 amendment and 21.0 after it, presidential 40.1–42.8, EP 21.1–23.9,
    municipal 18.1 and 20.0 — so one record at 1.4 is the single outlier in
    an otherwise exact distribution, and it is the field the person index
    keys identity on.
    """

    def test_the_one_real_finding(self):
        found = gate.check_record(
            record(anketa={"gimimo-data": "1995-05-22"}), SEIMAS_1996, "damanskis-adolfas"
        )
        self.assertEqual([f.rule for f in found], ["age-below-statutory-minimum"])
        self.assertIn("aged 1.4", found[0].facts)
        self.assertIn("must be 25", found[0].facts)

    def test_the_seimas_floor_follows_the_2022_amendment(self):
        # 21 of 2024-seimo's 1,740 candidates are between 21.0 and 24.3: a
        # flat floor of 25 reports every one of them, and a flat 21 misses
        # the real finding by a factor of fifteen.
        self.assertEqual(gate.statutory_min_age("seimo", "2020-10-11"), 25)
        self.assertEqual(gate.statutory_min_age("seimo", "2024-10-13"), 21)
        born_2003 = record(anketa={"gimimo-data": "2003-09-30"})
        self.assertEqual(gate.check_record(born_2003, SEIMAS_2024, "x"), [])
        self.assertEqual(
            [f.rule for f in gate.check_record(born_2003, {**SEIMAS_2024, "date": "2020-10-11"}, "x")],
            ["age-below-statutory-minimum"],
        )

    def test_every_offices_floor(self):
        for kind, floor in (("seimo", 25), ("prezidento", 40), ("ep", 21),
                            ("savivaldybiu", 18), ("mero", 18)):
            with self.subTest(kind):
                self.assertEqual(gate.statutory_min_age(kind, "2016-01-01"), floor)

    def test_a_candidate_on_the_floor_is_not_a_finding(self):
        # 2019-kovo-3's youngest is 18.1 and 2012-seimo's is 25.0; the
        # tolerance is what keeps a birthday on polling day out of the report.
        self.assertEqual(
            gate.check_record(record(anketa={"gimimo-data": "2005-01-01"}), MUNICIPAL_2023, "x"), []
        )
        self.assertEqual(
            gate.check_record(record(anketa={"gimimo-data": "1984-05-12"}), PRESIDENTIAL, "x"), []
        )

    def test_a_record_with_no_birth_date_is_not_a_finding(self):
        # The 1996-1999 archive family publishes none on any candidate page.
        self.assertEqual(gate.check_record(record(anketa={}), SEIMAS_1996, "x"), [])
        self.assertEqual(
            gate.check_record(record(anketa={"gimimo-data": "~1935"}), SEIMAS_1996, "x"), []
        )

    def test_the_biografija_section_is_read_too(self):
        found = gate.check_record(
            record(biografija={"gimimo-data": "1995-05-22"}), SEIMAS_1996, "x"
        )
        self.assertEqual([f.rule for f in found], ["age-below-statutory-minimum"])


class IncomeRatioTests(unittest.TestCase):
    """A total its own row 1 makes impossible.

    The archive parser's `trusted()` guard refuses a total the page's row 1
    contradicts *from below*, with a sub-litas tolerance for the era's
    truncation. The other direction was unchecked, and the threshold here is
    read off the corpus rather than picked: the two figures it flags are
    29,603× and 12,383×, and the next highest of 112,218 declarations is
    1,511× — a candidate with 170 Lt of employment income and 257,170 Lt of
    total income, which is a business owner and not an error.
    """

    @staticmethod
    def declaration(total, row):
        return record(**{
            "turto-ir-pajamu-deklaracijos": {
                "gautos-pajamos": total,
                "gautos-pajamos-darbo-santykiu": row,
            }
        })

    def test_the_two_unarguable_records(self):
        for total, row, ratio in ((334017647.47, 11283.19, "29603x"), (172087745.59, 13896.77, "12383x")):
            with self.subTest(ratio):
                found = gate.check_record(self.declaration(total, row), MUNICIPAL_2023, "x")
                self.assertEqual([f.rule for f in found], ["income-total-above-its-own-row"])
                self.assertIn(ratio, found[0].facts)

    def test_the_business_owner_next_to_them_is_not_a_finding(self):
        # 1,511x, and the corpus's highest ratio that is not an error.
        self.assertEqual(gate.check_record(self.declaration(257170.24, 170.24), MUNICIPAL_2023, "x"), [])

    def test_a_zero_or_absent_row_one_is_not_divided_by(self):
        for row in (0, 0.0, None):
            with self.subTest(repr(row)):
                self.assertEqual(
                    gate.check_record(self.declaration(1_000_000.0, row), MUNICIPAL_2023, "x"), []
                )

    def test_no_declaration_at_all(self):
        self.assertEqual(gate.check_record(record(anketa={}), MUNICIPAL_2023, "x"), [])
        self.assertEqual(
            gate.check_record(record(**{"turto-ir-pajamu-deklaracijos": None}), MUNICIPAL_2023, "x"), []
        )

    def test_the_asset_pair_is_deliberately_not_a_rule(self):
        # A year-start / year-end pair is a year apart and may differ by any
        # factor: the corpus holds a candidate whose year-start assets were
        # 0.01 Lt and year-end 196,272 -- a house, not a defect. A ratio
        # there flags 60 records to catch one, and that one is already in
        # SOURCE_ERRORS.
        assets = record(**{
            "turto-ir-pajamu-deklaracijos": {
                "turtas-ir-pinigines-lesos-metu-pradzioje": 0.01,
                "turtas-ir-pinigines-lesos-metu-pabaigoje": 196272.00,
            }
        })
        self.assertEqual(gate.check_record(assets, MUNICIPAL_2023, "x"), [])


class RegisterTests(unittest.TestCase):
    def test_a_finding_in_the_register_is_signed_off_and_a_new_one_is_not(self):
        finding = gate.Finding("date-out-of-range", "2024-seimo", "x", "normalized.a", "9999-12-31", "why")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "register.tsv"
            gate.write_register(path, [finding])
            register = gate.read_register(path)
            self.assertIn(finding.key, register)
            self.assertEqual(register[finding.key], "why")
            other = finding._replace(candidate="y")
            self.assertNotIn(other.key, register)

    def test_the_reason_survives_a_rewrite(self):
        # `--update` keeps each row's reason and re-measures the facts, so a
        # reviewed finding does not lose its evidence to a re-run.
        finding = gate.Finding("date-out-of-range", "e", "c", "p", "9999-12-31", "VRK's own typing")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "register.tsv"
            gate.write_register(path, [finding])
            gate.write_register(path, [finding._replace(facts=gate.read_register(path)[finding.key])])
            self.assertEqual(gate.read_register(path)[finding.key], "VRK's own typing")

    def test_a_tab_in_a_reason_cannot_break_the_columns(self):
        register = gate.read_register(REPO_ROOT / gate.REGISTER)
        self.assertTrue(register, "the checked-in register is missing or empty")
        for key, why in register.items():
            with self.subTest(key):
                self.assertTrue(why.strip(), "every registered finding needs a reason")


class CheckedInRegisterTests(unittest.TestCase):
    """The register is a claim about the corpus, and it is tracked."""

    REGISTER = gate.read_register(REPO_ROOT / gate.REGISTER)

    def test_it_holds_the_measured_counts(self):
        # 41 rows for 42 findings: the key is (rule, election, candidate,
        # path) and one 2007 record prints `1111-11-11` twice under the same
        # collapsed list path, so one row signs off both. The gate prints
        # both numbers for that reason.
        rules = {}
        for rule, _election, _candidate, _path in self.REGISTER:
            rules[rule] = rules.get(rule, 0) + 1
        self.assertEqual(
            rules,
            {"date-out-of-range": 38, "age-below-statutory-minimum": 1,
             "income-total-above-its-own-row": 2},
        )

    def test_every_rule_it_names_is_a_rule_the_gate_has(self):
        produced = set()
        for election, born in ((SEIMAS_1996, "1995-05-22"),):
            produced |= {f.rule for f in gate.check_record(record(anketa={"gimimo-data": born}), election, "x")}
        produced |= {f.rule for f in gate.check_record(record(anketa={"d": "9999-12-31"}), MUNICIPAL_2023, "x")}
        produced |= {
            f.rule
            for f in gate.check_record(
                record(**{"turto-ir-pajamu-deklaracijos": {
                    "gautos-pajamos": 1e9, "gautos-pajamos-darbo-santykiu": 1.0}}),
                MUNICIPAL_2023, "x",
            )
        }
        self.assertEqual({rule for rule, *_ in self.REGISTER}, produced)

    def test_the_one_age_finding_is_the_one_the_issue_named(self):
        ages = [row for row in self.REGISTER if row[0] == "age-below-statutory-minimum"]
        self.assertEqual(len(ages), 1)
        self.assertEqual(ages[0][1], "1996-spalio-20-seimo")
        self.assertTrue(ages[0][2].startswith("damanskis-adolfas"))


if __name__ == "__main__":
    unittest.main()
