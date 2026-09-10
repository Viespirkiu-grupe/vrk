"""Documented facts, generated-checked instead of hand-maintained.

Issue #84: the two documents a newcomer reads first both stated a corpus
size three elections out of date (113,002 / 51 while the corpus held
113,073 / 55) — nothing failed when a scrape moved the numbers. The headline
pin below was the answer, and for two years it was also the *only* doc-vs-code
test in the suite: grepping `tests/` for the other document names returned a
skip message and prose (issue #151). What had rotted meanwhile:

* `docs/CLI_REFERENCE.md`'s "Supported Election IDs" listed 52 of the 55,
  missing the three 1998/1999 Seimas repeats — each a live argparse choice
  with 11, 11 and 22 records, a row in DATASET's inventory, and a heading in
  CLI_REFERENCE's own workflow section;
* `docs/FIXTURE_SAMPLES.md`, whose shape is one section per election, covered
  50 of the 55 — those three plus `2020-seimo` and `2024-seimo`, each with an
  allowlist test and 60 to 136 tracked fixture files;
* `docs/goal.md`'s "Implemented commands" listed five of the seven the CLI
  builds;
* one relative link in 14 documents pointed at a heading renumbering had
  moved — the sentence telling a contributor a parser change is not done
  until the re-parse gate is green.

So the facts a document states about the code are read out of the prose here
and compared against the code. Most need no corpus and run on CI; the two
that walk `data/` skip without one. The record-shape half of the same audit
lives in `tests/test_record_shape.py`.
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

from local_data import require_corpus

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
DATA_GUIDE = REPO_ROOT / "docs" / "DATA_GUIDE.md"
CLI_REFERENCE = REPO_ROOT / "docs" / "CLI_REFERENCE.md"
FIXTURE_SAMPLES = REPO_ROOT / "docs" / "FIXTURE_SAMPLES.md"
DATASET = REPO_ROOT / "docs" / "DATASET.md"
GOAL = REPO_ROOT / "docs" / "goal.md"
REGISTRY = REPO_ROOT / "scraper" / "elections.json"


def registry_ids() -> set[str]:
    return {e["id"] for e in json.loads(REGISTRY.read_text(encoding="utf-8"))["elections"]}


def markdown_files() -> list[Path]:
    """Every markdown file git carries, which is what a reader can follow."""
    listed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "*.md", "docs/*.md"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [REPO_ROOT / name for name in listed]


def anchors(text: str) -> set[str]:
    """GitHub's heading slugs: lower-cased, punctuation dropped, spaces to `-`."""
    found = set()
    for line in text.splitlines():
        heading = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
        if not heading:
            continue
        found.add(re.sub(r"[^\w\s-]", "", heading.group(1).lower()).strip().replace(" ", "-"))
    return found

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
        _, elections = _headline(README)
        self.assertEqual(elections, len(registry_ids()))

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


class DocumentedElectionIds(unittest.TestCase):
    """Every election the CLI accepts, in the two documents that list them."""

    def test_the_cli_reference_lists_every_id(self):
        section = re.search(
            r"## Supported Election IDs(.*?)(?=\n## )",
            CLI_REFERENCE.read_text(encoding="utf-8"),
            re.S,
        )
        self.assertIsNotNone(section, "CLI_REFERENCE.md has no Supported Election IDs section")
        listed = set(re.findall(r"`([0-9a-z][0-9a-z-]+)`", section.group(1)))
        self.assertEqual(sorted(registry_ids() - listed), [])

    def test_the_fixture_policy_covers_every_election(self):
        # The document's shape is one section per election; an election with
        # an allowlist test and no section is a fixture set nobody documented.
        text = FIXTURE_SAMPLES.read_text(encoding="utf-8")
        self.assertEqual(sorted(e for e in registry_ids() if e not in text), [])

    def test_the_goal_document_lists_every_command(self):
        from scraper import cli

        parser = cli.build_parser()
        commands = set()
        for action in parser._actions:  # noqa: SLF001 - argparse offers no public accessor
            if getattr(action, "dest", None) == "command" and action.choices:
                commands |= set(action.choices)
        self.assertTrue(commands, "no subcommands found on the CLI parser")
        text = GOAL.read_text(encoding="utf-8")
        section = re.search(r"Implemented commands:(.*?)\n\n[A-Z]", text, re.S)
        self.assertIsNotNone(section, "goal.md no longer lists the implemented commands")
        listed = set(re.findall(r"^- `([a-z][a-z-]+)", section.group(1), re.M))
        self.assertEqual(sorted(commands - listed), [])


class DocumentedLinks(unittest.TestCase):
    """Relative links between the documents, and the headings they name."""

    def test_every_relative_link_resolves(self):
        files = markdown_files()
        self.assertGreater(len(files), 10)
        anchor_map = {path.resolve(): anchors(path.read_text(encoding="utf-8")) for path in files}
        broken: list[str] = []
        for path in files:
            for _, target in re.findall(
                r"\[([^\]]*)\]\(([^)\s]+)\)", path.read_text(encoding="utf-8")
            ):
                if target.startswith(("http://", "https://", "mailto:", "#")) and not target.startswith("#"):
                    continue
                file_part, _, anchor = target.partition("#")
                destination = (path.parent / file_part).resolve() if file_part else path.resolve()
                if file_part and not destination.exists():
                    broken.append(f"{path.name} -> {target} (no such file)")
                    continue
                if not anchor:
                    continue
                known = anchor_map.get(destination)
                if known is None:
                    broken.append(f"{path.name} -> {target} (target is not a tracked document)")
                elif anchor.lower() not in known:
                    broken.append(f"{path.name} -> {target} (no such heading)")
        self.assertEqual(broken, [])


class DatasetInventory(unittest.TestCase):
    """DATASET.md's 55-row inventory: 220 numbers, none of them pinned."""

    def test_the_records_column_is_the_corpus(self):
        require_corpus(complete=True)
        text = DATASET.read_text(encoding="utf-8")
        table = re.search(
            r"\| election \| records \| elected \|.*?\n((?:\|.*\n)+)", text
        )
        self.assertIsNotNone(table, "DATASET.md's inventory table has changed shape")
        rows = re.findall(r"^\|\s*`([0-9a-z-]+)`\s*\|\s*([\d,]+)\s*\|", table.group(1), re.M)
        self.assertEqual(len(rows), len(registry_ids()))
        wrong = []
        for election_id, stated in rows:
            directory = REPO_ROOT / "data" / election_id
            held = sum(1 for path in directory.glob("*.json") if path.name != "index.json")
            if held != int(stated.replace(",", "")):
                wrong.append(f"{election_id}: table {stated}, data/ {held}")
        self.assertEqual(wrong, [])


if __name__ == "__main__":
    unittest.main()
