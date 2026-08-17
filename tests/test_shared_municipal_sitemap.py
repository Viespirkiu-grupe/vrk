"""Unit tests for the sitemap machinery shared by the municipal elections.

`scraper.shared.municipal_sitemap` was extracted out of the 2023 module once
2019 turned out to publish the same two-structure listing. Both election
modules are now thin wrappers over it, which means a defect fixed here is fixed
for both — and a regression here breaks both silently.

Everything below runs on synthetic HTML modelled on the real
savKandidataiSarasai.html column layout, so these tests stay fast and stay
independent of either election's committed fixtures. The end-to-end counts are
pinned separately, per election, against VRK's own published totals.
"""

from __future__ import annotations

import re
import unittest

from bs4 import BeautifulSoup

from scraper.elections.savivaldybiu_2019.sitemap import (
    MAYOR_MARKER_PATTERN as MAYOR_MARKER_2019,
)
from scraper.elections.savivaldybiu_2023.sitemap import (
    MAYOR_MARKER_PATTERN as MAYOR_MARKER_2023,
)
from scraper.shared.municipal_sitemap import (
    LIST_LINK_MARKER,
    VRK_STATINIAI_BASE,
    build_candidate_id,
    clean_candidate_name,
    extract_candidate_note,
    extract_list_page_links,
    is_elected,
    municipality_from_cell,
    parse_int,
    parse_numbered_name,
    select_data_table,
    table_rows,
)


# --------------------------------------------------------------------------
# Synthetic savKandidataiSarasai.html
#
# Real column order, taken from the committed 2019 lists-index.html:
#
#   0 Savivaldybė                        (municipality link, "1. Akmenės rajono")
#   1 Mandatų skaičius (be merų)
#   2 Sąrašų skaičius
#   3 Kandidatų skaičius sąrašuose
#   4 Sąrašo numeris                     <- the list number
#   5 Sąrašas                            (list link, rpgId-N_rorgId-M)
#   6 Kandidatų skaičius sąraše          <- expectedCandidates, read as cells[-2]
#   7 Gautų mandatų skaičius (be mero)
#
# Only the first row of a municipality group fills columns 0-3; every later row
# for that municipality leaves them blank.
# --------------------------------------------------------------------------

BASE_PATH = "/rinkimai/864/rnk1144/kandidatai"
MUNICIPALITY_HREF = f"?srcUrl={BASE_PATH}/savKandidataiApygardoje_rpgId-{{rpg}}.html"
LIST_HREF = f"?srcUrl={BASE_PATH}/savKandidataiTarNarApygardoje_rpgId-{{rpg}}_rorgId-{{rorg}}.html"

AKMENE_RPG_ID = "19982"
AKMENE_NAME = "Akmenės rajono"
AKMENE_NUMBER = 1
# Column 1 of the group-header row. Deliberately different from any list number
# below: it is what a "first numeric cell" scan would wrongly return.
AKMENE_MANDATES = 24
AKMENE_LIST_COUNT = 5
AKMENE_TOTAL_CANDIDATES = 167

ALYTUS_RPG_ID = "19984"
ALYTUS_NAME = "Alytaus miesto"
ALYTUS_NUMBER = 2
ALYTUS_MANDATES = 27


def _municipality_cell(rpg_id: str, number: int, name: str) -> str:
    return (
        '<td align="left">'
        f'<a href="{MUNICIPALITY_HREF.format(rpg=rpg_id)}">{number}. {name}</a>'
        "</td>"
    )


def _list_row(
    *,
    leading_cells: str,
    list_number: object,
    rpg_id: str,
    rorg_id: str,
    list_name: str,
    list_candidates: object,
    list_mandates: object,
) -> str:
    return (
        "<tr>"
        f"{leading_cells}"
        f'<td align="right">{list_number}</td>'
        '<td align="left">'
        f'<a href="{LIST_HREF.format(rpg=rpg_id, rorg=rorg_id)}">{list_name}</a>'
        "</td>"
        f'<td align="right">{list_candidates}</td>'
        f'<td align="right">{list_mandates}</td>'
        "</tr>"
    )


