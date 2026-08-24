import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2002-gruodzio-22-savivaldybiu-tarybu"
# Nine of the 10,139, chosen by shape: the full field is scraped by
# scripts/run_election_batches.sh, not kept as fixtures.
ALLOWED_CANDIDATE_DIRS = {
    # Elected: the Akmenė Tautininkai leader (rank 1, 2,086 preference
    # votes, on the council from election day), the leader of Vilnius's
    # A. Zuoko coalition list (42,797 preference votes, the Liberals'
    # nominee) and the coalition's #2 (the Moderate Christian
    # Democrats' nominee, VRK person id "22" — the shortest id in the
    # election), the Neringa coalition's leader.
    "anicetas-lupeika-132972",
    "arturas-zuokas-154491",
    "vytautas-bogusis-22",
    "stasys-mikelis-135915",
    # Not elected: a substitute who entered the council 2004-03-17
    # (isrinktas false, tarybosNarysNuo set), a VNDPS candidate whose
    # list starts at position 2 (a withdrawn #1) with a prior-mandate
    # line and a widower's children-only family block, a Tautininkai
    # candidate with the 12-item declaration variant (the joint
    # bank-accounts item), a TS candidate whose declaration has an
    # empty workplace, a below-threshold-list candidate whose anketa
    # leaves most questions blank and omits Q19 entirely.
    "jadvyga-daukantaite-204265",
    "stasys-berzinis-132939",
    "vytautas-juozapavicius-132963",
    "algimantas-rasimas-121894",
    "veronika-staneikiene-202013",
}
# The two indexes plus the 60 constituency pages under municipalities/,
# the 25 party pages under parties/ and the 564 party-municipality
# pages under party-lists/.
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "parties.html",
}
ALLOWED_NON_CANDIDATE_DIRS = {
    "municipalities",
    "parties",
    "party-lists",
}


class Savivaldybiu2002SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS | ALLOWED_NON_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_listing_pages(self) -> None:
        self.assertEqual(len(list((SAMPLES_ROOT / "municipalities").iterdir())), 60)
        self.assertEqual(len(list((SAMPLES_ROOT / "parties").iterdir())), 25)
        self.assertEqual(len(list((SAMPLES_ROOT / "party-lists").iterdir())), 564)
        self.assertTrue((SAMPLES_ROOT / "municipalities" / "municipality-1354.html").exists())
        self.assertTrue((SAMPLES_ROOT / "party-lists" / "list-1410-909.html").exists())

    def test_each_candidate_holds_its_two_pages(self) -> None:
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            candidate_dir = SAMPLES_ROOT / candidate_id
            files = {child.name for child in candidate_dir.iterdir()}
            self.assertEqual(
                files,
                {"anketa.html", "turto-ir-pajamu-deklaracijos.html", "index.json"},
                candidate_id,
            )


if __name__ == "__main__":
    unittest.main()
