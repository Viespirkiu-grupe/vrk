import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scraper.elections.savivaldybiu_2015 import sitemap


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples" / "html" / "2015-kovo-1-savivaldybiu"


class Savivaldybiu2015SitemapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path, cls.stats = sitemap.build_sitemap_from_sample(
                sample_path=SAMPLES_DIR, output_path=Path(tmp) / "sitemap.json"
            )
            cls.payload = json.loads(output_path.read_text(encoding="utf-8"))
        cls.entries = cls.payload["entries"]
        cls.by_id = {entry["candidateId"]: entry for entry in cls.entries}

    def test_all_sixty_municipalities_are_walked(self) -> None:
        self.assertEqual(self.payload["stats"]["municipalities"], 60)
        self.assertEqual(len({entry["municipality"] for entry in self.entries}), 60)
        self.assertEqual(self.payload["stats"]["partyLists"], 478)

    def test_counts_reconcile_with_vrks_own_mayoral_listing(self) -> None:
        # The district walk and VRK's KandidataiMerai.html roll-up have to
        # name the same people; either direction disagreeing means the walk
        # missed a listing or the roll-up omits a candidate.
        stats = self.payload["stats"]
        self.assertEqual(stats["mayoralCandidates"], 434)
        self.assertEqual(stats["mayoralListingCandidates"], 434)
        self.assertEqual(stats["mayoralOnlyInListing"], 0)
        self.assertEqual(stats["mayoralOnlyInDistrictWalk"], 0)

    def test_structures_merge_on_vrk_candidate_id(self) -> None:
        stats = self.payload["stats"]
        self.assertEqual(stats["extracted"], 15149)
        self.assertEqual(stats["councilCandidates"], 15127)
        self.assertEqual(stats["dualCandidates"], 412)
        # The prose marker on the list pages and the id join agree exactly.
        self.assertEqual(stats["markerJoinMismatch"], 0)
        roles = Counter(tuple(entry["roles"]) for entry in self.entries)
        self.assertEqual(roles[("meras", "tarybos-narys")], 412)
        self.assertEqual(roles[("meras",)], 22)

    def test_candidate_ids_carry_vrks_own_id(self) -> None:
        # 140 candidates share a name slug with someone else, so a positional
        # suffix would make an id depend on traversal order — and the batch
        # runner uses the output filename as its resume marker.
        self.assertEqual(self.payload["stats"]["duplicateCandidateIds"], 0)
        self.assertEqual(len({e["candidateId"] for e in self.entries}), len(self.entries))
        for entry in self.entries[:50]:
            self.assertTrue(entry["candidateId"].endswith("-" + entry["vrkCandidateId"]))

        same_name = [e for e in self.entries if e["candidateName"] == "Albinas Klimas"]
        self.assertGreaterEqual(len(same_name), 2)
        self.assertEqual(len({e["candidateId"] for e in same_name}), len(same_name))

    def test_a_mayoral_row_may_name_no_nominator(self) -> None:
        # Twelve mayoral rows are published as the bare name, with no
        # "- iškėlė ..." clause, so nominatedBy is null there rather than
        # guessed at.
        missing = [
            e for e in self.entries
            if "meras" in e["roles"] and not (e.get("mayoralCandidacy") or {}).get("nominatedBy")
        ]
        self.assertEqual(len(missing), 12)


if __name__ == "__main__":
    unittest.main()
