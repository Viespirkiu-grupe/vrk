"""The 1998-11-15 Nevėžio re-run — 11 candidates, the complete field.

This is the first election added to the 1996-1998 Seimas archive family since
issue #69 taught the shared parser to read the card's questionnaire, so its
records are born with the full `anketa` rather than needing a second pass. The
coverage test below is the guard on that: it pins what these 11 cards publish,
so a regression in the shared card reader fails here and not silently.
"""

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scraper.elections.seimo_nevezio_1998_lapkricio.anketa_parser import parse_anketa_samples

ELECTION_ID = "1998-lapkricio-15-seimo-pakartotiniai"
CANDIDATE_IDS = (
    "baskas-antanas",
    "ciplyte-joana-viga",
    "daukas-virginijus",
    "davydovas-sergiejus",
    "gudas-kestutis",
    "josas-tomas",
    "krisciunas-edvardas",
    "malukas-edmundas-zenonas",
    "motuzas-algirdas",
    "satkevicius-vitalijus",
    "terleckas-antanas",
)


class SeimoNevezio1998LapkricioAnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.terleckas = self._parse("terleckas-antanas")

    def _parse(self, candidate_id: str) -> dict:
        results = parse_anketa_samples(
            candidate_ids=[candidate_id], output_root=Path(self._tmp.name)
        )
        self.assertEqual(results[0]["anomalies"], [], candidate_id)
        return json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.terleckas["electionId"], ELECTION_ID)
        self.assertEqual(self.terleckas["candidateId"], "terleckas-antanas")
        # The listing prints "Pavardė, vardas"; candidateName takes the card's
        # given-name-first heading, as everywhere else in the corpus.
        self.assertEqual(self.terleckas["candidateName"], "Antanas Terleckas")

    def test_constituency_is_nevezio_26(self) -> None:
        # One constituency, phase 10 -- the whole scope of this re-run.
        candidacies = self.terleckas["rawData"]["candidacies"]
        self.assertEqual(len(candidacies), 1)
        self.assertEqual(candidacies[0]["apygardaName"], "Nevėžio")
        self.assertEqual(candidacies[0]["apygardaNumber"], 26)
        # No multi-mandate list exists in a by-election, so no list number.
        self.assertIsNone(candidacies[0]["listNumber"])

    def test_the_card_questionnaire_is_read(self) -> None:
        anketa = self.terleckas["normalized"]["anketa"]
        self.assertEqual(anketa["tautybe"], "Lietuvis (-ė)")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Rusų", "Lenkų", "Vokiečių"])
        self.assertEqual(anketa["seimine-padetis"], "Vedęs")
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Elena")
        self.assertEqual(anketa["vaiku-vardai-pavardes"], "Gintautas, Ramūnas, Vilija")
        self.assertEqual(
            anketa["pagrindine-darboviete"],
            "Lietuvos gyventojų genocido ir rezistencijos tyrimų centras, asistentas",
        )
        # From the card's "Gimimo vieta", inside the malformed comment, so it
        # carries no prose-source marker.
        self.assertEqual(anketa["gimimo-vieta"], "Krivasalio k. , Ignalinos raj.")
        self.assertNotIn("gimimo-vietos-saltinis", anketa)
        # The date has no card field anywhere in this family; only the
        # biography's opening sentence has it, and it is marked as such.
        self.assertEqual(anketa["gimimo-data"], "1928-02-09")
        self.assertEqual(anketa["gimimo-data-saltinis"], "biografijos-tekstas")

    def test_a_self_nominated_candidate_has_no_nominator_link(self) -> None:
        candidacy = self._parse("baskas-antanas")["rawData"]["candidacies"][0]
        self.assertEqual(candidacy["nominator"], "Išsikėlė pats")
        self.assertEqual(candidacy["nominatorUrl"], "")

    def test_the_complete_field_parses_with_no_anomalies(self) -> None:
        records = {}
        for candidate_id in CANDIDATE_IDS:
            with self.subTest(candidate_id):
                records[candidate_id] = self._parse(candidate_id)
        self.assertEqual(len(records), 11)
        # Every one links a declaration and a biography -- the richest of the
        # three 1998-1999 by-elections in that respect.
        for candidate_id, record in records.items():
            with self.subTest(candidate_id):
                self.assertIsNotNone(record["normalized"]["turto-ir-pajamu-deklaracijos"])
                self.assertIsNotNone(record["normalized"]["biografija"])
                self.assertIsNotNone(record["normalized"]["gyvenamoji-vieta"])

        # What these 11 cards publish, pinned. Born complete because #69
        # landed first; before it every count below except the two birth rows
        # would have been 0.
        counts = Counter()
        for record in records.values():
            for key, value in (record["normalized"].get("anketa") or {}).items():
                if value not in (None, "", [], {}):
                    counts[key] += 1
        self.assertEqual(
            {key: counts[key] for key in sorted(counts)},
            {
                "anksciau-isrinktas": 6,
                "gimimo-data": 6,
                "gimimo-data-saltinis": 6,
                "gimimo-metai": 10,
                "gimimo-vieta": 5,
                "issilavinimas": 10,
                "mokslo-laipsnis": 3,
                "pagrindine-darboviete": 10,
                "pedagoginis-vardas": 2,
                "seimine-padetis": 7,
                "seimos-nariai": 10,
                "sutuoktinio-vardas-pavarde": 8,
                "tautybe": 10,
                "uzsienio-kalbos": 10,
                "vaiku-vardai-pavardes": 9,
                "visuomenine-veikla": 4,
            },
        )
        # No card prints "Ką dar norėtų parašyti apie save" here, so no record
        # carries the key at all.
        self.assertNotIn("kita-apie-save", counts)


if __name__ == "__main__":
    unittest.main()
