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
        self.assertEqual(self.pilvelis["candidateName"], "Algirdas Pilvelis")

    def test_candidacy_and_personal_fields(self) -> None:
        candidacy = self.pilvelis["rawData"]["candidacy"]
        self.assertEqual(candidacy["municipalityName"], "Vilniaus miesto")
        self.assertEqual(candidacy["municipalityNumber"], 1)
        self.assertEqual(candidacy["nominator"], "Lietuvos reformų partija")
        self.assertEqual(candidacy["listNumber"], 1)

        personal = self.pilvelis["rawData"]["personal"]
        self.assertEqual(personal["birthDate"], "1944-03-04")
        self.assertEqual(personal["residence"], "Vilnius")
        # A field genuinely absent from this candidate's page (no "Tautybė:"
        # line at all) normalizes to null rather than an empty string.
        self.assertIsNone(self.pilvelis["normalized"]["anketa"]["tautybe"])

    def test_birth_date_is_iso_and_does_not_swallow_the_next_label(self) -> None:
        # abariunas-bronius's page prints no "Gimimo vieta" line. Stopping only
        # at that one label let the birth date run to the end of the paragraph,
        # producing "1951 03 08 Gyvenamoji vieta: Vilnius Tautybė: ..." on 91%
        # of this election's records. It must stop at whichever label is next.
        abariunas = self._parse("abariunas-bronius")
        anketa = abariunas["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-data"], "1951-03-08")
        self.assertIsNone(anketa["gimimo-vieta"])
        self.assertEqual(anketa["gyvenamoji-vieta"], "Vilnius")
        self.assertEqual(anketa["tautybe"], "Lietuvis (-ė)")
        for key, value in anketa.items():
            if isinstance(value, str):
                self.assertNotIn(":", value, f"{key} swallowed a following label")

    def test_birth_date_format_matches_the_rest_of_the_corpus(self) -> None:
        # Every era from 2015 on writes anketa.gimimo-data as YYYY-MM-DD; the
        # source here prints "1944 03 04". Without normalizing, the person
        # index keys on "NAME|1944 03 04" and can never match a later
        # election's "NAME|1944-03-04" — 949 people would stay split.
        self.assertEqual(self.pilvelis["normalized"]["anketa"]["gimimo-data"], "1944-03-04")
        self.assertEqual(self.pilvelis["rawData"]["personal"]["birthDate"], "1944-03-04")

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
