"""The education ordinal (issue #88): tiers, degree words, and the resolver.

The mapping rules are pinned on the corpus's real surface forms — every
example below is a measured value, with its corpus frequency in a comment
where it matters. The ordering assertions are the contract consumers sort
by; the resolver tests pin the four absence states on synthetic records
shaped like the real eras.
"""

from __future__ import annotations

import unittest

from scraper.shared.education import (
    AUKSTASIS_RANK,
    DEGREES,
    LEVELS,
    RANK,
    degree_of,
    is_unfinished,
    issilavinimas,
    level_of,
)


class LevelTaxonomy(unittest.TestCase):
    def test_the_thirteen_tiers_are_ordered(self):
        self.assertEqual(len(LEVELS), 13)
        self.assertLess(RANK["pradinis"], RANK["pagrindinis"])
        self.assertLess(RANK["nebaigtas-vidurinis"], RANK["vidurinis"])
        self.assertLess(RANK["vidurinis"], RANK["profesinis-vidurinis"])
        self.assertLess(RANK["profesinis-vidurinis"], RANK["aukstesnysis"])
        self.assertLess(RANK["aukstesnysis"], RANK["nebaigtas-aukstasis"])
        self.assertLess(RANK["nebaigtas-aukstasis"], RANK["aukstasis-nedetalizuotas"])
        self.assertLess(RANK["aukstasis-nedetalizuotas"], RANK["aukstasis-neuniversitetinis"])
        self.assertLess(RANK["aukstasis-neuniversitetinis"], RANK["aukstasis-universitetinis"])
        self.assertLess(RANK["aukstasis-universitetinis"], RANK["aukstasis-bakalauras"])
        self.assertLess(RANK["aukstasis-bakalauras"], RANK["aukstasis-magistras"])
        self.assertLess(RANK["aukstasis-magistras"], RANK["doktorantura"])

    def test_the_top_ten_forms(self):
        # 96 % of all level tokens are these; each count is the corpus's.
        cases = {
            "Aukštasis": "aukstasis-nedetalizuotas",  # 44,576
            "Aukštasis universitetinis": "aukstasis-universitetinis",  # 29,616
            "Aukštesnysis": "aukstesnysis",  # 16,287
            "Vidurinis": "vidurinis",  # 9,328
            "Aukštasis neuniversitetinis": "aukstasis-neuniversitetinis",  # 3,817
            "Specialusis vidurinis": "profesinis-vidurinis",  # 2,061
            "Specialus vidurinis": "profesinis-vidurinis",  # 1,594
            "Nebaigtas aukštasis": "nebaigtas-aukstasis",  # 1,041
            "Spec. vidurinis": "profesinis-vidurinis",  # 784
            "Aukštasis magistrinis": "aukstasis-magistras",  # 639
        }
        for text, expected in cases.items():
            self.assertEqual(level_of(text), expected, text)

    def test_the_bare_aukstasis_is_never_guessed_into_a_type(self):
        # Every election up to 2007-vasario offers the bare form as its only
        # higher-education option; collapsing it into either qualified tier
        # invents data (issue #88 point 2).
        self.assertEqual(level_of("Aukštasis"), "aukstasis-nedetalizuotas")
        self.assertGreaterEqual(RANK["aukstasis-nedetalizuotas"], AUKSTASIS_RANK)
        self.assertLess(RANK["nebaigtas-aukstasis"], AUKSTASIS_RANK)

    def test_qualifier_traps(self):
        # "Aukštesnysis neuniversitetinis" is an aukštesnysis, not a kolegija
        # degree; "Bakalauras (aukštesnysis)" is the degree; "Profesinis
        # bakalauras" is the kolegija one; magistrantūra is a completed
        # bachelor still studying, not a master.
        self.assertEqual(level_of("Aukštesnysis neuniversitetinis"), "aukstesnysis")
        self.assertEqual(level_of("Bakalauras (aukštesnysis)"), "aukstasis-bakalauras")
        self.assertEqual(level_of("Verslo vadybos profesinis bakalauras"), "aukstasis-neuniversitetinis")
        self.assertEqual(level_of("Magistratūra"), "aukstasis-bakalauras")
        self.assertEqual(level_of("Aukštasis, magistrantūra"), "aukstasis-bakalauras")
        self.assertEqual(level_of("Aukštasis (magistratūros I kursas)"), "aukstasis-bakalauras")
        self.assertEqual(level_of("aukštasis universitetinis magistras"), "aukstasis-magistras")
        self.assertEqual(level_of("aukštasis (numatoma)"), "nebaigtas-aukstasis")
        self.assertEqual(level_of("Nebaigtas spec. vidurinis"), "nebaigtas-vidurinis")
        self.assertEqual(level_of("11 klasių"), "nebaigtas-vidurinis")
        self.assertEqual(level_of("vidurinis - techninis"), "profesinis-vidurinis")
        self.assertEqual(level_of("Aspirantūra"), "doktorantura")
        self.assertEqual(level_of("Daktaro laipsnis"), "doktorantura")
        self.assertEqual(level_of("Aštuonios klasės"), "pagrindinis")

    def test_the_unmappable_tail_stays_unmapped(self):
        # Headed by "Nereglamentuojamas" (385) — non-answers and institution
        # names, not levels. "Universitetas" is an institution, not
        # "universitetinis".
        for text in ("Nereglamentuojamas", "Universitetas", "Studijuoju", "VU",
                     "Sertifikatas", "IV kursai", "Docentas"):
            self.assertIsNone(level_of(text), text)
        self.assertIsNone(level_of(None))
        self.assertIsNone(level_of("  "))

    def test_unfinished_flag(self):
        self.assertTrue(is_unfinished("Nebaigtas aukštasis"))
        self.assertTrue(is_unfinished("aukštasis (numatoma)"))
        self.assertFalse(is_unfinished("Aukštasis"))


