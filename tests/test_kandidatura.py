"""The candidacy resolver (issue #93): five `kandidatavimas` shapes, one answer.

Each test is a synthetic record shaped exactly like its era's real ones (the
shapes are the measured ones from the corpus survey — camelCase root dicts,
the 1997 municipal kebab dict, the 1996-1999 archive list, the 2016-era
profile card, and the 2019/2023 string-vs-dict split)."""

from __future__ import annotations

import unittest

from scraper.shared.kandidatura import kandidatura


def _kita(record, **entries):
    profile = record.setdefault("normalized", {}).setdefault("profilis", {})
    profile["kita"] = {
        key.replace("_", "-"): {"pavadinimas": key, "reiksme": value, "nuorodos": []}
        for key, value in entries.items()
    }
    return record


class ArchiveList(unittest.TestCase):
    RECORD = {
        "normalized": {
            "kandidatavimas": [
                {
                    "apygarda": "Lazdijų Druskininkų",
                    "apygardos-numeris": 71,
                    "iskele": "Lietuvos lenkų rinkimų akcija",
                    "numeris-sarase": None,
                    "isrinktas": False,
                    "turai": [{"turas": 1}],
                },
                {
                    "apygarda": "Daugiamandatė",
                    "apygardos-numeris": None,
                    "iskele": "Lietuvos lenkų rinkimų akcija",
                    "numeris-sarase": 17,
                    "porinkiminis-numeris-sarase": 15,
                    "isrinktas": True,
                },
            ]
        }
    }

    def test_both_candidacies_fill_one_row(self):
        answer = kandidatura(self.RECORD, "seimo")
        self.assertEqual(answer["vaidmuo"], "seimo-narys")
        self.assertEqual(answer["apygarda"], "Lazdijų Druskininkų")
        self.assertEqual(answer["sarasas"], "Lietuvos lenkų rinkimų akcija")
        self.assertEqual(answer["numeris-sarase"], 17)
        self.assertEqual(answer["porinkiminis-numeris"], 15)
        # Elected if any one of the candidacies is.
        self.assertIs(answer["isrinktas"], True)


class Municipal1997(unittest.TestCase):
    def test_dict_shape_and_no_results(self):
        record = {
            "normalized": {
                "kandidatavimas": {
                    "savivaldybe": "Švenčionių rajono",
                    "iskele": "Lietuvos socialdemokratų partija",
                    "numeris-sarase": 2,
                }
            }
        }
        answer = kandidatura(record, "savivaldybiu")
        self.assertEqual(answer["vaidmuo"], "tarybos-narys")
        self.assertEqual(answer["savivaldybe"], "Švenčionių rajono")
        self.assertEqual(answer["sarasas"], "Lietuvos socialdemokratų partija")
        self.assertEqual(answer["numeris-sarase"], 2)
        # A record parsed without the election's results file carries no
        # `isrinktas` key: the absence must stay None, never read as false.
        self.assertIsNone(answer["isrinktas"])

    def test_dict_shape_carries_the_joined_elected_flag(self):
        # Since issue #92 the 1997 pair's records carry `isrinktas` joined
        # from VRK's per-municipality elected pages, a bool on every record.
        record = {
            "normalized": {
                "kandidatavimas": {
                    "savivaldybe": "Švenčionių rajono",
                    "iskele": "Lietuvos liberalų sąjunga",
                    "numeris-sarase": 1,
                    "isrinktas": True,
                    "isrinktas-kaip": "tarybos-narys",
                    "rezultatu-saltinis": "https://www.vrk.lt/…/rikl.htm-264.htm",
                }
            }
        }
        self.assertIs(kandidatura(record, "savivaldybiu")["isrinktas"], True)


class Seimas2000Root(unittest.TestCase):
    def test_constituency_and_list_are_separate_facts(self):
        record = {
            "kandidatavimas": {
                "roles": ["daugiamandate", "vienmandate"],
                "vienmandate": {"apygarda": "Šilainių", "apygardosNumeris": 21},
                "daugiamandate": {"sarasas": "Lietuvos centro sąjunga", "numerisSarase": 9},
                "isrinktas": False,
                "porinkiminisNumerisSarase": 12,
            },
            "normalized": {},
        }
        answer = kandidatura(record, "seimo")
        self.assertEqual(answer["vaidmuo"], "seimo-narys")
        self.assertEqual(answer["apygarda"], "Šilainių")
        self.assertEqual(answer["sarasas"], "Lietuvos centro sąjunga")
        self.assertEqual(answer["numeris-sarase"], 9)
        self.assertEqual(answer["porinkiminis-numeris"], 12)
        self.assertIs(answer["isrinktas"], False)


