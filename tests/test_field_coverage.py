"""`scripts/field_coverage.py` is the field-fill gate; this is what makes it trustworthy.

Issue #85: `2020-seimo` shipped with income `null` on all 1,753 records and a
green suite, because nothing measured how often a mapped field is filled. A
detector that under-reports is worse than none, so the two things it can get
wrong are pinned here: how a path resolves (against real records, parsed from
fixtures, not synthetic ones), and when the rules fire.

The checked-in `docs/coverage-baseline.tsv` is checked too -- for agreement
with the concept map, and for every zero-fill cell carrying a classification
and a reason. Those two run without `data/`, so a contributor who maps a new
election and never runs the script fails the suite rather than the gate.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import local_data
from scraper.cli import _parse_anketa_samples_for_election

REPO_ROOT = Path(__file__).resolve().parents[1]
ELECTION_ID = "2019-prezidento"
FIXTURES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID


def _load_script():
    path = REPO_ROOT / "scripts" / "field_coverage.py"
    spec = importlib.util.spec_from_file_location("field_coverage", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()
CONCEPT_MAP = json.loads((REPO_ROOT / script.CONCEPT_MAP).read_text(encoding="utf-8"))


class IsFilledTests(unittest.TestCase):
    def test_a_declared_zero_is_an_answer(self) -> None:
        # privalomas-registruoti-turtas is 0 for a candidate who registered
        # no property, and that zero is the declaration.
        self.assertTrue(script.is_filled(0))
        self.assertTrue(script.is_filled(0.0))
        self.assertTrue(script.is_filled(False))

    def test_nothing_is_not_an_answer(self) -> None:
        for value in (None, "", "   ", [], {}):
            self.assertFalse(script.is_filled(value), value)

    def test_text_and_rows_are_answers(self) -> None:
        self.assertTrue(script.is_filled("Ne"))
        self.assertTrue(script.is_filled([{"nuosprendzio-data": "1995-04-15"}]))


class ResolveTests(unittest.TestCase):
    def test_a_path_is_relative_to_normalized(self) -> None:
        record = {"normalized": {"biografija": {"gimimo-data": "1961-09-29"}}}
        self.assertEqual(script.resolve(record, "biografija.gimimo-data"), (True, True))

    def test_a_present_but_null_field_is_the_2020_seimo_shape(self) -> None:
        record = {"normalized": {"turto-ir-pajamu-deklaracijos": {"gautos-pajamos": None}}}
        self.assertEqual(
            script.resolve(record, "turto-ir-pajamu-deklaracijos.gautos-pajamos"),
            (True, False),
            "the key is present and the value is not: that is the whole defect",
        )

    def test_kandidatavimas_resolves_at_the_record_root(self) -> None:
        # 2007-vasario-25 and 2000-kovo-19 hoist the candidacy out of
        # `normalized`; a resolver that only walks `normalized` calls these
        # 100%-populated cells zeros.
        record = {"kandidatavimas": {"savivaldybe": "Vilniaus miesto"}, "normalized": {}}
        self.assertEqual(script.resolve(record, "kandidatavimas.savivaldybe"), (True, True))

    def test_kandidatavimas_also_resolves_inside_normalized(self) -> None:
        # And the two 1997 municipal archive elections leave it there, under
        # the same dotted path. Both shapes are in the corpus at once.
        record = {"normalized": {"kandidatavimas": {"savivaldybe": "Vilniaus miesto"}}}
        self.assertEqual(script.resolve(record, "kandidatavimas.savivaldybe"), (True, True))

    def test_a_missing_section_is_not_present(self) -> None:
        self.assertEqual(script.resolve({"normalized": {}}, "anketa.gimimo-data"), (False, False))
        self.assertEqual(script.resolve({}, "anketa.gimimo-data"), (False, False))

    def test_a_scalar_where_a_section_was_expected_does_not_raise(self) -> None:
        record = {"normalized": {"anketa": "Nenurodė"}}
        self.assertEqual(script.resolve(record, "anketa.gimimo-data"), (False, False))

    def test_alternatives_resolve_on_the_first_filled_one(self) -> None:
        # The municipal elections that ask the nominator once per seat.
        paths = [
            "profilis.kita.iskele-i-savivaldybes-merus.reiksme",
            "profilis.kita.iskele-i-tarybos-narius-ir-merus.reiksme",
        ]
        record = {
            "normalized": {
                "profilis": {
                    "kita": {
                        "iskele-i-savivaldybes-merus": {"reiksme": None},
                        "iskele-i-tarybos-narius-ir-merus": {"reiksme": "Liberalų sąjūdis"},
                    }
                }
            }
        }
        self.assertEqual(script.resolve_any(record, paths), (True, True))

    def test_alternatives_none_of_which_is_filled(self) -> None:
        paths = ["profilis.kita.a.reiksme", "profilis.kita.b.reiksme"]
        record = {"normalized": {"profilis": {"kita": {"a": {"reiksme": None}}}}}
        self.assertEqual(script.resolve_any(record, paths), (True, False))


class CheckTests(unittest.TestCase):
    """The two rules, on the shapes the corpus actually produced."""

    def _concept_at(self, *rates: tuple[str, int, int]) -> list:
        return [
            script.Cell("gautos-pajamos", election, records, records, filled)
            for election, records, filled in rates
        ]

    def test_the_2020_seimo_defect_is_an_error(self) -> None:
        cells = self._concept_at(
            ("2020-seimo", 1754, 0), ("2019-ep", 1000, 1000), ("2016-seimo", 1000, 978)
        )
        findings = script.check(cells, {}, max_drop=5.0)
        self.assertEqual(len(findings), 1)
        self.assertIn("2020-seimo", findings[0])
        self.assertIn("0 of 1754 records", findings[0])
        self.assertIn("2020-seimo shape", findings[0])

    def test_a_zero_needs_a_status_and_a_reason(self) -> None:
        cells = self._concept_at(("2020-seimo", 10, 0))
        for status, note in [
            (script.UNEXPLAINED, ""),
            ("upstream-absent", ""),
            ("made-up", "because"),
        ]:
            baseline = {("gautos-pajamos", "2020-seimo"): script.Baseline(0.0, status, note)}
            self.assertEqual(
                len(script.check(cells, baseline, max_drop=5.0)), 1, f"{status!r}/{note!r}"
            )

    def test_a_classified_zero_passes(self) -> None:
        cells = self._concept_at(("2020-seimo", 10, 0))
        baseline = {
            ("gautos-pajamos", "2020-seimo"): script.Baseline(
                0.0, "upstream-absent", "the page prints the label and no value"
            )
        }
        self.assertEqual(script.check(cells, baseline, max_drop=5.0), [])

    def test_empty_is_the_answer_may_not_hide_a_missing_key(self) -> None:
        # The claim is that the parser answered everywhere and the answer was
        # empty. A key that is absent on some records is a different thing.
        cells = [script.Cell("teistumo-detales", "2024-prezidento", 8, 5, 0)]
        baseline = {
            ("teistumo-detales", "2024-prezidento"): script.Baseline(
                0.0, "empty-is-the-answer", "nobody declared a conviction"
            )
        }
        findings = script.check(cells, baseline, max_drop=5.0)
        self.assertEqual(len(findings), 1)
        self.assertIn("absent on 3 of 8 records", findings[0])

    def test_a_drop_past_the_tolerance_is_an_error(self) -> None:
        cells = self._concept_at(("2016-seimo", 1000, 900))
        baseline = {("gautos-pajamos", "2016-seimo"): script.Baseline(97.8, "ok", "")}
        findings = script.check(cells, baseline, max_drop=5.0)
        self.assertEqual(len(findings), 1)
        self.assertIn("90.0% filled, was 97.8%", findings[0])

    def test_a_drop_inside_the_tolerance_is_not(self) -> None:
        cells = self._concept_at(("2016-seimo", 1000, 950))
        baseline = {("gautos-pajamos", "2016-seimo"): script.Baseline(97.8, "ok", "")}
        self.assertEqual(script.check(cells, baseline, max_drop=5.0), [])

    def test_a_rise_is_never_an_error(self) -> None:
        cells = self._concept_at(("2016-seimo", 1000, 1000))
        baseline = {("gautos-pajamos", "2016-seimo"): script.Baseline(50.0, "ok", "")}
        self.assertEqual(script.check(cells, baseline, max_drop=5.0), [])

    def test_an_election_with_no_records_is_not_a_finding(self) -> None:
        self.assertEqual(script.check([script.Cell("x", "y", 0, 0, 0)], {}, 5.0), [])


class BaselineFileTests(unittest.TestCase):
    def test_a_classification_survives_a_rewrite(self) -> None:
        cells = [script.Cell("porinkiminis-numeris", "2025-kovo-16-meru", 14, 14, 0)]
        previous = {
            ("porinkiminis-numeris", "2025-kovo-16-meru"): script.Baseline(
                0.0, "upstream-absent", "a single-seat election has no list"
            )
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.tsv"
            script.write_baseline(path, cells, previous)
            self.assertEqual(script.read_baseline(path), previous)

    def test_a_cell_that_stopped_being_zero_loses_its_excuse(self) -> None:
        # Otherwise a field that comes back and then breaks again inherits an
        # explanation nobody re-checked.
        cells = [script.Cell("gautos-pajamos", "2020-seimo", 1754, 1754, 1700)]
        previous = {
            ("gautos-pajamos", "2020-seimo"): script.Baseline(0.0, "upstream-absent", "was broken")
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.tsv"
            script.write_baseline(path, cells, previous)
            self.assertEqual(
                script.read_baseline(path),
                {("gautos-pajamos", "2020-seimo"): script.Baseline(96.9, script.OK, "")},
            )

    def test_a_new_zero_is_written_unexplained(self) -> None:
        cells = [script.Cell("gautos-pajamos", "2020-seimo", 1754, 1754, 0)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.tsv"
            script.write_baseline(path, cells, {})
            self.assertEqual(
                script.read_baseline(path)[("gautos-pajamos", "2020-seimo")].status,
                script.UNEXPLAINED,
            )


class CheckedInBaselineTests(unittest.TestCase):
    """The committed baseline, checked without needing the corpus."""

    baseline = script.read_baseline(REPO_ROOT / script.BASELINE)

    def test_it_covers_every_mapped_cell(self) -> None:
        mapped = {
            (concept, election)
            for concept, paths in script.concept_paths(CONCEPT_MAP).items()
            for election in paths
        }
        missing = sorted(mapped - set(self.baseline))
        self.assertEqual(
            missing,
            [],
            "concept-map.json gained cells with no measured fill rate;"
            " run scripts/field_coverage.py --update-baseline",
        )

    def test_it_maps_nothing_the_concept_map_dropped(self) -> None:
        mapped = {
            (concept, election)
            for concept, paths in script.concept_paths(CONCEPT_MAP).items()
            for election in paths
        }
        self.assertEqual(sorted(set(self.baseline) - mapped), [])

    def test_every_zero_carries_a_status_and_a_reason(self) -> None:
        unexplained = sorted(
            key
            for key, row in self.baseline.items()
            if row.pct == 0.0 and (row.status not in script.ZERO_STATUSES or not row.note.strip())
        )
        self.assertEqual(
            unexplained,
            [],
            "a mapped path no record fills has to say which of"
            f" {sorted(script.ZERO_STATUSES)} it is, and why",
        )

    def test_a_filled_cell_carries_no_excuse(self) -> None:
        self.assertEqual(
            sorted(key for key, row in self.baseline.items() if row.pct and row.status != script.OK),
            [],
        )


class RealRecordTests(unittest.TestCase):
    """Resolve against records a parser actually produced, not hand-built ones."""

    @classmethod
    def setUpClass(cls) -> None:
        local_data.require(FIXTURES_ROOT)
        cls._tmp = tempfile.TemporaryDirectory()
        cls.data_root = Path(cls._tmp.name)
        _parse_anketa_samples_for_election(
            election_id=ELECTION_ID,
            candidate_ids=None,
            samples_root=FIXTURES_ROOT,
            output_root=cls.data_root / ELECTION_ID,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_every_concept_mapped_to_this_election_resolves(self) -> None:
        cells = script.measure(self.data_root, script.concept_paths(CONCEPT_MAP), [ELECTION_ID])
        self.assertTrue(cells)
        absent = [cell.concept for cell in cells if cell.key_present == 0]
        self.assertEqual(absent, [], "a mapped path whose key no record even carries")

    def test_the_declared_income_is_measured_not_assumed(self) -> None:
        cells = script.measure(self.data_root, script.concept_paths(CONCEPT_MAP), [ELECTION_ID])
        income = next(cell for cell in cells if cell.concept == "gautos-pajamos")
        self.assertEqual(income.records, income.key_present)
        self.assertGreater(income.non_null, 0, "this is the cell 2020-seimo got wrong")

    def test_wiping_one_field_is_caught_as_the_2020_seimo_shape(self) -> None:
        """The end-to-end claim: break the corpus the way it was broken."""
        for path in (self.data_root / ELECTION_ID).glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            record["normalized"]["turto-ir-pajamu-deklaracijos"]["gautos-pajamos"] = None
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

        cells = script.measure(self.data_root, script.concept_paths(CONCEPT_MAP), [ELECTION_ID])
        # Alongside the real rates of every other election that maps the
        # concept, so the "filled everywhere else" half of the rule is real.
        elsewhere = [
            script.Cell("gautos-pajamos", election, 100, 100, int(row.pct))
            for (concept, election), row in CheckedInBaselineTests.baseline.items()
            if concept == "gautos-pajamos" and election != ELECTION_ID
        ]
        findings = script.check(cells + elsewhere, {}, max_drop=5.0)
        mine = [f for f in findings if f.startswith("gautos-pajamos\t" + ELECTION_ID)]
        self.assertEqual(len(mine), 1)
        self.assertIn("records fill a mapped path", mine[0])
        self.assertIn("2020-seimo shape", mine[0])


if __name__ == "__main__":
    unittest.main()
