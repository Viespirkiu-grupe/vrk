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

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import local_data
from scraper.cli import _parse_anketa_samples_for_election

REPO_ROOT = Path(__file__).resolve().parents[1]
ELECTION_ID = "2019-prezidento"
FIXTURES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
DATA_ROOT = REPO_ROOT / "data"


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


class BelowPeersTests(unittest.TestCase):
    """The third per-cell rule (issue #135): a filled cell far under the
    concept's other elections. The two older rules cannot see a new
    election's regression -- no baseline row to fall from, and 8 % is not
    zero -- and a mirror with a synthetic 2027-seimo shipped birth dates
    nulled on 1,600 of 1,740 records as `ok`."""

    def _cells(self, new_pct_filled: int, peers: tuple[int, ...] = (1000, 1000, 978)) -> list:
        cells = [script.Cell("gimimo-data", f"peer-{i}", 1000, 1000, filled) for i, filled in enumerate(peers)]
        cells.append(script.Cell("gimimo-data", "2027-seimo", 1740, 1740, new_pct_filled))
        return cells

    def test_eight_percent_against_peers_at_a_hundred_is_a_finding(self) -> None:
        findings = script.check(self._cells(140), {}, max_drop=5.0)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].startswith("gimimo-data\t2027-seimo\t"))
        self.assertIn("8.0% filled (140 of 1740)", findings[0])
        self.assertIn("median 100.0%", findings[0])
        self.assertIn("the key is present on every record; 1600 carry no value", findings[0])
        self.assertIn("partly-answered", findings[0])

    def test_an_absent_key_is_said_so(self) -> None:
        cells = self._cells(140)
        cells[-1] = script.Cell("gimimo-data", "2027-seimo", 1740, 200, 140)
        self.assertIn("the key is absent on 1540 of 1740 records", script.check(cells, {}, 5.0)[0])

    def test_a_classified_low_cell_passes(self) -> None:
        baseline = {("gimimo-data", "2027-seimo"): script.Baseline(8.0, "partly-answered", "asked, skipped")}
        self.assertEqual(script.check(self._cells(140), baseline, 5.0), [])

    def test_a_low_status_needs_a_note(self) -> None:
        baseline = {("gimimo-data", "2027-seimo"): script.Baseline(8.0, "partly-published", "")}
        self.assertEqual(len(script.check(self._cells(140), baseline, 5.0)), 1)

    def test_a_zero_status_does_not_excuse_a_low_cell(self) -> None:
        baseline = {("gimimo-data", "2027-seimo"): script.Baseline(8.0, "upstream-absent", "was a zero once")}
        self.assertEqual(len(script.check(self._cells(140), baseline, 5.0)), 1)

    def test_the_threshold_is_the_default_and_is_a_parameter(self) -> None:
        # 74.9 % against a median of 100 is 25.1 points down: a finding at the
        # default, none at 30.
        self.assertEqual(len(script.check(self._cells(1303), {}, 5.0)), 1)
        self.assertEqual(script.check(self._cells(1303), {}, 5.0, max_below=30.0), [])
        self.assertEqual(script.check(self._cells(1306), {}, 5.0), [])

    def test_a_concept_not_filled_everywhere_sets_no_yardstick(self) -> None:
        # Peers at 70 %: the concept is an era question, and 8 % on a new
        # election is not a regression the rule can call.
        self.assertEqual(script.check(self._cells(140, peers=(700, 700, 650)), {}, 5.0), [])

    def test_a_concept_mapped_once_has_no_peers(self) -> None:
        self.assertEqual(script.check(self._cells(140, peers=()), {}, 5.0), [])

    def test_the_regression_rule_reports_a_drop_once(self) -> None:
        baseline = {("gimimo-data", "2027-seimo"): script.Baseline(100.0, "ok", "")}
        findings = script.check(self._cells(140), baseline, 5.0)
        self.assertEqual(len(findings), 1)
        self.assertIn("a drop of 92.0 points", findings[0])

    def test_peer_medians_agree_with_concept_fill_rate(self) -> None:
        cells = self._cells(140)
        medians = script.peer_medians(cells)
        for cell in cells:
            self.assertEqual(
                medians[(cell.concept, cell.election)],
                script.concept_fill_rate(cells, cell.concept, cell.election),
            )


