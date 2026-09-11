"""`scraper/shared/tautybe.py` folds every spelling the corpus holds (issue #162).

The list below is every distinct `anketa.tautybe` / `biografija.tautybe`
answer in the corpus on 2026-09-11 -- 117 spellings of 89,154 answers -- so
the canonicaliser is pinned on a clone that has no corpus, and the corpus
test beside it catches a spelling a new election brings.
"""

import json
import unittest
from pathlib import Path

from scraper.shared.tautybe import GROUPS, fold_spelling, tautybe

REPO_ROOT = Path(__file__).resolve().parents[1]

CORPUS_SPELLINGS = [
    "Lietuvis (-ė)", "lietuvis", "Lietuvis", "Lietuvė", "lietuvė", "Lenkas (-ė)", "Rusas (-ė)",
    "lenkas", "lenkė", "rusas", "rusė", "Lenkė", "Lenkas", "LENKĖ", "RUSĖ", "LENKAS", "RUSAS",
    "Baltarusis (-ė)", "Ukrainietis (-ė)", "ukrainietis (-ė)", "baltarusė", "baltarusis",
    "Žydas (-ė)", "UKRAINIETIS", "Latvis (-ė)", "Vokietis (-ė)", "Rusas", "UKRAINIETĖ",
    "latvis (-ė)", "žydas", "totorius (-ė)", "Rusė", "Baltarusas", "Baltarusė", "Totorius (-ė)",
    "vokietė", "ŽYDAS", "žemaitis", "vokietis", "BALTARUSAS", "armėnas (-ė)", "TOTORIUS",
    "VOKIETĖ", "LATVIS", "ARMĖNAS", "Armėnas (-ė)", "BALTARUSĖ", "VOKIETIS", "gruzinė",
    "Graikas (-ė)", "TOTORĖ", "LATVĖ", "Karaimas (-ė)", "Lezginas (-ė)", "AZERBAIDŽANIETIS",
    "UZBEKĖ", "Azerbaidžanietis (-ė)", "Prancūzas (-ė)", "uzbekas (-ė)", "MOLDAVAS", "GRAIKĖ",
    "PRANCŪZAS", "Totorius", "Suomis (-ė)", "Moldavas (-ė)", "Žemaitis (-ė)", "italas (-ė)",
    "kazachas", "baškiras", "udmurtas (-ė)", "lezginas (-ė)", "graikas (-ė)", "ingušas (-ė)",
    "vengras (-ė)", "Žydas", "ESTĖ", "ANGLĖ", "KAZACHAS", "Graikė", "MOLDAVA", "ESTAS",
    "AFRIKANERĖ", "ARMĖNĖ", "Čekas (-ė)", "Ingušas(-ė)", "Uzbekas (-ė)", "Italas (-ė)",
    "Čiuvašas (-ė)", "čigonas (-ė)", "mari", "moldavas (-ė)", "libanietis (-ė)",
    "čiuvašas (-ė)", "karaimas (-ė)", "anglas (-ė)", "azerbaidžanietis (-ė)", "Žydė", "ITALAS",
    "VIETNAMIETIS", "GRUSĖ", "ČILIETIS", "SLOVAKĖ", "KOLUMBIETIS", "ISPANAS", "KOMĖ", "ETIOPĖ",
    "TALYŠAS", "Ukrainietė", "Vokietis", "Moldava", "Armėnė", "INDIJOS IR PAKISTANO TAUTYBĖS",
    "ISPANĖ", "GRUZINAS", "TURKAS", "AIRIS", "KARAIMĖ",
]


class FoldTests(unittest.TestCase):
    def test_gender_case_and_the_printed_suffix_fold_away(self):
        for spelling in ("Lietuvis (-ė)", "LIETUVIS", "lietuvis", "Lietuvis", "Ingušas(-ė)"):
            with self.subTest(spelling):
                self.assertNotIn("(", fold_spelling(spelling))
        self.assertEqual(tautybe("Lietuvis (-ė)"), tautybe("lietuvė"))
        self.assertEqual(tautybe("LENKĖ")["id"], "lenkai")

    def test_the_group_is_named_as_the_census_names_it(self):
        self.assertEqual(tautybe("Ukrainietis (-ė)"), {"id": "ukrainieciai", "label": "ukrainiečiai"})
        self.assertEqual(tautybe("čigonas (-ė)")["label"], "romai (čigonai)")

    def test_no_answer_is_none_and_an_unknown_one_is_shown_not_hidden(self):
        for empty in (None, "", "  ", 5):
            with self.subTest(repr(empty)):
                self.assertIsNone(tautybe(empty))
        self.assertEqual(tautybe("Marsietis"), {"id": None, "label": "marsietis"})

    def test_every_spelling_the_corpus_holds_folds_to_a_group(self):
        self.assertEqual(len(CORPUS_SPELLINGS), 117)
        unclaimed = [s for s in CORPUS_SPELLINGS if tautybe(s)["id"] is None]
        self.assertEqual(unclaimed, [])
        groups = {tautybe(s)["id"] for s in CORPUS_SPELLINGS}
        self.assertEqual(groups, set(GROUPS), "a group no spelling reaches is dead weight")


class CorpusTests(unittest.TestCase):
    """The same claim over data/ itself, where a checkout has it."""

    def test_every_answer_in_the_corpus_folds_to_a_group(self):
        data = REPO_ROOT / "data"
        if not data.is_dir() or not any(data.iterdir()):
            self.skipTest("no corpus under data/")
        unclaimed: set[str] = set()
        answers = 0
        for path in data.glob("*/*.json"):
            normalized = json.loads(path.read_text(encoding="utf-8")).get("normalized") or {}
            for section in ("anketa", "biografija"):
                value = (normalized.get(section) or {}).get("tautybe") if isinstance(normalized.get(section), dict) else None
                folded = tautybe(value)
                if folded is None:
                    continue
                answers += 1
                if folded["id"] is None:
                    unclaimed.add(value)
        self.assertGreater(answers, 0)
        self.assertEqual(sorted(unclaimed), [])


if __name__ == "__main__":
    unittest.main()
