"""The one reading of a declaration extract, for every era that publishes one.

Issue #98. Three things the normalized layer used to lose and this module
recovers: the GPM lines beyond the headline pair, the year and form the heading
states, and whose declaration it is — which on 243 records of
`2007-vasario-25-savivaldybiu` meant a spouse's assets were reported as the
candidate's.

The label table is pinned here against every spelling the corpus contains,
because a table keyed on the slug of VRK's whole sentence is exactly what
issue #81 was, and it stayed hidden because no test named the wordings.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scraper.shared.deklaracijos import (
    ASSET_VALUE_KEYS,
    DECLARATION_VALUE_KEYS,
    MONEY_KEY_PREFIXES,
    deklaruotos_pajamos,
    normalize_declaration,
    period_year,
    section_form,
    section_kind,
    section_scope,
    section_year,
    value_key,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Every declaration row label in the corpus that states a figure, measured
#: over all 113,073 records, with the key it has to resolve to.
LABELS = {
    # The five asset rows, in both capitalisations the eras print.
    "I. Privalomas registruoti turtas": "privalomas-registruoti-turtas",
    "I. PRIVALOMAS REGISTRUOTI TURTAS": "privalomas-registruoti-turtas",
    "II. Vertybiniai popieriai, meno kūriniai, juvelyriniai dirbiniai": (
        "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai"
    ),
    "III. Piniginės lėšos": "pinigines-lesos",
    "IV. Suteiktos paskolos": "suteiktos-paskolos",
    "V. GAUTOS PASKOLOS": "gautos-paskolos",
    # Income, six spellings across four income-tax forms.
    "Gautų pajamų suma (GPM305 formos 12, 13, 14 ir GPM305V formos V14 laukelių suma)": "gautos-pajamos",
    "Gautų pajamų suma (GPM308 formos 12, 13, 13A, 14, 22 laukelių ir GPM308 formos V priedo V13 laukelio suma)": "gautos-pajamos",
    "Gautų pajamų suma (GPM308 formos 12, 13, 13A, 14, 20 laukelių ir GPM308 formos V priedo V13 laukelių suma)": "gautos-pajamos",
    "Gautų pajamų suma (GPM308 formos 12, 13, 14 ir GPM308V formos V14 laukelių suma)": "gautos-pajamos",
    "Gautų pajamų suma (12, 13, 14 ir 15 laukelių bei GPM302V priedo V14 laukelio suma)": "gautos-pajamos",
    "Deklaruota apmokestinamųjų ir neapmokestinamųjų pajamų suma": "gautos-pajamos",
    # Tax, five spellings.
    "Išskaičiuota (sumokėta) pajamų mokesčio suma (GPM305 formos 27,28,30 laukelių suma)": "sumoketas-pajamu-mokestis",
    "Išskaičiuota (sumokėta) pajamų mokesčio suma (GPM308 formos 26 laukelis)": "sumoketas-pajamu-mokestis",
    "Išskaičiuota (sumokėta) pajamų mokesčio suma (GPM308 formos 27, 28, 30 laukelių suma)": "sumoketas-pajamu-mokestis",
    "Išskaičiuota mokesčio suma (36 laukelio suma)": "sumoketas-pajamu-mokestis",
    "Deklaruota mokėtina pajamų mokesčio suma": "sumoketas-pajamu-mokestis",
    # The four lines the 2018-and-later extract adds, and which nothing
    # normalized before issue #98 — 18,251 non-zero figures on 10,063 records.
    "Deklaruota individualios veiklos pajamų suma": "individualios-veiklos-pajamos",
    "Su individualios veiklos pajamų gavimu (uždirbimu) susijusių leidžiamų atskaitymų ir ankstesnių metų mokestinių nuostolių suma": "individualios-veiklos-atskaitymai",
    "Deklaruota ne individualios veiklos turto pardavimo ar kitokio perleidimo nuosavybėn pajamų suma": "turto-pardavimo-pajamos",
    "Deklaruoto turto įsigijimo kaina ir su jos pardavimu (kitokiu perleidimu nuosavybėn) susijusių privalomų mokėjimų suma": "turto-isigijimo-kaina",
    "To turto įsigijimo kaina ir su jos pardavimu (kitokiu perleidimu nuosavybėn) susijusių privalomų mokėjimų suma": "turto-isigijimo-kaina",
}

#: The labels that carry a form name or a profile fact rather than a figure.
#: They are read elsewhere (`section_form`, the era's own record assembly) and
#: must not resolve to a value key.
NON_VALUE_LABELS = (
    "GPM305 formos deklaracijos",
    "GPM308 formos deklaracijos",
    "GPM302 formos deklaracijos",
    "FR0462 Formos deklaracijos",
    "FR0462S33 Formos deklaracijos",
    "1) FR0462 formos deklaracijos",
    "5) FR0462S formos deklaracijos",
    "3. Darbovietė",
    "Pildymo data",
)


def _amount(value):
    """A trivial stand-in for an era's litas/euro reader."""
    if value in (None, "", "-"):
        return None
    return float(value) if "." in str(value) else int(value)


