import unittest
from pathlib import Path

from local_data import page_names


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2005-lapkricio-20-seimo-kedainiai"
# The complete five-candidate field of the Kėdainiai by-election.
ALLOWED_CANDIDATE_DIRS = {
    "tomas-bakucionis",
    "virginija-baltraitiene",
    "steponas-navajauskas",
    "stasys-sedbaras",
    "vytautas-valaitis",
}
# The constituency index, the party index and the one constituency page.
ALLOWED_NON_CANDIDATE_FILES = {"districts.html", "list.html"}
ALLOWED_NON_CANDIDATE_DIRS = {"districts"}


class SeimoKedainiu2005SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS | ALLOWED_NON_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_one_constituency_page(self) -> None:
        self.assertEqual({child.name for child in (SAMPLES_ROOT / "districts").iterdir()}, {"district-1675.html"})

    def test_each_candidate_holds_the_three_pages(self) -> None:
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            with self.subTest(candidate_id):
                files = page_names(SAMPLES_ROOT / candidate_id)
                self.assertEqual(files, {"anketa.html", "biografija.html", "turto-ir-pajamu-deklaracijos.html", "index.json"})


if __name__ == "__main__":
    unittest.main()
