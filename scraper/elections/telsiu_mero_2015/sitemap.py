from __future__ import annotations

from pathlib import Path

# Same pre-2016 static layout as the 2015 Seimo by-elections; the machinery is
# reused with this module's constants.
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    build_sitemap_from_sample as _build_sitemap_from_sample,
    fetch_listing_sample as _fetch_listing_sample,
    resolve_candidate_url,
)

ELECTION_ID = "2015-lapkricio-8-telsiu-mero"
# This election's static pages live under 2015_4_savivaldybiu_tarybu_rinkimai/,
# not the rinkimai/ base every other 2015 election uses.
LISTING_URL = (
    "https://www.vrk.lt/statiniai/puslapiai/2015_4_savivaldybiu_tarybu_rinkimai"
    "/469_lt/Apygardos/Apygarda7935/KandidataiApygardos7935.html"
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
