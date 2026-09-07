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


class DeepLinkTests(unittest.TestCase):
    """The pid is the durable deep link (issue #96); old links must not rot.

    Before the pid the hash was the raw name|birth key, and every merge or
    rename silently broke a shared URL. The page now writes the pid but still
    resolves a legacy key and a merged-away fragment's key from `ak`.
    """

    def test_the_page_writes_the_pid_into_the_hash(self):
        self.assertIn("location.hash = p.pid;", SOURCE)
        self.assertNotIn("location.hash = encodeURIComponent(p.k)", SOURCE)

    def test_a_legacy_or_merged_away_hash_still_resolves(self):
        self.assertRegex(
            SOURCE,
            r"p\.pid === hashKey \|\| p\.k === hashKey \|\| \(p\.ak \|\| \[\]\)\.includes\(hashKey\)",
        )

    def test_every_name_a_person_ran_under_is_searchable(self):
        # A merged person's other names live in the canonical key and "ak" —
        # the display name follows the latest election and can differ from
        # both (the Gerasimovičienė→Gasperavičienė remarriage displays only
        # the second name). The haystack must fold in all of them or a
        # former-name search finds nobody.
        self.assertRegex(
            SOURCE,
            r"\[p\.k, \.\.\.\(p\.ak \|\| \[\]\)\]\.map\(k => k\.slice\(0, k\.lastIndexOf\(\"\|\"\)\)",
        )

    def test_candidate_records_are_fetched_no_store(self):
        self.assertRegex(SOURCE, r'fetch\("\.\./"\s*\+\s*file,\s*\{\s*cache:\s*"no-store"')


class ComparisonTableRenderingTests(unittest.TestCase):
    def test_multi_line_cells_keep_their_line_breaks(self):
        # educationCell joins entries with \n, which textContent only shows
        # if the cell does not collapse whitespace.
        rule = re.search(r"table\.cmp th, table\.cmp td \{[^}]*\}", SOURCE).group(0)
        self.assertIn("white-space: pre-line", rule)

    def test_conviction_uses_the_formatter(self):
        row = re.search(r'\{ concept: "teistumas", derived: true, format: (\w+) \}', SOURCE)
        self.assertIsNotNone(row)
        self.assertEqual(row.group(1), "convictionCell")

    def test_education_uses_the_formatter(self):
        row = re.search(r'\{ concept: "issilavinimas", format: (\w+) \}', SOURCE)
        self.assertIsNotNone(row)
        self.assertEqual(row.group(1), "educationCell")

    def test_the_row_label_column_stays_visible_while_scrolling(self):
        # The table renders 1,746px wide inside a 1,085px pane for an
        # 8-election person; without a sticky first column the row label
        # scrolls away and every cell is a number with no name.
        rule = re.search(r"table\.cmp th:first-child \{[^}]*\}", SOURCE)
        self.assertIsNotNone(rule)
        self.assertIn("position: sticky", rule.group(0))

    def test_the_comparison_header_uses_short_election_names(self):
        # The chart always used shortName; the table used the full names and
        # was the wider for it.
        self.assertIn("th.textContent = electionShortName(e.id);", SOURCE)


class ElectionTermGroupingSourceTests(unittest.TestCase):
    """The election facet lists terms, not 55 peers (issue #122).

    `parent` in the registry names the general election a by-election,
    repeat or re-vote fills a seat of. Both election pickers group each
    general with its seat-fills, and selecting the general matches them too
    -- "2016 Seimas" used to exclude the 2017-2019 by-elections of that same
    Seimas, silently.
    """

    def test_the_facet_and_the_stats_picker_share_the_term_aware_list(self):
        self.assertIn("function fillElectionSelect(select)", SOURCE)
        self.assertIn("fillElectionSelect(fElection);", SOURCE)
        self.assertIn("fillElectionSelect(select);", SOURCE)
        self.assertNotIn(".reverse()) addOption(", SOURCE)

    def test_the_filter_and_the_stats_view_match_through_the_parent(self):
        self.assertIn("if (f.election && !inElection(e, f.election)) return false;", SOURCE)
        self.assertIn("if (inElection(e, id)) candidacies.push(e);", SOURCE)
        self.assertNotIn("e.id !== f.election", SOURCE)

    def test_a_term_row_says_what_it_covers(self):
        # The closed select shows the chosen option's text, so the general's
        # own row inside a group says it spans the term; the stats view then
        # names the seat-fills its figures include.
        self.assertIn("(visa kadencija)", UNCOMMENTED)
        self.assertIn("Skaičiai apima ir tos kadencijos naujus bei pakartotinius rinkimus", UNCOMMENTED)


