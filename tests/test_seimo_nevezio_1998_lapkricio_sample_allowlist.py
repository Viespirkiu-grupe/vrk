import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "1998-lapkricio-15-seimo-pakartotiniai"
# All eleven candidates in the single re-run constituency (Nevėžio, No. 26) --
# the complete field, so `samples/html/` is the whole election and there is no
# `samples-full/` capture for it.
ALLOWED_CANDIDATE_DIRS = {
    "baskas-antanas",
    "ciplyte-joana-viga",
    "daukas-virginijus",
    "davydovas-sergiejus",
    "gudas-kestutis",
    "josas-tomas",
    "krisciunas-edvardas",
    "malukas-edmundas-zenonas",
    "motuzas-algirdas",
    "satkevicius-vitalijus",
    "terleckas-antanas",
}
ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES = {
    "list.html",
}


class SeimoNevezio1998LapkricioSampleAllowlistTests(unittest.TestCase):
    def test_candidate_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        actual_dirs.discard("constituencies")
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES)

    def test_every_candidate_holds_the_three_pages_this_family_publishes(self) -> None:
        for candidate_id in sorted(ALLOWED_CANDIDATE_DIRS):
            with self.subTest(candidate_id):
                files = {c.name for c in (SAMPLES_ROOT / candidate_id).iterdir() if c.is_file()}
                self.assertEqual(
                    files,
                    {"candidate.html", "biography.html", "declaration.html", "index.json"},
                )


if __name__ == "__main__":
    unittest.main()