def _synthetic_corpus(root: Path, election: str, records: list[dict]) -> None:
    directory = root / election
    directory.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(records):
        (directory / f"c{index:04d}-{election}.json").write_text(json.dumps(record), encoding="utf-8")


class UnmappedElectionRuleTests(unittest.TestCase):
    """An election with records under data/ that no concept maps is a finding
    (issue #135); until then the run said so on stderr and exited 0."""

    PATHS = {"gimimo-data": {"2024-seimo": "biografija.gimimo-data"}}

    def test_an_unmapped_election_with_records_is_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _synthetic_corpus(root, "2024-seimo", [{"normalized": {}}] * 2)
            _synthetic_corpus(root, "2027-seimo", [{"normalized": {}}] * 3)
            findings = script.unmapped_election_findings(root, self.PATHS, {})
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].startswith("*\t2027-seimo\t3 records"))

    def test_a_not_mapped_row_with_a_note_is_the_opt_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _synthetic_corpus(root, "2027-seimo", [{"normalized": {}}] * 3)
            excused = {("*", "2027-seimo"): script.Baseline(0.0, script.NOT_MAPPED, "publishes no questionnaire")}
            self.assertEqual(script.unmapped_election_findings(root, self.PATHS, excused), [])
            unexcused = {("*", "2027-seimo"): script.Baseline(0.0, script.NOT_MAPPED, "")}
            self.assertEqual(len(script.unmapped_election_findings(root, self.PATHS, unexcused)), 1)

    def test_a_directory_holding_only_an_anomaly_log_is_not_an_election(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "2027-seimo").mkdir()
            (root / "2027-seimo" / "anomalies.jsonl").write_text("{}\n", encoding="utf-8")
            self.assertEqual(script.unmapped_election_findings(root, self.PATHS, {}), [])


class PeerGapRuleTests(unittest.TestCase):
    """A new election maps every concept its closest mapped peer of the same
    kind maps, or says why not (issue #135). On the mirror that motivated it,
    an unmapped copy of 2024-seimo lost five candidacy-table columns and
    every cell that existed read 100 %."""

    REGISTRY = [
        {"id": "2023-kovo-5-savivaldybiu-tarybu-ir-meru", "date": "2023-03-05", "kind": "savivaldybiu"},
        {"id": "2020-seimo", "date": "2020-10-11", "kind": "seimo"},
        {"id": "2024-seimo", "date": "2024-10-13", "kind": "seimo"},
        {"id": "2027-seimo", "date": "2027-10-10", "kind": "seimo"},
    ]
    PATHS = {
        "gimimo-data": {"2020-seimo": "a", "2024-seimo": "a", "2027-seimo": "a", "2023-kovo-5-savivaldybiu-tarybu-ir-meru": "a"},
        "gimimo-vieta": {"2020-seimo": "b", "2024-seimo": "b", "2023-kovo-5-savivaldybiu-tarybu-ir-meru": "b"},
        "iskele": {"2020-seimo": "c", "2024-seimo": "c"},
        "savivaldybe": {"2023-kovo-5-savivaldybiu-tarybu-ir-meru": "d"},
    }
    BASELINE = {
        ("gimimo-data", "2020-seimo"): script.Baseline(100.0, "ok", ""),
        ("gimimo-data", "2024-seimo"): script.Baseline(100.0, "ok", ""),
        ("gimimo-vieta", "2024-seimo"): script.Baseline(99.0, "ok", ""),
        ("iskele", "2024-seimo"): script.Baseline(100.0, "ok", ""),
        ("savivaldybe", "2023-kovo-5-savivaldybiu-tarybu-ir-meru"): script.Baseline(100.0, "ok", ""),
    }

    def test_the_new_election_is_measured_against_the_nearest_of_its_kind(self) -> None:
        findings = script.peer_gap_findings(self.PATHS, self.REGISTRY, ["2027-seimo", "2024-seimo"], self.BASELINE)
        self.assertEqual([script.finding_key(f) for f in findings], [("gimimo-vieta", "2027-seimo"), ("iskele", "2027-seimo")])
        self.assertIn("the closest mapped seimo election, 2024-seimo, maps this concept", findings[0])
        # The municipal `savivaldybe` is not asked of a Seimas election.
        self.assertNotIn("savivaldybe", " ".join(findings))

    def test_a_not_mapped_row_with_a_note_answers_a_gap(self) -> None:
        baseline = dict(self.BASELINE)
        baseline[("iskele", "2027-seimo")] = script.Baseline(0.0, script.NOT_MAPPED, "the 2027 card names no nominator")
        findings = script.peer_gap_findings(self.PATHS, self.REGISTRY, ["2027-seimo"], baseline)
        self.assertEqual([script.finding_key(f) for f in findings], [("gimimo-vieta", "2027-seimo")])

    def test_an_election_with_baseline_rows_is_not_new(self) -> None:
        baseline = dict(self.BASELINE)
        baseline[("gimimo-data", "2027-seimo")] = script.Baseline(100.0, "ok", "")
        self.assertEqual(script.peer_gap_findings(self.PATHS, self.REGISTRY, ["2027-seimo"], baseline), [])

    def test_a_new_election_the_registry_lacks_is_its_own_finding(self) -> None:
        paths = {"gimimo-data": {"2024-seimo": "a", "2099-x": "a"}}
        findings = script.peer_gap_findings(paths, self.REGISTRY, ["2099-x"], self.BASELINE)
        self.assertEqual(len(findings), 1)
        self.assertIn("no scraper/elections.json entry", findings[0])

    def test_no_registry_at_all_is_said_so(self) -> None:
        findings = script.peer_gap_findings(self.PATHS, None, ["2027-seimo"], self.BASELINE)
        self.assertEqual(len(findings), 1)
        self.assertIn("scraper/elections.json is not at hand", findings[0])

    def test_closest_peer_prefers_the_nearest_date_and_the_earlier_on_a_tie(self) -> None:
        registry = {e["id"]: e for e in self.REGISTRY}
        self.assertEqual(script.closest_peer("2027-seimo", registry, ["2020-seimo", "2024-seimo"]), "2024-seimo")
        registry["2022-seimo"] = {"id": "2022-seimo", "date": "2022-10-13", "kind": "seimo"}
        registry["2026-seimo"] = {"id": "2026-seimo", "date": "2026-10-13", "kind": "seimo"}
        self.assertEqual(script.closest_peer("2024-seimo", registry, ["2022-seimo", "2026-seimo"]), "2022-seimo")
        self.assertIsNone(script.closest_peer("2027-seimo", registry, ["2023-kovo-5-savivaldybiu-tarybu-ir-meru"]))


