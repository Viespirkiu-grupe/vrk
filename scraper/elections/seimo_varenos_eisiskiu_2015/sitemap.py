from __future__ import annotations

from pathlib import Path

# The pages are the same pre-2016 static layout as the March 2015 Žirmūnai
# by-election, election 459 instead of 448; the machinery is reused with this
# module's constants rather than restated.
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    build_sitemap_from_sample as _build_sitemap_from_sample,
    fetch_listing_sample as _fetch_listing_sample,
    resolve_candidate_url,
)

ELECTION_ID = "2015-birzelio-7-seimo-varena-eisiskes"
LISTING_URL = (
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/459_lt"
    "/Apygardos/Apygarda7925/KandidataiApygardos7925.html"
)

DEFAULT_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/list.html")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")


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
