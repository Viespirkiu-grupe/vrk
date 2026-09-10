"""The corpus-wide value rules, and the shapes issue #101 measured them against.

Every example here is a value the corpus actually held on 2026-08-29, so a
change that breaks one of these is a change to what the corpus says, not to a
made-up case.
"""

import unittest

from scraper.shared.values import (
    as_money,
    candidate_status_note,
    clean_value,
    collapse_repeated_date,
    interest_row_columns,
    is_missing_marker,
    is_refusal,
    parse_money,
    repair_lost_open_quote,
    repair_lost_punctuation,
    split_object_and_date,
    strip_trailing_separator,
)


class TrailingSeparatorTests(unittest.TestCase):
    def test_the_separator_that_separates_nothing_goes(self):
        # 2019-kovo-3 anketa.vaiku-vardai-pavardes, and 1,371 more like it.
        self.assertEqual(
            strip_trailing_separator("Jonas, Rasa, Živilė, Jovita,"),
            "Jonas, Rasa, Živilė, Jovita",
        )

    def test_a_semicolon_list_loses_only_its_tail(self):
        # 1996-spalio-20 anketa.visuomenine-veikla.
        self.assertEqual(
            strip_trailing_separator(
                "Lietuvių tautininkų sąjunga,valdybos narys;"
                "Lietuvos ūkininkų sąjunga,tarybos narys;"
            ),
            "Lietuvių tautininkų sąjunga,valdybos narys;"
            "Lietuvos ūkininkų sąjunga,tarybos narys",
        )

    def test_repeated_and_spaced_separators_all_go(self):
        self.assertEqual(strip_trailing_separator("Šiaulių dramos teatras , ;"), "Šiaulių dramos teatras")

    def test_a_sentence_keeps_its_full_stop(self):
        self.assertEqual(
            strip_trailing_separator("VšĮ Šiaulių universiteto gimnazija, projektų būrelio vadovė."),
            "VšĮ Šiaulių universiteto gimnazija, projektų būrelio vadovė.",
        )


class ReplacementCharacterTests(unittest.TestCase):
    def test_an_opening_quote_is_restored_where_a_closing_one_proves_it(self):
        # 2004-seimo anketa.pagrindine-darboviete. VRK serves the replacement
        # character itself; only the opening quote is restored, because the
        # plain `"` that closes the phrase is what VRK published.
        self.assertEqual(
            repair_lost_open_quote('AB �Lietuvos geležinkeliai"'),
            'AB „Lietuvos geležinkeliai"',
        )

    def test_an_opening_quote_followed_by_a_space_is_restored_too(self):
        # 2004-seimo anketa.pagrindine-darboviete and
        # privaciu-interesu-deklaracija …darboviete: VRK left a space after
        # the quote, and the rule's `\S` lookahead skipped both (issue #164).
        self.assertEqual(
            repair_lost_punctuation('AB � Vakarų skirstomieji tinklai"'),
            'AB „ Vakarų skirstomieji tinklai"',
        )

    def test_a_closing_quote_is_restored_where_the_opening_one_proves_it(self):
        # The mirror of the rule above, and 15 of the corpus's 30 broken
        # characters — every one the closing half of a pair the value itself
        # carries. The surviving glyph decides which one is written back.
        self.assertEqual(
            repair_lost_punctuation('dirba UAB "La-Nika Baltic Ltd� deklarantu'),
            'dirba UAB "La-Nika Baltic Ltd" deklarantu',
        )
        self.assertEqual(
            repair_lost_punctuation("„Vilniaus pirmoji autotransporto įmonė� naujų projektų vadovu"),
            "„Vilniaus pirmoji autotransporto įmonė“ naujų projektų vadovu",
        )

    def test_an_opening_bracket_is_restored_where_its_closing_one_is_there(self):
        # 2004-seimo anketa.politine-organizacija. This used to be the
        # test's example of a character that "could stand for anything" —
        # over a value carrying the closing bracket four characters later.
        self.assertEqual(
            repair_lost_punctuation(
                "Tėvynės Sąjunga (LK), Tėvynės liaudies partija �TLP) Dešiniųjų sąjunga (DS)"
            ),
            "Tėvynės Sąjunga (LK), Tėvynės liaudies partija (TLP) Dešiniųjų sąjunga (DS)",
        )

    def test_a_destroyed_letter_is_not_guessed_at(self):
        # The class that is left: 12 characters on nine 2000-seimo
        # biographies, every one of them `š` on the evidence of the word it
        # sits inside. Not repaired, because a rule that turned an in-word
        # replacement into `š` would be right on all twelve and wrong the
        # first time the lost byte was a `ž` (issue #164).
        for value in ("1993 m. buvo i�rinktas Tėvynės sąjungos", "Roki�kio rajono tarybos narys"):
            with self.subTest(value):
                self.assertEqual(repair_lost_punctuation(value), value)

    def test_a_value_that_is_only_a_replacement_character_is_missing(self):
        # 30 records, 28 of them in 2008-seimo: the biography div holds a NUL
        # byte, which the HTML parser renders as U+FFFD. There is no biography.
        self.assertTrue(is_missing_marker("�"))
        self.assertIsNone(clean_value("�"))

    def test_the_dash_a_page_prints_for_an_unanswered_field_is_missing(self):
        self.assertTrue(is_missing_marker("-"))
        self.assertFalse(is_missing_marker("-5"))


