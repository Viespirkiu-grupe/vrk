import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2019-kovo-3-savivaldybiu-tarybu"
ALLOWED_CANDIDATE_DIRS = {
    "agne-aleksejevaite-2409490",
    "gintas-orda-2400958",
    "gediminas-dauksys-2408494",
    "judita-ziliene-2409466",
    "kestutis-armonas-2404237",
    "nerijus-cesiulis-2406286",
    "ricardas-juska-2413847",
    "skirmantas-mockevicius-2400117",
    "vitalijus-mitrofanovas-2406746",
    "vytas-jareckas-2404239",
}
# Like 2023, this election publishes candidates through two structures, so the
# samples tree carries an extra listing page and a whole directory of
# party-list pages alongside the usual per-candidate dirs.
ALLOWED_SUPPORT_DIRS = {
    "lists",
}
# What a clone carries. `lists/` is 12.4 MB across the 465 party-list pages
# and five of the ten candidates embed a base64 portrait, each of them over
# the 1 MiB limit on a tracked fixture unit (scripts/tracked_fixtures.py).
TRACKED_CANDIDATE_DIRS = {
    "agne-aleksejevaite-2409490",
    "gintas-orda-2400958",
    "judita-ziliene-2409466",
    "kestutis-armonas-2404237",
    "vitalijus-mitrofanovas-2406746",
}
TRACKED_SUPPORT_DIRS: set[str] = set()
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "lists-index.html",
    "page.html",
}
# 465 lists in 2019 (2023 has 467): 87 visuomeniniai rinkimų komitetai and 14
# coalitions among them, and no politiniai komitetai — those did not exist yet.
EXPECTED_PARTY_LIST_COUNT = 465


class Savivaldybiu2019SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir() and child.name not in ALLOWED_SUPPORT_DIRS
        }

        self.assertEqual(actual_dirs - ALLOWED_CANDIDATE_DIRS, set())
        self.assertLessEqual(TRACKED_CANDIDATE_DIRS, actual_dirs)

    def test_samples_directory_contains_expected_support_directories(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}

        self.assertEqual(actual_dirs - (ALLOWED_CANDIDATE_DIRS | ALLOWED_SUPPORT_DIRS), set())
        self.assertLessEqual(TRACKED_CANDIDATE_DIRS | TRACKED_SUPPORT_DIRS, actual_dirs)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_file()
        }

        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_party_list_pages_are_complete(self) -> None:
        # The council half of the election is only reachable through these
        # pages; a short lists/ directory means the sitemap fixture no longer
        # covers all 465 party/coalition/committee lists.
        list_pages = sorted(
            child.name
            for child in (SAMPLES_ROOT / "lists").iterdir()
            if child.is_file() and child.suffix == ".html"
        )

        self.assertEqual(len(list_pages), EXPECTED_PARTY_LIST_COUNT)
        for name in list_pages:
            self.assertRegex(name, r"^rpgId-\d+_rorgId-\d+\.html$")

    def test_lists_directory_holds_nothing_but_list_pages(self) -> None:
        # build_sitemap looks a list page up by name, so a stray file here is
        # never read and never noticed; the count check above would still pass.
        strays = [
            child.name
            for child in (SAMPLES_ROOT / "lists").iterdir()
            if not (child.is_file() and child.suffix == ".html")
        ]

        self.assertEqual(strays, [])

    def test_every_candidate_directory_is_id_suffixed(self) -> None:
        # candidateId is "<name-slug>-<vrkCandidateId>" here because hundreds of
        # the 13,666 candidates collide on the bare name slug.
        for name in ALLOWED_CANDIDATE_DIRS:
            self.assertRegex(name, r"^[a-z0-9-]+-\d{7}$")
        for name in TRACKED_CANDIDATE_DIRS:
            self.assertTrue((SAMPLES_ROOT / name / "anketa.html").exists(), name)


if __name__ == "__main__":
    unittest.main()
