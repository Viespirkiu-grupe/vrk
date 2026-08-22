import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.svencioniu_tarybos_1997.anketa_parser import parse_anketa_samples


class SvencioniuTarybos1997AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lauzadis = self._parse("lauzadis-sarunas")

    def _parse(self, candidate_id: str) -> dict:
        output_root = Path(self._tmp.name)
        results = parse_anketa_samples(candidate_ids=[candidate_id], output_root=output_root)
        self.assertEqual(results[0]["anomalies"], [])
        return json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))

    def test_top_level_fields(self) -> None:
        self.assertEqual(
            self.lauzadis["electionId"], "1997-birzelio-29-svenciniu-tarybos-pakartotiniai"
        )
        self.assertEqual(self.lauzadis["candidateId"], "lauzadis-sarunas")
        self.assertEqual(self.lauzadis["candidateName"], "Šarūnas Laužadis")

    def test_record_section_order(self) -> None:
        self.assertEqual(
            list(self.lauzadis["rawData"].keys()),
            ["profile", "candidacy", "personal", "declaration"],
        )
        self.assertEqual(
            list(self.lauzadis["normalized"].keys()),
            ["profilis", "kandidatavimas", "anketa", "turto-ir-pajamu-deklaracijos"],
        )

    def test_candidacy_fields(self) -> None:
        candidacy = self.lauzadis["rawData"]["candidacy"]
        self.assertEqual(candidacy["municipalityName"], "Švenčionių rajono")
        self.assertEqual(candidacy["municipalityNumber"], 47)
        self.assertEqual(candidacy["nominator"], "Lietuvių tautininkų sąjunga")
        self.assertEqual(candidacy["listNumber"], 1)

    def test_personal_fields_absent_from_the_seimas_family_are_present_here(self) -> None:
        # Unlike the Seimas archive family (scraper/shared/seimo_archive_1990s.py),
        # this family's kandvl.htm carries birth date/place, nationality,
        # education, languages, workplace, public activity, family status and
        # family members directly as labelled paragraphs.
        personal = self.lauzadis["rawData"]["personal"]
        self.assertEqual(personal["birthDate"], "1951-09-27")
        self.assertEqual(personal["birthPlace"], "Švenčionys , Švenčionių raj.")
        self.assertEqual(personal["residence"], "Buivydiškių k. , Vilniaus raj.")
        self.assertEqual(personal["nationality"], "Lietuvis (-ė)")
        self.assertEqual(personal["education"], "Aukštasis")
        self.assertEqual(personal["foreignLanguages"], ["Vokiečių", "Rusų"])
        self.assertEqual(personal["mainWorkplace"], "Lietuvos bankas,ekonomistas")
        self.assertEqual(personal["familyStatus"], "Vedęs")
        self.assertEqual(
            personal["familyMembers"],
            [
                {"name": "Danutė", "relation": "Sutuoktinis/sutuoktinė"},
                {"name": "Agnė", "relation": "Vaikas"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
