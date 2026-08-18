"""Sitemap tests for the 2023 municipal council + mayor elections.

This is the only election that publishes candidates in two structures that are
not supersets of one another — a single mayoral page and 467 party-list pages —
so the sitemap has to fetch both, merge them on VRK's candidate id, and carry
municipality names forward across rows where the cell is blank. Every count
pinned here was cross-checked against VRK's own savKandidataiSuvestine totals.
"""

import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.elections.savivaldybiu_2023 import sitemap as sitemap_module
from scraper.elections.savivaldybiu_2023.sitemap import (
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


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
LIST_SAMPLE_PATH = SAMPLES_ROOT / "list.html"
LISTS_INDEX_SAMPLE_PATH = SAMPLES_ROOT / "lists-index.html"
LISTS_SAMPLE_DIR = SAMPLES_ROOT / "lists"

# VRK's published totals for this election, used as ground truth throughout.
EXPECTED_STATS = {
    "rows": 14202,
    "extracted": 13796,
    "skipped": 0,
    "duplicate_candidate_ids": 0,
    "party_lists": 467,
    "mayoral_candidates": 433,
    "council_candidates": 13769,
    "dual_candidates": 406,
    "marker_join_mismatch": 0,
    "elected_mayors": 60,
    "elected_council_members": 1498,
}

MUNICIPALITY_COUNT = 60
MAYOR_ONLY_COUNT = 27
COUNCIL_ONLY_COUNT = 13363

# `-<vrkCandidateId>` rather than a positional `-2`/`-3` suffix, because the
# batch runner uses data/<candidateId>-<electionId>.json as its resume marker
# and 244 candidates share a name slug with someone else.
CANDIDATE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-\d+$")


class Savivaldybiu2023SitemapTestBase(unittest.TestCase):
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


class Savivaldybiu2023SitemapStatsTests(Savivaldybiu2023SitemapTestBase):
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
        # 433 mayoral + 13,769 council candidates with 406 people in both is
        # exactly the 13,796 VRK publishes; neither structure is a superset.
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


class Savivaldybiu2023SitemapMergeTests(Savivaldybiu2023SitemapTestBase):
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
        # Algirdas ŽEBRAUSKAS stood on a coalition list in Telšiai and was
        # elected to the council while self-nominating for mayor.
        entry = self.entries_by_vrk_id["2424292"]

        self.assertEqual(entry["candidateId"], "algirdas-zebrauskas-2424292")
        self.assertEqual(entry["roles"], ["tarybos-narys", "meras"])
        self.assertEqual(entry["municipality"]["name"], "Telšių rajono")
        self.assertTrue(entry["councilCandidacy"]["elected"])
        self.assertEqual(entry["councilCandidacy"]["listPosition"], 1)
        self.assertFalse(entry["mayoralCandidacy"]["elected"])
        self.assertEqual(entry["mayoralCandidacy"]["nominatedBy"], "išsikėlė pats")

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
        entry = self.entries_by_vrk_id["2423015"]

        self.assertEqual(entry["candidateId"], "rasa-vitkauskiene-2423015")
        self.assertEqual(entry["mayoralCandidacy"]["round"], "II")
        self.assertTrue(entry["mayoralCandidacy"]["elected"])
        # Elected mayor, but not elected off the council list.
        self.assertFalse(entry["councilCandidacy"]["elected"])

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

        # Both self-nominated and on no party list at all.
        self.assertIn("mykolas-majauskas-2420485", mayor_only_ids)
        self.assertIn("skirmantas-mockevicius-2422343", mayor_only_ids)

    def test_council_only_candidates_have_no_mayoral_candidacy(self) -> None:
        council_only = [entry for entry in self.entries if "mayoralCandidacy" not in entry]

        self.assertEqual(len(council_only), COUNCIL_ONLY_COUNT)
        for entry in council_only:
            self.assertEqual(entry["roles"], ["tarybos-narys"])
            self.assertIn("councilCandidacy", entry)

    def test_council_only_entry_keeps_its_party_list(self) -> None:
        entry = self.entries_by_vrk_id["2421676"]

        self.assertEqual(entry["candidateId"], "linas-urmanavicius-2421676")
        self.assertNotIn("mayoralCandidacy", entry)
        self.assertEqual(
            entry["councilCandidacy"]["partyList"]["name"],
            "Politinis komitetas „Už Druskininkus“",
        )
        self.assertTrue(entry["councilCandidacy"]["elected"])


class Savivaldybiu2023SitemapCandidateIdTests(Savivaldybiu2023SitemapTestBase):
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


class Savivaldybiu2023SitemapMunicipalityTests(Savivaldybiu2023SitemapTestBase):
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

    def test_mayoral_listing_relies_on_municipality_carry_forward(self) -> None:
        # Only the first row of each municipality group fills the cell; the
        # remaining 373 mayoral rows would lose their municipality without the
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


class Savivaldybiu2023MayorMarkerTests(Savivaldybiu2023SitemapTestBase):
    """The `(kandidatas/kandidatė į savivaldybės merus)` marker on list rows.

    Both spellings are published. A character class that covers only `ė` sees
    105 of the 406 dual candidacies and silently drops the other 301, so the
    per-spelling counts are pinned separately.
    """

    MASCULINE_MARKER = "(kandidatas į savivaldybės merus)"
    FEMININE_MARKER = "(kandidatė į savivaldybės merus)"
    MASCULINE_COUNT = 301
    FEMININE_COUNT = 105

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        links = _extract_list_page_links(
            LISTS_INDEX_SAMPLE_PATH.read_text(encoding="utf-8")
        )
        cls.council_records = []
        for link in links:
            html = (LISTS_SAMPLE_DIR / link["sampleName"]).read_text(encoding="utf-8")
            cls.council_records.extend(_parse_list_page(html, link))

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

    def test_exactly_406_council_rows_carry_the_marker(self) -> None:
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

    def test_marker_is_stripped_from_the_candidate_name(self) -> None:
        for record in self.council_records:
            if not record["alsoMayoralCandidate"]:
                continue
            self.assertNotIn("merus", record["candidateName"])
            # The marker is a role flag, not a status note.
            self.assertEqual(record["candidateNote"], "")


class Savivaldybiu2023ElectedFlagTests(Savivaldybiu2023SitemapTestBase):
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

        self.assertEqual(rounds, Counter({"I": 26, "II": 34}))

    def test_council_elected_total(self) -> None:
        elected = [
            entry for entry in self.entries if entry.get("councilCandidacy", {}).get("elected")
        ]

        self.assertEqual(len(elected), EXPECTED_STATS["elected_council_members"])

    def test_elected_council_member_carries_a_post_election_position(self) -> None:
        entry = self.entries_by_vrk_id["2420505"]

        self.assertEqual(entry["candidateId"], "algirdas-gudaitis-2420505")
        self.assertTrue(entry["councilCandidacy"]["elected"])
        self.assertEqual(entry["councilCandidacy"]["postElectionPosition"], 2)

    def test_not_elected_council_candidate_is_flagged_false(self) -> None:
        entry = self.entries_by_vrk_id["2425331"]

        self.assertEqual(entry["candidateId"], "ingrida-sakalauskiene-2425331")
        self.assertFalse(entry["councilCandidacy"]["elected"])


class Savivaldybiu2023SitemapFixtureCoverageTests(Savivaldybiu2023SitemapTestBase):
    FIXTURE_CANDIDATE_IDS = {
        "algimantas-rusteika-2423645",
        "algirdas-gudaitis-2420505",
        "algirdas-zebrauskas-2424292",
        "ingrida-sakalauskiene-2425331",
        "linas-urmanavicius-2421676",
        "mykolas-majauskas-2420485",
        "rasa-vitkauskiene-2423015",
        "skirmantas-mockevicius-2422343",
        "vitalijus-mitrofanovas-2425352",
    }

    def test_every_committed_candidate_fixture_is_in_the_sitemap(self) -> None:
        candidate_ids = {entry["candidateId"] for entry in self.entries}

        self.assertTrue(self.FIXTURE_CANDIDATE_IDS <= candidate_ids)

    def test_committed_candidate_fixture_dirs_match_sitemap_ids(self) -> None:
        fixture_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        fixture_dirs.discard("lists")

        self.assertEqual(fixture_dirs, self.FIXTURE_CANDIDATE_IDS)


if __name__ == "__main__":
    unittest.main()
