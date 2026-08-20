from __future__ import annotations

from pathlib import Path

# Same two-structure listing as the June 7th repeat elections — a district page
# whose mayoral section and party-list index both hold candidates — so that
# module's walk and candidate-id merge are reused with this election's
# constants. One district here (457/Apygarda7923) instead of two.
from scraper.elections.pakartotiniai_sirvintu_traku_2015.sitemap import (
    build_sitemap_from_sample as _build_sitemap_from_sample,
    fetch_listing_sample as _fetch_listing_sample,
    resolve_candidate_url,
)

ELECTION_ID = "2015-birzelio-21-pakartotiniai-silutes"
DISTRICT_URLS = [
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/457_lt"
    "/Apygardos/Apygarda7923/KandidataiApygardos7923.html",
]

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    return _fetch_listing_sample(samples_dir=samples_dir, district_urls=DISTRICT_URLS)


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    if sample_path is None:
        sample_path = DEFAULT_SAMPLES_DIR
    return _build_sitemap_from_sample(
        sample_path=sample_path,
        output_path=output_path,
        election_id=ELECTION_ID,
        district_urls=DISTRICT_URLS,
    )
