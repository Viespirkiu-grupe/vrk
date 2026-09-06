"""The trees a clone does not carry, and the reason a test that needs one skips.

Four directories in this repository are produced by running the scraper rather
than by cloning it, and `.gitignore` keeps them out of git:

* `samples/` -- the fixture tree. A subset of it *is* tracked: every unit at
  most 1 MiB, which is 6,230 files covering at least one candidate of every
  election, retained portraits included (`scripts/tracked_fixtures.py` holds
  the rule). What a clone lacks is
  the rest -- the 2016-2019 candidates whose portrait is a multi-megabyte base64
  data URI inside the HTML, the full `lists/` walks of the municipal elections,
  and the larger `results/` trees.
* `sitemaps/` -- 77 MB of crawl plans, one or two files per election.
* `data/` -- the 3.6 GB corpus itself.
* `samples-full/` -- every retained candidate page, which is what
  `scripts/reparse_diff.py --full` re-parses.

A test that reads one of them used to fail on a machine that had never scraped
anything: 990 failures and 194 errors on a fresh clone, all of them
`FileNotFoundError` (issue #83). They skip now, naming the command that would
produce what they wanted. Four ways in:

* the root `conftest.py` turns a `FileNotFoundError` raised under one of these
  roots into a skip, which covers every test that simply opens a fixture --
  but only when the *unit* the path belongs to is absent (`unit_of`): the
  candidate directory under `samples/html/<election>/`, the election's
  `samples/results/` tree, the retained candidate under `samples-full/`, the
  sitemap file, the election directory under `data/`. A path missing inside a
  unit that is here is a parser building the wrong path, and stays a failure.
  Issue #145 measured the alternative: any `OSError` under the four roots
  became a skip, and a one-character parser bug ("anketa.htm") turned 18
  passing tests into 18 skips with the suite exiting 0.
* `require(path)` is for the tests that would otherwise fail an assertion
  instead of raising -- a glob over a missing directory yields nothing, and
  `0 != 600` does not say what is wrong;
* `require_corpus()` is for the tests that read `data/` as a whole: it skips
  unless an election's records are actually there (a `data/` holding only a
  coverage report is not a corpus), and with `complete=True` unless every
  registered election is, which is what a pin on the whole corpus assumes;
* `Fixture(load, ...)` is for a class that parses several fixtures of which a
  clone carries only some. Parsed in `setUp`, one absent fixture skips every
  test in the class; declared as a lazily loaded attribute, only the tests
  that read it skip (issue #111).
"""

from __future__ import annotations

import json
import os
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "scraper" / "elections.json"

#: The directories `.gitignore` keeps out of git, in the order a path is matched.
LOCAL_DATA_ROOTS = ("samples", "samples-full", "sitemaps", "data")

_OUTSIDE_SUBSET = (
    "fixture is outside the tracked subset (at most 1 MiB per unit, see "
    "scripts/tracked_fixtures.py)"
)


def _remedy(parts: tuple[str, ...]) -> str:
    """The command that would produce the path, as far as the path names it."""
    election = parts[2] if len(parts) > 2 else "<election-id>"
    if parts[0] == "samples":
        if len(parts) > 3 and parts[1] == "html":
            return (
                f"{_OUTSIDE_SUBSET}; `python -m scraper fetch-sample {election}` and "
                f"`fetch-candidate-samples {election} --candidate-id <id>` capture it"
            )
        if parts[1] == "results":
            return f"{_OUTSIDE_SUBSET}; `python -m scraper build-results {election}` captures it"
        return _OUTSIDE_SUBSET
    if parts[0] == "sitemaps":
        # sitemaps/<election-id>.json, sitemaps/<election-id>.results.json
        name = parts[1].split(".")[0] if len(parts) > 1 else "<election-id>"
        return f"build it with `python -m scraper sitemap {name}`"
    if parts[0] == "data":
        name = parts[1] if len(parts) > 1 else "<election-id>"
        return f"corpus record; scrape {name} to produce it (docs/CLI_REFERENCE.md)"
    return f"retained HTML is never tracked; it comes from a full scrape of {parts[1] if len(parts) > 1 else 'an election'}"


def unit_of(relative: Path) -> Path:
    """The local-data unit a repo-relative path belongs to -- what a scrape
    produces whole, and what a clone either has or lacks whole:

        samples/html/<election>/<unit>/…   -> samples/html/<election>/<unit>
        samples/results/<election>/…       -> samples/results/<election>
        samples-full/<election>/<cand>/…   -> samples-full/<election>/<cand>
        sitemaps/<file>                    -> sitemaps/<file>
        data/<election>/…                  -> data/<election>

    The same granularity `scripts/tracked_fixtures.py` tracks at, so a
    tracked unit is complete or absent, never half here. Anything shorter
    than its unit (the election directory itself, say) is its own unit.
    """
    parts = relative.parts
    root = parts[0] if parts else ""
    if root == "samples" and len(parts) >= 2:
        if parts[1] == "html":
            return Path(*parts[:4]) if len(parts) >= 4 else relative
        if parts[1] == "results":
            return Path(*parts[:3]) if len(parts) >= 3 else relative
        return relative
    if root == "samples-full":
        return Path(*parts[:3]) if len(parts) >= 3 else relative
    if root in ("sitemaps", "data"):
        return Path(*parts[:2]) if len(parts) >= 2 else relative
    return relative


