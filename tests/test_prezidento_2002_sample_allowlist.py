import unittest
from pathlib import Path

from local_data import page_names


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2002-prezidento"
# The complete seventeen-candidate field of the 2002 presidential election.
ALLOWED_CANDIDATE_DIRS = {
    "valdas-adamkus",
    "eugenijus-gentvilas",
    "algimantas-matulevicius",
    "vytenis-povilas-andriukaitis",
    "arturas-paulauskas",
    "vytautas-bernatonis",
    "kazys-bobelis",
    "kestutis-glaveckas",
    "vytautas-serenas",
    "rolandas-paksas",
    "vytautas-sustauskas",
    "rimantas-jonas-dagys",
    "vytautas-antanas-matulevicius",
    "kazimira-danute-prunskiene",
    "juozas-edvardas-petraitis",
    "algirdas-pilvelis",
    "julius-veselka",
}
# The shared candidate listing and the trustee index (whose per-candidate
# pages are 404 — the index survives as the name-to-registration-id map).
ALLOWED_NON_CANDIDATE_FILES = {"list.html", "patiketiniai-index.html"}


class Prezidento2002SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_each_candidate_holds_the_page_set(self) -> None:
        # The shared listing as the anketa, the HTML biography, the Word
        # programme, and the archived scans: the statement, the two-page
        # data questionnaire and the declaration. The health-certificate
        # scans four cards link are 404 on VRK's mirror, so no candidate
        # holds one — and Šustauskas's second questionnaire page was a
        # 404 on the original site already, so his set is one scan short.
        parsed = {
            "anketa.html",
            "biografija.html",
            "programa.doc",
            "index.json",
        }
        # Nothing reads the scans -- the record links them by path and there is
        # no OCR -- so they are outside the tracked fixture subset
        # (scripts/tracked_fixtures.py) and a clone does not carry them.
        scans = {
            "pareiskimas.jpg",
            "duomenu-anketa-1.jpg",
            "duomenu-anketa-2.jpg",
            "deklaracija.jpg",
        }
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            with self.subTest(candidate_id):
                files = page_names(SAMPLES_ROOT / candidate_id)
                expected = parsed | scans
                if candidate_id == "vytautas-sustauskas":
                    expected -= {"duomenu-anketa-2.jpg"}
                self.assertEqual(files - expected, set())
                self.assertLessEqual(parsed, files)


if __name__ == "__main__":
    unittest.main()
