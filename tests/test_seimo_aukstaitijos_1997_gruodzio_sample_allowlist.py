import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "1997-gruodzio-21-seimo-pakartotiniai"
# All four candidates in the single re-run constituency (Aukštaitijos, No.
# 28) -- the complete field.
ALLOWED_CANDIDATE_DIRS = {
    "babilius-vincas-kestutis",
    "velikonis-virmantas",
    "veselka-julius",
    "zekoniene-vanda",
}
ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES = {
    "list.html",
}


class SeimoAukstaitijos1997GruodzioSampleAllowlistTests(unittest.TestCase):
    def test_candidate_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        actual_dirs.discard("constituencies")
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES)


if __name__ == "__main__":
    unittest.main()
