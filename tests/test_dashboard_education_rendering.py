"""The education cell must render 2004-ep's institution-key spelling.

`2004-ep` slugs the institution key from its own column heading —
`mokyklos-istaigos-pavadinimas` on 360 of its 361 education entries — where
every other election writes `mokymo-istaigos-pavadinimas`. `educationCell`
read only the common spelling, so those 360 institution names rendered blank
in the dashboard (issue #88). Same lift-and-run harness as
tests/test_dashboard_money_rendering.py: the function is extracted from the
shipped page and executed with node; where node is missing the behavioural
test skips and the structural one still runs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from tests.dashboard_source import script_source

SOURCE = script_source()
NODE = shutil.which("node")


def _education_cell() -> str:
    match = re.search(r"^function educationCell\(.*?^}", SOURCE, re.S | re.M)
    assert match is not None, "educationCell not found in dashboard.js"
    return match.group(0)


def run(value: dict | list) -> object:
    script = (
        f"{_education_cell()}\n"
        f"console.log(JSON.stringify(educationCell({json.dumps(value, ensure_ascii=False)})));"
    )
    out = subprocess.run(
        [NODE, "--input-type=module", "-"], input=script,
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        raise AssertionError(out.stderr.strip())
    return json.loads(out.stdout)


class Structural(unittest.TestCase):
    def test_both_institution_spellings_are_read(self):
        cell = _education_cell()
        self.assertIn("mokymo-istaigos-pavadinimas", cell)
        self.assertIn("mokyklos-istaigos-pavadinimas", cell)


@unittest.skipIf(NODE is None, "node is not installed; behavioural half skipped")
class Behavioural(unittest.TestCase):
    def test_common_spelling_renders(self):
        rendered = run({"irasai": [{
            "issilavinimas": "Aukštasis",
            "mokymo-istaigos-pavadinimas": "Vilniaus universitetas",
            "specialybe": "teisė", "baigimo-metai": "1996",
        }]})
        self.assertEqual(rendered, "Aukštasis — Vilniaus universitetas, teisė (1996)")

    def test_the_entry_array_the_concept_map_hands_the_cell_renders(self):
        # docs/concept-map.json maps `issilavinimas` to `….issilavinimas.irasai`
        # on 43 of 55 elections, so resolveConcept hands the formatter the
        # entry ARRAY, not the object holding it. `value.irasai` off an array
        # is undefined, and the row read an em dash on 69,726 candidacies
        # whose records carry an education (issue #131).
        rendered = run([{
            "issilavinimas": "Aukštasis universitetinis",
            "mokymo-istaigos-pavadinimas": "Vilniaus universitetas",
            "specialybe": "teisė", "baigimo-metai": "1996",
        }])
        self.assertEqual(rendered, "Aukštasis universitetinis — Vilniaus universitetas, teisė (1996)")

    def test_an_empty_entry_array_is_a_dash(self):
        self.assertIsNone(run([]))

    def test_2004_ep_spelling_renders_identically(self):
        rendered = run({"irasai": [{
            "issilavinimas": "Aukštasis",
            "mokyklos-istaigos-pavadinimas": "Vilniaus universitetas",
            "specialybe": "teisė", "baigimo-metai": "1996",
        }]})
        self.assertEqual(rendered, "Aukštasis — Vilniaus universitetas, teisė (1996)")


if __name__ == "__main__":
    unittest.main()
