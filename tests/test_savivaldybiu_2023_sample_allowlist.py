import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2023-kovo-5-savivaldybiu-tarybu-ir-meru"
ALLOWED_CANDIDATE_DIRS = {
    "algimantas-rusteika-2423645",
    "algirdas-gudaitis-2420505",
    "algirdas-zebrauskas-2424292",
    "ingrida-sakalauskiene-2425331",
    "linas-urmanavicius-2421676",
    "mykolas-majauskas-2420485",
    "rasa-vitkauskiene-2423015",
    "skirmantas-mockevicius-2422343",
    "vitalijus-mitrofanovas-2425352",
}
# Unlike every other election this one publishes candidates through two
# structures, so the samples tree carries an extra listing page and a whole
# directory of party-list pages alongside the usual per-candidate dirs.
ALLOWED_SUPPORT_DIRS = {
    "lists",
}
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "lists-index.html",
    "page.html",
}
EXPECTED_PARTY_LIST_COUNT = 467


class Savivaldybiu2023SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir() and child.name not in ALLOWED_SUPPORT_DIRS
        }

        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_support_directories(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}

        self.assertEqual(
            actual_dirs,
            ALLOWED_CANDIDATE_DIRS | ALLOWED_SUPPORT_DIRS,
        )

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
        # covers all 467 party/committee lists.
        list_pages = sorted(
            child.name
            for child in (SAMPLES_ROOT / "lists").iterdir()
            if child.is_file() and child.suffix == ".html"
        )

        self.assertEqual(len(list_pages), EXPECTED_PARTY_LIST_COUNT)
        for name in list_pages:
            self.assertRegex(name, r"^rpgId-\d+_rorgId-\d+\.html$")

    def test_every_candidate_directory_is_id_suffixed(self) -> None:
        # candidateId is "<name-slug>-<vrkCandidateId>" here because 244 of the
        # 13,796 candidates collide on the bare name slug.
        for name in ALLOWED_CANDIDATE_DIRS:
            self.assertRegex(name, r"^[a-z0-9-]+-\d{7}$")
            self.assertTrue((SAMPLES_ROOT / name / "anketa.html").exists(), name)


if __name__ == "__main__":
    unittest.main()
