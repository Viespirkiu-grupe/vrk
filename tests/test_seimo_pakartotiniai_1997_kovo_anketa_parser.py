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

    def test_card_questionnaire_is_read(self) -> None:
        # This election is the one where every candidate fills in "Pagrindinė
        # darbovietė" (23 of 23, against 1 of 879 in the 1996 general).
        anketa = self.baskas["normalized"]["anketa"]
        self.assertEqual(anketa["pagrindine-darboviete"], "Matematikos ir informatikos institutas")
        self.assertEqual(anketa["mokslo-laipsnis"], "Daktaras")
        self.assertEqual(anketa["pedagoginis-vardas"], "Vyr. mokslinis bendradarbis")
        self.assertEqual(anketa["gimimo-vieta"], "Marijampolė")
        self.assertNotIn("gimimo-vietos-saltinis", anketa)

    def test_a_blank_card_birthplace_falls_back_to_the_biography(self) -> None:
        # Čobotas is one of the 9 records across this family whose card leaves
        # "Gimimo vieta" blank. The biography's opening sentence still names a
        # place, and the marker records that it is prose rather than a field.
        anketa = self._parse("cobotas-medardas")["normalized"]["anketa"]
        self.assertEqual(self._parse("cobotas-medardas")["rawData"]["personal"]["birthPlace"], "")
        self.assertEqual(anketa["gimimo-vieta"], "Vilniaus rajonas")
        self.assertEqual(anketa["gimimo-vietos-saltinis"], "biografijos-tekstas")


if __name__ == "__main__":
    unittest.main()
