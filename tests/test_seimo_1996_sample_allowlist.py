import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "1996-spalio-20-seimo"
ALLOWED_CANDIDATE_DIRS = {
    "asmolkov-vasilij",
    "butkevicius-audrius",
    "andriukaitis-vytenis-povilas",
    "saltiene-irena",
    "astrauskas-vytautas",
}
ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES = {
    "list.html",
}


class Seimo1996SampleAllowlistTests(unittest.TestCase):
    def test_candidate_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        # "constituencies" holds the 71 apgtl.htm crawl pages used to build the
        # sitemap -- discovery scaffolding, not a candidate fixture.
        actual_dirs.discard("constituencies")
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES)


if __name__ == "__main__":
    unittest.main()
