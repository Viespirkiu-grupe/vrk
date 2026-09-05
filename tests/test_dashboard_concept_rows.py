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


# The value a path form's leaf holds in the corpus, by the form's tail. What
# the cell is handed depends on where the map's path stops -- at an object,
# at the entry list inside it, or at a string -- and each formatter has to
# take every shape the map produces for its concept (issue #131: educationCell
# took the object and was handed the array on 43 elections).
EDUCATION_ENTRY = {
    "issilavinimas": "Aukštasis universitetinis",
    "mokymo-istaigos-pavadinimas": "Vilniaus universitetas",
    "specialybe": "teisė",
    "baigimo-metai": "1996",
}


def leaf_for(concept: str, form: str):
    if form == "anketa.issilavinimas":
        return {"aprasas": None, "irasai": [EDUCATION_ENTRY]}
    if form.endswith(".issilavinimas.irasai"):
        return [EDUCATION_ENTRY]
    if form == "biografija.darbo-patirtis":
        return {"irasai": [{"darboviete": "UAB Įmonė", "pareigos": "direktorius", "darbo-pradzia": "2010", "darbo-pabaiga": "2014"}]}
    if form.endswith("partyList"):
        return {"id": "28392", "number": 6, "name": "Tėvynės sąjunga"}
    if form.endswith(".irasai") or form.endswith("uzsienio-kalbos"):
        return ["Lietuvos socialdemokratų partija"]
    return "Reikšmė"


def plant(form: str, leaf):
    """A record carrying `leaf` at `form` -- under `normalized`, or at the
    record root for the hoisted sections, exactly where the parsers put it."""
    segments = form.split(".")
    record: dict = {"normalized": {}}
    node = record if segments[0] in field_coverage.RECORD_ROOT_SECTIONS else record["normalized"]
    for segment in segments[:-1]:
        node = node.setdefault(segment, {})
    node[segments[-1]] = leaf
    return record


class EveryPathShapeRendersTests(unittest.TestCase):
    """For every row the comparison table shows and every path form its
    concept is mapped through, a record carrying that form renders a cell --
    through the page's own resolver, formatter and the real concept map.
    The gate issue #131 asked for: the formatter is fed what the map hands
    it, not a hand-written object."""

    #: Rows whose formatter reads the whole declaration through helpers the
    #: lift-and-run harness stubs to null; their resolution is covered by
    #: field_coverage and the money-rendering tests.
    STUBBED_FORMATS = {"moneyCell", "incomeCell"}

    def _rows(self):
        block = re.search(r"^const CONCEPT_ROWS = \[(.*?)^\];", SOURCE, re.S | re.M).group(1)
        rows = []
        for line in block.splitlines():
            concept = re.search(r'concept: "([a-z0-9-]+)"', line)
            if not concept or "derived: true" in line:
                continue
            fmt = re.search(r"format: (\w+)", line)
            rows.append((concept.group(1), fmt.group(1) if fmt else None))
        return rows

    def _render(self, cases):
        helpers = "\n".join(
            re.search(rf"^function {name}\(.*?^}}", SOURCE, re.S | re.M).group(0)
            for name in (
                "compactValue", "educationCell", "workHistoryCell", "nameCell", "convictionCell",
                "convictionLines", "deslug", "labelFor", "isFilledValue", "walkValue", "resolveConcept",
                "resolveRow", "rowLabel",
            )
        )
        consts = "\n".join(
            re.search(pattern, SOURCE, flags).group(0)
            for pattern, flags in (
                (r"^const AFFIRMATIVE_ANSWERS = .*;$", re.M),
                (r"^const isAffirmative = .*;$", re.M),
                (r"^const RELATED_DECLARATIONS = \{.*?^\};", re.S | re.M),
                (r"^const OFFENCE_KEYS = .*;$", re.M),
                (r"^const SECTION_LABELS = \{.*?^\};", re.S | re.M),
                (r"^const ROOT_SECTIONS = .*?;$", re.S | re.M),
                (r"^const CONCEPT_ROWS = \[.*?^\];", re.S | re.M),
            )
        )
        script = (
            f"const CONCEPTS = {json.dumps(CONCEPT_MAP['concepts'])};\n"
            "const CONCEPT_LABELS = {}; const SEGMENT_LABELS = {};\n"
            f"{consts}\n{helpers}\n"
            "function moneyCell() { return null; }\nfunction incomeCell() { return null; }\n"
            f"const cases = {json.dumps(cases, ensure_ascii=False)};\n"
            "const out = cases.map(({concept, election, record}) => {\n"
            "  const row = CONCEPT_ROWS.find(r => r.concept === concept);\n"
            "  const { mapped, value } = resolveRow(row, record, election);\n"
            "  const c = row.format ? row.format(value, record) : compactValue(value);\n"
            "  return { mapped, cell: c == null ? null : c };\n"
            "});\n"
            "console.log(JSON.stringify(out));"
        )
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    @unittest.skipUnless(NODE, "node not installed")
    def test_every_form_of_every_row_concept_renders_a_cell(self):
        cases = []
        for concept, fmt in self._rows():
            if fmt in self.STUBBED_FORMATS:
                continue
            paths = CONCEPT_MAP["concepts"][concept]["paths"]
            for form in field_coverage.path_forms({concept: paths})[concept]:
                election = next(
                    eid for eid, mapping in paths.items()
                    if form in ([mapping] if isinstance(mapping, str) else mapping)
                )
                cases.append({"concept": concept, "form": form, "election": election, "record": plant(form, leaf_for(concept, form))})
        self.assertGreaterEqual(len(cases), 20)
        rendered = self._render(cases)
        blank = [
            f"{case['concept']} via {case['form']} ({case['election']})"
            for case, result in zip(cases, rendered)
            if not result["mapped"] or result["cell"] is None
        ]
        self.assertEqual(blank, [], "a mapped path form the page renders as an em dash")


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
