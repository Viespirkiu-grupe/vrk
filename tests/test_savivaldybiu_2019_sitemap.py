"""Sitemap tests for the 2019 municipal council + mayor elections.

Like 2023, this election publishes candidates in two structures that are not
supersets of one another — a single mayoral page and 465 party/coalition/
committee list pages — so the sitemap has to fetch both, merge them on VRK's
candidate id, and carry municipality names forward across rows where the cell is
blank. Every count pinned here reconciles with VRK's own savKandidataiSuvestine
totals, and the elected counts are cross-checked against the mandate columns
VRK publishes on savKandidataiSarasai.html.

The one thing that genuinely differs from 2023 is the prose flagging a candidate
who stands for both seats. 2019 says "(kandidatas į savivaldybės tarybos narius
- merus)" because mayors were elected off the council lists under the rules of
the time; 2023 says "(kandidatas į savivaldybės merus)". The 2023 pattern
matches *zero* 2019 rows, and because the sitemap only cross-checks the marker
against the id join rather than deriving roles from it, reusing the 2023 pattern
would not crash — it would quietly report 379 marker/join mismatches. That
regression is pinned explicitly below.
"""

import json
import re
import tempfile
import unittest
from collections import Counter
from functools import lru_cache
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.elections.savivaldybiu_2019.sitemap import (
    CANDIDATE_LINK_MARKER,
    ELECTION_ID,
    LIST_LINK_MARKER,
    MAYOR_MARKER_PATTERN,
    _extract_list_page_links,
    _is_elected,
    _municipality_from_cell,
    _parse_list_page,
    _parse_mayor_rows,
    _select_data_table,
    _table_rows,
    build_sitemap_from_sample,
)
from scraper.elections.savivaldybiu_2023.sitemap import (
    MAYOR_MARKER_PATTERN as MAYOR_MARKER_PATTERN_2023,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
LIST_SAMPLE_PATH = SAMPLES_ROOT / "list.html"
LISTS_INDEX_SAMPLE_PATH = SAMPLES_ROOT / "lists-index.html"
LISTS_SAMPLE_DIR = SAMPLES_ROOT / "lists"

# VRK's published totals for this election, used as ground truth throughout.
EXPECTED_STATS = {
    "rows": 14045,
    "extracted": 13666,
    "skipped": 0,
    "duplicate_candidate_ids": 0,
    "party_lists": 465,
    "mayoral_candidates": 410,
    "council_candidates": 13635,
    "dual_candidates": 379,
    "marker_join_mismatch": 0,
    "elected_mayors": 60,
    "elected_council_members": 1442,
}

MUNICIPALITY_COUNT = 60
MAYOR_ONLY_COUNT = 31
COUNCIL_ONLY_COUNT = 13256

# `-<vrkCandidateId>` rather than a positional `-2`/`-3` suffix, because the
# batch runner uses data/<candidateId>-<electionId>.json as its resume marker
# and 122 candidates share a name slug with someone else.
CANDIDATE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-\d+$")

# 2019 candidate pages are savKandidatasAnketa_rkndId-N.html — the `_2023`
# infix the later election added to the stem is not there yet.
CANDIDATE_URL_PATTERN = re.compile(
    r"^https://www\.vrk\.lt/statiniai/puslapiai/rinkimai/864/rnk1144/kandidatai"
    r"/savKandidatasAnketa_rkndId-\d+\.html$"
)

LIST_PAGE_ID_PATTERN = re.compile(r"rpgId-(\d+)_rorgId-(\d+)")


@lru_cache(maxsize=1)
def _load_council_records() -> tuple[dict, ...]:
    """Every council row of all 465 committed list pages, parsed once."""
    links = _extract_list_page_links(LISTS_INDEX_SAMPLE_PATH.read_text(encoding="utf-8"))
    records: list[dict] = []
    for link in links:
        html = (LISTS_SAMPLE_DIR / link["sampleName"]).read_text(encoding="utf-8")
        records.extend(_parse_list_page(html, link))
    return tuple(records)


@lru_cache(maxsize=1)
def _published_mandates() -> tuple[dict, dict]:
    """VRK's own mandate columns from savKandidataiSarasai.html.

    Both are headed "be merų"/"be mero" — the mayor's seat is counted
    separately from the council mandates, which is why an elected mayor is not
    marked as elected on his own party list. Returned as
    (per municipality id, per (municipality id, party list id)).
    """
    soup = BeautifulSoup(LISTS_INDEX_SAMPLE_PATH.read_text(encoding="utf-8"), "lxml")

    per_municipality: dict[str, int] = {}
    per_list: dict[tuple[str, str], int] = {}
    current_municipality_id = ""

    for row in _table_rows(_select_data_table(soup, "table2", LIST_LINK_MARKER)):
        cells = row.find_all("td")
        if not cells:
            continue

        municipality = _municipality_from_cell(cells[0])
        if municipality is not None:
            # "Mandatų skaičius (be merų)" sits beside the municipality name and
            # is filled only on the group-header row.
            current_municipality_id = municipality["id"]
            per_municipality[current_municipality_id] = int(
                cells[1].get_text(" ", strip=True)
            )

        list_anchor = next(
            (a for a in row.find_all("a", href=True) if LIST_LINK_MARKER in a["href"]),
            None,
        )
        if list_anchor is None:
            continue
        match = LIST_PAGE_ID_PATTERN.search(list_anchor["href"])
        if match is None:
            continue

        # "Gautų mandatų skaičius (be mero)" is the last cell of the list row.
        per_list[(match.group(1), match.group(2))] = int(cells[-1].get_text(" ", strip=True))

    return per_municipality, per_list


class Savivaldybiu2019SitemapTestBase(unittest.TestCase):
    """Builds the sitemap from the committed samples once for the whole class."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        output_path = Path(cls._tmp_dir.name) / "sitemap.json"

        cls.output_path, cls.stats = build_sitemap_from_sample(
            sample_path=LIST_SAMPLE_PATH,
            output_path=output_path,
        )
        cls.payload = json.loads(cls.output_path.read_text(encoding="utf-8"))
        cls.entries = cls.payload["entries"]
        cls.entries_by_vrk_id = {entry["vrkCandidateId"]: entry for entry in cls.entries}

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp_dir.cleanup()


class Savivaldybiu2019SitemapStatsTests(Savivaldybiu2019SitemapTestBase):
    def test_sitemap_is_written_to_the_requested_path(self) -> None:
        self.assertTrue(self.output_path.exists())
        self.assertEqual(self.payload["electionId"], ELECTION_ID)

    def test_stats_match_vrk_published_totals(self) -> None:
        self.assertEqual(self.stats, EXPECTED_STATS)

    def test_payload_stats_agree_with_returned_stats(self) -> None:
        self.assertEqual(
            self.payload["stats"],
            {
                "rows": EXPECTED_STATS["rows"],
                "extracted": EXPECTED_STATS["extracted"],
                "skipped": EXPECTED_STATS["skipped"],
                "duplicateCandidateIds": EXPECTED_STATS["duplicate_candidate_ids"],
                "partyLists": EXPECTED_STATS["party_lists"],
                "mayoralCandidates": EXPECTED_STATS["mayoral_candidates"],
                "councilCandidates": EXPECTED_STATS["council_candidates"],
                "dualCandidates": EXPECTED_STATS["dual_candidates"],
                "markerJoinMismatch": EXPECTED_STATS["marker_join_mismatch"],
                "electedMayors": EXPECTED_STATS["elected_mayors"],
                "electedCouncilMembers": EXPECTED_STATS["elected_council_members"],
            },
        )

    def test_nothing_is_skipped(self) -> None:
        self.assertEqual(self.payload["skipped"], [])

    def test_entry_count_matches_extracted_stat(self) -> None:
        self.assertEqual(len(self.entries), EXPECTED_STATS["extracted"])

    def test_union_of_both_structures_equals_published_total(self) -> None:
        # 410 mayoral + 13,635 council candidates with 379 people in both is
        # exactly the 13,666 VRK publishes; neither structure is a superset.
        union = (
            EXPECTED_STATS["mayoral_candidates"]
            + EXPECTED_STATS["council_candidates"]
            - EXPECTED_STATS["dual_candidates"]
        )
        self.assertEqual(union, EXPECTED_STATS["extracted"])

    def test_rows_stat_counts_both_structures(self) -> None:
        self.assertEqual(
            EXPECTED_STATS["mayoral_candidates"] + EXPECTED_STATS["council_candidates"],
            EXPECTED_STATS["rows"],
        )

    def test_source_url_is_the_2019_mayoral_listing(self) -> None:
        self.assertEqual(
            self.payload["sourceUrl"],
            "https://www.vrk.lt/2019-savivaldybiu-tarybu"
            "?srcUrl=/rinkimai/864/rnk1144/kandidatai/savKandidataiMerai.html",
        )


class Savivaldybiu2019SitemapMergeTests(Savivaldybiu2019SitemapTestBase):
    def test_role_combinations_partition_the_entries(self) -> None:
        role_counts = Counter(tuple(entry["roles"]) for entry in self.entries)

        self.assertEqual(
            role_counts,
            Counter(
                {
                    ("tarybos-narys",): COUNCIL_ONLY_COUNT,
                    ("tarybos-narys", "meras"): EXPECTED_STATS["dual_candidates"],
                    ("meras",): MAYOR_ONLY_COUNT,
                }
            ),
        )

    def test_dual_candidate_has_both_candidacies_under_one_entry(self) -> None:
        # Gediminas DAUKŠYS headed a committee list in Alytus, won his council
        # seat, and lost the mayoral runoff — the two candidacies must land on
        # one entry with one id, joined on rkndId-2408494.
        entry = self.entries_by_vrk_id["2408494"]

        self.assertEqual(entry["candidateId"], "gediminas-dauksys-2408494")
        self.assertEqual(entry["roles"], ["tarybos-narys", "meras"])
        self.assertEqual(entry["municipality"]["name"], "Alytaus miesto")
        self.assertEqual(
            entry["councilCandidacy"]["partyList"]["name"],
            "Visuomeninis rinkimų komitetas „Už Alytų“",
        )
        self.assertEqual(entry["councilCandidacy"]["listPosition"], 1)
        self.assertTrue(entry["councilCandidacy"]["elected"])
        self.assertEqual(entry["mayoralCandidacy"]["round"], "II")
        self.assertEqual(
            entry["mayoralCandidacy"]["nominatedBy"],
            "Visuomeninis rinkimų komitetas „Už Alytų“",
        )
        self.assertFalse(entry["mayoralCandidacy"]["elected"])

    def test_dual_candidates_appear_exactly_once_each(self) -> None:
        dual_entries = [entry for entry in self.entries if len(entry["roles"]) > 1]

        self.assertEqual(len(dual_entries), EXPECTED_STATS["dual_candidates"])
        self.assertEqual(
            len({entry["candidateId"] for entry in dual_entries}),
            EXPECTED_STATS["dual_candidates"],
        )
        for entry in dual_entries:
            self.assertIn("councilCandidacy", entry)
            self.assertIn("mayoralCandidacy", entry)

    def test_dual_candidate_elected_as_mayor_in_round_two(self) -> None:
        entry = self.entries_by_vrk_id["2406286"]

        self.assertEqual(entry["candidateId"], "nerijus-cesiulis-2406286")
        self.assertEqual(entry["mayoralCandidacy"]["round"], "II")
        self.assertTrue(entry["mayoralCandidacy"]["elected"])
        # Not "elected" on the council list, and that is what VRK's page says:
        # its mandate columns are headed "be merų", so a winning mayor's list
        # row is left un-highlighted even though his post-election position is 1.
        self.assertEqual(entry["councilCandidacy"]["postElectionPosition"], 1)
        self.assertFalse(entry["councilCandidacy"]["elected"])

    def test_dual_candidate_elected_as_mayor_in_round_one(self) -> None:
        entry = self.entries_by_vrk_id["2406746"]

        self.assertEqual(entry["candidateId"], "vitalijus-mitrofanovas-2406746")
        self.assertEqual(entry["mayoralCandidacy"]["round"], "I")
        self.assertTrue(entry["mayoralCandidacy"]["elected"])
        self.assertEqual(entry["municipality"]["name"], "Akmenės rajono")

    def test_dual_candidate_on_a_coalition_list(self) -> None:
        entry = self.entries_by_vrk_id["2404239"]

        self.assertEqual(entry["candidateId"], "vytas-jareckas-2404239")
        self.assertEqual(entry["roles"], ["tarybos-narys", "meras"])
        self.assertEqual(
            entry["councilCandidacy"]["partyList"]["name"],
            "VYTO JARECKO koalicija „VIENINGI BIRŽAI“ "
            "(Lietuvos valstiečių ir žaliųjų sąjunga, "
            "Lietuvos Respublikos liberalų sąjūdis)",
        )
        # The coalition is the list; the mayoral nomination is by one of its
        # member parties, so the two fields legitimately disagree.
        self.assertEqual(
            entry["mayoralCandidacy"]["nominatedBy"],
            "Lietuvos valstiečių ir žaliųjų sąjunga",
        )
        self.assertTrue(entry["mayoralCandidacy"]["elected"])

    def test_mayor_only_candidates_have_no_council_candidacy(self) -> None:
        mayor_only = [entry for entry in self.entries if "councilCandidacy" not in entry]

        self.assertEqual(len(mayor_only), MAYOR_ONLY_COUNT)
        for entry in mayor_only:
            self.assertEqual(entry["roles"], ["meras"])
            self.assertIn("mayoralCandidacy", entry)

    def test_named_mayor_only_candidates_are_present(self) -> None:
        mayor_only_ids = {
            entry["candidateId"] for entry in self.entries if "councilCandidacy" not in entry
        }

        # Party-nominated but on no council list, and self-nominated.
        self.assertIn("ricardas-juska-2413847", mayor_only_ids)
        self.assertIn("skirmantas-mockevicius-2400117", mayor_only_ids)

    def test_self_nominated_mayor_only_candidate_won(self) -> None:
        entry = self.entries_by_vrk_id["2400117"]

        self.assertEqual(entry["candidateId"], "skirmantas-mockevicius-2400117")
        self.assertEqual(entry["roles"], ["meras"])
        self.assertNotIn("councilCandidacy", entry)
        self.assertEqual(entry["mayoralCandidacy"]["nominatedBy"], "išsikėlė pats")
        self.assertEqual(entry["mayoralCandidacy"]["round"], "II")
        self.assertTrue(entry["mayoralCandidacy"]["elected"])

    def test_council_only_candidates_have_no_mayoral_candidacy(self) -> None:
        council_only = [entry for entry in self.entries if "mayoralCandidacy" not in entry]

        self.assertEqual(len(council_only), COUNCIL_ONLY_COUNT)
        for entry in council_only:
            self.assertEqual(entry["roles"], ["tarybos-narys"])
            self.assertIn("councilCandidacy", entry)

    def test_council_only_entry_keeps_its_coalition_list(self) -> None:
        entry = self.entries_by_vrk_id["2404237"]

        self.assertEqual(entry["candidateId"], "kestutis-armonas-2404237")
        self.assertNotIn("mayoralCandidacy", entry)
        self.assertEqual(
            entry["councilCandidacy"]["partyList"]["name"],
            "VYTO JARECKO koalicija „VIENINGI BIRŽAI“ "
            "(Lietuvos valstiečių ir žaliųjų sąjunga, "
            "Lietuvos Respublikos liberalų sąjūdis)",
        )
        self.assertTrue(entry["councilCandidacy"]["elected"])

    def test_council_candidacy_positions_are_populated(self) -> None:
        # One and only one council row leaves "Porinkiminis eilės numeris"
        # blank in the source HTML (Gytis ŠULINSKAS, Raseiniai, list 1); every
        # other row on all 465 pages carries both numbers.
        missing_post = [
            entry["candidateId"]
            for entry in self.entries
            if "councilCandidacy" in entry
            and entry["councilCandidacy"]["postElectionPosition"] is None
        ]
        missing_list = [
            entry["candidateId"]
            for entry in self.entries
            if "councilCandidacy" in entry and entry["councilCandidacy"]["listPosition"] is None
        ]

        self.assertEqual(missing_post, ["gytis-sulinskas-2410995"])
        self.assertEqual(missing_list, [])

    def test_mayoral_candidacy_fields_are_populated(self) -> None:
        for entry in self.entries:
            candidacy = entry.get("mayoralCandidacy")
            if candidacy is None:
                continue
            self.assertIn(candidacy["round"], {"I", "II"}, msg=entry["candidateId"])
            self.assertTrue(candidacy["nominatedBy"], msg=entry["candidateId"])


class Savivaldybiu2019SitemapCandidateIdTests(Savivaldybiu2019SitemapTestBase):
    def test_all_candidate_ids_are_unique(self) -> None:
        candidate_ids = [entry["candidateId"] for entry in self.entries]

        self.assertEqual(len(set(candidate_ids)), EXPECTED_STATS["extracted"])
        self.assertEqual(self.stats["duplicate_candidate_ids"], 0)

    def test_all_vrk_candidate_ids_are_unique(self) -> None:
        # One entry per person is the whole point of the merge.
        vrk_ids = [entry["vrkCandidateId"] for entry in self.entries]

        self.assertEqual(len(set(vrk_ids)), EXPECTED_STATS["extracted"])

    def test_candidate_id_is_name_slug_plus_vrk_candidate_id(self) -> None:
        for entry in self.entries:
            candidate_id = entry["candidateId"]
            self.assertRegex(candidate_id, CANDIDATE_ID_PATTERN)
            self.assertTrue(
                candidate_id.endswith(f"-{entry['vrkCandidateId']}"),
                msg=f"{candidate_id} does not end with -{entry['vrkCandidateId']}",
            )

    def test_candidate_ids_carry_no_positional_suffix(self) -> None:
        # A `-2`/`-3` collision suffix would be traversal-order dependent, and
        # the batch runner uses the id as its resume marker.
        name_slugs = [entry["candidateId"].rsplit("-", 1)[0] for entry in self.entries]
        colliding_slugs = {slug for slug, count in Counter(name_slugs).items() if count > 1}

        self.assertTrue(colliding_slugs, "expected shared name slugs in this corpus")
        for entry in self.entries:
            self.assertFalse(re.search(r"-\d+-\d+$", entry["candidateId"]))

    def test_candidate_url_contains_the_vrk_candidate_id(self) -> None:
        for entry in self.entries:
            self.assertIn(f"rkndId-{entry['vrkCandidateId']}", entry["url"])

    def test_candidate_urls_use_the_2019_page_stem(self) -> None:
        # savKandidatasAnketa_rkndId-N.html — no `_2023` infix, no `?srcUrl=`
        # wrapper left unresolved.
        for entry in self.entries:
            self.assertRegex(entry["url"], CANDIDATE_URL_PATTERN)


class Savivaldybiu2019SitemapMunicipalityTests(Savivaldybiu2019SitemapTestBase):
    def test_every_entry_has_a_fully_populated_municipality(self) -> None:
        for entry in self.entries:
            municipality = entry["municipality"]
            self.assertIsNotNone(municipality, msg=entry["candidateId"])
            self.assertTrue(municipality["id"], msg=entry["candidateId"])
            self.assertIsNotNone(municipality["number"], msg=entry["candidateId"])
            self.assertTrue(municipality["name"], msg=entry["candidateId"])

    def test_all_sixty_municipalities_are_covered(self) -> None:
        municipalities = {
            (
                entry["municipality"]["id"],
                entry["municipality"]["number"],
                entry["municipality"]["name"],
            )
            for entry in self.entries
        }

        self.assertEqual(len(municipalities), MUNICIPALITY_COUNT)
        self.assertEqual(
            sorted(number for _, number, _ in municipalities),
            list(range(1, MUNICIPALITY_COUNT + 1)),
        )
        # id, number and name agree one-to-one: a carry-forward that pasted the
        # wrong name onto a municipality would collapse one of these sets.
        self.assertEqual(len({id_ for id_, _, _ in municipalities}), MUNICIPALITY_COUNT)
        self.assertEqual(len({name for _, _, name in municipalities}), MUNICIPALITY_COUNT)

    def test_mayoral_listing_relies_on_municipality_carry_forward(self) -> None:
        # Only the first row of each municipality group fills the cell; the
        # remaining 350 mayoral rows would lose their municipality without the
        # carry-forward, so this pins that the fixture really exercises it.
        soup = BeautifulSoup(LIST_SAMPLE_PATH.read_text(encoding="utf-8"), "lxml")
        rows = _table_rows(_select_data_table(soup, "table2", CANDIDATE_LINK_MARKER))
        filled = [
            row
            for row in rows
            if row.find_all("td")
            and _municipality_from_cell(row.find_all("td")[0]) is not None
        ]

        self.assertEqual(len(filled), MUNICIPALITY_COUNT)
        self.assertGreater(len(rows), MUNICIPALITY_COUNT)

    def test_lists_index_relies_on_municipality_carry_forward(self) -> None:
        soup = BeautifulSoup(LISTS_INDEX_SAMPLE_PATH.read_text(encoding="utf-8"), "lxml")
        rows = _table_rows(_select_data_table(soup, "table2", LIST_LINK_MARKER))
        filled = [
            row
            for row in rows
            if row.find_all("td")
            and _municipality_from_cell(row.find_all("td")[0]) is not None
        ]

        self.assertEqual(len(filled), MUNICIPALITY_COUNT)
        self.assertGreater(len(rows), MUNICIPALITY_COUNT)

    def test_every_party_list_link_carries_a_municipality(self) -> None:
        links = _extract_list_page_links(
            LISTS_INDEX_SAMPLE_PATH.read_text(encoding="utf-8")
        )

        self.assertEqual(len(links), EXPECTED_STATS["party_lists"])
        self.assertEqual(len({link["municipality"]["id"] for link in links}), MUNICIPALITY_COUNT)
        for link in links:
            self.assertTrue(link["municipality"]["id"])
            self.assertIsNotNone(link["municipality"]["number"])
            self.assertTrue(link["municipality"]["name"])
            # The list URL names its own rpgId, so the carry-forward is checked
            # against it rather than trusted.
            self.assertTrue(link["municipalityCarryForwardOk"], msg=link["sampleName"])

    def test_every_party_list_page_sample_is_committed(self) -> None:
        links = _extract_list_page_links(
            LISTS_INDEX_SAMPLE_PATH.read_text(encoding="utf-8")
        )
        missing = [
            link["sampleName"]
            for link in links
            if not (LISTS_SAMPLE_DIR / link["sampleName"]).exists()
        ]

        self.assertEqual(missing, [])

    def test_published_candidate_counts_per_list_sum_to_the_council_total(self) -> None:
        # "Kandidatų skaičius sąraše" summed over all 465 lists is VRK's own
        # statement of how many council candidates there are; it catches a
        # truncated list-page sample that would otherwise parse cleanly.
        links = _extract_list_page_links(
            LISTS_INDEX_SAMPLE_PATH.read_text(encoding="utf-8")
        )

        self.assertEqual(
            sum(link["expectedCandidates"] for link in links),
            EXPECTED_STATS["council_candidates"],
        )


class Savivaldybiu2019MayorMarkerTests(Savivaldybiu2019SitemapTestBase):
    """The `(kandidatas/kandidatė į savivaldybės tarybos narius - merus)` marker.

    2019 mayors were elected off the council lists, so the marker names both
    seats — the wording 2023 dropped. Both gender inflections are published, and
    a pattern that covered only one would silently see 292 of the 379 dual
    candidacies.
    """

    MASCULINE_MARKER = "(kandidatas į savivaldybės tarybos narius - merus)"
    FEMININE_MARKER = "(kandidatė į savivaldybės tarybos narius - merus)"
    MASCULINE_COUNT = 292
    FEMININE_COUNT = 87

    # The wording 2023 uses, which must not be confused with the 2019 one.
    MARKER_2023 = "(kandidatas į savivaldybės merus)"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.council_records = _load_council_records()

    def test_pattern_matches_both_published_spellings(self) -> None:
        self.assertRegex(self.MASCULINE_MARKER, MAYOR_MARKER_PATTERN)
        self.assertRegex(self.FEMININE_MARKER, MAYOR_MARKER_PATTERN)

    def test_both_spellings_occur_in_the_corpus(self) -> None:
        spellings: Counter[str] = Counter()
        for path in sorted(LISTS_SAMPLE_DIR.glob("rpgId-*_rorgId-*.html")):
            html = path.read_text(encoding="utf-8")
            for match in MAYOR_MARKER_PATTERN.finditer(html):
                spellings[" ".join(match.group(0).split())] += 1

        self.assertEqual(
            spellings,
            Counter(
                {
                    self.MASCULINE_MARKER: self.MASCULINE_COUNT,
                    self.FEMININE_MARKER: self.FEMININE_COUNT,
                }
            ),
        )
        self.assertEqual(sum(spellings.values()), EXPECTED_STATS["dual_candidates"])

    def test_the_2023_pattern_matches_no_2019_row(self) -> None:
        # THE regression this module exists to prevent. Copying the 2023 pattern
        # does not crash — it flags nobody, and the sitemap then reports 379
        # marker/join mismatches instead of 0.
        mayors_html = LIST_SAMPLE_PATH.read_text(encoding="utf-8")
        matches_2023 = len(MAYOR_MARKER_PATTERN_2023.findall(mayors_html))
        matches_2019 = len(MAYOR_MARKER_PATTERN.findall(mayors_html))
        for path in sorted(LISTS_SAMPLE_DIR.glob("rpgId-*_rorgId-*.html")):
            html = path.read_text(encoding="utf-8")
            matches_2023 += len(MAYOR_MARKER_PATTERN_2023.findall(html))
            matches_2019 += len(MAYOR_MARKER_PATTERN.findall(html))

        self.assertEqual(matches_2023, 0)
        self.assertEqual(matches_2019, EXPECTED_STATS["dual_candidates"])

    def test_the_two_election_patterns_are_disjoint(self) -> None:
        self.assertNotRegex(self.MASCULINE_MARKER, MAYOR_MARKER_PATTERN_2023)
        self.assertNotRegex(self.FEMININE_MARKER, MAYOR_MARKER_PATTERN_2023)
        self.assertNotRegex(self.MARKER_2023, MAYOR_MARKER_PATTERN)
        self.assertRegex(self.MARKER_2023, MAYOR_MARKER_PATTERN_2023)

    def test_the_marker_lives_only_on_the_council_lists(self) -> None:
        # The mayoral listing states the role by being the mayoral listing, so
        # it carries no marker at all; the flag can only come from list rows.
        mayors_html = LIST_SAMPLE_PATH.read_text(encoding="utf-8")

        self.assertEqual(MAYOR_MARKER_PATTERN.findall(mayors_html), [])
        for record in _parse_mayor_rows(mayors_html):
            self.assertEqual(record["candidateNote"], "")

    def test_exactly_379_council_rows_carry_the_marker(self) -> None:
        marked = [record for record in self.council_records if record["alsoMayoralCandidate"]]

        self.assertEqual(len(marked), EXPECTED_STATS["dual_candidates"])

    def test_marked_council_rows_are_exactly_the_dual_candidates(self) -> None:
        marked_ids = {
            record["vrkCandidateId"]
            for record in self.council_records
            if record["alsoMayoralCandidate"]
        }
        dual_ids = {
            entry["vrkCandidateId"] for entry in self.entries if len(entry["roles"]) > 1
        }

        self.assertEqual(marked_ids, dual_ids)

    def test_marked_council_rows_are_exactly_the_two_way_intersection(self) -> None:
        mayor_ids = {
            record["vrkCandidateId"]
            for record in _parse_mayor_rows(LIST_SAMPLE_PATH.read_text(encoding="utf-8"))
        }
        council_ids = {record["vrkCandidateId"] for record in self.council_records}
        marked_ids = {
            record["vrkCandidateId"]
            for record in self.council_records
            if record["alsoMayoralCandidate"]
        }

        self.assertEqual(marked_ids, mayor_ids & council_ids)
        self.assertEqual(len(mayor_ids - council_ids), MAYOR_ONLY_COUNT)

    def test_marker_is_stripped_from_the_candidate_name(self) -> None:
        for record in self.council_records:
            if not record["alsoMayoralCandidate"]:
                continue
            self.assertNotIn("merus", record["candidateName"])
            self.assertNotIn("(", record["candidateName"])
            # The marker is a role flag, not a status note.
            self.assertEqual(record["candidateNote"], "")

    def test_no_entry_carries_a_candidate_note(self) -> None:
        # 2019 publishes no struck-off or withdrawn notes; if the marker ever
        # leaked into candidateNote this would be 379 instead of 0.
        self.assertEqual(
            Counter(entry["candidateNote"] for entry in self.entries),
            Counter({"": EXPECTED_STATS["extracted"]}),
        )


class Savivaldybiu2019ElectedFlagTests(Savivaldybiu2019SitemapTestBase):
    def test_elected_is_read_from_a_blue_font_tag(self) -> None:
        elected_anchor = BeautifulSoup(
            '<a href="#"><font color="blue">Vardas PAVARDĖ</font></a>', "lxml"
        ).find("a")
        plain_anchor = BeautifulSoup('<a href="#">Vardas PAVARDĖ</a>', "lxml").find("a")

        self.assertTrue(_is_elected(elected_anchor))
        self.assertFalse(_is_elected(plain_anchor))

    def test_mayoral_listing_has_sixty_blue_font_anchors(self) -> None:
        soup = BeautifulSoup(LIST_SAMPLE_PATH.read_text(encoding="utf-8"), "lxml")
        anchors = soup.select(f"a[href*='{CANDIDATE_LINK_MARKER}']")
        blue = [
            anchor for anchor in anchors if anchor.find("font", attrs={"color": "blue"}) is not None
        ]

        self.assertEqual(len(anchors), EXPECTED_STATS["mayoral_candidates"])
        self.assertEqual(len(blue), EXPECTED_STATS["elected_mayors"])

    def test_sixty_mayors_are_elected_one_per_municipality(self) -> None:
        elected = [
            entry for entry in self.entries if entry.get("mayoralCandidacy", {}).get("elected")
        ]

        self.assertEqual(len(elected), EXPECTED_STATS["elected_mayors"])
        self.assertEqual(
            len({entry["municipality"]["id"] for entry in elected}),
            MUNICIPALITY_COUNT,
        )

    def test_elected_mayors_split_across_both_rounds(self) -> None:
        rounds = Counter(
            entry["mayoralCandidacy"]["round"]
            for entry in self.entries
            if entry.get("mayoralCandidacy", {}).get("elected")
        )

        self.assertEqual(rounds, Counter({"I": 19, "II": 41}))

    def test_council_elected_total(self) -> None:
        elected = [
            entry for entry in self.entries if entry.get("councilCandidacy", {}).get("elected")
        ]

        self.assertEqual(len(elected), EXPECTED_STATS["elected_council_members"])

    def test_council_elected_total_matches_vrk_published_mandates(self) -> None:
        # Independent ground truth: "Mandatų skaičius (be merų)" summed over the
        # 60 municipality group rows of savKandidataiSarasai.html.
        per_municipality, _ = _published_mandates()

        self.assertEqual(len(per_municipality), MUNICIPALITY_COUNT)
        self.assertEqual(
            sum(per_municipality.values()), EXPECTED_STATS["elected_council_members"]
        )

    def test_blue_font_council_rows_match_the_per_list_mandate_column(self) -> None:
        # Every one of the 465 lists must produce exactly the "Gautų mandatų
        # skaičius (be mero)" VRK publishes for it. A whole-corpus total can hide
        # two compensating errors; this cannot.
        _, per_list = _published_mandates()
        elected_per_list: Counter[tuple[str, str]] = Counter()
        for record in _load_council_records():
            key = (record["municipality"]["id"], record["partyList"]["id"])
            elected_per_list[key] += 1 if record["elected"] else 0

        self.assertEqual(len(per_list), EXPECTED_STATS["party_lists"])
        mismatched = {
            key: (expected, elected_per_list[key])
            for key, expected in per_list.items()
            if elected_per_list[key] != expected
        }

        self.assertEqual(mismatched, {})
        self.assertEqual(
            sum(elected_per_list.values()), EXPECTED_STATS["elected_council_members"]
        )

    def test_an_elected_mayor_takes_no_council_mandate(self) -> None:
        # The mandate columns are counted "be merų", so nobody is flagged
        # elected on both sides. This is VRK's arithmetic, not a merge bug:
        # 1,442 council mandates + 60 mayors are disjoint sets.
        both = [
            entry
            for entry in self.entries
            if entry.get("mayoralCandidacy", {}).get("elected")
            and entry.get("councilCandidacy", {}).get("elected")
        ]

        self.assertEqual(both, [])

    def test_winning_mayor_tops_his_list_without_being_flagged_elected(self) -> None:
        entry = self.entries_by_vrk_id["2404239"]

        self.assertEqual(entry["candidateId"], "vytas-jareckas-2404239")
        self.assertTrue(entry["mayoralCandidacy"]["elected"])
        self.assertEqual(entry["councilCandidacy"]["postElectionPosition"], 1)
        self.assertFalse(entry["councilCandidacy"]["elected"])

    def test_elected_council_member_carries_a_post_election_position(self) -> None:
        entry = self.entries_by_vrk_id["2409466"]

        self.assertEqual(entry["candidateId"], "judita-ziliene-2409466")
        self.assertTrue(entry["councilCandidacy"]["elected"])
        self.assertEqual(entry["councilCandidacy"]["listPosition"], 4)
        self.assertEqual(entry["councilCandidacy"]["postElectionPosition"], 2)

    def test_not_elected_council_candidate_is_flagged_false(self) -> None:
        entry = self.entries_by_vrk_id["2409490"]

        self.assertEqual(entry["candidateId"], "agne-aleksejevaite-2409490")
        self.assertFalse(entry["councilCandidacy"]["elected"])
        self.assertEqual(entry["councilCandidacy"]["postElectionPosition"], 6)

    def test_losing_mayoral_candidate_is_flagged_false(self) -> None:
        entry = self.entries_by_vrk_id["2413847"]

        self.assertEqual(entry["candidateId"], "ricardas-juska-2413847")
        self.assertFalse(entry["mayoralCandidacy"]["elected"])
        self.assertEqual(entry["mayoralCandidacy"]["round"], "II")


class Savivaldybiu2019SitemapFixtureCoverageTests(Savivaldybiu2019SitemapTestBase):
    FIXTURE_CANDIDATE_IDS = {
        "agne-aleksejevaite-2409490",
        "gintas-orda-2400958",
        "gediminas-dauksys-2408494",
        "judita-ziliene-2409466",
        "kestutis-armonas-2404237",
        "nerijus-cesiulis-2406286",
        "ricardas-juska-2413847",
        "skirmantas-mockevicius-2400117",
        "vitalijus-mitrofanovas-2406746",
        "vytas-jareckas-2404239",
    }

    def test_every_committed_candidate_fixture_is_in_the_sitemap(self) -> None:
        candidate_ids = {entry["candidateId"] for entry in self.entries}

        self.assertTrue(self.FIXTURE_CANDIDATE_IDS <= candidate_ids)

    def test_committed_candidate_fixture_dirs_match_sitemap_ids(self) -> None:
        fixture_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        fixture_dirs.discard("lists")

        self.assertEqual(fixture_dirs, self.FIXTURE_CANDIDATE_IDS)

    def test_fixtures_cover_every_role_combination(self) -> None:
        roles = {
            tuple(entry["roles"])
            for entry in self.entries
            if entry["candidateId"] in self.FIXTURE_CANDIDATE_IDS
        }

        self.assertEqual(
            roles,
            {("tarybos-narys",), ("tarybos-narys", "meras"), ("meras",)},
        )


if __name__ == "__main__":
    unittest.main()
