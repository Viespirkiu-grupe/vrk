import unittest
from pathlib import Path

from local_data import require


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2011-vasario-27-savivaldybiu"
# Ten of 16,403 — a sample, not the field, as with the other municipal
# generals. Chosen for the shapes the record depends on: a self-nominated
# individual (two), a self-nominated coalition's leader (three, one of them
# elected), a party coalition's leader (two — their cards carry the member
# party as a second nomination), a party list's leader, a party list's
# last-but-one position, and a double surname.
ALLOWED_CANDIDATE_DIRS = {
    "darius-norkus-42302",
    "mindaugas-kaknevicius-26835",
    "valdemaras-stancikas-42569",
    "visvaldas-matijosaitis-29278",
    "arturas-zuokas-42680",
    "arunas-karlonas-43800",
    "arunas-burksas-27707",
    "viktor-uspaskich-48972",
    "diana-jokimciene-kachabrisvili-44060",
    "rimvydas-buinickas-59139",
}
ALLOWED_SUPPORT_DIRS = {"lists"}
# A clone carries none of it: `lists/` is 5.3 MB across 599 party-list
# pages, over the 1 MiB limit on a tracked fixture unit
# (scripts/tracked_fixtures.py).
TRACKED_SUPPORT_DIRS: set[str] = set()
# The listing tree: VRK's municipality index, the three roll-ups used as
# cross-checks (self-nominated candidates, party coalitions, coalitions of
# self-nominated candidates), and one page per municipality.
ALLOWED_NON_CANDIDATE_FILES = {
    "index.html",
    "issikele.html",
    "koalicijos.html",
    "issikele-koalicijos.html",
} | {f"district-{n}.html" for n in range(7131, 7191)}


class Savivaldybiu2011SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs - (ALLOWED_CANDIDATE_DIRS | ALLOWED_SUPPORT_DIRS), set())
        self.assertLessEqual(ALLOWED_CANDIDATE_DIRS | TRACKED_SUPPORT_DIRS, actual_dirs)

    def test_every_municipality_page_is_captured(self) -> None:
        districts = sorted(SAMPLES_ROOT.glob("district-*.html"))
        self.assertEqual(len(districts), 60)

    def test_top_level_files_are_the_listing_tree(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertTrue(actual_files <= ALLOWED_NON_CANDIDATE_FILES, actual_files - ALLOWED_NON_CANDIDATE_FILES)
        for name in ("index.html", "issikele.html", "koalicijos.html", "issikele-koalicijos.html"):
            self.assertIn(name, actual_files)

    def test_all_list_pages_are_captured(self) -> None:
        require(SAMPLES_ROOT / "lists")
        # The sitemap is rebuilt from these offline; a missing one silently
        # drops its candidates.
        self.assertEqual(len(sorted((SAMPLES_ROOT / "lists").glob("list-*.html"))), 599)

    def test_each_candidate_has_the_four_tabs(self) -> None:
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            names = {child.name for child in (SAMPLES_ROOT / candidate_id).iterdir()}
            self.assertEqual(
                names,
                {"index.json", "anketa.html", "turto-ir-pajamu-deklaracijos.html", "interesu-deklaracija.html", "kita.html"},
                candidate_id,
            )


if __name__ == "__main__":
    unittest.main()
