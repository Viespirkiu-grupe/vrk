"""`scripts/backfill_value_hygiene.py` must write what the parser writes.

The script exists for the records a re-parse cannot reach — the ones whose
page was never retained — so its whole claim is that applying the value rules
to a stored record lands in the same place the parser would. Two ways that
can go wrong, and both are pinned here:

* it does *more* than the parser. `interest_row_columns` renames columns and
  splits cells, and the parsers apply it only to a private-interest table's
  rows. Applied to a key/value section, or to `anketa`, it would rename things
  no parser renames and `reparse_diff.py` would report the difference forever.
* it does *less*. A record the parser would leave alone must come back
  unchanged, which is what makes a second run a no-op.

The last test is the strong one: a record the real parser just produced is a
fixed point. It parses a fixture rather than asserting against a literal, so
it keeps testing the actual parser output as the parsers change.
"""

import importlib.util
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scraper.cli import _parse_anketa_samples_for_election

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script():
    path = REPO_ROOT / "scripts" / "backfill_value_hygiene.py"
    spec = importlib.util.spec_from_file_location("backfill_value_hygiene", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

# A stale record's `normalized`, in the shapes issue #101 found: a money
# column stored as the string VRK printed, a gift cell holding its object and
# its date, a value ending in a separator, and an integral money figure.
STALE = {
    "anketa": {
        "vaiku-vardai-pavardes": "Jonas, Rasa,",
        "pagrindine-darboviete": "VšĮ Alytaus poliklinika",
    },
    "turto-ir-pajamu-deklaracijos": {
        "gautos-pajamos": 17861,
        "deklaracijos-metai": 2018,
    },
    "privaciu-interesu-deklaracija": {
        "deklaruojantis-asmuo": "Jonas Jonaitis",
        "id001s": [
            {
                "sandorio-sudarymo-data": "2018-10-27 2018-10-27",
                "sandorio-suma": "22000 EUR",
                "kitos-sandorio-salies-pavadinimas": "AB LUMINOR BANKAS",
            }
        ],
        "vii-gautos-dovanos": [
            {"tipas": "Gauta dovana", "dovana-data": "Kaimo sodyba su žeme, 2006-11-01"}
        ],
    },
}


class RewriteTests(unittest.TestCase):
    def _rewrite(self, normalized, float_paths=frozenset()):
        changes: Counter = Counter()
        return script.rewrite(normalized, set(float_paths), changes), changes

    def test_the_row_rules_reach_a_declaration_table_row(self):
        rewritten, _ = self._rewrite(STALE)
        interest = rewritten["privaciu-interesu-deklaracija"]
        self.assertEqual(
            interest["id001s"][0],
            {
                "sandorio-sudarymo-data": "2018-10-27",
                "sandorio-suma": 22000.0,
                "sandorio-suma-valiuta": "EUR",
                "kitos-sandorio-salies-pavadinimas": "AB LUMINOR BANKAS",
            },
        )
        self.assertEqual(
            interest["vii-gautos-dovanos"][0],
            {"tipas": "Gauta dovana", "dovana": "Kaimo sodyba su žeme", "data": "2006-11-01"},
        )

    def test_the_row_rules_do_not_reach_a_key_value_section(self):
        # `deklaruojantis-asmuo` sits directly under the block, not in a row
        # list, and no parser passes it through `interest_row_columns`.
        rewritten, _ = self._rewrite(
            {"privaciu-interesu-deklaracija": {"sandorio-suma": "22000 EUR"}}
        )
        self.assertEqual(
            rewritten["privaciu-interesu-deklaracija"], {"sandorio-suma": "22000 EUR"}
        )

    def test_the_row_rules_do_not_reach_another_block(self):
        rewritten, _ = self._rewrite({"anketa": {"irasai": [{"dovana-data": "Namas, 2005-01-10"}]}})
        self.assertEqual(rewritten["anketa"]["irasai"][0], {"dovana-data": "Namas, 2005-01-10"})

    def test_the_string_rules_reach_every_block(self):
        rewritten, _ = self._rewrite(STALE)
        self.assertEqual(rewritten["anketa"]["vaiku-vardai-pavardes"], "Jonas, Rasa")

    def test_an_int_is_cast_only_where_its_election_stores_a_float(self):
        rewritten, changes = self._rewrite(
            STALE, {"turto-ir-pajamu-deklaracijos.gautos-pajamos"}
        )
        declaration = rewritten["turto-ir-pajamu-deklaracijos"]
        self.assertIsInstance(declaration["gautos-pajamos"], float)
        # The year is an int in every record of every election, so nothing
        # marks its path as a float column and it stays an int.
        self.assertIsInstance(declaration["deklaracijos-metai"], int)
        self.assertIn("turto-ir-pajamu-deklaracijos.gautos-pajamos", changes)

    def test_a_second_pass_changes_nothing(self):
        float_paths = {"turto-ir-pajamu-deklaracijos.gautos-pajamos"}
        once, _ = self._rewrite(STALE, float_paths)
        twice, changes = self._rewrite(once, float_paths)
        self.assertEqual(twice, once)
        self.assertEqual(changes, Counter())


class FloatColumnTests(unittest.TestCase):
    def test_a_path_stored_as_a_float_on_any_record_is_a_float_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            election_dir = Path(tmp)
            (election_dir / "a.json").write_text(
                json.dumps({"normalized": {"d": {"suma": 5.0, "skaicius": 3}}}), encoding="utf-8"
            )
            (election_dir / "b.json").write_text(
                json.dumps({"normalized": {"d": {"suma": 7, "skaicius": 4}}}), encoding="utf-8"
            )
            self.assertEqual(script._numeric_columns(election_dir), {"d.suma"})


class ParserAgreementTests(unittest.TestCase):
    """A record the parser just wrote must be a fixed point of the backfill."""

    ELECTION_ID = "2019-kovo-3-savivaldybiu-tarybu"

    def test_a_freshly_parsed_record_is_left_alone(self):
        fixtures = REPO_ROOT / "samples" / "html" / self.ELECTION_ID
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            _parse_anketa_samples_for_election(
                election_id=self.ELECTION_ID,
                candidate_ids=None,
                samples_root=fixtures,
                output_root=output_root,
            )
            records = sorted(output_root.glob("*.json"))
            self.assertTrue(records, "the fixture tree parsed no records")
            float_paths = script._numeric_columns(output_root)
            for record_path in records:
                normalized = json.loads(record_path.read_text(encoding="utf-8"))["normalized"]
                changes: Counter = Counter()
                script.rewrite(normalized, float_paths, changes)
                with self.subTest(record_path.name):
                    self.assertEqual(changes, Counter())


if __name__ == "__main__":
    unittest.main()
