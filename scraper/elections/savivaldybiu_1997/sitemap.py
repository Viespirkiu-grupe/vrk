"""Sitemap building for the 1997-03-23 municipal council general election.

The candidate pages are the 1997 municipal archive layout (see
`scraper/shared/savivaldybiu_archive_1997.py`): a directory page enumerates
all 56 municipalities, each municipality page lists the parties/coalitions
fielding candidates there, and each party links one hop deeper to its
numbered candidate list. This module supplies the directory URL and the
directory-parsing loop; the shared module does the actual page parsing and
the three-hop crawl.
"""

from __future__ import annotations

from pathlib import Path

from scraper.shared.http import fetch_text
from scraper.shared.savivaldybiu_archive_1997 import (
    build_sitemap_from_target_samples,
    fetch_municipality_samples,
    fetch_party_list_samples,
    parse_municipality_directory,
)

ELECTION_ID = "1997-kovo-23-savivaldybiu-tarybu"
DIRECTORY_URL = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/19970323/apgsavl.htm-3.htm"

DEFAULT_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/list.html")
DEFAULT_MUNICIPALITIES_DIR = Path(f"samples/html/{ELECTION_ID}/municipalities")
DEFAULT_LISTS_DIR = Path(f"samples/html/{ELECTION_ID}/lists")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")


def fetch_listing_sample(sample_path: Path = DEFAULT_SAMPLE_PATH) -> Path:
    html = fetch_text(DIRECTORY_URL)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(html, encoding="utf-8")

    directory_entries = parse_municipality_directory(html, DIRECTORY_URL)
    targets = [
        {"municipality": entry["municipalityNumber"], "url": entry["url"]}
        for entry in directory_entries
    ]
    municipality_sample_paths = fetch_municipality_samples(targets, DEFAULT_MUNICIPALITIES_DIR)
    fetch_party_list_samples(municipality_sample_paths, DEFAULT_LISTS_DIR)
    return sample_path


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    del sample_path  # the directory sample only names the municipalities;
    # the per-municipality and per-party-list samples already saved by
    # fetch_listing_sample are what actually gets read back here.
    return build_sitemap_from_target_samples(
        DEFAULT_MUNICIPALITIES_DIR,
        DEFAULT_LISTS_DIR,
        output_path,
        election_id=ELECTION_ID,
        source_description=f"56 municipalities from {DIRECTORY_URL}",
    )
