import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.pakartotiniai_sirvintu_traku_2015 import sitemap


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples" / "html" / "2015-birzelio-7-pakartotiniai-sirvintos-trakai"


def _build() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = sitemap.build_sitemap_from_sample(
            sample_path=SAMPLES_DIR,
            output_path=Path(tmp) / "sitemap.json",
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class PakartotiniaiSirvintuTraku2015SitemapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = _build()
        self.entries = self.payload["entries"]
        self.by_id = {entry["candidateId"]: entry for entry in self.entries}

    def test_two_districts_merge_into_one_election(self) -> None:
        stats = self.payload["stats"]
        self.assertEqual(stats["mayoralCandidates"], 15)
        self.assertEqual(stats["councilCandidates"], 319)
        self.assertEqual(stats["partyLists"], 9)
        self.assertEqual(stats["extracted"], 327)
        municipalities = {entry["municipality"] for entry in self.entries}
        self.assertEqual(
            municipalities,
            {"Širvintų rajono savivaldybė", "Trakų rajono savivaldybė"},
        )

    def test_district_ids_are_not_what_the_titles_suggest(self) -> None:
        # Apygarda7921 is Širvintos and Apygarda7911 is Trakai, the reverse of
        # the order the election title names them in.
        sirvintos = [e for e in self.entries if e["municipality"].startswith("Širvintų")]
        self.assertEqual(len(sirvintos), 7)
        self.assertTrue(all(e["roles"] == ["meras"] for e in sirvintos))
        # Širvintos repeated only the member-mayor vote, so it has no lists.
        self.assertFalse(any("councilCandidacy" in e for e in sirvintos))

    def test_dual_candidacies_merge_on_vrk_candidate_id(self) -> None:
        duals = [e for e in self.entries if len(e["roles"]) > 1]
        self.assertEqual(len(duals), 7)
        mikutiene = self.by_id["dangute-mikutiene"]
        self.assertEqual(mikutiene["roles"], ["meras", "tarybos-narys"])
        # The mayoral row names both nominating parties; the list row names
        # only the list she stood on.
        self.assertEqual(
            mikutiene["mayoralCandidacy"]["nominatedBy"],
            "Darbo partija, Lietuvos žaliųjų partija",
        )
        self.assertEqual(mikutiene["councilCandidacy"]["partyList"], "Darbo partija")
        self.assertEqual(mikutiene["councilCandidacy"]["listPosition"], 1)

    def test_vrk_issued_one_person_two_candidate_ids(self) -> None:
        # Marija Puč runs for both seats in Trakai, but VRK gave the two
        # candidacies separate candidate ids (87693 mayoral, 87694 council),
        # so the id join cannot merge them the way it merges the other seven
        # dual candidates. Both entries are kept, and the sitemap's own
        # marker/join cross-check reports the disagreement rather than
        # hiding it.
        mayoral = self.by_id["marija-puc"]
        council = self.by_id["marija-puc-2"]
        self.assertEqual(mayoral["vrkCandidateId"], "87693")
        self.assertEqual(council["vrkCandidateId"], "87694")
        self.assertEqual(mayoral["roles"], ["meras"])
        self.assertEqual(council["roles"], ["tarybos-narys"])
        self.assertEqual(mayoral["candidateName"], council["candidateName"])
        self.assertEqual(self.payload["stats"]["markerJoinMismatch"], 1)
        self.assertEqual(self.payload["stats"]["duplicateCandidateIds"], 1)

    def test_council_entries_carry_list_facts(self) -> None:
        vilkauskas = self.by_id["kestutis-vilkauskas"]
        self.assertEqual(vilkauskas["roles"], ["tarybos-narys"])
        self.assertEqual(
            vilkauskas["councilCandidacy"]["partyList"],
            "Lietuvos socialdemokratų partija",
        )
        self.assertEqual(vilkauskas["councilCandidacy"]["listNumber"], 2)
        self.assertEqual(vilkauskas["councilCandidacy"]["listPosition"], 2)

    def test_no_entry_claims_an_elected_flag(self) -> None:
        # The 2015 pages publish no elected markers, so no candidacy block
        # carries one — an absent flag, not a false one.
        for entry in self.entries:
            for key in ("mayoralCandidacy", "councilCandidacy"):
                if key in entry:
                    self.assertNotIn("elected", entry[key])


if __name__ == "__main__":
    unittest.main()
