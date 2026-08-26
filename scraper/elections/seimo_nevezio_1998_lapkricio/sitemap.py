"""Sitemap building for the 1998-11-15 Seimo repeat election.

VRK re-ran the vote in one constituency -- Nevėžio (No. 26) -- named
explicitly on the `seimpk` by-elections index page
(https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seimpk/index.html), which
also links the first-round results and the VRK decision ending Mečys
Laurinkus's mandate that occasioned the re-run. The candidate page is the same
1996-1998 Seimas archive layout (`scraper/shared/seimo_archive_1990s.py`),
under the `seimpk` directory and phase prefix `10` (`apgtl.htm-10+26.htm`).

The re-run failed too: `rapgpl.htm-392+1.htm` records 11,651 of 38,358 voters
(30.37%) and closes "Rinkimai apygardoje neįvyko." So no candidate here was
elected -- but this family publishes no elected marker on the pages it does
parse, and adding a results reader for it is a decision shared with the other
1998-1999 by-elections rather than one to take in a single module; see
`docs/DATASET.md`.
"""

from __future__ import annotations

from pathlib import Path

from scraper.shared.seimo_archive_1990s import (
    build_sitemap_from_targets,
    constituency_url,
    fetch_listing_sample_for_targets,
)

ELECTION_ID = "1998-lapkricio-15-seimo-pakartotiniai"
DIRECTORY = "seimpk"
PHASE = "10"
CONSTITUENCIES = [26]

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
            "Nevėžio (26) constituency, named on "
            "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seimpk/index.html"
        ),
    )