@unittest.skipIf(NODE is None, "node not installed — behavioural checks skipped")
class ElectionTermGroupingTests(unittest.TestCase):
    """The grouping and the match rule, run under node on a small index."""

    ELECTIONS = [
        {"id": "1996-spalio-20-seimo", "date": "1996-10-20", "shortName": "1996 Seimas"},
        {"id": "1997-kovo-23-seimo-pakartotiniai", "date": "1997-03-23",
         "parent": "1996-spalio-20-seimo", "shortName": "1997-03 Seimas"},
        {"id": "1997-gruodzio-21-seimo-pakartotiniai", "date": "1997-12-21",
         "parent": "1996-spalio-20-seimo", "shortName": "1997-12 Seimas"},
        {"id": "2000-kovo-19-savivaldybiu-tarybu", "date": "2000-03-19", "shortName": "2000 Savivaldybės"},
        {"id": "2000-seimo", "date": "2000-10-08", "shortName": "2000 Seimas"},
        {"id": "2003-birzelio-15-seimo-nauji", "date": "2003-06-15",
         "parent": "2000-seimo", "shortName": "2003-06 Seimas"},
    ]

    def _run(self, expression, elections=None):
        helpers = "\n".join(
            re.search(pattern, SOURCE, re.S | re.M).group(0)
            for pattern in (
                r"^const electionParent = .*?;$",
                r"^const inElection = .*?;$",
                r"^function electionTree\(.*?^}",
            )
        )
        script = (
            f"const ELECTIONS = new Map({json.dumps(elections or self.ELECTIONS)}.map(e => [e.id, e]));\n"
            f"{helpers}\nconsole.log(JSON.stringify({expression}));"
        )
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    TREE = "electionTree([...ELECTIONS.values()]).map(n => [n.election.id, n.children.map(e => e.id)])"

    def test_a_general_groups_its_seat_fills_and_the_terms_run_newest_first(self):
        # Terms newest first; inside a term the general leads and its
        # seat-fills follow in order, the way the term happened.
        self.assertEqual(
            self._run(self.TREE),
            [
                ["2000-seimo", ["2003-birzelio-15-seimo-nauji"]],
                ["2000-kovo-19-savivaldybiu-tarybu", []],
                ["1996-spalio-20-seimo", ["1997-kovo-23-seimo-pakartotiniai", "1997-gruodzio-21-seimo-pakartotiniai"]],
            ],
        )

    def test_a_child_whose_parent_the_index_lacks_stands_on_its_own(self):
        # A subset build carries the by-election but not its general.
        orphan = {"id": "2015-lapkricio-8-telsiu-mero", "date": "2015-11-08",
                  "parent": "2015-kovo-1-savivaldybiu", "shortName": "2015-11 Merai"}
        tree = self._run(self.TREE, [self.ELECTIONS[0], orphan])
        self.assertEqual(tree, [["2015-lapkricio-8-telsiu-mero", []], ["1996-spalio-20-seimo", []]])

    def test_selecting_a_general_includes_its_seat_fills_but_a_seat_fill_stands_alone(self):
        self.assertEqual(
            self._run(
                '[inElection({id: "1997-kovo-23-seimo-pakartotiniai"}, "1996-spalio-20-seimo"),'
                ' inElection({id: "1996-spalio-20-seimo"}, "1996-spalio-20-seimo"),'
                ' inElection({id: "1997-kovo-23-seimo-pakartotiniai"}, "1997-kovo-23-seimo-pakartotiniai"),'
                ' inElection({id: "1996-spalio-20-seimo"}, "1997-kovo-23-seimo-pakartotiniai"),'
                ' inElection({id: "2003-birzelio-15-seimo-nauji"}, "1996-spalio-20-seimo")]'
            ),
            [True, True, True, False, False],
        )


