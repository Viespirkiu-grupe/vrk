import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2000-kovo-19-savivaldybiu-tarybu"
# Ten of the 9,881, chosen by shape: the full field is scraped by
# scripts/run_election_batches.sh, not kept as fixtures.
ALLOWED_CANDIDATE_DIRS = {
    # Elected: the Vilnius LLS leader (47,349 preference votes), the
    # candidate who climbed furthest (LLS #52 to rank 6), a coalition
    # list's leader and its #5 who took rank 2 (both with the card's
    # member-party line), a Birštonas #17 elected at rank 6.
    "paksas-rolandas-84817",
    "cekuolis-jonas-85130",
    "jusas-albertas-94748",
    "zekas-algis-94742",
    "martusevicius-stasys-algirdas-89379",
    # Not elected: a coalition candidate ranked 15th, the leader of a
    # list below the threshold (mandates "-"), the KDS leader in Vilnius
    # with a sparse card (pensioner, no languages, zero income).
    "dagys-algirdas-89945",
    "lizdenis-antanas-85463",
    "petkus-viktoras-89850",
    # Jurbarkas, one of the five municipalities whose per-candidate
    # results VRK never captured: elected status unknown, the list's
    # votes and mandates still joined.
    "zairys-aloyzas-86350",
    "karaliene-rasa-88512",
}
# The two indexes plus the 60 municipality pages under municipalities/,
# the 651 list pages under lists/ and the 28 party pages under parties/.
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "municipalities.html",
}
ALLOWED_NON_CANDIDATE_DIRS = {
    "municipalities",
    "lists",
    "parties",
}


class Savivaldybiu2000SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS | ALLOWED_NON_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_listing_pages(self) -> None:
        self.assertEqual(len(list((SAMPLES_ROOT / "municipalities").iterdir())), 60)
        self.assertEqual(len(list((SAMPLES_ROOT / "lists").iterdir())), 651)
        self.assertEqual(len(list((SAMPLES_ROOT / "parties").iterdir())), 28)
        self.assertTrue((SAMPLES_ROOT / "municipalities" / "municipality-57.html").exists())
        self.assertTrue((SAMPLES_ROOT / "lists" / "list-551-38.html").exists())

    def test_each_candidate_holds_its_one_page(self) -> None:
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            with self.subTest(candidate_id):
                files = {child.name for child in (SAMPLES_ROOT / candidate_id).iterdir()}
                self.assertEqual(files, {"candidate.html", "index.json"})


if __name__ == "__main__":
    unittest.main()
