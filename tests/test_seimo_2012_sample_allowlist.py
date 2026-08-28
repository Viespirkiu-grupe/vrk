import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2012-seimo"
# Nine fixtures chosen for shape: a dual list+constituency leader, a
# coalition nominee, a party nominee who also self-nominated, a
# self-nominated constituency candidate on a coalition list, a list-only
# candidate, two constituency-only candidates (self-nominated; a
# single-member-only party), and the one name collision. The 1,927-candidate
# field is scraped by scripts/run_election_batches.sh, not kept as fixtures.
ALLOWED_CANDIDATE_DIRS = {
    "algirdas-butkevicius",
    "alvydas-medalinskas",
    "arunas-markunas",
    "arunas-markunas-2",
    "gediminas-navaitis",
    "linas-balsys",
    "naglis-puteikis",
    "tirkisas-amanovas",
    "vilija-blinkeviciute",
}
# list.html is the party-list index, districts.html the constituency index;
# lists/ holds the 18 list pages plus the 11 side pages (coalition members,
# single-member-only parties, the self-nominated), districts/ the 71
# constituency pages.
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "districts.html",
}
ALLOWED_NON_CANDIDATE_DIRS = {
    "lists",
    "districts",
}
# Of the two, the one a clone carries: `lists/` is 1.1 MB across the 29
# party-list pages, over the 1 MiB limit on a tracked fixture unit
# (scripts/tracked_fixtures.py).
TRACKED_SUPPORT_DIRS = {"districts"}


class Seimo2012SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir()
        }

        self.assertEqual(actual_dirs - (ALLOWED_CANDIDATE_DIRS | ALLOWED_NON_CANDIDATE_DIRS), set())
        self.assertLessEqual(ALLOWED_CANDIDATE_DIRS | TRACKED_SUPPORT_DIRS, actual_dirs)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_file()
        }

        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_listing_pages_are_complete(self) -> None:
        self.assertEqual(len(list((SAMPLES_ROOT / "lists").iterdir())), 29)
        self.assertEqual(len(list((SAMPLES_ROOT / "districts").iterdir())), 71)
        self.assertTrue((SAMPLES_ROOT / "lists" / "list-issikele.html").exists())


if __name__ == "__main__":
    unittest.main()
