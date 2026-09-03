import unittest
from pathlib import Path

from local_data import page_names


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2003-birzelio-15-seimo-nauji"
# The complete 27-candidate field of the June 2003 new Seimas election —
# Senamiesčio Nr. 2 (7), Antakalnio Nr. 3 (7), Šeškinės Nr. 6 (8) and
# Nevėžio Nr. 26 (5).
ALLOWED_CANDIDATE_DIRS = {
    "alfonsas-bute",
    "algirdas-paleckis",
    "danielius-sadauskas",
    "danute-krisciuniene",
    "edmund-sot",
    "eduardas-pabarcius",
    "eugenijus-gentvilas",
    "gediminas-ramanauskas",
    "giedre-kvieskiene",
    "jonas-kaliacius",
    "julius-dautartas",
    "juzef-kvetkovskij",
    "nijole-velickiene",
    "ramunas-vyzintas",
    "rimantas-vaitkus",
    "stasys-karcinskas",
    "tatjana-vojeika",
    "valerijus-gorskovas",
    "viktor-balakin",
    "vilija-aleknaite-abramikiene",
    "vilija-blinkeviciute",
    "virgilijus-kestutis-noreika",
    "vladislav-voinic",
    "vytautas-aleksas-lazinka",
    "vytautas-bernatonis",
    "zigfrid-rackovskis",
    "zita-kukuraitiene",
}
# The constituency index and the party index; their pages sit below.
ALLOWED_NON_CANDIDATE_FILES = {"districts.html", "list.html"}
ALLOWED_NON_CANDIDATE_DIRS = {"districts", "lists"}


class SeimoNauji2003SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_dir()}
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS | ALLOWED_NON_CANDIDATE_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {child.name for child in SAMPLES_ROOT.iterdir() if child.is_file()}
        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_four_constituency_pages(self) -> None:
        self.assertEqual(
            {child.name for child in (SAMPLES_ROOT / "districts").iterdir()},
            {f"district-{district}.html" for district in (1476, 1477, 1478, 1479)},
        )

    def test_twelve_party_pages(self) -> None:
        self.assertEqual(
            {child.name for child in (SAMPLES_ROOT / "lists").iterdir()},
            {
                f"list-{party}.html"
                for party in (1645, 1647, 1648, 1650, 1651, 1661, 1686, 1687, 1688, 1690, 1693, 1694)
            },
        )

    def test_each_candidate_holds_the_three_pages(self) -> None:
        for candidate_id in ALLOWED_CANDIDATE_DIRS:
            with self.subTest(candidate_id):
                files = page_names(SAMPLES_ROOT / candidate_id)
                self.assertEqual(
                    files,
                    {
                        "anketa.html",
                        "biografija.html",
                        "turto-ir-pajamu-deklaracijos.html",
                        "index.json",
                    },
                )


if __name__ == "__main__":
    unittest.main()
