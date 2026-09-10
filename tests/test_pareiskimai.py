"""The declarations block (issue #162): one reading, in Python and in the page.

`scraper/shared/pareiskimai.py` flags, for the candidacy table, the answers
that depart from each question's usual one; the dashboard's
`declarationsCell` does the same for its comparison row. Both read the rule
from docs/concept-map.json -- `grupe`, `iprastas-atsakymas`, `trumpas` -- and
these tests pin the rule on the answer shapes the corpus holds and hold the
two readings together under node.
"""

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import field_coverage  # noqa: E402
from scraper.shared import pareiskimai  # noqa: E402

CONCEPT_MAP = json.loads((REPO_ROOT / "docs" / "concept-map.json").read_text(encoding="utf-8"))
SOURCE = (REPO_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
REGISTRY = json.loads((REPO_ROOT / "scraper" / "elections.json").read_text(encoding="utf-8"))["elections"]
NODE = shutil.which("node")
DECLARATIONS = pareiskimai.declaration_concepts(CONCEPT_MAP)


def record(answers: dict) -> dict:
    return {"normalized": {"anketa": {"pareiskimai": answers}}}


def unasked_election() -> str:
    """An election whose form asks none of the declarations."""
    mapped = {eid for _, spec in DECLARATIONS for eid in spec["paths"]}
    return next(e["id"] for e in REGISTRY if e["id"] not in mapped)


#: (election, answers under anketa.pareiskimai, what `flagged` returns).
CASES = [
    # 5,207 answers like this one: an office-holder standing for another seat.
    (
        "2024-seimo",
        {"ar-eina-nesuderinamas-pareigas": "Taip", "ar-esate-ar-buvote-kitos-valstybes-pilietis": "Ne"},
        {"nesuderinamos-pareigos": "Taip"},
    ),
    # The echo words: "Nesu/nebuvau" is a denial, "Esu" an affirmative.
    (
        "2020-seimo",
        {"ar-turite-kitos-valstybes-pilietybe": "Nesu/nebuvau", "ar-atliekate-karo-tarnyba": "Esu"},
        {"karo-tarnyba": "Esu"},
    ),
    # The eligibility questions expect "Taip"; it is the "Ne" that departs.
    (
        "2019-prezidento",
        {"ar-esate-pilietis-pagal-kilme": "Taip", "ar-gyvenate-lietuvoje-trejus-metus": "Ne"},
        {"gyvena-lietuvoje": "Ne"},
    ),
    # 2007's question asks whether the right is *not* restricted, and its
    # usual answer, "Neapribota", is a negative word.
    (
        "2007-vasario-25-savivaldybiu",
        {"ar-pasyvioji-rinkimu-teise-neapribota": "Neapribota", "ar-turite-kitos-valstybes-pilietybe": "Turiu"},
        {"kita-pilietybe": "Turiu"},
    ),
    # Asked, and nothing departs.
    ("2016-seimo", {"ar-turite-kitos-valstybes-pilietybe": "Ne"}, {}),
    # Something that is no answer word at all is flagged as given.
    ("2016-seimo", {"ar-turite-kitos-valstybes-pilietybe": "Dvigubą"}, {"kita-pilietybe": "Dvigubą"}),
]


class RuleTests(unittest.TestCase):
    def test_the_answer_words_fall_into_their_classes(self):
        for word in ("Ne", "Nesu", "Neturiu", "Neturi", "Neinu", "Nėra", "Nebuvo", "Nesu/nebuvau", "Neapribota"):
            with self.subTest(word):
                self.assertEqual(pareiskimai.answer_class(word), "neigiamas")
        for word in ("Taip", "Esu", "Turiu", "Einu", "Yra", "Buvo", "Esu/buvau"):
            with self.subTest(word):
                self.assertEqual(pareiskimai.answer_class(word), "teigiamas")
        self.assertIsNone(pareiskimai.answer_class("Dvigubą"))
        self.assertIsNone(pareiskimai.answer_class(None))

    def test_each_case_is_flagged_as_the_rule_says(self):
        for election, answers, expected in CASES:
            with self.subTest(f"{election} {answers}"):
                self.assertEqual(
                    pareiskimai.flagged(record(answers), election, DECLARATIONS, field_coverage.concept_value),
                    expected,
                )

    def test_a_form_that_asks_none_is_not_asked_rather_than_clean(self):
        election = unasked_election()
        flags = pareiskimai.flagged(record({}), election, DECLARATIONS, field_coverage.concept_value)
        self.assertIsNone(flags)
        self.assertEqual(pareiskimai.status(flags), pareiskimai.NOT_ASKED)
        self.assertEqual(pareiskimai.status({}), pareiskimai.ALL_USUAL)
        self.assertEqual(pareiskimai.status({"x": "Taip"}), pareiskimai.SOME_FLAGGED)

    def test_every_declaration_concept_says_what_is_usual(self):
        self.assertGreaterEqual(len(DECLARATIONS), 16)
        for name, spec in DECLARATIONS:
            with self.subTest(name):
                self.assertIn(spec.get("iprastas-atsakymas"), {"neigiamas", "teigiamas"})
                self.assertTrue(spec.get("trumpas"))
                self.assertTrue(spec.get("label-lt"))
                self.assertTrue(spec["paths"])
                # One key per election: a chain, never two questions at once.
                for election, path in spec["paths"].items():
                    self.assertIsInstance(path, str, election)
                    self.assertTrue(path.startswith("anketa.pareiskimai."), path)


@unittest.skipUnless(NODE, "node not installed")
class PageAgreesTests(unittest.TestCase):
    """The page's declarationsCell against the Python rule, case for case."""

    def test_the_comparison_row_says_what_the_table_says(self):
        helpers = "\n".join(
            re.search(rf"^function {name}\(.*?^}}", SOURCE, re.S | re.M).group(0)
            for name in ("isFilledValue", "walkValue", "resolveConcept", "declarationAnswerClass", "declarationsCell")
        )
        consts = "\n".join(
            re.search(pattern, SOURCE, re.M).group(0)
            for pattern in (
                r"^const ROOT_SECTIONS = .*;$",
                r"^const DECLARATION_NEGATIVE = .*;$",
                r"^const DECLARATION_AFFIRMATIVE = .*;$",
                r"^const fmtInt = .*;$",
                r"^const PLURAL = .*;$",
                r"^const plural = .*;$",
            )
        )
        cases = [{"election": e, "record": record(a)} for e, a, _ in CASES]
        cases.append({"election": unasked_election(), "record": record({})})
        script = (
            f"const CONCEPTS = {json.dumps(CONCEPT_MAP['concepts'], ensure_ascii=False)};\n"
            f"{consts}\n{helpers}\n"
            f"const cases = {json.dumps(cases, ensure_ascii=False)};\n"
            "console.log(JSON.stringify(cases.map(c => declarationsCell(null, c.record, { id: c.election }))));"
        )
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        cells = json.loads(out.stdout)
        short = {name: spec["trumpas"] for name, spec in DECLARATIONS}
        for (election, answers, expected), cell in zip(CASES, cells):
            with self.subTest(f"{election} {answers}"):
                if expected:
                    self.assertEqual(cell.split("\n"), [f"{short[k]}: {v}" for k, v in expected.items()])
                else:
                    self.assertTrue(cell.startswith("Įprasti atsakymai"), cell)
        self.assertEqual(cells[-1], "Neklausta")


if __name__ == "__main__":
    unittest.main()
