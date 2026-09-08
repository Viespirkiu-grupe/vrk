"""Unit tests for the cross-election person index builder.

The builder groups candidacies into persons by normalized name + birth date —
measured over the corpus: birth date present on 33,118 of 33,119 records, zero
same-election collisions, 305 namesake names that name-only grouping would
merge wrongly. These tests pin the grouping rules on synthetic records so the
identity key cannot drift silently.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "build_person_index", REPO_ROOT / "scripts" / "build_person_index.py"
)
build_person_index = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_person_index)


def _record(name, birth=None, birth_section="anketa", elected_note=None):
    normalized = {}
    if birth is not None:
        normalized[birth_section] = {"gimimo-data": birth}
    if elected_note is not None:
        normalized["profilis"] = {"pastaba": elected_note}
    return {"candidateName": name, "normalized": normalized}


class NormalizeNameTests(unittest.TestCase):
    def test_case_and_whitespace_fold(self):
        self.assertEqual(
            build_person_index.normalize_name("  Ingrida   Šimonytė "),
            "INGRIDA ŠIMONYTĖ",
        )

    def test_diacritics_are_preserved(self):
        # ŠIMONYTĖ and SIMONYTE are different names; folding diacritics is the
        # search layer's job, not the identity key's.
        self.assertNotEqual(
            build_person_index.normalize_name("Šimonytė"),
            build_person_index.normalize_name("Simonyte"),
        )


class BirthDateTests(unittest.TestCase):
    def test_anketa_first_then_biografija(self):
        self.assertEqual(
            build_person_index.birth_date_of(_record("X", "1974-11-15", "anketa")),
            "1974-11-15",
        )
        self.assertEqual(
            build_person_index.birth_date_of(_record("X", "1974-11-15", "biografija")),
            "1974-11-15",
        )
        self.assertIsNone(build_person_index.birth_date_of(_record("X")))


class RegistryCarriageTests(unittest.TestCase):
    """people.json copies the registry entries whole, `parent` included: the
    dashboard's term grouping (issue #122) reads that field and nothing else,
    and a parent that names no registered election must fail the build
    rather than leave its by-election ungrouped."""

    REGISTRY = [
        {"id": "2016-seimo", "date": "2016-10-09", "kind": "seimo",
         "name": "2016 m. spalio 9 d. Lietuvos Respublikos Seimo rinkimai", "shortName": "2016 Seimas"},
        {"id": "2017-balandzio-23-seimo-anyksciai-panevezys", "date": "2017-04-23", "kind": "seimo",
         "parent": "2016-seimo", "name": "2017 m. balandžio 23 d. nauji Lietuvos Respublikos Seimo rinkimai",
         "shortName": "2017-04 Seimas"},
        {"id": "2020-seimo", "date": "2020-10-11", "kind": "seimo",
         "name": "2020 m. spalio 11 d. Lietuvos Respublikos Seimo rinkimai", "shortName": "2020 Seimas"},
    ]

    def test_present_elections_ride_whole_into_the_index_parent_included(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for eid in ("2016-seimo", "2017-balandzio-23-seimo-anyksciai-panevezys"):
                (root / eid).mkdir()
                record = dict(_record("Jonas JONAITIS", "1970-01-01"), candidateId="jonas-jonaitis")
                (root / eid / f"jonas-jonaitis-{eid}.json").write_text(
                    json.dumps(record, ensure_ascii=False), encoding="utf-8"
                )
            index = build_person_index.build_index(
                root, registry=self.REGISTRY, overrides={"decisions": []}
            )
        self.assertEqual(index["elections"], self.REGISTRY[:2])

    def test_a_parent_that_names_no_registered_election_fails_to_load(self):
        import tempfile

        broken = [dict(e) for e in self.REGISTRY]
        broken[1]["parent"] = "2016-seimas"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "elections.json"
            path.write_text(json.dumps({"elections": broken}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unregistered parent"):
                build_person_index.load_registry(path)


class PartyTableTests(unittest.TestCase):
    """people.json's parties table carries, per used nominator id, the label,
    the kind and -- since issue #123 -- `pr`, the registry's `predecessors`,
    which the dashboard's party facet turns into lineage rows."""

    def test_predecessors_ride_into_the_parties_table_whole(self):
        import tempfile

        registry = build_person_index.load_registry()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "2023-kovo-5-savivaldybiu-tarybu-ir-meru").mkdir()
            record = dict(
                _record("Jonas JONAITIS", "1970-01-01"),
                candidateId="jonas-jonaitis",
                kandidatavimas={
                    "roles": ["tarybos-narys"],
                    "savivaldybe": "Kauno miesto",
                    "tarybosNarys": {"partyList": {"name": "Vieningas Kaunas"}},
                },
            )
            (root / "2023-kovo-5-savivaldybiu-tarybu-ir-meru" / "jonas-jonaitis.json").write_text(
                json.dumps(record, ensure_ascii=False), encoding="utf-8"
            )
            index = build_person_index.build_index(root, registry=registry, overrides={"decisions": []})
        self.assertEqual(index["people"][0]["e"][0]["p"], "vieningas-kaunas")
        # The whole registry list, even though this index carries no candidacy
        # of the committee: the page skips what it lacks rather than the
        # builder deciding what a lineage is.
        self.assertEqual(index["parties"]["vieningas-kaunas"]["pr"], ["komitetas-vieningas-kaunas"])
        self.assertEqual(index["parties"]["vieningas-kaunas"]["t"], "partija")


