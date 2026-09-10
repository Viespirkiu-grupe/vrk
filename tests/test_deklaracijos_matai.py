"""The money-comparability layer of deklaracijos.py (issue #97).

Four eras publish "the same" income figure under one key while measuring
different things — net of tax before 2004, gross after, with the tax row
flipping from paid to payable in 2018 — and three different wealth shapes
normalize alongside seven documented keys that reach only 73.9 % of records.
These tests pin the measure detection, the era-aware total, the currency
rule and the re-grossing on synthetic declaration blocks shaped like each
era's real ones.
"""

from __future__ import annotations

import unittest

from scraper.shared.deklaracijos import (
    LITAS_PER_EURO,
    deklaracijos_valiuta,
    deklaruotas_turtas,
    deklaruotos_pajamos,
    deklaruotos_pajamos_bruto,
    mokescio_matas,
    pajamu_matas,
)

#: The archive form: combined wealth rows, employment-income rows, and the
#: modern keys present as null placeholders — which is exactly why key
#: *presence* must never be read as key *meaning*.
ARCHIVE = {
    "valiuta": "Lt",
    "privalomas-registruoti-turtas": None,
    "pinigines-lesos": None,
    "turtas-ir-pinigines-lesos-metu-pradzioje": 50000.0,
    "turtas-ir-pinigines-lesos-metu-pabaigoje": 82521.0,
    "gautos-pajamos": 26240.0,
    "gautos-pajamos-darbo-santykiu": 20000.0,
    "sumoketas-pajamu-mokestis": 3952.0,
    "sumoketas-pajamu-mokestis-darbo-santykiu": 3000.0,
}

MUNICIPAL_2002 = {
    "valiuta": "Lt",
    "privalomas-registruoti-turtas": None,
    "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": None,
    "turtas-ir-vertybiniai-popieriai-laikotarpio-pabaigoje": 120000.0,
    "pinigines-lesos": 8000.0,
    "gautos-pajamos": 15000.0,
    "sumoketas-pajamu-mokestis": 5000.0,
}

MODERN = {
    "privalomas-registruoti-turtas": 150000.0,
    "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 0.0,
    "pinigines-lesos": 30000.0,
    "gautos-pajamos": 45000.0,
    "sumoketas-pajamu-mokestis": 4500.0,
    "deklaracijos-forma": "GPM311",
}


def _raw(*labels):
    return {"sections": [{"items": [{"key": label, "value": "1"} for label in labels]}]}


class Valiuta(unittest.TestCase):
    def test_litas_where_stated_euro_where_silent(self):
        self.assertEqual(deklaracijos_valiuta(ARCHIVE), "Lt")
        # No record anywhere says "EUR" — the euro era is marked by absence,
        # which this turns into an explicit answer.
        self.assertEqual(deklaracijos_valiuta(MODERN), "EUR")
        self.assertIsNone(deklaracijos_valiuta(None))

    def test_deklaruotos_pajamos_reports_the_same_currency(self):
        # It used to return `declaration.get("valiuta")` raw, so the two
        # disagreed on 33,120 of the 112,218 records with a declaration:
        # None where its sibling says EUR. Latent, because both builders take
        # the currency from the sibling — but a consumer reading this
        # function's own `valiuta` got the absence the resolver exists to
        # remove (issue #161).
        for name, declaration, expected in (
            ("archive", ARCHIVE, "Lt"),
            ("2002 municipal", MUNICIPAL_2002, "Lt"),
            ("modern", MODERN, "EUR"),
            ("none", None, None),
        ):
            with self.subTest(name):
                self.assertEqual(
                    deklaruotos_pajamos(declaration)["valiuta"],
                    deklaracijos_valiuta(declaration),
                )
                self.assertEqual(deklaruotos_pajamos(declaration)["valiuta"], expected)

    def test_the_currency_travels_with_every_income_source(self):
        # All three branches of deklaruotos_pajamos: a stated total, the
        # employment floor, and nothing at all.
        employment_only = {k: v for k, v in MODERN.items() if k != "gautos-pajamos"}
        employment_only["gautos-pajamos-darbo-santykiu"] = 30000.0
        for name, declaration in (
            ("total", MODERN),
            ("employment floor", employment_only),
            ("nothing", {"deklaracijos-forma": "GPM311"}),
        ):
            with self.subTest(name):
                self.assertEqual(deklaruotos_pajamos(declaration)["valiuta"], "EUR")


