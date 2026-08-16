import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2019-rugsejo-8-seimo"
ALLOWED_CANDIDATE_DIRS = {
    "algis-caplikas",
    "darius-ulickas",
    "dovilas-petkus",
    "eduardas-sablinskas",
    "gintautas-kniuksta",
    "gintautas-paluckas",
    "ieva-budraite",
    "ingrida-venciuviene",
    "justas-ruskys",
    "kazimieras-juraitis",
    "kristupas-augustas-krivickas",
    "ligita-liutikiene",
    "lina-martinaitiene",
    "liudas-jonaitis",
    "martynas-pocius",
    "paule-kuzmickiene",
    "povilas-gylys",
    "raimundas-daubaris",
    "rasa-petrauskiene",
    "rima-olberkyte",
    "ruta-bilkstyte",
    "ruta-janutiene",
    "saulius-gegieckas",
    "tomas-kersys",
    "vaclovas-dackauskas",
    "valdas-rimkus",
    "vilma-galdike",
}
ALLOWED_NON_CANDIDATE_FILES = {
    "list.html",
    "page.html",
}


class Seimo2019SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir()
        }

        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_file()
        }

        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)


if __name__ == "__main__":
    unittest.main()
