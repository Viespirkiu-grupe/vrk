import unittest
from pathlib import Path

from local_data import page_names


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "1998-kovo-22-seimo-pakartotiniai"
# All eleven candidates across the two re-run constituencies -- Naujosios
# Vilnios (No. 10) and Vilniaus Trakų (No. 57), 5 and 6 -- the complete field,
# so `samples/html/` is the whole election and there is no `samples-full/`
# capture for it.
ALLOWED_CANDIDATE_DIRS = {
    "antanaitis-audrys",
    "bologoviene-regina",
    "filipovic-tadeus",
    "jocius-kazimieras-jonas",
    "maldaikiene-birute",
    "mickevicius-antanas",
    "paulauskas-arturas",
    "petniunas-vytautas",
    "suboc-danute",
    "subotinas-jurijus",
    "tomasevski-valdemar",
}
# Only these two link `kpdl.htm`; the rest genuinely publish no declaration.
CANDIDATES_WITH_A_DECLARATION = {"filipovic-tadeus", "tomasevski-valdemar"}
ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES = {
    "list.html",
}


class SeimoPakartotiniai1998KovoSampleAllowlistTests(unittest.TestCase):
    def test_candidate_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        actual_dirs.discard("constituencies")
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_TOP_LEVEL_FILES)

    def test_every_candidate_holds_the_pages_their_card_actually_links(self) -> None:
        for candidate_id in sorted(ALLOWED_CANDIDATE_DIRS):
            with self.subTest(candidate_id):
                files = page_names(SAMPLES_ROOT / candidate_id)
                expected = {"candidate.html", "biography.html", "index.json"}
                if candidate_id in CANDIDATES_WITH_A_DECLARATION:
                    expected.add("declaration.html")
                self.assertEqual(files, expected)


if __name__ == "__main__":
    unittest.main()
