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
