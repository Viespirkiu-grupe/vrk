"""Sitemap building for the 1997-12-21 Seimo repeat election.

VRK re-ran the vote in one constituency -- Aukštaitijos (No. 28) -- named
explicitly on the `seimpk` by-elections index page
(https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seimpk/index.html#1997).
The candidate page is the same 1996-1998 Seimas archive layout
(`scraper/shared/seimo_archive_1990s.py`), under the `seimpk` directory and
phase prefix `7` (`apgtl.htm-7+28.htm`).
"""

from __future__ import annotations

from pathlib import Path

from scraper.shared.seimo_archive_1990s import (
    build_sitemap_from_targets,
    constituency_url,
    fetch_listing_sample_for_targets,
)

ELECTION_ID = "1997-gruodzio-21-seimo-pakartotiniai"
DIRECTORY = "seimpk"
PHASE = "7"
CONSTITUENCIES = [28]

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
            "Aukštaitijos (28) constituency, named on "
            "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seimpk/index.html#1997"
        ),
    )
