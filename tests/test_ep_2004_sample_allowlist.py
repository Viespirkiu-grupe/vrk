import unittest
from pathlib import Path

from local_data import page_names


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2004-ep"
# Thirteen of the 241, chosen by shape: the full 241-candidate field is
# scraped by scripts/run_election_batches.sh, not kept as fixtures.
ALLOWED_CANDIDATE_DIRS = {
    # Elected: the LSDP list leader (two education records, a prior mandate,
    # three children), the TS leader (degree and academic title), the VNDPS
    # leader whose mandate VRK declared terminated (decision Nr. 180) and
    # the list's second, seated in her place (decision Nr. 181), and a
    # winner with the individual-form asset declaration.
    "justas-vincas-paleckis",
    "vytautas-landsbergis",
    "kazimira-danute-prunskiene",
    "gintaras-didziokas",
    "laima-liucija-andrikiene",
    # The one candidate with another member state's citizenship (Q8.4.1 /
    # 8.4.2 answered).
    "vytautas-ricardas-backis",
    # The Q9 block's free-text explanation, under each of the three
    # questions it can follow: 9.2 "Yra", 9.1 "Yra" (KGB service), 9.3 "Buvo".
    "nikolajus-salkovskis",
    "viktor-balakin",
    "vladislavas-kazakevicius",
    # A page that omits Q19, the spouse line and Q20 altogether.
    "evalda-siskauskiene",
    # The two sparsest questionnaires (no education table, no languages, no
    # birthplace), one of them with no income declared on any form.
    "juozas-imbrasas",
    "marius-kundrotas",
    # Income filed on two FR0462 form variants, so the total is a sum.
    "kornelijus-platelis",
}
# The list index plus the twelve list pages the sitemap walks
# (lists/list-<id>.html).
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
}
ALLOWED_NON_CANDIDATE_DIRS = {
    "lists",
}


class Ep2004SampleAllowlistTests(unittest.TestCase):
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

    def test_list_pages_are_the_twelve_lists(self) -> None:
        actual = {child.name for child in (SAMPLES_ROOT / "lists").iterdir()}
        self.assertEqual(len(actual), 12)
        self.assertIn("list-1698.html", actual)

    def test_each_candidate_holds_the_three_pages(self) -> None:
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            with self.subTest(candidate_id):
                files = page_names(SAMPLES_ROOT / candidate_id)
                self.assertEqual(
                    files,
                    {"anketa.html", "biografija.html", "turto-ir-pajamu-deklaracijos.html", "index.json"},
                )


if __name__ == "__main__":
    unittest.main()
