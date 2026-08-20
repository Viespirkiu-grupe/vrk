import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_varenos_eisiskiu_2015.anketa_parser import parse_anketa_sample
from scraper.elections.seimo_varenos_eisiskiu_2015.sitemap import ELECTION_ID, LISTING_URL


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2015-birzelio-7-seimo-varena-eisiskes"


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class SeimoVarenosEisiskiu2015AnketaParserTests(unittest.TestCase):
    """The parsers are the Žirmūnai 2015 era set running under this election's
    id; these tests pin the wiring and this election's own facts."""

    def setUp(self) -> None:
        self.markoviciene = _parse("gitana-markoviciene")
        self.mikalauskas = _parse("vidas-mikalauskas")

    def test_module_constants(self) -> None:
        self.assertEqual(ELECTION_ID, "2015-birzelio-7-seimo-varena-eisiskes")
        self.assertIn("rinkimai/459_lt", LISTING_URL)

    def test_records_carry_this_election_id(self) -> None:
        self.assertEqual(self.markoviciene["electionId"], ELECTION_ID)
        self.assertTrue(
            self.markoviciene["source"]["candidateSourceUrl"].endswith(
                "Kandidatas87561/Kandidato87561Anketa.html"
            )
        )

    def test_era_shapes_hold(self) -> None:
        n = self.markoviciene["normalized"]
        self.assertEqual(
            list(n.keys()),
            [
                "profilis",
                "anketa",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
                "privaciu-interesu-deklaracija",
                "politines-kampanijos-dalyvio-duomenys",
                "kita",
            ],
        )
        self.assertEqual(n["turto-ir-pajamu-deklaracijos"]["valiuta"], "Lt")
        self.assertIsNone(n["profilis"]["pastaba"])

    def test_the_one_self_nominated_candidate_is_the_one_independent_campaign(self) -> None:
        # Seven of the eight candidates are represented by their nominating
        # party; only the self-nominated candidate runs her own campaign.
        self.assertEqual(
            self.markoviciene["normalized"]["profilis"]["kita"]["iskele"]["reiksme"],
            "Išsikėlė pats",
        )
        entry = self.markoviciene["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(entry["statusas"], "Savarankiškas")
        self.assertNotIn("atstovauja", entry)

        represented = self.mikalauskas["normalized"]["politines-kampanijos-dalyvio-duomenys"][0]
        self.assertEqual(represented["statusas"], "Atstovaujamasis")
        self.assertEqual(
            represented["atstovauja"]["pavadinimas"],
            "LIETUVOS SOCIALDEMOKRATŲ PARTIJA (S)",
        )

    def test_anketa_values(self) -> None:
        anketa = self.mikalauskas["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1955-08-10")
        # Q16 is the bare-comma template artifact on this record.
        self.assertIsNone(anketa["pagrindine-darboviete"])
        self.assertTrue(all(value == "Ne" for value in anketa["pareiskimai"].values()))


if __name__ == "__main__":
    unittest.main()