def group_header_row(
    *,
    municipality_rpg_id: str,
    municipality_number: int,
    municipality_name: str,
    mandates: object,
    list_count: object,
    total_candidates: object,
    **list_kwargs: object,
) -> str:
    leading = (
        _municipality_cell(municipality_rpg_id, municipality_number, municipality_name)
        + f'<td align="right">{mandates}</td>'
        + f'<td align="right">{list_count}</td>'
        + f'<td align="right">{total_candidates}</td>'
    )
    return _list_row(leading_cells=leading, **list_kwargs)  # type: ignore[arg-type]


def continuation_row(**list_kwargs: object) -> str:
    # Blank municipality/mandate/list-count/total cells, exactly as VRK emits
    # them on every row after the first of a group.
    leading = (
        '<td align="left"></td>'
        '<td align="right"></td>'
        '<td align="right"></td>'
        '<td align="right"></td>'
    )
    return _list_row(leading_cells=leading, **list_kwargs)  # type: ignore[arg-type]


def lists_index_html(*rows: str) -> str:
    body = "".join(rows)
    return (
        "<html><body>"
        '<table id="table2" class="partydata"><tbody>'
        "<tr>"
        '<th scope="col">Savivaldybė</th>'
        '<th scope="col">Mandatų skaičius (be merų)</th>'
        '<th scope="col">Sąrašų skaičius</th>'
        '<th scope="col">Kandidatų skaičius sąrašuose</th>'
        '<th scope="col">Sąrašo numeris</th>'
        '<th scope="col">Sąrašas</th>'
        '<th scope="col">Kandidatų skaičius sąraše</th>'
        '<th scope="col">Gautų mandatų skaičius (be mero)</th>'
        "</tr>"
        f"{body}"
        "</tbody></table>"
        "</body></html>"
    )


TWO_MUNICIPALITY_INDEX = lists_index_html(
    group_header_row(
        municipality_rpg_id=AKMENE_RPG_ID,
        municipality_number=AKMENE_NUMBER,
        municipality_name=AKMENE_NAME,
        mandates=AKMENE_MANDATES,
        list_count=AKMENE_LIST_COUNT,
        total_candidates=AKMENE_TOTAL_CANDIDATES,
        list_number=2,
        rpg_id=AKMENE_RPG_ID,
        rorg_id="28698",
        list_name="Lietuvos valstiečių ir žaliųjų sąjunga",
        list_candidates=42,
        list_mandates=5,
    ),
    continuation_row(
        list_number=4,
        rpg_id=AKMENE_RPG_ID,
        rorg_id="28232",
        list_name="Lietuvos socialdemokratų partija",
        list_candidates=50,
        list_mandates=12,
    ),
    continuation_row(
        list_number=6,
        rpg_id=AKMENE_RPG_ID,
        rorg_id="28364",
        list_name="Tėvynės sąjunga – Lietuvos krikščionys demokratai",
        list_candidates=16,
        list_mandates=2,
    ),
    group_header_row(
        municipality_rpg_id=ALYTUS_RPG_ID,
        municipality_number=ALYTUS_NUMBER,
        municipality_name=ALYTUS_NAME,
        mandates=ALYTUS_MANDATES,
        list_count=8,
        total_candidates=300,
        list_number=1,
        rpg_id=ALYTUS_RPG_ID,
        rorg_id="28236",
        list_name="Darbo partija",
        list_candidates=30,
        list_mandates=3,
    ),
)


def statiniai_url(rpg_id: str, rorg_id: str) -> str:
    return (
        f"{VRK_STATINIAI_BASE.rstrip('/')}{BASE_PATH}"
        f"/savKandidataiTarNarApygardoje_rpgId-{rpg_id}_rorgId-{rorg_id}.html"
    )


