"""`scripts/renormalize_declarations.py` must land where a re-parse would.

The script rebuilds the declaration block from each record's `rawData` rather
than from HTML, which is the only route to the records whose page was never
retained. That is only safe if the two routes agree, so this asserts it on the
candidates where both are available: a record made stale in the shape the
corpus actually had, re-normalized, has to come out byte-identical to what
`parse_anketa_sample` writes from the same candidate's HTML.

It also pins the resolution the script does for itself — every election id to
the normalizer its own module calls — because a table that silently loses an
election is how issue #81 stayed hidden for four elections at a time.
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
        cls.normalizers = cls.script.election_normalizers()
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

        That is exactly what the pre-#81 normalizer wrote — a fresh parse of
        these fixtures reproduced the stored records key for key, the money
        rows aside.
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

            updated, unchanged, changes = self.script.renormalize_election(
                root / "2020-seimo",
                self.normalizers["2020-seimo"],
                dry_run=False,
            )

            self.assertEqual(updated, len(self.candidate_ids))
            self.assertEqual(unchanged, 0)
            for key in MONEY_KEYS:
                self.assertEqual(changes[f"~ {key}"], len(self.candidate_ids))

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
                updated, unchanged, _ = self.script.renormalize_election(
                    root / "2020-seimo",
                    self.normalizers["2020-seimo"],
                    dry_run=False,
                )
            self.assertEqual(updated, 0)
            self.assertEqual(unchanged, len(self.candidate_ids))

    def test_a_dry_run_reports_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._stale_election_dir(root)
            before = {
                path.name: path.read_text(encoding="utf-8")
                for path in (root / "2020-seimo").glob("*.json")
            }

            updated, _, changes = self.script.renormalize_election(
                root / "2020-seimo",
                self.normalizers["2020-seimo"],
                dry_run=True,
            )

            self.assertEqual(updated, len(self.candidate_ids))
            self.assertEqual(changes[f"~ {MONEY_KEYS[0]}"], len(self.candidate_ids))
            for path in (root / "2020-seimo").glob("*.json"):
                self.assertEqual(path.read_text(encoding="utf-8"), before[path.name])

    def test_a_record_with_no_stored_block_is_left_alone(self) -> None:
        """The block's absence is the parser's statement, not a gap to fill.

        `jonas-korsakas-2020-seimo` has no declarations page at all; a record
        like it must not gain an all-null block from a run of this script.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._stale_election_dir(root)
            record_path = next((root / "2020-seimo").glob("*.json"))
            record = json.loads(record_path.read_text(encoding="utf-8"))
            del record["normalized"][DECLARATION_KEY]
            written = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
            record_path.write_text(written, encoding="utf-8")

            self.script.renormalize_election(
                root / "2020-seimo", self.normalizers["2020-seimo"], dry_run=False
            )

            self.assertEqual(record_path.read_text(encoding="utf-8"), written)

    def test_every_election_with_a_declaration_resolves_to_a_normalizer(self) -> None:
        """Every election whose pages publish a declaration has to be reachable.

        The 1996-2002 archive elections are the documented exception on the
        other side: their parser writes the declaration straight into
        `rawData`, so there is nothing to re-normalize it from.
        """
        for election_id in (
            "2004-ep",
            "2004-seimo",
            "2007-vasario-25-savivaldybiu",
            "2011-vasario-27-savivaldybiu",
            "2015-kovo-1-savivaldybiu",
            "2016-seimo",
            "2019-kovo-3-savivaldybiu-tarybu",
            "2020-seimo",
            "2023-kovo-5-savivaldybiu-tarybu-ir-meru",
            "2024-seimo",
            "2025-kovo-16-meru",
            "2002-gruodzio-22-savivaldybiu-tarybu",
            "2003-birzelio-15-seimo-nauji",
        ):
            with self.subTest(election=election_id):
                self.assertIn(election_id, self.normalizers)

    def test_the_archive_elections_are_not_claimed(self) -> None:
        for election_id in ("1996-spalio-20-seimo", "1997-kovo-23-savivaldybiu-tarybu", "2000-seimo"):
            with self.subTest(election=election_id):
                self.assertNotIn(election_id, self.normalizers)


if __name__ == "__main__":
    unittest.main()
