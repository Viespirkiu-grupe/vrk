import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2015-birzelio-21-pakartotiniai-silutes"
# 366 candidates, so the fixture set is curated: the eight dual candidates —
# which between them stand on all eight party lists — plus the two different
# people who share the name Jonas Šakurskis.
ALLOWED_CANDIDATE_DIRS = {
    "alfredas-stasys-nauseda",
    "sandra-tamasauskiene",
    "arvydas-jakas",
    "virgilijus-pozingis",
    "tomas-budrikis",
    "vytautas-laurinaitis",
    "jonas-jatautas",
    "daiva-zebeliene",
    "jonas-sakurskis",
    "jonas-sakurskis-2",
}
ALLOWED_SUPPORT_DIRS = {"lists"}
ALLOWED_NON_CANDIDATE_FILES = {"district-7923.html"}


class PakartotiniaiSilutes2015SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS | ALLOWED_SUPPORT_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_all_party_list_pages_are_captured(self) -> None:
        self.assertEqual(len(sorted((SAMPLES_ROOT / "lists").glob("list-*.html"))), 8)


if __name__ == "__main__":
    unittest.main()
