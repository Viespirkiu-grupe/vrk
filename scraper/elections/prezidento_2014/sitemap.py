from __future__ import annotations

from pathlib import Path

# The 2014 presidential election (VRK election 424) is the pre-2016 static
# layout family: separate static files per candidate tab, the
# "Kandidato<ID>Anketa.html" link stem, JPG photo sidecars. The listing is a
# single table of the seven candidates — each row links the anketa twice,
# from the name and from a "Plačiau" link, and the era's row walker takes the
# first — so the March 2015 Žirmūnai machinery runs with this module's
# constants.
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    build_sitemap_from_sample as _build_sitemap_from_sample,
    fetch_listing_sample as _fetch_listing_sample,
    resolve_candidate_url,
)

ELECTION_ID = "2014-prezidento"
LISTING_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/424_lt/Kandidatai/index.html"

DEFAULT_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/list.html")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

__all__ = [
    "ELECTION_ID",
    "LISTING_URL",
    "build_sitemap_from_sample",
    "fetch_listing_sample",
    "resolve_candidate_url",
]


def fetch_listing_sample(sample_path: Path = DEFAULT_SAMPLE_PATH) -> Path:
    return _fetch_listing_sample(sample_path=sample_path, listing_url=LISTING_URL)


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    if sample_path is None:
        sample_path = DEFAULT_SAMPLE_PATH
    return _build_sitemap_from_sample(
        sample_path=sample_path,
        output_path=output_path,
        election_id=ELECTION_ID,
        listing_url=LISTING_URL,
    )
