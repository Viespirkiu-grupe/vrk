"""The fixture subset git carries: exactly the rule, and enough of it to matter.

`scripts/tracked_fixtures.py` decides what is tracked -- every fixture unit at
most 1 MiB -- and this is what keeps git and that rule from drifting apart. It
has to hold in two different worlds: on a machine that scraped everything,
where `samples/` is 427 MB and most of it is deliberately untracked, and in a
clone, where `samples/` *is* the tracked subset. The rule is monotone, so it
selects the same paths in both.

The last test is the one with teeth. A clone whose fixtures had quietly rotted
would still be green -- every test that needs a missing fixture skips -- so
something has to assert that CI is not skipping the whole suite. Every election
module the CLI can parse must have at least one candidate to parse.
"""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

from scraper.cli import PARSABLE_ELECTION_IDS

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_policy():
    path = REPO_ROOT / "scripts" / "tracked_fixtures.py"
    spec = importlib.util.spec_from_file_location("tracked_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = _load_policy()


def _git_tracked() -> list[str] | None:
    """What git carries under `samples/`, or None outside a work tree."""
    try:
        return policy.tracked_paths(REPO_ROOT)
    except (OSError, subprocess.CalledProcessError):
        return None


class TrackedFixtureTests(unittest.TestCase):
    def test_git_carries_exactly_what_the_rule_selects(self) -> None:
        tracked = _git_tracked()
        if tracked is None:
            raise unittest.SkipTest("not a git work tree, so there is nothing to compare")

        selected = policy.selected_paths(REPO_ROOT)
        self.assertEqual(
            sorted(set(selected) - set(tracked)),
            [],
            "fixture(s) under the 1 MiB unit limit are not tracked; run "
            "`python scripts/tracked_fixtures.py --sync`",
        )
        self.assertEqual(
            sorted(set(tracked) - set(selected)),
            [],
            "tracked fixture(s) the rule no longer selects; run "
            "`python scripts/tracked_fixtures.py --sync`",
        )

    def test_every_tracked_fixture_is_in_the_checkout(self) -> None:
        tracked = _git_tracked()
        if tracked is None:
            raise unittest.SkipTest("not a git work tree, so there is nothing to compare")

        missing = [path for path in tracked if not (REPO_ROOT / path).is_file()]
        self.assertEqual(missing, [], "tracked fixture(s) missing from the working tree")

    def test_every_parsable_election_has_a_candidate_to_parse(self) -> None:
        without = []
        for election_id in PARSABLE_ELECTION_IDS:
            election_root = REPO_ROOT / "samples" / "html" / election_id
            candidates = [
                child
                for child in election_root.iterdir()
                if child.is_dir()
                and ((child / "index.json").exists() or (child / "anketa.html").exists())
            ] if election_root.is_dir() else []
            if not candidates:
                without.append(election_id)

        self.assertEqual(
            without,
            [],
            "election module(s) with no candidate fixture in this checkout: the "
            "parser tests for them can only skip",
        )



class PortraitRuleTests(unittest.TestCase):
    """A candidate's retained portrait is tracked with its unit (issue #118)."""

    def _candidate(self, root: Path, portrait_bytes: int) -> Path:
        directory = root / "samples" / "html" / "2020-seimo" / "jonas"
        directory.mkdir(parents=True)
        (directory / "anketa.html").write_text("<html></html>", encoding="utf-8")
        (directory / "index.json").write_text("{}", encoding="utf-8")
        (directory / "portrait.json").write_text("{}", encoding="utf-8")
        (directory / "portrait.jpg").write_bytes(b"\xff" * portrait_bytes)
        # The 2002 presidential declaration scans, by analogy: an image the
        # parsers never open stays local.
        (directory / "deklaracija-1.jpg").write_bytes(b"\xff" * 10)
        return directory

    def test_the_portrait_travels_with_its_pages_and_other_images_do_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._candidate(root, 100)
            self.assertEqual(
                policy.selected_paths(root),
                [
                    "samples/html/2020-seimo/jonas/anketa.html",
                    "samples/html/2020-seimo/jonas/index.json",
                    "samples/html/2020-seimo/jonas/portrait.jpg",
                    "samples/html/2020-seimo/jonas/portrait.json",
                ],
            )

    def test_a_portrait_over_the_limit_takes_its_unit_out_whole(self) -> None:
        # Half a unit -- pages tracked, portrait not -- would parse to a record
        # no scrape could produce; the rule stays per unit.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._candidate(root, policy.UNIT_LIMIT_BYTES)
            self.assertEqual(policy.selected_paths(root), [])

if __name__ == "__main__":
    unittest.main()
