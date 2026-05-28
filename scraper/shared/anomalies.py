from __future__ import annotations

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
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
