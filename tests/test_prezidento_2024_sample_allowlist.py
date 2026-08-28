import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2024-prezidento"
ALLOWED_CANDIDATE_DIRS = {
    "andrius-mazuronis",
    "dainius-zalimas",
    "eduardas-vaitkus",
    "giedrimas-jeglinskas",
    "gitanas-nauseda",
    "ignas-vegele",
    "ingrida-simonyte",
    "remigijus-zemaitaitis",
}
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "page.html",
}
# `page.html` is the only top-level file a clone carries: `list.html` is
# 3.2 MB of embedded portraits, over the 1 MiB limit on a tracked fixture
# unit (scripts/tracked_fixtures.py).
TRACKED_NON_CANDIDATE_FILES = {"page.html"}


class Prezidento2024SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir()
        }

        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_file()
        }

        self.assertEqual(actual_files - ALLOWED_NON_CANDIDATE_FILES, set())
        self.assertLessEqual(TRACKED_NON_CANDIDATE_FILES, actual_files)


if __name__ == "__main__":
    unittest.main()
