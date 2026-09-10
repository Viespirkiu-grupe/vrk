"""The candidacy-table projector (issue #93) on synthetic records.

`scripts/build_candidacy_table.py` is the derived layer over the whole
corpus; these tests pin its per-record projection — the typed absences, the
EUR conversion, the measure tags, the campaign key and the CSV encoding —
on records shaped like the real eras, so the projector's contract holds
without a corpus present.
"""

from __future__ import annotations

import importlib.util
import json
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
        self.assertIsNone(row["constituency_number"])
        self.assertEqual(row["list_name"], "Sąrašas A")
        self.assertEqual(row["list_position"], 7)
        # The 2016 record publishes no votes; the ranking pair is its only
        # preference signal (issue #133).
        self.assertIsNone(row["preference_votes"])
        self.assertIsNone(row["votes_source"])
        self.assertIsNone(row["list_movement"])
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
        known = table._known_zero_note(
            "constituency", {"id": "2019-kovo-3-savivaldybiu-tarybu", "kind": "savivaldybiu", "date": "2019-03-03"}
        )
        self.assertEqual(known.status, "upstream-absent")
        self.assertIn("Seimas", known.note)
        known = table._known_zero_note(
            "list_name", {"id": "2013-kovo-3-seimo-birzai-zarasai-ukmerge", "kind": "seimo", "date": "2013-03-03"}
        )
        self.assertIn("by-election", known.note)
        self.assertIsNone(
            table._known_zero_note("income_eur", {"id": "2016-seimo", "kind": "seimo", "date": "2016-10-09"})
        )

    def test_the_vote_columns_say_parser_gap_where_the_results_exist_and_are_not_read(self):
        # Issue #133: the 2016-2025 results are on vrk.lt; the corpus does
        # not read them. That is not an upstream absence and must not be
        # filed as one.
        seimas_2020 = {"id": "2020-seimo", "kind": "seimo", "date": "2020-10-11"}
        for column in table.VOTE_COLUMNS:
            with self.subTest(column):
                known = table._known_zero_note(column, seimas_2020)
                self.assertEqual(known.status, "parser-gap")
                self.assertIn("VOTES_JOINED", known.note)
        # A joined election: what is structurally absent stays upstream-absent.
        by_election = {"id": "2015-kovo-1-seimo-zirmunai", "kind": "seimo", "date": "2015-03-01"}
        self.assertEqual(table._known_zero_note("preference_votes", by_election).status, "upstream-absent")
        self.assertIsNone(table._known_zero_note("constituency_votes", by_election))
        # The 2004 tree: preference votes joined, constituency rounds not.
        seimas_2004 = {"id": "2004-seimo", "kind": "seimo", "date": "2004-10-10"}
        self.assertIsNone(table._known_zero_note("preference_votes", seimas_2004))
        self.assertEqual(table._known_zero_note("constituency_votes", seimas_2004).status, "parser-gap")
        # The list movement is empty exactly where the ranking is.
        self.assertEqual(
            table._known_zero_note("list_movement", by_election).note,
            table._known_zero_note("post_election_position", by_election).note,
        )