def _section(title, **values):
    return {"title": title, "items": [{"key": key, "value": value} for key, value in values.items()]}


class LabelTableTests(unittest.TestCase):
    def test_every_corpus_label_resolves(self) -> None:
        for label, expected in LABELS.items():
            with self.subTest(label=label):
                self.assertEqual(value_key(label), expected)

    def test_a_label_carrying_no_figure_resolves_to_nothing(self) -> None:
        for label in NON_VALUE_LABELS:
            with self.subTest(label=label):
                self.assertIsNone(value_key(label))

    def test_no_two_prefixes_overlap(self) -> None:
        """A label must not be claimed by two keys, whatever the table's order."""
        for prefix, key in MONEY_KEY_PREFIXES:
            others = [
                other_key
                for other_prefix, other_key in MONEY_KEY_PREFIXES
                if other_prefix != prefix and prefix.startswith(other_prefix)
            ]
            with self.subTest(prefix=prefix):
                self.assertEqual([other for other in others if other != key], [])

    def test_a_trailing_colon_and_odd_spacing_do_not_matter(self) -> None:
        self.assertEqual(value_key("  III.   Piniginės  lėšos:  "), "pinigines-lesos")


class HeadingTests(unittest.TestCase):
    def test_scope(self) -> None:
        cases = {
            "Gyventojo turto deklaracija": "gyventojo",
            "METINĖ GYVENTOJO TURTO DEKLARACIJA": "gyventojo",
            "Šeimos turto deklaracija": "seimos",
            "METINĖ ŠEIMOS TURTO DEKLARACIJA": "seimos",
            "Sutuoktinio turto deklaracija": "sutuoktinio",
            "METINĖS GYVENTOJO(ŠEIMOS) TURTO DEKLARACIJOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS": "gyventojo-seimos",
            "METINĖS GYVENTOJO (ŠEIMOS) TURTO DEKLARACIJOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS (2023 m.)": "gyventojo-seimos",
            "Pajamų deklaracija": None,
            "METINĖS PAJAMŲ MOKESČIO DEKLARACIJOS GPM311 FORMOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS (2023 m.)": None,
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(section_scope(title), expected)

    def test_kind(self) -> None:
        self.assertEqual(section_kind("METINĖ ŠEIMOS TURTO DEKLARACIJA"), "turto")
        # The 2004 income heading names GYVENTOJO and PAJAMŲ and no TURTO.
        self.assertEqual(section_kind("METINĖ GYVENTOJO PAJAMŲ DEKLARACIJA"), "pajamu")
        self.assertEqual(
            section_kind("LAIKINOSIOS METINĖS PAJAMŲ MOKESČIO DEKLARACIJOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS"),
            "pajamu",
        )
        self.assertIsNone(section_kind(""))

    def test_year(self) -> None:
        self.assertEqual(
            section_year("METINĖS GYVENTOJO (ŠEIMOS) TURTO DEKLARACIJOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS (2023 m.)"),
            2023,
        )
        # The 2008-2020 headings state no year at all; the note may.
        self.assertIsNone(section_year("METINĖS GYVENTOJO(ŠEIMOS) TURTO DEKLARACIJOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS"))

    def test_year_from_the_declaration_period_note(self) -> None:
        note = (
            "Pastaba. Pagal Seimo rinkimų įstatymo 38 straipsnį, kandidatas pateikia "
            "gyventojo pajamų mokesčio bei gyventojo turto deklaracijų ... 2012 m. Lietuvos "
            "Respublikos Seimo rinkimuose deklaracijos pateikiamos už laikotarpį nuo "
            "2011-01-01 iki 2011-12-31"
        )
        self.assertEqual(period_year(note), 2011)
        self.assertIsNone(period_year(""))
        # A period spanning two calendar years names no single tax year.
        self.assertIsNone(period_year("nuo 2011-01-01 iki 2012-12-31"))

    def test_form(self) -> None:
        self.assertEqual(
            section_form("METINĖS PAJAMŲ MOKESČIO DEKLARACIJOS GPM311 FORMOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS (2023 m.)"),
            "GPM311",
        )
        # 2004 and 2007 head the section with no form and list one line per
        # form; the first of those names the family.
        self.assertEqual(
            section_form("Pajamų deklaracija", ["FR0462 Formos deklaracijos", "FR0462S33 Formos deklaracijos"]),
            "FR0462",
        )
        self.assertEqual(
            section_form(
                "LAIKINOSIOS METINĖS PAJAMŲ MOKESČIO DEKLARACIJOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS",
                ["GPM302 formos deklaracijos"],
            ),
            "GPM302",
        )
        self.assertIsNone(section_form("Gyventojo turto deklaracija", ["I. Privalomas registruoti turtas"]))


class ScopeResolutionTests(unittest.TestCase):
    """Whose figures the block's own keys carry, on the 2007 municipal shapes."""

    OWN = _section(
        "Gyventojo turto deklaracija",
        **{"I. Privalomas registruoti turtas": "10", "III. Piniginės lėšos": "20"},
    )
    FAMILY = _section(
        "Šeimos turto deklaracija",
        **{"I. Privalomas registruoti turtas": "30", "III. Piniginės lėšos": "40"},
    )
    SPOUSE = _section(
        "Sutuoktinio turto deklaracija",
        **{"I. Privalomas registruoti turtas": "50", "III. Piniginės lėšos": "60"},
    )

    def _block(self, *sections):
        return normalize_declaration({"sections": list(sections)}, _amount)

    def test_a_spouse_declaration_alone_leaves_the_candidates_keys_empty(self) -> None:
        # The worked example of issue #98: rawData holds only the spouse's
        # declaration and the corpus reported its three figures as his own.
        block = self._block(self.SPOUSE)

        for key in ASSET_VALUE_KEYS:
            self.assertIsNone(block[key], key)
        self.assertIsNone(block["deklaracijos-apimtis"])
        self.assertEqual(block["sutuoktinio"]["privalomas-registruoti-turtas"], 50)
        self.assertEqual(block["sutuoktinio"]["pinigines-lesos"], 60)
        # And nothing is lost: the declaration is still there, labelled.
        self.assertEqual([s["apimtis"] for s in block["deklaracijos"]], ["sutuoktinio"])

    def test_a_spouse_declaration_printed_last_does_not_win(self) -> None:
        for own, label in ((self.OWN, "gyventojo"), (self.FAMILY, "seimos")):
            with self.subTest(scope=label):
                block = self._block(own, self.SPOUSE)
                self.assertEqual(block["deklaracijos-apimtis"], label)
                self.assertEqual(
                    block["privalomas-registruoti-turtas"],
                    own["items"][0]["value"] and int(own["items"][0]["value"]),
                )
                self.assertEqual(block["sutuoktinio"]["privalomas-registruoti-turtas"], 50)

    def test_the_candidates_own_declaration_beats_the_familys(self) -> None:
        block = self._block(self.OWN, self.FAMILY)
        self.assertEqual(block["deklaracijos-apimtis"], "gyventojo")
        self.assertEqual(block["privalomas-registruoti-turtas"], 10)
        self.assertEqual(len(block["deklaracijos"]), 2)

    def test_no_spouse_key_where_the_page_publishes_no_spouse_declaration(self) -> None:
        self.assertNotIn("sutuoktinio", self._block(self.OWN))


class RepeatedSectionTests(unittest.TestCase):
    INCOME = _section(
        "METINĖS PAJAMŲ MOKESČIO DEKLARACIJOS GPM305 FORMOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS",
        **{"Gautų pajamų suma (GPM305 formos 12, 13, 14 ir GPM305V formos V14 laukelių suma)": "100"},
    )

    def test_an_extract_printed_twice_is_counted_once(self) -> None:
        # Fifteen records in four elections carry a byte-identical repeat;
        # summing them reported thirteen 2007 candidates' income twice over.
        block = normalize_declaration({"sections": [self.INCOME, dict(self.INCOME)]}, _amount)
        self.assertEqual(block["gautos-pajamos"], 100)
        self.assertEqual(len(block["deklaracijos"]), 1)

    def test_a_second_extract_that_differs_is_a_second_declaration(self) -> None:
        other = _section(
            "METINĖS PAJAMŲ MOKESČIO DEKLARACIJOS GPM305 FORMOS PAGRINDINIŲ DUOMENŲ IŠRAŠAS",
            **{"Gautų pajamų suma (GPM305 formos 12, 13, 14 ir GPM305V formos V14 laukelių suma)": "25"},
        )
        block = normalize_declaration({"sections": [self.INCOME, other]}, _amount)
        self.assertEqual(block["gautos-pajamos"], 125)
        self.assertEqual(len(block["deklaracijos"]), 2)


class EmptyPayloadTests(unittest.TestCase):
    def test_no_sections_gives_every_key_as_null(self) -> None:
        block = normalize_declaration({"sections": []}, _amount)
        for key in DECLARATION_VALUE_KEYS:
            self.assertIsNone(block[key], key)
        self.assertEqual(block["deklaracijos"], [])
        self.assertIsNone(block["deklaracijos-forma"])
        self.assertNotIn("pajamos-pagal-forma", block)

    def test_a_payload_that_is_not_a_dict_is_survivable(self) -> None:
        self.assertEqual(normalize_declaration(None, _amount)["deklaracijos"], [])


class DeklaruotosPajamosTests(unittest.TestCase):
    """The derived income concept — issue #98's fourth loss.

    `1997-kovo-23-savivaldybiu-tarybu` has `gautos-pajamos` null on 4,463 of
    its 6,276 records because VRK's own page printed a broken total, and the
    parser rightly refuses it. Row 1 of the same page is present on every one
    of them — 4,628 records corpus-wide — and nothing downstream substituted
    it.
    """

    def test_a_declared_total_is_returned_as_one(self) -> None:
        self.assertEqual(
            deklaruotos_pajamos({"gautos-pajamos": 18200, "valiuta": None}),
            {"suma": 18200, "saltinis": "deklaruota-suma", "valiuta": None},
        )

    def test_a_refused_total_falls_back_to_row_one_and_says_so(self) -> None:
        self.assertEqual(
            deklaruotos_pajamos(
                {
                    "gautos-pajamos": None,
                    "gautos-pajamos-darbo-santykiu": 756,
                    "valiuta": "Lt",
                }
            ),
            {"suma": 756, "saltinis": "darbo-santykiu", "valiuta": "Lt"},
        )

    def test_a_declared_zero_is_a_total_and_not_a_missing_one(self) -> None:
        resolved = deklaruotos_pajamos(
            {"gautos-pajamos": 0, "gautos-pajamos-darbo-santykiu": 756}
        )
        self.assertEqual(resolved["suma"], 0)
        self.assertEqual(resolved["saltinis"], "deklaruota-suma")

    def test_neither_figure(self) -> None:
        self.assertEqual(deklaruotos_pajamos({})["saltinis"], "nera")
        self.assertEqual(deklaruotos_pajamos(None)["saltinis"], "nera")


class RomanovskijFixtureTests(unittest.TestCase):
    """End to end on the record issue #98 names.

    `rawData` holds *Sutuoktinio turto deklaracija* alone (20000.00 / 3000.00 /
    30000.00 Lt) and the corpus reported exactly those three numbers as the
    candidate's `privalomas-registruoti-turtas`, `vertybiniai-popieriai` and
    `pinigines-lesos`.
    """

    def test_the_spouses_assets_are_not_the_candidates(self) -> None:
        from scraper.elections.savivaldybiu_2007.anketa_parser import parse_anketa_sample

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path, _ = parse_anketa_sample(
                candidate_id="tadeus-romanovskij-11440",
                samples_root=REPO_ROOT / "samples" / "html" / "2007-vasario-25-savivaldybiu",
                output_root=Path(tmp_dir),
            )
            record = json.loads(output_path.read_text(encoding="utf-8"))

        declaration = record["normalized"]["turto-ir-pajamu-deklaracijos"]
        for key in ASSET_VALUE_KEYS:
            self.assertIsNone(declaration[key], key)
        self.assertEqual(
            declaration["sutuoktinio"],
            {
                "privalomas-registruoti-turtas": 20000,
                "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 3000,
                "pinigines-lesos": 30000,
                "suteiktos-paskolos": 0,
                "gautos-paskolos": 0,
            },
        )
        # The income extract is unscoped on these pages and stays his.
        self.assertEqual(declaration["gautos-pajamos"], 1381)
        self.assertEqual(declaration["deklaracijos-forma"], "FR0462")
        self.assertEqual(
            [line["forma"] for line in declaration["pajamos-pagal-forma"]],
            ["FR0462", "FR0462S33", "FR0462S15", "FR0462S0", "FR0462S"],
        )


if __name__ == "__main__":
    unittest.main()