class UpdateBaselineTests(unittest.TestCase):
    """`--update-baseline` is additive and loud (issue #135): it used to
    rewrite every row and exit 0 over a real 74-point drop."""

    PEERS = [script.Cell("gautos-pajamos", f"peer-{i}", 1000, 1000, 1000) for i in range(3)]

    def _run(self, cells, previous, *, force=False, election_findings=()):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.tsv"
            if previous:
                script.write_baseline(path, [], previous)
            before = path.read_text(encoding="utf-8") if path.exists() else None
            err = io.StringIO()
            code = script.update_baseline(
                path, cells, previous, script.check(cells, previous, 5.0), list(election_findings), force=force, out=err
            )
            after = path.read_text(encoding="utf-8") if path.exists() else None
            rows = script.read_baseline(path) if path.exists() else {}
        return code, before, after, rows, err.getvalue()

    def test_a_drop_on_an_existing_row_is_refused_and_nothing_is_written(self) -> None:
        previous = {("gautos-pajamos", "2016-seimo"): script.Baseline(97.8, "ok", "")}
        cells = self.PEERS + [script.Cell("gautos-pajamos", "2016-seimo", 1000, 1000, 238)]
        code, before, after, _, err = self._run(cells, previous)
        self.assertEqual(code, 1)
        self.assertEqual(before, after, "the refusal must leave the file as it was")
        self.assertIn("refused", err)
        self.assertIn("a drop of 74.0 points", err)

    def test_force_writes_over_the_drop_and_says_so(self) -> None:
        previous = {("gautos-pajamos", "2016-seimo"): script.Baseline(97.8, "ok", "")}
        cells = self.PEERS + [script.Cell("gautos-pajamos", "2016-seimo", 1000, 1000, 238)]
        code, _, _, rows, _ = self._run(cells, previous, force=True)
        self.assertEqual(rows[("gautos-pajamos", "2016-seimo")].pct, 23.8)
        # 23.8 against peers at 100 is below its peers, and unexplained.
        self.assertEqual(rows[("gautos-pajamos", "2016-seimo")].status, script.UNEXPLAINED)
        self.assertEqual(code, 1)

    def test_a_new_elections_rows_are_added_and_its_unexplained_cells_exit_one(self) -> None:
        previous = {(c.concept, c.election): script.Baseline(100.0, "ok", "") for c in self.PEERS}
        cells = self.PEERS + [
            script.Cell("gautos-pajamos", "2027-seimo", 1740, 1740, 40),
            script.Cell("gimimo-data", "2027-seimo", 1740, 1740, 0),
        ]
        code, _, _, rows, err = self._run(cells, previous)
        self.assertEqual(code, 1)
        self.assertEqual(rows[("gautos-pajamos", "2027-seimo")], script.Baseline(2.3, script.UNEXPLAINED, ""))
        self.assertEqual(rows[("gimimo-data", "2027-seimo")], script.Baseline(0.0, script.UNEXPLAINED, ""))
        self.assertIn("2 cell(s) written unexplained", err)
        self.assertIn("2.3% filled (40 of 1740)", err)
        self.assertIn("0 of 1740 records fill it", err)

    def test_a_clean_update_reports_what_it_did(self) -> None:
        previous = {(c.concept, c.election): script.Baseline(99.0, "ok", "") for c in self.PEERS}
        cells = self.PEERS + [script.Cell("gautos-pajamos", "2027-seimo", 1740, 1740, 1735)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.tsv"
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = script.update_baseline(path, cells, previous, [], force=False, out=io.StringIO())
        self.assertEqual(code, 0)
        self.assertIn("1 row(s) added, 3 changed, 0 down more than 5 points", out.getvalue())

    def test_an_election_level_finding_blocks_the_update(self) -> None:
        previous = {(c.concept, c.election): script.Baseline(100.0, "ok", "") for c in self.PEERS}
        cells = self.PEERS + [script.Cell("gautos-pajamos", "2027-seimo", 1740, 1740, 1740)]
        gap = "gimimo-data\t2027-seimo\tthe closest mapped seimo election, peer-0, maps this concept and 2027-seimo does not"
        code, _, _, rows, err = self._run(cells, previous, election_findings=[gap])
        self.assertEqual(code, 1)
        self.assertNotIn(("gautos-pajamos", "2027-seimo"), rows)
        self.assertIn("maps this concept", err)


class GateEndToEndTests(unittest.TestCase):
    """The script on a synthetic repo root: a mapped 2024 election and a new
    2027 one with the two regressions issue #135 injected -- gimimo-data
    nulled on 1,600 of 1,740 and gautos-pajamos on 1,700 -- plus a concept
    the 2024 peer maps and 2027 does not. The plain run has to fail on all
    three, the update has to refuse and then list the cells, and only a
    classified baseline passes."""

    CONCEPT_MAP = {
        "concepts": {
            "gimimo-data": {"paths": {"2024-seimo": "biografija.gimimo-data", "2027-seimo": "biografija.gimimo-data"}},
            "gautos-pajamos": {"paths": {"2024-seimo": "turto-ir-pajamu-deklaracijos.gautos-pajamos", "2027-seimo": "turto-ir-pajamu-deklaracijos.gautos-pajamos"}},
            "iskele": {"paths": {"2024-seimo": "profilis.kita.iskele.reiksme"}},
        }
    }
    REGISTRY = {"elections": [
        {"id": "2024-seimo", "date": "2024-10-13", "kind": "seimo"},
        {"id": "2027-seimo", "date": "2027-10-10", "kind": "seimo"},
    ]}

    @staticmethod
    def _record(birth, income, nominator="LSDP"):
        return {
            "normalized": {
                "biografija": {"gimimo-data": birth},
                "turto-ir-pajamu-deklaracijos": {"gautos-pajamos": income},
                "profilis": {"kita": {"iskele": {"reiksme": nominator}}},
            }
        }

    def _repo(self, root: Path, size_new: int = 174) -> None:
        (root / "docs").mkdir()
        (root / "scraper").mkdir()
        (root / "docs" / "concept-map.json").write_text(json.dumps(self.CONCEPT_MAP), encoding="utf-8")
        (root / "scraper" / "elections.json").write_text(json.dumps(self.REGISTRY), encoding="utf-8")
        _synthetic_corpus(root / "data", "2024-seimo", [self._record("1970-01-01", 1000.0)] * 50)
        # 2027: birth date kept on 14 of 174 (8.0 %), income on 4 (2.3 %) --
        # the two regressions issue #135 injected, at a tenth of the scale.
        records = [self._record("1970-01-01" if i < 14 else None, 1000.0 if i < 4 else None) for i in range(size_new)]
        _synthetic_corpus(root / "data", "2027-seimo", records)
        (root / "docs" / "coverage-baseline.tsv").write_text(
            "concept\telection\tpct\tstatus\tnote\n"
            "gautos-pajamos\t2024-seimo\t100.0\tok\t\n"
            "gimimo-data\t2024-seimo\t100.0\tok\t\n"
            "iskele\t2024-seimo\t100.0\tok\t\n",
            encoding="utf-8",
        )

    def _run(self, root: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "field_coverage.py"), "--repo-root", str(root), *args],
            capture_output=True, text=True, timeout=120,
        )

    def test_the_new_elections_regressions_and_gap_fail_the_gate_and_the_update_listens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            plain = self._run(root)
            self.assertEqual(plain.returncode, 1, plain.stderr)
            self.assertIn("gimimo-data\t2027-seimo\t8.0% filled", plain.stderr)
            self.assertIn("gautos-pajamos\t2027-seimo\t2.3% filled", plain.stderr)
            self.assertIn("iskele\t2027-seimo\tthe closest mapped seimo election, 2024-seimo", plain.stderr)

            # The update refuses while the peer gap stands, and writes nothing.
            baseline_path = root / "docs" / "coverage-baseline.tsv"
            before = baseline_path.read_text(encoding="utf-8")
            update = self._run(root, "--update-baseline")
            self.assertEqual(update.returncode, 1)
            self.assertIn("refused", update.stderr)
            self.assertEqual(baseline_path.read_text(encoding="utf-8"), before)

            # Record why iskele is not mapped; now the update adds the rows and
            # lists the two low cells it wrote unexplained.
            with baseline_path.open("a", encoding="utf-8") as handle:
                handle.write("iskele\t2027-seimo\t0.0\tnot-mapped\tthe 2027 card names no nominator\n")
            update = self._run(root, "--update-baseline")
            self.assertEqual(update.returncode, 1, update.stderr)
            self.assertIn("2 row(s) added", update.stdout)
            self.assertIn("2 cell(s) written unexplained", update.stderr)
            rows = script.read_baseline(baseline_path)
            self.assertEqual(rows[("gimimo-data", "2027-seimo")].status, script.UNEXPLAINED)
            self.assertEqual(rows[("iskele", "2027-seimo")].status, script.NOT_MAPPED, "the opt-out survives the rewrite")

            # The plain run still fails: unexplained is not a classification.
            self.assertEqual(self._run(root).returncode, 1)

            # A human classifies both; the gate passes and the update is clean.
            text = baseline_path.read_text(encoding="utf-8")
            text = text.replace("gimimo-data\t2027-seimo\t8.0\tunexplained\t", "gimimo-data\t2027-seimo\t8.0\tpartly-answered\tthe 2027 card makes the date optional")
            text = text.replace("gautos-pajamos\t2027-seimo\t2.3\tunexplained\t", "gautos-pajamos\t2027-seimo\t2.3\tpartly-published\tVRK publishes the 2027 declarations for 4 candidates")
            baseline_path.write_text(text, encoding="utf-8")
            final = self._run(root)
            self.assertEqual(final.returncode, 0, final.stderr)
            self.assertIn("No findings.", final.stdout)
            clean = self._run(root, "--update-baseline")
            self.assertEqual(clean.returncode, 0, clean.stderr)
            self.assertIn("0 row(s) added, 0 changed, 0 down", clean.stdout)

    def test_an_unmapped_election_fails_the_gate_until_opted_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            _synthetic_corpus(root / "data", "2028-prezidento", [self._record("1970-01-01", 1.0)] * 5)
            plain = self._run(root, "2024-seimo")
            self.assertEqual(plain.returncode, 1)
            self.assertIn("*\t2028-prezidento\t5 records under data/ and no concept maps this election", plain.stderr)
            with (root / "docs" / "coverage-baseline.tsv").open("a", encoding="utf-8") as handle:
                handle.write("*\t2028-prezidento\t0.0\tnot-mapped\tthe 2028 pages carry no questionnaire\n")
            self.assertNotIn("2028-prezidento", self._run(root, "2024-seimo").stderr)


