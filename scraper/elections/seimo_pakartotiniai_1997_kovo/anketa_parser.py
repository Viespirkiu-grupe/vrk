"""Candidate record parsing for the 1997-03-23 Seimo repeat election."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_pakartotiniai_1997_kovo.candidate_samples import DEFAULT_SAMPLES_ROOT
from scraper.elections.seimo_pakartotiniai_1997_kovo.sitemap import DEFAULT_SITEMAP_PATH, ELECTION_ID
from scraper.shared.seimo_archive_1990s import parse_anketa_samples as _parse_anketa_samples

DEFAULT_OUTPUT_ROOT = Path(f"data/{ELECTION_ID}")


def parse_anketa_samples(
    candidate_ids: list[str] | None = None,
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> list[dict[str, Any]]:
    return _parse_anketa_samples(
        ELECTION_ID,
        candidate_ids,
        sitemap_path=sitemap_path,
        samples_root=samples_root,
        output_root=output_root,
    )
