"""The issue #82 corpus assertion, checked against every record rather than a sample.

Every record of every mapped election -- the 51 non-presidential ones plus
2024-prezidento -- resolves a non-null nominator, and every resolved string is
claimed by the party registry. Per election, not in aggregate: a corpus-wide
99.5 % would let one municipal election quietly lose its join. Skips entirely
on a checkout with no corpus, which is every CI run.
"""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

import local_data

from scraper.shared.nominator import nominator_paths, resolve_nominator
from scraper.shared.parties import match

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"
FORMS_TABLE = REPO_ROOT / "docs" / "nominator-forms.tsv"


class CorpusNominatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        local_data.require(DATA_ROOT)
        cls.mapped = nominator_paths()
        cls.forms: Counter[str] = Counter()
        cls.unresolved: dict[str, list[str]] = {}
        cls.unmatched: dict[str, list[str]] = {}
        cls.elections_seen: list[str] = []
        for election_dir in sorted(p for p in DATA_ROOT.iterdir() if p.is_dir()):
            election_id = election_dir.name
            if election_id not in cls.mapped:
                continue
            cls.elections_seen.append(election_id)
            for record_path in sorted(election_dir.glob("*.json")):
                if record_path.name == "anomalies.jsonl":
                    continue
                record = json.loads(record_path.read_text(encoding="utf-8"))
                raw = resolve_nominator(record, election_id)
                if raw is None:
                    cls.unresolved.setdefault(election_id, []).append(record_path.name)
                    continue
                cls.forms[raw] += 1
                if match(raw) is None:
                    cls.unmatched.setdefault(election_id, []).append(raw)

    def test_the_corpus_has_the_mapped_elections(self):
        self.assertGreater(len(self.elections_seen), 0)

    def test_every_unmapped_data_directory_is_a_nominator_less_presidential_election(self):
        # A new election directory that maps no iskele paths would be
        # invisible to the resolver; only the five elections whose pages
        # publish no nominator are allowed to be.
        present = {p.name for p in DATA_ROOT.iterdir() if p.is_dir()}
        self.assertLessEqual(
            present - set(self.mapped),
            {
                "2002-prezidento",
                "2004-prezidento",
                "2009-prezidento",
                "2014-prezidento",
                "2019-prezidento",
            },
        )

    def test_every_record_of_every_mapped_election_resolves_a_nominator(self):
        self.assertEqual(
            {e: names[:5] for e, names in self.unresolved.items()},
            {},
            "records whose nominator resolves to null on a mapped election",
        )

    def test_every_resolved_form_is_claimed_by_the_registry(self):
        self.assertEqual(
            {e: sorted(set(forms))[:5] for e, forms in self.unmatched.items()},
            {},
            "resolved nominator strings no registry entry claims"
            " -- run scripts/nominator_report.py --update and classify them",
        )

    def test_the_forms_table_is_in_step_with_the_corpus(self):
        # docs/nominator-forms.tsv is the checked-in measurement; a corpus
        # that yields a form the table lacks (or lost one it has) means a
        # scrape moved and `scripts/nominator_report.py --update` was not run.
        table = {
            line.split("\t")[0]
            for line in FORMS_TABLE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("form\t")
        }
        self.assertEqual(set(self.forms), table)


if __name__ == "__main__":
    unittest.main()