class ParseIntTests(unittest.TestCase):
    """`parse_int` degrades to None instead of aborting a 465-page build."""

    def test_reads_a_plain_count(self) -> None:
        self.assertEqual(parse_int("24"), 24)

    def test_strips_the_surrounding_whitespace_vrk_emits(self) -> None:
        # Every numeric cell in the real table is wrapped in newlines and
        # indentation, so this is the normal case, not an edge case.
        self.assertEqual(parse_int("\n                        42\n                    "), 42)

    def test_superscript_footnote_marker_returns_none(self) -> None:
        # This is the reason parse_int exists rather than a bare int() guarded
        # by str.isdigit(): the guard passes and the conversion still raises.
        self.assertTrue("²".isdigit())
        with self.assertRaises(ValueError):
            int("²")

        self.assertIsNone(parse_int("²"))

    def test_empty_and_missing_values_return_none(self) -> None:
        self.assertIsNone(parse_int(""))
        self.assertIsNone(parse_int("   "))
        self.assertIsNone(parse_int(None))

    def test_non_numeric_text_returns_none(self) -> None:
        self.assertIsNone(parse_int("-"))
        self.assertIsNone(parse_int("Nenurodė"))
        self.assertIsNone(parse_int("12 (II turas)"))


class ParseNumberedNameTests(unittest.TestCase):
    def test_splits_the_leading_ordinal_off_the_municipality_name(self) -> None:
        self.assertEqual(parse_numbered_name("1. Akmenės rajono"), (1, "Akmenės rajono"))
        self.assertEqual(parse_numbered_name("60. Zarasų rajono"), (60, "Zarasų rajono"))

    def test_collapses_the_whitespace_around_the_split(self) -> None:
        self.assertEqual(
            parse_numbered_name("\n  12.   Kauno   miesto \n"),
            (12, "Kauno miesto"),
        )

    def test_unnumbered_text_keeps_the_whole_string_as_the_name(self) -> None:
        self.assertEqual(parse_numbered_name("Akmenės rajono"), (None, "Akmenės rajono"))

    def test_empty_text_yields_no_number_and_no_name(self) -> None:
        self.assertEqual(parse_numbered_name("   "), (None, ""))


class MunicipalityFromCellTests(unittest.TestCase):
    @staticmethod
    def _cell(html: str):
        return BeautifulSoup(f"<table><tr>{html}</tr></table>", "lxml").find("td")

    def test_reads_id_number_and_name_from_a_group_header_cell(self) -> None:
        cell = self._cell(_municipality_cell(AKMENE_RPG_ID, AKMENE_NUMBER, AKMENE_NAME))

        self.assertEqual(
            municipality_from_cell(cell),
            {"id": AKMENE_RPG_ID, "number": AKMENE_NUMBER, "name": AKMENE_NAME},
        )

    def test_blank_continuation_cell_returns_none_so_the_caller_carries_forward(self) -> None:
        self.assertIsNone(municipality_from_cell(self._cell('<td align="left"></td>')))
        self.assertIsNone(municipality_from_cell(self._cell('<td align="left">\n  \n</td>')))

    def test_missing_cell_returns_none(self) -> None:
        self.assertIsNone(municipality_from_cell(None))

    def test_name_without_a_municipality_link_still_parses_but_has_no_id(self) -> None:
        # The empty id is what makes the carry-forward cross-check downgrade the
        # rows beneath such a header instead of silently mis-attributing them.
        cell = self._cell(f'<td align="left">{AKMENE_NUMBER}. {AKMENE_NAME}</td>')

        self.assertEqual(
            municipality_from_cell(cell),
            {"id": "", "number": AKMENE_NUMBER, "name": AKMENE_NAME},
        )

    def test_a_list_link_is_not_mistaken_for_a_municipality_link(self) -> None:
        # savKandidataiTarNarApygardoje also carries an rpgId, but it names the
        # list page, not the municipality page.
        cell = self._cell(
            '<td align="left">'
            f'<a href="{LIST_HREF.format(rpg=AKMENE_RPG_ID, rorg="28698")}">{AKMENE_NAME}</a>'
            "</td>"
        )

        self.assertEqual(municipality_from_cell(cell)["id"], "")


