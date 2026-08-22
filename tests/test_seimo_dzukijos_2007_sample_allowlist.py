import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2007-spalio-7-seimo-dzukija"
# The fixture set is the whole ten-candidate field.
ALLOWED_CANDIDATE_DIRS = {
    "antanas-terleckas",
    "aurimas-trunce",
    "gediminas-jegelevicius",
    "kestutis-cilinskas",
    "monika-razanauskiene",
    "ona-baleviciute",
    "ramute-oreniene",
    "viktor-uspaskich",
    "vytautas-jurgis-kadzys",
    "zenonas-zvikas",
}
# The district page is the listing (the index is a meta-refresh to it).
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
}


class SeimoDzukijos2007SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)


if __name__ == "__main__":
    unittest.main()
