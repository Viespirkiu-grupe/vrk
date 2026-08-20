import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2015-birzelio-7-pakartotiniai-sirvintos-trakai"
# 327 candidates is past the point of capturing the whole field, so the
# fixture set is curated like the municipal general elections': both
# municipalities, both roles, dual candidacies, both campaign participant
# types, and the pair of ids VRK issued to one person.
ALLOWED_CANDIDATE_DIRS = {
    "zivile-pinskuviene",
    "rita-tamasuniene",
    "marija-puc",
    "marija-puc-2",
    "dangute-mikutiene",
    "vytautas-zalieckas",
    "kestutis-vilkauskas",
    "kestutis-mikulskas",
    "julija-meskauskiene",
    "albertas-malasauskas",
}
# This election publishes candidates through two structures, so the samples
# tree carries per-district listing pages and a directory of party-list pages
# alongside the per-candidate dirs.
ALLOWED_SUPPORT_DIRS = {
    "lists",
}
ALLOWED_NON_CANDIDATE_FILES = {
    "district-7911.html",
    "district-7921.html",
}


class PakartotiniaiSirvintuTraku2015SampleAllowlistTests(unittest.TestCase):
    def test_samples_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir()
        }

        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS | ALLOWED_SUPPORT_DIRS)

    def test_samples_directory_contains_expected_top_level_files(self) -> None:
        actual_files = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_file()
        }

        self.assertEqual(actual_files, ALLOWED_NON_CANDIDATE_FILES)

    def test_party_list_pages_are_captured(self) -> None:
        # Nine lists across the two districts; the sitemap is rebuilt from
        # these offline, so all of them have to be on disk.
        lists = sorted((SAMPLES_ROOT / "lists").glob("list-*.html"))
        self.assertEqual(len(lists), 9)


if __name__ == "__main__":
    unittest.main()