class PartyLineageSourceTests(unittest.TestCase):
    """The party facet groups a nominator with what it continues (issue #123).

    people.json's parties table carries `pr`, the registry's `predecessors`;
    a lineage root gets a group whose first row -- "<name> ir pirmtakai" --
    matches the whole lineage, while every plain row still matches the one
    nominator, so the exact counts the facet showed before are all still
    there.
    """

    def test_the_facet_offers_a_lineage_row_per_root(self):
        self.assertIn("ir pirmtakai", UNCOMMENTED)
        self.assertIn("partyLineageRoots(INDEX.parties || {})", SOURCE)
        self.assertIn("PARTY_LINEAGE_PREFIX + row.root", SOURCE)

    def test_the_filter_matches_through_the_lineage(self):
        self.assertIn("if (f.party && !inParty(e, f.party)) return false;", SOURCE)
        self.assertNotIn("e.p !== f.party", SOURCE)


@unittest.skipIf(NODE is None, "node not installed — behavioural checks skipped")
class PartyLineageTests(unittest.TestCase):
    """The lineage walk and the roots, run under node on a small parties table."""

    PARTIES = {
        "ts-lkd": {"n": "TS-LKD", "t": "partija", "pr": ["tevynes-sajunga", "lkd"]},
        "tevynes-sajunga": {"n": "TS", "t": "partija", "pr": ["lpkts"]},
        "lkd": {"n": "LKD", "t": "partija", "pr": ["lkdp", "krikscioniu-demokratu-sajunga"]},
        "lpkts": {"n": "LPKTS", "t": "partija"},
        "lkdp": {"n": "LKDP", "t": "partija"},
        "krikscioniu-demokratu-sajunga": {"n": "Krikščionių demokratų sąjunga", "t": "partija"},
        "lsdp": {"n": "LSDP", "t": "partija", "pr": ["lddp"]},
        "lddp": {"n": "LDDP", "t": "partija"},
        "vieningas-kaunas": {"n": "Vieningas Kaunas", "t": "partija", "pr": ["komitetas-vieningas-kaunas"]},
        "komitetas-vieningas-kaunas": {"n": "VRK „Vieningas Kaunas“", "t": "komitetas", "pr": ["koalicija-vieningas-kaunas"]},
        "darbo-partija": {"n": "DP", "t": "partija"},
    }

    def _run(self, expression, parties=None):
        helpers = "\n".join(
            re.search(pattern, SOURCE, re.S | re.M).group(0)
            for pattern in (
                r"^const PARTY_LINEAGE_PREFIX = .*?;$",
                r"^let PARTY_LINEAGES = .*?;$",
                r"^const inParty = .*?;$",
                r"^function partyLineage\(.*?^}",
                r"^function partyLineageRoots\(.*?^}",
            )
        )
        script = (
            f"const PARTIES = {json.dumps(parties or self.PARTIES, ensure_ascii=False)};\n"
            f"{helpers}\nconsole.log(JSON.stringify({expression}));"
        )
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    def test_a_lineage_walks_depth_first_in_registry_order(self):
        self.assertEqual(
            self._run('partyLineage(PARTIES, "ts-lkd").map(l => [l.id, l.depth])'),
            [["ts-lkd", 0], ["tevynes-sajunga", 1], ["lpkts", 2], ["lkd", 1],
             ["lkdp", 2], ["krikscioniu-demokratu-sajunga", 2]],
        )

    def test_a_predecessor_the_index_lacks_is_skipped_not_invented(self):
        # The 2011 coalition is in the registry but not in this (subset) index.
        self.assertEqual(
            self._run('partyLineage(PARTIES, "vieningas-kaunas").map(l => l.id)'),
            ["vieningas-kaunas", "komitetas-vieningas-kaunas"],
        )

    def test_the_roots_are_the_entries_nothing_continues(self):
        # TS and LKD have predecessors but are themselves listed by TS-LKD;
        # DP has none at all; the committee is listed by the party.
        self.assertEqual(
            sorted(self._run("partyLineageRoots(PARTIES)")),
            ["lsdp", "ts-lkd", "vieningas-kaunas"],
        )

    def test_a_lineage_row_matches_the_whole_lineage_and_a_plain_row_one_nominator(self):
        self.assertEqual(
            self._run(
                'PARTY_LINEAGES.set("ts-lkd", new Set(partyLineage(PARTIES, "ts-lkd").map(l => l.id))) && '
                '[inParty({p: "lkdp"}, "+ts-lkd"), inParty({p: "ts-lkd"}, "+ts-lkd"), inParty({p: "lsdp"}, "+ts-lkd"),'
                ' inParty({p: "lkdp"}, "ts-lkd"), inParty({p: "ts-lkd"}, "ts-lkd"), inParty({p: "lkdp"}, "+lsdp")]'
            ),
            [True, True, False, False, True, False],
        )


