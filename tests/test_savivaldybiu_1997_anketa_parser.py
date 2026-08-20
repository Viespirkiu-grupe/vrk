import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.savivaldybiu_1997.anketa_parser import parse_anketa_samples


class Savivaldybiu1997AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pilvelis = self._parse("pilvelis-algirdas")
        self.tamulevicius_1 = self._parse("tamulevicius-kestutis")
        self.tamulevicius_2 = self._parse("tamulevicius-kestutis-2")

    def _parse(self, candidate_id: str) -> dict:
        output_root = Path(self._tmp.name)
        results = parse_anketa_samples(candidate_ids=[candidate_id], output_root=output_root)
        self.assertEqual(results[0]["anomalies"], [])
        return json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.pilvelis["electionId"], "1997-kovo-23-savivaldybiu-tarybu")
        self.assertEqual(self.pilvelis["candidateId"], "pilvelis-algirdas")
        self.assertEqual(self.pilvelis["candidateName"], "Pilvelis Algirdas")

    def test_candidacy_and_personal_fields(self) -> None:
        candidacy = self.pilvelis["rawData"]["candidacy"]
        self.assertEqual(candidacy["municipalityName"], "Vilniaus miesto")
        self.assertEqual(candidacy["municipalityNumber"], 1)
        self.assertEqual(candidacy["nominator"], "Lietuvos reformų partija")
        self.assertEqual(candidacy["listNumber"], 1)

        personal = self.pilvelis["rawData"]["personal"]
        self.assertEqual(personal["birthDate"], "1944 03 04")
        self.assertEqual(personal["residence"], "Vilnius")
        # A field genuinely absent from this candidate's page (no "Tautybė:"
        # line at all) normalizes to null rather than an empty string.
        self.assertIsNone(self.pilvelis["normalized"]["asmeniniaiDuomenys"]["tautybe"])

    def test_same_name_different_municipality_gets_distinct_ids_and_records(self) -> None:
        # Two different VRK candidate ids (37862 and 37809) share the exact
        # name "Tamulevičius Kęstutis" -- one of the corpus' 46 slug
        # collisions the sitemap resolves with a "-2" suffix, not a merge.
        self.assertEqual(self.tamulevicius_1["candidateId"], "tamulevicius-kestutis")
        self.assertEqual(self.tamulevicius_2["candidateId"], "tamulevicius-kestutis-2")
        self.assertEqual(
            self.tamulevicius_1["candidateName"], self.tamulevicius_2["candidateName"]
        )
        self.assertNotEqual(
            self.tamulevicius_1["source"]["candidateSourceUrl"],
            self.tamulevicius_2["source"]["candidateSourceUrl"],
        )
        self.assertEqual(
            self.tamulevicius_1["rawData"]["candidacy"]["municipalityName"], "Alytaus miesto"
        )
        self.assertEqual(
            self.tamulevicius_2["rawData"]["candidacy"]["municipalityName"], "Druskininkų miesto"
        )


if __name__ == "__main__":
    unittest.main()
