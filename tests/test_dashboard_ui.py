"""Page-level invariants for dashboard/index.html.

The UI is Lithuanian, like the data it shows. The two things here worth
pinning against regression rather than eyeballing are the Lithuanian plural
rule -- which is not "n === 1", so a hand-rolled ternary gets 11 and 21 wrong
-- and the sidebar's `white-space: nowrap`, without which a birth date breaks
mid-date onto two lines. See GitHub issue #63.

The plural helper is lifted out of the page and run under node, so the test
covers the shipped code; where node is missing that half skips.
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


class DocumentTests(unittest.TestCase):
    def test_the_page_declares_itself_lithuanian(self):
        self.assertIn('<html lang="lt">', SOURCE)

    def test_birth_dates_do_not_wrap_in_the_sidebar(self):
        rule = re.search(r"\.row \.bd \{[^}]*\}", SOURCE)
        self.assertIsNotNone(rule)
        self.assertIn("white-space: nowrap", rule.group(0))

    def test_the_two_plus_elections_filter_is_gone(self):
        for trace in ("multiOnly", "2+ elections"):
            self.assertNotIn(trace, SOURCE)

    def test_no_english_chrome_survives(self):
        # The strings this pass replaced; a regression would reintroduce them.
        for phrase in (
            "Biggest movers",
            "Search a person",
            "Select a person",
            "Elections & answers",
            "Assets & income",
            "Compare across elections",
            "birth date unknown",
            "✓ elected",
            "largest increase",
        ):
            with self.subTest(phrase):
                self.assertNotIn(phrase, SOURCE)

    def test_the_result_count_reports_matches_and_rendered_rows(self):
        # It used to print the match count alone while 300 rows existed.
        self.assertIn("rodoma ${fmtInt(shown)}", SOURCE)
        self.assertIn("RENDER_LIMIT", SOURCE)


@unittest.skipIf(NODE is None, "node not installed — behavioural checks skipped")
class LithuanianPluralTests(unittest.TestCase):
    """1 asmuo, 2 asmenys, 11 asmenų, 21 asmuo — not an n===1 split."""

    def _forms(self, numbers):
        helpers = "\n".join(
            re.search(rf"^const {name} = .*?;$", SOURCE, re.S | re.M).group(0)
            for name in ("PLURAL", "plural")
        )
        script = (
            f"{helpers}\nconsole.log(JSON.stringify("
            f'{json.dumps(numbers)}.map(n => plural(n, "asmuo", "asmenys", "asmenų"))));'
        )
        out = subprocess.run(
            [NODE, "-e", script], capture_output=True, text=True, timeout=30
        )
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    def test_singular_form_applies_to_1_21_and_101_but_not_11(self):
        self.assertEqual(
            self._forms([1, 11, 21, 101, 111]),
            ["asmuo", "asmenų", "asmuo", "asmuo", "asmenų"],
        )

    def test_few_form_applies_to_2_through_9_and_their_decades(self):
        self.assertEqual(
            self._forms([2, 9, 22, 39]), ["asmenys", "asmenys", "asmenys", "asmenys"]
        )

    def test_genitive_form_applies_to_the_teens_and_round_tens(self):
        self.assertEqual(
            self._forms([10, 11, 19, 20, 100]),
            ["asmenų", "asmenų", "asmenų", "asmenų", "asmenų"],
        )


if __name__ == "__main__":
    unittest.main()
