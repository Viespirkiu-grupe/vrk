import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "1997-kovo-23-seimo-pakartotiniai"
# All 23 candidates across the four re-run constituencies (Naujosios Vilnios,
# Vilniaus-Šalčininkų, Vilniaus-Trakų, Trakų) -- the complete field, since the
# whole election is this small.
ALLOWED_CANDIDATE_DIRS = {
    "lazinko-vytautas-aleksas",
    "maciejkianiec-rysard",
    "melianas-arturas",
    "musteikis-petras",
    "strizenas-jurijus",
    "vaskovic-mecislav",
    "reiciunas-algimantas",
    "senkevic-jan",
    "busma-bronislavas",
    "juchnevicius-vladas",
    "kolosauskas-feliksas",
    "remeika-rimantas",
    "tomasevski-valdemar",
    "vertelkiene-vanda",
    "aleksiuniene-danute",
    "baskas-antanas",
    "bologoviene-regina",
    "cereska-vytautas",
    "cobotas-medardas",
    "jankovski-henrik",
    "matulevicius-algimantas",
    "merkevicius-juozas",
    "pilikauskas-stasys",
}
ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES = {
    "list.html",
}


class SeimoPakartotiniai1997KovoSampleAllowlistTests(unittest.TestCase):
    def test_candidate_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        actual_dirs.discard("constituencies")
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES)


if __name__ == "__main__":
    unittest.main()