class GroupingTests(unittest.TestCase):
    def _build(self, tmp_records, overrides=None):
        # lay records out as data/<election>/<cid>-<election>.json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for eid, cid, record in tmp_records:
                d = root / eid
                d.mkdir(exist_ok=True)
                record = dict(record, candidateId=cid)
                (d / f"{cid}-{eid}.json").write_text(
                    json.dumps(record, ensure_ascii=False), encoding="utf-8"
                )
            return build_person_index.build_index(
                root, overrides=overrides or {"decisions": []}
            )

    def test_same_name_and_birth_groups_across_elections(self):
        index = self._build(
            [
                ("2016-seimo", "jonas-jonaitis", _record("Jonas JONAITIS", "1970-01-01")),
                ("2020-seimo", "jonas-jonaitis", _record("Jonas JONAITIS", "1970-01-01")),
            ]
        )
        self.assertEqual(index["stats"]["persons"], 1)
        self.assertEqual(index["stats"]["personsInMultipleElections"], 1)
        self.assertEqual(len(index["people"][0]["e"]), 2)

    def test_namesakes_with_distinct_birth_dates_stay_apart(self):
        index = self._build(
            [
                ("2016-seimo", "jonas-jonaitis", _record("Jonas JONAITIS", "1970-01-01")),
                ("2020-seimo", "jonas-jonaitis", _record("Jonas JONAITIS", "1985-05-05")),
            ]
        )
        self.assertEqual(index["stats"]["persons"], 2)
        self.assertEqual(index["stats"]["personsInMultipleElections"], 0)

    def test_missing_birth_date_groups_by_name_and_is_counted(self):
        index = self._build(
            [("2020-seimo", "jonas-korsakas", _record("Jonas KORSAKAS"))]
        )
        self.assertEqual(index["stats"]["recordsWithoutBirthDate"], 1)
        self.assertIsNone(index["people"][0]["b"])

    def test_birth_year_keys_apart_what_a_date_would_have(self):
        # The 1996-1998 Seimas archive publishes no birth date but usually a
        # year; two same-named archive candidates born in different years
        # must not collapse into one person just because the date is absent.
        a = _record("Jonas JONAITIS")
        a["normalized"]["anketa"] = {"gimimo-metai": 1936}
        b = _record("Jonas JONAITIS")
        b["normalized"]["anketa"] = {"gimimo-metai": 1960}
        index = self._build(
            [("1996-spalio-20-seimo", "a", a), ("1997-kovo-23-seimo-pakartotiniai", "b", b)]
        )
        self.assertEqual(index["stats"]["persons"], 2)
        self.assertEqual(index["stats"]["recordsWithBirthYearOnly"], 2)
        self.assertEqual(
            sorted(p["b"] for p in index["people"]), ["~1936", "~1960"]
        )

    def test_a_full_date_still_beats_the_year(self):
        record = _record("Jonas JONAITIS", "1936-02-22")
        record["normalized"]["anketa"]["gimimo-metai"] = 1936
        index = self._build([("2000-seimo", "a", record)])
        self.assertEqual(index["people"][0]["b"], "1936-02-22")
        self.assertEqual(index["stats"]["recordsWithBirthYearOnly"], 0)

    def test_every_person_carries_a_deterministic_pid(self):
        index = self._build(
            [("2016-seimo", "jonas-jonaitis", _record("Jonas JONAITIS", "1970-01-01"))]
        )
        person = index["people"][0]
        # The literal digest pins the hash recipe itself: a quiet change to
        # the pid formula would silently break every shared deep link.
        self.assertEqual(person["pid"], build_person_index.person_pid(person["k"]))
        self.assertEqual(
            build_person_index.person_pid("JONAS JONAITIS|1970-01-01"),
            "pff9fb9faa17a",
        )

    def test_the_pid_survives_a_new_election(self):
        before = self._build(
            [("2016-seimo", "a-b", _record("A B", "1970-01-01"))]
        )
        after = self._build(
            [
                ("2016-seimo", "a-b", _record("A B", "1970-01-01")),
                ("2020-seimo", "a-b", _record("A B", "1970-01-01")),
            ]
        )
        self.assertEqual(before["people"][0]["pid"], after["people"][0]["pid"])

    def test_a_pid_collision_fails_the_build(self):
        with mock.patch.object(build_person_index, "person_pid", return_value="pdeadbeef0000"):
            with self.assertRaises(ValueError):
                self._build(
                    [
                        ("2016-seimo", "a-b", _record("A B", "1970-01-01")),
                        ("2016-seimo", "c-d", _record("C D", "1980-01-01")),
                    ]
                )

    def test_an_override_merge_folds_two_fragments_into_one_person(self):
        # Surname change between elections: two natural keys, one human.
        # The canonical fragment is the chronologically earliest, so the pid
        # does not move when a later election arrives; the other key lands in
        # "ak" so an old deep link still resolves; the display name and birth
        # follow the latest record, like an unmerged person's do.
        merge = {
            "decisions": [
                {
                    "decision": "merge",
                    "keys": ["A MAIDENYTĖ|1970-01-01", "A MAIDENYTĖ-VED|1970-01-01"],
                    "why": "test",
                }
            ]
        }
        index = self._build(
            [
                ("2016-seimo", "a-m", _record("A Maidenytė", "1970-01-01")),
                ("2020-seimo", "a-mv", _record("A MAIDENYTĖ-VED", "1970-01-01")),
            ],
            overrides=merge,
        )
        self.assertEqual(index["stats"]["persons"], 1)
        self.assertEqual(index["stats"]["mergedPersons"], 1)
        person = index["people"][0]
        self.assertEqual(person["k"], "A MAIDENYTĖ|1970-01-01")
        self.assertEqual(person["pid"], build_person_index.person_pid(person["k"]))
        self.assertEqual(person["ak"], ["A MAIDENYTĖ-VED|1970-01-01"])
        self.assertEqual(person["n"], "A MAIDENYTĖ-VED")
        self.assertEqual([e["id"] for e in person["e"]], ["2016-seimo", "2020-seimo"])
        self.assertEqual(index["unmatchedOverrideKeys"], [])

    def test_a_distinct_decision_merges_nothing(self):
        distinct = {
            "decisions": [
                {
                    "decision": "distinct",
                    "keys": ["A MAIDENYTĖ|1970-01-01", "A MAIDENYTĖ-VED|1970-01-01"],
                    "why": "test",
                }
            ]
        }
        index = self._build(
            [
                ("2016-seimo", "a-m", _record("A Maidenytė", "1970-01-01")),
                ("2020-seimo", "a-mv", _record("A MAIDENYTĖ-VED", "1970-01-01")),
            ],
            overrides=distinct,
        )
        self.assertEqual(index["stats"]["persons"], 2)
        self.assertEqual(index["stats"]["mergedPersons"], 0)

    def test_two_pair_entries_chain_into_a_three_way_merge(self):
        merge = {
            "decisions": [
                {"decision": "merge", "keys": ["A B|1970-01-01", "A B|~1970"], "why": "t"},
                {"decision": "merge", "keys": ["A B|~1970", "A B|?"], "why": "t"},
            ]
        }
        dated = _record("A B", "1970-01-01")
        year = _record("A B")
        year["normalized"]["anketa"] = {"gimimo-metai": 1970}
        bare = _record("A B")
        index = self._build(
            [
                ("2016-seimo", "d", dated),
                ("1996-spalio-20-seimo", "y", year),
                ("2020-seimo", "b", bare),
            ],
            overrides=merge,
        )
        self.assertEqual(index["stats"]["persons"], 1)
        person = index["people"][0]
        # 1996 is the earliest candidacy, so the year fragment is canonical —
        # and the shown birth is still the latest *full* date, not the year.
        self.assertEqual(person["k"], "A B|~1970")
        self.assertEqual(sorted(person["ak"]), ["A B|1970-01-01", "A B|?"])
        self.assertEqual(person["b"], "1970-01-01")

    def test_an_override_key_matching_no_person_is_reported(self):
        merge = {
            "decisions": [
                {
                    "decision": "merge",
                    "keys": ["A B|1970-01-01", "GONE PERSON|1900-01-01"],
                    "why": "test",
                }
            ]
        }
        index = self._build(
            [("2016-seimo", "a-b", _record("A B", "1970-01-01"))], overrides=merge
        )
        self.assertEqual(index["unmatchedOverrideKeys"], ["GONE PERSON|1900-01-01"])
        self.assertEqual(index["stats"]["persons"], 1)

    def test_the_win_flag_is_the_candidacy_resolvers_tri_state(self):
        # Elected status resolves through scraper/shared/kandidatura.py alone.
        # The prose-note pathway lives in the parsers now
        # (candidacy_from_elected_note, issue #100), which emit the root
        # kandidatavimas block these records carry — measured 2026-08-30, all
        # 3,522 Išrink…-noted records agree with the block, zero disagree.
        # "w" is emitted for both known outcomes and omitted where no results
        # exist, so "lost" and "no results data" are no longer the same
        # absence (issue #87).
        winner = _record("A B", "1970-01-01", elected_note="Išrinkta pagal sąrašą")
        winner["kandidatavimas"] = {"vrkCandidateId": "1", "isrinktas": True, "isrinktasKaip": "vienmandate"}
        loser = _record("A B", "1970-01-01")
        loser["kandidatavimas"] = {"vrkCandidateId": "2", "isrinktas": False}
        unknown = _record("A B", "1970-01-01")
        unknown["kandidatavimas"] = {"vrkCandidateId": "3", "isrinktas": None}
        index = self._build([("2012-seimo", "a-b", winner), ("2014-ep", "a-b", loser), ("2015-kovo-1-savivaldybiu", "a-b", unknown)])
        entries = index["people"][0]["e"]
        self.assertIs(entries[0].get("w"), True)
        self.assertIs(entries[1].get("w"), False)
        self.assertNotIn("w", entries[2])
        self.assertEqual(index["stats"]["candidaciesWon"], 1)
        self.assertEqual(index["stats"]["candidaciesLost"], 1)
        self.assertEqual(index["stats"]["candidaciesWithoutResultsData"], 1)

    def test_a_prose_note_without_the_block_does_not_win_on_its_own(self):
        # A record with only the note and no kandidatavimas block does not
        # exist in the corpus (the parsers guarantee the block); the builder
        # deliberately reads the one resolver rather than keeping a second
        # elected rule of its own.
        noted = _record("A B", "1970-01-01", elected_note="Išrinkta pagal sąrašą")
        index = self._build([("2016-seimo", "a-b", noted)])
        self.assertNotIn("w", index["people"][0]["e"][0])

    def test_archive_family_list_shaped_candidacy_becomes_the_win_flag(self):
        # The 1996-1999 Seimas archive family's kandidatavimas is a list under
        # `normalized` — a 1996 candidate could stand in a constituency and on
        # a list at once — so any elected candidacy wins the record, and a
        # record whose candidacies are all false lost.
        winner = _record("A B", "1970-01-01")
        winner["normalized"]["kandidatavimas"] = [
            {"apygarda": "Žirmūnų", "isrinktas": False},
            {"apygarda": "Daugiamandatė", "isrinktas": True, "isrinktas-kaip": "daugiamandate"},
        ]
        loser = _record("A B", "1970-01-01")
        loser["normalized"]["kandidatavimas"] = [
            {"apygarda": "Naujosios Vilnios", "isrinktas": False},
            {"apygarda": "Daugiamandatė", "isrinktas": False},
        ]
        index = self._build(
            [("1996-spalio-20-seimo", "a-b", winner), ("1999-kovo-21-seimo-pakartotiniai", "a-b", loser)]
        )
        entries = index["people"][0]["e"]
        self.assertIs(entries[0].get("w"), True)
        self.assertIs(entries[1].get("w"), False)

    def test_candidacy_facets_ride_into_the_index(self):
        # The dashboard's facets and search work off people.json alone
        # (issue #87): the interned municipality ("sv"), the mayor flag on a
        # two-office ballot ("r"), the workplace string the search box
        # matches ("wp", resolved through docs/concept-map.json), and the
        # education rank ("ed", scraper/shared/education.py's ordinal).
        record = _record("A B", "1970-01-01")
        record["kandidatavimas"] = {
            "savivaldybe": {"id": "1", "number": 45, "name": "Šiaulių rajono"},
            "roles": ["meras", "tarybos-narys"],
            "isrinktas": False,
        }
        record["normalized"]["anketa"]["pagrindine-darboviete"] = "AB Žeimena, inspektorė"
        record["normalized"]["anketa"]["issilavinimas"] = {
            "aprasas": None,
            "irasai": [{"issilavinimas": "Aukštasis universitetinis"}],
        }
        index = self._build([("2019-kovo-3-savivaldybiu-tarybu", "a-b", record)])
        entry = index["people"][0]["e"][0]
        # The facet lists the registry's official name, whatever the era's
        # card said (issue #137).
        self.assertEqual(index["municipalities"], ["Šiaulių rajono savivaldybė"])
        self.assertEqual(index["unresolvedMunicipalities"], [])
        self.assertEqual(entry["sv"], 0)
        self.assertEqual(entry["r"], "tm")
        self.assertEqual(entry["wp"], "AB Žeimena, inspektorė")
        self.assertEqual(entry["ed"], 10)

    def test_the_votes_and_the_constituency_ride_into_the_index(self):
        # Issue #133: 29.5 million preference votes on 59,275 candidacies
        # reached no consumer; the constituency was dropped on the way to
        # people.json.
        record = _record("A B", "1970-01-01")
        record["kandidatavimas"] = {
            "roles": ["daugiamandate", "vienmandate"],
            "vienmandate": {"apygarda": "Akmenės Joniškio", "apygardosNumeris": 39},
            "daugiamandate": {"sarasas": "LSDP", "numerisSarase": 9},
            "isrinktas": False,
            "pirmumoBalsai": 4321,
            "vienmandatesBalsai": {"isViso": 321, "procentai": 1.67, "vieta": 7},
            "vienmandatesBalsai2": {"isViso": 6999, "procentai": 55.5, "vieta": 1},
        }
        index = self._build([("2000-seimo", "a-b", record)])
        entry = index["people"][0]["e"][0]
        self.assertEqual(entry["v"], 4321)
        self.assertEqual(entry["cv"], 6999)
        self.assertEqual(index["constituencies"], ["Akmenės–Joniškio"])
        self.assertEqual(entry["ap"], 0)
        self.assertEqual(index["stats"]["candidaciesWithVotes"], 1)

    def test_a_2016_candidacy_carries_the_constituency_and_no_votes(self):
        record = _record("A B", "1970-01-01")
        record["normalized"]["profilis"] = {"kita": {"vienmandate-apygarda": {"pavadinimas": "x", "reiksme": "Dzūkijos (Nr. 69)", "nuorodos": []}}}
        index = self._build([("2016-seimo", "a-b", record)])
        entry = index["people"][0]["e"][0]
        self.assertEqual(index["constituencies"], ["Dzūkijos"])
        self.assertEqual(entry["ap"], 0)
        self.assertNotIn("v", entry)
        self.assertNotIn("cv", entry)
        self.assertEqual(index["stats"]["candidaciesWithVotes"], 0)

    def test_two_wordings_of_one_municipality_are_one_facet_row(self):
        # 'Vilniaus miesto' (2019) and 'Vilniaus miesto savivaldybė' (2015)
        # were two adjacent rows in the select, each showing half the
        # history (issue #137).
        older = _record("A B", "1970-01-01")
        older["kandidatavimas"] = {"savivaldybe": "Vilniaus miesto savivaldybė", "roles": ["tarybos-narys"], "isrinktas": False}
        newer = _record("A B", "1970-01-01")
        newer["kandidatavimas"] = {"savivaldybe": {"id": "1", "number": 1, "name": "Vilniaus miesto"}, "roles": ["tarybos-narys"], "isrinktas": False}
        index = self._build([("2015-kovo-1-savivaldybiu", "a-b", older), ("2019-kovo-3-savivaldybiu-tarybu", "a-b", newer)])
        self.assertEqual(index["municipalities"], ["Vilniaus miesto savivaldybė"])
        self.assertEqual([e["sv"] for e in index["people"][0]["e"]], [0, 0])

    def test_a_wording_the_registry_lacks_is_reported_not_hidden(self):
        record = _record("A B", "1970-01-01")
        record["kandidatavimas"] = {"savivaldybe": "Naujoji savivaldybė", "roles": ["tarybos-narys"], "isrinktas": False}
        index = self._build([("2019-kovo-3-savivaldybiu-tarybu", "a-b", record)])
        self.assertEqual(index["municipalities"], ["Naujoji savivaldybė"])
        self.assertEqual(index["unresolvedMunicipalities"], ["Naujoji savivaldybė"])

    def test_the_mayor_flag_is_only_carried_on_two_office_ballots(self):
        # On a mero-kind election the kind alone decides the office, so the
        # per-candidacy flag would be redundant bytes 1,368 times over.
        record = _record("A B", "1970-01-01")
        index = self._build([("2021-spalio-10-meru", "a-b", record)])
        self.assertNotIn("r", index["people"][0]["e"][0])

    def test_a_dual_candidacy_carries_both_offices_and_both_outcomes(self):
        # Issue #140: one code and one flag showed 448 council winners who
        # lost the mayoralty as elected mayors.
        record = _record("A B", "1970-01-01")
        record["kandidatavimas"] = {
            "savivaldybe": {"id": "1", "number": 13, "name": "Kaišiadorių rajono"},
            "roles": ["tarybos-narys", "meras"],
            "tarybosNarys": {"partyList": {"id": "2", "number": 4, "name": "LSDP"}, "listPosition": 1, "elected": True},
            "meras": {"round": "I", "elected": False},
            "isrinktas": True,
        }
        entry = self._build([("2019-kovo-3-savivaldybiu-tarybu", "a-b", record)])["people"][0]["e"][0]
        self.assertEqual(entry["r"], "tm")
        self.assertIs(entry["w"], True)
        self.assertIs(entry["wt"], True)
        self.assertIs(entry["wm"], False)

    def test_a_mayor_only_run_carries_the_code_and_no_split_outcome(self):
        record = _record("A B", "1970-01-01")
        record["kandidatavimas"] = {"savivaldybe": "Kauno miesto", "roles": ["meras"], "tarybosNarys": None, "meras": {"elected": False}, "isrinktas": False}
        entry = self._build([("2019-kovo-3-savivaldybiu-tarybu", "a-b", record)])["people"][0]["e"][0]
        self.assertEqual(entry["r"], "m")
        self.assertNotIn("wt", entry)
        self.assertNotIn("wm", entry)

    def test_a_council_only_run_carries_neither(self):
        record = _record("A B", "1970-01-01")
        record["kandidatavimas"] = {"savivaldybe": "Kauno miesto", "roles": ["tarybos-narys"], "tarybosNarys": {"elected": True}, "isrinktas": True}
        entry = self._build([("2019-kovo-3-savivaldybiu-tarybu", "a-b", record)])["people"][0]["e"][0]
        self.assertNotIn("r", entry)
        self.assertNotIn("wt", entry)

    def test_the_education_ladder_rides_with_lithuanian_labels(self):
        # The slugs are ASCII-folded, so de-slugging in the page would lose
        # the diacritics; the labels travel in people.json, rank-ordered.
        index = self._build([("2016-seimo", "a-b", _record("A B", "1970-01-01"))])
        levels = index["educationLevels"]
        self.assertEqual(len(levels), 13)
        self.assertEqual(
            levels[9], {"id": "aukstasis-universitetinis", "label": "Aukštasis universitetinis"}
        )

    def test_litas_declarations_are_converted_to_euro_and_flagged(self):
        # The 2012-2015 pages declare in litas; the index converts at the
        # irrevocable 3.4528 Lt/€ changeover rate so a person's series stays
        # comparable across 2015→2016, and flags the converted candidacy.
        litas = _record("A B", "1970-01-01")
        litas["normalized"]["turto-ir-pajamu-deklaracijos"] = {
            "privalomas-registruoti-turtas": 345280,
            "pinigines-lesos": "34 528,00",
            "gautos-pajamos": None,
            "valiuta": "Lt",
        }
        euro = _record("A B", "1970-01-01")
        euro["normalized"]["turto-ir-pajamu-deklaracijos"] = {
            "privalomas-registruoti-turtas": 100000,
            "pinigines-lesos": 10000,
            "gautos-pajamos": 5000,
        }
        index = self._build([("2012-seimo", "a-b", litas), ("2016-seimo", "a-b", euro)])
        entries = index["people"][0]["e"]
        # The fourth slot is the 1996-1997 form's combined turtas + piniginės
        # lėšos, which neither of these modern-shaped records declares.
        self.assertEqual(entries[0]["m"], [100000.0, 10000.0, None, None])
        self.assertTrue(entries[0].get("lt"))
        self.assertEqual(entries[1]["m"], [100000.0, 10000.0, 5000.0, None])
        self.assertNotIn("lt", entries[1])

    def test_the_archive_combined_turtas_lands_in_the_fourth_slot(self):
        # The 1996-1997 pages sum turtas and piniginės lėšos, so those two
        # keys are null and the combined figure carries the era's only asset
        # number. Babravičius 1996: 381,757 Lt at the changeover rate.
        record = _record("A B", "1970-01-01")
        record["normalized"]["turto-ir-pajamu-deklaracijos"] = {
            "privalomas-registruoti-turtas": None,
            "pinigines-lesos": None,
            "gautos-pajamos": 169391,
            "turtas-ir-pinigines-lesos-metu-pabaigoje": 381757,
            "valiuta": "Lt",
        }
        index = self._build([("1996-spalio-20-seimo", "a-b", record)])
        entry = index["people"][0]["e"][0]
        self.assertEqual(entry["m"], [None, None, 49059.02, 110564.47])
        self.assertTrue(entry.get("lt"))

    def test_undeclared_litas_record_carries_no_flag(self):
        record = _record("A B", "1970-01-01")
        record["normalized"]["turto-ir-pajamu-deklaracijos"] = {"valiuta": "Lt"}
        index = self._build([("2012-seimo", "a-b", record)])
        entry = index["people"][0]["e"][0]
        self.assertNotIn("m", entry)
        self.assertNotIn("lt", entry)


if __name__ == "__main__":
    unittest.main()
