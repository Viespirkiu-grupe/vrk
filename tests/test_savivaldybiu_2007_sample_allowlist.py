import unittest
from pathlib import Path

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2007-vasario-25-savivaldybiu"
# Eleven of 13,422 — a sample, not the field, as with the other municipal
# generals. Chosen for the shapes the record depends on: a party list's
# leader who won (two, one of them in Vilnius, the largest municipality),
# the same list's last position after a withdrawn number (33 of 1–33 with
# 29 missing), a winner from the tail of a list (position 25, post-election
# number 3), the leaders of three of the four party coalitions (two elected,
# one not — their cards carry a second "Numeris partijos sąraše" line), a
# double surname, a three-part name whose questionnaire stops after an
# empty "Tautybė", a page with the degree line, and — since issue #98 — the
# election's other declaration shape: a page whose only asset declaration is
# the *spouse's*, which the corpus used to store as the candidate's.
ALLOWED_CANDIDATE_DIRS = {
    "arvydas-vysniauskas-7357",
    "algirdas-strignatavicius-7436",
    "arturas-zuokas-12711",
    "rolandas-paksas-1537",
    "viktor-uspaskich-9852",
    "vigantas-giedraitis-2544",
    "bronis-rope-660",
    "danute-mileikiene-3258",
    "giedre-ramanauskaite-kedikiene-9665",
    "zigfridas-herbertas-pilvinis-996",
    "tadeus-romanovskij-11440",
}
ALLOWED_SUPPORT_DIRS = {"lists", "parties"}
# Of the two, the one a clone carries: `lists/` is 4.5 MB across 600
# party-list pages, over the 1 MiB limit on a tracked fixture unit
# (scripts/tracked_fixtures.py).
TRACKED_SUPPORT_DIRS = {"parties"}
# The listing tree: VRK's index and one page per municipality; the 24
# by-party pages (the cross-check) live under parties/.
ALLOWED_NON_CANDIDATE_FILES = {"index.html"} | {f"district-{n}.html" for n in range(6776, 6836)}


class Savivaldybiu2007SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs - (ALLOWED_CANDIDATE_DIRS | ALLOWED_SUPPORT_DIRS), set())
        self.assertLessEqual(ALLOWED_CANDIDATE_DIRS | TRACKED_SUPPORT_DIRS, actual_dirs)

    def test_every_municipality_page_is_captured(self) -> None:
        districts = sorted(SAMPLES_ROOT.glob("district-*.html"))
        self.assertEqual(len(districts), 60)

    def test_top_level_files_are_the_listing_tree(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertTrue(actual_files <= ALLOWED_NON_CANDIDATE_FILES, actual_files - ALLOWED_NON_CANDIDATE_FILES)
        self.assertIn("index.html", actual_files)

    def test_all_list_and_party_pages_are_captured(self) -> None:
        require(SAMPLES_ROOT / "lists", SAMPLES_ROOT / "parties")
        # The sitemap is rebuilt from these offline; a missing list page
        # silently drops its candidates, a missing party page weakens the
        # cross-check.
        self.assertEqual(len(sorted((SAMPLES_ROOT / "lists").glob("list-*.html"))), 600)
        self.assertEqual(len(sorted((SAMPLES_ROOT / "parties").glob("party-*.html"))), 24)

    def test_each_candidate_has_the_three_tabs(self) -> None:
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            names = {child.name for child in (SAMPLES_ROOT / candidate_id).iterdir()}
            self.assertEqual(
                names,
                {"index.json", "anketa.html", "turto-ir-pajamu-deklaracijos.html", "interesu-deklaracija.html"},
                candidate_id,
            )


if __name__ == "__main__":
    unittest.main()
