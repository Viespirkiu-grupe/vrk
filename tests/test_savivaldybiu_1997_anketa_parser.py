import json
import tempfile
import unittest
from pathlib import Path

from local_data import require

from scraper.elections.savivaldybiu_1997.anketa_parser import (
    DEFAULT_RESULTS_PATH,
    parse_anketa_samples,
)
from scraper.shared.savivaldybiu_archive_1997 import education_record


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
        # This election's declaration pages print a section III total of 0
        # against a non-zero row 1 -- measured on 72 of 84 sampled pages --
        # so a DeclarationTotalBelowItsOwnRow warning is expected here and is
        # asserted on its own in DeclarationTests below. Nothing else should
        # be raised, and nothing at error severity.
        unexpected = [
            a for a in results[0]["anomalies"]
            if a["eventType"] != "DeclarationTotalBelowItsOwnRow"
        ]
        self.assertEqual(unexpected, [])
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



class ElectedStatusTests(unittest.TestCase):
    """`isrinktas`, joined from VRK's per-municipality elected pages (#92).

    The join needs the built results file, so these skip where
    `sitemaps/<id>.results.json` is absent (`python -m scraper build-results`
    produces it); everything above parses fine without it — the candidacy
    then simply carries no `isrinktas` at all.
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
        # Margevičienė led the LPKTS list in Kaunas (Nr. 5) and took one of
        # its seats; the page naming her is the municipality's rikl page.
        candidacy = self._parse("margeviciene-vince-vaidevute")["normalized"]["kandidatavimas"]
        self.assertIs(candidacy["isrinktas"], True)
        self.assertEqual(candidacy["isrinktas-kaip"], "tarybos-narys")
        self.assertEqual(
            candidacy["rezultatu-saltinis"],
            "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/19970323/rikl.htm-148.htm",
        )

    def test_a_non_winner_is_a_known_false(self) -> None:
        candidacy = self._parse("pilvelis-algirdas")["normalized"]["kandidatavimas"]
        self.assertIs(candidacy["isrinktas"], False)
        self.assertNotIn("isrinktas-kaip", candidacy)
        self.assertNotIn("rezultatai-negalioja", candidacy)


class EducationShapeTests(unittest.TestCase):
    """This era's one-word level, carried in the corpus's education object.

    Every election from 2007 on publishes `issilavinimas` as
    `{"aprasas", "irasai": [...]}`. These pages publish a single level from a
    controlled list, which is exactly the modern entry's own `issilavinimas`
    field -- so it goes there rather than staying the corpus's one concept
    with two shapes.
    """

    def test_a_level_becomes_a_single_entry_in_the_corpus_object(self):
        self.assertEqual(
            education_record("Aukštasis"),
            {
                "aprasas": None,
                "irasai": [
                    {
                        "issilavinimas": "Aukštasis",
                        "mokymo-istaigos-pavadinimas": None,
                        "specialybe": None,
                        "baigimo-metai": None,
                    }
                ],
            },
        )

    def test_every_level_this_era_publishes_is_carried_through(self):
        # The eight values the 6,276-record general election actually uses.
        for level in (
            "Aukštasis", "Aukštesnysis", "Specialus vidurinis", "Vidurinis",
            "Nebaigtas aukštasis", "Nebaigtas vidurinis", "Aspirantūra",
            "Doktorantūra",
        ):
            with self.subTest(level):
                record = education_record(level)
                self.assertEqual(record["irasai"][0]["issilavinimas"], level)

    def test_no_education_stays_null_rather_than_an_empty_object(self):
        self.assertIsNone(education_record(""))
        self.assertIsNone(education_record(None))

    def test_a_parsed_record_carries_the_object_shape(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        results = parse_anketa_samples(
            candidate_ids=["pilvelis-algirdas"], output_root=Path(tmp.name)
        )
        record = json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))
        value = record["normalized"]["anketa"]["issilavinimas"]
        self.assertIsInstance(value, dict)
        self.assertEqual(sorted(value), ["aprasas", "irasai"])


class DeclarationTests(unittest.TestCase):
    """The kpdl.htm declaration, now read into the corpus's usual key.

    This election is the one whose section III total renders 0 against a
    non-zero row 1 -- 72 of 84 sampled pages -- so it is where the
    "a total its own row contradicts is not a total" rule earns its keep.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        results = parse_anketa_samples(
            candidate_ids=["tamulevicius-kestutis"], output_root=Path(self._tmp.name)
        )
        self.result = results[0]
        self.record = json.loads(
            Path(self.result["outputPath"]).read_text(encoding="utf-8")
        )
        self.declaration = self.record["normalized"]["turto-ir-pajamu-deklaracijos"]

    def test_the_declaration_lands_in_the_corpus_wide_key(self):
        self.assertIn("turto-ir-pajamu-deklaracijos", self.record["normalized"])

    def test_figures_are_litas_so_the_corpus_conversion_applies(self):
        self.assertEqual(self.declaration["valiuta"], "Lt")

    def test_the_combined_section_totals_are_present(self):
        # Float, not int: issue #101 made money a property of the column
        # rather than of whether this candidate's figure happened to be whole.
        for key in (
            "turtas-ir-pinigines-lesos-metu-pradzioje",
            "turtas-ir-pinigines-lesos-metu-pabaigoje",
            "kalendoriniais-metais-isigytas-turtas",
        ):
            with self.subTest(key):
                self.assertIsInstance(self.declaration[key], float)

    def test_the_modern_split_keys_are_null_not_invented(self):
        self.assertIsNone(self.declaration["privalomas-registruoti-turtas"])
        self.assertIsNone(self.declaration["pinigines-lesos"])

    def test_the_employment_row_is_published(self):
        self.assertEqual(self.declaration["gautos-pajamos-darbo-santykiu"], 2589)

    def test_the_contradicted_total_is_refused_and_flagged(self):
        self.assertIsNone(self.declaration["gautos-pajamos"])
        events = [
            a for a in self.result["anomalies"]
            if a["eventType"] == "DeclarationTotalBelowItsOwnRow"
        ]
        self.assertTrue(events)
        self.assertEqual(events[0]["electionId"], "1997-kovo-23-savivaldybiu-tarybu")
        self.assertEqual(events[0]["stage"], "parse")
        self.assertEqual(events[0]["detail"]["row1Employment"], 2589)
        self.assertEqual(events[0]["detail"]["row20Total"], 0)


if __name__ == "__main__":
    unittest.main()