class ClassificationsAgreeWithTheBaseline(unittest.TestCase):
    """A structural reason is a claim about the corpus, and the checked-in
    baseline is the corpus's own measurement of it (issue #165).

    `_known_zero_note`'s rules are hand-written lists of elections, and a
    list written against one corpus goes stale under the next: issue #99's
    results join recovered the post-election ranking for six of the eleven
    elections `POST_RANKING_ABSENT` says never printed one, and six rows of
    `docs/candidacy-baseline.tsv` went on saying "VRK publishes no
    post-election list ranking for this election" over 35,507 values. Nothing
    could tell, because a rule is only consulted when a cell reads zero.

    So the rules are checked against the baseline instead of against a
    corpus: both files are tracked, so this runs on a clone, and a rule that
    excuses a column the baseline measures as filled is a false statement in
    a tracked file whichever direction it rotted from.
    """

    BASELINE = table.field_coverage.read_baseline(REPO_ROOT / "docs" / "candidacy-baseline.tsv")
    REGISTRY = {
        e["id"]: e for e in table.identity.load_registry(REPO_ROOT / "scraper" / "elections.json")
    }

    def test_every_zero_row_carries_a_status_and_a_reason(self):
        # `docs/coverage-baseline.tsv` has had these three file-level
        # invariants since #135 (test_field_coverage.CheckedInBaselineTests);
        # the candidacy baseline, the one that rotted, was read by no test
        # at all.
        for key, row in sorted(self.BASELINE.items()):
            if row.pct:
                continue
            with self.subTest(key):
                self.assertIn(row.status, table.field_coverage.ZERO_STATUSES)
                self.assertTrue(row.note.strip(), "a zero-fill classification needs a reason")

    def test_a_filled_row_carries_no_excuse_it_does_not_need(self):
        for key, row in sorted(self.BASELINE.items()):
            if not row.pct:
                continue
            with self.subTest(key):
                self.assertIn(
                    row.status, {table.field_coverage.OK, *table.field_coverage.LOW_STATUSES}
                )
                if row.status in table.field_coverage.LOW_STATUSES:
                    self.assertTrue(row.note.strip(), "a low-fill classification needs a reason")

    def test_nothing_is_unexplained(self):
        self.assertEqual(
            sorted(k for k, row in self.BASELINE.items() if row.status == table.field_coverage.UNEXPLAINED),
            [],
        )

    def test_no_rule_excuses_a_column_the_baseline_measures_as_filled(self):
        for (column, election), row in sorted(self.BASELINE.items()):
            if row.pct <= 0.0 or election not in self.REGISTRY:
                continue
            with self.subTest(column=column, election=election):
                known = table._known_zero_note(column, self.REGISTRY[election])
                self.assertIsNone(
                    known,
                    f"{column}/{election} fills at {row.pct:.1f}% and a rule calls it"
                    f" structurally empty: {known.status} -- {known.note}"
                    if known
                    else "",
                )

    def test_a_rule_that_fires_on_a_zero_agrees_with_its_checked_in_status(self):
        # The other direction: where a rule does fire, its status is what
        # the baseline carries. An `upstream-absent` rule over a row filed
        # `parser-gap` (or the reverse) means one of the two is lying about
        # whether vrk.lt publishes the value.
        for (column, election), row in sorted(self.BASELINE.items()):
            if row.pct > 0.0 or election not in self.REGISTRY:
                continue
            known = table._known_zero_note(column, self.REGISTRY[election])
            if known is None:
                continue
            with self.subTest(column=column, election=election):
                self.assertEqual(known.status, row.status)

    def test_every_post_ranking_absent_election_really_fills_none(self):
        # The named form of the same check, because this is the constant
        # that rotted and the one whose loss would cost the most.
        for election in sorted(table.POST_RANKING_ABSENT):
            with self.subTest(election):
                row = self.BASELINE.get(("post_election_position", election))
                self.assertIsNotNone(row, "no baseline row: is the election still in the corpus?")
                self.assertEqual(row.pct, 0.0)

    def test_the_seimas_generals_come_from_the_registry(self):
        # A hand copy is right until the next election is added, and a
        # seimo-kind election missing from the set is read as a by-election
        # with no list on the ballot -- the excuse for three columns a
        # general fills on nearly every row.
        self.assertEqual(
            table.SEIMAS_GENERALS,
            frozenset(
                e["id"] for e in self.REGISTRY.values() if e["kind"] == "seimo" and not e.get("parent")
            ),
        )
        # Adding an election means adding it to scraper/elections.json, and
        # the set is re-derived from that file on import -- so the state to
        # check is the module as it would load the day after. A by-election
        # of the same term still reads as one.
        future = {"id": "2028-seimo", "kind": "seimo", "date": "2028-10-08", "parent": None}
        by_election = {"id": "2029-kovo-4-seimo-x", "kind": "seimo", "date": "2029-03-04", "parent": "2028-seimo"}
        derived = table._seimas_generals([*self.REGISTRY.values(), future, by_election])
        self.assertIn("2028-seimo", derived)
        self.assertNotIn("2029-kovo-4-seimo-x", derived)
        with mock.patch.object(table, "SEIMAS_GENERALS", derived):
            for column in ("list_name", "list_position", "post_election_position"):
                with self.subTest(column):
                    self.assertIsNone(
                        table._known_zero_note(column, future),
                        "a new Seimas general must inherit no by-election excuse",
                    )
                    self.assertIn(
                        "by-election", table._known_zero_note(column, by_election).note
                    )

    def test_every_rule_text_appears_on_a_baseline_row(self):
        # A rule whose note is on no row either never fires or describes
        # something that never happens. `income_floor_only`'s did the
        # latter: the column is a bool and `is_filled` counts False as an
        # answer, so the cell can never read zero on a parsed declaration.
        #
        # This ties a rule's wording to the tracked measurement, so
        # rewording one means rewriting the rows that carry it --
        # `--update-baseline` will not, by design: `classify` keeps the note
        # a classified zero already has rather than clobbering a note a
        # human wrote.
        notes = {row.note for row in self.BASELINE.values() if row.note.strip()}
        unused = []
        for election in self.REGISTRY.values():
            for column in table.COLUMNS:
                known = table._known_zero_note(column, election)
                if known is not None and known.note not in notes:
                    unused.append((column, election["id"], known.note))
        self.assertEqual(unused, [], "rule text on no baseline row")