class IsElectedTests(unittest.TestCase):
    """VRK marks a winner by colouring the name blue inside the anchor."""

    @staticmethod
    def _anchor(html: str):
        return BeautifulSoup(html, "lxml").find("a")

    def test_blue_font_child_marks_an_elected_candidate(self) -> None:
        anchor = self._anchor('<a href="#"><font color="blue">Vardas PAVARDĖ</font></a>')

        self.assertTrue(is_elected(anchor))

    def test_blue_style_attribute_marks_an_elected_candidate(self) -> None:
        self.assertTrue(is_elected(self._anchor('<a href="#" style="color: blue">V P</a>')))
        self.assertTrue(is_elected(self._anchor('<a href="#" style="color:blue">V P</a>')))

    def test_plain_anchor_is_not_elected(self) -> None:
        self.assertFalse(is_elected(self._anchor('<a href="#">Vardas PAVARDĖ</a>')))

    def test_other_colours_are_not_elected(self) -> None:
        self.assertFalse(
            is_elected(self._anchor('<a href="#"><font color="red">Vardas PAVARDĖ</font></a>'))
        )
        self.assertFalse(is_elected(self._anchor('<a href="#" style="color: red">V P</a>')))

    def test_missing_anchor_is_not_elected(self) -> None:
        self.assertFalse(is_elected(None))


class ExtractListPageLinksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = extract_list_page_links(TWO_MUNICIPALITY_INDEX)

    def test_every_list_row_yields_one_entry(self) -> None:
        self.assertEqual(len(self.entries), 4)

    def test_group_header_row_carries_its_own_municipality(self) -> None:
        self.assertEqual(
            self.entries[0]["municipality"],
            {"id": AKMENE_RPG_ID, "number": AKMENE_NUMBER, "name": AKMENE_NAME},
        )
        self.assertTrue(self.entries[0]["municipalityCarryForwardOk"])

    def test_municipality_carries_forward_to_continuation_rows(self) -> None:
        # Rows 2 and 3 leave the municipality cell empty; without the
        # carry-forward they would lose the municipality entirely.
        for entry in self.entries[:3]:
            self.assertEqual(
                entry["municipality"],
                {"id": AKMENE_RPG_ID, "number": AKMENE_NUMBER, "name": AKMENE_NAME},
            )
            self.assertTrue(entry["municipalityCarryForwardOk"])

    def test_next_group_header_replaces_the_carried_municipality(self) -> None:
        self.assertEqual(
            self.entries[3]["municipality"],
            {"id": ALYTUS_RPG_ID, "number": ALYTUS_NUMBER, "name": ALYTUS_NAME},
        )

    def test_list_number_is_read_from_the_cell_before_the_anchor(self) -> None:
        # "Sąrašo numeris", not "Mandatų skaičius".
        self.assertEqual([entry["partyList"]["number"] for entry in self.entries], [2, 4, 6, 1])

    def test_group_header_list_number_is_not_the_municipality_mandate_count(self) -> None:
        # The regression this guards: reading the list number by scanning for
        # the first numeric cell works on continuation rows (where columns 1-3
        # are blank) and quietly returns the municipality's mandate count on
        # every group-header row.
        self.assertEqual(self.entries[0]["partyList"]["number"], 2)
        self.assertNotEqual(self.entries[0]["partyList"]["number"], AKMENE_MANDATES)
        self.assertEqual(self.entries[3]["partyList"]["number"], 1)
        self.assertNotEqual(self.entries[3]["partyList"]["number"], ALYTUS_MANDATES)

    def test_fixture_really_defeats_a_first_numeric_cell_scan(self) -> None:
        # Proves the assertion above discriminates: on the group-header row a
        # scan genuinely lands on the mandate count.
        soup = BeautifulSoup(TWO_MUNICIPALITY_INDEX, "lxml")
        header_row = next(
            row
            for row in table_rows(select_data_table(soup, "table2", LIST_LINK_MARKER))
            if municipality_from_cell(row.find("td")) is not None
        )
        scanned = next(
            parse_int(cell.get_text(" ", strip=True))
            for cell in header_row.find_all("td")
            if parse_int(cell.get_text(" ", strip=True)) is not None
        )

        self.assertEqual(scanned, AKMENE_MANDATES)

    def test_party_list_identity_comes_from_the_anchor(self) -> None:
        party_list = self.entries[0]["partyList"]

        self.assertEqual(party_list["id"], "28698")
        self.assertEqual(party_list["name"], "Lietuvos valstiečių ir žaliųjų sąjunga")

    def test_expected_candidates_is_the_per_list_count_not_the_per_municipality_one(self) -> None:
        # "Kandidatų skaičius sąraše" (42), not "Kandidatų skaičius sąrašuose"
        # (167). This count is the only thing that catches a truncated sample.
        self.assertEqual(
            [entry["expectedCandidates"] for entry in self.entries], [42, 50, 16, 30]
        )
        self.assertNotIn(AKMENE_TOTAL_CANDIDATES, [e["expectedCandidates"] for e in self.entries])

    def test_url_and_sample_name_are_derived_from_the_href(self) -> None:
        self.assertEqual(self.entries[0]["url"], statiniai_url(AKMENE_RPG_ID, "28698"))
        self.assertEqual(
            self.entries[0]["sampleName"], f"rpgId-{AKMENE_RPG_ID}_rorgId-28698.html"
        )

    def test_missing_table_yields_no_entries(self) -> None:
        self.assertEqual(extract_list_page_links("<html><body></body></html>"), [])


