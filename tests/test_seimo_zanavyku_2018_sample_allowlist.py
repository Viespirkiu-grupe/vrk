import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2018-rugsejo-16-seimo-zanavykai"
ALLOWED_CANDIDATE_DIRS = {
    "giedrius-surplys",
    "irena-haase",
    "mindaugas-bastys",
    "mindaugas-tarnauskas",
    "paulius-visockas",
    "vigilijus-jukna",
}
# The candidate directories a clone carries. The rest embed the portrait as a
# base64 data URI in the page itself, putting the directory over the 1 MiB
# limit on a tracked fixture unit (scripts/tracked_fixtures.py).
TRACKED_CANDIDATE_DIRS = {"mindaugas-tarnauskas", "vigilijus-jukna"}
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "page.html",
}


class SeimoZanavyku2018SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir()
        }

        self.assertEqual(actual_dirs - ALLOWED_CANDIDATE_DIRS, set())
        self.assertLessEqual(TRACKED_CANDIDATE_DIRS, actual_dirs)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_file()
        }

        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)


if __name__ == "__main__":
    unittest.main()
