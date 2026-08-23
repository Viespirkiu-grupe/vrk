"""Candidate sample fetching for the 2000-03-19 municipal council election.

One page per candidate (``kandvl.htm-<ID>.htm``: card, declarations,
questionnaire fields and the income extract in one document), saved as
``candidate.html`` by the October 2000 Seimas election's fetcher.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.savivaldybiu_2000.sitemap import DEFAULT_SITEMAP_PATH, ELECTION_ID, load_sitemap_entries
from scraper.elections.seimo_2000.candidate_samples import (
    CANDIDATE_PAGE_NAME,
    EXPECTED_TABS,
    fetch_candidate_sample,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")

__all__ = ["CANDIDATE_PAGE_NAME", "EXPECTED_TABS", "fetch_candidates_with_tabs", "fetch_first_candidate_with_tabs"]


def fetch_candidates_with_tabs(
    candidate_ids: list[str],
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    if not candidate_ids:
        raise ValueError("At least one candidate id must be provided")
    entries_by_id = {entry["candidateId"]: entry for entry in load_sitemap_entries(sitemap_path)}
    missing_ids = [cid for cid in candidate_ids if cid not in entries_by_id]
    if missing_ids:
        raise ValueError("Candidate IDs not found in sitemap: " + ", ".join(sorted(set(missing_ids))))
    results = [
        fetch_candidate_sample(entries_by_id[candidate_id], samples_root, allow_new_candidate_dir)
        for candidate_id in candidate_ids
    ]
    return {"count": len(results), "results": results}


def fetch_first_candidate_with_tabs(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    entry = load_sitemap_entries(sitemap_path)[0]
    return fetch_candidate_sample(entry, samples_root, allow_new_candidate_dir)
