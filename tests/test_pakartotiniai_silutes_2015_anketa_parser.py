import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.pakartotiniai_silutes_2015.anketa_parser import parse_anketa_sample
from scraper.elections.pakartotiniai_silutes_2015.sitemap import ELECTION_ID


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2015-birzelio-21-pakartotiniai-silutes"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id, samples_root=SAMPLES_ROOT, output_root=Path(tmp)
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class PakartotiniaiSilutes2015AnketaParserTests(unittest.TestCase):
    """The 2015-era walkers with the municipal question mapping; these tests
    pin the wiring and this election's own facts."""

    def setUp(self) -> None:
        self.nauseda = _parse("alfredas-stasys-nauseda")
        self.sakurskis = _parse("jonas-sakurskis")
        self.sakurskis2 = _parse("jonas-sakurskis-2")

    def test_records_carry_this_election_id(self) -> None:
        self.assertEqual(self.nauseda["electionId"], ELECTION_ID)
        self.assertEqual(self.nauseda["normalized"]["profilis"]["vardas-pavarde"], "Alfredas Stasys Nausėda")

    def test_kandidatavimas_carries_the_listing_only_facts(self) -> None:
        # Which list and seat order someone stood on appears on the listing
        # and nowhere on the candidate page — for a dual candidate the profile
        # card does not even print a list number.
        k = self.nauseda["kandidatavimas"]
        self.assertEqual(k["vrkCandidateId"], "88018")
        self.assertEqual(k["savivaldybe"], "Šilutės rajono savivaldybė")
        self.assertEqual(k["roles"], ["meras", "tarybos-narys"])
        self.assertEqual(k["tarybosNarys"]["partyList"], "Lietuvos socialdemokratų partija")
        self.assertEqual(k["tarybosNarys"]["listPosition"], 1)
        self.assertEqual(k["meras"]["nominatedBy"], "Lietuvos socialdemokratų partija")
        # The results join: he lost the mayoral runoff but took his list's
        # first seat, so the record says elected, as a council member.
        self.assertIs(k["isrinktas"], True)
        self.assertEqual(k["isrinktasKaip"], "tarybos-narys")
        self.assertIsNone(self.nauseda["normalized"]["profilis"]["pastaba"])

    def test_municipal_question_mapping_and_era_shapes(self) -> None:
        n = self.nauseda["normalized"]
        self.assertEqual(
            list(n["anketa"]["pareiskimai"].keys()),
            [
                "ar-nebaigta-teismo-paskirta-bausme",
                "ar-atliekate-karo-tarnyba",
                "ar-eina-nesuderinamas-pareigas",
                "ar-kitos-valstybes-institucijos-narys",
                "ar-turite-kitos-valstybes-pilietybe",
                "ar-buvote-pripazintas-kaltu",
            ],
        )
        self.assertEqual(n["turto-ir-pajamu-deklaracijos"]["valiuta"], "Lt")
        self.assertEqual(n["anketa"]["gimimo-data"], "1950-06-17")

    def test_the_two_same_name_candidates_are_distinct_people(self) -> None:
        # Same name, different birth dates and different lists.
        self.assertEqual(
            self.sakurskis["candidateName"], self.sakurskis2["candidateName"]
        )
        self.assertEqual(self.sakurskis["normalized"]["anketa"]["gimimo-data"], "1953-03-25")
        self.assertEqual(self.sakurskis2["normalized"]["anketa"]["gimimo-data"], "1957-08-29")
        self.assertNotEqual(
            self.sakurskis["kandidatavimas"]["vrkCandidateId"],
            self.sakurskis2["kandidatavimas"]["vrkCandidateId"],
        )

    def test_a_candidate_may_have_no_campaign_participant_at_all(self) -> None:
        # Council candidates are usually covered by their list's campaign;
        # this one has no participant link on the page at all, so the record
        # simply has no campaign section.
        self.assertNotIn(
            "politines-kampanijos-dalyvio-duomenys", self.sakurskis2["normalized"]
        )
        self.assertEqual(
            self.sakurskis["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Savarankiškas",
        )

    def test_biografija_is_mayoral_only(self) -> None:
        self.assertIn("biografija", self.nauseda["normalized"])
        self.assertNotIn("biografija", self.sakurskis["normalized"])


if __name__ == "__main__":
    unittest.main()