class ListPageLinkCarryForwardMismatchTests(unittest.TestCase):
    """The list URL names its own rpgId, so the carry-forward is checked.

    Without the check, one unparseable group-header cell would re-attribute
    every list beneath it to the previous municipality, with all counts intact
    and nothing to show for it.
    """

    def setUp(self) -> None:
        self.html = lists_index_html(
            group_header_row(
                municipality_rpg_id=AKMENE_RPG_ID,
                municipality_number=AKMENE_NUMBER,
                municipality_name=AKMENE_NAME,
                mandates=AKMENE_MANDATES,
                list_count=AKMENE_LIST_COUNT,
                total_candidates=AKMENE_TOTAL_CANDIDATES,
                list_number=2,
                rpg_id=AKMENE_RPG_ID,
                rorg_id="28698",
                list_name="Lietuvos valstiečių ir žaliųjų sąjunga",
                list_candidates=42,
                list_mandates=5,
            ),
            # A continuation row whose list page belongs to a different
            # municipality: the header cell for that group failed to parse.
            continuation_row(
                list_number=3,
                rpg_id=ALYTUS_RPG_ID,
                rorg_id="28368",
                list_name="Darbo partija",
                list_candidates=30,
                list_mandates=3,
            ),
        )
        self.entries = extract_list_page_links(self.html)

    def test_matching_row_is_flagged_ok(self) -> None:
        self.assertTrue(self.entries[0]["municipalityCarryForwardOk"])

    def test_contradicting_row_is_flagged_not_ok(self) -> None:
        self.assertFalse(self.entries[1]["municipalityCarryForwardOk"])

    def test_contradicting_row_does_not_inherit_the_wrong_municipality(self) -> None:
        # It falls back to the id the URL itself names, with the name and
        # number left blank rather than borrowed from the wrong group.
        self.assertEqual(
            self.entries[1]["municipality"],
            {"id": ALYTUS_RPG_ID, "number": None, "name": ""},
        )
        self.assertNotEqual(self.entries[1]["municipality"]["name"], AKMENE_NAME)

    def test_the_rest_of_the_row_is_still_extracted(self) -> None:
        # The mismatch is recorded, not fatal; build_sitemap still parses the
        # page and reports the mismatch under `skipped`.
        self.assertEqual(self.entries[1]["partyList"]["id"], "28368")
        self.assertEqual(self.entries[1]["partyList"]["number"], 3)
        self.assertEqual(self.entries[1]["expectedCandidates"], 30)
        self.assertEqual(self.entries[1]["url"], statiniai_url(ALYTUS_RPG_ID, "28368"))


