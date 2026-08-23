import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2004-prezidento"
# The complete five-candidate field of the 2004 presidential election.
ALLOWED_CANDIDATE_DIRS = {
    "valdas-adamkus",
    "petras-austrevicius",
    "vilija-blinkeviciute",
    "ceslovas-jursenas",
    "kazimira-danute-prunskiene",
}
# The one shared candidate listing.
ALLOWED_NON_CANDIDATE_FILES = {"list.html"}
# The candidates who published no election programme.
CANDIDATES_WITHOUT_PROGRAMA = {"petras-austrevicius"}


class Prezidento2004SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_each_candidate_holds_the_page_set(self) -> None:
        # The listing card's page-set: the shared listing as the anketa, the
        # declaration extracts, the Word-document biography (and programme,
        # where published) and the full-portrait page.
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            with self.subTest(candidate_id):
                expected = {
                    "anketa.html",
                    "biografija.doc",
                    "nuotrauka.html",
                    "turto-ir-pajamu-deklaracijos.html",
                    "index.json",
                }
                if candidate_id not in CANDIDATES_WITHOUT_PROGRAMA:
                    expected.add("programa.doc")
                files = {child.name for child in (SAMPLES_ROOT / candidate_id).iterdir()}
                self.assertEqual(files, expected)


if __name__ == "__main__":
    unittest.main()
