"""Page-level invariants for the Astro dashboard.

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

from tests.dashboard_source import dashboard_source, style_source

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = dashboard_source()
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
            [NODE, "-"], input=script, capture_output=True, text=True, timeout=30
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
        out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
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
        out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
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
        # A row's link *is* the pid URL, so the click, the shared link and the
        # Back button all take one path (issue #147). showPerson only
        # canonicalises a legacy key, and with replaceState, so it adds no
        # history entry and does not re-enter the router.
        self.assertIn('main.href = `#${p.pid}`;', SOURCE)
        self.assertIn(
            'if (decodeURIComponent(location.hash.slice(1)) !== p.pid) {\n'
            '    history.replaceState(null, "", `#${p.pid}`);',
            SOURCE,
        )
        self.assertNotIn("location.hash = p.pid;", SOURCE)
        self.assertNotIn("location.hash = encodeURIComponent(p.k)", SOURCE)

    def test_a_legacy_or_merged_away_hash_still_resolves(self):
        self.assertRegex(
            SOURCE,
            r"p\.pid === key \|\| p\.k === key \|\| \(p\.ak \|\| \[\]\)\.includes\(key\)",
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
        # The stats view scopes through `candidacyMatches` now, which starts
        # with the same `inElection` test — and applies the other five facets
        # too, which it used to drop (issue #148).
        self.assertIn("if (f.election && !inElection(e, f.election)) return false;", SOURCE)
        self.assertIn("if (candidacyMatches(e, f)) pairs.push([p, e]);", SOURCE)
        self.assertIn("function scopedFilters(electionId)", SOURCE)
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
        out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    TREE = "electionTree([...ELECTIONS.values()]).map(n => [n.election.id, n.children.map(e => e.id)])"

    def test_a_general_groups_its_seat_fills_and_the_terms_run_newest_first(self):
        # Terms newest first; inside a term the general leads and its
        # seat-fills also run newest first.
        self.assertEqual(
            self._run(self.TREE),
            [
                ["2000-seimo", ["2003-birzelio-15-seimo-nauji"]],
                ["2000-kovo-19-savivaldybiu-tarybu", []],
                ["1996-spalio-20-seimo", ["1997-gruodzio-21-seimo-pakartotiniai", "1997-kovo-23-seimo-pakartotiniai"]],
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
        out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
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
    elements in the whole document, 300 rendered rows of tabIndex -1 divs.
    Then it was reachable but its comparison checkbox was not (issue #147):
    each row was a `role="button"` div wrapping the box, which makes the box
    presentational to ARIA -- no role, no name, no checked state -- while the
    row's own keydown handler preventDefaulted Space and opened the person
    instead. Measured in the live page: the box was focusable, Space arrived
    with `defaultPrevented: true` and the box stayed unticked, so the
    Palyginti flow that docs/DASHBOARD.md presents as a headline feature was
    mouse-only.
    """

    def test_the_row_is_not_a_button_wrapping_a_checkbox(self):
        self.assertNotIn('div.setAttribute("role", "button");', SOURCE)
        self.assertNotIn("div.tabIndex = 0;", SOURCE)
        # Nothing swallows a key on the row any more, and the box is not
        # asked to stop a click from reaching a handler that is gone.
        self.assertNotIn('ev.key === "Enter" || ev.key === " "', SOURCE)
        self.assertNotIn('box.addEventListener("click", (ev) => ev.stopPropagation());', SOURCE)

    def test_the_name_is_a_link_and_the_checkbox_says_whom_it_compares(self):
        self.assertIn('const main = document.createElement("a");', SOURCE)
        self.assertIn('main.href = `#${p.pid}`;', SOURCE)
        self.assertIn('box.setAttribute("aria-label", `Pažymėti palyginimui: ${p.n}`);', SOURCE)

    def test_the_arrow_keys_still_walk_the_list(self):
        for fragment in ('ev.key === "ArrowDown"', 'ev.key === "ArrowUp"'):
            with self.subTest(fragment):
                self.assertIn(fragment, SOURCE)
        # From the last row back up to the search box, and from the search box
        # down into the first row's link.
        self.assertIn('else document.getElementById("search").focus();', SOURCE)
        self.assertIn('document.querySelector("#results .row .rowmain")', SOURCE)


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
        out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
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


