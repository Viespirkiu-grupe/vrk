import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.pakartotiniai_silutes_2015 import sitemap


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples" / "html" / "2015-birzelio-21-pakartotiniai-silutes"


def _build() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = sitemap.build_sitemap_from_sample(
            sample_path=SAMPLES_DIR, output_path=Path(tmp) / "sitemap.json"
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class PakartotiniaiSilutes2015SitemapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = _build()
        self.entries = self.payload["entries"]
        self.by_id = {entry["candidateId"]: entry for entry in self.entries}

    def test_module_constants(self) -> None:
        self.assertEqual(sitemap.ELECTION_ID, "2015-birzelio-21-pakartotiniai-silutes")
        self.assertEqual(len(sitemap.DISTRICT_URLS), 1)
        self.assertIn("rinkimai/457_lt", sitemap.DISTRICT_URLS[0])

    def test_one_district_two_structures(self) -> None:
        stats = self.payload["stats"]
        self.assertEqual(stats["mayoralCandidates"], 8)
        self.assertEqual(stats["councilCandidates"], 366)
        self.assertEqual(stats["partyLists"], 8)
        self.assertEqual(stats["extracted"], 366)
        self.assertEqual(
            {entry["municipality"] for entry in self.entries}, {"Šilutės rajono savivaldybė"}
        )

    def test_every_mayoral_candidate_also_stands_for_the_council(self) -> None:
        # Unlike Trakai, no one here ran for the mayoralty alone, so all eight
        # mayoral candidates merge into council entries and the marker and the
        # id join agree exactly.
        self.assertEqual(self.payload["stats"]["dualCandidates"], 8)
        self.assertEqual(self.payload["stats"]["markerJoinMismatch"], 0)
        self.assertFalse([e for e in self.entries if e["roles"] == ["meras"]])

    def test_name_collision_is_two_different_people(self) -> None:
        # Two Jonas Šakurskis stand on different lists under different VRK
        # ids — a genuine collision, so the positional suffix is right here.
        # Contrast the June 7th election, where two ids are one person.
        first = self.by_id["jonas-sakurskis"]
        second = self.by_id["jonas-sakurskis-2"]
        self.assertEqual(first["candidateName"], second["candidateName"])
        self.assertNotEqual(first["vrkCandidateId"], second["vrkCandidateId"])
        self.assertNotEqual(
            first["councilCandidacy"]["listNumber"], second["councilCandidacy"]["listNumber"]
        )
        self.assertEqual(self.payload["stats"]["duplicateCandidateIds"], 1)

    def test_public_election_committee_is_a_nominator(self) -> None:
        zebeliene = self.by_id["daiva-zebeliene"]
        self.assertEqual(
            zebeliene["councilCandidacy"]["partyList"],
            "Visuomeninis rinkimų komitetas „Už žmonių valdžią“",
        )


if __name__ == "__main__":
    unittest.main()
