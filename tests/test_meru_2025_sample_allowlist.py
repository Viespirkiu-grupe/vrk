import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2025-kovo-16-meru"
ALLOWED_CANDIDATE_DIRS = {
    # Jonavos rajono — every candidate struck off by Seimas resolution
    "jolita-peleckiene",
    "povilas-beisys",
    "renata-sorakiene",
    "romanas-steponavicius",
    # Joniškio rajono
    "benjaminas-rimdzius",
    "gediminas-cepulis",
    "liudas-jonaitis",
    "saulius-kuzmarskis",
    # Panevėžio miesto
    "algimantas-kolpertas",
    "ignas-gaiziunas",
    "julius-limantas",
    "loreta-masiliuniene",
    "saulius-raziunas",
    "solveiga-dage",
}
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "page.html",
}


class Meru2025SampleAllowlistTests(unittest.TestCase):
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

        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)


if __name__ == "__main__":
    unittest.main()