class KnownLows(unittest.TestCase):
    """A column far below its peers inherits its concept's classification
    from docs/coverage-baseline.tsv (issue #135), so the same fact -- the
    2000 card prints no birthplace field -- is classified once."""

    COVERAGE = {
        ("gimimo-vieta", "2000-seimo"): table.field_coverage.Baseline(10.9, "partly-published", "no card field"),
        ("gimimo-vieta", "2016-seimo"): table.field_coverage.Baseline(99.0, "ok", ""),
    }

    def test_a_classified_concept_cell_is_inherited_with_its_note(self):
        inherited = table._known_low_note("birth_place", "2000-seimo", self.COVERAGE)
        self.assertEqual(inherited.status, "partly-published")
        self.assertEqual(inherited.note, "as the gimimo-vieta concept: no card field")

    def test_a_generals_constituency_column_has_a_structural_reason(self):
        inherited = table._known_low_note("constituency", "2008-seimo", {})
        self.assertEqual(inherited.status, "partly-published")
        self.assertIn("Daugiamandatė", inherited.note)
        self.assertIsNone(table._known_low_note("constituency", "2015-kovo-1-seimo-zirmunai", {}))

    def test_an_ok_or_missing_concept_cell_leaves_the_column_unexplained(self):
        self.assertIsNone(table._known_low_note("birth_place", "2016-seimo", self.COVERAGE))
        self.assertIsNone(table._known_low_note("birth_place", "2020-seimo", self.COVERAGE))
        self.assertIsNone(table._known_low_note("list_position", "2000-seimo", self.COVERAGE))

    def test_every_projected_column_names_a_real_concept(self):
        concepts = set(json.loads((REPO_ROOT / "docs" / "concept-map.json").read_text(encoding="utf-8"))["concepts"])
        for column, concept in table.COLUMN_CONCEPTS.items():
            with self.subTest(column):
                self.assertIn(column, table.COLUMNS)
                self.assertIn(concept, concepts)


