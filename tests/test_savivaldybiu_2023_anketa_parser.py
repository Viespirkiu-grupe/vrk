import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.kupiskio_mero_2023.anketa_parser import _normalize_anketa_rows
from scraper.elections.savivaldybiu_2023.anketa_parser import parse_anketa_sample
from scraper.elections.savivaldybiu_2023.candidate_samples import expected_tabs_for
from scraper.shared.deklaracijos import DECLARATION_BLOCK_KEYS


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2023-kovo-5-savivaldybiu-tarybu-ir-meru"

ELECTION_ID = "2023-kovo-5-savivaldybiu-tarybu-ir-meru"

BASE_SECTIONS = [
    "profilis",
    "anketa",
    "biografija",
    "turto-ir-pajamu-deklaracijos",
    "privaciu-interesu-deklaracija",
    "kita",
]
MAYORAL_SECTIONS = [
    "profilis",
    "anketa",
    "biografija",
    "turto-ir-pajamu-deklaracijos",
    "privaciu-interesu-deklaracija",
    "politines-kampanijos-dalyvio-duomenys",
    "kita",
]


def _parse(candidate_id: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        output_path, _ = parse_anketa_sample(
            candidate_id=candidate_id,
            samples_root=SAMPLES_ROOT,
            output_root=Path(tmp),
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


class Savivaldybiu2023ExpectedTabsTests(unittest.TestCase):
    def test_campaign_tab_is_expected_only_of_mayoral_candidates(self) -> None:
        # A council candidate's campaign is run by the party list, so only the
        # people who also stand for mayor register a campaign of their own.
        # A fixed six-tab expectation would warn on 13,363 council candidates.
        for roles, campaign_expected in (
            (["tarybos-narys"], False),
            (["meras"], True),
            (["tarybos-narys", "meras"], True),
        ):
            with self.subTest(roles=roles):
                tabs = expected_tabs_for({"roles": roles})
                self.assertEqual(
                    "politines-kampanijos-dalyvio-duomenys" in tabs, campaign_expected
                )
                self.assertTrue(
                    {
                        "anketa",
                        "biografija",
                        "turto-ir-pajamu-deklaracijos",
                        "privaciu-interesu-deklaracijos",
                        "kita",
                    }.issubset(tabs)
                )


class Savivaldybiu2023AnketaParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rusteika = _parse("algimantas-rusteika-2423645")
        cls.gudaitis = _parse("algirdas-gudaitis-2420505")
        cls.zebrauskas = _parse("algirdas-zebrauskas-2424292")
        cls.sakalauskiene = _parse("ingrida-sakalauskiene-2425331")
        cls.urmanavicius = _parse("linas-urmanavicius-2421676")
        cls.majauskas = _parse("mykolas-majauskas-2420485")
        cls.vitkauskiene = _parse("rasa-vitkauskiene-2423015")
        cls.mockevicius = _parse("skirmantas-mockevicius-2422343")
        cls.mitrofanovas = _parse("vitalijus-mitrofanovas-2425352")

    @property
    def council_only(self) -> tuple[dict, ...]:
        return (self.rusteika, self.gudaitis, self.sakalauskiene, self.urmanavicius)

    @property
    def mayoral(self) -> tuple[dict, ...]:
        return (
            self.zebrauskas,
            self.majauskas,
            self.vitkauskiene,
            self.mockevicius,
            self.mitrofanovas,
        )

    @property
    def everyone(self) -> tuple[dict, ...]:
        return self.council_only + self.mayoral

    # ------------------------------------------------------------------
    # Top-level record
    # ------------------------------------------------------------------

    def test_top_level_fields(self) -> None:
        self.assertEqual(
            list(self.gudaitis.keys()),
            [
                "electionId",
                "candidateId",
                "candidateName",
                "candidateNote",
                "kandidatavimas",
                "source",
                "rawData",
                "normalized",
                "provenance",
            ],
        )
        self.assertEqual(self.gudaitis["electionId"], ELECTION_ID)
        self.assertEqual(self.gudaitis["candidateId"], "algirdas-gudaitis-2420505")
        self.assertEqual(self.gudaitis["candidateName"], "Algirdas GUDAITIS")
        self.assertIsNone(self.gudaitis["candidateNote"])
        self.assertTrue(
            self.gudaitis["source"]["candidateSourceUrl"].endswith(
                "savKandidatasAnketa_2023_rkndId-2420505.html"
            )
        )

    def test_candidate_id_carries_the_vrk_candidate_id(self) -> None:
        # 244 of 13,796 candidates collide on the bare name slug, and the batch
        # runner resumes off data/<candidateId>-<electionId>.json, so the id has
        # to be stable rather than order-dependent.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                vrk_id = payload["kandidatavimas"]["vrkCandidateId"]
                self.assertTrue(payload["candidateId"].endswith(f"-{vrk_id}"))
                self.assertTrue(
                    payload["source"]["candidateSourceUrl"].endswith(
                        f"savKandidatasAnketa_2023_rkndId-{vrk_id}.html"
                    )
                )

    # ------------------------------------------------------------------
    # kandidatavimas: the listing-only candidacy context
    # ------------------------------------------------------------------

    def test_kandidatavimas_block_shape(self) -> None:
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    list(payload["kandidatavimas"].keys()),
                    [
                        "vrkCandidateId",
                        "savivaldybe",
                        "roles",
                        "tarybosNarys",
                        "meras",
                        "isrinktas",
                    ],
                )
                self.assertEqual(
                    list(payload["kandidatavimas"]["savivaldybe"].keys()),
                    ["id", "number", "name"],
                )

    def test_kandidatavimas_council_only(self) -> None:
        # Council-only candidates carry a list seat and no mayoral candidacy.
        kandidatavimas = self.sakalauskiene["kandidatavimas"]
        self.assertEqual(kandidatavimas["vrkCandidateId"], "2425331")
        self.assertEqual(
            kandidatavimas["savivaldybe"],
            {"id": "21944", "number": 1, "name": "Akmenės rajono"},
        )
        self.assertEqual(kandidatavimas["roles"], ["tarybos-narys"])
        self.assertIsNone(kandidatavimas["meras"])
        self.assertFalse(kandidatavimas["isrinktas"])
        # List 5, not 25: the number is the party's number in this
        # municipality, and the two Akmenė fixtures pinned the group-header
        # value the sitemap builder emitted before the 2026-08-17 fix. Their
        # `index.json` carried it until issue #91's gate caught the
        # disagreement with `sitemaps/`, which
        # `tests/test_fixture_sitemap_agreement.py` now guards.
        self.assertEqual(
            kandidatavimas["tarybosNarys"],
            {
                "partyList": {
                    "id": "32298",
                    "number": 5,
                    "name": "Lietuvos socialdemokratų partija",
                },
                "listPosition": 30,
                "postElectionPosition": 17,
                "elected": False,
            },
        )

        # Coalition and political-committee lists are carried verbatim.
        self.assertEqual(
            self.rusteika["kandidatavimas"]["tarybosNarys"]["partyList"]["name"],
            "„STIPRI ŠEIMA – STIPRUS KAUNAS“ Krikščionių sąjungos ir Tautos ir "
            "teisingumo sąjungos (centristų, tautininkų) koalicija",
        )
        self.assertEqual(
            self.urmanavicius["kandidatavimas"]["tarybosNarys"]["partyList"]["name"],
            "Politinis komitetas „Už Druskininkus“",
        )
        self.assertTrue(self.urmanavicius["kandidatavimas"]["tarybosNarys"]["elected"])
        self.assertTrue(self.urmanavicius["kandidatavimas"]["isrinktas"])

    def test_kandidatavimas_mayor_only(self) -> None:
        kandidatavimas = self.mockevicius["kandidatavimas"]
        self.assertEqual(kandidatavimas["roles"], ["meras"])
        self.assertIsNone(kandidatavimas["tarybosNarys"])
        self.assertEqual(
            kandidatavimas["meras"],
            {"round": "II", "nominatedBy": "išsikėlė pats", "elected": True},
        )
        self.assertTrue(kandidatavimas["isrinktas"])

        self.assertEqual(
            self.majauskas["kandidatavimas"]["meras"],
            {"round": "I", "nominatedBy": "išsikėlė pats", "elected": False},
        )
        self.assertFalse(self.majauskas["kandidatavimas"]["isrinktas"])

    def test_kandidatavimas_dual_candidates_carry_both_roles(self) -> None:
        # 406 people stand for both a council seat and the mayoralty under one
        # VRK candidate id; the two candidacies are independent.
        self.assertEqual(
            self.vitkauskiene["kandidatavimas"]["roles"], ["tarybos-narys", "meras"]
        )
        self.assertFalse(self.vitkauskiene["kandidatavimas"]["tarybosNarys"]["elected"])
        self.assertEqual(
            self.vitkauskiene["kandidatavimas"]["meras"],
            {
                "round": "II",
                "nominatedBy": "Demokratų sąjunga „Vardan Lietuvos“",
                "elected": True,
            },
        )
        self.assertTrue(self.vitkauskiene["kandidatavimas"]["isrinktas"])

        # Elected to the council, beaten for mayor.
        self.assertEqual(
            self.zebrauskas["kandidatavimas"]["roles"], ["tarybos-narys", "meras"]
        )
        self.assertTrue(self.zebrauskas["kandidatavimas"]["tarybosNarys"]["elected"])
        self.assertFalse(self.zebrauskas["kandidatavimas"]["meras"]["elected"])
        self.assertEqual(
            self.zebrauskas["kandidatavimas"]["meras"]["nominatedBy"], "išsikėlė pats"
        )

        # Elected mayor in round I, not elected off the list.
        self.assertEqual(
            self.mitrofanovas["kandidatavimas"]["meras"],
            {
                "round": "I",
                "nominatedBy": "Lietuvos socialdemokratų partija",
                "elected": True,
            },
        )
        self.assertFalse(self.mitrofanovas["kandidatavimas"]["tarybosNarys"]["elected"])
        self.assertTrue(self.mitrofanovas["kandidatavimas"]["isrinktas"])

    # ------------------------------------------------------------------
    # Section presence
    # ------------------------------------------------------------------

    def test_normalized_section_order(self) -> None:
        for payload in self.mayoral:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    list(payload["normalized"].keys()), MAYORAL_SECTIONS
                )

    def test_council_only_candidates_have_no_campaign_section(self) -> None:
        # Not a parse failure: the campaign belongs to the party list, so these
        # pages publish five tabs and never a campaign one.
        for payload in self.council_only:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(list(payload["normalized"].keys()), BASE_SECTIONS)
                self.assertNotIn(
                    "politinesKampanijosDalyvioDuomenys", payload["rawData"]
                )
                self.assertEqual(payload["kandidatavimas"]["roles"], ["tarybos-narys"])

    def test_raw_data_section_order(self) -> None:
        self.assertEqual(
            list(self.zebrauskas["rawData"].keys()),
            [
                "profile",
                "anketa",
                "biografija",
                "turtoIrPajamuDeklaracijos",
                "privaciuInteresuDeklaracija",
                "politinesKampanijosDalyvioDuomenys",
                "kita",
            ],
        )
        self.assertEqual(
            list(self.rusteika["rawData"].keys()),
            [
                "profile",
                "anketa",
                "biografija",
                "turtoIrPajamuDeklaracijos",
                "privaciuInteresuDeklaracija",
                "kita",
            ],
        )

    # ------------------------------------------------------------------
    # profilis
    # ------------------------------------------------------------------

    def test_profilis_shape(self) -> None:
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                profilis = payload["normalized"]["profilis"]
                self.assertEqual(
                    list(profilis.keys()),
                    ["vardas-pavarde", "pastaba", "nuotrauka", "kita", "kandidatuoja-i", "dokumentu-pateikimo-data"],
                )
                # The page links a kandImg URL; the record carries the archived
                # sidecar and photoMeta remembers the URL (issue #118).
                self.assertEqual(profilis["nuotrauka"], f"photos/{payload['candidateId']}.jpg")
                photo_url = payload["rawData"]["profile"]["photoMeta"]["url"]
                self.assertIn("kandImg", photo_url)
                self.assertTrue(photo_url.startswith("https://"))

    def test_profilis_kita_keys_vary_by_role(self) -> None:
        # Council-only pages carry neither a nomination line nor a round; the
        # mayoral pages carry both, under a role-specific nomination label.
        council_keys = [
            "savivaldybe",
            "sarasas",
            "numeris-sarase",
            "porinkiminis-numeris-sarase",
        ]
        for payload in self.council_only:
            with self.subTest(candidate=payload["candidateId"]):
                kita = payload["normalized"]["profilis"]["kita"]
                self.assertEqual(list(kita.keys()), council_keys)
                self.assertNotIn("turas", kita)
                self.assertFalse([key for key in kita if key.startswith("iskele-")])

        for payload, nomination_key in (
            (self.zebrauskas, "iskele-i-tarybos-narius-ir-merus"),
            (self.vitkauskiene, "iskele-i-tarybos-narius-ir-merus"),
            (self.mitrofanovas, "iskele-i-tarybos-narius-ir-merus"),
            (self.majauskas, "iskele-i-savivaldybes-merus"),
            (self.mockevicius, "iskele-i-savivaldybes-merus"),
        ):
            with self.subTest(candidate=payload["candidateId"]):
                kita = payload["normalized"]["profilis"]["kita"]
                self.assertEqual(
                    list(kita.keys()),
                    [
                        "savivaldybe",
                        nomination_key,
                        "turas",
                        "sarasas",
                        "numeris-sarase",
                        "porinkiminis-numeris-sarase",
                    ],
                )
                self.assertEqual(
                    kita["turas"]["reiksme"],
                    payload["kandidatavimas"]["meras"]["round"],
                )
                self.assertEqual(
                    kita[nomination_key]["reiksme"],
                    payload["kandidatavimas"]["meras"]["nominatedBy"],
                )

    def test_profilis_kita_values(self) -> None:
        kita = self.rusteika["normalized"]["profilis"]["kita"]
        self.assertEqual(kita["savivaldybe"]["pavadinimas"], "Savivaldybė")
        self.assertEqual(kita["savivaldybe"]["reiksme"], "Kauno miesto (15)")
        self.assertTrue(
            kita["savivaldybe"]["nuorodos"][0].endswith(
                "savKandidataiApygardoje_rpgId-21934.html"
            )
        )
        self.assertEqual(kita["numeris-sarase"]["reiksme"], "4")
        self.assertEqual(kita["porinkiminis-numeris-sarase"]["reiksme"], "1")

        # Mayor-only candidates stand on no list, so the three list rows are
        # published empty rather than dropped.
        mayor_kita = self.mockevicius["normalized"]["profilis"]["kita"]
        self.assertIsNone(mayor_kita["sarasas"]["reiksme"])
        self.assertIsNone(mayor_kita["numeris-sarase"]["reiksme"])
        self.assertIsNone(mayor_kita["porinkiminis-numeris-sarase"]["reiksme"])
        self.assertIsNone(self.mockevicius["kandidatavimas"]["tarybosNarys"])

    def test_profilis_pastaba_forms(self) -> None:
        # Three shapes appear: the list-elected note (gendered, and naming the
        # list in the genitive), the mayoral note, and nothing at all.
        self.assertEqual(
            self.gudaitis["normalized"]["profilis"]["pastaba"],
            "Išrinktas pagal Demokratų sąjungos „Vardan Lietuvos“ sąrašą",
        )
        self.assertEqual(
            self.urmanavicius["normalized"]["profilis"]["pastaba"],
            "Išrinktas pagal Politinio komiteto „Už Druskininkus“ sąrašą",
        )
        self.assertEqual(
            self.zebrauskas["normalized"]["profilis"]["pastaba"],
            "Išrinktas pagal Koalicijos „Geriausias pasirinkimas“ (Partijos "
            "„Laisvė ir teisingumas“, Laisvės partijos, Liberalų sąjūdžio) sąrašą",
        )

        self.assertEqual(
            self.mitrofanovas["normalized"]["profilis"]["pastaba"],
            "Išrinktas Akmenės rajono (Nr.1) savivaldybėje I ture",
        )
        self.assertEqual(
            self.mockevicius["normalized"]["profilis"]["pastaba"],
            "Išrinktas Jurbarko rajono (Nr.12) savivaldybėje II ture",
        )
        # The mayoral note is gendered too.
        self.assertEqual(
            self.vitkauskiene["normalized"]["profilis"]["pastaba"],
            "Išrinkta Alytaus rajono (Nr.3) savivaldybėje II ture",
        )

        for payload in (self.rusteika, self.sakalauskiene, self.majauskas):
            with self.subTest(candidate=payload["candidateId"]):
                self.assertIsNone(payload["normalized"]["profilis"]["pastaba"])
                self.assertFalse(payload["kandidatavimas"]["isrinktas"])

    # ------------------------------------------------------------------
    # anketa
    # ------------------------------------------------------------------

    def test_anketa_key_set(self) -> None:
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    list(payload["normalized"]["anketa"].keys()),
                    [
                        "adresas",
                        "einamos-pareigos",
                        "narystes-politinese-organizacijose",
                        "pareiskimai",
                        "teistumo-detales",
                        "mandato-netekimo-detales",
                    ],
                )

    def test_anketa_core_fields(self) -> None:
        anketa = self.zebrauskas["normalized"]["anketa"]
        self.assertEqual(anketa["adresas"], "Telšiai")
        self.assertEqual(
            anketa["einamos-pareigos"],
            "Telšių rajono savivaldybės tarybos narys. UAB Architekto studija "
            "direktorius.",
        )
        self.assertEqual(
            self.majauskas["normalized"]["anketa"]["einamos-pareigos"],
            "Lietuvos Respublikos Seimo narys",
        )

    def test_anketa_membership_answer_is_inline_text(self) -> None:
        # This vintage answers Q8 inline instead of with the 2024 membership
        # table, so the record list stays empty.
        for payload, text in (
            (self.zebrauskas, "Nepartinis"),
            (self.rusteika, "Asociacija Lietuvos šeimų sąjūdis"),
            (self.urmanavicius, 'Politinis komitetas "Už Druskininkus"'),
            (self.mitrofanovas, "LSDP"),
        ):
            with self.subTest(candidate=payload["candidateId"]):
                naryste = payload["normalized"]["anketa"][
                    "narystes-politinese-organizacijose"
                ]
                self.assertEqual(list(naryste.keys()), ["tekstas", "irasai"])
                self.assertEqual(naryste["tekstas"], text)
                self.assertEqual(naryste["irasai"], [])

    def test_anketa_pareiskimai_keys(self) -> None:
        # The nine "Pagal Rinkimų kodekso 76 straipsnį" declarations, Q9-Q14.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                pareiskimai = payload["normalized"]["anketa"]["pareiskimai"]
                self.assertEqual(
                    list(pareiskimai.keys()),
                    [
                        "ar-kitos-valstybes-institucijos-narys",
                        "ar-eina-nesuderinamas-pareigas",
                        "ar-bendradarbiavote-su-ssrs-tarnybomis",
                        "ar-nebaigta-teismo-paskirta-bausme",
                        "ar-buvote-pripazintas-kaltu",
                        "ar-veika-dekriminalizuota",
                        "ar-buvote-pripazintas-kaltu-uzsienyje",
                        "ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo",
                        "ar-neteko-mandato-uz-pazeidimus",
                    ],
                )
                # Q10-Q12 are numbered "10 ." on these pages; without the
                # tolerant question-number repair their answers drop silently.
                self.assertEqual(
                    list(pareiskimai.values()),
                    ["Ne"] * 9,
                )

    def test_conditional_blocks_absent(self) -> None:
        # Nobody in the fixture set answered Q13 or Q14 "Taip".
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                anketa = payload["normalized"]["anketa"]
                # Uniform shape: no conviction block means an empty entry
                # list, not the old skeleton of null fields.
                self.assertEqual(anketa["teistumo-detales"], {"irasai": []})
                self.assertIsNone(anketa["mandato-netekimo-detales"])

    def test_every_offence_block_is_kept(self) -> None:
        # A candidate with more than one offence gets one Q13.4 block per
        # offence, separated by an empty spacer row. The era's own collector
        # stopped at the first non-table row, so every offence after the first
        # was dropped — 243 of them across this election's 509 stored blocks,
        # measured against rawData when the shared collector replaced it
        # (issue #86). No fixture candidate declared a conviction, so the shape
        # is guarded on the rows the parse produces for one.
        rows = [
            {"questionNumber": "13", "prompt": "13. Ar buvote pripažintas kaltu?", "answer": "Taip"},
            {"questionNumber": "13.1", "prompt": "13.1. ...", "answer": "1995-12-28"},
            {"questionNumber": "13.2", "prompt": "13.2. ...", "answer": "Lietuva"},
            {"questionNumber": "13.3", "prompt": "13.3. ...", "answer": "LAZDIJŲ R. APYLINKĖS TEISMAS"},
            {"questionNumber": "13.4", "prompt": "13.4. Nusikalstamos veikos rūšis ...", "answer": ""},
            {
                "questionNumber": None,
                "prompt": "",
                "answer": ["Kėsinimosi objektas - 16 str.(senas (iki 2003-05-01));"],
            },
            {"questionNumber": None, "prompt": "", "answer": ""},
            {
                "questionNumber": None,
                "prompt": "",
                "answer": ["Kėsinimosi objektas - 82 str. 1 d.(senas (iki 2003-05-01));"],
            },
            {"questionNumber": "13.5", "prompt": "13.5. ...", "answer": "Ne"},
        ]
        entries = _normalize_anketa_rows(rows)["teistumo-detales"]["irasai"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["nuosprendzio-data"], "1995-12-28")
        # The page ends each offence with a semicolon; issue #101's value
        # rules drop a separator that separates nothing.
        self.assertEqual(
            [veika["kesinimosi-objektas"] for veika in entries[0]["nusikalstamos-veikos"]],
            ["16 str.(senas (iki 2003-05-01))", "82 str. 1 d.(senas (iki 2003-05-01))"],
        )

    # ------------------------------------------------------------------
    # biografija
    # ------------------------------------------------------------------

    def test_biografija_uses_2023_question_numbering(self) -> None:
        # Nationality is Q2 in this vintage, so education is Q3 and work history
        # Q5 — one behind the 2024/2025 modules, which have no Q2 at all.
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    list(payload["normalized"]["biografija"].keys()),
                    [
                        "gimimo-data",
                        "gimimo-vieta",
                        "tautybe",
                        "issilavinimas",
                        "mokslo-laipsnis",
                        "pedagoginis-vardas",
                        "uzsienio-kalbos",
                        "darbo-patirtis",
                        "visuomenine-veikla",
                        "pomegiai",
                        "seimine-padetis",
                    ],
                )
                self.assertIsNotNone(payload["normalized"]["biografija"]["tautybe"])

    def test_biografija_values(self) -> None:
        bio = self.zebrauskas["normalized"]["biografija"]
        self.assertEqual(bio["gimimo-data"], "1955-01-05")
        self.assertEqual(bio["gimimo-vieta"], "Plungė")
        self.assertEqual(bio["tautybe"], "Lietuvis")
        self.assertEqual(bio["mokslo-laipsnis"], "Magistras")
        self.assertEqual(bio["pedagoginis-vardas"], "Profesorius")
        self.assertEqual(bio["uzsienio-kalbos"], ["Prancūzų", "Rusų"])
        self.assertEqual(bio["seimine-padetis"], "Vedęs")

        # Feminine forms and an empty language list both occur.
        self.assertEqual(self.sakalauskiene["normalized"]["biografija"]["tautybe"], "Lietuvė")
        self.assertEqual(
            self.sakalauskiene["normalized"]["biografija"]["seimine-padetis"],
            "Ištekėjusi",
        )
        self.assertEqual(
            self.sakalauskiene["normalized"]["biografija"]["uzsienio-kalbos"], []
        )
        self.assertIsNone(self.urmanavicius["normalized"]["biografija"]["pomegiai"])

    def test_biografija_record_tables(self) -> None:
        bio = self.mockevicius["normalized"]["biografija"]
        self.assertEqual(len(bio["issilavinimas"]["irasai"]), 3)
        self.assertEqual(
            bio["issilavinimas"]["irasai"][0],
            {
                "issilavinimas": "Aukštasis universitetinis",
                "mokymo-istaigos-pavadinimas": "Mykolo Romerio universitetas",
                "specialybe": "finansų teisė",
                "baigimo-metai": "2006",
            },
        )
        self.assertEqual(len(bio["darbo-patirtis"]["irasai"]), 6)
        self.assertEqual(
            bio["darbo-patirtis"]["irasai"][0],
            {
                "darbo-pradzia": "2019",
                "darbo-pabaiga": "2023",
                "darboviete": "Jurbarko rajono savivaldybė",
                "pareigos": "Savivaldybės meras",
            },
        )

    # ------------------------------------------------------------------
    # turto ir pajamu deklaracijos
    # ------------------------------------------------------------------

    def test_turto_ir_pajamu_normalized(self) -> None:
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    list(payload["normalized"]["turto-ir-pajamu-deklaracijos"].keys()),
                    list(DECLARATION_BLOCK_KEYS),
                )

        turtas = self.zebrauskas["normalized"]["turto-ir-pajamu-deklaracijos"]
        self.assertEqual(turtas["privalomas-registruoti-turtas"], 125750)
        self.assertEqual(
            turtas["vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai"], 3500
        )
        self.assertEqual(turtas["pinigines-lesos"], 30000)
        self.assertEqual(turtas["suteiktos-paskolos"], 0)
        # Comma-decimal amounts parse to floats.
        self.assertEqual(turtas["gautos-pajamos"], 43591.44)
        self.assertEqual(turtas["sumoketas-pajamu-mokestis"], 7479.67)

    # ------------------------------------------------------------------
    # privaciu interesu deklaracija
    # ------------------------------------------------------------------

    def test_privaciu_interesu_declarant_hoisted(self) -> None:
        privaciu = self.zebrauskas["normalized"]["privaciu-interesu-deklaracija"]
        self.assertEqual(privaciu["deklaruojantis-asmuo"], "Algirdas ŽEBRAUSKAS")
        self.assertEqual(privaciu["pateikimo-data"], "2022-12-26")
        self.assertEqual(
            privaciu["sutuoktinis-sugyventinis-ar-partneris"], "Aldona ŽEBRAUSKIENĖ"
        )
        self.assertEqual(len(privaciu["deklaruojancio-darbovietes"]), 2)
        self.assertEqual(
            privaciu["deklaruojancio-darbovietes"][0]["pavadinimas"],
            "UAB Architekto studija",
        )
        self.assertEqual(len(privaciu["rysiai-su-juridiniais-asmenimis"]), 5)
        self.assertEqual(len(privaciu["rysiai-sudarius-sandorius"]), 1)
        self.assertEqual(
            privaciu["rysiai-sudarius-sandorius"][0]["kitos-sandorio-salies-pavadinimas"],
            "AB SEB bankas",
        )

        # Sections are only present when the declaration carries them.
        self.assertEqual(
            list(self.sakalauskiene["normalized"]["privaciu-interesu-deklaracija"].keys()),
            [
                "pateikimo-data",
                "deklaruojantis-asmuo",
                "sutuoktinis-sugyventinis-ar-partneris",
                "deklaruojancio-darbovietes",
            ],
        )

    def test_free_text_privaciu_section_is_kept(self) -> None:
        # Regression guard for the shared ep_2024 normalizer, which used to drop
        # every declaration item with an empty key. "Kiti duomenys" is published
        # as one unlabelled sentence, so the whole section was lost from
        # normalized output while rawData still had it.
        for payload, expected in (
            (
                self.zebrauskas,
                "Dukra Šarūnė Žebrauskaitė-Lekavičienė yra Telšių rajono apygardos "
                "Nr. 51 rinkimų komisijos narė, dirba Telšių rajono savivaldybės "
                "administracijoje. Patalpų nuoma Turgaus a. 14, Telšiai.",
            ),
            (
                self.majauskas,
                "Jūratė Janavičiūtė (sugyventinės mama) dirba LR Statistikos "
                "departamente.",
            ),
        ):
            with self.subTest(candidate=payload["candidateId"]):
                kiti = payload["normalized"]["privaciu-interesu-deklaracija"][
                    "kiti-duomenys"
                ]
                self.assertEqual(kiti, [{"tekstas": expected}])

        # Declarations without the section do not gain an empty one.
        for payload in (self.rusteika, self.gudaitis, self.urmanavicius, self.mitrofanovas):
            with self.subTest(candidate=payload["candidateId"]):
                self.assertNotIn(
                    "kiti-duomenys",
                    payload["normalized"]["privaciu-interesu-deklaracija"],
                )

    # ------------------------------------------------------------------
    # politines kampanijos dalyvio duomenys
    # ------------------------------------------------------------------

    def test_campaign_shape(self) -> None:
        for payload in self.mayoral:
            with self.subTest(candidate=payload["candidateId"]):
                campaigns = payload["normalized"][
                    "politines-kampanijos-dalyvio-duomenys"
                ]
                self.assertEqual(len(campaigns), 1)
                self.assertEqual(
                    list(campaigns[0].keys()),
                    [
                        "statusas",
                        "registravimo-data",
                        "sprendimo-numeris",
                        "kontaktai",
                        "izdininkas",
                        "auditorius",
                        "aukos-pagal-sekcija",
                        "finansavimo-ataskaitos",
                        "sutartys",
                        "sprendimai",
                    ],
                )

    def test_campaign_participant_status_and_donations(self) -> None:
        campaign = self.zebrauskas["normalized"][
            "politines-kampanijos-dalyvio-duomenys"
        ][0]
        self.assertEqual(campaign["statusas"], "Savarankiškas")
        self.assertEqual(campaign["registravimo-data"], "2022-12-06")
        self.assertEqual(campaign["sprendimo-numeris"], "PK1-2023STR-S240")
        self.assertEqual(campaign["izdininkas"]["vardas-pavarde"], "BIRUTĖ RINKEVIČIENĖ")
        self.assertEqual(campaign["auditorius"]["imones-pavadinimas"], 'UAB "LEXIN auditas"')
        self.assertEqual(len(campaign["finansavimo-ataskaitos"]), 3)
        self.assertEqual(len(campaign["sutartys"]), 1)

        donations = campaign["aukos-pagal-sekcija"]["gautos-ir-priimtos-aukos"]
        self.assertEqual(len(donations["records"]), 4)
        self.assertEqual(
            donations["records"][0],
            {
                "rowNumber": "1.",
                "donor": "ALGIRDAS ŽEBRAUSKAS",
                "municipality": None,
                "date": "2023-01-23",
                "incomeSourceCode": "KL",
                "amount": 3000.0,
                "notes": "Piniginės lėšos, Priimtas",
            },
        )
        self.assertEqual(donations["totals"]["is-viso"], 3208.18)
        self.assertEqual(donations["totals"]["kandidato-nuosavos-lesos"], 3173.54)
        self.assertEqual(
            round(sum(record["amount"] for record in donations["records"]), 2),
            donations["totals"]["is-viso"],
        )

        # A represented participant and a rejected-donations section.
        self.assertEqual(
            self.vitkauskiene["normalized"]["politines-kampanijos-dalyvio-duomenys"][0][
                "statusas"
            ],
            "Atstovaujamasis",
        )
        majauskas_sections = self.majauskas["normalized"][
            "politines-kampanijos-dalyvio-duomenys"
        ][0]["aukos-pagal-sekcija"]
        self.assertEqual(
            list(majauskas_sections.keys()),
            ["gautos-ir-priimtos-aukos", "nepriimtos-aukos"],
        )
        self.assertEqual(
            len(majauskas_sections["gautos-ir-priimtos-aukos"]["records"]), 98
        )
        self.assertEqual(
            majauskas_sections["gautos-ir-priimtos-aukos"]["totals"]["is-viso"],
            165980.02,
        )
        self.assertEqual(len(majauskas_sections["nepriimtos-aukos"]["records"]), 11)

        # A registered participant that filed nothing at all. The donations
        # section is still reported, carrying the empty state rather than
        # disappearing — "declared no donations" and "section never published"
        # have to stay distinguishable downstream.
        mitrofanovas = self.mitrofanovas["normalized"][
            "politines-kampanijos-dalyvio-duomenys"
        ][0]
        self.assertEqual(
            mitrofanovas["aukos-pagal-sekcija"],
            {
                "gautos-ir-priimtos-aukos": {
                    "title": "Gautos ir priimtos aukos",
                    "status": "noData",
                    "message": "Duomenų nėra",
                }
            },
        )
        self.assertEqual(mitrofanovas["finansavimo-ataskaitos"], [])

    def test_sprendimai_tab_is_normalized(self) -> None:
        # Regression guard for the shared campaign normalizer (seimo_2016's,
        # scraper/shared/anketa_tabs.py since issue #90), which
        # fetched the "Sprendimai" tab into rawData but never normalized it.
        sprendimai = self.zebrauskas["normalized"][
            "politines-kampanijos-dalyvio-duomenys"
        ][0]["sprendimai"]
        self.assertEqual(len(sprendimai), 1)
        decision = sprendimai[0]
        self.assertEqual(
            list(decision.keys()),
            ["rowNumber", "title", "date", "number", "note", "urls"],
        )
        self.assertEqual(decision["rowNumber"], "1.")
        self.assertEqual(decision["date"], "2023-10-06")
        self.assertEqual(decision["number"], "Sp-242")
        self.assertIsNone(decision["note"])
        self.assertIn("išsikėlusio kandidato Algirdo Žebrausko", decision["title"])
        self.assertIn("politinės reklamos", decision["title"])
        self.assertEqual(len(decision["urls"]), 1)
        self.assertTrue(decision["urls"][0].startswith("https://e-seimas.lrs.lt/"))

        # Campaigns with no VRK decisions get an empty list, not a missing key.
        for payload in (
            self.majauskas,
            self.vitkauskiene,
            self.mockevicius,
            self.mitrofanovas,
        ):
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    payload["normalized"]["politines-kampanijos-dalyvio-duomenys"][0][
                        "sprendimai"
                    ],
                    [],
                )

    # ------------------------------------------------------------------
    # kita
    # ------------------------------------------------------------------

    def test_kita_tab_is_empty_for_every_candidate(self) -> None:
        for payload in self.everyone:
            with self.subTest(candidate=payload["candidateId"]):
                self.assertEqual(
                    payload["normalized"]["kita"], {"tekstai": [], "nuorodos": []}
                )


if __name__ == "__main__":
    unittest.main()