class VotesAndConstituencyTests(unittest.TestCase):
    """Issue #133: 29.5 million preference votes on 59,275 candidacies and
    the constituency on 9,309 reached no artifact. people.json now carries
    `v`, `cv` and `ap`; the page offers the constituency as a facet, the
    votes as comparison rows, CSV columns, a line on the election card and
    a ranking in the election summary."""

    ROOT_2000 = {
        "kandidatavimas": {
            "vienmandatesBalsai": {"balsadezese": 301, "pastu": 20, "isViso": 321, "procentai": 1.67, "vieta": 7},
            "vienmandatesBalsai2": {"isViso": 6999, "procentai": 55.52, "vieta": 1},
        },
        "normalized": {},
    }
    PRESIDENTIAL = {"kandidatavimas": {"turai": [{"turas": 1, "balsai": 147610, "procentai-nuo-galiojanciu": 11.85}, {"turas": 2, "balsai": 700000}]}, "normalized": {}}
    ARCHIVE = {"normalized": {"kandidatavimas": [{"apygarda": "Gargždų", "turai": [{"turas": 1, "balsai": 398, "vieta": 9}]}, {"apygarda": "Daugiamandatė"}]}}
    MODERN = {"kandidatavimas": {"isrinktas": False}, "normalized": {"profilis": {"kita": {}}}}

    def _run(self, expression):
        helpers = "\n".join(
            re.search(rf"^function {name}\(.*?^}}", SOURCE, re.S | re.M).group(0)
            for name in ("votesCell", "constituencyRounds", "constituencyVotesCell", "rolesOf", "electedAs", "candidacyMatches")
        )
        consts = "\n".join(
            re.search(pattern, SOURCE, re.S | re.M).group(0)
            for pattern in (r"^const fmtInt = .*?;$", r"^const ROUND_NUMERALS = .*?;$", r"^const ROLE_LABELS = new Map\(\[.*?^\]\);", r"^const ROLE_BY_KIND = .*?;$")
        )
        script = (
            'const ELECTIONS = new Map([["2016-seimo", {kind: "seimo"}]]);\n'
            "function inElection() { return true; }\nfunction inParty() { return true; }\n"
            f"{consts}\n{helpers}\n"
            f"const ROOT_2000 = {json.dumps(self.ROOT_2000)}, PRESIDENTIAL = {json.dumps(self.PRESIDENTIAL)}, "
            f"ARCHIVE = {json.dumps(self.ARCHIVE)}, MODERN = {json.dumps(self.MODERN)};\n"
            f"console.log(JSON.stringify({expression}));"
        )
        out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    @staticmethod
    def _spaces(text):
        return text.replace("\u00a0", " ").replace("\u202f", " ") if isinstance(text, str) else text

    def test_the_facet_the_csv_and_the_summary_are_in_the_page(self):
        self.assertIn('id="fConstituency"', SOURCE)
        self.assertIn("INDEX.constituencies", SOURCE)
        self.assertIn('"apygarda", "partijos_id"', SOURCE)
        self.assertIn('"pirmumo_balsai", "balsai_apygardoje"', SOURCE)
        self.assertIn("Daugiausiai pirmumo balsų", SOURCE)
        self.assertIn("balsų skaičių nėra", SOURCE)

    def test_the_comparison_rows_name_the_three_vote_concepts(self):
        for concept in ("pirmumo-balsai", "apygardos-balsai", "sarasas-balsai"):
            self.assertIn(f'concept: "{concept}"', SOURCE)

    @unittest.skipUnless(NODE, "node not installed")
    def test_votes_render_as_a_count_and_nothing_as_nothing(self):
        self.assertEqual(self._spaces(self._run("votesCell(4321)")), "4 321")
        self.assertEqual(self._run("[votesCell(null), votesCell(''), votesCell('x')]"), [None, None, None])

    @unittest.skipUnless(NODE, "node not installed")
    def test_every_round_of_the_race_is_read_off_the_record(self):
        rounds = self._run("[constituencyRounds(ROOT_2000), constituencyRounds(PRESIDENTIAL), constituencyRounds(ARCHIVE), constituencyRounds(MODERN)]")
        self.assertEqual([[r["balsai"] for r in shape] for shape in rounds], [[321, 6999], [147610, 700000], [398], []])
        self.assertEqual(rounds[0][0], {"turas": 1, "balsai": 321, "procentai": 1.67, "vieta": 7})
        self.assertEqual(rounds[1][0]["procentai"], 11.85)

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_constituency_row_prints_one_line_per_round(self):
        cells = self._run("[constituencyVotesCell(null, ROOT_2000), constituencyVotesCell(null, PRESIDENTIAL), constituencyVotesCell(null, MODERN)]")
        self.assertEqual(self._spaces(cells[0]), "I turas: 321 (1,67 %), 7 vieta\nII turas: 6 999 (55,52 %), 1 vieta")
        self.assertEqual(self._spaces(cells[1]), "I turas: 147 610 (11,85 %)\nII turas: 700 000")
        self.assertIsNone(cells[2])

    @unittest.skipUnless(NODE, "node not installed")
    def test_the_constituency_facet_matches_by_the_interned_index(self):
        f = lambda ap: f'{{election: "", party: "", municipality: "", constituency: "{ap}", role: "", won: "", any: true}}'
        self.assertEqual(
            self._run(f"[candidacyMatches({{id: '2016-seimo', ap: 3}}, {f(3)}), candidacyMatches({{id: '2016-seimo', ap: 3}}, {f(0)}), candidacyMatches({{id: '2016-seimo'}}, {f(3)}), candidacyMatches({{id: '2016-seimo', ap: 0}}, {f(0)})]"),
            [True, False, False, True],
        )


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
                "votesCell", "constituencyRounds", "constituencyVotesCell",
                "priorOfficeCell", "declarationScopeCell", "campaignCell", "declarationsCell",
                "declarationAnswerClass",
            )
        )
        consts = "\n".join(
            re.search(pattern, SOURCE, re.S | re.M).group(0)
            for pattern in (
                r"^const SECTION_LABELS = \{.*?^\};",
                r"^const ROOT_SECTIONS = .*?;$",
                r"^const CONCEPT_ROWS = \[.*?^\];",
                r"^const fmtInt = .*?;$",
                r"^const ROUND_NUMERALS = .*?;$",
                r"^const DECLARATION_SCOPES = \{.*?^\};",
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
        out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
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


class ThreeFalsehoods(unittest.TestCase):
    """Three views stated something false rather than showing a gap (#148).

    Each of the three was reproduced against the running dashboard before it
    was fixed, and again after; these hold the shipped code to what those
    runs showed.
    """

    def test_the_remainder_row_fills_its_winner_cell(self):
        # It was set to the empty string while the count and share were
        # filled, and an empty cell in a column of numbers reads as a zero:
        # 2019 municipal's summary said "išrinkta 1 505" over a column
        # summing to 1 184, hiding 321 winners. Verified live after the fix:
        # the column sums to 1,505 and the "kiti (99)" row reads 321.
        self.assertIn("const restIds = new Set(top.slice(15).map(([pid]) => pid));", SOURCE)
        self.assertIn(
            "const restWon = withParty.filter(e => restIds.has(e.p) && e.w === true).length;",
            SOURCE,
        )
        self.assertIn("tr.insertCell().textContent = fmtInt(restWon);", SOURCE)
        self.assertNotIn('tr.insertCell().textContent = "";', SOURCE)

    def test_a_failed_record_load_is_said_out_loud_in_every_view(self):
        # The comparison view ended its fan-out in
        # `records.filter(([, r]) => !r._error)` and rendered 16 rows of em
        # dashes over the failures, with two index-derived rows above still
        # looking authoritative. One banner, both views.
        self.assertIn("function failureBanner(failed) {", SOURCE)
        self.assertIn('warn.setAttribute("role", "alert");', SOURCE)
        self.assertIn("const banner = failureBanner(failed);", SOURCE)
        self.assertIn("const compareBanner = failureBanner(failed);", SOURCE)
        self.assertIn(
            "return [p, records.filter(([, r]) => !r._error), records.filter(([, r]) => r._error)];",
            SOURCE,
        )
        # And it says what the empty cells below it do not mean.
        self.assertIn("tušti langeliai nereiškia, kad nebuvo atsakyta", UNCOMMENTED)

    def test_the_asset_pane_does_not_claim_nothing_was_declared(self):
        # "Nė vienuose šio asmens rinkimuose turto ar pajamų nedeklaruota" is
        # a claim about the data; with every record failing to load it is a
        # claim about nothing.
        self.assertIn("function buildAssetPane(loaded, failedCount = 0) {", SOURCE)
        self.assertIn("buildAssetPane(loaded, failed.length)", SOURCE)
        self.assertIn("Nėra ką rodyti:", UNCOMMENTED)

    def test_the_header_views_honour_the_sidebar_facets(self):
        # `showAggregates` copied one facet across (the election) and then
        # walked every person; `showMovers` read none. With 2024 Seimas +
        # a party + "tik išrinkti" the list said one number and the summary
        # another, with the selects still showing the filters.
        self.assertIn("function scopedFilters(electionId)", SOURCE)
        self.assertIn("if (candidacyMatches(e, f)) pairs.push([p, e]);", SOURCE)
        self.assertIn("if (f.any && !p.e.some(e => candidacyMatches(e, f))) continue;", SOURCE)
        # The three facet-scoped views -- the election summary, the movers
        # and one nominator's summary (issue #162) -- name what they are
        # scoped by, and offer a way out. The coverage grid takes no facets:
        # it describes the forms, not the candidacies.
        self.assertEqual(SOURCE.count("appendFacetNote(facetLine,"), 3)
        self.assertIn("Taikomi šoniniai filtrai", UNCOMMENTED)
        self.assertIn('clear.textContent = "rodyti visus";', SOURCE)

    def test_the_facet_note_is_silent_when_nothing_is_filtered(self):
        # The absence of the line is the default and is not a claim.
        self.assertIn("if (!named.length) return;", SOURCE)


class ExportTests(unittest.TestCase):
    """What the CSV hands to a spreadsheet (issue #149).

    `exportCSV` writes a BOM and joins on ';' "which is what lt-LT Excel
    expects", and then wrote its money through `String(number)`: replaying the
    page's own field function over all 113,073 rows gave 308,135 money cells,
    199,626 of them with a '.' decimal -- which an lt-LT import reads as text,
    so no sum, no sort, no chart -- and 90 cells starting with one of
    `= + - @ TAB CR`, which Excel renders as #NAME?.
    """

    def _run(self, names, script):
        helpers = "\n".join(
            re.search(rf"^function {name}\(.*?^\}}$", SOURCE, re.S | re.M).group(0)
            for name in names
        )
        out = subprocess.run(
            [NODE, "-"], input=f"{helpers}\n{script}", capture_output=True, text=True, timeout=30
        )
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    @unittest.skipIf(NODE is None, "node not installed")
    def test_money_carries_a_comma_decimal(self):
        cells = self._run(
            ["csvMoney"],
            "console.log(JSON.stringify([12345.67, 0, 0.5, -8.25, null, 1000000]"
            ".map(csvMoney)));",
        )
        self.assertEqual(cells, ["12345,67", "0", "0,5", "-8,25", "", "1000000"])

    @unittest.skipIf(NODE is None, "node not installed")
    def test_a_formula_looking_cell_is_quoted_out(self):
        cells = self._run(
            ["csvField"],
            "console.log(JSON.stringify(["
            '"=SUM(A1:A2)", "+37060000000", "-8,25", "@svetaine.lt", "\\tPastaba",'
            ' "UAB \\"Katos studija\\"", "Salės nuoma", null'
            "].map(csvField)));",
        )
        self.assertEqual(
            cells,
            [
                "'=SUM(A1:A2)",
                "'+37060000000",
                "'-8,25",
                "'@svetaine.lt",
                # A tab is not the ';' separator, so it needs the apostrophe
                # but no quoting.
                "'\tPastaba",
                '"UAB ""Katos studija"""',
                "Salės nuoma",
                "",
            ],
        )

    def test_the_election_column_carries_its_name_beside_the_slug(self):
        # The nominator has had an id/name pair since #82; the election, which
        # is the column a reader groups by, had only "2024-seimo".
        self.assertIn('"rinkimai", "rinkimu_pavadinimas", "data",', SOURCE)
        self.assertIn(
            '(ELECTIONS.get(e.id) || {}).name || (ELECTIONS.get(e.id) || {}).shortName || ""',
            SOURCE,
        )

    def test_every_money_column_goes_through_the_money_formatter(self):
        self.assertIn("csvMoney(m[0]), csvMoney(m[1]), csvMoney(m[2]), csvMoney(m[3]),", SOURCE)


class AssetChartTests(unittest.TestCase):
    """The chart's axis and its width (issue #149)."""

    @unittest.skipIf(NODE is None, "node not installed")
    def test_no_bar_rises_above_the_top_gridline(self):
        # Bars were scaled to `max` and gridlines drawn while `t <= max`, so
        # the top label was floor(max/tick)*tick: replayed over every person,
        # 59,177 of the 60,379 charts with a value (98.01 %) had their
        # tallest bar above the axis, median ratio 0.824, worst 0.667.
        script = """
        const cases = [316000, 240000, 1, 999, 1000, 4001, 1234567, 0.5];
        console.log(JSON.stringify(cases.map(max => {
          const step = Math.pow(10, Math.floor(Math.log10(max / 4)));
          const tick = Math.ceil(max / 4 / step) * step;
          const axisMax = Math.ceil(max / tick) * tick;
          let top = 0;
          for (let t = 0; t <= axisMax; t += tick) top = t;
          return [max <= axisMax, Math.abs(top - axisMax) < tick / 1000];
        })));
        """
        out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        for fits, labelled in json.loads(out.stdout):
            self.assertTrue(fits, "a bar can still exceed the axis")
            self.assertTrue(labelled, "the top gridline is not the axis maximum")

    def test_the_axis_maximum_drives_the_bars_the_gridlines_and_the_loop(self):
        self.assertIn("const axisMax = Math.ceil(max / tick) * tick;", SOURCE)
        self.assertIn("const y = (v) => mT + plotH - (v / axisMax) * plotH;", SOURCE)
        self.assertIn("for (let t = 0; t <= axisMax; t += tick)", SOURCE)
        self.assertIn("const h = Math.max(1.5, (v / axisMax) * plotH);", SOURCE)
        self.assertNotIn("(v / max) * plotH", SOURCE)

    def test_the_chart_is_sized_to_the_pane_it_is_drawn_into(self):
        # It was `cols.length * 132 + 100` whatever it had to fit in: 2,740 px
        # in an 830 px wrapper for a 20-candidacy person. Columns narrow to
        # fit, down to 52 px, and only past that does the wrapper scroll --
        # verified in the browser at 1280x900, where 1 to 13 candidacies fit
        # whole and 20 scrolls 321 px instead of 1,910.
        self.assertIn("function availableWidth() {", SOURCE)
        self.assertIn(
            "const colW = Math.max(52, Math.min(132, (availableWidth() - mL - mR) / cols.length));",
            SOURCE,
        )
        self.assertNotIn("cols.length * 132 + 100", UNCOMMENTED)

    def test_a_scrolling_chart_opens_on_the_most_recent_election(self):
        # Built while its tab is display:none, where every width is 0, so the
        # scroll has to wait for the tab to be shown.
        self.assertIn('pane.dataset.scrollRight = "1";', SOURCE)
        self.assertIn("scrollRightOnce(pane);", SOURCE)
        self.assertIn(
            'for (const wrap of pane.querySelectorAll(".chartwrap")) wrap.scrollLeft = wrap.scrollWidth;',
            SOURCE,
        )

    def test_a_wrapper_with_more_to_show_says_so(self):
        rule = re.search(r"\.tablewrap \{([^}]+)\}", SOURCE).group(1)
        self.assertIn("overflow-x: auto", rule)
        # The scrolling-shadows pair: a panel-coloured mask that scrolls with
        # the content, and a shadow fixed to each edge.
        self.assertRegex(rule, r"background-attachment:\s*local,\s*local,\s*scroll,\s*scroll")
        self.assertEqual(rule.count("radial-gradient(farthest-side"), 2)


class NarrowScreenTests(unittest.TestCase):
    """Under 900 px (issue #149).

    Measured at 375x812 before the fix: the header took 158.5 px, the list
    361.75 and the person pane 291.75 -- 35.9 % of the screen for the thing
    the page is for -- and `body { overflow: hidden }` meant there was no
    scrolling to reclaim it. After: the same person's pane is 3,035 px tall in
    a 3,683 px document that scrolls, with no horizontal overflow.
    """

    QUERY = style_source().split("@media (max-width: 900px) {", 1)[1].split("@media", 1)[0]

    def test_the_document_scrolls(self):
        self.assertIn("html, body { height: auto; }", self.QUERY)
        self.assertIn("body { overflow: visible; }", self.QUERY)
        self.assertIn("#person { overflow-y: visible;", self.QUERY)

    def test_the_result_list_keeps_a_bounded_scroll_of_its_own(self):
        # Otherwise the document grows by every rendered row.
        rule = re.search(r"#results \{([^}]+)\}", self.QUERY).group(1)
        cap = re.search(r"max-height:\s*(\d+)vh", rule)
        self.assertIsNotNone(cap)
        self.assertLessEqual(int(cap.group(1)), 46)
        self.assertIn("overflow-y: auto", re.search(r"#results \{([^}]+)\}", SOURCE).group(1))

    def test_the_filters_fold_away(self):
        self.assertIn('<button id="filterToggle" type="button" aria-controls="filters"', SOURCE)
        self.assertRegex(self.QUERY, r"#filterToggle \{ display: inline-(?:block|flex);")
        # `display: grid` on #filters beats the UA sheet's rule for [hidden],
        # which is why this has to be said -- and why the filters come back by
        # themselves on a wide screen whatever the button was left at.
        self.assertIn("#filters[hidden] { display: none; }", self.QUERY)
        self.assertIn("setFilters(false);", SOURCE)
        self.assertIn('filterToggle.setAttribute("aria-expanded", String(open));', SOURCE)

    def test_the_field_list_stacks(self):
        # 260px of label beside the value leaves 100px for the value on a
        # 375px screen.
        self.assertIn("dl { grid-template-columns: minmax(0, 1fr);", self.QUERY)


class BareUrlTests(unittest.TestCase):
    def test_a_url_renders_as_a_link(self):
        # 17 keys hold a bare http(s) URL and 802 of the 1,329 sampled
        # records printed at least one as an 88-character string, while
        # `appendSourceLinks` had rendered the `nuorodos` shape as anchors all
        # along. Verified live: a 6-candidacy person's page went from 0 to 5
        # anchors, each rel="noopener noreferrer".
        scalar = re.search(r'if \(typeof v !== "object"\) \{(.*?)\n  \}', SOURCE, re.S).group(1)
        self.assertIn('if (/^https?:\\/\\/\\S+$/.test(text)) {', scalar)
        self.assertIn('a.rel = "noopener noreferrer";', scalar)
        self.assertIn('a.target = "_blank";', scalar)


class RoutingTests(unittest.TestCase):
    """The URL and the screen say the same thing (issue #147).

    `grep hashchange|popstate|pushState` matched nothing: the hash was read
    once at boot, `showPerson` assigned it (one history entry per person) and
    three views assigned `""`, so Back moved history while the pane still
    showed the previous person and the shared URL no longer matched the
    screen. Driven in the live page after the fix: two clicks, then Back
    brings the first person *and their hash* back, Back again lands on the
    empty hash with the placeholder, and Forward returns the person.
    """

    def test_the_hash_is_the_one_way_in(self):
        self.assertIn('window.addEventListener("hashchange", routeFromHash);', SOURCE)
        self.assertIn("function routeFromHash() {", SOURCE)
        self.assertIn("function personFromHash() {", SOURCE)
        # Boot routes through the same function rather than reading the hash
        # itself.
        self.assertIn("  routeFromHash();\n}", SOURCE)

    def test_a_hash_naming_nobody_is_said_out_loud(self):
        # Leaving the last person on screen under a stale link is the defect;
        # the placeholder names the key that resolved to nothing.
        self.assertIn("function showPlaceholder(message) {", SOURCE)
        self.assertIn("Nuoroda „${key}“ nieko neatitinka.", SOURCE)

    def test_the_header_views_do_not_claim_a_person(self):
        # `location.hash = ""` pushes an entry and re-enters the router.
        # Five views: the election summary, the movers, the comparison, and
        # issue #162's nominator summary and coverage grid.
        self.assertNotIn('location.hash = ""', SOURCE)
        self.assertEqual(SOURCE.count("clearHash();"), 5)
        self.assertIn(
            'history.replaceState(null, "", location.pathname + location.search);', SOURCE
        )

    def test_a_slow_render_cannot_land_on_a_later_one(self):
        # `fetchRecord` memoises by file, so an uncached 20-election person
        # followed by a cached one used to end with the first rendered under
        # the second's URL and row highlight. Driven live after the fix: the
        # second person is on screen, under their own hash and
        # announcement.
        self.assertIn("let renderToken = 0;", SOURCE)
        self.assertEqual(SOURCE.count("const token = ++renderToken;"), 2)
        self.assertEqual(SOURCE.count("if (token !== renderToken) return;"), 2)
        # And the synchronous views end whatever is in flight: the
        # placeholder, the election summary, the movers, and the nominator
        # summary and coverage grid of issue #162.
        self.assertEqual(SOURCE.count("renderToken += 1;"), 5)


class ScreenReaderTests(unittest.TestCase):
    """Measured in the live page before the fix: 0 elements with aria-live, 0
    `<label>` elements, `aria-label` on `#search` null -- the six facets
    carried only a `title` -- and `showPerson` moved no focus and announced
    nothing while the first focusable inside `#person` was the 614th tab stop
    (issue #147). After: 7 labels, one live region, and focus on the pane.
    """

    def test_the_search_box_and_every_facet_have_a_label(self):
        self.assertRegex(SOURCE, r'<label\b[^>]*for="search"[^>]*>[^<]+</label>')
        # Astro expands each FilterField into an associated label and select.
        # Browser tests additionally assert the actual compiled accessible names.
        self.assertIn('<label for={id}>{label}</label>', SOURCE)
        self.assertIn('<select id={id} title={title}>', SOURCE)
        for control in ("fElection", "fParty", "fMunicipality", "fConstituency", "fRole", "fWon", "fNationality"):
            with self.subTest(control):
                self.assertRegex(SOURCE, rf'<FilterField id="{control}" label="[^"]+"')
        rule = re.search(r"\.sr \{([^}]+)\}", SOURCE).group(1)
        self.assertIn("position: absolute", rule)
        self.assertIn("clip: rect(0 0 0 0)", rule)

    def test_the_page_has_a_live_region_and_uses_it(self):
        self.assertIn('<div id="announce" class="sr" role="status" aria-live="polite">', SOURCE)
        self.assertIn("function announce(text) {", SOURCE)
        # Whose record is on screen, and whether any of it failed to load.
        self.assertIn("`${p.n}: ${fmtInt(p.e.length)}", SOURCE)

    def test_a_rendered_person_takes_focus(self):
        self.assertRegex(SOURCE, r'<(?:div|section) id="person" tabindex="-1"[ >]')
        self.assertIn("root.focus({ preventScroll: true });", SOURCE)
        self.assertIn('root.scrollIntoView({ block: "start" });', SOURCE)
        self.assertIn("root.scrollTop = 0;", SOURCE)
        # Focused programmatically on every render, so the ring belongs to
        # keyboard navigation only.
        self.assertRegex(SOURCE, r"#person:focus:not\(:focus-visible\)[^{]*\{ outline: none; \}")


class FacetUsabilityTests(unittest.TestCase):
    """The selects and the typing cost (issue #147)."""

    def test_every_option_carries_its_label_as_a_tooltip(self):
        # 299 of 338 nominator options were wider than their box, the widest
        # 7.1x over, and 25 of them had a title.
        self.assertIn("  option.title = label;", SOURCE)

    def test_the_two_long_label_facets_take_the_whole_row(self):
        for control in ("fParty", "fMunicipality"):
            self.assertRegex(SOURCE, rf'<FilterField id="{control}"[^>]+\bwide\s*/>')
        self.assertIn(".filter-field-wide { grid-column: 1 / -1; }", SOURCE)
        # Measured live after the fix: the box goes 163 -> 333 px, the
        # nominator overflow 299 -> 123 of 338 and the municipality 50 -> 0
        # of 63.

    def test_typing_renders_once_a_burst_not_once_a_keystroke(self):
        # renderList rebuilds 300 rows over a scan costing 14.0 ms; measured
        # live, "KAZLAUSKAS" now renders the list once instead of ten times.
        self.assertIn("const SEARCH_DEBOUNCE_MS = 120;", SOURCE)
        self.assertIn("searchTimer = setTimeout(renderList, SEARCH_DEBOUNCE_MS);", SOURCE)
        self.assertNotIn('addEventListener("input", renderList)', SOURCE)
        # A select fires once, so the facets stay immediate.
        self.assertIn('document.getElementById(id).addEventListener("change", renderList);', SOURCE)


@unittest.skipIf(NODE is None, "node not installed — behavioural checks skipped")
class FilterCompositionTests(unittest.TestCase):
    """`candidacyMatches`, the point where every facet meets (issue #163).

    `grep -rl candidacyMatches tests/` was empty: the tested predicates
    (`inElection`, `inParty`) were covered and the function that composes them
    with the municipality, constituency, role and tri-state outcome filters
    was not — and three separately-filed defects sat in that gap, including
    the dual-role outcome collapse of issue #140 and the facet scoping of
    #155.
    """

    ELECTIONS = [
        {"id": "2019-kovo-3-savivaldybiu-tarybu", "kind": "savivaldybiu", "date": "2019-03-03"},
        {"id": "2020-seimo", "kind": "seimo", "date": "2020-10-11"},
        {"id": "2021-spalio-10-meru", "kind": "mero", "date": "2021-10-10",
         "parent": "2019-kovo-3-savivaldybiu-tarybu"},
        {"id": "2019-prezidento", "kind": "prezidento", "date": "2019-05-12"},
    ]

    #: A council-and-mayor candidacy that won the seat and lost the mayoralty
    #: — 448 people in 2019/2023 — plus one of each simpler shape.
    DUAL = {"id": "2019-kovo-3-savivaldybiu-tarybu", "r": "tm", "w": True, "wt": True, "wm": False,
            "sv": 0, "p": "ts-lkd"}
    COUNCIL = {"id": "2019-kovo-3-savivaldybiu-tarybu", "w": False, "sv": 12, "p": "lsdp"}
    SEIMAS = {"id": "2020-seimo", "w": True, "ap": 0, "p": "ts-lkd"}
    NO_RESULTS = {"id": "2019-prezidento", "p": "ts-lkd"}
    BY_ELECTION = {"id": "2021-spalio-10-meru", "r": "m", "w": True, "sv": 12}

    def _matches(self, candidacy, **filters):
        full = {"election": "", "party": "", "municipality": "", "constituency": "",
                "role": "", "won": "", "any": True}
        full.update(filters)
        helpers = "\n".join(
            re.search(pattern, SOURCE, re.S | re.M).group(0)
            for pattern in (
                r"^const PARTY_LINEAGE_PREFIX = .*?;$",
                r"^const electionParent = .*?;$",
                r"^const inElection = .*?;$",
                r"^const inParty = \(e, value\).*?;$",
                r"^const ROLE_BY_KIND = .*?;$",
                r"^function rolesOf\(e\) \{.*?^\}",
                r"^function electedAs\(e, role\) \{.*?^\}",
                r"^function candidacyMatches\(e, f\) \{.*?^\}",
            )
        )
        script = (
            f"const ELECTIONS = new Map({json.dumps(self.ELECTIONS)}.map(e => [e.id, e]));\n"
            "const PARTY_LINEAGES = new Map();\n"
            f"{helpers}\n"
            f"console.log(JSON.stringify(candidacyMatches({json.dumps(candidacy)}, {json.dumps(full)})));"
        )
        out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    def test_an_office_filter_reads_that_offices_outcome(self):
        # "Meras" + "tik išrinkti" is the mayors, not the mayors plus the
        # council winners who also stood for mayor (issue #140).
        self.assertTrue(self._matches(self.DUAL, role="t", won="won"))
        self.assertFalse(self._matches(self.DUAL, role="m", won="won"))
        self.assertTrue(self._matches(self.DUAL, role="m", won="lost"))
        # And with no office chosen the any-office flag applies.
        self.assertTrue(self._matches(self.DUAL, won="won"))

    def test_the_outcome_filter_is_tri_state(self):
        self.assertTrue(self._matches(self.NO_RESULTS, won="unknown"))
        self.assertFalse(self._matches(self.NO_RESULTS, won="lost"))
        self.assertFalse(self._matches(self.NO_RESULTS, won="won"))
        self.assertTrue(self._matches(self.COUNCIL, won="lost"))
        self.assertFalse(self._matches(self.COUNCIL, won="unknown"))

    def test_municipality_zero_is_a_municipality(self):
        # `if (f.municipality !== "")` rather than a truthiness test: index 0
        # is Akmenė, and `!f.municipality` would drop it.
        self.assertTrue(self._matches(self.DUAL, municipality="0"))
        self.assertFalse(self._matches(self.COUNCIL, municipality="0"))
        self.assertTrue(self._matches(self.COUNCIL, municipality="12"))

    def test_constituency_zero_is_a_constituency(self):
        self.assertTrue(self._matches(self.SEIMAS, constituency="0"))
        self.assertFalse(self._matches(self.COUNCIL, constituency="0"))

    def test_the_role_comes_from_the_election_kind_or_the_candidacy(self):
        self.assertTrue(self._matches(self.SEIMAS, role="s"))
        self.assertFalse(self._matches(self.SEIMAS, role="t"))
        self.assertTrue(self._matches(self.COUNCIL, role="t"))
        self.assertTrue(self._matches(self.DUAL, role="t"))
        self.assertTrue(self._matches(self.DUAL, role="m"))
        self.assertTrue(self._matches(self.BY_ELECTION, role="m"))

    def test_a_general_election_filter_includes_its_seat_fills(self):
        self.assertTrue(self._matches(self.BY_ELECTION, election="2019-kovo-3-savivaldybiu-tarybu"))
        self.assertTrue(self._matches(self.BY_ELECTION, election="2021-spalio-10-meru"))
        self.assertFalse(self._matches(self.COUNCIL, election="2021-spalio-10-meru"))

    def test_the_filters_conjoin(self):
        self.assertTrue(
            self._matches(self.DUAL, election="2019-kovo-3-savivaldybiu-tarybu",
                          party="ts-lkd", municipality="0", role="t", won="won")
        )
        # One clause failing is enough.
        self.assertFalse(
            self._matches(self.DUAL, election="2019-kovo-3-savivaldybiu-tarybu",
                          party="lsdp", municipality="0", role="t", won="won")
        )


@unittest.skipIf(NODE is None, "node not installed — behavioural checks skipped")
class CsvRowTests(unittest.TestCase):
    """The row `exportCSV` writes, which nothing exercised (issue #163).

    `csvField` and `csvMoney` are pinned above; this runs the whole row
    builder over a synthetic index, because the defects issue #149 measured
    were in how the row *assembles* — a money column that skipped the
    formatter, a missing election name — not in the helpers.
    """

    INDEX = {
        "elections": [
            {"id": "2020-seimo", "kind": "seimo", "date": "2020-10-11",
             "name": "2020 m. spalio 11 d. Lietuvos Respublikos Seimo rinkimai",
             "shortName": "2020 Seimas"},
        ],
        "municipalities": ["Akmenės rajono"],
        "constituencies": ["Aukštaitijos"],
        "parties": {"ts-lkd": {"n": "Tėvynės sąjunga – Lietuvos krikščionys demokratai"}},
        "educationLevels": [{"label": "Aukštasis universitetinis"}],
        "people": [
            {"pid": "p1", "n": "Vardenė PAVARDENĖ", "b": "1970-01-02", "_f": "",
             "e": [{"id": "2020-seimo", "w": True, "sv": 0, "ap": 0, "p": "ts-lkd",
                    "v": 1234, "cv": 5678, "ed": 1, "wp": "=UAB \"Rizika\"",
                    "m": [1234.5, 0, 98765.43, None], "lt": True, "ds": False}]},
        ],
    }

    def _row(self):
        helpers = "\n".join(
            re.search(pattern, SOURCE, re.S | re.M).group(0)
            for pattern in (
                r"^const PARTY_LINEAGE_PREFIX = .*?;$",
                r"^const electionParent = .*?;$",
                r"^const inElection = .*?;$",
                r"^const inParty = \(e, value\).*?;$",
                r"^const ROLE_LABELS = new Map\(\[.*?\]\);$",
                r"^const ROLE_BY_KIND = .*?;$",
                r"^function rolesOf\(e\) \{.*?^\}",
                r"^function electedAs\(e, role\) \{.*?^\}",
                r"^function roleLabel\(e\) \{.*?^\}",
                r"^function electedLabel\(e\) \{.*?^\}",
                r"^function candidacyMatches\(e, f\) \{.*?^\}",
                r"^function personMatches\(p, q, f\) \{.*?^\}",
                r"^function csvField\(value\) \{.*?^\}",
                r"^function csvMoney\(value\) \{.*?^\}",
                r"^function exportCSV\(\) \{.*?^\}",
            )
        )
        # exportCSV reads the search box and the facets, and hands the rows to
        # a Blob and an anchor: the smallest possible stand-ins for both, so
        # the row builder itself is what runs.
        stubs = """
        const INDEX = %s;
        const ELECTIONS = new Map(INDEX.elections.map(e => [e.id, e]));
        const PARTY_LINEAGES = new Map();
        const fold = (s) => (s || "").toUpperCase();
        const activeFilters = () => ({election: "", party: "", municipality: "",
          constituency: "", role: "", won: "", any: false});
        let captured = "";
        globalThis.document = {
          getElementById: () => ({ value: "" }),
          createElement: () => ({ click() {}, set href(v) {}, get href() { return ""; } }),
        };
        globalThis.Blob = class { constructor(parts) { captured = parts.join(""); } };
        globalThis.URL = { createObjectURL: () => "blob:x", revokeObjectURL() {} };
        """ % json.dumps(self.INDEX)
        script = f"{stubs}\n{helpers}\nexportCSV();\nconsole.log(JSON.stringify(captured));"
        out = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr.strip())
        return json.loads(out.stdout)

    def _cells(self):
        text = self._row()
        self.assertTrue(text.startswith("\ufeff"), "no BOM: lt-LT Excel needs one")
        lines = text.lstrip("\ufeff").split("\r\n")
        self.assertEqual(len(lines), 2)
        header, row = (line.split(";") for line in lines)
        self.assertEqual(len(header), len(row))
        return dict(zip(header, row))

    def test_the_export_is_a_bom_a_header_and_one_row_per_candidacy(self):
        self.assertEqual(self._cells()["pid"], "p1")

    def test_every_column_holds_what_it_says(self):
        cells = self._cells()
        self.assertEqual(cells["vardas_pavarde"], "Vardenė PAVARDENĖ")
        self.assertEqual(cells["gimimo_data"], "1970-01-02")
        self.assertEqual(cells["rinkimai"], "2020-seimo")
        # The registry name beside the slug (issue #149). No `;` or `"` in it,
        # so `csvField` leaves it unquoted.
        self.assertEqual(
            cells["rinkimu_pavadinimas"],
            "2020 m. spalio 11 d. Lietuvos Respublikos Seimo rinkimai",
        )
        self.assertEqual(cells["data"], "2020-10-11")
        self.assertEqual(cells["pareigos"], "Seimo narys")
        self.assertEqual(cells["savivaldybe"], "Akmenės rajono")
        self.assertEqual(cells["apygarda"], "Aukštaitijos")
        self.assertEqual(cells["isrinktas"], "taip")
        self.assertEqual(cells["pirmumo_balsai"], "1234")
        self.assertEqual(cells["balsai_apygardoje"], "5678")
        self.assertEqual(cells["deklaruota_litais"], "taip")
        self.assertEqual(cells["tik_darbo_santykiu_pajamos"], "")

    def test_money_is_comma_decimal_and_a_formula_is_neutralised(self):
        cells = self._cells()
        self.assertEqual(cells["turtas_eur"], "1234,5")
        self.assertEqual(cells["pinigines_lesos_eur"], "0")
        self.assertEqual(cells["pajamos_eur"], "98765,43")
        self.assertEqual(cells["turtas_ir_lesos_eur"], "")
        # A workplace starting with `=` is a formula to Excel.
        self.assertEqual(cells["darboviete"], '"\'=UAB ""Rizika"""')


if __name__ == "__main__":
    unittest.main()