class WriterTests(unittest.TestCase):
    """The two writers, which no test named (issue #163).

    `write_csv_gz`, `write_sqlite`, `_sqlite_type` and `_sqlite_value` were
    reached only through a three-candidate synthetic build in the
    distribution suite, which asserts table names and row counts. Nothing
    asserted that a CSV cell equals its sqlite cell, that a column gets the
    right affinity — adding `_id` to the REAL suffixes would silently retype
    `person_id`, `party_id` and `campaign_key` in every shipped database —
    or that the five indexes exist.
    """

    ROWS = [
        {
            "person_id": "p1",
            "election_id": "2020-seimo",
            "candidate_id": "a",
            "party_id": "ts-lkd",
            "campaign_key": "dalyvis-1",
            "income_eur": 1234.5,
            "currency_rate": 1.0,
            "elected": True,
            "elected_council": None,
            "list_position": 7,
            "education_higher": False,
            "education_entries": [{"level": "aukstasis"}],
            "declared_currency": "EUR",
        },
        {
            "person_id": "p2",
            "election_id": "2020-seimo",
            "candidate_id": "b",
            "party_id": None,
            "campaign_key": None,
            "income_eur": None,
            "currency_rate": 3.4528,
            "elected": False,
            "elected_council": True,
            "list_position": None,
            "education_higher": None,
            "education_entries": [],
            "declared_currency": None,
        },
    ]

    def _write(self, directory: Path):
        csv_path = directory / "candidacies.csv.gz"
        sqlite_path = directory / "vrk.sqlite"
        table.write_csv_gz(csv_path, table.COLUMNS, self.ROWS)
        table.write_sqlite(
            sqlite_path,
            self.ROWS,
            campaigns={},
            elections_table=[
                {"id": "2020-seimo", "date": "2020-10-11", "kind": "seimo", "parent": None,
                 "name": "2020 Seimas", "shortName": "2020 Seimas", "records": 2}
            ],
            persons=[
                {"person_id": "p1", "name": "A", "birth_key": "A|1970-01-01",
                 "candidacies": 1, "elections": 1, "merged_keys": 0}
            ],
            parties_path=REPO_ROOT / "scraper" / "parties.json",
        )
        return csv_path, sqlite_path

    def test_every_csv_cell_is_its_sqlite_cell(self):
        import csv
        import gzip
        import io
        import sqlite3
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            csv_path, sqlite_path = self._write(Path(tmp))
            with gzip.open(csv_path) as handle:
                csv_rows = list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8")))
            connection = sqlite3.connect(sqlite_path)
            connection.row_factory = sqlite3.Row
            try:
                sql_rows = [
                    dict(row)
                    for row in connection.execute("SELECT * FROM candidacies ORDER BY candidate_id")
                ]
            finally:
                connection.close()

        self.assertEqual(len(csv_rows), len(sql_rows))
        self.assertEqual(list(csv_rows[0]), list(table.COLUMNS))
        for csv_row, sql_row in zip(csv_rows, sql_rows):
            for column in table.COLUMNS:
                with self.subTest(candidate=csv_row["candidate_id"], column=column):
                    value = sql_row[column]
                    # Both writers put a value through the same conversion —
                    # a bool becomes 1/0, a dict or list becomes compact
                    # JSON, None becomes empty — so the CSV cell is `str()`
                    # of the sqlite cell, in every column, with no exceptions.
                    self.assertEqual(csv_row[column], "" if value is None else str(value))

    def test_a_column_gets_the_affinity_its_name_implies(self):
        for column, affinity in (
            ("income_eur", "REAL"),
            ("currency_rate", "REAL"),
            ("donations_total_eur", "REAL"),
            ("list_position", "INTEGER"),
            ("declaration_year", "INTEGER"),
            ("preference_votes", "INTEGER"),
            ("elected", "INTEGER"),
            ("education_higher", "INTEGER"),
            ("person_id", "TEXT"),
            ("party_id", "TEXT"),
            ("campaign_key", "TEXT"),
            ("election_id", "TEXT"),
            ("education_entries", "TEXT"),
        ):
            with self.subTest(column):
                self.assertEqual(table._sqlite_type(column), affinity)

    def test_the_declared_affinities_are_what_the_database_holds(self):
        import sqlite3
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            _, sqlite_path = self._write(Path(tmp))
            connection = sqlite3.connect(sqlite_path)
            try:
                declared = {
                    row[1]: row[2]
                    for row in connection.execute("PRAGMA table_info(candidacies)")
                }
                indexes = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"
                    )
                }
            finally:
                connection.close()
        self.assertEqual(declared, {column: table._sqlite_type(column) for column in table.COLUMNS})
        # The five the query examples in docs/CANDIDACIES.md rely on.
        self.assertEqual(
            indexes,
            {
                "idx_candidacies_person_id",
                "idx_candidacies_election_id",
                "idx_candidacies_party_id",
                "idx_candidacies_campaign_key",
                "idx_campaigns_campaign_key",
            },
        )

    def test_a_value_sqlite_cannot_hold_is_json(self):
        self.assertEqual(table._sqlite_value(True), 1)
        self.assertEqual(table._sqlite_value(False), 0)
        self.assertEqual(table._sqlite_value(None), None)
        self.assertEqual(table._sqlite_value(3.5), 3.5)
        self.assertEqual(table._sqlite_value([{"a": 1}]), '[{"a":1}]')
        self.assertEqual(table._sqlite_value({"a": "ą"}), '{"a":"ą"}')

    def test_the_other_tables_are_created_with_their_documented_columns(self):
        import sqlite3
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            _, sqlite_path = self._write(Path(tmp))
            connection = sqlite3.connect(sqlite_path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                columns = {
                    name: [row[1] for row in connection.execute(f"PRAGMA table_info({name})")]
                    for name in sorted(tables)
                }
            finally:
                connection.close()
        self.assertEqual(
            tables,
            {"candidacies", "campaigns", "elections", "persons", "municipalities", "parties",
             "party_predecessors"},
        )
        self.assertEqual(
            columns["persons"],
            ["person_id", "name", "birth_key", "candidacies", "elections", "merged_keys"],
        )
        self.assertEqual(columns["parties"], ["party_id", "name", "short_name", "type"])
        self.assertEqual(columns["party_predecessors"], ["party_id", "predecessor_id"])
        self.assertEqual(
            columns["elections"], ["id", "date", "kind", "parent", "name", "shortName", "records"]
        )


if __name__ == "__main__":
    unittest.main()