class BaselineFileTests(unittest.TestCase):
    def test_a_low_classification_survives_while_the_cell_is_below_its_peers(self) -> None:
        cells = [script.Cell("gimimo-vieta", f"peer-{i}", 100, 100, 96) for i in range(3)]
        cells.append(script.Cell("gimimo-vieta", "2000-seimo", 1271, 1271, 138))
        previous = {("gimimo-vieta", "2000-seimo"): script.Baseline(10.9, "partly-published", "no card field")}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.tsv"
            script.write_baseline(path, cells, previous)
            rows = script.read_baseline(path)
        self.assertEqual(rows[("gimimo-vieta", "2000-seimo")], previous[("gimimo-vieta", "2000-seimo")])
        self.assertEqual(rows[("gimimo-vieta", "peer-0")], script.Baseline(96.0, script.OK, ""))

    def test_a_low_classification_is_dropped_once_the_cell_is_back_with_its_peers(self) -> None:
        cells = [script.Cell("gimimo-vieta", f"peer-{i}", 100, 100, 96) for i in range(3)]
        cells.append(script.Cell("gimimo-vieta", "2000-seimo", 1271, 1271, 1200))
        previous = {("gimimo-vieta", "2000-seimo"): script.Baseline(10.9, "partly-published", "no card field")}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.tsv"
            script.write_baseline(path, cells, previous)
            self.assertEqual(script.read_baseline(path)[("gimimo-vieta", "2000-seimo")], script.Baseline(94.4, script.OK, ""))

    def test_not_mapped_rows_survive_a_rewrite_until_the_cell_is_measured(self) -> None:
        previous = {
            ("*", "2028-prezidento"): script.Baseline(0.0, script.NOT_MAPPED, "no questionnaire"),
            ("iskele", "2027-seimo"): script.Baseline(0.0, script.NOT_MAPPED, "no nominator on the card"),
            ("iskele", "2024-seimo"): script.Baseline(0.0, script.NOT_MAPPED, "stale: it is mapped now"),
        }
        cells = [script.Cell("iskele", "2024-seimo", 10, 10, 10), script.Cell("gimimo-data", "2027-seimo", 10, 10, 10)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.tsv"
            script.write_baseline(path, cells, previous)
            rows = script.read_baseline(path)
        self.assertEqual(rows[("*", "2028-prezidento")], previous[("*", "2028-prezidento")])
        self.assertEqual(rows[("iskele", "2027-seimo")], previous[("iskele", "2027-seimo")])
        self.assertEqual(rows[("iskele", "2024-seimo")], script.Baseline(100.0, script.OK, ""))

    def test_a_star_row_is_dropped_once_the_election_is_measured(self) -> None:
        previous = {("*", "2027-seimo"): script.Baseline(0.0, script.NOT_MAPPED, "was unmapped")}
        cells = [script.Cell("gimimo-data", "2027-seimo", 10, 10, 10)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.tsv"
            script.write_baseline(path, cells, previous)
            self.assertNotIn(("*", "2027-seimo"), script.read_baseline(path))

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
        # A `not-mapped` row is the one kind of row that names an unmapped
        # cell on purpose (issue #135), and it says why.
        measured = {key for key, row in self.baseline.items() if row.status != script.NOT_MAPPED}
        self.assertEqual(sorted(measured - mapped), [])
        for key, row in self.baseline.items():
            if row.status == script.NOT_MAPPED:
                with self.subTest(key):
                    self.assertNotIn(key, mapped)
                    self.assertTrue(row.note.strip())

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

    def test_a_filled_cell_carries_no_excuse_it_does_not_need(self) -> None:
        # `ok`, or -- far below the concept's other elections -- one of the
        # two low-fill words with a note (issue #135). Nothing else.
        for key, row in self.baseline.items():
            if not row.pct:
                continue
            with self.subTest(key):
                self.assertIn(row.status, {script.OK, *script.LOW_STATUSES})
                if row.status in script.LOW_STATUSES:
                    self.assertTrue(row.note.strip(), "a low-fill classification needs a reason")

    def _measured_cells(self) -> list:
        # The checked-in rates as cells (records=1000 so pct round-trips),
        # which is enough to re-derive every peer median from the file alone.
        return [
            script.Cell(concept, election, 1000, 1000, round(row.pct * 10))
            for (concept, election), row in self.baseline.items()
            if row.status != script.NOT_MAPPED
        ]

    def test_every_below_peers_cell_is_classified_and_no_classification_is_stale(self) -> None:
        # The file's own rates say which cells the below-peers rule flags at
        # the default threshold: each of those carries a `partly-*` word, and
        # no cell carries one it no longer needs.
        cells = self._measured_cells()
        medians = script.peer_medians(cells)
        for cell in cells:
            row = self.baseline[(cell.concept, cell.election)]
            low = script.below_peers(cell, medians[(cell.concept, cell.election)])
            with self.subTest((cell.concept, cell.election)):
                if low:
                    self.assertIn(row.status, script.LOW_STATUSES, "below its peers and unclassified")
                elif row.pct:
                    self.assertEqual(row.status, script.OK, "a classification the cell no longer needs")

    def test_nothing_is_unexplained(self) -> None:
        self.assertEqual(
            sorted(key for key, row in self.baseline.items() if row.status == script.UNEXPLAINED), []
        )


class UnmappedFillTests(unittest.TestCase):
    """The third rule (issue #131): a concept's own path form filling an
    election the map does not give the concept for. The dashboard renders
    such a cell as "this election never published this field"."""

    PATHS = {
        "savivaldybe": {"a": "kandidatavimas.savivaldybe", "b": "profilis.kita.savivaldybe.reiksme"},
        "pomegiai": {"a": "anketa.pomegiai"},
    }

    def _corpus(self, root: Path, election: str, records: list[dict]) -> None:
        directory = root / election
        directory.mkdir(parents=True)
        for index, record in enumerate(records):
            (directory / f"c{index:04d}-{election}.json").write_text(json.dumps(record), encoding="utf-8")

    def test_a_filled_form_on_an_unmapped_election_is_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # `c` is not mapped for savivaldybe, yet every record carries the
            # 2019 shape of it -- the 27,523-candidacy cell of issue #131.
            self._corpus(root, "c", [{"normalized": {}, "kandidatavimas": {"savivaldybe": {"name": "Kauno miesto"}}}] * 5)
            findings = script.unmapped_fills(root, self.PATHS, ["c"])
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].startswith("savivaldybe\tc\tkandidatavimas.savivaldybe fills 5 of 5"))

    def test_a_stray_record_below_the_floor_is_not(self) -> None:
        # anketa.pomegiai on 1 of 10,138 records of 2002-gruodzio-22 is a
        # form that does not ask the question, not a missing mapping.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [{"normalized": {"anketa": {"pomegiai": None}}}] * 199 + [{"normalized": {"anketa": {"pomegiai": "šachmatai"}}}]
            self._corpus(root, "c", records)
            self.assertEqual(script.unmapped_fills(root, self.PATHS, ["c"]), [])
            self.assertEqual(len(script.unmapped_fills(root, self.PATHS, ["c"], floor_pct=0.1)), 1)

    def test_a_mapped_election_is_not_checked_against_itself(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._corpus(root, "a", [{"normalized": {}, "kandidatavimas": {"savivaldybe": "Trakų rajono"}}] * 3)
            self.assertEqual(script.unmapped_fills(root, self.PATHS, ["a"]), [])

    def test_the_sample_caps_the_records_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._corpus(root, "c", [{"normalized": {}, "kandidatavimas": {"savivaldybe": "X"}}] * 10)
            findings = script.unmapped_fills(root, self.PATHS, ["c"], sample=4)
        self.assertIn("fills 4 of 4 records", findings[0])

    def test_the_corpus_has_no_unmapped_fill(self) -> None:
        # The real map against a sample of every election under data/: the
        # 30 cells of issue #131 are mapped, and the two stray-record cells
        # the map excludes on purpose (anketa.pomegiai on 2002-gruodzio-22,
        # anketa.kita-apie-save on 2000-kovo-19) sit under the floor.
        local_data.require_corpus()
        paths = script.concept_paths(CONCEPT_MAP)
        election_ids = sorted(child.name for child in DATA_ROOT.iterdir() if child.is_dir() and any(child.glob("*.json")))
        self.assertEqual(script.unmapped_fills(DATA_ROOT, paths, election_ids, sample=300), [])


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
