import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_aukstaitijos_1997_gruodzio.anketa_parser import parse_anketa_samples


class SeimoAukstaitijos1997GruodzioAnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.babilius = self._parse("babilius-vincas-kestutis")

    def _parse(self, candidate_id: str) -> dict:
        output_root = Path(self._tmp.name)
        results = parse_anketa_samples(candidate_ids=[candidate_id], output_root=output_root)
        self.assertEqual(results[0]["anomalies"], [])
        return json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.babilius["electionId"], "1997-gruodzio-21-seimo-pakartotiniai")
        self.assertEqual(self.babilius["candidateId"], "babilius-vincas-kestutis")

    def test_constituency_is_aukstaitijos_28(self) -> None:
        candidacy = self.babilius["rawData"]["candidacies"][0]
        self.assertEqual(candidacy["apygardaName"], "Aukštaitijos")
        self.assertEqual(candidacy["apygardaNumber"], 28)

    def test_all_four_candidates_parse_with_no_anomalies(self) -> None:
        for candidate_id in (
            "babilius-vincas-kestutis",
            "velikonis-virmantas",
            "veselka-julius",
            "zekoniene-vanda",
        ):
            self._parse(candidate_id)

    def test_the_runoff_winner_carries_the_results_join(self) -> None:
        velikonis = self._parse("velikonis-virmantas")["normalized"]["kandidatavimas"][0]
        self.assertTrue(velikonis["isrinktas"])
        self.assertEqual(velikonis["isrinktas-kaip"], "vienmandate")
        self.assertEqual(velikonis["rezultatu-turas"], 2)
        self.assertEqual([r["turas"] for r in velikonis["turai"]], [1, 2])
        self.assertEqual(velikonis["turai"][1]["balsai"], 16835)
        # The candidate who lost the runoff is a known false, not a null.
        zekoniene = self._parse("zekoniene-vanda")
        self.assertIs(zekoniene["normalized"]["kandidatavimas"][0]["isrinktas"], False)


if __name__ == "__main__":
    unittest.main()
