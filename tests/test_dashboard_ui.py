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
# Comments may name an English label while explaining it (the Biggest movers
# picker, say); only text that can reach the DOM is chrome.
UNCOMMENTED = "\n".join(
    line for line in SOURCE.splitlines() if not line.lstrip().startswith("//")
)
NODE = shutil.which("node")

# The module-level constants `convictionCell` closes over, lifted with it
# whenever the page's conviction helpers are run under node.
CONVICTION_CONSTANTS = "\n".join(
    re.search(pattern, SOURCE, flags).group(0)
    for pattern, flags in (
        (r"^const AFFIRMATIVE_ANSWERS = .*;$", re.M),
        (r"^const isAffirmative = .*;$", re.M),
        (r"^const RELATED_DECLARATIONS = \{.*?^\};$", re.S | re.M),
        (r"^const OFFENCE_KEYS = .*;$", re.M),
    )
)


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
                self.assertNotIn(phrase, UNCOMMENTED)

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


@unittest.skipIf(NODE is None, "node not installed — behavioural checks skipped")
class EducationCellTests(unittest.TestCase):
    """`issilavinimas` is an object; compactValue() dumped its raw keys.

    Before the formatter every column read
    "irasai: issilavinimas: Aukštasis; mokymo-istaigos-pavadinimas: ..."
    across the whole comparison row.
    """

    def _render(self, values):
        fn = re.search(r"^function educationCell\(.*?^}", SOURCE, re.S | re.M).group(0)
        script = f"{fn}\nconsole.log(JSON.stringify({json.dumps(values)}.map(educationCell)));"
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    def test_one_line_per_education_entry(self):
        value = {
            "aprasas": None,
            "irasai": [
                {
                    "issilavinimas": "Aukštasis universitetinis",
                    "mokymo-istaigos-pavadinimas": "Vilniaus universitetas",
                    "specialybe": "Filologija",
                    "baigimo-metai": "2001",
                },
                {
                    "issilavinimas": "Aukštasis",
                    "mokymo-istaigos-pavadinimas": "Mykolo Romerio universitetas",
                    "specialybe": "Viešasis administravimas",
                    "baigimo-metai": "2021",
                },
            ],
        }
        self.assertEqual(
            self._render([value])[0],
            "Aukštasis universitetinis — Vilniaus universitetas, Filologija (2001)\n"
            "Aukštasis — Mykolo Romerio universitetas, Viešasis administravimas (2021)",
        )

    def test_the_1997_archive_shape_renders_as_its_bare_level(self):
        # scripts/reshape_1997_education.py wraps that era's single level in
        # the corpus object, leaving the three fields it never published null.
        value = {
            "aprasas": None,
            "irasai": [
                {
                    "issilavinimas": "Aukštasis",
                    "mokymo-istaigos-pavadinimas": None,
                    "specialybe": None,
                    "baigimo-metai": None,
                }
            ],
        }
        self.assertEqual(self._render([value])[0], "Aukštasis")

    def test_nothing_declared_renders_as_a_dash_not_an_empty_object(self):
        self.assertEqual(
            self._render([{"aprasas": None, "irasai": []}, None, ""]),
            [None, None, None],
        )

    def test_a_free_text_description_leads(self):
        value = {"aprasas": "Savarankiškos studijos", "irasai": []}
        self.assertEqual(self._render([value])[0], "Savarankiškos studijos")


