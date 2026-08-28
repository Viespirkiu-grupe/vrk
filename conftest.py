"""Make the suite runnable on a checkout that has never scraped anything.

Two jobs, both of which the suite used to leave to whoever ran it:

1. Put the repository root on `sys.path`, so `import scraper` works whatever
   directory `pytest` was invoked from.
2. Turn "this fixture is not in the checkout" into a skip instead of a failure.
   `samples/` beyond the tracked subset, `sitemaps/`, `data/` and `samples-full/`
   are scraper outputs that `.gitignore` keeps out of git; a clone that lacks
   them used to report 990 failures and 194 errors, every one of them a
   `FileNotFoundError` with no hint of what to do about it (issue #83).

The conversion is deliberately narrow. Only `OSError`s carrying a filename
under one of those four roots become skips -- a parser that raises
`FileNotFoundError` for a path it built wrongly still fails, and so does an
assertion about a fixture that is present. Tests that would pass vacuously
rather than raise call `tests/local_data.py`'s `require()` instead.
"""

from __future__ import annotations

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
        if isinstance(error, OSError) and error.filename:
            reason = describe(error.filename)
            if reason is not None:
                return reason
        error = error.__cause__ or error.__context__
    return None


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
