import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2008-seimo"
# Ten fixtures chosen for shape: a list-only list leader, a dual
# list+constituency leader, a coalition nominee from each member party, a
# self-nominated constituency candidate, a single-member-only party's
# candidate, both name collisions, a page with the degree-and-title line,
# and the one candidate whose anketa VRK never published (an empty content
# div). The 1,603-candidate field is scraped by
# scripts/run_election_batches.sh, not kept as fixtures.
ALLOWED_CANDIDATE_DIRS = {
    "algis-kaseta-2",
    "andrius-kubilius",
    "arimantas-dumcius",
    "arunas-rimkus-2",
    "gediminas-kirkilas",
    "loreta-grauziniene",
    "sigitas-bankauskas",
    "valdemaras-puodziunas",
    "virginija-baltraitiene",
    "vytautas-aleksas-lazinka",
}
# list.html is the party-list index, districts.html the constituency index;
# lists/ holds the 16 list pages plus the 4 side pages (two coalition
# members, two single-member-only parties; no self-nominated page in 2008),
# districts/ the 71 constituency pages.
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "districts.html",
}
ALLOWED_NON_CANDIDATE_DIRS = {
    "lists",
    "districts",
}


class Seimo2008SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir()
        }

        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS | ALLOWED_NON_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_file()
        }

        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_listing_pages_are_complete(self) -> None:
        self.assertEqual(len(list((SAMPLES_ROOT / "lists").iterdir())), 20)
        self.assertEqual(len(list((SAMPLES_ROOT / "districts").iterdir())), 71)
        self.assertFalse((SAMPLES_ROOT / "lists" / "list-issikele.html").exists())


if __name__ == "__main__":
    unittest.main()