class BuildCandidateIdTests(unittest.TestCase):
    """`<name-slug>-<vrkCandidateId>`, never a positional collision suffix."""

    def test_joins_the_name_slug_to_the_vrk_id(self) -> None:
        self.assertEqual(
            build_candidate_id("Vitalijus MITROFANOVAS", "2406746"),
            "vitalijus-mitrofanovas-2406746",
        )

    def test_lithuanian_diacritics_are_folded_to_ascii(self) -> None:
        self.assertEqual(
            build_candidate_id("Nerijus ČESIULIS", "2406286"), "nerijus-cesiulis-2406286"
        )
        self.assertEqual(
            build_candidate_id("Agnė ALEKSEJEVAITĖ", "2409490"), "agne-aleksejevaite-2409490"
        )

    def test_same_name_different_person_yields_different_ids(self) -> None:
        # The whole point of the VRK id suffix: hundreds of candidates share a
        # name slug, and a positional `-2` suffix would depend on traversal
        # order — which the batch runner uses as its resume marker.
        first = build_candidate_id("Mindaugas BALČIŪNAS", "2400001")
        second = build_candidate_id("Mindaugas BALČIŪNAS", "2400002")

        self.assertNotEqual(first, second)
        self.assertEqual(first.rsplit("-", 1)[0], second.rsplit("-", 1)[0])

    def test_empty_name_falls_back_to_the_vrk_id_alone(self) -> None:
        self.assertEqual(build_candidate_id("", "2406286"), "2406286")

    def test_unsluggable_name_falls_back_to_the_vrk_id_alone(self) -> None:
        # Nothing survives the ascii fold, so the slug is empty.
        self.assertEqual(build_candidate_id("–––", "2406286"), "2406286")

    def test_missing_vrk_id_falls_back_to_the_name_slug_alone(self) -> None:
        self.assertEqual(build_candidate_id("Nerijus ČESIULIS", ""), "nerijus-cesiulis")

    def test_both_missing_yields_an_empty_id(self) -> None:
        # build_sitemap never reaches this: it skips a record with no VRK id and
        # a record with no name before an id is built.
        self.assertEqual(build_candidate_id("", ""), "")


# Both wordings VRK has published for "this council candidate is also standing
# for mayor". 2019 says "tarybos narius - merus" because mayors were council
# members too under the rules of the time; 2023 says "savivaldybės merus".
MAYOR_MARKERS = {
    "2019": (
        MAYOR_MARKER_2019,
        "(kandidatas į savivaldybės tarybos narius - merus)",
        "(kandidatė į savivaldybės tarybos narius - merus)",
    ),
    "2023": (
        MAYOR_MARKER_2023,
        "(kandidatas į savivaldybės merus)",
        "(kandidatė į savivaldybės merus)",
    ),
}

# The wording actually observed in a VRK listing note, from the 2025 mayoral
# election where two candidates were struck off by a Seimas resolution.
STATUS_NOTE = "išbrauktas - Seimo nutarimu"