class KeyboardAccessTests(unittest.TestCase):
    """The people list used to be unreachable by keyboard: two focusable
    elements in the whole document, 300 rendered rows of tabIndex -1 divs."""

    def test_rows_are_focusable_buttons(self):
        self.assertIn("div.tabIndex = 0;", SOURCE)
        self.assertIn('div.setAttribute("role", "button");', SOURCE)

    def test_rows_open_on_enter_and_space_and_arrow_between_rows(self):
        for fragment in ('ev.key === "Enter"', 'ev.key === "ArrowDown"', 'ev.key === "ArrowUp"'):
            with self.subTest(fragment):
                self.assertIn(fragment, SOURCE)


class BootFailureTests(unittest.TestCase):
    """boot() used to have no res.ok check and no try/catch, so a missing
    people.json froze the app on "kraunamas indeksas…" with no message."""

    def test_both_fetches_are_ok_checked(self):
        self.assertIn("if (!indexRes.ok) throw new Error", SOURCE)
        self.assertIn("if (!mapRes.ok) throw new Error", SOURCE)

    def test_a_failed_boot_reports_instead_of_freezing(self):
        self.assertIn("function bootFailed(", SOURCE)
        self.assertIn("catch (err)", SOURCE)
        self.assertIn("indekso įkelti nepavyko", SOURCE)


class TriStateElectedTests(unittest.TestCase):
    """`w` is true, false, or absent (no results data) — three states the
    page must keep apart. Counting truthiness read 7,192 unknown outcomes as
    losses (issue #87)."""

    def test_the_won_count_counts_only_true(self):
        self.assertIn("p.e.filter(e => e.w === true).length", SOURCE)

    def test_the_unknown_count_is_reported_beside_it(self):
        self.assertIn("e.w === undefined", SOURCE)
        self.assertIn("be rezultatų duomenų", SOURCE)

    def test_a_card_says_when_results_data_is_missing(self):
        self.assertIn("rezultatų duomenų nėra", SOURCE)