def describe(path: Path | str, repo_root: Path = REPO_ROOT) -> str | None:
    """Why `path` is absent, or None when its absence is not a clone's --
    because it is not local-only data at all, or because the unit it belongs
    to *is* in this checkout and the path was built wrongly."""
    # `abspath`, not `resolve`: a checkout may reach these trees through a
    # symlink, and following it would land outside the repository.
    try:
        relative = Path(os.path.abspath(path)).relative_to(repo_root)
    except ValueError:
        return None
    parts = relative.parts
    if not parts or parts[0] not in LOCAL_DATA_ROOTS:
        return None
    unit = unit_of(relative)
    if (repo_root / unit).exists():
        return None
    return f"{unit.as_posix()} is not in this checkout: {_remedy(parts)}"


def page_names(directory: Path) -> set[str]:
    """The names in a fixture candidate directory, less its retained portrait.

    The allowlists pin what a candidate directory holds *of the site* -- the
    pages the walker fetched. The `portrait.json` and `portrait.<ext>` that
    scripts/backfill_url_portraits.py leaves beside them (issue #118) are the
    portrait those pages link, retained so the record writer can externalize
    it; `tests/test_retained_portraits.py` checks those, not the allowlists.
    """
    return {child.name for child in directory.iterdir() if child.stem != "portrait"}


def require(*paths: Path) -> None:
    """Skip the calling test when a local-only path it needs is absent.

    For the tests that would not raise on their own: a glob over a directory
    that does not exist returns an empty list, and the assertion that follows
    reports `0 != 600` rather than the missing tree.
    """
    for path in paths:
        if not path.exists():
            raise unittest.SkipTest(describe(path) or f"{path} is missing")


def corpus_elections(repo_root: Path = REPO_ROOT) -> set[str]:
    """The elections whose records are under data/ -- a directory with at
    least one record file, not merely a directory."""
    data_root = repo_root / "data"
    if not data_root.is_dir():
        return set()
    return {
        child.name
        for child in data_root.iterdir()
        if child.is_dir() and any(path.name != "anomalies.jsonl" for path in child.glob("*.json"))
    }


def require_corpus(*, complete: bool = False, repo_root: Path = REPO_ROOT) -> None:
    """Skip the calling test unless `data/` holds a corpus to read.

    `data/` existing is not the corpus existing: `scripts/field_coverage.py`
    used to create it for its report on a pristine clone, after which every
    whole-corpus test ran against nothing and failed (issue #145). With
    `complete=True` every registered election has to be present -- the
    assumption behind a pin on the whole corpus's record count, which one
    election copied in turned into `113073 != 9`.
    """
    present = corpus_elections(repo_root)
    if not present:
        raise unittest.SkipTest(
            "data/ holds no election records: the corpus is scraped, not cloned"
            " (docs/CLI_REFERENCE.md)"
        )
    if complete:
        registry = json.loads((repo_root / "scraper" / "elections.json").read_text(encoding="utf-8"))["elections"]
        missing = sorted(entry["id"] for entry in registry if entry["id"] not in present)
        if missing:
            shown = ", ".join(missing[:4]) + (", …" if len(missing) > 4 else "")
            raise unittest.SkipTest(
                f"data/ holds {len(present)} of {len(registry)} registered elections; this"
                f" whole-corpus pin needs all of them (missing: {shown})"
            )


class Fixture:
    """A parsed fixture, loaded the first time a test reads it.

    A `setUp` that parses every fixture its class uses lets one untracked
    fixture skip the whole class on a clone -- the tests that read only
    tracked fixtures included. That is how the 2019 declaration tests sat
    asserting a shape two refactors old while CI stayed green (issue #111):
    CI never ran them. Declared as a class attribute instead,

        nauseda = Fixture(_parse, "gitanas-nauseda")

    the fixture is parsed once, on the first test that reads `self.nauseda`,
    and the `FileNotFoundError` for an absent one is raised in that test alone,
    where the root conftest turns it into a skip. Raised inside `subTest` it
    skips that subtest alone, so a loop that reads each candidate inside its
    own subtest checks the tracked candidates on a clone and skips the rest
    by name.
    """

    _UNSET = object()

    def __init__(self, load: Callable[..., Any], *args: Any) -> None:
        self._load = load
        self._args = args
        self._value: Any = self._UNSET

    def __get__(self, instance: object, owner: type | None = None) -> Any:
        if instance is None:
            return self
        if self._value is self._UNSET:
            self._value = self._load(*self._args)
        return self._value
