"""The compare tab must render declared money the way the assets tab does.

Both panes read the same `turto-ir-pajamu-deklaracijos` fields, but only the
assets pane converted: the compare table printed the stored number raw, so a
2008 income (declared in litas) sat beside a 2024 one 3.4528x too large and
carrying no unit. 36,362 of the corpus's 76,776 records declare in litas, so
this was just under half the table. The conversion itself is correct and
wanted -- these tests pin that *both* renderers do it. See GitHub issue #63.

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

# The three declaration fields every module normalizes under the same keys.
MONEY_PATHS = (
    "turto-ir-pajamu-deklaracijos.privalomas-registruoti-turtas",
    "turto-ir-pajamu-deklaracijos.pinigines-lesos",
    "turto-ir-pajamu-deklaracijos.gautos-pajamos",
)


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
        for n in ("LITAS_PER_EURO", "parseMoney", "declaredInLitas", "fmtEUR", "moneyCell")
    )
    script = f"{helpers}\nconsole.log(JSON.stringify({expression}));"
    out = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        raise AssertionError(out.stderr.strip())
    return json.loads(out.stdout)


def litas(value):
    return {"normalized": {"turto-ir-pajamu-deklaracijos": {"valiuta": "Lt", "x": value}}}


def euro(value):
    return {"normalized": {"turto-ir-pajamu-deklaracijos": {"x": value}}}


class FieldMapWiringTests(unittest.TestCase):
    """Structural: the money rows must carry the formatter."""

    def test_each_money_row_uses_the_money_formatter(self):
        for path in MONEY_PATHS:
            with self.subTest(path):
                row = re.search(rf'\["{re.escape(path)}"\](,\s*\w+)?\]', SOURCE)
                self.assertIsNotNone(row, f"{path} missing from FIELD_MAP")
                self.assertEqual(
                    (row.group(1) or "").strip(" ,"),
                    "moneyCell",
                    f"{path} would render raw, unconverted and unlabelled",
                )

    def test_the_compare_table_applies_the_formatter(self):
        self.assertIn("const c = format ? format(v, r) : compactValue(v);", SOURCE)

    def test_converted_columns_are_marked_in_the_compare_header(self):
        header = SOURCE[SOURCE.index("table.cmp") : SOURCE.index("function showMovers")]
        self.assertIn("declaredInLitas(r)", header)
        self.assertIn("Lt→€", header)


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