class PunctuationOnlyTests(unittest.TestCase):
    """A value made only of punctuation is not an answer (issue #164).

    207 of them survived in 194 records across 14 elections: `"."` 89,
    `"-,-"` 73, `"-, -"` 28, `"–"` 7 and six more literals. The one module
    that noticed wrote `value.strip(" ,")`, which catches a bare comma and
    not the `-,-` a candidate who dashed *both* halves of question 16
    produced — and the other 41 modules had nothing.
    """

    def test_every_literal_the_corpus_held(self):
        for value in (".", "-,-", "-, -", "–", "..", "...", "....", ",-", "., .", ". ."):
            with self.subTest(value):
                self.assertTrue(is_missing_marker(value))
                self.assertIsNone(clean_value(value))

    def test_a_value_with_a_word_in_it_is_untouched(self):
        # `is_missing_marker` asks whether a value is *entirely* marks.
        for value in ("Vilnius, LT", "UAB -Termoizoliacija-", "1-2", "-5", "A.", "Nr. 3"):
            with self.subTest(value):
                self.assertFalse(is_missing_marker(value))
                self.assertIsNotNone(clean_value(value))


class RefusalTests(unittest.TestCase):
    """VRK's own refusal token is a word, not punctuation (issue #164).

    It appears 185,939 times in `rawData` across 43 elections and every
    era's normalizer folds it to null — except the 1996 Seimas archive card,
    where 20 reached `normalized`: 18 as a marital status and 2 as an entry
    of `anksciau-isrinktas`, so the corpus asserted a prior mandate for two
    candidates who had declined to answer.
    """

    def test_the_token_and_its_variants(self):
        for value in ("Nenurodė", "nenurodė", "  Nenurodė  ", "Nenurodyta", "NENURODĖ"):
            with self.subTest(value):
                self.assertTrue(is_refusal(value))

    def test_a_real_answer_is_not_a_refusal(self):
        for value in ("Nesusituokęs", "Vedęs", "Nenurodė savo pareigų", None, 5, ""):
            with self.subTest(repr(value)):
                self.assertFalse(is_refusal(value))

    def test_clean_value_leaves_the_refusal_alone(self):
        # Deliberately: `clean_value`'s output is also what lands in
        # `rawData`, which the docs promise keeps the text VRK published. The
        # refusal is filtered at the normalizer boundary instead.
        self.assertEqual(clean_value("Nenurodė"), "Nenurodė")


