from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.prezidento_2009.sitemap import ELECTION_ID
from scraper.elections.seimo_zirmunu_2015.candidate_samples import (
    EXPECTED_TABS as _ERA_EXPECTED_TABS,
    fetch_candidates_with_tabs as _fetch_candidates_with_tabs,
    fetch_first_candidate_with_tabs as _fetch_first_candidate_with_tabs,
)

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")

# The presidential pages add a sixth tab, the candidate's trustees
# ("Patikėtiniai"), to the era's five — the link is on every 2009 page as it
# is on every 2014 one, but here the file behind it was never published:
# all seven Kandidato<ID>Patiketiniai.html URLs answer 404 (probed
# 2026-08-22; 2014's still resolve), and no other page of the election
# carries the trustees. The link is recorded as an unpublished tab, not
# fetched, and not expected, so the record simply has no `patiketiniai`
# block.
EXPECTED_TABS = set(_ERA_EXPECTED_TABS)
UNPUBLISHED_TABS = {"patiketiniai"}

__all__ = [
    "EXPECTED_TABS",
    "UNPUBLISHED_TABS",
    "fetch_first_candidate_with_tabs",
    "fetch_candidates_with_tabs",
]


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
        unpublished_tabs=UNPUBLISHED_TABS,
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
        unpublished_tabs=UNPUBLISHED_TABS,
    )
