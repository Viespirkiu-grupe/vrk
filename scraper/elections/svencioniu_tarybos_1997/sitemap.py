"""Sitemap building for the 1997-06-29 Švenčionys district council repeat
election.

VRK re-ran the March 1997 municipal council vote in one municipality --
Švenčionių rajono (No. 47) -- after invalidating the original result there.
Both elections' candidate lists live under the same `19970323` directory and
the same municipality number, distinguished only by phase prefix: the March
general election is phase `3` (`apgtl.htm-3+47.htm`, filed May 1997), the
June repeat is phase `5` (`apgtl.htm-5+47.htm`, filed May 20-23 1997 --
confirmed by diffing the two pages, which differ only in filing dates and
candidate rosters, not in page shape). The candidate pages are the 1997
municipal archive layout (`scraper/shared/savivaldybiu_archive_1997.py`).
"""

from __future__ import annotations

from pathlib import Path

from scraper.shared.savivaldybiu_archive_1997 import (
    build_sitemap_from_target_samples,
    fetch_listing_sample_for_targets,
    municipality_url,
)

ELECTION_ID = "1997-birzelio-29-svenciniu-tarybos-pakartotiniai"
PHASE = "5"
MUNICIPALITIES = [47]

DEFAULT_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/list.html")
DEFAULT_MUNICIPALITIES_DIR = Path(f"samples/html/{ELECTION_ID}/municipalities")
DEFAULT_LISTS_DIR = Path(f"samples/html/{ELECTION_ID}/lists")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

TARGETS = [
    {"municipality": number, "url": municipality_url(PHASE, number)} for number in MUNICIPALITIES
]


def fetch_listing_sample(sample_path: Path = DEFAULT_SAMPLE_PATH) -> Path:
    return fetch_listing_sample_for_targets(
        TARGETS, sample_path, DEFAULT_MUNICIPALITIES_DIR, DEFAULT_LISTS_DIR
    )


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    del sample_path  # unused: see fetch_listing_sample's docstring
    return build_sitemap_from_target_samples(
        DEFAULT_MUNICIPALITIES_DIR,
        DEFAULT_LISTS_DIR,
        output_path,
        election_id=ELECTION_ID,
        source_description="Švenčionių rajono (47) municipality repeat, phase 5",
    )
