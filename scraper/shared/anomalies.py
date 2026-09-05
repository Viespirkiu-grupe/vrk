"""Anomaly events, and the one rule for writing them back to an election's file.

`data/<election-id>/anomalies.jsonl` is written by more than one hand: the
batch runner appends each candidate's events as it goes, `parse-anketa-samples`
writes the events of whatever it parsed, `scripts/reparse_diff.py --apply`
regenerates a whole election's parse-stage events, and
`scripts/backfill_url_portraits.py` records the portrait fetches no parser
makes. Until issue #139 the parse command opened the file with `"w"` and
wrote only its own run's events, so the documented one-candidate form
(`parse-anketa-samples 2016-seimo --candidate-id regina-ablom`) took the
election's file from 8,636 lines to 2 -- and the 32 `PortraitFetchFailed`
events in it, which no re-parse can regenerate, went with it.

The rule every writer follows now is ownership by (stage, candidate): a run
owns the events *of its stage* for *the candidates it processed*, replaces
exactly those, and leaves every other line as it found it. `merge_run` is
that rule; `write_run_events` applies it to a file.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from scraper.shared.files import ensure_parent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_anomaly_event(
    *,
    event_type: str,
    severity: str,
    stage: str,
    election_id: str,
    candidate_id: str,
    detail: dict[str, Any] | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": utc_now_iso(),
        "eventType": event_type,
        "severity": severity,
        "stage": stage,
        "electionId": election_id,
        "candidateId": candidate_id,
        "sourceUrl": source_url,
        "detail": detail or {},
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write `rows` as the whole file. Callers that hold only *part* of an
    election's events -- one run's -- go through `write_run_events` instead."""
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Every event in the file, or [] when there is no file.

    A line that is not JSON is skipped rather than raised on, as
    `anomaly_report.read_events` does: the batch runner appends to this file
    over a long unattended scrape, and a truncated last line must not stop
    the next writer from keeping everything else.
    """
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def merge_run(
    stored: list[dict[str, Any]],
    fresh: list[dict[str, Any]],
    *,
    stage: str,
    candidate_ids: Iterable[str] | None,
) -> list[dict[str, Any]]:
    """The file a run leaves behind: what it did not own, then what it found.

    A run owns the events of its own `stage` for the candidates it processed
    (`candidate_ids`; None means the run covered the whole election, as
    `scripts/reparse_diff.py --apply` does). Everything else is kept as
    stored -- another stage's events describe fetches this run never made,
    and another candidate's events describe pages it never opened -- and the
    run's own events follow. Order within the kept part is preserved, so a
    file that is appended to in scrape order stays in scrape order.
    """
    owned = None if candidate_ids is None else set(candidate_ids)
    kept = [
        event
        for event in stored
        if event.get("stage") != stage
        or (owned is not None and event.get("candidateId") not in owned)
    ]
    return kept + list(fresh)


def write_run_events(
    path: Path,
    fresh: list[dict[str, Any]],
    *,
    stage: str,
    candidate_ids: Iterable[str] | None,
) -> tuple[int, int]:
    """Apply `merge_run` to the file at `path`.

    Returns (kept, replaced): how many stored events survived because the run
    did not own them, and how many the run's own events superseded.
    """
    stored = read_jsonl(path)
    merged = merge_run(stored, fresh, stage=stage, candidate_ids=candidate_ids)
    kept = len(merged) - len(fresh)
    write_jsonl(path, merged)
    return kept, len(stored) - kept
