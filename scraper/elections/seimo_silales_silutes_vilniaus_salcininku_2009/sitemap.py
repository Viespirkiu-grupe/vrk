from __future__ import annotations

from pathlib import Path

# VRK election 406: two Seimo seats fell vacant after the June 2009 European Parliament election took their holders (Šilalės–Šilutės No. 33, Vilniaus–Šalčininkų No. 56), and both voted again on one day. The pages are the pre-2016 static layout family and the entry
# point is an index of constituencies, each with its own candidate page —
# the March 2013 repeat election's shape exactly, so that module's
# index-driven walk runs with this module's constants.
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import (
    build_sitemap_from_sample as _build_sitemap_from_sample,
    fetch_listing_sample as _fetch_listing_sample,
)
from scraper.elections.seimo_zirmunu_2015.sitemap import resolve_candidate_url

ELECTION_ID = "2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai"
LISTING_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/406_lt/Kandidatai/index.html"

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
