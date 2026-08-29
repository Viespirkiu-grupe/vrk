"""Read the corpus's `anomalies.jsonl` files, and say what changed.

The scrapers have written anomaly events since the first election, and until
issue #85 no command read them back. Eight and a half thousand events sat in
`data/*/anomalies.jsonl` with nothing to compare them against, so nobody could
tell a new failure from the known ones -- and 8,598 of them are a single
archive page type printing VRK's own query-error banner, which drowns the
other 351 completely.

Two things make the pile readable:

* **severity**: the banner events are `info`. Anything above that is a finding
  somebody has to look at, and `--errors-only` narrows further to the events
  that mean a page was lost rather than doubted.
* **a baseline**: `docs/anomaly-baseline.tsv` records one line per (election,
  event type, severity) with the count the corpus holds today. A run that
  produces an event type the baseline does not name, or more of one than it
  records, is a finding; fewer is progress and is reported without failing.

The baseline keys on severity as well as type, so that reclassifying an event
-- which is a real change to what stops an unattended run -- shows up as a
resolved row and a new one rather than passing silently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, NamedTuple

ANOMALIES_NAME = "anomalies.jsonl"
BASELINE = Path("docs/anomaly-baseline.tsv")
BASELINE_COLUMNS = ("election", "eventType", "severity", "count")

#: Ascending, so a report can sort by how much attention an event wants.
#: `critical` is in the parsers (44 call sites, none of which has ever fired)
#: and was in none of the documentation; a report that did not know the word
#: would sort the worst event in the corpus below the quietest.
SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2, "critical": 3}


class Key(NamedTuple):
    election: str
    event_type: str
    severity: str


def read_events(data_root: Path, election_ids: list[str] | None = None) -> Iterator[dict[str, Any]]:
    """Every anomaly event in the corpus, or in the named elections.

    A line that is not JSON is skipped rather than raised on: this file is
    appended to by a shell loop over a long unattended scrape, and a truncated
    last line should not stop the report that would tell you the scrape died.
    """
    if election_ids is None:
        directories = sorted(child for child in data_root.iterdir() if child.is_dir())
    else:
        directories = [data_root / election_id for election_id in election_ids]
    for directory in directories:
        path = directory / ANOMALIES_NAME
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                event.setdefault("electionId", directory.name)
                yield event


def tally(events: Iterator[dict[str, Any]] | list[dict[str, Any]]) -> dict[Key, int]:
    counts: dict[Key, int] = {}
    for event in events:
        key = Key(
            str(event.get("electionId", "unknown")),
            str(event.get("eventType", "unknown")),
            str(event.get("severity", "unknown")),
        )
        counts[key] = counts.get(key, 0) + 1
    return counts


def read_baseline(path: Path) -> dict[Key, int]:
    if not path.exists():
        return {}
    baseline: dict[Key, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 4 or fields[0] == BASELINE_COLUMNS[0]:
            continue
        election, event_type, severity, count = fields
        baseline[Key(election, event_type, severity)] = int(count)
    return baseline


def write_baseline(path: Path, counts: dict[Key, int]) -> None:
    lines = ["\t".join(BASELINE_COLUMNS)]
    lines.extend(
        "\t".join([key.election, key.event_type, key.severity, str(count)])
        for key, count in sorted(counts.items())
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def diff(
    counts: dict[Key, int], baseline: dict[Key, int]
) -> tuple[list[tuple[Key, int]], list[tuple[Key, int, int]], list[tuple[Key, int, int]]]:
    """Compare a tally against the baseline.

    Returns (new, regressed, improved): types the baseline does not name,
    counts above it, and counts below it. Only the first two are findings --
    an event type that stopped firing is a parser fix, and the baseline is
    updated deliberately rather than by the check that reads it.
    """
    new = [(key, count) for key, count in sorted(counts.items()) if key not in baseline]
    regressed = [
        (key, count, baseline[key])
        for key, count in sorted(counts.items())
        if key in baseline and count > baseline[key]
    ]
    improved = [
        (key, counts.get(key, 0), was)
        for key, was in sorted(baseline.items())
        if counts.get(key, 0) < was
    ]
    return new, regressed, improved


def by_election(counts: dict[Key, int]) -> dict[str, list[tuple[Key, int]]]:
    """Group a tally for printing: worst severity first, then commonest."""
    grouped: dict[str, list[tuple[Key, int]]] = {}
    for key, count in counts.items():
        grouped.setdefault(key.election, []).append((key, count))
    for rows in grouped.values():
        rows.sort(key=lambda row: (-SEVERITY_ORDER.get(row[0].severity, 0), -row[1], row[0].event_type))
    return dict(sorted(grouped.items()))


def severity_totals(counts: dict[Key, int]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for key, count in counts.items():
        totals[key.severity] = totals.get(key.severity, 0) + count
    return dict(sorted(totals.items(), key=lambda item: -SEVERITY_ORDER.get(item[0], 0)))
