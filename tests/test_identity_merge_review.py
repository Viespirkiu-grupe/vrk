"""Unit tests for the identity merge-candidate scorer (issue #96).

The scorer's tiers matter because they route review effort: `strong` pairs
were mergeable nearly on sight, `given-name` pairs are the scorer's known
false-positive shape (a shared middle given name is not a kept surname), and
the extension test marks the pairs that needed no judgement at all. These pin
the tier boundaries on the real shapes from the review.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "find_identity_merge_candidates",
    REPO_ROOT / "scripts" / "find_identity_merge_candidates.py",
)
review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(review)


class ScorePairTests(unittest.TestCase):
    def test_a_kept_maiden_name_in_a_double_barrel_is_strong(self):
        self.assertEqual(
            review.score_pair("MORKŪNAITĖ", "MORKŪNAITĖ-MIKULĖNIENĖ"), "strong"
        )

    def test_the_maiden_to_married_stem_rule_is_strong(self):
        self.assertEqual(review.score_pair("KERUCKYTĖ", "KERUCKIENĖ"), "strong")

    def test_a_space_joined_compound_surname_is_strong(self):
        # BRAZIENĖ is the whole surname on one side and the first half of a
        # space-joined compound on the other — a surname token, not a middle
        # name.
        self.assertEqual(review.score_pair("BRAZIENĖ GITELMAN", "BRAZIENĖ"), "strong")

    def test_a_shared_middle_given_name_is_not_strong(self):
        # Raimonda Marija Gasperavičienė / Gerasimovičienė: MARIJA links them,
        # but MARIJA closes neither name and has no surname morphology — it is
        # somebody's second given name. This shape used to score strong and
        # was the old scorer's documented false-positive.
        self.assertEqual(
            review.score_pair("MARIJA GASPERAVIČIENĖ", "MARIJA GERASIMOVIČIENĖ"),
            "given-name",
        )

    def test_unrelated_surnames_are_weak(self):
        self.assertEqual(review.score_pair("PETRAITYTĖ", "KAZLAUSKIENĖ"), "weak")


class DiacriticFoldingTests(unittest.TestCase):
    """A missing macron is not a different surname (issue #141)."""

    def test_a_surname_differing_only_in_diacritics_is_strong(self):
        # Both on birth date 1954-06-06 / 1968-07-25 in the corpus; the old
        # byte-wise comparison scored them `weak` and buried them among 1,404
        # other weak pairs.
        self.assertEqual(review.score_pair("GREBLIAUSKAS", "GRĖBLIAUSKAS"), "strong")
        self.assertEqual(review.score_pair("BARTKUNIENĖ", "BARTKŪNIENĖ"), "strong")

    def test_folding_does_not_make_different_surnames_the_same(self):
        self.assertEqual(review.score_pair("PETRAITIS", "PETRAUSKAS"), "weak")

    def test_fold_strips_diacritics_and_upper_cases(self):
        self.assertEqual(review.fold("Šimonytė"), "SIMONYTE")
        self.assertEqual(review.fold("ŠIMONYTĖ"), review.fold("simonyte"))


class FragmentKeyTests(unittest.TestCase):
    """A key shorter than a birth date, beside the person it belongs to.

    The corpus's 222 `NAME|?` and `NAME|~YYYY` persons come from the
    1996-1999 Seimas archive, which publishes no birth date. 147 of them were
    a second copy of somebody already in the index, and the review could not
    form one of those pairs: it bucketed on the exact birth string and
    skipped a falsy one, so a `~YYYY` bucket could never hold a full-date
    person (issue #141).
    """

    HELD = {"1996-spalio-20-seimo": "1996-10-20", "2020-seimo": "2020-10-11"}

    @staticmethod
    def person(key, name, birth, elections):
        return {
            "k": key,
            "n": name,
            "b": birth,
            "e": [{"id": e, "c": "x"} for e in elections],
        }

    def rows(self, people):
        def pair_row(a, b, score):
            return {"score": score, "name_a": a["n"], "name_b": b["n"], "key_a": a["k"], "key_b": b["k"]}

        return review.fragment_pairs(people, pair_row, self.HELD)

    def test_a_name_only_fragment_pairs_with_its_sole_full_date_bearer(self):
        rows = self.rows([
            self.person("VYTAUTAS LANDSBERGIS|?", "Vytautas Landsbergis", None, ["1996-spalio-20-seimo"]),
            self.person("VYTAUTAS LANDSBERGIS|1932-10-18", "Vytautas LANDSBERGIS", "1932-10-18", ["2020-seimo"]),
        ])
        self.assertEqual([r["score"] for r in rows], ["strong"])

    def test_a_year_only_fragment_needs_the_year_to_agree(self):
        bearer = self.person("EDUARDAS ŠABLINSKAS|1957-10-19", "Eduardas ŠABLINSKAS", "1957-10-19", ["2020-seimo"])
        agrees = self.person("EDUARDAS ŠABLINSKAS|~1957", "Eduardas Šablinskas", "~1957", ["1996-spalio-20-seimo"])
        differs = self.person("EDUARDAS ŠABLINSKAS|~1961", "Eduardas Šablinskas", "~1961", ["1996-spalio-20-seimo"])
        self.assertEqual([r["score"] for r in self.rows([agrees, bearer])], ["strong"])
        self.assertEqual(self.rows([differs, bearer]), [], "a disagreeing year forms no pair")

    def test_several_bearers_of_the_name_is_a_real_ambiguity(self):
        rows = self.rows([
            self.person("JONAS GENYS|?", "Jonas Genys", None, ["1996-spalio-20-seimo"]),
            self.person("JONAS GENYS|1950-01-01", "Jonas GENYS", "1950-01-01", ["2020-seimo"]),
            self.person("JONAS GENYS|1961-02-02", "Jonas Genys", "1961-02-02", ["2020-seimo"]),
        ])
        self.assertEqual(sorted(r["score"] for r in rows), ["given-name", "given-name"])

    def test_one_ballot_settles_it_the_other_way(self):
        # Marija Puč: VRK issued two candidate ids in the 2015 Trakai repeat
        # and published one as a page with no birth date.
        rows = self.rows([
            self.person("MARIJA PUČ|?", "Marija Puč", None, ["1996-spalio-20-seimo"]),
            self.person("MARIJA PUČ|1964-08-13", "Marija PUČ", "1964-08-13", ["1996-spalio-20-seimo"]),
        ])
        self.assertEqual([r["score"] for r in rows], ["same-ballot"])

    def test_a_bearer_who_was_a_minor_is_somebody_else(self):
        # Vytautas Astrauskas: born 1982-09-11 on his 2019 municipal card,
        # 14 years old at the 1996 Seimas election his namesake contested.
        # The only one of the 147 the age check rejected, and the only one
        # whose two birthplaces contradicted.
        rows = self.rows([
            self.person("VYTAUTAS ASTRAUSKAS|?", "Vytautas Astrauskas", None, ["1996-spalio-20-seimo"]),
            self.person("VYTAUTAS ASTRAUSKAS|1982-09-11", "Vytautas ASTRAUSKAS", "1982-09-11", ["2020-seimo"]),
        ])
        self.assertEqual([r["score"] for r in rows], ["impossible"])
        self.assertIn("1996-spalio-20-seimo", rows[0]["note"])

    def test_the_names_are_matched_folded(self):
        rows = self.rows([
            self.person("JOLANTA BARTKUNIENĖ|?", "Jolanta Bartkunienė", None, ["1996-spalio-20-seimo"]),
            self.person("JOLANTA BARTKŪNIENĖ|1968-07-25", "Jolanta Bartkūnienė", "1968-07-25", ["2020-seimo"]),
        ])
        self.assertEqual([r["score"] for r in rows], ["strong"])

    def test_is_fragment_and_birth_year(self):
        self.assertTrue(review.is_fragment({"b": None}))
        self.assertTrue(review.is_fragment({"b": "~1957"}))
        self.assertFalse(review.is_fragment({"b": "1957-10-19"}))
        self.assertIsNone(review.birth_year(None))
        self.assertEqual(review.birth_year("~1957"), "1957")
        self.assertEqual(review.birth_year("1957-10-19"), "1957")


class GivenNameTests(unittest.TestCase):
    """One birth date and one surname, two given names (issue #141).

    The other passes pair only inside an exact first-name match, so 64 such
    pairs were never scored at all — and 21 of them stand in one election,
    which settles those the other way.
    """

    @staticmethod
    def person(name, elections):
        return {"n": name, "e": [{"id": e, "c": "x"} for e in elections]}

    def score(self, first_a, first_b, elections_a=("a",), elections_b=("b",)):
        return review.score_given_names(
            first_a,
            first_b,
            self.person(f"{first_a} X", elections_a),
            self.person(f"{first_b} X", elections_b),
        )

    def test_an_inflection_of_the_same_name_is_strong(self):
        self.assertEqual(self.score("VIKTOR", "VIKTORAS"), "strong")
        self.assertEqual(self.score("VLADIMIR", "VLADIMIRAS"), "strong")

    def test_a_transliteration_is_at_least_worth_review(self):
        for a, b in (("EDUARD", "EDVARD"), ("WALDEMAR", "VALDEMAR"), ("ČESLOVAS", "ČESLAVAS")):
            with self.subTest(f"{a}/{b}"):
                self.assertIn(self.score(a, b), {"strong", "given-name"})

    def test_two_different_names_are_weak(self):
        self.assertEqual(self.score("KAZYS", "JONAS"), "weak")
        self.assertEqual(self.score("EDITA", "HENRIETA"), "weak")

    def test_one_ballot_outranks_every_name_similarity(self):
        # Darjuš and Kšištof Lavrinovič share a birthday and a ballot: twins,
        # not one person. So do 20 other pairs among the 64.
        self.assertEqual(
            self.score("VIKTOR", "VIKTORAS", elections_a=("2016-seimo",), elections_b=("2016-seimo",)),
            "same-ballot",
        )


class ExtensionTests(unittest.TestCase):
    def test_a_hyphenated_married_addition_is_an_extension(self):
        self.assertTrue(
            review.is_extension("Radvilė MORKŪNAITĖ", "Radvilė MORKŪNAITĖ-MIKULĖNIENĖ")
        )

    def test_a_prefixed_maiden_name_is_an_extension(self):
        self.assertTrue(
            review.is_extension("Laima MOGENIENĖ", "Laima VYSKUPAITYTĖ-MOGENIENĖ")
        )

    def test_a_middle_name_on_one_side_only_is_an_extension(self):
        self.assertTrue(
            review.is_extension("Antanas PETUŠKA", "Antanas Juozas Petuška")
        )

    def test_two_different_married_additions_are_not(self):
        self.assertFalse(
            review.is_extension(
                "Edita PUPKEVIČIŪTĖ-BAČĖNĖ", "Edita PUPKEVIČIŪTĖ-KIGUOLĖ"
            )
        )


if __name__ == "__main__":
    unittest.main()