class DegreeWords(unittest.TestCase):
    def test_degrees(self):
        self.assertEqual(degree_of("Magistras"), "magistras")  # 3,695 + case variants
        self.assertEqual(degree_of("Bakalauro laipsnis"), "bakalauras")
        self.assertEqual(degree_of("Socialinių mokslų daktaras"), "daktaras")
        self.assertEqual(degree_of("Habilituotas mokslų daktaras"), "habilituotas-daktaras")
        self.assertEqual(degree_of("Neturiu"), "nera")
        self.assertEqual(DEGREES.index("nera"), 0)

    def test_titles_and_levels_are_not_degrees(self):
        # The field holds four different things at once (issue #88 point 7);
        # only degree words count. 90 records in 2023-kovo-5 typed an
        # education *level* into mokslo-laipsnis.
        for text in ("Docentas", "Profesorius", "Vyr. mokytoja",
                     "Mokytoja metodininkė", "Aukštasis"):
            self.assertIsNone(degree_of(text), text)

    def test_a_masters_student_is_not_a_master(self):
        # The level rules have guarded `magistrant|magistratur` ahead of
        # `magistr` since issue #88 — Magistrantūra is a completed bachelor
        # in master's studies — and the degree rules did not, so 17 records
        # were given `magistras` while their level said `aukstasis-bakalauras`
        # and `education_degree` shipped the contradiction (issue #161).
        # These are the corpus's own 12 surface forms.
        for text in ("Magistrantūra", "Magistrantas", "Magistrantė", "magistrantas",
                     "Magistrantūros", "Magistrantūro laipsnis",
                     "Magistrantūra verslo administravimas", "Magistratūra",
                     "Magistratura", "Magistratūros", "Magistratūros studijos",
                     "METODININKĖ, magistratūra", "Metodininkas, Magistrantas"):
            with self.subTest(text):
                self.assertIsNone(degree_of(text))
        # And the guard must not swallow the degree itself.
        self.assertEqual(degree_of("Magistras"), "magistras")
        self.assertEqual(degree_of("Viešojo administravimo magistras"), "magistras")
        self.assertEqual(degree_of("Magistro kvalifikacijos laipsnis"), "magistras")

    def test_a_frozen_dissertation_is_not_a_doctorate(self):
        self.assertIsNone(
            degree_of("Daktaro disertacija įšaldyta (išlaikyti visi doktorantūros egzaminai)")
        )
        self.assertEqual(degree_of("Socialinių mokslų daktaras"), "daktaras")

    def test_the_level_and_the_degree_agree_on_every_surface_form(self):
        # The two rule sets read the same words out of different fields, and
        # a form that yields a bachelor's *level* must not yield a master's
        # *degree*. That pairing was the shipped contradiction.
        for text in ("Magistrantūra", "Magistratūros studijos", "Aukštasis, magistrantūra"):
            with self.subTest(text):
                self.assertEqual(level_of(text), "aukstasis-bakalauras")
                self.assertIsNone(degree_of(text))


