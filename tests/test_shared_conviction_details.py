import unittest

from scraper.shared.conviction_details import (
    DECLARED,
    DECLARED_WITHOUT_DETAIL,
    DENIED,
    NOT_ASKED,
    conviction_entries,
    conviction_field_keys,
    conviction_record_groups,
    conviction_records,
    teistumas,
)


# The Q9.2 detail table as 2016-seimo stores it: columns spelled out in full,
# numbered after the sub-questions.
SEIMO_2016_ROWS = [
    {"rowIndex": 10, "questionNumber": "9.2", "prompt": "9.2. Ar buvote ...", "answer": "Taip"},
    {
        "rowIndex": 12,
        "questionNumber": None,
        "prompt": "",
        "answer": [
            {
                "9.2.1. Apkaltinamojo nuosprendžio (sprendimo) data": "2008-06-04",
                "9.2.2. Apkaltinamojo nuosprendžio (sprendimo) priėmimo valstybė (vieta)": "Lietuva",
                "9.2.3. Nuosprendį (sprendimą) priėmusios institucijos pavadinimas": "Ukmergės rajono apylinkės teismas",
                "9.2.4. Nusikalstama veika, už kurią buvote nuteistas (pavadinimas)": "BK 178 str. 1 d.",
            }
        ],
    },
    {"rowIndex": 13, "questionNumber": "9.3", "prompt": "9.3. ...", "answer": ""},
]

# 2020-seimo prints the block's lead-in as a row of its own between the
# question and its table, and ends each column heading with a colon.
SEIMO_2020_ROWS = [
    {"rowIndex": 15, "questionNumber": "9.2", "prompt": "9.2. Ar po 1990-03-11 ...", "answer": "Taip"},
    {
        "rowIndex": 16,
        "questionNumber": None,
        "prompt": "Jeigu buvote pripažintas kaltu, privalote nurodyti (dėl kiekvieno nuosprendžio atskirai):",
        "answer": "",
    },
    {
        "rowIndex": 17,
        "questionNumber": None,
        "prompt": "",
        "answer": [
            {
                "9.2.1. Apkaltinamojo nuosprendžio (sprendimo) data:": "2015",
                "9.2.2. Apkaltinamojo nuosprendžio (sprendimo) priėmimo valstybė (vieta):": "LIETUVA",
                "9.2.3. Nuosprendį (sprendimą) priėmusios institucijos pavadinimas:": "Vilniaus apygardos teismas",
                "9.2.4. Nusikalstama veika, už kurią buvote nuteistas (pavadinimas)": "Šmeižtas",
            }
        ],
    },
    {"rowIndex": 18, "questionNumber": "9.3", "prompt": "9.3. ...", "answer": "Ne"},
]

# 2019-ep slugifies its column headings before printing them.
EP_2019_ROWS = [
    {"rowIndex": 9, "questionNumber": "9.2", "prompt": "9.2 Ar buvote ...", "answer": "Taip"},
    {
        "rowIndex": 10,
        "questionNumber": None,
        "prompt": "",
        "answer": [
            {
                "9-2-1-apkaltinamojo-nuosprendzio-sprendimo-data": "2016",
                "9-2-2-apkaltinamojo-nuosprendzio-sprendimo-priemimo-valstybe-vieta": "AIRIJA",
                "9-2-3-nuosprendi-sprendima-priemusios-institucijos-pavadinimas": "Ballymenos magistrato teismas",
                "9-2-4-nusikalstama-veika-uz-kuria-buvote-nuteistas-pavadinimas": "vairavimas be draudimo",
            }
        ],
    },
]

