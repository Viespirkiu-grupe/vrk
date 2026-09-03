"""Which fixture files git carries, and the one rule that decides it.

`samples/` is 427 MB on the machine that scraped it -- 55 elections' raw HTML,
two thirds of it embedded base64 portraits -- and it had never been in git. That
left the test suite unrunnable anywhere else: a fresh clone at the same commit
failed 990 tests and errored 194 more, purely because the fixtures were absent
(issue #83). Nothing gated a merge, either, so a parser regression reached the
corpus before anyone could see it.

What git carries is the subset this module selects, and the rule is one number:

    a fixture unit is tracked when it is at most 1 MiB.

A *unit* is a candidate directory with all of its files together, a listing
subdirectory (`lists/`, `districts/`, `municipalities/`, ...), one election's
`samples/results/<election-id>/` tree, or a single top-level listing file
(`list.html`, `page.html`, `lists-index.html`, ...). Units rather than files,
because a candidate whose `anketa.html` was tracked and whose `biografija.html`
was not would not fail -- it would quietly parse to a candidate with no
biography, and the test asserting on that biography would blame the parser.

Only the extensions the parsers open are eligible: `.html`, `.htm`, `.json`,
`.doc` -- and a candidate's retained portrait, `portrait.<ext>` beside the
`portrait.json` that names it, which the record writer reads to externalize
the photo (issue #118); a fixture holding the one and not the other would
parse to a record no scrape could produce. The 2002 presidential declaration
scans (`.jpg`, about 1 MB per candidate) are recorded by path and never read,
so they stay local.

That yields 6,230 files and 69 MiB (852 of them, 25 MiB, the retained
portraits of issue #118) -- every election keeps at least one
candidate fixture, and the 48 candidates that exceed the limit are all
2018-2019 pages carrying the portrait as a base64 data URI in the HTML itself
(`2018-rugsejo-16-seimo-zanavykai/giedrius-surplys` is 86 MB of it). Tests that
need one of those, or a full `lists/` walk, or `sitemaps/`, or `data/`, skip
with a message naming the command that would produce it; see `tests/local_data.py`.

The rule is monotone: pruning a tree can only shrink a unit, so applying it to a
fresh clone selects exactly the files the clone already has. That is why
`tests/test_tracked_fixtures.py` can hold the rule against `git ls-files` and
expect the same answer on this laptop and in CI.

    python scripts/tracked_fixtures.py           # what the rule selects
    python scripts/tracked_fixtures.py --check   # does git agree?
    python scripts/tracked_fixtures.py --sync    # make git agree
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The extensions a parser or a test opens. Everything else in a fixture tree is
#: referenced by path only and is not worth a clone's bytes.
TRACKED_SUFFIXES = frozenset({".html", ".htm", ".json", ".doc"})

#: The one file a parser opens regardless of extension: the retained portrait
#: beside a candidate's pages, whatever container VRK served it in
#: (scraper/shared/files.py reads it when it writes the record).
PORTRAIT_STEM = "portrait"

#: The whole policy. Per unit, not per file -- see the module docstring.
UNIT_LIMIT_BYTES = 1 << 20


def _eligible(path: Path) -> bool:
    return path.suffix.lower() in TRACKED_SUFFIXES or path.stem == PORTRAIT_STEM


def _unit_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*") if path.is_file() and _eligible(path))


def _unit_size(paths: list[Path]) -> int:
    return sum(path.stat().st_size for path in paths)


def _units(samples_root: Path) -> list[list[Path]]:
    """Every candidate group, listing subtree, results tree and listing file."""
    units: list[list[Path]] = []

    html_root = samples_root / "html"
    if html_root.is_dir():
        for election in sorted(html_root.iterdir()):
            if not election.is_dir():
                continue
            for child in sorted(election.iterdir()):
                if child.is_file():
                    if child.suffix.lower() in TRACKED_SUFFIXES:
                        units.append([child])
                elif child.is_dir():
                    units.append(_unit_files(child))

    results_root = samples_root / "results"
    if results_root.is_dir():
        for election in sorted(results_root.iterdir()):
            if election.is_dir():
                units.append(_unit_files(election))

    return units


def selected_paths(repo_root: Path = REPO_ROOT) -> list[str]:
    """The repo-relative fixture paths the rule tracks, in git's order."""
    samples_root = repo_root / "samples"
    selected: list[str] = []
    for unit in _units(samples_root):
        if unit and _unit_size(unit) <= UNIT_LIMIT_BYTES:
            selected.extend(path.relative_to(repo_root).as_posix() for path in unit)
    return sorted(selected)


def tracked_paths(repo_root: Path = REPO_ROOT) -> list[str]:
    """What git currently carries under `samples/`."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--", "samples"],
        cwd=repo_root,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return sorted(entry for entry in listing.split("\0") if entry)


def _git(repo_root: Path, *args: str, paths: list[str]) -> None:
    # One argv per 500 paths keeps the command line well inside every platform's
    # limit; 5,348 fixtures in one call would not be.
    for start in range(0, len(paths), 500):
        subprocess.run(
            ["git", *args, "--", *paths[start : start + 500]],
            cwd=repo_root,
            check=True,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero when git and the rule disagree",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="git add -f / git rm --cached until git and the rule agree",
    )
    args = parser.parse_args(argv)

    selected = selected_paths()

    if not (args.check or args.sync):
        print("\n".join(selected))
        return 0

    tracked = tracked_paths()
    to_add = sorted(set(selected) - set(tracked))
    to_drop = sorted(set(tracked) - set(selected))

    if args.sync:
        if to_add:
            _git(REPO_ROOT, "add", "-f", paths=to_add)
        if to_drop:
            _git(REPO_ROOT, "rm", "--cached", "--quiet", paths=to_drop)
        print(f"tracked {len(selected)} fixture files (+{len(to_add)} -{len(to_drop)})")
        return 0

    for path in to_add:
        print(f"untracked but selected: {path}")
    for path in to_drop:
        print(f"tracked but not selected: {path}")
    if to_add or to_drop:
        print(
            f"\n{len(to_add) + len(to_drop)} path(s) differ; "
            "run `python scripts/tracked_fixtures.py --sync`",
            file=sys.stderr,
        )
        return 1
    print(f"{len(selected)} fixture files tracked, matching the 1 MiB unit rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
