"""The comparison rows resolve through docs/concept-map.json — provably.

Issue #87's test gap: the dashboard tests asserted that a path was *written*
in the page, never that it *resolves*, so the page's private FIELD_MAP
drifted from the data with a green suite (two era-split rows permanently
empty for half the corpus each). The page now names concepts instead of
paths, which moves the resolution question to three provable claims:

1. every concept the page's rows name exists in the concept map (and is
   mapped for at least one election, and measured in the coverage baseline
   with a non-zero fill somewhere) — so a typo'd or retired concept is a red
   test, not an empty row;
2. the page's JS resolver agrees with `field_coverage.concept_value` — the
   resolver the map is *verified* with — on the shapes a naive walker gets
   wrong: zero/False are answers, ""/[] are not, `kandidatavimas` falls back
   to the record root, list mappings try alternatives in order, and a list
   met mid-path fans out over its entries;
3. the era-fallback chain actually bridges: the one row that covers
   einamos-pareigos (2020 on) and pagrindine-darboviete (before) resolves a
   record from each era, and the mapped/unmapped distinction the table
   renders ("the form never asked" vs "asked, not answered") is real.

`scripts/field_coverage.py` gates the map itself against the full corpus, so
together the chain page → concept map → corpus is closed.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = REPO_ROOT / "dashboard" / "index.html"
CONCEPT_MAP_PATH = REPO_ROOT / "docs" / "concept-map.json"
COVERAGE_BASELINE_PATH = REPO_ROOT / "docs" / "coverage-baseline.tsv"
SOURCE = DASHBOARD_PATH.read_text(encoding="utf-8")
CONCEPT_MAP = json.loads(CONCEPT_MAP_PATH.read_text(encoding="utf-8"))
NODE = shutil.which("node")

_spec = importlib.util.spec_from_file_location(
    "field_coverage", REPO_ROOT / "scripts" / "field_coverage.py"
)
field_coverage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(field_coverage)


def concept_rows() -> list[dict]:
    """The page's CONCEPT_ROWS, read out of the shipped source."""
    block = re.search(r"^const CONCEPT_ROWS = \[(.*?)^\];", SOURCE, re.S | re.M).group(1)
    rows = []
    for line in block.splitlines():
        concept = re.search(r'concept: "([a-z0-9-]+)"', line)
        if not concept:
            continue
        rows.append(
            {
                "concept": concept.group(1),
                "fallbacks": re.findall(r'"([a-z0-9-]+)"', line.partition("fallbacks: [")[2].partition("]")[0]),
                "derived": "derived: true" in line,
            }
        )
    return rows


class RowsNameRealConceptsTests(unittest.TestCase):
    def test_the_page_has_rows_at_all(self):
        self.assertGreaterEqual(len(concept_rows()), 10)

    def test_every_row_concept_is_in_the_map(self):
        concepts = CONCEPT_MAP["concepts"]
        derived = CONCEPT_MAP.get("derived", {})
        for row in concept_rows():
            with self.subTest(row["concept"]):
                if row["derived"]:
                    self.assertIn(row["concept"], derived)
                else:
                    self.assertIn(row["concept"], concepts)
                    self.assertTrue(concepts[row["concept"]]["paths"], "mapped for no election")
            for fallback in row["fallbacks"]:
                with self.subTest(f"{row['concept']} -> {fallback}"):
                    self.assertIn(fallback, concepts)

    def test_every_row_concept_has_measured_fill_in_the_baseline(self):
        # The baseline is field_coverage's checked-in measurement of the map
        # against the full corpus; a concept the page shows but no record
        # fills anywhere would render a row of em-dashes forever.
        filled: dict[str, float] = {}
        for line in COVERAGE_BASELINE_PATH.read_text(encoding="utf-8").splitlines()[1:]:
            concept, _election, pct, *_ = line.split("\t")
            filled[concept] = max(filled.get(concept, 0.0), float(pct))
        for row in concept_rows():
            if row["derived"]:
                continue  # derived concepts resolve in code, not via a path
            for concept in [row["concept"], *row["fallbacks"]]:
                with self.subTest(concept):
                    self.assertGreater(filled.get(concept, 0.0), 0.0)

    def test_no_dotted_path_survives_outside_the_shared_money_constants(self):
        # The whole point: the page must not grow a private path list again.
        # MONEY_SERIES and the two income paths mirror MONEY_FIELDS in
        # scripts/build_person_index.py (order-coupled with people.json's "m")
        # and are the one sanctioned exception; resolvePath call sites for
        # photos read rawData, which the concept map does not cover.
        block = re.search(r"^const CONCEPT_ROWS = \[.*?^\];", SOURCE, re.S | re.M).group(0)
        self.assertNotIn('"anketa.', block)
        self.assertNotIn('"biografija.', block)
        self.assertNotIn('"turto-ir-pajamu-deklaracijos.', block)


# ---------------------------------------------------------------------------
# Resolver agreement: the page's walkValue/resolveConcept against
# field_coverage.concept_value on the shapes that earn false zeros.
# ---------------------------------------------------------------------------

