"""The trees a clone does not carry, and the reason a test that needs one skips.

Four directories in this repository are produced by running the scraper rather
than by cloning it, and `.gitignore` keeps them out of git:

* `samples/` -- the fixture tree. A subset of it *is* tracked: every unit at
  most 1 MiB, which is 5,344 files covering at least one candidate of every
  election (`scripts/tracked_fixtures.py` holds the rule). What a clone lacks is
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
produce what they wanted. Two ways in:

* the root `conftest.py` turns a `FileNotFoundError` raised under one of these
  roots into a skip, which covers every test that simply opens a fixture;
* `require(path)` is for the tests that would otherwise fail an assertion
  instead of raising -- a glob over a missing directory yields nothing, and
  `0 != 600` does not say what is wrong.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

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


def describe(path: Path | str) -> str | None:
    """Why `path` is absent, or None when it is not local-only data at all."""
    # `abspath`, not `resolve`: a checkout may reach these trees through a
    # symlink, and following it would land outside the repository.
    try:
        relative = Path(os.path.abspath(path)).relative_to(REPO_ROOT)
    except ValueError:
        return None
    parts = relative.parts
    if not parts or parts[0] not in LOCAL_DATA_ROOTS:
        return None
    return f"{relative.as_posix()} is not in this checkout: {_remedy(parts)}"


def require(*paths: Path) -> None:
    """Skip the calling test when a local-only path it needs is absent.

    For the tests that would not raise on their own: a glob over a directory
    that does not exist returns an empty list, and the assertion that follows
    reports `0 != 600` rather than the missing tree.
    """
    for path in paths:
        if not path.exists():
            raise unittest.SkipTest(describe(path) or f"{path} is missing")
