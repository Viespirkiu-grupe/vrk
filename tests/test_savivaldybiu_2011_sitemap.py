import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scraper.elections.savivaldybiu_2011 import sitemap


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples" / "html" / "2011-vasario-27-savivaldybiu"


class Savivaldybiu2011SitemapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path, cls.stats = sitemap.build_sitemap_from_sample(
                sample_path=SAMPLES_DIR, output_path=Path(tmp) / "sitemap.json"
            )
            cls.payload = json.loads(output_path.read_text(encoding="utf-8"))
        cls.entries = cls.payload["entries"]
        cls.by_id = {entry["candidateId"]: entry for entry in cls.entries}

    def test_all_sixty_municipalities_and_every_list_are_walked(self) -> None:
        stats = self.payload["stats"]
        self.assertEqual(self.payload["electionId"], "2011-vasario-27-savivaldybiu")
        self.assertEqual(stats["municipalities"], 60)
        self.assertEqual(len({entry["municipality"] for entry in self.entries}), 60)
        self.assertEqual(stats["partyLists"], 599)
        self.assertEqual(
            stats["listKinds"],
            {"partija": 560, "partiju-koalicija": 11, "issikelusiu-kandidatu-koalicija": 28},
        )
        self.assertEqual(stats["extracted"], 16403)
        self.assertEqual(stats["listCandidates"], 16260)
        self.assertEqual(stats["selfNominatedCandidates"], 143)

    def test_counts_reconcile_with_vrks_own_roll_ups(self) -> None:
        # KandidataiIssikele.html names every self-nominated candidate — the
        # individuals and the members of the self-nominated coalitions — and
        # the two coalition roll-ups declare each coalition's member count.
        # Any disagreement is a listing the walk missed.
        stats = self.payload["stats"]
        self.assertEqual(stats["selfNominatedListingCandidates"], 505)
        self.assertEqual(stats["selfNominatedCoalitionMembers"], 362)
        self.assertEqual(stats["selfNominatedCandidates"] + stats["selfNominatedCoalitionMembers"], 505)
        self.assertEqual(stats["selfNominatedOnlyInListing"], 0)
        self.assertEqual(stats["selfNominatedOnlyInDistrictWalk"], 0)
        self.assertEqual(stats["selfNominatedAlsoOnList"], 0)
        self.assertEqual(stats["coalitionListsNotWalked"], 0)
        self.assertEqual(stats["coalitionSizeMismatches"], 0)

    def test_every_entry_is_a_council_candidacy(self) -> None:
        # No mayor was elected directly in 2011, so there is one role and no
        # mayoral block anywhere.
        self.assertEqual(Counter(tuple(entry["roles"]) for entry in self.entries), {("tarybos-narys",): 16403})
        self.assertFalse(any("mayoralCandidacy" in entry for entry in self.entries))

    def test_list_candidacy_carries_list_kind_number_and_position(self) -> None:
        uspaskich = self.by_id["viktor-uspaskich-48972"]["councilCandidacy"]
        self.assertEqual(
            uspaskich,
            {"partyList": "Darbo partija", "listKind": "partija", "listNumber": 10, "listPosition": 1, "selfNominated": False},
        )
        karlonas = self.by_id["arunas-karlonas-43800"]["councilCandidacy"]
        self.assertEqual(karlonas["listKind"], "partiju-koalicija")
        self.assertTrue(karlonas["partyList"].startswith("Pakaunės krašto koalicija"))
        zuokas = self.by_id["arturas-zuokas-42680"]["councilCandidacy"]
        self.assertEqual(zuokas["listKind"], "issikelusiu-kandidatu-koalicija")
        self.assertEqual((zuokas["listNumber"], zuokas["listPosition"]), (2, 1))
        self.assertEqual(self.by_id["rimvydas-buinickas-59139"]["councilCandidacy"]["listPosition"], 60)

    def test_self_nominated_individual_has_a_ballot_number_and_no_list(self) -> None:
        norkus = self.by_id["darius-norkus-42302"]
        self.assertEqual(norkus["municipality"], "Vilniaus miesto savivaldybė")
        self.assertEqual(
            norkus["councilCandidacy"],
            {"partyList": None, "listKind": None, "listNumber": 3, "listPosition": None, "selfNominated": True},
        )
        individuals = [e for e in self.entries if e["councilCandidacy"]["selfNominated"]]
        self.assertEqual(len(individuals), 143)
        self.assertTrue(all(e["councilCandidacy"]["listNumber"] for e in individuals))

    def test_names_are_title_case_from_either_page(self) -> None:
        # The list pages print names in capitals, the municipality pages in
        # title case; the sitemap keeps one form.
        self.assertEqual(self.by_id["valdemaras-stancikas-42569"]["candidateName"], "Valdemaras Stančikas")
        self.assertEqual(self.by_id["darius-norkus-42302"]["candidateName"], "Darius Norkus")
        self.assertEqual(
            self.by_id["diana-jokimciene-kachabrisvili-44060"]["candidateName"],
            "Diana Jokimčienė-Kachabrišvili",
        )
        self.assertEqual(sitemap.title_case_name("JACEK JAN  KOMAR"), "Jacek Jan Komar")
        self.assertFalse(any(name.isupper() for name in (e["candidateName"] for e in self.entries)))

    def test_candidate_ids_carry_vrks_own_id(self) -> None:
        self.assertEqual(self.payload["stats"]["duplicateCandidateIds"], 0)
        self.assertEqual(len({e["candidateId"] for e in self.entries}), len(self.entries))
        for entry in self.entries[:50]:
            self.assertTrue(entry["candidateId"].endswith("-" + entry["vrkCandidateId"]))
        slugs = Counter(e["candidateId"].rsplit("-", 1)[0] for e in self.entries)
        self.assertGreater(sum(1 for count in slugs.values() if count > 1), 0)


if __name__ == "__main__":
    unittest.main()
