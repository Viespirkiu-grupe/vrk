import unittest
from pathlib import Path

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2015-kovo-1-savivaldybiu"
# Nine of 15,149 — a sample, not the field, as with the 2019 and 2023
# municipal generals. Chosen for the archetypes the record shape depends on:
# role, list kind, and whether the id has to disambiguate a shared name.
ALLOWED_CANDIDATE_DIRS = {
    "skirmantas-mockevicius-71130",
    "mindaugas-filipavicius-71111",
    "adele-dimsiene-85873",
    "irina-rozova-80134",
    "jelena-berezina-74643",
    "valius-micevicius-85875",
    "albinas-klimas-79174",
    "albinas-klimas-85125",
    "antanas-gasparavicius-86679",
}
ALLOWED_SUPPORT_DIRS = {"lists"}
# A clone carries none of it: `lists/` is 4.9 MB across 478 party-list
# pages, over the 1 MiB limit on a tracked fixture unit
# (scripts/tracked_fixtures.py).
TRACKED_SUPPORT_DIRS: set[str] = set()
# The listing tree: VRK's municipality index, its mayoral roll-up used as a
# cross-check, and one page per municipality.
ALLOWED_NON_CANDIDATE_FILES = {"index.html", "merai.html"} | {
    f"district-{n}.html" for n in range(7761, 7821)
}


class Savivaldybiu2015SampleAllowlistTests(unittest.TestCase):
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
        self.assertIn("merai.html", actual_files)

    def test_all_party_list_pages_are_captured(self) -> None:
        require(SAMPLES_ROOT / "lists")
        # The sitemap is rebuilt from these offline; a missing one silently
        # drops its candidates.
        self.assertEqual(len(sorted((SAMPLES_ROOT / "lists").glob("list-*.html"))), 478)


if __name__ == "__main__":
    unittest.main()
