import unittest
from pathlib import Path

from local_data import page_names


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2000-seimo"
# Eighteen of the 1,271, chosen by shape: the full field is scraped by
# scripts/run_election_batches.sh, not kept as fixtures.
ALLOWED_CANDIDATE_DIRS = {
    # Elected: a constituency winner who heads the Brazauskas coalition
    # list as an LSDP member (the card's member-party line), a coalition
    # list seat (elected note on the multi-member block), a plain-party
    # list seat with no photo and no autobiography, a self-nominated
    # constituency winner (Uspaskich, Kėdainiai), a constituency-only
    # party's winner (MKDS), the KDS leader (a list with no seats,
    # constituency winner), a TS list seat who also self-nominated beside
    # her party in one constituency (three card blocks, feminine note),
    # an NDP member of the coalition who won a constituency.
    "andriukaitis-vytenis-povilas",
    "sakalas-aloyzas",
    "maldeikis-eugenijus",
    "uspaskich-viktor",
    "kaseta-algis",
    "bobelis-kazys",
    "jukneviciene-rasa",
    "narviliene-jane",
    # Candidacy shapes: list-only with no autobiography and no family
    # line, a self-nominated woman in a constituency only with a
    # birthplace, a numbered party's constituency-only nominee (an
    # unnumbered row on its page), a cross-party pair (LTS list, Lietuvos
    # laisvės lyga constituency), the one constituency nominee his party
    # page omits, a namesake with the positional id (LDDP member of the
    # coalition list), a candidate with a degree, a title and five
    # languages.
    "petkus-viktoras",
    "ozelyte-nijole",
    "gaizauskas-raimundas",
    "terleckas-antanas",
    "smigelskas-virginijus",
    "sedzius-alvydas-2",
    "cobotas-medardas",
    # The Q8 sub-questions: a US citizen who also declared a foreign oath
    # (8.3.1 and a filled 8.4.1), a holder of two citizenships (8.3.1
    # twice, the bare "<STATE> -" template after 8.4); and one of the 32
    # pre-results-vintage pages (CGI links, no winner note) that belongs
    # to a constituency winner.
    "vaitas-vilimantas-stanislovas",
    "laugalis-victor-vitold-vytautas",
    "zukauskas-henrikas",
}
# The two indexes plus the 28 party pages (15 lists, 4 coalition members,
# 9 constituency-only parties) under lists/ and the 71 constituency pages
# under districts/.
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "districts.html",
}
ALLOWED_NON_CANDIDATE_DIRS = {
    "lists",
    "districts",
}


class Seimo2000SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS | ALLOWED_NON_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_listing_pages(self) -> None:
        self.assertEqual(len(list((SAMPLES_ROOT / "lists").iterdir())), 28)
        self.assertEqual(len(list((SAMPLES_ROOT / "districts").iterdir())), 71)
        self.assertTrue((SAMPLES_ROOT / "lists" / "list-698.html").exists())
        self.assertTrue((SAMPLES_ROOT / "districts" / "district-757.html").exists())

    def test_each_candidate_holds_its_one_page(self) -> None:
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            with self.subTest(candidate_id):
                files = page_names(SAMPLES_ROOT / candidate_id)
                self.assertEqual(files, {"candidate.html", "index.json"})


if __name__ == "__main__":
    unittest.main()
