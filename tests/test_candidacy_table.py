"""The candidacy-table projector (issue #93) on synthetic records.

`scripts/build_candidacy_table.py` is the derived layer over the whole
corpus; these tests pin its per-record projection — the typed absences, the
EUR conversion, the measure tags, the campaign key and the CSV encoding —
on records shaped like the real eras, so the projector's contract holds
without a corpus present.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "build_candidacy_table", REPO_ROOT / "scripts" / "build_candidacy_table.py"
)
table = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(table)

PATHS = {
    "gimimo-data": {
        "2016-seimo": "anketa.gimimo-data",
        "2012-seimo": "anketa.gimimo-data",
        "1996-spalio-20-seimo": "anketa.gimimo-data",
    },
    "gimimo-vieta": {"2016-seimo": "anketa.gimimo-vieta"},
}


def _election(eid, date, kind):
    return {"id": eid, "date": date, "kind": kind}


MODERN_RECORD = {
    "electionId": "2016-seimo",
    "candidateId": "vardene-pavardene",
    "candidateName": "Vardenė PAVARDENĖ",
    "source": "https://www.vrk.lt/x",
    "kandidatavimas": {"isrinktas": True},
    "normalized": {
        "profilis": {
            "vardas-pavarde": "Vardenė PAVARDENĖ",
            "kita": {
                "vienmandate-apygarda": {"pavadinimas": "x", "reiksme": "Žirmūnų", "nuorodos": []},
                "sarasas": {"pavadinimas": "x", "reiksme": "Sąrašas A", "nuorodos": []},
                "numeris-sarase": {"pavadinimas": "x", "reiksme": "7", "nuorodos": []},
            },
        },
        "anketa": {
            "gimimo-data": "1970-01-02",
            "gimimo-vieta": "Vilnius",
            "issilavinimas": {
                "aprasas": None,
                "irasai": [
                    {"issilavinimas": "Aukštasis universitetinis",
                     "mokymo-istaigos-pavadinimas": "VU", "specialybe": "teisė",
                     "baigimo-metai": "1993"}
                ],
            },
            "mokslo-laipsnis": "Daktaras",
            "pareiskimai": {"ar-buvote-pripazintas-kaltu": "Ne"},
        },
        "turto-ir-pajamu-deklaracijos": {
            "privalomas-registruoti-turtas": 100000.0,
            "vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai": 0.0,
            "pinigines-lesos": 20000.0,
            "suteiktos-paskolos": None,
            "gautos-paskolos": 5000.0,
            "gautos-pajamos": 30000.0,
            "sumoketas-pajamu-mokestis": 3000.0,
            "deklaracijos-metai": 2015,
            "deklaracijos-forma": "GPM308",
        },
        "politines-kampanijos-dalyvio-duomenys": [
            {
                "statusas": "Savarankiškas",
                "aukos-pagal-sekcija": {
                    "gautos-ir-priimtos-aukos": {
                        "title": "Gautos ir priimtos aukos",
                        "records": [],
                        "totals": {"is-viso": 1234.5},
                    }
                },
            }
        ],
    },
    "rawData": {
        "turtoIrPajamuDeklaracijos": {
            "sections": [{"items": [
                {"key": "Gautų pajamų suma (GPM308 formos ...)", "value": "30 000"},
                {"key": "Išskaičiuota (sumokėta) pajamų mokesčio suma", "value": "3 000"},
            ]}]
        },
        "politinesKampanijosDalyvioDuomenys": {
            "campaigns": [{"campaignKey": "dalyvis-999", "campaignLabel": "X"}]
        },
    },
}


class ModernRecord(unittest.TestCase):
    def setUp(self):
        self.row = table.project_record(
            MODERN_RECORD, _election("2016-seimo", "2016-10-09", "seimo"), PATHS
        )

    def test_identity_and_candidacy(self):
        row = self.row
        self.assertEqual(row["election_kind"], "seimo")
        self.assertEqual(row["birth_date"], "1970-01-02")
        self.assertEqual(row["birth_place"], "Vilnius")
        self.assertEqual(row["role"], "seimo-narys")
        self.assertEqual(row["constituency"], "Žirmūnų")
        self.assertEqual(row["list_name"], "Sąrašas A")
        self.assertEqual(row["list_position"], 7)
        self.assertIs(row["elected"], True)

    def test_euro_era_money(self):
        row = self.row
        self.assertEqual(row["declaration_status"], "yra")
        self.assertEqual(row["declared_currency"], "EUR")
        self.assertEqual(row["currency_rate"], 1.0)
        self.assertEqual(row["declaration_year"], 2015)
        self.assertEqual(row["income_eur"], 30000.0)
        self.assertEqual(row["income_gross_eur"], 30000.0)
        self.assertEqual(row["income_measure"], "gpm-bruto")
        self.assertEqual(row["tax_measure"], "sumoketas")
        self.assertEqual(row["assets_total_eur"], 120000.0)
        self.assertEqual(row["assets_measure"], "skaidytas")
        self.assertEqual(row["securities_eur"], 0.0)  # a declared zero is a value
        self.assertIs(row["income_floor_only"], False)

    def test_education_and_conviction(self):
        row = self.row
        self.assertEqual(row["education_status"], "nurodyta")
        self.assertEqual(row["education_level"], "aukstasis-universitetinis")
        self.assertIs(row["education_higher"], True)
        self.assertEqual(row["education_degree"], "daktaras")
        self.assertEqual(row["education_entries"][0]["mokymo-istaigos-pavadinimas"], "VU")
        self.assertEqual(row["conviction_status"], "ne")
        self.assertIsNone(row["conviction_details"])

    def test_campaign(self):
        self.assertEqual(self.row["campaign_key"], "dalyvis-999")
        self.assertEqual(self.row["campaign_status"], "savarankiskas")


class MunicipalityJoin(unittest.TestCase):
    def test_the_column_is_the_official_name_and_the_id_joins(self):
        # Issue #137: the eras' wordings shipped as different municipalities.
        older = {"electionId": "2015-kovo-1-savivaldybiu", "candidateId": "x", "candidateName": "X Y",
                 "kandidatavimas": {"savivaldybe": "Kauno miesto savivaldybė", "roles": ["tarybos-narys"], "isrinktas": False},
                 "normalized": {}}
        newer = {"electionId": "2019-kovo-3-savivaldybiu-tarybu", "candidateId": "x", "candidateName": "X Y",
                 "kandidatavimas": {"savivaldybe": {"id": "19972", "number": 15, "name": "Kauno miesto"}, "roles": ["tarybos-narys"], "isrinktas": False},
                 "normalized": {}}
        rows = [
            table.project_record(older, _election("2015-kovo-1-savivaldybiu", "2015-03-01", "savivaldybiu"), PATHS),
            table.project_record(newer, _election("2019-kovo-3-savivaldybiu-tarybu", "2019-03-03", "savivaldybiu"), PATHS),
        ]
        self.assertEqual({row["municipality"] for row in rows}, {"Kauno miesto savivaldybė"})
        self.assertEqual({row["municipality_id"] for row in rows}, {"kauno-miesto"})

    def test_a_dual_candidacy_projects_both_outcomes(self):
        # Issue #140: role='meras' AND elected=1 returned 410 rows for 2019.
        record = {"electionId": "2019-kovo-3-savivaldybiu-tarybu", "candidateId": "x", "candidateName": "X Y",
                  "kandidatavimas": {"savivaldybe": {"id": "1", "number": 13, "name": "Kaišiadorių rajono"},
                                     "roles": ["tarybos-narys", "meras"],
                                     "tarybosNarys": {"partyList": {"id": "2", "number": 4, "name": "LSDP"}, "listPosition": 1, "elected": True},
                                     "meras": {"round": "I", "elected": False}, "isrinktas": True},
                  "normalized": {}}
        row = table.project_record(record, _election("2019-kovo-3-savivaldybiu-tarybu", "2019-03-03", "savivaldybiu"), PATHS)
        self.assertEqual(row["role"], "meras")
        self.assertIs(row["elected"], True)
        self.assertIs(row["elected_council"], True)
        self.assertIs(row["elected_mayor"], False)
        seimas = table.project_record(MODERN_RECORD, _election("2016-seimo", "2016-10-09", "seimo"), PATHS)
        self.assertIsNone(seimas["elected_council"])
        self.assertIsNone(seimas["elected_mayor"])

    def test_a_seimas_row_has_no_municipality(self):
        row = table.project_record(MODERN_RECORD, _election("2016-seimo", "2016-10-09", "seimo"), PATHS)
        self.assertIsNone(row["municipality"])
        self.assertIsNone(row["municipality_id"])


class LitasConversion(unittest.TestCase):
    def test_litas_era_divides_at_the_changeover_rate(self):
        record = {
            "electionId": "2012-seimo",
            "candidateId": "x",
            "candidateName": "X Y",
            "normalized": {
                "turto-ir-pajamu-deklaracijos": {
                    "privalomas-registruoti-turtas": 34528.0,
                    "pinigines-lesos": None,
                    "gautos-pajamos": 3452.8,
                    "sumoketas-pajamu-mokestis": None,
                    "valiuta": "Lt",
                    "deklaracijos-forma": "GPM308",
                }
            },
        }
        row = table.project_record(record, _election("2012-seimo", "2012-10-14", "seimo"), PATHS)
        self.assertEqual(row["declared_currency"], "Lt")
        self.assertEqual(row["currency_rate"], 3.4528)
        self.assertEqual(row["assets_registered_eur"], 10000.0)
        self.assertEqual(row["income_eur"], 1000.0)
        self.assertEqual(row["assets_total_eur"], 10000.0)


class ArchiveRecord(unittest.TestCase):
    def test_net_era_regrosses_and_flags_the_floor(self):
        record = {
            "electionId": "1996-spalio-20-seimo",
            "candidateId": "y",
            "candidateName": "Y Z",
            "normalized": {
                "kandidatavimas": [
                    {"apygarda": "Nevėžio", "iskele": "LDDP", "numeris-sarase": None, "isrinktas": False}
                ],
                "turto-ir-pajamu-deklaracijos": {
                    "valiuta": "Lt",
                    "turtas-ir-pinigines-lesos-metu-pabaigoje": 34528.0,
                    "gautos-pajamos": None,
                    "gautos-pajamos-darbo-santykiu": 3452.8,
                    "sumoketas-pajamu-mokestis": None,
                    "sumoketas-pajamu-mokestis-darbo-santykiu": 345.28,
                },
            },
        }
        row = table.project_record(record, _election("1996-spalio-20-seimo", "1996-10-20", "seimo"), PATHS)
        self.assertEqual(row["income_eur"], 1000.0)  # the row-1 floor, converted
        self.assertIs(row["income_floor_only"], True)
        self.assertEqual(row["income_tax_eur"], 100.0)  # the floor's own tax row
        self.assertEqual(row["income_measure"], "neto-archyvas")
        self.assertEqual(row["income_gross_eur"], 1100.0)
        self.assertEqual(row["assets_total_eur"], 10000.0)
        self.assertEqual(row["assets_measure"], "turtas-plius-lesos")
        self.assertEqual(row["conviction_status"], "neklausta")


class TypedAbsence(unittest.TestCase):
    def test_missing_declaration_is_nera(self):
        record = {"electionId": "2016-seimo", "candidateId": "z", "candidateName": "Z", "normalized": {}}
        row = table.project_record(record, _election("2016-seimo", "2016-10-09", "seimo"), PATHS)
        self.assertEqual(row["declaration_status"], "nera")
        self.assertIsNone(row["declared_currency"])
        self.assertIsNone(row["income_measure"])

    def test_scanned_declarations_are_their_own_state(self):
        record = {"electionId": "2002-prezidento", "candidateId": "z", "candidateName": "Z", "normalized": {}}
        row = table.project_record(record, _election("2002-prezidento", "2002-12-22", "prezidento"), PATHS)
        self.assertEqual(row["declaration_status"], "archyvo-skenai")

    def test_verified_source_error_is_flagged_not_filtered(self):
        record = {
            "electionId": "2016-seimo",
            "candidateId": "flagged-one",
            "candidateName": "F",
            "normalized": {"turto-ir-pajamu-deklaracijos": {"gautos-pajamos": 9e9}},
        }
        with mock.patch.dict(table.SOURCE_ERRORS, {("2016-seimo", "flagged-one"): "note"}):
            row = table.project_record(record, _election("2016-seimo", "2016-10-09", "seimo"), PATHS)
        self.assertEqual(row["quality_flags"], "saltinio-klaida")
        self.assertEqual(row["income_eur"], 9e9)  # flagged, never dropped


class DonationTotals(unittest.TestCase):
    def test_totals_shape(self):
        entry = {"aukos-pagal-sekcija": {"gautos-ir-priimtos-aukos": {"totals": {"is-viso": 640.0}}}}
        self.assertEqual(table.campaign_donation_total_eur(entry), 640.0)

    def test_suvestine_prefers_euro_and_converts_litas(self):
        eur = {"aukos-pagal-sekcija": {"gautos-ir-priimtos-aukos": {"suvestine": [
            {"label": "Iš viso", "amountEur": 20700.26, "amountLt": 71474.44}]}}}
        litas = {"aukos-pagal-sekcija": {"gautos-ir-priimtos-aukos": {"suvestine": [
            {"label": "Iš viso", "amountEur": None, "amountLt": 34528.0}]}}}
        self.assertEqual(table.campaign_donation_total_eur(eur), 20700.26)
        self.assertEqual(table.campaign_donation_total_eur(litas), 10000.0)

    def test_no_donation_data_is_none_not_zero(self):
        # An Atstovaujamasis participant with an empty payload is "financed
        # through the party's campaign", not "declared nothing" (issue #97).
        self.assertIsNone(table.campaign_donation_total_eur({"aukos-pagal-sekcija": {}}))
        self.assertIsNone(table.campaign_donation_total_eur(None))


class CsvEncoding(unittest.TestCase):
    def test_cells(self):
        self.assertEqual(table._cell(None), "")
        self.assertEqual(table._cell(True), "1")
        self.assertEqual(table._cell(False), "0")
        self.assertEqual(table._cell(0.0), "0.0")
        self.assertEqual(table._cell([{"a": "ą"}]), '[{"a":"ą"}]')

    def test_fill_semantics_count_zero_and_false_as_filled(self):
        rows = [
            {"election_id": "e", "elected": False, "income_eur": 0.0, "list_name": None},
            {"election_id": "e", "elected": None, "income_eur": None, "list_name": ""},
        ]
        with mock.patch.object(table, "COLUMNS", ("election_id", "elected", "income_eur", "list_name")):
            cells = {(c.concept): c for c in table.measure_cells(rows)}
        self.assertEqual(cells["elected"].non_null, 1)
        self.assertEqual(cells["income_eur"].non_null, 1)
        self.assertEqual(cells["list_name"].non_null, 0)


class KnownZeros(unittest.TestCase):
    def test_structural_reasons_resolve(self):
        note = table._known_zero_note(
            "constituency", {"id": "2019-kovo-3-savivaldybiu-tarybu", "kind": "savivaldybiu", "date": "2019-03-03"}
        )
        self.assertIn("Seimas", note)
        note = table._known_zero_note(
            "list_name", {"id": "2013-kovo-3-seimo-birzai-zarasai-ukmerge", "kind": "seimo", "date": "2013-03-03"}
        )
        self.assertIn("by-election", note)
        self.assertIsNone(
            table._known_zero_note("income_eur", {"id": "2016-seimo", "kind": "seimo", "date": "2016-10-09"})
        )


if __name__ == "__main__":
    unittest.main()
