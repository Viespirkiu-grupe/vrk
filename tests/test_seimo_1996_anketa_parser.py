import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_1996.anketa_parser import parse_anketa_samples


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
            ["profile", "candidacies", "residence", "biography"],
        )
        self.assertEqual(
            list(self.asmolkov["normalized"].keys()),
            ["profilis", "kandidatavimas", "gyvenamoji-vieta", "biografija"],
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

if __name__ == "__main__":
    unittest.main()