RESOLVER_FIXTURES = [
    # (record, mapping) — mapping is a concept's per-election path value.
    ({"normalized": {"anketa": {"x": 0}}}, "anketa.x"),
    ({"normalized": {"anketa": {"x": False}}}, "anketa.x"),
    ({"normalized": {"anketa": {"x": ""}}}, "anketa.x"),
    ({"normalized": {"anketa": {"x": "  "}}}, "anketa.x"),
    ({"normalized": {"anketa": {"x": []}}}, "anketa.x"),
    ({"normalized": {"anketa": {"x": {}}}}, "anketa.x"),
    ({"normalized": {"anketa": {"x": ["a", "b"]}}}, "anketa.x"),
    # The record-root fallback: pre-2016 candidacies are hoisted to the root…
    ({"normalized": {}, "kandidatavimas": {"savivaldybe": "Trakų"}}, "kandidatavimas.savivaldybe"),
    # …and the normalized copy wins where both exist (the 1997 archive pair).
    (
        {
            "normalized": {"kandidatavimas": {"savivaldybe": "Norm"}},
            "kandidatavimas": {"savivaldybe": "Root"},
        },
        "kandidatavimas.savivaldybe",
    ),
    # A list mapping tries alternatives in order, first filled one wins.
    ({"normalized": {"anketa": {"a": None, "b": "B"}}}, ["anketa.a", "anketa.b"]),
    ({"normalized": {"anketa": {"a": "A", "b": "B"}}}, ["anketa.a", "anketa.b"]),
    # A list met mid-path fans out over its entries (the 1996-1999 archive
    # family's kandidatavimas is a list of candidacies).
    (
        {"normalized": {"kandidatavimas": [{"iskele": None}, {"iskele": "LSDP"}]}},
        "kandidatavimas.iskele",
    ),
    # Deep dict walking.
    ({"normalized": {"profilis": {"kita": {"iskele": {"reiksme": "TS-LKD"}}}}}, "profilis.kita.iskele.reiksme"),
    ({"normalized": {"profilis": {}}}, "profilis.kita.iskele.reiksme"),
]


class ResolverAgreementTests(unittest.TestCase):
    @unittest.skipUnless(NODE, "node not installed")
    def test_the_page_resolver_matches_field_coverage(self):
        python_side = [
            field_coverage.concept_value(record, mapping)
            for record, mapping in RESOLVER_FIXTURES
        ]
        helpers = "\n".join(
            re.search(rf"^function {name}\(.*?^}}", SOURCE, re.S | re.M).group(0)
            for name in ("isFilledValue", "walkValue", "resolveConcept")
        )
        root_sections = re.search(r"^const ROOT_SECTIONS = .*?;$", SOURCE, re.S | re.M).group(0)
        cases = [
            {"record": record, "mapping": mapping} for record, mapping in RESOLVER_FIXTURES
        ]
        script = (
            f"{root_sections}\n{helpers}\n"
            f"const cases = {json.dumps(cases)};\n"
            "const out = cases.map(({record, mapping}) => {\n"
            "  globalThis.CONCEPTS = { probe: { paths: { e: mapping } } };\n"
            "  return resolveConcept(record, 'e', 'probe').value;\n"
            "});\n"
            "console.log(JSON.stringify(out));"
        )
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        js_side = json.loads(out.stdout)
        # Through JSON both sides land on the same representations
        # (None ↔ null, False ↔ false), so equality is exact.
        self.assertEqual(js_side, json.loads(json.dumps(python_side)))


class EraFallbackTests(unittest.TestCase):
    """The one row bridging einamos-pareigos (2020 on) and
    pagrindine-darboviete (before): each era resolves through its own
    concept, and an election neither concept maps reads as unmapped."""

    def _resolve_row(self, record, election_id):
        helpers = "\n".join(
            re.search(rf"^function {name}\(.*?^}}", SOURCE, re.S | re.M).group(0)
            for name in ("isFilledValue", "walkValue", "resolveConcept", "resolveRow")
        )
        root_sections = re.search(r"^const ROOT_SECTIONS = .*?;$", SOURCE, re.S | re.M).group(0)
        script = (
            f"const CONCEPTS = {json.dumps(CONCEPT_MAP['concepts'])};\n"
            f"{root_sections}\n{helpers}\n"
            'const row = { concept: "einamos-pareigos", fallbacks: ["pagrindine-darboviete"] };\n'
            f"const record = {json.dumps(record)};\n"
            f"console.log(JSON.stringify(resolveRow(row, record, {json.dumps(election_id)})));"
        )
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_2020_era_answers_through_einamos_pareigos(self):
        record = {"normalized": {"anketa": {"einamos-pareigos": "UAB X direktorius"}}}
        self.assertEqual(
            self._resolve_row(record, "2024-seimo"),
            {"mapped": True, "value": "UAB X direktorius"},
        )

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_earlier_eras_answer_through_pagrindine_darboviete(self):
        record = {"normalized": {"anketa": {"pagrindine-darboviete": "AB Žeimena, inspektorė"}}}
        self.assertEqual(
            self._resolve_row(record, "2016-seimo"),
            {"mapped": True, "value": "AB Žeimena, inspektorė"},
        )

    @unittest.skipUnless(NODE, "node not installed")
    def test_an_election_that_never_asked_reads_as_unmapped(self):
        # 2002-prezidento maps neither workplace concept — its cell renders
        # as "the form never asked", not as an unanswered question.
        self.assertEqual(
            self._resolve_row({"normalized": {}}, "2002-prezidento"),
            {"mapped": False, "value": None},
        )

    @unittest.skipUnless(NODE, "node not installed")
    def test_an_asked_but_unanswered_question_reads_as_mapped_and_empty(self):
        self.assertEqual(
            self._resolve_row({"normalized": {}}, "2016-seimo"),
            {"mapped": True, "value": None},
        )


if __name__ == "__main__":
    unittest.main()
