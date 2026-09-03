import unittest
from pathlib import Path

from local_data import page_names


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "1999-kovo-21-seimo-pakartotiniai"
# All twenty-two candidates across the three re-run constituencies --
# Naujosios Vilnios (No. 10), Nevėžio (No. 26) and Vilniaus Trakų (No. 57),
# 7 + 8 + 7 -- the complete field, so `samples/html/` is the whole election
# and there is no `samples-full/` capture for it.
ALLOWED_CANDIDATE_DIRS = {
    "antanaitis-audrys", "balcevic-zbignev", "braziene-valerija", "daukas-virginijus",
    "davydovas-sergiejus", "garbovskaja-marija", "ivanoviene-bronislava",
    "jankovski-henrik", "komiciene-vida", "liepa-rimantas", "malukas-edmundas-zenonas",
    "melianas-arturas", "petkevicius-juozapas", "pilikauskas-stasys",
    "purvaneckiene-giedre", "sablinskas-eduardas", "sarkus-juozas",
    "satkevicius-vitalijus", "sedzius-laimutis", "terleckas-antanas", "tryk-zdislav",
    "zacharevic-miroslav",
}
ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES = {
    "list.html",
}


class SeimoPakartotiniai1999KovoSampleAllowlistTests(unittest.TestCase):
    def test_candidate_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        actual_dirs.discard("constituencies")
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES)

    def test_every_candidate_holds_all_three_pages(self) -> None:
        # 22/22 on both sub-pages -- the most complete of the four
        # by-elections of this era (March 1998 links only 2 declarations).
        for candidate_id in sorted(ALLOWED_CANDIDATE_DIRS):
            with self.subTest(candidate_id):
                files = page_names(SAMPLES_ROOT / candidate_id)
                self.assertEqual(
                    files,
                    {"candidate.html", "biography.html", "declaration.html", "index.json"},
                )


if __name__ == "__main__":
    unittest.main()
