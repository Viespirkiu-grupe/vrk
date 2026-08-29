"""Elected status derived from the profile's prose note (issue #100).

The 2016-2025 candidate pages publish no results tree; their only elected
signal is `profilis.pastaba` ("Išrinktas pagal sąrašą", "Išrinkta
vienmandatėje Zanavykų (Nr.64) apygardoje II ture", …). Measured across the
corpus the notes name the complete winner set — 141 of 141 Seimas seats in
2016, 2020 and 2024, 11 of 11 EP seats in 2019 and 2024 — so
`candidacy_from_elected_note` turns them into the minimal `kandidatavimas`
block the results-joined elections already carry, with `isrinktas: false` a
real statement on the noteless records.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.meru_2025.anketa_parser import (
    parse_anketa_sample as parse_meru_2025_sample,
)
from scraper.elections.prezidento_2024.anketa_parser import (
    parse_anketa_sample as parse_prezidento_2024_sample,
)
from scraper.elections.seimo_2016.anketa_parser import (
    parse_anketa_sample as parse_seimo_2016_sample,
)
from scraper.elections.seimo_2024.anketa_parser import (
    parse_anketa_sample as parse_seimo_2024_sample,
)
from scraper.shared.election_results import candidacy_from_elected_note


class CandidacyFromElectedNoteTests(unittest.TestCase):
    def test_seat_forms(self) -> None:
        cases = [
            ("Išrinktas pagal sąrašą", {"isrinktas": True, "isrinktasKaip": "daugiamandate"}),
            (
                "Išrinkta pagal Tėvynės sąjungos - Lietuvos krikščionių demokratų sąrašą",
                {"isrinktas": True, "isrinktasKaip": "daugiamandate"},
            ),
            (
                "Išrinktas vienmandatėje Gargždų (Nr. 31) apygardoje II ture",
                {"isrinktas": True, "isrinktasKaip": "vienmandate"},
            ),
            (
                "Išrinkta Marijampolės (Nr.25) savivaldybėje II ture",
                {"isrinktas": True, "isrinktasKaip": "meras"},
            ),
            ("Išrinktas II ture", {"isrinktas": True, "isrinktasKaip": "prezidentas"}),
        ]
        for note, expected in cases:
            with self.subTest(note):
                self.assertEqual(candidacy_from_elected_note(note), expected)

    def test_non_winner_notes_and_blanks(self) -> None:
        for note in ("Dalyvavo I ture", "Dalyvavo II ture", "", None):
            with self.subTest(repr(note)):
                self.assertEqual(candidacy_from_elected_note(note), {"isrinktas": False})

    def test_unrecognised_winner_prose_keeps_the_win(self) -> None:
        self.assertEqual(
            candidacy_from_elected_note("Išrinktas kokiu nors nauju būdu"),
            {"isrinktas": True, "isrinktasKaip": None},
        )


def _parse(parse, candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse(candidate_id, output_root=Path(tmp))
        return json.loads(output_path.read_text(encoding="utf-8"))


class FixtureRecordsCarryTheBlockTests(unittest.TestCase):
    def test_list_winner_2016(self) -> None:
        record = _parse(parse_seimo_2016_sample, "algirdas-butkevicius")
        self.assertEqual(record["kandidatavimas"], {"isrinktas": True, "isrinktasKaip": "daugiamandate"})

    def test_constituency_winner_2024(self) -> None:
        record = _parse(parse_seimo_2024_sample, "algirdas-butkevicius")
        self.assertEqual(record["kandidatavimas"], {"isrinktas": True, "isrinktasKaip": "vienmandate"})

    def test_mayor_winner_2025(self) -> None:
        record = _parse(parse_meru_2025_sample, "gediminas-cepulis")
        self.assertEqual(record["kandidatavimas"], {"isrinktas": True, "isrinktasKaip": "meras"})

    def test_first_round_participant_is_not_elected(self) -> None:
        record = _parse(parse_prezidento_2024_sample, "andrius-mazuronis")
        self.assertEqual(record["kandidatavimas"], {"isrinktas": False})


if __name__ == "__main__":
    unittest.main()
