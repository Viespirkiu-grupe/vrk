"""Candidate sample fetching for the 2002-12-22 municipal general.

A 2002 candidate is two static pages keyed by ``asm_kod``: the anketa
(``kandidatai_anketa_jsp_ri_id_15_asm_kod_<ID>.htm``) and the income
and asset declaration extract
(``kandidatai_deklaracija_jsp_ri_id_15_asm_kod_<ID>.htm``, "Lietuvos
Respublikos gyventojo turto ir pajamų deklaracija"), each linking the
other. There is no biography, no private-interest declaration and no
campaign page on this site generation. The declaration is saved under
the corpus's usual ``turto-ir-pajamu-deklaracijos.html`` name so the
record's sections keep their cross-era keys.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from scraper.elections.savivaldybiu_2002.sitemap import (
    DEFAULT_SITEMAP_PATH,
    DEKLARACIJA_PAGE_PATTERN,
    ELECTION_ID,
    resolve_site_url,
)
from scraper.elections.seimo_zirmunu_2015.candidate_samples import (
    fetch_candidates_with_tabs as _fetch_candidates_with_tabs,
    fetch_first_candidate_with_tabs as _fetch_first_candidate_with_tabs,
    normalize_space,
)

DEFAULT_SAMPLES_ROOT = Path(f"samples/html/{ELECTION_ID}")

EXPECTED_TABS = {"anketa", "turto-ir-pajamu-deklaracijos"}

__all__ = [
    "EXPECTED_TABS",
    "extract_tab_links",
    "fetch_candidates_with_tabs",
    "fetch_first_candidate_with_tabs",
]


def extract_tab_links(candidate_html: str, candidate_url: str) -> list[dict[str, str]]:
    """The anketa itself plus the declaration page it links.

    Returned in the era fetcher's shape so the index.json and the saved
    file names match every other election's; the anketa entry carries
    the page's own URL, which the fetcher recognises and does not fetch
    twice.
    """
    soup = BeautifulSoup(candidate_html, "lxml")
    links: list[dict[str, str]] = [
        {"label": "Anketa", "slug": "anketa", "url": candidate_url},
    ]
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        if DEKLARACIJA_PAGE_PATTERN.search(href) is None:
            continue
        links.append(
            {
                "label": normalize_space(anchor.get_text(" ", strip=True)),
                "slug": "turto-ir-pajamu-deklaracijos",
                "url": resolve_site_url(href),
            }
        )
        break
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