# The Rinkimų kodekso block: one "Label - value" line per field, one row per
# offence, with an empty spacer row between the offences.
KODEKSAS_2023_ROWS = [
    {"rowIndex": 14, "questionNumber": "13.4", "prompt": "13.4. Nusikalstamos veikos rūšis ...", "answer": ""},
    {
        "rowIndex": 15,
        "questionNumber": None,
        "prompt": "",
        "answer": [
            "Nusikalstamos veikos rūšis (nusikaltimas ar baudžiamasis įsakymas) -",
            "Kaltės forma - Tyčia",
            "Kėsinimosi objektas (Baudžiamojo kodekso skyriaus ir straipsnio pavadinimas) - 16 str.(senas (iki 2003-05-01));",
            "Teistumo išnykimo ar panaikinimo data - 1996-12-13",
        ],
    },
    {"rowIndex": 16, "questionNumber": None, "prompt": "", "answer": ""},
    {
        "rowIndex": 17,
        "questionNumber": None,
        "prompt": "",
        "answer": [
            "Kėsinimosi objektas (Baudžiamojo kodekso skyriaus ir straipsnio pavadinimas) – 82 str. 1 d.(senas (iki 2003-05-01));",
            "Teistumo išnykimo ar panaikinimo data – 1996-12-13",
        ],
    },
    {"rowIndex": 18, "questionNumber": None, "prompt": "", "answer": ""},
    {"rowIndex": 19, "questionNumber": "13.5", "prompt": "13.5. ...", "answer": "Ne"},
]


class ConvictionFieldKeysTests(unittest.TestCase):
    def test_era_difference_is_the_question_number(self) -> None:
        # The four columns are named after the sub-questions that ask for them,
        # so an era's whole column map follows from its question number.
        self.assertEqual(
            conviction_field_keys("9.2"),
            {
                "9-2-1": "nuosprendzio-data",
                "9-2-2": "nuosprendzio-valstybe",
                "9-2-3": "nuosprendzio-institucija",
                "9-2-4": "nusikalstama-veika",
            },
        )
        self.assertEqual(
            list(conviction_field_keys("9.1")),
            ["9-1-1", "9-1-2", "9-1-3", "9-1-4"],
        )


class ConvictionRecordsTests(unittest.TestCase):
    def test_spelled_out_columns_map_to_the_shared_field_names(self) -> None:
        self.assertEqual(
            conviction_records(SEIMO_2016_ROWS, "9.2", conviction_field_keys("9.2")),
            [
                {
                    "nuosprendzio-data": "2008-06-04",
                    "nuosprendzio-valstybe": "Lietuva",
                    "nuosprendzio-institucija": "Ukmergės rajono apylinkės teismas",
                    "nusikalstama-veika": "BK 178 str. 1 d.",
                }
            ],
        )

    def test_lead_in_row_does_not_end_the_block(self) -> None:
        # 2020's "Jeigu buvote pripažintas kaltu, privalote nurodyti" row sits
        # between the question and its table. Breaking on it — as the era's
        # own collectors did — loses every 2020 conviction.
        self.assertEqual(
            conviction_records(SEIMO_2020_ROWS, "9.2", conviction_field_keys("9.2")),
            [
                {
                    "nuosprendzio-data": "2015",
                    "nuosprendzio-valstybe": "LIETUVA",
                    "nuosprendzio-institucija": "Vilniaus apygardos teismas",
                    "nusikalstama-veika": "Šmeižtas",
                }
            ],
        )

    def test_slugified_columns_map_the_same_way(self) -> None:
        self.assertEqual(
            conviction_records(EP_2019_ROWS, "9.2", conviction_field_keys("9.2")),
            [
                {
                    "nuosprendzio-data": "2016",
                    "nuosprendzio-valstybe": "AIRIJA",
                    "nuosprendzio-institucija": "Ballymenos magistrato teismas",
                    "nusikalstama-veika": "vairavimas be draudimo",
                }
            ],
        )

    def test_a_blank_column_reads_as_null_not_as_a_missing_key(self) -> None:
        rows = [
            {"questionNumber": "9.1", "prompt": "9.1 ...", "answer": "Taip"},
            {
                "questionNumber": None,
                "prompt": "",
                "answer": [{"9.1.1 Apkaltinamojo nuosprendžio (sprendimo) data": "1988"}],
            },
        ]
        self.assertEqual(
            conviction_records(rows, "9.1", conviction_field_keys("9.1")),
            [
                {
                    "nuosprendzio-data": "1988",
                    "nuosprendzio-valstybe": None,
                    "nuosprendzio-institucija": None,
                    "nusikalstama-veika": None,
                }
            ],
        )

    def test_dash_lines_fold_into_one_record_per_offence(self) -> None:
        # Both dash spellings — a plain hyphen on the 2023 pages, an en dash on
        # the 2024 ones — and both offences, which the spacer row between them
        # used to cut short at the first.
        self.assertEqual(
            conviction_records(KODEKSAS_2023_ROWS, "13.4"),
            [
                {
                    "nusikalstamos-veikos-rusis-nusikaltimas-ar-baudziamasis-isakymas": None,
                    "kaltes-forma": "Tyčia",
                    "kesinimosi-objektas-baudziamojo-kodekso-skyriaus-ir-straipsnio-pavadinimas": (
                        "16 str.(senas (iki 2003-05-01))"
                    ),
                    "teistumo-isnykimo-ar-panaikinimo-data": "1996-12-13",
                },
                {
                    "kesinimosi-objektas-baudziamojo-kodekso-skyriaus-ir-straipsnio-pavadinimas": (
                        "82 str. 1 d.(senas (iki 2003-05-01))"
                    ),
                    "teistumo-isnykimo-ar-panaikinimo-data": "1996-12-13",
                },
            ],
        )

    def test_no_declaration_is_an_empty_list(self) -> None:
        rows = [
            {"questionNumber": "9.2", "prompt": "9.2. ...", "answer": "Ne"},
            {"questionNumber": "9.3", "prompt": "9.3. ...", "answer": "Ne"},
        ]
        self.assertEqual(conviction_records(rows, "9.2", conviction_field_keys("9.2")), [])
        self.assertEqual(conviction_records(rows, "13.4"), [])

    def test_the_next_numbered_question_ends_the_block(self) -> None:
        rows = SEIMO_2016_ROWS + [
            {
                "rowIndex": 14,
                "questionNumber": None,
                "prompt": "",
                "answer": [{"issilavinimas": "Aukštasis"}],
            }
        ]
        # The education table sits after Q9.3, so it is not collected under Q9.2.
        groups = conviction_record_groups(rows, "9.2")
        self.assertEqual(len(groups), 1)

    def test_free_text_under_the_question_ends_the_block(self) -> None:
        rows = [
            {"questionNumber": "9.2", "prompt": "9.2. ...", "answer": "Taip"},
            {"questionNumber": None, "prompt": "Tai nurodoma šioje anketoje", "answer": "Teistumas išnykęs"},
            {"questionNumber": None, "prompt": "", "answer": [{"kaltes-forma": "Tyčia"}]},
        ]
        self.assertEqual(conviction_record_groups(rows, "9.2"), [])


