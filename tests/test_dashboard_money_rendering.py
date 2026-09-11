"""The compare tab must render declared money the way the assets tab does.

Both panes read the same `turto-ir-pajamu-deklaracijos` fields, but only the
assets pane converted: the compare table printed the stored number raw, so a
2008 income (declared in litas) sat beside a 2024 one 3.4528x too large and
carrying no unit. 36,362 of the corpus's 76,776 records declare in litas, so
this was just under half the table. The conversion itself is correct and
wanted -- these tests pin that *both* renderers do it. The figures carry no
"Lt→€" marker: the conversion is obvious from the currency and the labels were
removed. See GitHub issue #63.

The money helpers are lifted out of dashboard/index.html and executed with
node, so this tests the shipped code rather than a transcription of it. The
page has no build step and the repo no JS toolchain; where node is missing the
behavioural tests skip and the structural ones still run.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = REPO_ROOT / "dashboard" / "index.html"
SOURCE = DASHBOARD_PATH.read_text(encoding="utf-8")
NODE = shutil.which("node")

# The money concepts of the comparison table, and the renderer each row has
# to carry. The rows name concepts from docs/concept-map.json now, not paths
# (issue #87). The income row goes through `incomeCell`, which resolves the
# `deklaruotos-pajamos` concept before converting -- see the module docstring
# of scraper/shared/deklaracijos.py.
MONEY_CONCEPTS = {
    "privalomas-registruoti-turtas": "moneyCell",
    "pinigines-lesos": "moneyCell",
    "gautos-pajamos": "incomeCell",
    "turtas-ir-pinigines-lesos": "moneyCell",
    "turtas-ir-pinigines-lesos-metu-pradzioje": "moneyCell",
    "kalendoriniais-metais-isigytas-turtas": "moneyCell",
    "gautos-pajamos-darbo-santykiu": "moneyCell",
}


def _extract(name: str) -> str:
    """Pull one top-level `function name(...)` or `const name = ...;` out."""
    fn = re.search(rf"^function {re.escape(name)}\(.*?^}}", SOURCE, re.S | re.M)
    if fn:
        return fn.group(0)
    const = re.search(rf"^const {re.escape(name)} = .*?;$", SOURCE, re.S | re.M)
    if const:
        return const.group(0)
    raise AssertionError(f"{name} not found in {DASHBOARD_PATH.name}")


def run_in_node(expression: str) -> object:
    helpers = "\n".join(
        _extract(n)
        for n in (
            "LITAS_PER_EURO",
            "INCOME_PATH",
            "EMPLOYMENT_INCOME_PATH",
            "resolvePath",
            "parseMoney",
            "declaredInLitas",
            "declaredIncome",
            "fmtEUR",
            "moneyCell",
            "incomeCell",
        )
    )
    script = f"{helpers}\nconsole.log(JSON.stringify({expression}));"
    out = subprocess.run(
        [NODE, "--input-type=module", "-"], input=script,
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        raise AssertionError(out.stderr.strip())
    return json.loads(out.stdout)


def litas(value):
    return {"normalized": {"turto-ir-pajamu-deklaracijos": {"valiuta": "Lt", "x": value}}}


def euro(value):
    return {"normalized": {"turto-ir-pajamu-deklaracijos": {"x": value}}}


class ConceptRowWiringTests(unittest.TestCase):
    """Structural: the money rows must carry the formatter."""

    def test_each_money_row_uses_the_money_formatter(self):
        for concept, renderer in MONEY_CONCEPTS.items():
            with self.subTest(concept):
                row = re.search(rf'\{{ concept: "{re.escape(concept)}", format: (\w+) \}}', SOURCE)
                self.assertIsNotNone(row, f"{concept} missing from CONCEPT_ROWS")
                self.assertEqual(
                    row.group(1),
                    renderer,
                    f"{concept} would render raw, unconverted and unlabelled",
                )

    def test_the_compare_table_applies_the_formatter(self):
        self.assertIn("const c = format ? format(v, r, e) : compactValue(v);", SOURCE)

    def test_no_conversion_marker_is_shown_anywhere(self):
        # The figures are converted; saying so on every column and in three
        # footnotes was noise, so the labels went. The conversion did not.
        self.assertNotIn("Lt→€", SOURCE)

    def test_the_conversion_itself_is_still_applied_in_both_renderers(self):
        for renderer in ("moneyCell", "incomeCell", "moneyEUR"):
            with self.subTest(renderer):
                body = re.search(rf"^function {renderer}\(.*?^}}", SOURCE, re.S | re.M).group(0)
                self.assertIn("declaredInLitas", body)
                self.assertIn("LITAS_PER_EURO", body)


# fmtEUR formats with toLocaleString("lt-LT"), whose thousands separator is a
# non-breaking space, not a plain one. Spelling it out keeps these literals
# honest about what the page actually renders.
NB = "\u00a0"


@unittest.skipIf(NODE is None, "node not installed — behavioural checks skipped")
class MoneyCellTests(unittest.TestCase):
    """Behavioural: the shipped moneyCell, executed."""

    def test_litas_are_converted_at_the_changeover_rate(self):
        # 34 821.19 Lt is Babravičius's 2008 declared income; the assets pane
        # has always shown it as 10 085 €, the compare tab used to print
        # "34821.19".
        self.assertEqual(run_in_node("moneyCell(34821.19, r)".replace("r", json.dumps(litas(0)))), f"10{NB}085 €")

    def test_euro_figures_pass_through_unconverted(self):
        self.assertEqual(run_in_node(f"moneyCell(9680.84, {json.dumps(euro(0))})"), f"9{NB}681 €")

    def test_a_declared_zero_is_rendered_not_dropped(self):
        # 0 is a real declaration ("declared nothing"), distinct from "—".
        self.assertEqual(run_in_node(f"moneyCell(0, {json.dumps(euro(0))})"), "0 €")

    def test_undeclared_values_stay_null_so_the_cell_shows_a_dash(self):
        for missing in ("null", '""', '"n/a"'):
            with self.subTest(missing):
                self.assertIsNone(run_in_node(f"moneyCell({missing}, {json.dumps(euro(0))})"))

    def test_a_litas_figure_renders_smaller_than_the_same_number_in_euro(self):
        pair = run_in_node(
            f"[moneyCell(345280, {json.dumps(litas(0))}), moneyCell(345280, {json.dumps(euro(0))})]"
        )
        self.assertEqual(pair, [f"100{NB}000 €", f"345{NB}280 €"])

    def test_string_figures_with_spaces_and_commas_parse(self):
        self.assertEqual(run_in_node(f'moneyCell("34 528,00", {json.dumps(euro(0))})'), f"34{NB}528 €")


if __name__ == "__main__":
    unittest.main()


class DeclaredIncomeTests(unittest.TestCase):
    """The compare table's income row resolves `deklaruotos-pajamos`.

    The 1990s form prints rows 1 and 20 of its income section, and row 20 is
    not always trustworthy: it renders 0 against a non-zero row 1, so the
    parser refuses it and `gautos-pajamos` is null on 4,463 of the 1997
    municipal election's 6,276 records. The row the page does publish is
    employment income, so the cell shows it and says which it is (issue #98).
    """

    @unittest.skipUnless(NODE, "node not installed")
    def test_a_declared_total_renders_as_before(self):
        record = {
            "normalized": {
                "turto-ir-pajamu-deklaracijos": {
                    "gautos-pajamos": 5000,
                    "gautos-pajamos-darbo-santykiu": 4000,
                }
            }
        }
        self.assertEqual(run_in_node(f"incomeCell(null, {json.dumps(record)})"), "5\u00a0000 €")

    @unittest.skipUnless(NODE, "node not installed")
    def test_a_refused_total_falls_back_to_the_employment_row_and_says_so(self):
        record = {
            "normalized": {
                "turto-ir-pajamu-deklaracijos": {
                    "gautos-pajamos": None,
                    "gautos-pajamos-darbo-santykiu": 3452.8,
                    "valiuta": "Lt",
                }
            }
        }
        self.assertEqual(
            run_in_node(f"incomeCell(null, {json.dumps(record)})"),
            "1\u00a0000 € (darbo santykiai)",
        )

    @unittest.skipUnless(NODE, "node not installed")
    def test_neither_figure_still_reads_as_nothing(self):
        record = {"normalized": {"turto-ir-pajamu-deklaracijos": {"gautos-pajamos": None}}}
        self.assertIsNone(run_in_node(f"incomeCell(null, {json.dumps(record)})"))


# The one shared money-string rule (issue #87): the page's parseMoney and the
# builder's parse_money_text must agree on every one of these, because they
# used to diverge exactly where it is dangerous — parseFloat's prefix parse
# read "1.234.567,89" as 1.234 while Python raised and stored None. The rule:
# strip € and whitespace (NBSP included), allow one decimal separator (comma
# or dot), refuse everything else. Dormant today — no money field in the
# corpus is a string — which is why refusal is safe.
PARSE_MONEY_FIXTURES = [
    ("34 528,00", 34528.0),
    ("1 234 567,89", 1234567.89),
    ("12 345,67", 12345.67),
    ("9680.84", 9680.84),
    ("0", 0.0),
    ("-12,5", -12.5),
    ("€ 100", 100.0),
    ("1.234.567,89", None),
    ("1,234.56", None),
    ("12abc", None),
    ("", None),
    ("Lt", None),
]


class SharedMoneyRuleTests(unittest.TestCase):
    def _python_side(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_person_index", REPO_ROOT / "scripts" / "build_person_index.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.parse_money_text

    def test_the_builder_follows_the_rule(self):
        parse_money_text = self._python_side()
        for text, expected in PARSE_MONEY_FIXTURES:
            with self.subTest(text):
                self.assertEqual(parse_money_text(text), expected)

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_page_follows_the_same_rule(self):
        texts = [text for text, _ in PARSE_MONEY_FIXTURES]
        got = run_in_node(f"{json.dumps(texts)}.map(parseMoney)")
        self.assertEqual(got, [expected for _, expected in PARSE_MONEY_FIXTURES])
