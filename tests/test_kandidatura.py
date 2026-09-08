"""The candidacy resolver (issue #93): five `kandidatavimas` shapes, one answer.

Each test is a synthetic record shaped exactly like its era's real ones (the
shapes are the measured ones from the corpus survey — camelCase root dicts,
the 1997 municipal kebab dict, the 1996-1999 archive list, the 2016-era
profile card, and the 2019/2023 string-vs-dict split)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import local_data

from scraper.shared.kandidatura import kandidatura

REPO_ROOT = Path(__file__).resolve().parents[1]


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
        # The archive's dashless spelling is the district's one name (issue
        # #133); the label rides beside it as published.
        self.assertEqual(answer["apygarda"], "Lazdijų–Druskininkų")
        self.assertEqual(answer["apygardos-numeris"], 71)
        self.assertEqual(answer["apygarda-raw"], "Lazdijų Druskininkų")
        self.assertEqual(answer["sarasas"], "Lietuvos lenkų rinkimų akcija")
        self.assertEqual(answer["numeris-sarase"], 17)
        self.assertEqual(answer["porinkiminis-numeris"], 15)
        # Elected if any one of the candidacies is.
        self.assertIs(answer["isrinktas"], True)

    def test_the_1996_rating_figures_and_the_round_votes(self):
        record = json.loads(json.dumps(self.RECORD))
        entries = record["normalized"]["kandidatavimas"]
        entries[0]["turai"] = [
            {"turas": 1, "apygardos-numeris": 71, "balsai-apygardoje": 388, "balsai-pastu": 10, "balsai": 398, "vieta": 9, "saltinis": "https://www.vrk.lt/r1"},
        ]
        entries[1].update({"teigiami-balsai": 193, "neigiami-balsai": 13, "reitingo-balai": 101836, "reitingo-saltinis": "https://www.vrk.lt/rk"})
        answer = kandidatura(record, "seimo")
        # The positive votes are the era's preference vote, and the measure says so.
        self.assertEqual(answer["pirmumo-balsai"], 193)
        self.assertEqual(answer["pirmumo-balsu-matas"], "teigiami-balsai")
        self.assertEqual((answer["teigiami-balsai"], answer["neigiami-balsai"], answer["reitingo-balai"]), (193, 13, 101836))
        self.assertEqual(answer["apygardos-turai"], [{"turas": 1, "balsai": 398, "procentai": None, "vieta": 9, "saltinis": "https://www.vrk.lt/r1"}])
        self.assertEqual((answer["apygardos-balsai"], answer["apygardos-turas"], answer["apygardos-vieta"]), (398, 1, 9))
        self.assertEqual(answer["balsu-saltinis"], "https://www.vrk.lt/rk")
        self.assertIsNone(answer["sarasas-balsai"])

    def test_a_by_election_entry_has_round_votes_and_no_list(self):
        record = {"normalized": {"kandidatavimas": [{
            "apygarda": "Nevėžio", "apygardos-numeris": 26, "iskele": "LDDP", "numeris-sarase": None, "isrinktas": True,
            "turai": [{"turas": 1, "balsai": 4051, "vieta": 1, "saltinis": "https://www.vrk.lt/r1"}, {"turas": 2, "balsai": 6000, "vieta": 1, "saltinis": "https://www.vrk.lt/r2"}],
        }]}}
        answer = kandidatura(record, "seimo")
        self.assertIsNone(answer["pirmumo-balsai"])
        self.assertEqual([r["balsai"] for r in answer["apygardos-turai"]], [4051, 6000])
        self.assertEqual((answer["apygardos-balsai"], answer["apygardos-turas"], answer["apygardos-vieta"]), (6000, 2, 1))
        self.assertEqual(answer["balsu-saltinis"], "https://www.vrk.lt/r2")


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
        self.assertEqual(answer["savivaldybe"], "Švenčionių rajono savivaldybė")
        self.assertEqual(answer["savivaldybe-id"], "svencioniu-rajono")
        self.assertEqual(answer["savivaldybe-raw"], "Švenčionių rajono")
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
        answer = kandidatura(record, "savivaldybiu")
        self.assertIs(answer["isrinktas"], True)
        self.assertIs(answer["isrinktas-tarybos-nariu"], True)
        self.assertIsNone(answer["isrinktas-meru"])


class Seimas2000Root(unittest.TestCase):
    RECORD = {
        "kandidatavimas": {
            "roles": ["daugiamandate", "vienmandate"],
            "vienmandate": {"apygarda": "Šilainių", "apygardosNumeris": 21},
            "daugiamandate": {"sarasas": "Lietuvos centro sąjunga", "numerisSarase": 9},
            "isrinktas": False,
            "porinkiminisNumerisSarase": 12,
            "pirmumoBalsai": 22,
            "partinisReitingas": 124,
            "reitingoBalai": 0,
            "pirmumoBalsuSaltinis": "https://www.vrk.lt/rdpbl",
            "vienmandatesBalsai": {"balsadezese": 301, "pastu": 20, "isViso": 321, "procentai": 1.67, "vieta": 7, "saltinis": "https://www.vrk.lt/rvapgl"},
        },
        "normalized": {},
    }

    def test_constituency_and_list_are_separate_facts(self):
        answer = kandidatura(self.RECORD, "seimo")
        self.assertEqual(answer["vaidmuo"], "seimo-narys")
        self.assertEqual(answer["apygarda"], "Šilainių")
        self.assertEqual(answer["apygardos-numeris"], 21)
        self.assertEqual(answer["sarasas"], "Lietuvos centro sąjunga")
        self.assertEqual(answer["numeris-sarase"], 9)
        self.assertEqual(answer["porinkiminis-numeris"], 12)
        self.assertIs(answer["isrinktas"], False)

    def test_the_votes_of_both_races(self):
        answer = kandidatura(self.RECORD, "seimo")
        self.assertEqual((answer["pirmumo-balsai"], answer["pirmumo-balsu-matas"], answer["reitingo-balai"]), (22, "pirmumo-balsai", 0))
        self.assertEqual(answer["apygardos-turai"], [{"turas": 1, "balsai": 321, "procentai": 1.67, "vieta": 7, "saltinis": "https://www.vrk.lt/rvapgl"}])
        self.assertEqual((answer["apygardos-balsai"], answer["apygardos-turas"], answer["apygardos-vieta"], answer["apygardos-procentai"]), (321, 1, 7, 1.67))
        self.assertEqual(answer["balsu-saltinis"], "https://www.vrk.lt/rdpbl")

    def test_a_runoff_is_the_second_round_and_the_flat_figures_follow_it(self):
        record = json.loads(json.dumps(self.RECORD))
        del record["kandidatavimas"]["pirmumoBalsai"]
        del record["kandidatavimas"]["pirmumoBalsuSaltinis"]
        record["kandidatavimas"]["vienmandatesBalsai2"] = {"isViso": 6999, "procentai": 55.52, "vieta": 1, "saltinis": "https://www.vrk.lt/r2"}
        answer = kandidatura(record, "seimo")
        self.assertEqual([r["turas"] for r in answer["apygardos-turai"]], [1, 2])
        self.assertEqual((answer["apygardos-balsai"], answer["apygardos-turas"], answer["apygardos-vieta"]), (6999, 2, 1))
        self.assertIsNone(answer["pirmumo-balsai"])
        self.assertIsNone(answer["pirmumo-balsu-matas"])
        self.assertEqual(answer["balsu-saltinis"], "https://www.vrk.lt/r2")

    def test_a_list_only_candidate_has_no_constituency(self):
        # The 2000-2012 cards print "Daugiamandatė" in the constituency row
        # of a list-only candidate: 2,980 rows shipped it as a district.
        record = {"kandidatavimas": {"roles": ["daugiamandate"], "isrinktas": False}, "normalized": {}}
        _kita(record, apygarda="Daugiamandatė", sarasas="LSDP", numeris_sarase="7")
        answer = kandidatura(record, "seimo")
        self.assertIsNone(answer["apygarda"])
        self.assertIsNone(answer["apygardos-numeris"])
        self.assertEqual(answer["apygarda-raw"], "Daugiamandatė")
        self.assertEqual(answer["sarasas"], "LSDP")

    def test_a_presidential_race_carries_its_rounds(self):
        record = {"kandidatavimas": {"isrinktas": True, "turai": [
            {"turas": 1, "balsai": 147610, "balsai-apylinkese": 126485, "balsai-pastu": 21125, "procentai-nuo-dalyvavusiu": 11.49, "procentai-nuo-galiojanciu": 11.85, "saltinis": "https://www.vrk.lt/p1"},
            {"turas": 2, "balsai": 700000, "procentai-nuo-galiojanciu": 52.1, "saltinis": "https://www.vrk.lt/p2"},
        ]}, "normalized": {}}
        answer = kandidatura(record, "prezidento")
        self.assertEqual(answer["vaidmuo"], "prezidentas")
        self.assertEqual([(r["turas"], r["balsai"], r["procentai"], r["vieta"]) for r in answer["apygardos-turai"]], [(1, 147610, 11.85, None), (2, 700000, 52.1, None)])
        self.assertEqual((answer["apygardos-balsai"], answer["apygardos-turas"]), (700000, 2))
        self.assertEqual(answer["balsu-saltinis"], "https://www.vrk.lt/p2")


class Municipal2000Root(unittest.TestCase):
    def test_the_lists_votes_are_the_lists_not_the_candidates(self):
        record = {"kandidatavimas": {
            "savivaldybe": "Šiaulių rajono", "roles": ["tarybos-narys"],
            "tarybosNarys": {"partyList": "Koalicija", "listPosition": 29, "sarasoBalsai": 3781, "sarasoMandatai": 5},
            "isrinktas": False, "porinkiminisNumerisSarase": 18, "pirmumoBalsai": 50, "pirmumoBalsuSaltinis": "https://www.vrk.lt/rpb",
        }, "normalized": {}}
        answer = kandidatura(record, "savivaldybiu")
        self.assertEqual((answer["pirmumo-balsai"], answer["sarasas-balsai"]), (50, 3781))
        self.assertEqual(answer["apygardos-turai"], [])
        self.assertIsNone(answer["apygardos-balsai"])
        self.assertEqual(answer["balsu-saltinis"], "https://www.vrk.lt/rpb")


class ModernCard(unittest.TestCase):
    def test_the_2016_and_2020_labels_are_one_district_and_no_votes(self):
        for label, number in (("Dzūkijos (Nr. 69)", 69), ("69. Dzūkijos", 69), ("Dzūkijos Nr. 69", 69), ("Dzūkijos", None)):
            with self.subTest(label):
                record = {"kandidatavimas": {"isrinktas": False}, "normalized": {}}
                _kita(record, vienmandate_apygarda=label, turas="I")
                answer = kandidatura(record, "seimo")
                self.assertEqual(answer["apygarda"], "Dzūkijos")
                self.assertEqual(answer["apygardos-numeris"], number)
                self.assertEqual(answer["apygarda-raw"], label)
                self.assertIsNone(answer["pirmumo-balsai"])
                self.assertIsNone(answer["balsu-saltinis"])


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
        self.assertEqual(answer["savivaldybe"], "Kauno miesto savivaldybė")
        self.assertEqual(answer["savivaldybe-id"], "kauno-miesto")
        self.assertEqual(answer["savivaldybe-raw"], "Kauno miesto")
        self.assertEqual(answer["sarasas"], "Tėvynės sąjunga")
        self.assertEqual(answer["numeris-sarase"], 28)
        self.assertEqual(answer["porinkiminis-numeris"], 32)

    def test_dual_candidacy_takes_the_mayoral_office(self):
        answer = kandidatura(self.RECORD, "savivaldybiu")
        self.assertEqual(answer["vaidmuo"], "meras")
        self.assertEqual(answer["vaidmenys"], ["tarybos-narys", "meras"])

    def test_each_office_keeps_its_own_outcome(self):
        # 228 (2019) + 220 (2023) records: elected to the council, not mayor.
        # The office off `vaidmuo` and the outcome off `isrinktas` made them
        # elected mayors (issue #140).
        record = json.loads(json.dumps(self.RECORD))
        record["kandidatavimas"]["tarybosNarys"]["elected"] = True
        record["kandidatavimas"]["isrinktas"] = True
        answer = kandidatura(record, "savivaldybiu")
        self.assertIs(answer["isrinktas"], True)
        self.assertIs(answer["isrinktas-tarybos-nariu"], True)
        self.assertIs(answer["isrinktas-meru"], False)
        # The reverse: the mayor-elect's list seat passes on.
        record["kandidatavimas"]["tarybosNarys"]["elected"] = False
        record["kandidatavimas"]["meras"]["elected"] = True
        answer = kandidatura(record, "savivaldybiu")
        self.assertIs(answer["isrinktas-tarybos-nariu"], False)
        self.assertIs(answer["isrinktas-meru"], True)

    def test_a_mayor_only_candidacy_has_no_council_outcome(self):
        record = {
            "kandidatavimas": {"roles": ["meras"], "tarybosNarys": None, "meras": {"round": "I", "elected": True}, "isrinktas": True},
            "normalized": {},
        }
        answer = kandidatura(record, "savivaldybiu")
        self.assertEqual(answer["vaidmenys"], ["meras"])
        self.assertIsNone(answer["isrinktas-tarybos-nariu"])
        self.assertIs(answer["isrinktas-meru"], True)

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
        self.assertEqual(answer["savivaldybe"], "Vilniaus miesto savivaldybė")
        self.assertEqual(answer["sarasas"], "Darbo partija")
        self.assertEqual(answer["porinkiminis-numeris"], 2)

    def test_every_eras_wording_joins_to_one_municipality(self):
        # Issue #137: 'Vilniaus miesto' (1997/2000/2002/2019/2023) and
        # 'Vilniaus miesto savivaldybė' (2007/2011/2015) are one body; so are
        # 1997's 'Birštono miesto' and the later 'Birštono' / 'Birštono
        # savivaldybė'. The 1997 Marijampolė city and district stay apart from
        # the 2000 municipality that replaced them both.
        def resolve(raw):
            record = {"kandidatavimas": {"savivaldybe": raw, "isrinktas": False}, "normalized": {}}
            answer = kandidatura(record, "savivaldybiu")
            return answer["savivaldybe-id"], answer["savivaldybe"]

        self.assertEqual(resolve("Vilniaus miesto"), resolve("Vilniaus miesto savivaldybė"))
        self.assertEqual(resolve("Birštono miesto"), resolve("Birštono savivaldybė"))
        self.assertEqual(resolve("Palangos savivaldybė")[0], "palangos-miesto")
        self.assertEqual(resolve("Marijampolės miesto")[0], "marijampoles-miesto")
        self.assertEqual(resolve("Marijampolės rajono")[0], "marijampoles-rajono")
        self.assertEqual(resolve("Marijampolės")[0], "marijampoles")
        self.assertNotEqual(resolve("Alytaus miesto")[0], resolve("Alytaus rajono")[0])

    def test_an_unregistered_wording_keeps_itself_and_no_id(self):
        record = {"kandidatavimas": {"savivaldybe": "Nežinoma vietovė (3)", "isrinktas": False}, "normalized": {}}
        answer = kandidatura(record, "savivaldybiu")
        self.assertIsNone(answer["savivaldybe-id"])
        self.assertEqual(answer["savivaldybe"], "Nežinoma vietovė")
        self.assertEqual(answer["savivaldybe-raw"], "Nežinoma vietovė (3)")


class Municipal2015(unittest.TestCase):
    """The 2015 ballots carry `elected: null` on both office blocks; the seat
    the results file named (`isrinktasKaip`) is the per-office answer."""

    def _record(self, roles, elected, seat=None, **extra):
        return {
            "kandidatavimas": {
                "roles": roles,
                "tarybosNarys": {"partyList": "Darbo partija", "listPosition": 1, "elected": None} if "tarybos-narys" in roles else None,
                "meras": {"nominatedBy": "Darbo partija", "elected": None} if "meras" in roles else None,
                "isrinktas": elected,
                **({"isrinktasKaip": seat} if seat else {}),
                **extra,
            },
            "normalized": {},
        }

    def test_a_dual_candidate_elected_to_the_council_lost_the_mayoralty(self):
        # 236 of 2015's 292 elected dual candidates -- shipped as mayors.
        answer = kandidatura(self._record(["meras", "tarybos-narys"], True, "tarybos-narys"), "savivaldybiu")
        self.assertEqual(answer["vaidmuo"], "meras")
        self.assertIs(answer["isrinktas-tarybos-nariu"], True)
        self.assertIs(answer["isrinktas-meru"], False)

    def test_a_dual_candidate_elected_mayor_took_the_mayoral_seat(self):
        answer = kandidatura(self._record(["meras", "tarybos-narys"], True, "meras", rezultatuTuras=2), "savivaldybiu")
        self.assertIs(answer["isrinktas-meru"], True)
        self.assertIs(answer["isrinktas-tarybos-nariu"], False)

    def test_an_annulled_dual_candidate_lost_both(self):
        # Šilutė/Trakai March 2015: the results page named them, VRK's
        # decision unmade it; isrinktas is false with the seat still recorded.
        answer = kandidatura(
            self._record(["meras", "tarybos-narys"], False, "tarybos-narys", rezultataiPanaikinti="Sprendimas Nr. …"),
            "savivaldybiu",
        )
        self.assertIs(answer["isrinktas-tarybos-nariu"], False)
        self.assertIs(answer["isrinktas-meru"], False)

    def test_elected_without_a_named_seat_leaves_both_offices_unknown(self):
        answer = kandidatura(self._record(["meras", "tarybos-narys"], True), "savivaldybiu")
        self.assertIs(answer["isrinktas"], True)
        self.assertIsNone(answer["isrinktas-tarybos-nariu"])
        self.assertIsNone(answer["isrinktas-meru"])

    def test_a_council_only_ballot_needs_no_seat(self):
        answer = kandidatura(self._record(["tarybos-narys"], True, "tarybos-narys"), "savivaldybiu")
        self.assertEqual(answer["vaidmenys"], ["tarybos-narys"])
        self.assertIs(answer["isrinktas-tarybos-nariu"], True)
        self.assertIsNone(answer["isrinktas-meru"])

    def test_no_results_file_leaves_every_outcome_unknown(self):
        answer = kandidatura(self._record(["meras", "tarybos-narys"], None), "savivaldybiu")
        self.assertIsNone(answer["isrinktas"])
        self.assertIsNone(answer["isrinktas-tarybos-nariu"])
        self.assertIsNone(answer["isrinktas-meru"])


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
        # the municipal generals' own names.
        record = _kita({"kandidatavimas": {"isrinktas": False}}, savivaldybe="Jonavos rajono (10)")
        self.assertEqual(kandidatura(record, "mero")["savivaldybe-id"], "jonavos-rajono")
        record = _kita({"kandidatavimas": {"isrinktas": False}}, savivaldybe="Telšių rajono (Nr. 51)")
        answer = kandidatura(record, "mero")
        self.assertEqual(answer["savivaldybe"], "Telšių rajono savivaldybė")
        self.assertEqual(answer["savivaldybe-raw"], "Telšių rajono (Nr. 51)")
        self.assertEqual(answer["vaidmuo"], "meras")
        # A mayoral election is one office: its outcome is the mayoralty's.
        self.assertEqual(answer["vaidmenys"], ["meras"])
        self.assertIs(answer["isrinktas-meru"], False)
        self.assertIsNone(answer["isrinktas-tarybos-nariu"])


class Presidential(unittest.TestCase):
    def test_office_only(self):
        answer = kandidatura({"kandidatavimas": {"isrinktas": False}, "normalized": {}}, "prezidento")
        self.assertEqual(answer["vaidmuo"], "prezidentas")
        self.assertEqual(answer["vaidmenys"], ["prezidentas"])
        self.assertIsNone(answer["sarasas"])
        self.assertIsNone(answer["savivaldybe"])
        # Neither municipal office was on the ballot.
        self.assertIsNone(answer["isrinktas-tarybos-nariu"])
        self.assertIsNone(answer["isrinktas-meru"])

    def test_ep_office(self):
        answer = kandidatura({"kandidatavimas": {"isrinktas": False}, "normalized": {}}, "ep")
        self.assertEqual(answer["vaidmuo"], "ep-narys")


class CorpusOfficeTests(unittest.TestCase):
    """The population the issue measured, when data/ is here: 60 elected
    mayors a year -- 57 in March 2015, three races annulled and re-run --
    against the 288/280/293 the collapsed reading gave."""

    EXPECTED_MAYORS = {
        "2015-kovo-1-savivaldybiu": 57,
        "2019-kovo-3-savivaldybiu-tarybu": 60,
        "2023-kovo-5-savivaldybiu-tarybu-ir-meru": 60,
    }

    def test_every_year_elected_as_many_mayors_as_it_has_municipalities(self):
        for election_id, expected in self.EXPECTED_MAYORS.items():
            with self.subTest(election_id):
                directory = REPO_ROOT / "data" / election_id
                local_data.require(directory)
                mayors = council_only_mayors = dual = 0
                for path in directory.glob("*.json"):
                    answer = kandidatura(json.loads(path.read_text(encoding="utf-8")), "savivaldybiu")
                    if len(answer["vaidmenys"]) == 2:
                        dual += 1
                    if answer["isrinktas-meru"] is True:
                        mayors += 1
                    if answer["vaidmuo"] == "meras" and answer["isrinktas"] is True and answer["isrinktas-meru"] is not True:
                        council_only_mayors += 1
                self.assertEqual(mayors, expected)
                self.assertGreater(council_only_mayors, 200, "the council winners who lost the mayoralty")
                self.assertGreater(dual, 300)


if __name__ == "__main__":
    unittest.main()
