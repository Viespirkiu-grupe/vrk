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

    def test_elected_note_becomes_the_win_flag(self):
        index = self._build(
            [
                (
                    "2016-seimo",
                    "a-b",
                    _record("A B", "1970-01-01", elected_note="Išrinkta pagal sąrašą"),
                ),
                ("2020-seimo", "a-b", _record("A B", "1970-01-01")),
            ]
        )
        entries = index["people"][0]["e"]
        self.assertTrue(entries[0].get("w"))
        self.assertNotIn("w", entries[1])

    def test_results_joined_elected_flag_becomes_the_win_flag(self):
        # The 2012-2015 pages carry no elected note; the results join sets
        # kandidatavimas.isrinktas instead, and false/null must not win.
        winner = _record("A B", "1970-01-01")
        winner["kandidatavimas"] = {"vrkCandidateId": "1", "isrinktas": True, "isrinktasKaip": "vienmandate"}
        loser = _record("A B", "1970-01-01")
        loser["kandidatavimas"] = {"vrkCandidateId": "2", "isrinktas": False}
        unknown = _record("A B", "1970-01-01")
        unknown["kandidatavimas"] = {"vrkCandidateId": "3", "isrinktas": None}
        index = self._build([("2012-seimo", "a-b", winner), ("2014-ep", "a-b", loser), ("2015-kovo-1-savivaldybiu", "a-b", unknown)])
        entries = index["people"][0]["e"]
        self.assertTrue(entries[0].get("w"))
        self.assertNotIn("w", entries[1])
        self.assertNotIn("w", entries[2])

    def test_archive_family_list_shaped_candidacy_becomes_the_win_flag(self):
        # The 1996-1999 Seimas archive family's kandidatavimas is a list under
        # `normalized` — a 1996 candidate could stand in a constituency and on
        # a list at once — so any elected candidacy wins the record, and a
        # record whose candidacies are all false does not.
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
        self.assertTrue(entries[0].get("w"))
        self.assertNotIn("w", entries[1])

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