def _record(election_id, section="anketa", levels=(), aprasas=None,
            degree=None, raw_answer=None):
    entries = [{"issilavinimas": level, "mokymo-istaigos-pavadinimas": None,
                "specialybe": None, "baigimo-metai": None} for level in levels]
    record = {
        "electionId": election_id,
        "normalized": {
            section: {
                "issilavinimas": {"aprasas": aprasas, "irasai": entries},
                "mokslo-laipsnis": degree,
            }
        },
    }
    if raw_answer is not None:
        record["rawData"] = {
            section: {"rows": [{"prompt": "12. Išsilavinimas:", "answer": raw_answer}]}
        }
    return record


class Resolver(unittest.TestCase):
    def test_highest_tier_wins_across_entries(self):
        answer = issilavinimas(_record("2019-ep", levels=("Vidurinis", "Aukštasis universitetinis")))
        self.assertEqual(answer["busena"], "nurodyta")
        self.assertEqual(answer["lygis"], "aukstasis-universitetinis")
        self.assertTrue(answer["aukstasis"])

    def test_aprasas_is_a_level_source(self):
        # 2000-kovo-19 and 2002-gruodzio-22 answer the level in `aprasas`
        # with empty irasai — 19,861 records a consumer reading only irasai
        # scores as no education (issue #88 point 4).
        answer = issilavinimas(_record("2000-kovo-19-savivaldybiu-tarybu", aprasas="Aukštasis"))
        self.assertEqual(answer["busena"], "nurodyta")
        self.assertEqual(answer["lygis"], "aukstasis-nedetalizuotas")

    def test_biografija_era_resolves_too(self):
        answer = issilavinimas(_record("2024-seimo", section="biografija", levels=("Aukštasis universitetinis magistras",)))
        self.assertEqual(answer["lygis"], "aukstasis-magistras")

    def test_answered_but_unmapped_is_still_answered(self):
        answer = issilavinimas(_record("2019-ep", levels=("Nereglamentuojamas",)))
        self.assertEqual(answer["busena"], "nurodyta")
        self.assertIsNone(answer["lygis"])
        self.assertIsNone(answer["aukstasis"])

    def test_printed_decline_is_nenurode(self):
        answer = issilavinimas(_record("2019-kovo-3-savivaldybiu-tarybu", raw_answer="Nenurodė"))
        self.assertEqual(answer["busena"], "nenurode")

    def test_a_decline_inside_the_education_table_is_nenurode_too(self):
        # The second shape of the same refusal (issue #161): VRK prints the
        # decline as the *level of each entry*, beside the school and the year
        # the candidate did give. 78 records fell through to `neatsakyta` --
        # "the page shows no answer", over a page showing an explicit refusal
        # -- and `education_status` shipped it.
        answer = issilavinimas(
            _record(
                "2023-kovo-5-savivaldybiu-tarybu-ir-meru",
                raw_answer=[{
                    "issilavinimas": "Nenurodė",
                    "mokymo-istaigos-pavadinimas": "Kauno technikos profesinio mokymo centras",
                    "specialybe": "Orlaivio mechanika",
                    "baigimo-metai": "2021",
                }],
            )
        )
        self.assertEqual(answer["busena"], "nenurode")

    def test_the_declines_display_label_spelling_is_read_too(self):
        # The 2011-2016 rows carry the display labels, the 2020-era ones the
        # slugs. A reader that knows only one spelling sees half the corpus.
        answer = issilavinimas(
            _record(
                "2016-seimo",
                raw_answer=[{
                    "Išsilavinimas": "Nenurodė",
                    "Mokymo įstaigos pavadinimas": "Kauno politechnikos institutas",
                    "Specialybė": "inžinerija",
                    "Baigimo metai": "1974",
                }],
            )
        )
        self.assertEqual(answer["busena"], "nenurode")

    def test_a_table_where_only_some_entries_decline_is_an_answer(self):
        # Those candidates answered, for the schooling they chose to list.
        record = _record(
            "2023-kovo-5-savivaldybiu-tarybu-ir-meru",
            levels=("Vidurinis",),
            raw_answer=[
                {"issilavinimas": "Nenurodė", "mokymo-istaigos-pavadinimas": "x"},
                {"issilavinimas": "Vidurinis", "mokymo-istaigos-pavadinimas": "y"},
            ],
        )
        answer = issilavinimas(record)
        self.assertEqual(answer["busena"], "nurodyta")
        self.assertEqual(answer["lygis"], "vidurinis")

    def test_an_empty_education_table_is_not_a_decline(self):
        answer = issilavinimas(_record("2016-seimo", raw_answer=[]))
        self.assertEqual(answer["busena"], "neatsakyta")

    def test_level_not_published_elections(self):
        # 2000-seimo publishes institution/specialty/year and zero levels;
        # reading its nulls as 0 % higher education is an artefact (issue
        # #88 point 5).
        record = _record("2000-seimo", degree="Humanitarinių mokslų daktaras")
        record["normalized"]["anketa"]["issilavinimas"]["irasai"] = [
            {"mokymo-istaigos-pavadinimas": "Vilniaus universitetas",
             "specialybe": "istorija", "baigimo-metai": "1980"}
        ]
        answer = issilavinimas(record)
        self.assertEqual(answer["busena"], "neskelbta")
        self.assertIsNone(answer["lygis"])
        self.assertEqual(answer["laipsnis"], "daktaras")  # degree-only record
        self.assertEqual(len(answer["irasai"]), 1)

    def test_blank_without_a_printed_decline_is_neatsakyta(self):
        answer = issilavinimas(_record("2015-kovo-1-savivaldybiu"))
        self.assertEqual(answer["busena"], "neatsakyta")

    def test_2004_ep_institution_key_alias_is_folded(self):
        # 2004-ep spells the institution key from its own column heading on
        # 360 of 361 entries; the dashboard rendered them blank (issue #88).
        record = {
            "electionId": "2004-ep",
            "normalized": {"anketa": {"issilavinimas": {"aprasas": None, "irasai": [
                {"issilavinimas": "Aukštasis",
                 "mokyklos-istaigos-pavadinimas": "Vilniaus universitetas",
                 "specialybe": "teisė", "baigimo-metai": "1996"}
            ]}}},
        }
        answer = issilavinimas(record)
        self.assertEqual(
            answer["irasai"][0]["mokymo-istaigos-pavadinimas"], "Vilniaus universitetas"
        )

    def test_degree_read_from_fused_pedagoginis_vardas(self):
        # Eight elections fused the degree and title questions into one row;
        # the answer landed under pedagoginis-vardas alone (issue #88 point 7).
        record = {
            "electionId": "2016-seimo",
            "normalized": {"anketa": {
                "issilavinimas": {"aprasas": None, "irasai": []},
                "pedagoginis-vardas": "Magistras",
            }},
        }
        self.assertEqual(issilavinimas(record)["laipsnis"], "magistras")


if __name__ == "__main__":
    unittest.main()