class DualOfficeTests(unittest.TestCase):
    """A council-and-mayor candidacy is two offices with two outcomes (issue
    #140). The page used to read one code, "m", and one flag, "w", so the
    228 + 220 council winners of 2019/2023 who lost the mayoralty matched
    "Meras" + "tik išrinkti" and were absent from "Tarybos narys"."""

    DUAL = {"id": "2019", "r": "tm", "w": True, "wm": False, "wt": True}
    MAYOR_ONLY = {"id": "2019", "r": "m", "w": False}
    COUNCIL = {"id": "2019", "w": True}
    SEIMAS = {"id": "2016-seimo", "w": True}

    def _run(self, expression):
        helpers = "\n".join(
            re.search(rf"^function {name}\(.*?^}}", SOURCE, re.S | re.M).group(0)
            for name in ("rolesOf", "electedAs", "roleLabel", "electedLabel", "candidacyMatches")
        )
        consts = "\n".join(
            re.search(pattern, SOURCE, re.S | re.M).group(0)
            for pattern in (r"^const ROLE_LABELS = new Map\(\[.*?^\]\);", r"^const ROLE_BY_KIND = .*?;$")
        )
        script = (
            'const ELECTIONS = new Map([["2019", {kind: "savivaldybiu"}], ["2016-seimo", {kind: "seimo"}]]);\n'
            "function inElection() { return true; }\nfunction inParty() { return true; }\n"
            f"{consts}\n{helpers}\n"
            f"const DUAL = {json.dumps(self.DUAL)}, MAYOR_ONLY = {json.dumps(self.MAYOR_ONLY)}, "
            f"COUNCIL = {json.dumps(self.COUNCIL)}, SEIMAS = {json.dumps(self.SEIMAS)};\n"
            f"console.log(JSON.stringify({expression}));"
        )
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_roles_are_read_off_the_code_and_the_kind(self):
        self.assertEqual(self._run("[rolesOf(DUAL), rolesOf(MAYOR_ONLY), rolesOf(COUNCIL), rolesOf(SEIMAS)]"),
                         [["t", "m"], ["m"], ["t"], ["s"]])

    @unittest.skipUnless(NODE, "node not installed")
    def test_a_dual_candidacy_matches_both_office_filters(self):
        f = lambda role, won="": f'{{election: "", party: "", municipality: "", role: "{role}", won: "{won}", any: true}}'
        self.assertEqual(self._run(f"[candidacyMatches(DUAL, {f('t')}), candidacyMatches(DUAL, {f('m')}), candidacyMatches(MAYOR_ONLY, {f('t')})]"),
                         [True, True, False])

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_outcome_follows_the_office_chosen(self):
        f = lambda role, won: f'{{election: "", party: "", municipality: "", role: "{role}", won: "{won}", any: true}}'
        self.assertEqual(
            self._run(
                f"[candidacyMatches(DUAL, {f('m', 'won')}), candidacyMatches(DUAL, {f('m', 'lost')}),"
                f" candidacyMatches(DUAL, {f('t', 'won')}), candidacyMatches(DUAL, {f('', 'won')})]"
            ),
            [False, True, True, True],
        )

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_labels_name_both_offices_and_the_one_won(self):
        self.assertEqual(self._run("[roleLabel(DUAL), electedLabel(DUAL), roleLabel(SEIMAS), electedLabel(MAYOR_ONLY)]"),
                         ["Tarybos narys / Meras", "Tarybos narys", "Seimo narys", ""])

    def test_the_csv_exports_the_office_won(self):
        self.assertIn('"isrinktas", "isrinktas_kaip"', SOURCE)
        self.assertIn("electedLabel(e),", SOURCE)


class PhotoShapeTests(unittest.TestCase):
    """25,332 records carry their portrait as VRK's own URL — the only shape
    29% of persons have — and the page used to refuse it, show a photo for
    3% of persons, and prefer the oldest election's portrait."""

    def test_the_url_shape_is_accepted(self):
        self.assertIn('/^https?:\\/\\//.test(photo)', SOURCE)

    def test_the_newest_portrait_wins(self):
        self.assertIn("[...loaded].reverse()", SOURCE)

    def test_photos_load_lazily(self):
        self.assertIn('img.loading = "lazy";', SOURCE)