class Municipal2019(unittest.TestCase):
    RECORD = {
        "kandidatavimas": {
            "savivaldybe": {"id": "19972", "number": 15, "name": "Kauno miesto"},
            "roles": ["tarybos-narys", "meras"],
            "tarybosNarys": {
                "partyList": {"id": "28392", "number": 6, "name": "Tėvynės sąjunga"},
                "listPosition": 28,
                "postElectionPosition": 32,
                "elected": False,
            },
            "meras": {"round": "I", "elected": False},
            "isrinktas": False,
        },
        "normalized": {},
    }

    def test_dict_valued_fields_resolve_to_names(self):
        answer = kandidatura(self.RECORD, "savivaldybiu")
        self.assertEqual(answer["savivaldybe"], "Kauno miesto")
        self.assertEqual(answer["sarasas"], "Tėvynės sąjunga")
        self.assertEqual(answer["numeris-sarase"], 28)
        self.assertEqual(answer["porinkiminis-numeris"], 32)

    def test_dual_candidacy_takes_the_mayoral_office(self):
        self.assertEqual(kandidatura(self.RECORD, "savivaldybiu")["vaidmuo"], "meras")

    def test_string_valued_fields_resolve_too(self):
        # The same fields are plain strings in the 2000-2015 municipal eras
        # (issue #93's type split).
        record = {
            "kandidatavimas": {
                "savivaldybe": "Vilniaus miesto",
                "roles": ["tarybos-narys"],
                "tarybosNarys": {"partyList": "Darbo partija", "listPosition": 3},
                "isrinktas": True,
                "porinkiminisNumerisSarase": 2,
            },
            "normalized": {},
        }
        answer = kandidatura(record, "savivaldybiu")
        self.assertEqual(answer["vaidmuo"], "tarybos-narys")
        self.assertEqual(answer["savivaldybe"], "Vilniaus miesto")
        self.assertEqual(answer["sarasas"], "Darbo partija")
        self.assertEqual(answer["porinkiminis-numeris"], 2)


class Era2016(unittest.TestCase):
    def test_profile_card_fills_what_the_root_stub_lacks(self):
        record = _kita(
            {"kandidatavimas": {"isrinktas": True}},
            vienmandate_apygarda="Žirmūnų",
            sarasas="Lietuvos laisvės sąjunga",
            numeris_sarase="7",
            porinkiminis_eiles_numeris="4",
        )
        answer = kandidatura(record, "seimo")
        self.assertEqual(answer["vaidmuo"], "seimo-narys")
        self.assertEqual(answer["apygarda"], "Žirmūnų")
        self.assertEqual(answer["sarasas"], "Lietuvos laisvės sąjunga")
        self.assertEqual(answer["numeris-sarase"], 7)
        self.assertEqual(answer["porinkiminis-numeris"], 4)
        self.assertIs(answer["isrinktas"], True)

    def test_mayoral_card_municipality_number_is_stripped(self):
        # "Telšių rajono (Nr. 51)" and "Jonavos rajono (10)" must join with
        # the municipal generals' own clean names.
        record = _kita({"kandidatavimas": {"isrinktas": False}}, savivaldybe="Jonavos rajono (10)")
        self.assertEqual(kandidatura(record, "mero")["savivaldybe"], "Jonavos rajono")
        record = _kita({"kandidatavimas": {"isrinktas": False}}, savivaldybe="Telšių rajono (Nr. 51)")
        answer = kandidatura(record, "mero")
        self.assertEqual(answer["savivaldybe"], "Telšių rajono")
        self.assertEqual(answer["vaidmuo"], "meras")


class Presidential(unittest.TestCase):
    def test_office_only(self):
        answer = kandidatura({"kandidatavimas": {"isrinktas": False}, "normalized": {}}, "prezidento")
        self.assertEqual(answer["vaidmuo"], "prezidentas")
        self.assertIsNone(answer["sarasas"])
        self.assertIsNone(answer["savivaldybe"])

    def test_ep_office(self):
        answer = kandidatura({"kandidatavimas": {"isrinktas": False}, "normalized": {}}, "ep")
        self.assertEqual(answer["vaidmuo"], "ep-narys")


if __name__ == "__main__":
    unittest.main()
