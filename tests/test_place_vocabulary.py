"""The place vocabulary is generated, and now gated like one (issue #155).

`scraper/shared/vietovardziai.json` is a precision whitelist: the 1996-1999
archive biographies print a birthplace in the locative, suffix rules generate
nominative candidates, and a candidate is written only if it appears in this
file. Nothing looked at it after the commit that created it —
`git log --oneline -- scraper/shared/vietovardziai.json` returned one line
while the corpus grew from ~20 elections to 55, its generator had no
`--check`, no `--dry-run` and no `--repo-root` and wrote on sight, and no
test named it. All five figures in its own header were unreproducible.

So the file is held against its generator here, the way
`docs/coverage-baseline.tsv` is held against `field_coverage.py`. The
`--check` half needs the corpus and skips without it; the filter is unit
tested on the values the corpus actually holds and runs anywhere.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "build_place_vocabulary", REPO_ROOT / "scripts" / "build_place_vocabulary.py"
)
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)

VOCABULARY = json.loads(
    (REPO_ROOT / "scraper" / "shared" / "vietovardziai.json").read_text(encoding="utf-8")
)


class NameFilterTests(unittest.TestCase):
    """What is a nominative place name and what is a questionnaire answer.

    Every string here is a value the corpus holds under `gimimo-vieta`.
    """

    def test_the_names_it_keeps(self):
        for value in ("Akmenė", "Alytus", "Anykščiai", "Adutiškis", "Baltarusija",
                      "Akmenės rajonas", "Alytaus miestas", "Baltarusijos Respublika",
                      "Krasnojarsko kraštas", "Vilniaus rajonas", "Kauno miestas",
                      "Irkutsko sritis", "Sankt-Peterburgas", "Nida", "Šeduvos miestas"):
            with self.subTest(value):
                self.assertTrue(script.looks_like_a_name(value))

    def test_the_answers_it_rejects(self):
        for value in (
            "AKMENĖS RAJ.",              # all-caps
            "AKMENĖ",                    # all-caps, and the same name as Akmenė
            "alytus",                    # lower-cased; no suffix rule produces it
            "Akmenių k., Lazdijų r.",    # a comma: two places, not one name
            "Ariogala,Raseinių raj.",
            "Alytaus r.",                # an abbreviated qualifier
            "Alytaus raj",               # …with the full stop dropped, as VRK often does
            "Kauno m",
            "Klaipėdos raj",
            "Irkutsko sr. Rusija",
            "Adutiškio k. , Švenčionių raj.",
            "Alytaus raj. Punia 2",      # a digit
            "Marijampolė (Kapsukas)",    # a parenthetical
        ):
            with self.subTest(value):
                self.assertFalse(script.looks_like_a_name(value))

    def test_a_space_is_not_a_rejection(self):
        # The multi-word nominatives are what the vocabulary exists for: 9 of
        # the 19 records it resolves go through one.
        for value in ("Krasnojarsko kraštas", "Vilniaus rajonas", "Kauno miestas",
                      "Irkutsko sritis", "Marijampolės apskritis"):
            with self.subTest(value):
                self.assertTrue(script.looks_like_a_name(value))

    def test_the_qualifier_token_has_to_be_a_token(self):
        # `m` in `miestas` and `r` in `rajonas` are not qualifiers, or the
        # filter would reject the very names it is for.
        self.assertTrue(script.looks_like_a_name("Akmenės miestas"))
        self.assertTrue(script.looks_like_a_name("Akmenės rajonas"))
        self.assertTrue(script.looks_like_a_name("Marijampolė"))
        self.assertFalse(script.looks_like_a_name("Akmenės m"))
        self.assertFalse(script.looks_like_a_name("Akmenės r."))


class TrackedFileTests(unittest.TestCase):
    def test_every_tracked_entry_passes_the_filter(self):
        # The file used to hold 1,100 entries of which 778 could never be
        # matched: a suffix rule rewrites the last word of a locative head,
        # so a comma-qualified or mis-capitalised entry is dead weight. This
        # runs on a clone, with no corpus.
        rejected = [n for n in VOCABULARY["places"] if not script.looks_like_a_name(n)]
        self.assertEqual(rejected, [])

    def test_it_says_it_is_generated(self):
        comment = " ".join(VOCABULARY["_comment"])
        self.assertIn("GENERATED", comment)
        self.assertIn("build_place_vocabulary.py", comment)

    def test_its_header_states_the_size_it_has(self):
        # All five figures in the previous header were unreproducible, which
        # is the finding this test exists for.
        comment = " ".join(VOCABULARY["_comment"])
        self.assertIn(f"{len(VOCABULARY['places'])} entries", comment)

    def test_the_entries_are_sorted_and_unique(self):
        places = VOCABULARY["places"]
        self.assertEqual(places, sorted(places))
        self.assertEqual(len(places), len(set(places)))

    def test_the_generator_agrees_with_the_tracked_file(self):
        data_root = REPO_ROOT / "data"
        if not data_root.is_dir() or not any(p.is_dir() for p in data_root.iterdir()):
            raise unittest.SkipTest(
                "no local corpus — `python scripts/build_place_vocabulary.py --check` needs data/"
            )
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "build_place_vocabulary.py"),
             "--check", "--repo-root", str(REPO_ROOT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            "the tracked vocabulary no longer matches its generator:\n"
            + result.stdout + result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
