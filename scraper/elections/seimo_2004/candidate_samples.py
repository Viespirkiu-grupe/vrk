from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.ep_2004.candidate_samples import (
    EXPECTED_TABS,
    extract_tab_links,
)
from scraper.elections.seimo_2004.sitemap import ELECTION_ID
from scraper.elections.seimo_zirmunu_2015.candidate_samples import (
    fetch_candidates_with_tabs as _fetch_candidates_with_tabs,
    fetch_first_candidate_with_tabs as _fetch_first_candidate_with_tabs,
)

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")

# The same three pages as the 2004 EP candidate — questionnaire, biography,
# declaration extracts — under the same file stems; the card's fourth link,
# an independent campaign participant's registration decision (a PDF), is
# a card field, not a page.
__all__ = ["EXPECTED_TABS", "fetch_first_candidate_with_tabs", "fetch_candidates_with_tabs"]


def fetch_first_candidate_with_tabs(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    return _fetch_first_candidate_with_tabs(
        sitemap_path=sitemap_path,
        samples_root=samples_root,
        allow_new_candidate_dir=allow_new_candidate_dir,
        election_id=ELECTION_ID,
        expected_tabs=EXPECTED_TABS,
        tab_links_extractor=extract_tab_links,
    )


def fetch_candidates_with_tabs(
    candidate_ids: list[str],
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    samples_root: Path = DEFAULT_SAMPLES_ROOT,
    allow_new_candidate_dir: bool = False,
) -> dict[str, Any]:
    return _fetch_candidates_with_tabs(
        candidate_ids=candidate_ids,
        sitemap_path=sitemap_path,
        samples_root=samples_root,
        allow_new_candidate_dir=allow_new_candidate_dir,
        election_id=ELECTION_ID,
        expected_tabs=EXPECTED_TABS,
        tab_links_extractor=extract_tab_links,
    )
