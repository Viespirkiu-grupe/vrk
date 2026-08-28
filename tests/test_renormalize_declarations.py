"""`scripts/renormalize_declarations.py` must land where a re-parse would.

`2020-seimo` has no retained HTML beyond its six fixture candidates, so the
election cannot be re-parsed and the repair for issue #81 rebuilds the
declaration block from each record's `rawData` instead. This asserts the two
routes agree on the candidates where both are available, and that the script
refuses to overwrite a figure that is already there.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from scraper.elections.seimo_2020.anketa_parser import parse_anketa_sample


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = REPO_ROOT / "samples" / "html" / "2020-seimo"
DECLARATION_KEY = "turto-ir-pajamu-deklaracijos"
MONEY_KEYS = ("gautos-pajamos", "sumoketas-pajamu-mokestis")


def _load_script():
    path = REPO_ROOT / "scripts" / "renormalize_declarations.py"
    spec = importlib.util.spec_from_file_location("renormalize_declarations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RenormalizeDeclarationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = _load_script()
        cls.candidate_ids = sorted(p.name for p in SAMPLES_ROOT.iterdir() if p.is_dir())

    def _fresh_record(self, candidate_id: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path, _ = parse_anketa_sample(
                candidate_id=candidate_id,
                samples_root=SAMPLES_ROOT,
                output_root=Path(tmp_dir),
            )
            return json.loads(output_path.read_text(encoding="utf-8"))

    def _stale_election_dir(self, root: Path) -> dict[str, dict]:
        """The corpus as it stood: every field parsed, the two money keys null.

        That is exactly what the old normalizer wrote — a fresh parse of these
        fixtures reproduced the stored records key for key, the money rows
        aside.
        """
        election_dir = root / "2020-seimo"
        election_dir.mkdir(parents=True)
        fresh_records = {}
        for candidate_id in self.candidate_ids:
            record = self._fresh_record(candidate_id)
            fresh_records[candidate_id] = record
            stale = json.loads(json.dumps(record))
            for key in MONEY_KEYS:
                stale["normalized"][DECLARATION_KEY][key] = None
            (election_dir / f"{candidate_id}-2020-seimo.json").write_text(
                json.dumps(stale, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        return fresh_records

    def test_renormalized_record_equals_a_fresh_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            fresh_records = self._stale_election_dir(root)

            updated, unchanged, recovered, conflicts = self.script.renormalize_election(
                root / "2020-seimo",
                self.script.ELECTION_NORMALIZERS["2020-seimo"],
                dry_run=False,
            )

            self.assertEqual(updated, len(self.candidate_ids))
            self.assertEqual(unchanged, 0)
            self.assertEqual(conflicts, [])
            for key in MONEY_KEYS:
                self.assertEqual(recovered[key], len(self.candidate_ids))

            for candidate_id in self.candidate_ids:
                patched = json.loads(
                    (root / "2020-seimo" / f"{candidate_id}-2020-seimo.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(patched, fresh_records[candidate_id], candidate_id)

    def test_second_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._stale_election_dir(root)
            for _ in range(2):
                updated, unchanged, _, conflicts = self.script.renormalize_election(
                    root / "2020-seimo",
                    self.script.ELECTION_NORMALIZERS["2020-seimo"],
                    dry_run=False,
                )
                self.assertEqual(conflicts, [])
            self.assertEqual(updated, 0)
            self.assertEqual(unchanged, len(self.candidate_ids))

    def test_a_disagreeing_figure_is_reported_and_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._stale_election_dir(root)
            record_path = next((root / "2020-seimo").glob("*.json"))
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["normalized"][DECLARATION_KEY]["gautos-pajamos"] = 1.0
            record_path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

            _, _, _, conflicts = self.script.renormalize_election(
                root / "2020-seimo",
                self.script.ELECTION_NORMALIZERS["2020-seimo"],
                dry_run=False,
            )

            self.assertEqual(len(conflicts), 1)
            self.assertIn("gautos-pajamos", conflicts[0])
            self.assertEqual(
                json.loads(record_path.read_text(encoding="utf-8")), record
            )


if __name__ == "__main__":
    unittest.main()
