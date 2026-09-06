"""Make the suite runnable on a checkout that has never scraped anything.

Two jobs, both of which the suite used to leave to whoever ran it:

1. Put the repository root on `sys.path`, so `import scraper` works whatever
   directory `pytest` was invoked from.
2. Turn "this fixture is not in the checkout" into a skip instead of a failure.
   `samples/` beyond the tracked subset, `sitemaps/`, `data/` and `samples-full/`
   are scraper outputs that `.gitignore` keeps out of git; a clone that lacks
   them used to report 990 failures and 194 errors, every one of them a
   `FileNotFoundError` with no hint of what to do about it (issue #83).

The conversion is deliberately narrow. Only a `FileNotFoundError` whose
filename lies under one of those four roots becomes a skip, and only when the
*unit* the path belongs to -- the candidate directory, the election's results
tree, the sitemap file, the election's `data/` directory
(`local_data.unit_of`) -- is absent from the checkout. A parser that builds
the wrong path inside a unit that is here still fails, and so does an
assertion about a fixture that is present. Until issue #145 any `OSError`
under those roots was a skip, which is exactly where every path a parser
builds lives: a one-character bug in one parser turned 18 passing tests into
18 skips and the suite exited 0. Tests that would pass vacuously rather than
raise call `tests/local_data.py`'s `require()` / `require_corpus()` instead.

The same file holds the one environment contract CI has: the dashboard tests
run their JavaScript under node, and without it 42 of them skip. Locally that
is a skip; on CI (`CI` set, as GitHub Actions does) it is a broken runner, and
the session refuses to start rather than report a green suite that verified
less than it claims.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent

for entry in (REPO_ROOT, REPO_ROOT / "tests"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from local_data import describe  # noqa: E402  (needs the sys.path above)


def _missing_local_data(error: BaseException | None) -> str | None:
    """The skip reason for an error raised by reading absent local data."""
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, FileNotFoundError) and error.filename:
            reason = describe(error.filename)
            if reason is not None:
                return reason
        error = error.__cause__ or error.__context__
    return None


def pytest_sessionstart(session):
    if os.environ.get("CI") and shutil.which("node") is None:
        raise pytest.UsageError(
            "node is not on PATH: the dashboard tests would skip and CI would report a"
            " suite that verified less than it claims. .github/workflows/tests.yml installs"
            " it with actions/setup-node; a runner without it is broken, not green."
        )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not report.failed or call.excinfo is None:
        return
    reason = _missing_local_data(call.excinfo.value)
    if reason is not None:
        report.outcome = "skipped"
        report.longrepr = (str(item.path), item.location[1] + 1, f"Skipped: {reason}")