@unittest.skipIf(NODE is None, "node not installed — behavioural checks skipped")
class ConvictionCellTests(unittest.TestCase):
    """One conviction concept over the three shapes the corpus publishes.

    The row used to print the yes/no answer alone, so a candidate's actual
    conviction record -- the most consequential fact on their page -- never
    reached the screen, and "VRK never asked" rendered exactly like "no".
    Mirrors scraper/shared/conviction_details.teistumas(); see GitHub issue #86.
    """

    def _render(self, anketa):
        functions = "\n".join(
            re.search(rf"^function {name}\(.*?^}}", SOURCE, re.S | re.M).group(0)
            for name in ("convictionCell", "convictionLines")
        )
        record = json.dumps({"normalized": {"anketa": anketa}})
        script = (
            f"{CONVICTION_CONSTANTS}\n{functions}\n"
            f"console.log(JSON.stringify(convictionCell(null, {record})));"
        )
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    def test_a_question_never_asked_does_not_read_as_a_denial(self):
        self.assertEqual(self._render({"pareiskimai": {}}), "Neklausta")

    def test_a_denial_is_the_answer_itself(self):
        self.assertEqual(
            self._render({"pareiskimai": {"ar-buvote-pripazintas-kaltu": "Ne"}}), "Ne"
        )
        # The 2000/2004 forms spell the same answer "Nėra".
        self.assertEqual(
            self._render({"pareiskimai": {"ar-buvote-pripazintas-kaltu": "Nėra"}}), "Nėra"
        )

    def test_declared_with_nothing_published_says_so(self):
        self.assertEqual(
            self._render(
                {
                    "pareiskimai": {"ar-buvote-pripazintas-kaltu": "Taip"},
                    "teistumo-detales": {"irasai": []},
                }
            ),
            "Taip — detalių nepaskelbta",
        )

    def test_one_line_per_conviction(self):
        self.assertEqual(
            self._render(
                {
                    "pareiskimai": {"ar-buvote-pripazintas-kaltu": "Taip"},
                    "teistumo-detales": {
                        "irasai": [
                            {
                                "nuosprendzio-data": "2008-06-04",
                                "nuosprendzio-valstybe": "Lietuva",
                                "nuosprendzio-institucija": "Ukmergės rajono apylinkės teismas",
                                "nusikalstama-veika": "BK 178 str. 1 d.",
                            }
                        ]
                    },
                }
            ),
            "Taip\n2008-06-04, Ukmergės rajono apylinkės teismas — BK 178 str. 1 d.",
        )

    def test_the_nested_offence_shape_renders_the_same_way(self):
        self.assertEqual(
            self._render(
                {
                    "pareiskimai": {"ar-buvote-pripazintas-kaltu": "Taip"},
                    "teistumo-detales": {
                        "irasai": [
                            {
                                "nuosprendzio-data": "1995-12-28",
                                "nuosprendzio-institucija": "LAZDIJŲ R. APYLINKĖS TEISMAS",
                                "nusikalstamos-veikos": [
                                    {"kesinimosi-objektas-baudziamojo-kodekso-skyriaus-ir-straipsnio-pavadinimas": "16 str."},
                                    {"kesinimosi-objektas-baudziamojo-kodekso-skyriaus-ir-straipsnio-pavadinimas": "82 str. 1 d."},
                                ],
                            }
                        ]
                    },
                }
            ),
            "Taip\n1995-12-28, LAZDIJŲ R. APYLINKĖS TEISMAS — 16 str.; 82 str. 1 d.",
        )

    def test_a_conviction_under_a_neighbouring_question_is_not_hidden_by_a_no(self):
        # The 2000-2014 forms ask separately about a grave crime. It is a
        # different question, so the answer to this one stands — but printing
        # the "Ne" alone reads as "no conviction" for the 20 records that
        # declared one there.
        self.assertEqual(
            self._render(
                {
                    "pareiskimai": {
                        "ar-buvote-pripazintas-kaltu": "Ne",
                        "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Buvo",
                    }
                }
            ),
            "Ne\nTaip: sunkus nusikaltimas",
        )

    def test_a_denied_neighbouring_question_adds_nothing(self):
        self.assertEqual(
            self._render(
                {
                    "pareiskimai": {
                        "ar-buvote-pripazintas-kaltu": "Ne",
                        "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Nebuvo",
                        "ar-nebaigta-teismo-paskirta-bausme": "Neturiu",
                    }
                }
            ),
            "Ne",
        )

    def test_a_free_text_explanation_is_the_detail_where_that_is_all_there_is(self):
        # 2000-2015: no detail table, an explanation instead — and the 2000 and
        # 2004 forms answer the question "Yra", not "Taip".
        self.assertEqual(
            self._render(
                {
                    "pareiskimai": {
                        "ar-buvote-pripazintas-kaltu": "Yra",
                        "teisiniai-argumentai": "Teistumas panaikintas (2003)",
                    }
                }
            ),
            "Yra\nTeistumas panaikintas (2003)",
        )


class FreshnessTests(unittest.TestCase):
    """Both fetches must bypass the browser cache.

    Records are rewritten in place when a parser gains a field, so a cached
    copy shows empty rows against a corpus that has the figures — and an empty
    row is indistinguishable from "never declared".
    """

    def test_the_index_is_fetched_no_store(self):
        self.assertRegex(SOURCE, r'fetch\("people\.json",\s*\{\s*cache:\s*"no-store"')

    def test_candidate_records_are_fetched_no_store(self):
        self.assertRegex(SOURCE, r'fetch\("\.\./"\s*\+\s*file,\s*\{\s*cache:\s*"no-store"')


