from __future__ import annotations

from pathlib import Path
import re

# The 2004 European Parliament election — Lithuania's first, one month after
# accession — is published on VRK's original static site
# (rinkimai/2004/euro/, the LRS-ITD page template), not on the 2015-era
# layout every later election of the corpus shares. The listing is still
# the index-and-lists shape the 2014 EP walker reads: an index of the 12
# party lists (VRK number, name, declared candidate count), each a page of
# candidates in list order, no constituencies. The walker runs with this
# tree's link patterns — the pages are `kand_part_l_<ID>.htm` and
# `kand_anketa_l_<ID>.htm` (the `_l_` is the Lithuanian version; an `_e_`
# English twin of every page exists and is not read).
from scraper.elections.ep_2014.sitemap import (
    build_sitemap_from_sample as _build_sitemap_from_sample,
    fetch_listing_sample as _fetch_listing_sample,
)
from scraper.elections.seimo_zirmunu_2015.sitemap import resolve_candidate_url

ELECTION_ID = "2004-ep"
LISTING_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/euro/kandidatai/part_sar_l_18.htm"

CANDIDATE_ANKETA_PATTERN = re.compile(r"kand_anketa_l_(\d+)\.htm$")
LIST_LINK_PATTERN = re.compile(r"kand_part_l_(\d+)\.htm$")

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

__all__ = [
    "CANDIDATE_ANKETA_PATTERN",
    "ELECTION_ID",
    "LISTING_URL",
    "LIST_LINK_PATTERN",
    "build_sitemap_from_sample",
    "fetch_listing_sample",
    "resolve_candidate_url",
]


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    return _fetch_listing_sample(
        samples_dir=samples_dir,
        listing_url=LISTING_URL,
        list_link_pattern=LIST_LINK_PATTERN,
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
        list_link_pattern=LIST_LINK_PATTERN,
        candidate_pattern=CANDIDATE_ANKETA_PATTERN,
    )
