import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_pakartotiniai_1997_kovo.anketa_parser import parse_anketa_samples


class SeimoPakartotiniai1997KovoAnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lazinko = self._parse("lazinko-vytautas-aleksas")
        self.baskas = self._parse("baskas-antanas")
        self.bologoviene = self._parse("bologoviene-regina")

    def _parse(self, candidate_id: str) -> dict:
        output_root = Path(self._tmp.name)
        results = parse_anketa_samples(candidate_ids=[candidate_id], output_root=output_root)
        self.assertEqual(results[0]["anomalies"], [])
        return json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.lazinko["electionId"], "1997-kovo-23-seimo-pakartotiniai")
        self.assertEqual(self.lazinko["candidateId"], "lazinko-vytautas-aleksas")
        self.assertEqual(self.lazinko["candidateName"], "Vytautas Aleksas Lazinko")

    def test_constituency_carried_from_the_re_run_listing(self) -> None:
        candidacy = self.lazinko["rawData"]["candidacies"][0]
        self.assertEqual(candidacy["apygardaName"], "Naujosios Vilnios")
        self.assertEqual(candidacy["apygardaNumber"], 10)
        self.assertEqual(candidacy["nominator"], "Lietuvos liaudies partija")

    def test_masculine_and_feminine_self_nomination_both_parse(self) -> None:
        self.assertEqual(
            self.baskas["rawData"]["candidacies"][0]["nominator"], "Išsikėlė pats"
        )
        self.assertEqual(
            self.bologoviene["rawData"]["candidacies"][0]["nominator"], "Išsikėlė pati"
        )


if __name__ == "__main__":
    unittest.main()
