"""Candidate sample fetching for the 1997-12-21 Seimo repeat election."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_aukstaitijos_1997_gruodzio.sitemap import (
    DEFAULT_SITEMAP_PATH,
    ELECTION_ID,
)
from scraper.shared.seimo_archive_1990s import (
    fetch_candidates_samples,
    fetch_first_candidate_sample,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")


def fetch_first_candidate_with_tabs(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    return fetch_first_candidate_sample(sitemap_path, samples_root, allow_new_candidate_dir, ELECTION_ID)


def fetch_candidates_with_tabs(
    candidate_ids: list[str],
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    return fetch_candidates_samples(candidate_ids, sitemap_path, samples_root, allow_new_candidate_dir, ELECTION_ID)