class CandidateStatusNoteTests(unittest.TestCase):
    """A trailing parenthetical on a listing name (issue #164).

    Measured across every retained listing page of all 55 elections: 25
    distinct forms, and exactly six occurrences say something about the
    *candidate* rather than about the ballot. Two 2016-seimo candidates lost
    theirs to `clean_candidate_name` with nothing keeping it, so the corpus
    said a candidate who died before polling day and one whose registration
    was revoked were ordinary losing candidates.
    """

    def test_the_six_status_markers_the_listings_hold(self):
        for raw, expected in (
            ("Kęstas KOMSKIS (panaikinta kandidato registracija)", "panaikinta kandidato registracija"),
            ("Juras POŽELA (mirė)", "mirė"),
            ("Vardenis PAVARDENIS (išbrauktas - Seimo nutarimu)", "išbrauktas - Seimo nutarimu"),
            ("Vardenė PAVARDENĖ (išbraukta - Seimo nutarimu)", "išbraukta - Seimo nutarimu"),
        ):
            with self.subTest(raw):
                self.assertEqual(candidate_status_note(raw), expected)

    def test_what_the_ballot_says_is_not_a_status(self):
        # The other 24 forms: the 2016 constituency flags on 141 of its 1,415
        # rows, party and coalition names, the mayoral role marker, list
        # numbers, page furniture. A broad rule reads 143 notes out of the
        # 2016 listing where there are two.
        for raw in (
            "Vida AČIENĖ (D)",
            "Valius ĄŽUOLAS (V)",
            "Vardenis PAVARDENIS (liberalai)",
            "Vardenis PAVARDENIS (centristai, tautininkai)",
            "Vardenis PAVARDENIS (kandidatas į savivaldybės merus)",
            "Vardenis PAVARDENIS (Nr.6)",
            "Vardenis PAVARDENIS (Lietuvos konservatoriai)",
            "Vardenis PAVARDENIS",
        ):
            with self.subTest(raw):
                self.assertEqual(candidate_status_note(raw), "")

    def test_the_marker_is_matched_as_a_phrase(self):
        # Diacritic- and case-insensitive, so a listing that prints MIRĖ or
        # drops the macron still resolves.
        for raw in ("X Y (MIRĖ)", "X Y (mire)", "X Y (Mirė)"):
            with self.subTest(raw):
                self.assertTrue(candidate_status_note(raw))


class CleanValueTests(unittest.TestCase):
    def test_the_repair_runs_before_the_value_is_judged_empty(self):
        self.assertEqual(clean_value('VĮ �Oro navigacija",'), 'VĮ „Oro navigacija"')

    def test_ordinary_text_is_returned_unchanged(self):
        self.assertEqual(clean_value("Vaikų darželis \"Saulutė\", sargas"), "Vaikų darželis \"Saulutė\", sargas")


class MoneyTests(unittest.TestCase):
    def test_money_is_a_float_whether_or_not_it_has_centai(self):
        self.assertIsInstance(as_money(202000), float)
        self.assertEqual(as_money(17861.65), 17861.65)
        self.assertIsNone(as_money(None))

    def test_a_figure_carrying_its_currency_splits_in_two(self):
        self.assertEqual(parse_money("22000 EUR"), (22000.0, "EUR"))
        self.assertEqual(parse_money("75000 Eur"), (75000.0, "EUR"))

    def test_the_litas_spellings_all_normalize_to_the_corpus_key(self):
        # `Lt` is what turto-ir-pajamu-deklaracijos.valiuta already says.
        self.assertEqual(parse_money("15000 Ltl"), (15000.0, "Lt"))
        self.assertEqual(parse_money("250000 LTL"), (250000.0, "Lt"))

    def test_a_figure_whose_header_names_the_currency_parses_without_one(self):
        self.assertEqual(parse_money("13000"), (13000.0, None))
        self.assertEqual(parse_money("3859,5"), (3859.5, None))
        self.assertEqual(parse_money("1 618 795 Ltl"), (1618795.0, "Lt"))

    def test_something_that_is_not_a_figure_is_not_invented_into_one(self):
        self.assertEqual(parse_money("AB LUMINOR BANKAS"), (None, None))
        self.assertEqual(parse_money(None), (None, None))


