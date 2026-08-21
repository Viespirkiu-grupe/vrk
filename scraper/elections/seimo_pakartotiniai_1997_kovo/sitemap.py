"""Sitemap building for the 1997-03-23 Seimo repeat election.

VRK re-ran the vote in four constituencies -- Naujosios Vilnios (No. 10),
Vilniaus-Šalčininkų (No. 56), Vilniaus-Trakų (No. 57), Trakų (No. 58) -- named
explicitly on the `seimpk` by-elections index page
(https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seimpk/index.html#1997).
No directory page covers only these four, so they are hardcoded here rather
than crawled from one (contrast `seimo_1996`, which crawls its directory
page since it covers the whole country). The candidate pages are the same
1996-1998 Seimas archive layout (`scraper/shared/seimo_archive_1990s.py`),
under the `seimpk` directory and phase prefix `4`
(`apgtl.htm-4+<constituency>.htm`).
"""

from __future__ import annotations

from pathlib import Path

from scraper.shared.seimo_archive_1990s import (
    build_sitemap_from_targets,
    constituency_url,
    fetch_listing_sample_for_targets,
)

ELECTION_ID = "1997-kovo-23-seimo-pakartotiniai"
DIRECTORY = "seimpk"
PHASE = "4"
CONSTITUENCIES = [10, 56, 57, 58]

DEFAULT_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/list.html")
DEFAULT_CONSTITUENCIES_DIR = Path(f"samples/html/{ELECTION_ID}/constituencies")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

TARGETS = [
    {"constituency": number, "url": constituency_url(DIRECTORY, PHASE, number)}
    for number in CONSTITUENCIES
]


def fetch_listing_sample(sample_path: Path = DEFAULT_SAMPLE_PATH) -> Path:
    return fetch_listing_sample_for_targets(TARGETS, sample_path, DEFAULT_CONSTITUENCIES_DIR)


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    del sample_path  # unused: see fetch_listing_sample's docstring
    return build_sitemap_from_targets(
        DEFAULT_CONSTITUENCIES_DIR,
        output_path,
        election_id=ELECTION_ID,
        source_description=(
            "Naujosios Vilnios (10), Vilniaus-Šalčininkų (56), Vilniaus-Trakų (57), "
            "Trakų (58) constituencies, named on "
            "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seimpk/index.html#1997"
        ),
    )
