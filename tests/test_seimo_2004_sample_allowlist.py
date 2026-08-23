import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2004-seimo"
# Fourteen of the 1,251, chosen by shape: the full field is scraped by
# scripts/run_election_batches.sh, not kept as fixtures.
ALLOWED_CANDIDATE_DIRS = {
    # Elected: the Paksas coalition's leader (LDP member, list seat, first
    # on the coalition list and on the LDP one), a constituency runoff winner
    # (TS, Naujamiestis), a first-round constituency winner (LSDP member of
    # the Brazauskas–Paulauskas coalition), a coalition list seat lower down,
    # the LLRA leader (constituency seat; the one list VRK did not rank at
    # the party's request), a VNDPS constituency winner with a Q9
    # explanation under a "Yra", and a TS winner with a degree and a title.
    "valentinas-mazuronis",
    "irena-degutiene",
    "zigmantas-balcytis",
    "remigijus-acas",
    "valdemar-tomasevski",
    "jonas-ramonas",
    "arimantas-dumcius",
    # Candidacy shapes: a numbered-list party's constituency-only nominee
    # (an unnumbered row on its page), a cross-party pair (LLRA list,
    # Lietuvos rusų sąjunga constituency), a party nominee who also
    # self-nominated in the same constituency, a self-nominated woman
    # ("Išsikėlė pati") standing in a constituency only, a constituency-only
    # party's nominee, a list-only coalition candidate.
    "vytautas-ricardas-backis",
    "nikolajus-salkovskis",
    "saulius-gintautas",
    "alma-vitkiene",
    "nikolaj-medvedev",
    "visvaldas-matkevicius",
    # The one candidate whose declarations page VRK never published (no
    # link on the card, the URL a 404): the fixture index records the
    # MissingExpectedTab.
    "genovaite-ziobakiene",
}
# The two indexes plus the 22 party pages (15 lists, 3 constituency-only
# parties, 4 coalition members) under lists/ and the 71 constituency pages
# under districts/.
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "districts.html",
}
ALLOWED_NON_CANDIDATE_DIRS = {
    "lists",
    "districts",
}


class Seimo2004SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS | ALLOWED_NON_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_listing_pages(self) -> None:
        self.assertEqual(len(list((SAMPLES_ROOT / "lists").iterdir())), 22)
        self.assertEqual(len(list((SAMPLES_ROOT / "districts").iterdir())), 71)
        self.assertTrue((SAMPLES_ROOT / "lists" / "list-1874.html").exists())
        self.assertTrue((SAMPLES_ROOT / "districts" / "district-1603.html").exists())

    def test_each_candidate_holds_its_pages(self) -> None:
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            with self.subTest(candidate_id):
                files = {child.name for child in (SAMPLES_ROOT / candidate_id).iterdir()}
                expected = {"anketa.html", "biografija.html", "turto-ir-pajamu-deklaracijos.html", "index.json"}
                if candidate_id == "genovaite-ziobakiene":
                    expected.discard("turto-ir-pajamu-deklaracijos.html")
                self.assertEqual(files, expected)


if __name__ == "__main__":
    unittest.main()
