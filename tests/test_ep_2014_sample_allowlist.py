import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2014-ep"
# One fixture per list: the ten list leaders. The full 215-candidate field is
# scraped by scripts/run_election_batches.sh, not kept as fixtures.
ALLOWED_CANDIDATE_DIRS = {
    "algirdas-saudargas",
    "arturas-melianas",
    "gintaras-steponavicius",
    "julius-panka",
    "linas-balsys",
    "ramunas-karbauskis",
    "rolandas-paksas",
    "valdemar-tomasevski",
    "viktor-uspaskich",
    "zigmantas-balcytis",
}
# The list index plus the ten list pages the sitemap walks (lists/list-<id>.html).
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
}
ALLOWED_NON_CANDIDATE_DIRS = {
    "lists",
}


class Ep2014SampleAllowlistTests(unittest.TestCase):
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

    def test_list_pages_are_the_ten_lists(self) -> None:
        actual = {child.name for child in (SAMPLES_ROOT / "lists").iterdir()}
        self.assertEqual(len(actual), 10)
        self.assertIn("list-4953.html", actual)


if __name__ == "__main__":
    unittest.main()