class ObjectAndDateTests(unittest.TestCase):
    def test_the_gift_and_its_date_come_apart(self):
        # 2007-vasario-25 vii-gautos-dovanos: VRK heads the column
        # "Dovana, data" and prints both values in the one cell.
        self.assertEqual(
            split_object_and_date("Kaimo sodyba su žeme, 2006-11-01"),
            ("Kaimo sodyba su žeme", "2006-11-01"),
        )

    def test_a_cell_holding_only_a_date_yields_only_a_date(self):
        self.assertEqual(split_object_and_date("2005-01-10"), (None, "2005-01-10"))

    def test_a_year_is_a_date_too(self):
        # 2008-seimo paslauga-data: "Apmokėti liko m, 2007".
        self.assertEqual(split_object_and_date("Apmokėti liko m, 2007"), ("Apmokėti liko m", "2007"))

    def test_a_cell_with_no_date_keeps_its_text(self):
        self.assertEqual(split_object_and_date("paveikslas"), ("paveikslas", None))


class RepeatedDateTests(unittest.TestCase):
    def test_a_date_printed_twice_is_kept_once(self):
        # 2011-vasario-13 vii-sandoriai, in the page's own source.
        self.assertEqual(collapse_repeated_date("2009-12-14 2009-12-14"), "2009-12-14")

    def test_two_different_dates_are_left_alone(self):
        self.assertEqual(collapse_repeated_date("2009-12-14 2010-01-01"), "2009-12-14 2010-01-01")


class InterestRowColumnTests(unittest.TestCase):
    def test_the_money_column_gains_the_currency_it_printed(self):
        self.assertEqual(
            interest_row_columns("sandorio-suma", "22000 EUR"),
            {"sandorio-suma": 22000.0, "sandorio-suma-valiuta": "EUR"},
        )

    def test_a_column_naming_its_currency_in_the_header_gains_no_second_key(self):
        self.assertEqual(interest_row_columns("sandorio-suma-lt", "13000"), {"sandorio-suma-lt": 13000.0})
        self.assertEqual(interest_row_columns("suma-skaiciais", "3859,5"), {"suma-skaiciais": 3859.5})

    def test_the_value_band_code_stays_a_string_with_its_leading_zeros(self):
        self.assertEqual(
            interest_row_columns("sandorio-vertes-litais-kodas", "001"),
            {"sandorio-vertes-litais-kodas": "001"},
        )

    def test_the_comma_headed_columns_become_the_pair_they_name(self):
        self.assertEqual(
            interest_row_columns("dovana-data", "Namas, 2005-01-10"),
            {"dovana": "Namas", "data": "2005-01-10"},
        )
        self.assertEqual(
            interest_row_columns("paslauga-data", "kelionė, 2005-01-01"),
            {"paslauga": "kelionė", "data": "2005-01-01"},
        )

    def test_a_date_column_loses_a_date_printed_twice(self):
        self.assertEqual(
            interest_row_columns("sandorio-sudarymo-data", "2009-12-14 2009-12-14"),
            {"sandorio-sudarymo-data": "2009-12-14"},
        )

    def test_an_empty_money_cell_stays_empty_rather_than_becoming_zero(self):
        self.assertEqual(interest_row_columns("sandorio-suma", None), {"sandorio-suma": None})

    def test_a_column_the_rules_do_not_know_passes_through(self):
        self.assertEqual(
            interest_row_columns("kitos-sandorio-salies-pavadinimas", "AB LUMINOR BANKAS"),
            {"kitos-sandorio-salies-pavadinimas": "AB LUMINOR BANKAS"},
        )


if __name__ == "__main__":
    unittest.main()
