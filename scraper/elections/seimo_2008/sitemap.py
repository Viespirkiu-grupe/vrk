from __future__ import annotations

from pathlib import Path

# The 2008 Seimo general election (VRK election 400) is the 2012 general
# election's two-structure listing one term earlier: an index of the 16
# numbered party and coalition lists (each a page of candidates in list
# order, with the constituency each also stood in) and an index of the 71
# single-member constituencies (each a page of candidates with the
# nominator), merged on VRK's candidate id. The 2012 module's walk runs
# with this module's URLs; two things in it were generalised for 2008: the
# coalition list page links its member parties' plain list pages (2012
# appends "_3"), and the index has no "Išsikėlę" page, so the self-nominated
# are accounted for from the constituency pages' own "Išsikėlė pats" rows
# in the district-only reconciliation.
from scraper.elections.seimo_2012.sitemap import (
    build_sitemap_from_sample as _build_sitemap_from_sample,
    fetch_listing_sample as _fetch_listing_sample,
)
from scraper.elections.seimo_zirmunu_2015.sitemap import resolve_candidate_url

ELECTION_ID = "2008-seimo"
LISTING_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/400_lt/KandidatuSarasai/index.html"
DISTRICTS_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/400_lt/Kandidatai/index.html"

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

__all__ = [
    "ELECTION_ID",
    "LISTING_URL",
    "DISTRICTS_URL",
    "build_sitemap_from_sample",
    "fetch_listing_sample",
    "resolve_candidate_url",
]


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    return _fetch_listing_sample(
        samples_dir=samples_dir, listing_url=LISTING_URL, districts_url=DISTRICTS_URL
    )


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    return _build_sitemap_from_sample(
        sample_path=sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR,
        output_path=output_path,
        election_id=ELECTION_ID,
        listing_url=LISTING_URL,
        districts_url=DISTRICTS_URL,
    )