class ArchiveComparisonRowTests(unittest.TestCase):
    """Four comparison rows read an em-dash for every 1996-1998 Seimas archive
    record until issue #69, because that family's card questionnaire was never
    parsed. This runs a real re-parsed record through the page's own concept
    rows — CONCEPT_ROWS resolved against the real docs/concept-map.json, the
    exact machinery showPerson uses — so it fails if the parser stops emitting
    those keys, the concept map stops mapping them, or the page's resolver
    stops resolving them (issue #87's test gap).
    """

    ELECTION = "1996-spalio-20-seimo"

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

    def _cells(self, record, election=None):
        election = election or self.ELECTION
        concept_map = json.loads(
            (REPO_ROOT / "docs" / "concept-map.json").read_text(encoding="utf-8")
        )
        labels = {
            cid: spec["label-lt"]
            for cid, spec in {**concept_map["concepts"], **concept_map.get("derived", {})}.items()
            if spec.get("label-lt")
        }
        helpers = "\n".join(
            re.search(rf"^function {name}\(.*?^}}", SOURCE, re.S | re.M).group(0)
            for name in (
                "resolvePath", "compactValue", "educationCell", "workHistoryCell",
                "nameCell", "convictionCell", "convictionLines", "deslug", "labelFor",
                "isFilledValue", "walkValue", "resolveConcept", "resolveRow", "rowLabel",
            )
        )
        consts = "\n".join(
            re.search(pattern, SOURCE, re.S | re.M).group(0)
            for pattern in (
                r"^const SECTION_LABELS = \{.*?^\};",
                r"^const ROOT_SECTIONS = .*?;$",
                r"^const CONCEPT_ROWS = \[.*?^\];",
            )
        )
        script = (
            f"{CONVICTION_CONSTANTS}\n"
            f"const CONCEPTS = {json.dumps(concept_map['concepts'])};\n"
            f"const CONCEPT_LABELS = {json.dumps(labels, ensure_ascii=False)};\n"
            "const SEGMENT_LABELS = {};\n"
            f"{consts}\n{helpers}\n"
            "function moneyCell() { return null; }\n"
            "function incomeCell() { return null; }\n"
            f"const r = {json.dumps(self.RECORD if record is None else record)};\n"
            "const out = {};\n"
            "for (const row of CONCEPT_ROWS) {\n"
            f"  const {{ value }} = resolveRow(row, r, {json.dumps(election)});\n"
            "  const c = row.format ? row.format(value, r) : compactValue(value);\n"
            "  out[rowLabel(row)] = c == null ? null : c;\n"
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
    def test_the_entry_array_eras_render_their_education(self):
        # The 43 elections mapped through `….issilavinimas.irasai` handed the
        # cell an array and rendered an em dash for every one of their
        # 69,726 educated candidacies (issue #131): the 2020-era biography
        # shape and the 2016-era anketa shape, through the real map.
        entry = {"issilavinimas": "Aukštasis universitetinis",
                 "mokymo-istaigos-pavadinimas": "Vilniaus universitetas",
                 "specialybe": "teisė", "baigimo-metai": "1996"}
        biography = {"normalized": {"biografija": {"issilavinimas": {"aprasas": None, "irasai": [entry]}}}}
        self.assertEqual(
            self._cells(biography, "2020-seimo")["Išsilavinimas"],
            "Aukštasis universitetinis — Vilniaus universitetas, teisė (1996)",
        )
        anketa = {"normalized": {"anketa": {"issilavinimas": {"aprasas": None, "irasai": [entry]}}}}
        self.assertEqual(
            self._cells(anketa, "2016-seimo")["Išsilavinimas"],
            "Aukštasis universitetinis — Vilniaus universitetas, teisė (1996)",
        )

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_municipality_row_reads_the_2019_dict_and_the_mayoral_card(self):
        # 27,523 candidacies carried kandidatavimas.savivaldybe or the
        # mayoral card's savivaldybe and rendered "this election never
        # published this field" (issue #131).
        record = {"normalized": {}, "kandidatavimas": {"savivaldybe": {"id": "19972", "number": 15, "name": "Kauno miesto"}}}
        self.assertEqual(self._cells(record, "2019-kovo-3-savivaldybiu-tarybu")["Savivaldybė"], "Kauno miesto")
        self.assertEqual(self._cells(record, "2023-kovo-5-savivaldybiu-tarybu-ir-meru")["Savivaldybė"], "Kauno miesto")
        mayoral = {"normalized": {"profilis": {"kita": {"savivaldybe": {"pavadinimas": "Savivaldybė", "reiksme": "Jonavos rajono (10)", "nuorodos": []}}}}}
        self.assertEqual(self._cells(mayoral, "2017-balandzio-23-meru")["Savivaldybė"], "Jonavos rajono (10)")

    @unittest.skipUnless(NODE, "node not installed")
    def test_a_label_the_card_omits_still_reads_as_nothing(self):
        # Astrauskas' card leaves the workplace blank, so the parser writes no
        # key and the cell must stay an em-dash rather than "null". The row is
        # the era-bridged one: einamos-pareigos falls back to
        # pagrindine-darboviete, which is what the 1996 card maps.
        self.assertIsNone(self._cells(self.RECORD)["Einamos pareigos / darbovietė"])


if __name__ == "__main__":
    unittest.main()
