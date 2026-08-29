"""Unit tests for the one nominator resolver over the corpus's eleven paths.

Issue #82: reaching the nominator took knowing eleven paths and two value
shapes, and a resolver that walked any one of them reported nulls that were
indistinguishable from a non-partisan candidate. These tests pin the walk
rules on synthetic records of every era shape, and pin the resolver to the
same path semantics `scripts/field_coverage.py` measures with, so the
resolution order declared in docs/concept-map.json means one thing.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from scraper.shared.nominator import nominator_paths, resolve_nominator

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "field_coverage", REPO_ROOT / "scripts" / "field_coverage.py"
)
field_coverage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(field_coverage)

#: The elections whose pages name no nominator: candidates self-nominate by
#: law and the concept map deliberately maps no paths, so the resolver's None
#: is the answer there, not a gap. 2024-prezidento is not among them -- its
#: card prints "Kandidatą iškėlė".
NO_NOMINATOR_ELECTIONS = {
    "2002-prezidento",
    "2004-prezidento",
    "2009-prezidento",
    "2014-prezidento",
    "2019-prezidento",
}


class PathTableTests(unittest.TestCase):
    def test_every_election_maps_except_the_nominator_less_presidential_five(self):
        # docs/concept-map.json's own election list is the corpus roster; the
        # iskele concept must order paths for every election but the five
        # whose pages publish no nominator at all.
        import json

        concept_map = json.loads(
            (REPO_ROOT / "docs" / "concept-map.json").read_text(encoding="utf-8")
        )
        expected = set(concept_map["elections"]) - NO_NOMINATOR_ELECTIONS
        self.assertEqual(set(nominator_paths()), expected)

    def test_paths_come_back_as_tuples_whatever_the_map_writes(self):
        paths = nominator_paths()
        self.assertEqual(paths["2000-seimo"], ("profilis.kita.iskele.reiksme",))
        self.assertEqual(
            paths["2016-seimo"],
            ("profilis.kita.iskele.reiksme", "profilis.kita.sarasas.reiksme"),
        )


class EraShapeTests(unittest.TestCase):
    """One synthetic record per era shape the corpus actually has."""

    def test_archive_candidacy_list_fans_out_in_order(self):
        # 1996-1999: normalized.kandidatavimas is a LIST -- a candidate could
        # stand in a constituency and on a party list at once -- and the first
        # entry that names a nominator wins.
        record = {
            "electionId": "1996-spalio-20-seimo",
            "normalized": {
                "kandidatavimas": [
                    {"apygarda": "Gargždų", "iskele": None},
                    {"iskele": "Lietuvos liberalų sąjunga"},
                ]
            },
        }
        self.assertEqual(resolve_nominator(record), "Lietuvos liberalų sąjunga")

    def test_1997_municipal_dict_under_normalized(self):
        record = {
            "electionId": "1997-kovo-23-savivaldybiu-tarybu",
            "normalized": {"kandidatavimas": {"iskele": "Lietuvos liaudies partija"}},
        }
        self.assertEqual(resolve_nominator(record), "Lietuvos liaudies partija")

    def test_2000_municipal_party_list_is_a_bare_string_on_the_record_root(self):
        record = {
            "electionId": "2000-kovo-19-savivaldybiu-tarybu",
            "normalized": {"profilis": {"kita": {}}},
            "kandidatavimas": {"tarybosNarys": {"partyList": 'Koalicija "Santarvės kelias"'}},
        }
        self.assertEqual(resolve_nominator(record), 'Koalicija "Santarvės kelias"')

    def test_2019_municipal_party_list_is_a_dict_and_the_name_resolves(self):
        record = {
            "electionId": "2019-kovo-3-savivaldybiu-tarybu",
            "normalized": {"profilis": {"kita": {}}},
            "kandidatavimas": {
                "tarybosNarys": {
                    "partyList": {"id": "28756", "name": "Lietuvos valstiečių ir žaliųjų sąjunga"}
                }
            },
        }
        self.assertEqual(resolve_nominator(record), "Lietuvos valstiečių ir žaliųjų sąjunga")

    def test_2019_municipal_mayoral_key_outranks_the_council_join(self):
        record = {
            "electionId": "2019-kovo-3-savivaldybiu-tarybu",
            "normalized": {
                "profilis": {
                    "kita": {
                        "iskele-i-tarybos-narius-merus": {"reiksme": "Darbo partija"},
                    }
                }
            },
            "kandidatavimas": {"tarybosNarys": {"partyList": {"name": "Kita partija"}}},
        }
        self.assertEqual(resolve_nominator(record), "Darbo partija")

    def test_2016_seimas_falls_back_to_the_list_when_iskele_is_printed_empty(self):
        # The 2016/2020/2024 cards print the "Iškėlė" row with no value for a
        # list-only candidacy; the null must not shadow the list name.
        record = {
            "electionId": "2016-seimo",
            "normalized": {
                "profilis": {
                    "kita": {
                        "iskele": {"pavadinimas": "Iškėlė", "reiksme": None},
                        "sarasas": {"pavadinimas": "Sąrašas", "reiksme": "Laisvės partija"},
                    }
                }
            },
        }
        self.assertEqual(resolve_nominator(record), "Laisvės partija")

    def test_2015_self_nomination_is_the_bare_label(self):
        # The 2011/2015-era pages mark self-nomination with a label whose
        # value is empty, so the label itself is the resolved string and the
        # party registry maps it to the self-nomination entry.
        record = {
            "electionId": "2015-kovo-1-savivaldybiu",
            "normalized": {
                "profilis": {
                    "kita": {
                        "issikeles-kandidatas": {
                            "pavadinimas": "Išsikėlęs kandidatas",
                            "reiksme": None,
                        }
                    }
                }
            },
        }
        self.assertEqual(resolve_nominator(record), "Išsikėlęs kandidatas")


class ValueRuleTests(unittest.TestCase):
    def test_unmapped_election_resolves_none(self):
        record = {"electionId": "2019-prezidento", "normalized": {"profilis": {"kita": {}}}}
        self.assertIsNone(resolve_nominator(record))

    def test_blank_and_whitespace_strings_are_not_values(self):
        record = {
            "electionId": "2016-seimo",
            "normalized": {"profilis": {"kita": {"iskele": {"reiksme": "   "}}}},
        }
        self.assertIsNone(resolve_nominator(record))

    def test_a_container_leaf_is_not_a_value(self):
        # kandidatavimas.tarybosNarys.partyList is a dict in 2019/2023; only
        # its `name` path may answer, never the container itself.
        record = {
            "electionId": "2019-kovo-3-savivaldybiu-tarybu",
            "kandidatavimas": {"tarybosNarys": {"partyList": {"id": "1"}}},
        }
        self.assertIsNone(resolve_nominator(record))

    def test_the_value_is_stripped(self):
        record = {
            "electionId": "2016-seimo",
            "normalized": {"profilis": {"kita": {"iskele": {"reiksme": " Darbo partija "}}}},
        }
        self.assertEqual(resolve_nominator(record), "Darbo partija")

    def test_explicit_election_id_overrides_the_record(self):
        record = {
            "electionId": "2019-prezidento",
            "normalized": {"profilis": {"kita": {"iskele": {"reiksme": "Darbo partija"}}}},
        }
        self.assertEqual(resolve_nominator(record, "2016-seimo"), "Darbo partija")


class FieldCoverageAgreementTests(unittest.TestCase):
    """The resolver and scripts/field_coverage.py walk the same declared paths.

    Both implement "normalized first, record root for kandidatavimas, lists
    fan out in order" independently; drift between them would let coverage
    report a cell filled that the resolver returns None for. Pin agreement on
    the shapes that exercise every rule.
    """

    RECORDS = [
        {
            "electionId": "1996-spalio-20-seimo",
            "normalized": {"kandidatavimas": [{"iskele": None}, {"iskele": "A"}]},
        },
        {
            "electionId": "2000-kovo-19-savivaldybiu-tarybu",
            "kandidatavimas": {"tarybosNarys": {"partyList": "B"}},
        },
        {
            "electionId": "2016-seimo",
            "normalized": {
                "profilis": {"kita": {"iskele": {"reiksme": None}, "sarasas": {"reiksme": "C"}}}
            },
        },
        {"electionId": "2016-seimo", "normalized": {"profilis": {"kita": {}}}},
        {"electionId": "1996-spalio-20-seimo", "normalized": {"kandidatavimas": []}},
    ]

    def test_resolved_exactly_when_coverage_reports_filled(self):
        for record in self.RECORDS:
            paths = list(nominator_paths()[record["electionId"]])
            _, filled = field_coverage.resolve_any(record, paths)
            value = resolve_nominator(record)
            self.assertEqual(
                value is not None, filled, f"disagree on {record!r}: {value!r} vs {filled}"
            )


if __name__ == "__main__":
    unittest.main()
