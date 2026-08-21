import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "1997-kovo-23-savivaldybiu-tarybu"
ALLOWED_CANDIDATE_DIRS = {
    # Page omits the "Gimimo vieta" label entirely — the shape that made the
    # birth date swallow the following labels on 91% of this election's
    # records until _field learned to stop at any known label.
    "abariunas-bronius",
    "pilvelis-algirdas",
    "kizelavicius-stasys",
    "dapkus-ramualdas",
    "margeviciene-vince-vaidevute",
    "tamulevicius-kestutis",
    "tamulevicius-kestutis-2",
}
ALLOWED_NON_CANDIDATE_TOP_LEVEL_ENTRIES = {
    "list.html",
    "municipalities",
    "lists",
}


class Savivaldybiu1997SampleAllowlistTests(unittest.TestCase):
    def test_candidate_directory_contains_only_allowlisted_candidates(self) -> None:
        actual_dirs = {
            child.name
            for child in SAMPLES_ROOT.iterdir()
            if child.is_dir() and child.name not in ALLOWED_NON_CANDIDATE_TOP_LEVEL_ENTRIES
        }
        self.assertEqual(actual_dirs, ALLOWED_CANDIDATE_DIRS)


if __name__ == "__main__":
    unittest.main()
