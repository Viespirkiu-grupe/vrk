import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scraper.elections.savivaldybiu_2007 import sitemap


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples" / "html" / "2007-vasario-25-savivaldybiu"


class Savivaldybiu2007SitemapTests(unittest.TestCase):
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
        self.assertEqual(self.payload["electionId"], "2007-vasario-25-savivaldybiu")
        self.assertEqual(stats["municipalities"], 60)
        self.assertEqual(len({entry["municipality"] for entry in self.entries}), 60)
        self.assertEqual(stats["parties"], 24)
        self.assertEqual(stats["partyLists"], 600)
        self.assertEqual(stats["listKinds"], {"partija": 596, "partiju-koalicija": 4})
        self.assertEqual(stats["extracted"], 13422)
        self.assertEqual(stats["listCandidates"], 13422)
        self.assertEqual(stats["candidatesOnSeveralLists"], 0)
        self.assertEqual(stats["duplicateCandidateIds"], 0)

    def test_counts_reconcile_with_vrks_by_party_pages(self) -> None:
        # Every party's own page links its list in each municipality it
        # stood in. Every party list walked is there, and the eight links
        # that lead nowhere on the ballot are the coalition members' empty
        # shells — two member parties for each of the four coalitions.
        stats = self.payload["stats"]
        self.assertEqual(stats["partyPageLists"], 604)
        self.assertEqual(stats["coalitionMemberShells"], 8)
        self.assertEqual(stats["partyPageListsUnexplained"], 0)
        self.assertEqual(stats["walkedPartyListsNotOnPartyPages"], 0)

    def test_coalitions_carry_their_member_parties(self) -> None:
        coalitions = {c["name"]: c for c in self.payload["coalitions"]}
        self.assertEqual(len(coalitions), 4)
        neringa = coalitions['Koalicija "Už Neringos ateitį"']
        self.assertEqual(neringa["municipality"], "Neringos savivaldybė")
        self.assertEqual((neringa["listId"], neringa["listNumber"]), ("2300", 3))
        self.assertEqual(neringa["memberParties"], ["Darbo partija", "Lietuvos krikščionys demokratai"])
        self.assertEqual(
            coalitions["G.Vagnoriaus koalicija"]["memberParties"],
            ["Krikščionių konservatorių socialinė sąjunga", "Partija „Jaunoji Lietuva“"],
        )
        self.assertTrue(all(len(c["memberParties"]) == 2 for c in coalitions.values()))

    def test_every_entry_is_a_party_list_council_candidacy(self) -> None:
        # Council seats only, no self-nomination of any kind in 2007.
        self.assertEqual(Counter(tuple(entry["roles"]) for entry in self.entries), {("tarybos-narys",): 13422})
        self.assertFalse(any("mayoralCandidacy" in entry for entry in self.entries))
        self.assertFalse(any(entry["councilCandidacy"]["selfNominated"] for entry in self.entries))
        self.assertTrue(all(entry["councilCandidacy"]["listPosition"] for entry in self.entries))

    def test_list_candidacy_carries_list_kind_number_and_position(self) -> None:
        uspaskich = self.by_id["viktor-uspaskich-9852"]
        self.assertEqual(uspaskich["municipality"], "Kėdainių rajono savivaldybė")
        self.assertEqual(
            uspaskich["councilCandidacy"],
            {"partyList": "Darbo partija", "listKind": "partija", "listNumber": 21, "listPosition": 25, "selfNominated": False},
        )
        giedraitis = self.by_id["vigantas-giedraitis-2544"]["councilCandidacy"]
        self.assertEqual(giedraitis["listKind"], "partiju-koalicija")
        self.assertEqual((giedraitis["partyList"], giedraitis["listNumber"], giedraitis["listPosition"]), ('Koalicija "Už Neringos ateitį"', 3, 1))
        # The ballot numbers a withdrawn candidate's place and skips it: the
        # Elektrėnai LSDP list runs 1–33 with no 29.
        self.assertEqual(self.by_id["algirdas-strignatavicius-7436"]["councilCandidacy"]["listPosition"], 33)
        elektrenai_lsdp = sorted(
            e["councilCandidacy"]["listPosition"] for e in self.entries
            if e["municipality"] == "Elektrėnų savivaldybė" and e["councilCandidacy"]["partyList"] == "Lietuvos socialdemokratų partija"
        )
        self.assertEqual(elektrenai_lsdp, [n for n in range(1, 34) if n != 29])

    def test_names_are_title_cased_and_ids_carry_vrks_id(self) -> None:
        zuokas = self.by_id["arturas-zuokas-12711"]
        self.assertEqual(zuokas["candidateName"], "Artūras Zuokas")
        self.assertEqual(zuokas["vrkCandidateId"], "12711")
        self.assertTrue(zuokas["url"].endswith("/rinkimai/3/Kandidatai/Kandidatas12711/Kandidato12711Anketa.html"))
        self.assertEqual(self.by_id["giedre-ramanauskaite-kedikiene-9665"]["candidateName"], "Giedrė Ramanauskaitė-Kedikienė")

    def test_municipality_names_follow_the_corpus_form(self) -> None:
        self.assertEqual(sitemap.municipality_from_heading("Elektrėnų rinkimų apygarda"), "Elektrėnų savivaldybė")
        self.assertEqual(sitemap.municipality_from_heading("Akmenės rajono rinkimų apygarda"), "Akmenės rajono savivaldybė")
        self.assertIn("Vilniaus miesto savivaldybė", {e["municipality"] for e in self.entries})


if __name__ == "__main__":
    unittest.main()
