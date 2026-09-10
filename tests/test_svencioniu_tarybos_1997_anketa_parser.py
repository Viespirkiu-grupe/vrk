import json
import tempfile
import unittest
from pathlib import Path

from local_data import require

from scraper.elections.svencioniu_tarybos_1997.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    parse_anketa_samples,
)


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
        # `anketa` before `kandidatavimas` since issue #144: this module used
        # to emit them the other way round, which made its 6,386 records the
        # only ones in the corpus to interleave a section between `profilis`
        # and `anketa` -- against its own sibling `seimo_archive_1990s.py`,
        # which emits `profilis|anketa|kandidatavimas` for the other 950
        # records of the same era. `tests/test_record_shape.py` holds the one
        # order over the whole corpus.
        self.assertEqual(
            list(self.lauzadis["normalized"].keys()),
            ["profilis", "anketa", "kandidatavimas", "turto-ir-pajamu-deklaracijos"],
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


class ElectedStatusTests(unittest.TestCase):
    """`isrinktas`, joined from the one rikl page this election has (#92).

    Skips where `sitemaps/<id>.results.json` is absent (`python -m scraper
    build-results` produces it); the parses above then simply carry no
    `isrinktas` key at all.
    """

    def setUp(self) -> None:
        require(DEFAULT_RESULTS_PATH)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _parse(self, candidate_id: str) -> dict:
        results = parse_anketa_samples(
            candidate_ids=[candidate_id], output_root=Path(self._tmp.name)
        )
        return json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))

    def test_a_winner_carries_the_seat_and_the_source(self) -> None:
        # Klipčius led the LLS list, which took 10 of the 25 seats.
        candidacy = self._parse("klipcius-rimas")["normalized"]["kandidatavimas"]
        self.assertIs(candidacy["isrinktas"], True)
        self.assertEqual(candidacy["isrinktas-kaip"], "tarybos-narys")
        self.assertEqual(
            candidacy["rezultatu-saltinis"],
            "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/19970323/rikl.htm-264.htm",
        )

    def test_a_non_winner_is_a_known_false(self) -> None:
        # Laužadis led the tautininkai list, which won no seat ("-" in the
        # mandate column) — a stated nothing, so false, not null.
        candidacy = self._parse("lauzadis-sarunas")["normalized"]["kandidatavimas"]
        self.assertIs(candidacy["isrinktas"], False)
        self.assertNotIn("isrinktas-kaip", candidacy)
        # The invalidation belongs to the *March* election's records only.
        self.assertNotIn("rezultatai-negalioja", candidacy)


if __name__ == "__main__":
    unittest.main()
