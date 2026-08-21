import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2013-kovo-3-seimo-birzai-zarasai-ukmerge"
# The fixture set is the whole 37-candidate field across the three constituencies.
ALLOWED_CANDIDATE_DIRS = {
    "aleksandras-zeltinis",
    "algimantas-dumbrava",
    "algirdas-kiznis",
    "arturas-melianas",
    "aurelija-gurskiene",
    "ausra-lamanauskiene",
    "dailis-alfonsas-barakauskas",
    "daiva-krikstaponiene",
    "dalius-bitaitis",
    "dangirdas-miksys",
    "danute-uzkurelyte",
    "genrich-sarbaj",
    "gintaras-songaila",
    "gintaris-petrenas",
    "janina-galiauskiene",
    "julius-girdvainis",
    "julius-kazenas",
    "juozas-murauskas",
    "juozas-stanenas",
    "kazys-grybauskas",
    "kestutis-slavinskas",
    "kristina-brazauskiene",
    "ligitas-kernagis",
    "mindaugas-kluonis",
    "nijole-satiene",
    "nikolajus-gusevas",
    "rimantas-kumpis",
    "rimvydas-podolskis",
    "ritas-vaiginas",
    "rolandas-janickas",
    "rolandas-urniezius",
    "sergejus-kotovas",
    "sigitas-martinavicius",
    "valdemaras-valkiunas",
    "vytautas-galvonas",
    "vytautas-sustauskas",
    "zydrunas-savickas",
}
# The constituency index plus the three constituency candidate pages the
# sitemap walks (districts/district-<id>.html).
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
}
ALLOWED_NON_CANDIDATE_DIRS = {
    "districts",
}


class SeimoBirzuZarasuUkmerges2013SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir()
        }

        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS | ALLOWED_NON_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_file()
        }

        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_district_pages_are_the_three_constituencies(self) -> None:
        actual = {child.name for child in (SAMPLES_ROOT / "districts").iterdir()}
        self.assertEqual(actual, {"district-7433.html", "district-7434.html", "district-7435.html"})


if __name__ == "__main__":
    unittest.main()
