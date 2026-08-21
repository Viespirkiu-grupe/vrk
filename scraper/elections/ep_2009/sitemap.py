from __future__ import annotations

from pathlib import Path

# The 2009 European Parliament election (VRK election 404) is the 2014 EP
# listing one revision earlier and the same shape: an index of the party
# lists (number, name, declared candidate count), each linking a
# RinkimuOrganizacija<ID>.html page of candidates in list order, no
# constituencies. The 2014 module's index-and-list walk runs with this
# module's constants.
from scraper.elections.ep_2014.sitemap import (
    build_sitemap_from_sample as _build_sitemap_from_sample,
    fetch_listing_sample as _fetch_listing_sample,
)
from scraper.elections.seimo_zirmunu_2015.sitemap import resolve_candidate_url

ELECTION_ID = "2009-ep"
LISTING_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/404_lt/KandidatuSarasai/index.html"

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

__all__ = [
    "ELECTION_ID",
    "LISTING_URL",
    "build_sitemap_from_sample",
    "fetch_listing_sample",
    "resolve_candidate_url",
]


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    return _fetch_listing_sample(samples_dir=samples_dir, listing_url=LISTING_URL)


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    return _build_sitemap_from_sample(
        sample_path=sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR,
        output_path=output_path,
        election_id=ELECTION_ID,
        listing_url=LISTING_URL,
    )
