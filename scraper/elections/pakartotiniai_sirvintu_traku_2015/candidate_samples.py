from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.pakartotiniai_sirvintu_traku_2015.sitemap import ELECTION_ID
from scraper.elections.seimo_zirmunu_2015.candidate_samples import (
    fetch_candidates_with_tabs as _fetch_candidates_with_tabs,
    fetch_first_candidate_with_tabs as _fetch_first_candidate_with_tabs,
)

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")

# Only mayoral candidates publish a Biografija tab in this election; a
# council-only candidate's page legitimately carries four tabs. The expected
# set is therefore computed per candidate from the role the sitemap recorded —
# a flat five-tab set would warn about 312 of the 327 candidates.
BASE_EXPECTED_TABS = {
    "anketa",
    "turto-ir-pajamu-deklaracijos",
    "interesu-deklaracija",
    "kita",
}
MAYORAL_EXPECTED_TABS = BASE_EXPECTED_TABS | {"biografija"}


def expected_tabs_for_entry(entry: dict[str, Any]) -> set[str]:
    roles = entry.get("roles")
    if isinstance(roles, list) and "meras" in roles:
        return MAYORAL_EXPECTED_TABS
    return BASE_EXPECTED_TABS

__all__ = [
    "BASE_EXPECTED_TABS",
    "MAYORAL_EXPECTED_TABS",
    "expected_tabs_for_entry",
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
        expected_tabs=expected_tabs_for_entry,
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
        expected_tabs=expected_tabs_for_entry,
    )
