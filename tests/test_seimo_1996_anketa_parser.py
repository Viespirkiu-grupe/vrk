import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_1996.anketa_parser import parse_anketa_samples
from scraper.shared.seimo_archive_1990s import extract_biography_birth_date


class Seimo1996AnketaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.asmolkov = self._parse_into_tmp("asmolkov-vasilij")
        self.butkevicius = self._parse_into_tmp("butkevicius-audrius")
        self.andriukaitis = self._parse_into_tmp("andriukaitis-vytenis-povilas")
        self.saltiene = self._parse_into_tmp("saltiene-irena")
        self.astrauskas = self._parse_into_tmp("astrauskas-vytautas")

    def _parse_into_tmp(self, candidate_id: str) -> dict:
        self._tmp = getattr(self, "_tmp", None) or tempfile.TemporaryDirectory()
        output_root = Path(self._tmp.name)
        results = parse_anketa_samples(candidate_ids=[candidate_id], output_root=output_root)
        self.assertEqual(results[0]["anomalies"], [], f"{candidate_id}: {results[0]['anomalies']}")
        return json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        tmp = getattr(self, "_tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def test_top_level_fields(self) -> None:
        self.assertEqual(self.asmolkov["electionId"], "1996-spalio-20-seimo")
        self.assertEqual(self.asmolkov["candidateId"], "asmolkov-vasilij")
        # The listing prints "Pavardė, vardas" (surname first); candidateName
        # takes the candidate page's given-name-first heading instead, so a
        # name is comparable with the modern eras. candidateId still comes
        # from the listing slug, so record filenames are unaffected.
        self.assertEqual(self.asmolkov["candidateName"], "Vasilij Asmolkov")
        self.assertEqual(self.asmolkov["candidateId"], "asmolkov-vasilij")
        self.assertTrue(
            self.asmolkov["source"]["candidateSourceUrl"].endswith("kandvl.htm-17109.htm")
        )

    def test_record_section_order(self) -> None:
        self.assertEqual(
            list(self.asmolkov["rawData"].keys()),
            ["profile", "candidacies", "residence", "biography", "declaration"],
        )
        # `anketa` keeps the corpus's position right after `profilis`. Asmolkov's
        # biography gives a year only, so his anketa holds `gimimo-metai` alone.
        self.assertEqual(
            list(self.asmolkov["normalized"].keys()),
            [
                "profilis",
                "anketa",
                "kandidatavimas",
                "gyvenamoji-vieta",
                "biografija",
                # The kpdl.htm declaration, read into the corpus-wide key.
                "turto-ir-pajamu-deklaracijos",
            ],
        )
        # A candidate whose biography page is missing gets no anketa at all,
        # rather than an empty one. The declaration is a separate page and is
        # read regardless.
        self.assertEqual(
            list(self.astrauskas["normalized"].keys()),
            [
                "profilis",
                "kandidatavimas",
                "gyvenamoji-vieta",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
            ],
        )

    def test_dual_candidacy_carries_both_single_and_multi_mandate_entries(self) -> None:
        # Asmolkov ran both in his single-member constituency and on his
        # party's multi-mandate ("Daugiamandatė") list, at position 60.
        candidacies = self.asmolkov["rawData"]["candidacies"]
        self.assertEqual(len(candidacies), 2)
        self.assertEqual(candidacies[0]["apygardaName"], "Naujamiesčio")
        self.assertEqual(candidacies[0]["apygardaNumber"], 1)
        self.assertIsNone(candidacies[0]["listNumber"])
        self.assertEqual(candidacies[1]["apygardaName"], "Daugiamandatė")
        self.assertIsNone(candidacies[1]["apygardaNumber"])
        self.assertEqual(candidacies[1]["listNumber"], 60)
        self.assertEqual(candidacies[1]["nominator"], "Lietuvos ūkio partija")

    def test_self_nominated_candidate_has_no_nominator_link(self) -> None:
        # Butkevičius' listing row reads "Išsikėlė pats" (self-nominated) as
        # plain text, not a link to a party page.
        candidacy = self.butkevicius["rawData"]["candidacies"][0]
        self.assertEqual(candidacy["nominator"], "Išsikėlė pats")
        self.assertEqual(candidacy["nominatorUrl"], "")
        self.assertIsNone(self.butkevicius["normalized"]["kandidatavimas"][0]["iskele-nuoroda"])

    def test_biography_text_is_captured(self) -> None:
        self.assertIn("Gimė 1960", self.butkevicius["rawData"]["biography"]["text"])
        self.assertIn(
            "Gimė 1960", self.butkevicius["normalized"]["biografija"]["tekstas"]
        )

    def test_residence_recovered_from_malformed_html_comment(self) -> None:
        # Regression guard for the "<!--sql format>...-->" comment that
        # swallows the residence line on these archived pages (see
        # scraper/shared/seimo_archive_1990s.py's module docstring).
        self.assertEqual(self.asmolkov["rawData"]["residence"], "Vilnius")
        self.assertEqual(self.asmolkov["normalized"]["gyvenamoji-vieta"], "Vilnius")

    def test_missing_photo_and_biography_normalize_to_null(self) -> None:
        self.assertEqual(self.saltiene["rawData"]["profile"]["photoUrl"], "")
        self.assertIsNone(self.saltiene["normalized"]["profilis"]["nuotrauka"])

        self.assertEqual(self.astrauskas["rawData"]["profile"]["biographyUrl"], "")
        self.assertIsNone(self.astrauskas["rawData"]["biography"])
        self.assertIsNone(self.astrauskas["normalized"]["profilis"]["biografijos-nuoroda"])
        self.assertIsNone(self.astrauskas["normalized"]["biografija"])

    def test_astrauskas_also_ran_on_a_multi_mandate_list(self) -> None:
        candidacies = self.astrauskas["rawData"]["candidacies"]
        self.assertEqual(len(candidacies), 2)
        self.assertEqual(candidacies[1]["apygardaName"], "Daugiamandatė")
        self.assertEqual(candidacies[1]["listNumber"], 20)

class Seimo1996BiographyBirthDateTests(unittest.TestCase):
    """The Seimas archive publishes no birth-date field, so the only one these
    records can have is recovered from the biography's opening sentence."""

    def test_full_date_is_parsed_from_the_genitive_month(self) -> None:
        date, year = extract_biography_birth_date(
            "Andrius KUBILIUS ... Gimė 1956 m. gruodžio 8 d. Vilniuje. Tėvai - ..."
        )
        self.assertEqual(date, "1956-12-08")
        self.assertEqual(year, 1956)

    def test_year_only_sentence_yields_a_year_and_no_date(self) -> None:
        # "Gimė 1950 m." with no month or day. A year is never promoted to a
        # birth date: name+year would merge namesakes wholesale.
        date, year = extract_biography_birth_date("Gimė 1950 m. Baigė Riazanės institutą.")
        self.assertIsNone(date)
        self.assertEqual(year, 1950)

    def test_a_parents_year_later_in_the_text_is_not_taken(self) -> None:
        # Biographies routinely carry other people's years further down
        # ("Tėvas - Vincas Mickus 1926 m. baigė ..."). Only the first Gimė
        # sentence counts, and only its full-date form fixes the date.
        date, year = extract_biography_birth_date(
            "Gimė 1942 m. rugpjūčio 3 d. Panevėžyje. "
            "Tėvas - Vincas Mickus 1926 m. baigė Dotnuvos žemės ūkio akademiją."
        )
        self.assertEqual(date, "1942-08-03")
        self.assertEqual(year, 1942)

    def test_no_birth_sentence_yields_nothing(self) -> None:
        self.assertEqual(extract_biography_birth_date("Klaida užklausoje."), (None, None))
        self.assertEqual(extract_biography_birth_date(""), (None, None))


class Seimo1996BirthDateRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _parse(self, candidate_id: str) -> dict:
        results = parse_anketa_samples(
            candidate_ids=[candidate_id], output_root=Path(self._tmp.name)
        )
        return json.loads(Path(results[0]["outputPath"]).read_text(encoding="utf-8"))

    def test_full_date_lands_in_anketa_with_its_provenance(self) -> None:
        anketa = self._parse("butkevicius-audrius")["normalized"]["anketa"]
        # Written to the corpus's usual key so the person index and dashboard
        # need no special case...
        self.assertEqual(anketa["gimimo-data"], "1960-09-24")
        # ...but flagged, because unlike every other era this is prose-derived.
        self.assertEqual(anketa["gimimo-data-saltinis"], "biografijos-tekstas")

    def test_year_only_candidate_gets_a_year_but_no_birth_date(self) -> None:
        anketa = self._parse("asmolkov-vasilij")["normalized"]["anketa"]
        self.assertEqual(anketa["gimimo-metai"], 1950)
        self.assertNotIn("gimimo-data", anketa)
        self.assertNotIn("gimimo-data-saltinis", anketa)

    def test_candidate_without_a_biography_page_gets_no_anketa_section(self) -> None:
        record = self._parse("astrauskas-vytautas")
        self.assertIsNone(record["rawData"]["biography"])
        self.assertNotIn("anketa", record["normalized"])


if __name__ == "__main__":
    unittest.main()