class ExtractCandidateNoteTests(unittest.TestCase):
    def test_mayoral_marker_is_not_a_status_note(self) -> None:
        # It is a role flag; the merge records it as a role instead, so letting
        # it through here would put it in candidateNote for every dual
        # candidate — 379 of them in 2019, 406 in 2023.
        for year, (pattern, masculine, feminine) in MAYOR_MARKERS.items():
            for marker in (masculine, feminine):
                with self.subTest(year=year, marker=marker):
                    self.assertEqual(
                        extract_candidate_note(f"Vardas PAVARDĖ {marker}", pattern), ""
                    )

    def test_marker_is_matched_case_and_whitespace_insensitively(self) -> None:
        for year, (pattern, masculine, _) in MAYOR_MARKERS.items():
            with self.subTest(year=year):
                shouted = masculine.upper()
                padded = masculine.replace(" ", "  ").replace("(", "( ").replace(")", " )")

                self.assertEqual(extract_candidate_note(f"Vardas PAVARDĖ {shouted}", pattern), "")
                self.assertEqual(extract_candidate_note(f"Vardas PAVARDĖ {padded}", pattern), "")

    def test_a_real_status_note_is_returned(self) -> None:
        for year, (pattern, _, _) in MAYOR_MARKERS.items():
            with self.subTest(year=year):
                self.assertEqual(
                    extract_candidate_note(f"Vardas PAVARDĖ ({STATUS_NOTE})", pattern),
                    STATUS_NOTE,
                )

    def test_note_whitespace_is_collapsed(self) -> None:
        pattern = MAYOR_MARKERS["2019"][0]

        self.assertEqual(
            extract_candidate_note("Vardas PAVARDĖ (\n  išbrauktas -   Seimo\nnutarimu )", pattern),
            STATUS_NOTE,
        )

    def test_plain_name_has_no_note(self) -> None:
        for year, (pattern, _, _) in MAYOR_MARKERS.items():
            with self.subTest(year=year):
                self.assertEqual(extract_candidate_note("Vardas PAVARDĖ", pattern), "")

    def test_note_must_close_at_the_end_of_the_name(self) -> None:
        pattern = MAYOR_MARKERS["2019"][0]

        self.assertEqual(extract_candidate_note("Vardas (X) PAVARDĖ", pattern), "")

    def test_each_election_needs_its_own_marker(self) -> None:
        # Cross-applying the patterns is the failure this parameterisation
        # exists to catch: the other election's marker does not match, so it is
        # not recognised as a role flag and lands in candidateNote instead.
        for year, (pattern, masculine, _) in MAYOR_MARKERS.items():
            other_year = "2023" if year == "2019" else "2019"
            other_marker = MAYOR_MARKERS[other_year][1]
            with self.subTest(pattern=year, marker=other_year):
                self.assertNotEqual(
                    extract_candidate_note(f"Vardas PAVARDĖ {other_marker}", pattern), ""
                )
                self.assertEqual(
                    extract_candidate_note(f"Vardas PAVARDĖ {other_marker}", pattern),
                    other_marker.strip("()"),
                )
                # And its own marker still is recognised.
                self.assertEqual(
                    extract_candidate_note(f"Vardas PAVARDĖ {masculine}", pattern), ""
                )

    def test_a_custom_marker_is_honoured(self) -> None:
        # The helper takes the pattern as an argument precisely so a module can
        # supply its own; a future rewording only needs a new constant.
        pattern = re.compile(r"\(\s*busimas meras\s*\)", flags=re.IGNORECASE)

        self.assertEqual(extract_candidate_note("Vardas PAVARDĖ (busimas meras)", pattern), "")
        self.assertEqual(
            extract_candidate_note(f"Vardas PAVARDĖ ({STATUS_NOTE})", pattern), STATUS_NOTE
        )


class CleanCandidateNameTests(unittest.TestCase):
    """The complement of extract_candidate_note: whatever the note took, goes."""

    def test_trailing_parenthetical_is_stripped(self) -> None:
        for year, (_, masculine, feminine) in MAYOR_MARKERS.items():
            for marker in (masculine, feminine):
                with self.subTest(year=year, marker=marker):
                    self.assertEqual(
                        clean_candidate_name(f"Vardas PAVARDĖ {marker}"), "Vardas PAVARDĖ"
                    )

    def test_status_note_is_stripped_too(self) -> None:
        self.assertEqual(
            clean_candidate_name(f"Vardas PAVARDĖ ({STATUS_NOTE})"), "Vardas PAVARDĖ"
        )

    def test_plain_name_is_only_whitespace_normalised(self) -> None:
        self.assertEqual(clean_candidate_name("\n Vardas   PAVARDĖ \n"), "Vardas PAVARDĖ")

    def test_mid_name_parenthetical_is_kept(self) -> None:
        self.assertEqual(clean_candidate_name("Vardas (X) PAVARDĖ"), "Vardas (X) PAVARDĖ")


if __name__ == "__main__":
    unittest.main()
