import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai"
# The fixture set is the whole 17-candidate field.
ALLOWED_CANDIDATE_DIRS = {
    "algimantas-matulevicius",
    "alina-gorevaja",
    "ceslava-stanul",
    "daiva-vaitkeviciute-rekasiene",
    "darius-kasperaitis",
    "darius-skusevicius",
    "janina-simkuviene",
    "jonas-gudauskas",
    "jonas-purlys",
    "laima-zemeckiene",
    "leonard-talmont",
    "lilijana-astra",
    "osvaldas-sarmavicius",
    "raimundas-vaitiekus",
    "remigijus-zemaitaitis",
    "renatas-saladzius",
    "vidmantas-zilius",
}
# The constituency index plus the constituency candidate page(s) the
# sitemap walks (districts/district-<id>.html).
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
}
ALLOWED_NON_CANDIDATE_DIRS = {
    "districts",
}


class SeimoSilalesSilutesVilniausSalcininku2009SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()} - ALLOWED_NON_CANDIDATE_DIRS
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_listing_pages_are_complete(self) -> None:
        self.assertEqual(len(list((SAMPLES_ROOT / "districts").iterdir())), 2)


if __name__ == "__main__":
    unittest.main()
