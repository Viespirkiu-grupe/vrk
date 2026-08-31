"""Candidate record parsing for the 1997-03-23 municipal council general election."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.savivaldybiu_1997.candidate_samples import DEFAULT_SAMPLES_ROOT
from scraper.elections.savivaldybiu_1997.sitemap import DEFAULT_SITEMAP_PATH, ELECTION_ID
from scraper.shared.savivaldybiu_archive_1997 import parse_anketa_samples as _parse_anketa_samples

DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")
# Elected status, joined in from VRK's results pages when the file exists;
# see `results.py`.
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def parse_anketa_samples(
    candidate_ids: list[str] | None = None,
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    results_path: Path | None = DEFAULT_RESULTS_PATH,
) -> list[dict[str, Any]]:
    return _parse_anketa_samples(
        ELECTION_ID,
        candidate_ids,
        sitemap_path=sitemap_path,
        samples_root=samples_root,
        output_root=output_root,
        results_path=results_path,
    )
