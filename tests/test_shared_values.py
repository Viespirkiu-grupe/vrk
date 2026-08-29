"""The corpus-wide value rules, and the shapes issue #101 measured them against.

Every example here is a value the corpus actually held on 2026-08-29, so a
change that breaks one of these is a change to what the corpus says, not to a
made-up case.
"""

import unittest

from scraper.shared.values import (
    as_money,
    clean_value,
    collapse_repeated_date,
    interest_row_columns,
    is_missing_marker,
    parse_money,
    repair_lost_open_quote,
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

    def test_a_replacement_character_with_nothing_quoted_after_it_is_left(self):
        # 2004-seimo anketa.politine-organizacija: no closing quote, so the
        # character could stand for anything and is not guessed at.
        value = "Tėvynės Sąjunga (LK), Tėvynės liaudies partija �TLP) Dešiniųjų sąjunga (DS)"
        self.assertEqual(repair_lost_open_quote(value), value)

    def test_a_value_that_is_only_a_replacement_character_is_missing(self):
        # 30 records, 28 of them in 2008-seimo: the biography div holds a NUL
        # byte, which the HTML parser renders as U+FFFD. There is no biography.
        self.assertTrue(is_missing_marker("�"))
        self.assertIsNone(clean_value("�"))

    def test_the_dash_a_page_prints_for_an_unanswered_field_is_missing(self):
        self.assertTrue(is_missing_marker("-"))
        self.assertFalse(is_missing_marker("-5"))


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
