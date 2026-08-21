import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.savivaldybiu_2015.anketa_parser import parse_anketa_sample
from scraper.elections.savivaldybiu_2015.sitemap import ELECTION_ID


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2015-kovo-1-savivaldybiu"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id, samples_root=SAMPLES_ROOT, output_root=Path(tmp)
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Savivaldybiu2015AnketaParserTests(unittest.TestCase):
    """The 2015-era walkers with the municipal question mapping, at the scale
    of the whole country; these tests pin what is specific to this election."""

    def setUp(self) -> None:
        self.dimsiene = _parse("adele-dimsiene-85873")
        self.mockevicius = _parse("skirmantas-mockevicius-71130")
        self.micevicius = _parse("valius-micevicius-85875")
        self.klimas_plunge = _parse("albinas-klimas-79174")
        self.klimas_akmene = _parse("albinas-klimas-85125")

    def test_records_carry_this_election_id(self) -> None:
        self.assertEqual(self.dimsiene["electionId"], ELECTION_ID)
        self.assertEqual(ELECTION_ID, "2015-kovo-1-savivaldybiu")
        self.assertEqual(self.dimsiene["candidateId"], "adele-dimsiene-85873")

    def test_kandidatavimas_carries_the_listing_only_facts(self) -> None:
        k = self.dimsiene["kandidatavimas"]
        self.assertEqual(k["vrkCandidateId"], "85873")
        self.assertEqual(k["savivaldybe"], "Alytaus miesto savivaldybė")
        self.assertEqual(k["roles"], ["meras", "tarybos-narys"])
        self.assertEqual(k["tarybosNarys"]["listPosition"], 1)
        self.assertIn("komitetas", k["tarybosNarys"]["partyList"].lower())
        # No 2015 page marks a winner; electedness is joined in from VRK's
        # results tree (sitemaps/<id>.results.json), so it is a real false
        # here — the page's own note stays null.
        self.assertIs(k["isrinktas"], False)
        self.assertIsNone(self.dimsiene["normalized"]["profilis"]["pastaba"])

    def test_mayor_only_candidate_has_no_council_block(self) -> None:
        k = self.mockevicius["kandidatavimas"]
        self.assertEqual(k["roles"], ["meras"])
        self.assertIsNone(k["tarybosNarys"])
        # This is one of the twelve mayoral rows VRK published without a
        # nominator clause.
        self.assertIsNone(k["meras"]["nominatedBy"])

    def test_same_name_candidates_stay_distinct_people(self) -> None:
        # Two Albinas Klimas in different municipalities, born a year apart.
        # The VRK-id suffix keeps their records apart without depending on
        # traversal order.
        self.assertEqual(
            self.klimas_plunge["candidateName"], self.klimas_akmene["candidateName"]
        )
        self.assertEqual(self.klimas_plunge["normalized"]["anketa"]["gimimo-data"], "1952-03-25")
        self.assertEqual(self.klimas_akmene["normalized"]["anketa"]["gimimo-data"], "1953-11-30")
        self.assertNotEqual(
            self.klimas_plunge["kandidatavimas"]["savivaldybe"],
            self.klimas_akmene["kandidatavimas"]["savivaldybe"],
        )

    def test_municipal_question_mapping_and_era_shapes(self) -> None:
        n = self.dimsiene["normalized"]
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
        self.assertEqual(n["anketa"]["gimimo-data"], "1945-12-16")
        self.assertEqual(n["profilis"]["vardas-pavarde"], "Adelė Dimšienė")

    def test_biografija_is_mayoral_only_and_campaigns_are_optional(self) -> None:
        self.assertIn("biografija", self.dimsiene["normalized"])
        self.assertNotIn("biografija", self.micevicius["normalized"])
        # A council candidate need not have a campaign participant at all.
        self.assertNotIn(
            "politines-kampanijos-dalyvio-duomenys", self.micevicius["normalized"]
        )
        self.assertEqual(
            self.mockevicius["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]["statusas"],
            "Savarankiškas",
        )


if __name__ == "__main__":
    unittest.main()