class Turtas(unittest.TestCase):
    def test_modern_split_rows_sum(self):
        total = deklaruotas_turtas(MODERN)
        self.assertEqual(total, {"suma": 180000.0, "matas": "skaidytas"})

    def test_archive_combined_row_wins_over_placeholder_keys(self):
        # The null modern keys must not turn the era into a zero "skaidytas"
        # sum; the combined row is the era's figure and includes the cash.
        total = deklaruotas_turtas(ARCHIVE)
        self.assertEqual(total, {"suma": 82521.0, "matas": "turtas-plius-lesos"})

    def test_2002_combined_row_plus_cash(self):
        total = deklaruotas_turtas(MUNICIPAL_2002)
        self.assertEqual(total, {"suma": 128000.0, "matas": "turtas-plius-vp"})

    def test_no_figures_no_measure(self):
        self.assertEqual(
            deklaruotas_turtas({"turtas-ir-pinigines-lesos-metu-pabaigoje": None}),
            {"suma": None, "matas": None},
        )
        self.assertEqual(deklaruotas_turtas(None), {"suma": None, "matas": None})

    def test_partial_split_sum_ignores_nulls(self):
        total = deklaruotas_turtas({"privalomas-registruoti-turtas": None, "pinigines-lesos": 500.0})
        self.assertEqual(total, {"suma": 500.0, "matas": "skaidytas"})


class PajamuMatas(unittest.TestCase):
    def test_archive_is_net(self):
        self.assertEqual(pajamu_matas(ARCHIVE), "neto-archyvas")
        self.assertEqual(pajamu_matas(MUNICIPAL_2002), "neto-archyvas")

    def test_wording_decides_the_gpm_eras(self):
        old = _raw("Gautų pajamų suma (GPM308 formos 12, 13 laukelių suma)")
        new = _raw("Deklaruota apmokestinamųjų ir neapmokestinamųjų pajamų suma")
        self.assertEqual(pajamu_matas(MODERN, old), "gpm-bruto")
        self.assertEqual(pajamu_matas(MODERN, new), "deklaruota-apmokestinamos")

    def test_form_lines_do_not_shadow_the_gpm_label(self):
        # `pajamos-pagal-forma` exists on every 2004-2015 declaration (issue
        # #98 normalizes the whole span), so it must not read as FR0462 when
        # the page prints the GPM income label — the 2015 mayoral records do
        # both.
        declaration = dict(MODERN, **{"pajamos-pagal-forma": [], "deklaracijos-forma": "GPM305"})
        raw = _raw("Gautų pajamų suma (GPM305 formos ...)")
        self.assertEqual(pajamu_matas(declaration, raw), "gpm-bruto")

    def test_fr0462_era(self):
        declaration = {"gautos-pajamos": 100.0, "pajamos-pagal-forma": [], "deklaracijos-forma": "FR0462"}
        self.assertEqual(pajamu_matas(declaration, None), "fr0462")

    def test_no_declaration(self):
        self.assertIsNone(pajamu_matas(None))


class MokescioMatas(unittest.TestCase):
    def test_paid_vs_payable(self):
        self.assertEqual(mokescio_matas(ARCHIVE), "sumoketas")
        old = _raw("Išskaičiuota (sumokėta) pajamų mokesčio suma (GPM308 formos 26 laukelis)")
        new = _raw("Deklaruota mokėtina pajamų mokesčio suma")
        self.assertEqual(mokescio_matas(MODERN, old), "sumoketas")
        self.assertEqual(mokescio_matas(MODERN, new), "moketinas")


class Bruto(unittest.TestCase):
    def test_gross_eras_pass_through(self):
        self.assertEqual(deklaruotos_pajamos_bruto(MODERN, "gpm-bruto"), 45000.0)

    def test_net_era_regresses_income_plus_tax(self):
        # Exactly issue #97's recipe: the era's two rows of the same form.
        self.assertEqual(deklaruotos_pajamos_bruto(ARCHIVE), 30192.0)

    def test_employment_floor_regresses_with_its_own_tax_row(self):
        floor = dict(ARCHIVE, **{"gautos-pajamos": None})
        self.assertEqual(deklaruotos_pajamos_bruto(floor), 23000.0)

    def test_net_without_tax_is_unknowable(self):
        no_tax = dict(ARCHIVE, **{"sumoketas-pajamu-mokestis": None})
        self.assertIsNone(deklaruotos_pajamos_bruto(no_tax))

    def test_litas_rate_is_the_irrevocable_one(self):
        self.assertEqual(LITAS_PER_EURO, 3.4528)


if __name__ == "__main__":
    unittest.main()
