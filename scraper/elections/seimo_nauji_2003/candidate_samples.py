from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup

from scraper.elections.seimo_nauji_2003.sitemap import ELECTION_ID, resolve_candidate_url
from scraper.elections.seimo_zirmunu_2015.candidate_samples import (
    fetch_candidates_with_tabs as _fetch_candidates_with_tabs,
    fetch_first_candidate_with_tabs as _fetch_first_candidate_with_tabs,
    normalize_space,
)

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")

# A 2003 candidate is the same three static pages as a 2004 one, under the
# servlet's own file stems: the questionnaire
# (`w3_smn_kand.kand_anketa_l-id=<ID>.htm`), the free-text autobiography
# (`kand_biog_l-id=`) and the income-and-asset declaration extract
# (`kand_pajam_l-id=`), which the card links as "Autobiografija" and
# "Pajamų deklaracija". No tab bar, no private-interest declaration and no
# campaign page; all 27 candidates have all three.
SUBPAGE_LINK_PATTERN = re.compile(r"kand_(biog|pajam)_l-id=(\d+)\.htm$")
SUBPAGE_SLUGS = {
    "biog": "biografija",
    "pajam": "turto-ir-pajamu-deklaracijos",
}

EXPECTED_TABS = {"anketa", "biografija", "turto-ir-pajamu-deklaracijos"}

__all__ = [
    "EXPECTED_TABS",
    "extract_tab_links",
    "fetch_candidates_with_tabs",
    "fetch_first_candidate_with_tabs",
]


def extract_tab_links(candidate_html: str, candidate_url: str) -> list[dict[str, str]]:
    """The questionnaire itself plus the two sub-pages its card links,
    in the era fetcher's shape (the anketa entry carries the page's own
    URL, which the fetcher recognises and does not fetch twice)."""
    soup = BeautifulSoup(candidate_html, "lxml")
    links: list[dict[str, str]] = [
        {"label": "Anketa", "slug": "anketa", "url": candidate_url},
    ]
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        match = SUBPAGE_LINK_PATTERN.search(href)
        if match is None:
            continue
        slug = SUBPAGE_SLUGS[match.group(1)]
        if slug in seen:
            continue
        seen.add(slug)
        links.append(
            {
                "label": normalize_space(anchor.get_text(" ", strip=True)),
                "slug": slug,
                "url": resolve_candidate_url(href),
            }
        )
    return links


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
