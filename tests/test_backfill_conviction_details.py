"""`scripts/backfill_conviction_details.py` must write what the parser writes.

Issue #86's HTML route re-parses `2019-kovo-3-savivaldybiu-tarybu` and stores
the result in `rawData`. `parse_anketa_html` returns the parser's working
dict -- `rows`, `normalized` and `stats` -- while the module's record
assembly keeps only `rows`, so storing the whole thing put a second copy of
`normalized.anketa` inside every record it touched. The re-parse gate found
it on all 13,666 (issue #91). This pins the envelope.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.savivaldybiu_2019.anketa_parser import parse_anketa_sample

REPO_ROOT = Path(__file__).resolve().parents[1]
ELECTION_ID = "2019-kovo-3-savivaldybiu-tarybu"
FIXTURES_ROOT = REPO_ROOT / "samples" / "html" / ELECTION_ID
CONVICTION_KEY = "teistumo-detales"


def _load_script():
    path = REPO_ROOT / "scripts" / "backfill_conviction_details.py"
    spec = importlib.util.spec_from_file_location("backfill_conviction_details", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()


class RawDataEnvelopeTests(unittest.TestCase):
    """A backfilled record must be indistinguishable from a parsed one."""

    @classmethod
    def setUpClass(cls) -> None:
        # Gintas Orda is the fixture with a conviction detail table.
        cls.candidate_id = "gintas-orda-2400958"

    def _parsed_record(self, output_root: Path) -> dict:
        output_path, _ = parse_anketa_sample(
            candidate_id=self.candidate_id,
            samples_root=FIXTURES_ROOT,
            output_root=output_root,
        )
        return json.loads(output_path.read_text(encoding="utf-8"))

    def test_the_parser_keeps_only_rows_in_rawdata_anketa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = self._parsed_record(Path(tmp))
        self.assertEqual(set(record["rawData"]["anketa"]), {"rows"})

    def test_the_backfill_leaves_the_same_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            election_dir = root / "data" / ELECTION_ID
            election_dir.mkdir(parents=True)
            (root / "samples" / "html").mkdir(parents=True)
            (root / "samples" / "html" / ELECTION_ID).symlink_to(FIXTURES_ROOT)

            record = self._parsed_record(election_dir)
            record_path = next(election_dir.glob("*.json"))

            # The corpus as it stood before issue #86: the detail table
            # dropped by the 2019-era row loop, in neither layer.
            stored_entries = record["normalized"]["anketa"][CONVICTION_KEY]["irasai"]
            self.assertTrue(stored_entries, "fixture must declare a conviction")
            record["normalized"]["anketa"][CONVICTION_KEY] = {"irasai": []}
            record_path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

            counts, conflicts = script.backfill_from_html(election_dir, root, dry_run=False)
            self.assertEqual(conflicts, [])
            self.assertEqual(counts["updated"], 1)

            healed = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(
                healed["normalized"]["anketa"][CONVICTION_KEY]["irasai"], stored_entries
            )
            self.assertEqual(
                set(healed["rawData"]["anketa"]),
                {"rows"},
                "the backfill must not store the parser's normalized/stats copy",
            )

    def test_a_second_run_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            election_dir = root / "data" / ELECTION_ID
            election_dir.mkdir(parents=True)
            (root / "samples" / "html").mkdir(parents=True)
            (root / "samples" / "html" / ELECTION_ID).symlink_to(FIXTURES_ROOT)

            self._parsed_record(election_dir)
            counts, conflicts = script.backfill_from_html(election_dir, root, dry_run=False)
            self.assertEqual(conflicts, [])
            self.assertEqual(counts["updated"], 0)
            self.assertEqual(counts["unchanged"], 1)


if __name__ == "__main__":
    unittest.main()
