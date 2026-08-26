"""The retention pass's stale-vs-wrong judgement.

`--retain-only` re-fetches the declaration pages the corpus was parsed from
but never kept, so that a later parser fix can be applied offline. It parses
each page again purely as a check -- and the check has to tell two different
things apart:

- a **stale** record, parsed before the parser gained a key. All 5,471 of the
  1997 municipal general election's declarations are this: they predate
  `darboviete`, `pareigos`, `nepagrindines-darbovietes` and
  `pareigos-nepagrindinese-darbovietese`. Re-parsing heals them.
- a **mismatch**, where a key both sides have carries a different value. That
  would mean the live page no longer says what the corpus recorded, and no
  amount of re-parsing fixes it.

A whole-dict comparison collapses the two, flags every record, and says
nothing -- which is exactly what the first version of this check did.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "backfill_archive_declarations.py"

_spec = importlib.util.spec_from_file_location("backfill_archive_declarations", SCRIPT)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
compare_declaration = _module.compare_declaration

# The four keys `deklaracija_archive_1990s.py` gained after the 1997 municipal
# scrape, and the shape of what those records actually stored.
STORED = {
    "valiuta": "Lt",
    "gautos-pajamos-darbo-santykiu": 756,
    "seimos-nariu-skaicius": 4,
}
FRESH = dict(STORED, darboviete='AB"Žeimena"', pareigos="kadrų inspektorė")


class CompareDeclarationTests(unittest.TestCase):
    def test_a_key_the_corpus_never_had_is_stale_not_a_mismatch(self) -> None:
        differing, added = compare_declaration(STORED, FRESH)
        self.assertEqual(differing, [])
        self.assertEqual(added, ["darboviete", "pareigos"])

    def test_a_shared_key_whose_value_moved_is_a_mismatch(self) -> None:
        differing, added = compare_declaration(
            STORED, dict(FRESH, **{"gautos-pajamos-darbo-santykiu": 999})
        )
        self.assertEqual(differing, ["gautos-pajamos-darbo-santykiu"])

    def test_both_can_be_true_at_once(self) -> None:
        differing, added = compare_declaration(STORED, dict(FRESH, valiuta="EUR"))
        self.assertEqual(differing, ["valiuta"])
        self.assertEqual(added, ["darboviete", "pareigos"])

    def test_an_identical_declaration_is_neither(self) -> None:
        self.assertEqual(compare_declaration(STORED, dict(STORED)), ([], []))

    def test_a_key_the_parser_stopped_emitting_is_not_a_mismatch(self) -> None:
        # Dropping a key is a parser regression to catch in the parser's own
        # tests, not evidence that this page disagrees with the corpus.
        differing, added = compare_declaration(FRESH, STORED)
        self.assertEqual(differing, [])
        self.assertEqual(added, [])

    def test_a_missing_declaration_on_either_side_is_survivable(self) -> None:
        self.assertEqual(compare_declaration(None, None), ([], []))
        self.assertEqual(compare_declaration(None, FRESH), ([], sorted(FRESH)))
        self.assertEqual(compare_declaration(STORED, None), ([], []))


class SamplePathsTests(unittest.TestCase):
    """A retained page must land in *every* root the candidate lives in.

    Writing to only one silently breaks a re-parse driven from the other. That
    is not hypothetical: it dropped `abariunas-bronius`'s declaration on the
    next re-parse, because his page went to the fixture directory while
    `parse-anketa-samples` was reading `samples-full/`.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        _module.SAMPLES_ROOT = root / "samples-full"
        _module.FIXTURE_ROOT = root / "samples" / "html"

    def _make(self, root: Path, candidate_id: str) -> Path:
        d = root / "e" / candidate_id
        d.mkdir(parents=True)
        return d

    def test_a_candidate_in_both_roots_gets_both(self) -> None:
        full = self._make(_module.SAMPLES_ROOT, "abariunas-bronius")
        fixture = self._make(_module.FIXTURE_ROOT, "abariunas-bronius")
        self.assertEqual(
            sorted(_module.sample_paths("e", "abariunas-bronius")), sorted([full, fixture])
        )

    def test_a_fixture_only_candidate_stays_beside_its_siblings(self) -> None:
        fixture = self._make(_module.FIXTURE_ROOT, "pilvelis-algirdas")
        self.assertEqual(_module.sample_paths("e", "pilvelis-algirdas"), [fixture])

    def test_a_candidate_with_no_directory_yet_goes_under_samples_full(self) -> None:
        self.assertEqual(
            _module.sample_paths("e", "nobody-at-all"),
            [_module.SAMPLES_ROOT / "e" / "nobody-at-all"],
        )


if __name__ == "__main__":
    unittest.main()
