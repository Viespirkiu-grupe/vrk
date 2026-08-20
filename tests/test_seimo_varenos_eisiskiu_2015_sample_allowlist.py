import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2015-birzelio-7-seimo-varena-eisiskes"
# The fixture set is the whole 8-candidate field.
ALLOWED_CANDIDATE_DIRS = {
    "andzej-andruskevic",
    "juozas-baublys",
    "vidmantas-bizokas",
    "marius-juskevicius",
    "gitana-markoviciene",
    "vidas-mikalauskas",
    "miroslavas-monkevicius",
    "virginijus-varanavicius",
}
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
}


class SeimoVarenosEisiskiu2015SampleAllowlistTests(unittest.TestCase):
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
