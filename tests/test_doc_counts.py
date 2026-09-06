"""The headline corpus counts, generated-checked instead of hand-maintained.

Issue #84: the two documents a newcomer reads first both stated a corpus
size three elections out of date (113,002 / 51 while the corpus held
113,073 / 55) — nothing failed when a scrape moved the numbers. These tests
read the headlines out of README.md and docs/DATA_GUIDE.md and compare them
against the ground truth: the election registry always, and the corpus
record count whenever a local `data/` tree is present.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from local_data import require_corpus

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
DATA_GUIDE = REPO_ROOT / "docs" / "DATA_GUIDE.md"
REGISTRY = REPO_ROOT / "scraper" / "elections.json"

HEADLINE = re.compile(
    r"([\d,]+) candidate records\s+across\s+(\d+)\s+(?:Lithuanian\s+)?elections"
)


def _headline(path: Path) -> tuple[int, int]:
    match = HEADLINE.search(path.read_text(encoding="utf-8"))
    assert match is not None, f"{path} no longer states the record/election headline"
    return int(match.group(1).replace(",", "")), int(match.group(2))


class HeadlineCounts(unittest.TestCase):
    def test_both_docs_state_the_same_numbers(self):
        self.assertEqual(_headline(README), _headline(DATA_GUIDE))

    def test_election_count_is_the_registry(self):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["elections"]
        _, elections = _headline(README)
        self.assertEqual(elections, len(registry))

    def test_record_count_is_the_corpus(self):
        # A whole-corpus pin: one election copied into data/ made this
        # `113073 != 9` rather than a skip (issue #145).
        require_corpus(complete=True)
        records = sum(
            1
            for child in (REPO_ROOT / "data").iterdir()
            if child.is_dir()
            for path in child.glob("*.json")
            if path.name != "anomalies.jsonl"
        )
        stated, _ = _headline(README)
        self.assertEqual(stated, records)


if __name__ == "__main__":
    unittest.main()