class ConvictionEntriesTests(unittest.TestCase):
    def test_an_empty_block_is_an_empty_list(self) -> None:
        self.assertEqual(conviction_entries(None, None, None, []), [])

    def test_a_populated_block_is_one_entry(self) -> None:
        self.assertEqual(
            conviction_entries("2022-06-30", "Lietuva", "TEISMAS", [{"kaltes-forma": "Tyčia"}]),
            [
                {
                    "nuosprendzio-data": "2022-06-30",
                    "nuosprendzio-valstybe": "Lietuva",
                    "nuosprendzio-institucija": "TEISMAS",
                    "nusikalstamos-veikos": [{"kaltes-forma": "Tyčia"}],
                }
            ],
        )


class TeistumasConceptTests(unittest.TestCase):
    """One concept over the three shapes the corpus publishes."""

    def test_not_asked(self) -> None:
        # 2019-prezidento asks constitutional eligibility questions instead,
        # and the 1990s archive cards ask nothing of the kind. An absent
        # question is not a denial.
        self.assertEqual(teistumas({"pareiskimai": {}})["busena"], NOT_ASKED)
        self.assertEqual(teistumas(None)["busena"], NOT_ASKED)

    def test_denied(self) -> None:
        anketa = {"pareiskimai": {"ar-buvote-pripazintas-kaltu": "Ne"}}
        self.assertEqual(teistumas(anketa)["busena"], DENIED)
        # "Nėra" is the 2000/2004 forms' spelling of the same answer.
        anketa = {"pareiskimai": {"ar-buvote-pripazintas-kaltu": "Nėra"}}
        self.assertEqual(teistumas(anketa)["busena"], DENIED)

    def test_declared_with_no_detail_published(self) -> None:
        # 352 records: the page asks the question and publishes no block —
        # upstream, not a parse loss. Distinct from a denial and from a
        # detail.
        anketa = {
            "pareiskimai": {"ar-buvote-pripazintas-kaltu": "Taip"},
            "teistumo-detales": {"irasai": []},
        }
        self.assertEqual(teistumas(anketa)["busena"], DECLARED_WITHOUT_DETAIL)

    def test_yra_is_an_affirmative(self) -> None:
        # The 2000 and 2004 static-site forms ask whether there is anything to
        # declare, so their sixteen declarers answer "Yra" — a consumer
        # filtering on "Taip" alone misses every one of them.
        anketa = {
            "pareiskimai": {
                "ar-buvote-pripazintas-kaltu": "Yra",
                "teisiniai-argumentai": "Nuteistas pagal BK 162(2) str.",
            }
        }
        resolved = teistumas(anketa)
        self.assertEqual(resolved["busena"], DECLARED)
        self.assertEqual(resolved["aprasas"], "Nuteistas pagal BK 162(2) str.")
        self.assertEqual(resolved["irasai"], [])

    def test_a_conviction_declared_under_a_neighbouring_question_is_surfaced(self) -> None:
        # The 2000-2014 forms ask separately about a grave crime, a foreign
        # court, a political-persecution carve-out and an unserved sentence.
        # Those are different questions, so they do not move `busena` — but 20
        # records answer one of them "Taip" and the main question "Ne", and a
        # consumer counting only the main question calls all 20 unconvicted.
        anketa = {
            "pareiskimai": {
                "ar-buvote-pripazintas-kaltu": "Ne",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Buvo",
            }
        }
        resolved = teistumas(anketa)
        self.assertEqual(resolved["busena"], DENIED)
        self.assertEqual(
            resolved["kiti-pareiskimai"],
            {"ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Buvo"},
        )

    def test_a_denied_neighbouring_question_is_not_surfaced(self) -> None:
        anketa = {
            "pareiskimai": {
                "ar-buvote-pripazintas-kaltu": "Ne",
                "ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo": "Nebuvo",
                "ar-nebaigta-teismo-paskirta-bausme": "Neturiu",
            }
        }
        self.assertEqual(teistumas(anketa)["kiti-pareiskimai"], {})

    def test_the_2016_era_table_flattens(self) -> None:
        anketa = {
            "pareiskimai": {"ar-buvote-pripazintas-kaltu": "Taip"},
            "teistumo-detales": {
                "irasai": [
                    {
                        "nuosprendzio-data": "2008-06-04",
                        "nuosprendzio-valstybe": "Lietuva",
                        "nuosprendzio-institucija": "Ukmergės rajono apylinkės teismas",
                        "nusikalstama-veika": "BK 178 str. 1 d.",
                    }
                ]
            },
        }
        resolved = teistumas(anketa)
        self.assertEqual(resolved["busena"], DECLARED)
        self.assertEqual(resolved["irasai"][0]["data"], "2008-06-04")
        self.assertEqual(resolved["irasai"][0]["veikos"], ["BK 178 str. 1 d."])

    def test_the_rinkimu_kodekso_block_flattens_the_same_way(self) -> None:
        # Same concept, a different storage shape: the offences sit in a
        # nested list under a name of their own.
        anketa = {
            "pareiskimai": {"ar-buvote-pripazintas-kaltu": "Taip"},
            "teistumo-detales": {
                "irasai": [
                    {
                        "nuosprendzio-data": "1995-12-28",
                        "nuosprendzio-valstybe": "Lietuva",
                        "nuosprendzio-institucija": "LAZDIJŲ R. APYLINKĖS TEISMAS",
                        "nusikalstamos-veikos": [
                            {
                                "kaltes-forma": "Tyčinis",
                                "kesinimosi-objektas-baudziamojo-kodekso-skyriaus-ir-straipsnio-pavadinimas": "16 str.",
                            },
                            {
                                "kesinimosi-objektas-baudziamojo-kodekso-skyriaus-ir-straipsnio-pavadinimas": "82 str. 1 d.",
                            },
                        ],
                    }
                ]
            },
        }
        resolved = teistumas(anketa)
        self.assertEqual(resolved["busena"], DECLARED)
        self.assertEqual(resolved["irasai"][0]["institucija"], "LAZDIJŲ R. APYLINKĖS TEISMAS")
        self.assertEqual(resolved["irasai"][0]["veikos"], ["16 str.", "82 str. 1 d."])
        # Nothing is lost to the flattening.
        self.assertEqual(len(resolved["irasai"][0]["saltinis"]["nusikalstamos-veikos"]), 2)


if __name__ == "__main__":
    unittest.main()
