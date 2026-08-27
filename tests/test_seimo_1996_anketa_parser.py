import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_1996.anketa_parser import parse_anketa_samples
from scraper.shared.seimo_archive_1990s import (
    extract_biography_birth_date,
    extract_biography_birth_place,
    nominative_place,
)


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
            ["profile", "candidacies", "residence", "personal", "biography", "declaration"],
        )
        # `anketa` keeps the corpus's position right after `profilis`. Asmolkov
        # answered none of the card's questions, so his anketa holds only the
        # `gimimo-metai` his biography's opening sentence gives.
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
        self.assertEqual(list(self.asmolkov["normalized"]["anketa"].keys()), ["gimimo-metai"])
        # Astrauskas has no biography page at all, and used to get no anketa
        # for that reason -- the card's own questionnaire is where the rest of
        # this era's per-candidate data actually lives.
        self.assertIsNone(self.astrauskas["rawData"]["biography"])
        self.assertEqual(
            list(self.astrauskas["normalized"].keys()),
            [
                "profilis",
                "anketa",
                "kandidatavimas",
                "gyvenamoji-vieta",
                "biografija",
                "turto-ir-pajamu-deklaracijos",
            ],
        )

    def test_card_questionnaire_lands_under_the_corpus_anketa_keys(self) -> None:
        # Astrauskas' card fills in most of the questionnaire. Every key here
        # is the name the 2015/2016 eras use, so the concept map, the
        # dashboard's field map and the person index resolve them unchanged.
        anketa = self.astrauskas["normalized"]["anketa"]
        self.assertEqual(anketa["tautybe"], "Lietuvis (-ė)")
        self.assertEqual(anketa["mokslo-laipsnis"], "Habilituotas medicinos mokslų daktaras")
        self.assertEqual(anketa["pedagoginis-vardas"], "Profesorius")
        self.assertEqual(anketa["uzsienio-kalbos"], ["Rusų", "Anglų", "Vokiečių"])
        self.assertEqual(anketa["seimine-padetis"], "Vedęs")
        # "Buvo išrinktas į ... Aukščiausiąją Tarybą, Seimą, savivaldybių
        # tarybas" names bodies with no term dates, so `laikotarpis` is null
        # exactly as the 2000 Seimas card's entries are.
        self.assertEqual(
            anketa["anksciau-isrinktas"],
            {
                "aprasas": None,
                "irasai": [
                    {
                        "institucijos-pavadinimas-pareigos": "Lietuvos Respublikos Seimas",
                        "laikotarpis": None,
                    }
                ],
            },
        )
        # A label the candidate left blank yields no key at all, rather than a
        # null: the record says what the card carried.
        for absent in ("issilavinimas", "pagrindine-darboviete", "visuomenine-veikla"):
            with self.subTest(absent):
                self.assertNotIn(absent, anketa)

    def test_two_previous_mandates_become_two_entries(self) -> None:
        # One <b> per body: Andriukaitis sat in both.
        self.assertEqual(
            [
                entry["institucijos-pavadinimas-pareigos"]
                for entry in self.andriukaitis["normalized"]["anketa"]["anksciau-isrinktas"]["irasai"]
            ],
            ["Lietuvos Respublikos Aukščiausioji Taryba", "Lietuvos Respublikos Seimas"],
        )

    def test_education_level_takes_the_modern_entry_shape(self) -> None:
        # The card publishes one level from a controlled list, which is the
        # modern form's per-entry `issilavinimas` field -- not its free-text
        # `aprasas`. Same call the 1997 municipal family made.
        self.assertEqual(
            self.andriukaitis["normalized"]["anketa"]["issilavinimas"],
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

    def test_family_members_split_into_the_two_keyed_roles(self) -> None:
        anketa = self.butkevicius["normalized"]["anketa"]
        self.assertEqual(anketa["sutuoktinio-vardas-pavarde"], "Vilija")
        self.assertEqual(anketa["vaiku-vardai-pavardes"], "Aušrinė, Vytenis")
        self.assertEqual(
            anketa["seimos-nariai"],
            [
                {"name": "Vilija", "relation": "Sutuoktinis/sutuoktinė"},
                {"name": "Aušrinė", "relation": "Vaikas"},
                {"name": "Vytenis", "relation": "Vaikas"},
            ],
        )

    def test_nationality_recovered_from_the_malformed_comment(self) -> None:
        # Tautybė sits inside the same "<!--sql format>...-->" comment as the
        # residence and the birthplace, so it is invisible to a DOM parser and
        # only a regex over the raw HTML reaches it.
        self.assertEqual(self.butkevicius["rawData"]["personal"]["nationality"], "Lietuvis (-ė)")
        self.assertEqual(self.butkevicius["normalized"]["anketa"]["tautybe"], "Lietuvis (-ė)")
        # Šaltienė's card leaves it blank; a blank field yields no key.
        self.assertEqual(self.saltiene["rawData"]["personal"]["nationality"], "")
        self.assertNotIn("tautybe", self.saltiene["normalized"]["anketa"])

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

    def test_the_results_join_marks_the_won_seat_only(self) -> None:
        # Andriukaitis won Žirmūnų in the runoff; his list candidacy is a
        # known false and carries the ranking figures instead of votes.
        constituency, party_list = self.andriukaitis["normalized"]["kandidatavimas"]
        self.assertTrue(constituency["isrinktas"])
        self.assertEqual(constituency["isrinktas-kaip"], "vienmandate")
        self.assertEqual(constituency["rezultatu-turas"], 2)
        self.assertTrue(constituency["rezultatu-saltinis"].endswith("rsnl.htm-1.htm"))
        self.assertEqual([r["turas"] for r in constituency["turai"]], [1, 2])
        self.assertEqual(constituency["turai"][1]["balsai"], 10746)
        self.assertIs(party_list["isrinktas"], False)
        self.assertNotIn("turai", party_list)
        self.assertEqual(party_list["porinkiminis-numeris-sarase"], 17)
        self.assertEqual(party_list["teigiami-balsai"], 1739)

    def test_a_candidate_who_won_nothing_is_false_on_every_candidacy(self) -> None:
        candidacies = self.asmolkov["normalized"]["kandidatavimas"]
        self.assertEqual([c["isrinktas"] for c in candidacies], [False, False])
        self.assertEqual(candidacies[0]["turai"][0]["vieta"], 8)

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

    def test_candidate_without_a_biography_page_still_gets_the_card_anketa(self) -> None:
        # No biography means no birth date -- there is no date anywhere else on
        # these pages -- but the card's own questionnaire is unaffected.
        record = self._parse("astrauskas-vytautas")
        self.assertIsNone(record["rawData"]["biography"])
        self.assertNotIn("gimimo-data", record["normalized"]["anketa"])
        self.assertNotIn("gimimo-metai", record["normalized"]["anketa"])
        self.assertEqual(record["normalized"]["anketa"]["pedagoginis-vardas"], "Profesorius")



class BirthPlaceFromBiographyTests(unittest.TestCase):
    """The prose birthplace, now the *fallback* for the 9 records of this
    family whose card leaves "Gimimo vieta" blank (7 of them people born
    outside Lithuania -- Rusija, Ukraina, Krasnojarsko kraštas).

    The card does publish the field, inside the malformed comment; the first
    pass over these pages missed it and read the biography instead. The
    extractor stays because it still covers those 9, and because the 2002 and
    2004 presidential families -- Word-document sources with no card at all --
    import it.

    The sentence prints the place in the locative ("Kaune", "Klaipėdoje")
    while the rest of the corpus stores the nominative, and suffix rules alone
    cannot convert it -- "-yje" yields both Panevėžys and Radviliškis. So
    candidates are checked against scraper/shared/vietovardziai.json, and that
    lookup is what keeps a mis-parse out of the record.
    """

    def test_a_city_in_the_locative_becomes_the_nominative(self):
        self.assertEqual(
            extract_biography_birth_place("Gimė 1955 m. rugsėjo 8 d. Klaipėdoje."),
            "Klaipėda",
        )

    def test_the_family_background_clause_is_not_a_place(self):
        # "Gimė ... Vilniuje, tarnautojų šeimoje" — the place ends at the comma.
        self.assertEqual(
            extract_biography_birth_place(
                "Gimė 1947 m. gegužės 11 d. Vilniuje, tarnautojų šeimoje."
            ),
            "Vilnius",
        )

    def test_a_sentence_naming_only_a_background_yields_nothing(self):
        self.assertIsNone(
            extract_biography_birth_place("Gimė 1946 m. sausio 20 d. darbininkų šeimoje.")
        )

    def test_the_vocabulary_settles_what_suffix_rules_cannot(self):
        # Both end in -yje and the ending alone does not say which.
        self.assertEqual(nominative_place("Panevėžyje"), "Panevėžys")
        self.assertEqual(nominative_place("Radviliškyje"), "Radviliškis")

    def test_plural_and_district_forms(self):
        self.assertEqual(nominative_place("Zarasuose"), "Zarasai")
        self.assertEqual(nominative_place("Šiauliuose"), "Šiauliai")
        self.assertEqual(nominative_place("Pakruojo rajone"), "Pakruojo rajonas")

    def test_a_misparse_resolves_to_nothing_rather_than_a_wrong_place(self):
        # Real fragments this used to pick up before the vocabulary check.
        for fragment in ("Lietuvė", "1976 m", "Bobriškių kaime", "Adutiškio parapijoje"):
            with self.subTest(fragment):
                self.assertIsNone(nominative_place(fragment))

    def test_the_country_is_refused_as_too_coarse(self):
        # "Gimė ... Lietuvoje" resolves but says nothing, and was wrong on all
        # three candidates who had a specific birthplace published elsewhere.
        self.assertIsNone(nominative_place("Lietuvoje"))

    def _anketa(self, candidate_id: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            results = parse_anketa_samples(candidate_ids=[candidate_id], output_root=Path(tmp))
            return json.loads(
                Path(results[0]["outputPath"]).read_text(encoding="utf-8")
            )["normalized"]["anketa"]

    def test_the_card_field_wins_and_carries_no_source_marker(self):
        # Butkevičius' card and biography agree on Kaunas. The marker is what
        # says "prose-derived, weaker than a published field", so a card value
        # must not carry it -- its absence is what makes this record read like
        # every other era's.
        anketa = self._anketa("butkevicius-audrius")
        self.assertEqual(anketa["gimimo-vieta"], "Kaunas")
        self.assertNotIn("gimimo-vietos-saltinis", anketa)

    def test_the_card_wins_even_where_it_is_more_specific_than_the_prose(self):
        # The prose gave "Plungės rajonas"; the card names the village too.
        # Across the family the two agree on 433 of 438 such records.
        self.assertEqual(
            self._anketa("astrauskas-vytautas")["gimimo-vieta"], "Macenių k. , Plungės raj."
        )

    def test_a_candidate_with_neither_source_gets_no_key(self):
        anketa = self._anketa("asmolkov-vasilij")
        self.assertNotIn("gimimo-vieta", anketa)
        self.assertNotIn("gimimo-vietos-saltinis", anketa)


if __name__ == "__main__":
    unittest.main()