class ComparisonTableRenderingTests(unittest.TestCase):
    def test_multi_line_cells_keep_their_line_breaks(self):
        # educationCell joins entries with \n, which textContent only shows
        # if the cell does not collapse whitespace.
        rule = re.search(r"table\.cmp th, table\.cmp td \{[^}]*\}", SOURCE).group(0)
        self.assertIn("white-space: pre-line", rule)

    def test_conviction_uses_the_formatter(self):
        row = re.search(r'\["Teistumas", \[[^\]]*\](, *\w+)?\]', SOURCE)
        self.assertIsNotNone(row)
        self.assertEqual((row.group(1) or "").strip(" ,"), "convictionCell")

    def test_education_uses_the_formatter(self):
        row = re.search(r'\["Išsilavinimas", \[[^\]]*\](, *\w+)?\]', SOURCE)
        self.assertIsNotNone(row)
        self.assertEqual((row.group(1) or "").strip(" ,"), "educationCell")


class ArchiveComparisonRowTests(unittest.TestCase):
    """Four comparison rows read an em-dash for every 1996-1998 Seimas archive
    record until issue #69, because that family's card questionnaire was never
    parsed. This runs a real re-parsed record through the page's own
    `resolvePath`/`compactValue`/`educationCell`, so it fails if either the
    parser stops emitting those keys or the field map stops resolving them.
    """

    # astrauskas-vytautas, 1996-spalio-20-seimo: the fixture candidate with no
    # biography page at all, whose whole anketa therefore comes from the card.
    RECORD = {
        "normalized": {
            "anketa": {
                "gimimo-vieta": "Macenių k. , Plungės raj.",
                "tautybe": "Lietuvis (-ė)",
                "mokslo-laipsnis": "Habilituotas medicinos mokslų daktaras",
                "pedagoginis-vardas": "Profesorius",
                "uzsienio-kalbos": ["Rusų", "Anglų", "Vokiečių"],
                "seimine-padetis": "Vedęs",
            }
        }
    }

    def _cells(self, record):
        helpers = "\n".join(
            re.search(rf"^function {name}\(.*?^}}", SOURCE, re.S | re.M).group(0)
            for name in ("resolvePath", "compactValue", "educationCell", "convictionCell", "convictionLines")
        )

        field_map = re.search(r"^const FIELD_MAP = \[.*?^\];", SOURCE, re.S | re.M).group(0)
        script = (
            f"{CONVICTION_CONSTANTS}\n{helpers}\n"
            "function moneyCell() { return null; }\n"
            f"{field_map}\n"
            f"const r = {json.dumps(record)};\n"
            "const out = {};\n"
            "for (const [label, paths, format] of FIELD_MAP) {\n"
            "  let v = null;\n"
            "  for (const p of paths) { v = resolvePath(r.normalized || {}, p);"
            " if (v != null && v !== '') break; }\n"
            "  const c = format ? format(v, r) : compactValue(v);\n"
            "  out[label] = c == null ? null : c;\n"
            "}\n"
            "console.log(JSON.stringify(out));"
        )
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_card_questionnaire_reaches_the_comparison_table(self):
        cells = self._cells(self.RECORD)
        self.assertEqual(cells["Šeiminė padėtis"], "Vedęs")
        self.assertEqual(cells["Užsienio kalbos"], "Rusų; Anglų; Vokiečių")

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_cards_education_level_renders_as_its_level(self):
        record = json.loads(json.dumps(self.RECORD))
        record["normalized"]["anketa"]["issilavinimas"] = {
            "aprasas": None,
            "irasai": [{
                "issilavinimas": "Aukštasis",
                "mokymo-istaigos-pavadinimas": None,
                "specialybe": None,
                "baigimo-metai": None,
            }],
        }
        self.assertEqual(self._cells(record)["Išsilavinimas"], "Aukštasis")

    @unittest.skipUnless(NODE, "node not installed")
    def test_a_label_the_card_omits_still_reads_as_nothing(self):
        # Astrauskas' card leaves "Pagrindinė darbovietė" blank, so the parser
        # writes no key and the cell must stay an em-dash rather than "null".
        self.assertIsNone(self._cells(self.RECORD)["Pagrindinė darbovietė"])


if __name__ == "__main__":
    unittest.main()
