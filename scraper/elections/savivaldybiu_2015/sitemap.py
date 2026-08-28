from __future__ import annotations

import errno
import json
from pathlib import Path
import re
import time
from typing import Any

from bs4 import BeautifulSoup

from scraper.elections.pakartotiniai_sirvintu_traku_2015.sitemap import (
    CANDIDATE_ANKETA_PATTERN,
    build_sitemap_from_sample as _build_sitemap_from_sample,
    fetch_listing_sample as _fetch_listing_sample,
    resolve_candidate_url,
)
from scraper.elections.seimo_zirmunu_2015.sitemap import normalize_space
from scraper.shared.municipal_sitemap import build_candidate_id
from scraper.shared.files import write_json
from scraper.shared.http import fetch_text

ELECTION_ID = "2015-kovo-1-savivaldybiu"

# The first direct mayoral election, held with the council vote. Unlike the
# 2019 and 2023 municipal generals — which publish one flat index of party
# lists — 2015 publishes a per-municipality district page, and the lists hang
# off those. That is the shape the 2015 repeat elections already walk, so this
# module discovers the 60 district pages and reuses their machinery rather
# than scraper/shared/municipal_sitemap.py, whose URL grammar, table ids and
# blue-anchor elected detection all belong to the 2019/2023 pages.
INDEX_URL = (
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/440_lt/Kandidatai/index.html"
)
# VRK's own roll-up of every mayoral candidate, used only to cross-check the
# mayoral count the district walk produces.
MERAI_URL = (
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/440_lt/Kandidatai/KandidataiMerai.html"
)

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

INDEX_SAMPLE_NAME = "index.html"
MERAI_SAMPLE_NAME = "merai.html"

DISTRICT_LINK_PATTERN = re.compile(r"KandidataiApygardos\d+\.html$")

FETCH_PAUSE_SECONDS = 0.3


def extract_district_urls(index_html: str) -> list[str]:
    soup = BeautifulSoup(index_html, "lxml")
    urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        if not DISTRICT_LINK_PATTERN.search(href):
            continue
        url = resolve_candidate_url(href)
        if url not in urls:
            urls.append(url)
    return urls


def _read_district_urls(samples_dir: Path) -> list[str]:
    index_path = samples_dir / INDEX_SAMPLE_NAME
    if not index_path.exists():
        raise FileNotFoundError(
            errno.ENOENT,
            "Missing municipality index sample (run fetch-sample first)",
            str(index_path),
        )
    return extract_district_urls(index_path.read_text(encoding="utf-8"))


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    samples_dir.mkdir(parents=True, exist_ok=True)

    index_path = samples_dir / INDEX_SAMPLE_NAME
    if index_path.exists():
        index_html = index_path.read_text(encoding="utf-8")
    else:
        index_html = fetch_text(INDEX_URL)
        index_path.write_text(index_html, encoding="utf-8")
        time.sleep(FETCH_PAUSE_SECONDS)

    merai_path = samples_dir / MERAI_SAMPLE_NAME
    if not merai_path.exists():
        merai_path.write_text(fetch_text(MERAI_URL), encoding="utf-8")
        time.sleep(FETCH_PAUSE_SECONDS)

    district_urls = extract_district_urls(index_html)
    return _fetch_listing_sample(samples_dir=samples_dir, district_urls=district_urls)


def _mayoral_listing_ids(samples_dir: Path) -> set[str]:
    merai_path = samples_dir / MERAI_SAMPLE_NAME
    if not merai_path.exists():
        return set()
    soup = BeautifulSoup(merai_path.read_text(encoding="utf-8"), "lxml")
    ids: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = CANDIDATE_ANKETA_PATTERN.search(normalize_space(anchor["href"]))
        if match:
            ids.add(match.group(1))
    return ids


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    district_urls = _read_district_urls(samples_dir)

    written_path, stats = _build_sitemap_from_sample(
        sample_path=samples_dir,
        output_path=output_path,
        election_id=ELECTION_ID,
        district_urls=district_urls,
        # 140 of the 15,149 candidates share a name slug with someone else, so
        # the id carries VRK's own candidate id rather than a positional
        # suffix that would depend on traversal order — the batch runner uses
        # the output filename as its resume marker.
        candidate_id_builder=build_candidate_id,
    )

    # Cross-check the district walk against VRK's own roll-up of mayoral
    # candidates before trusting anything downstream: the walk should find
    # exactly the people that page links, and any difference is a listing the
    # walk missed or a person the roll-up omits.
    payload = json.loads(written_path.read_text(encoding="utf-8"))
    walked_mayoral = {
        entry["vrkCandidateId"] for entry in payload["entries"] if "meras" in entry["roles"]
    }
    listing_mayoral = _mayoral_listing_ids(samples_dir)

    payload["stats"]["municipalities"] = len(district_urls)
    payload["stats"]["mayoralListingCandidates"] = len(listing_mayoral)
    payload["stats"]["mayoralOnlyInListing"] = len(listing_mayoral - walked_mayoral)
    payload["stats"]["mayoralOnlyInDistrictWalk"] = len(walked_mayoral - listing_mayoral)
    payload["sourceUrl"] = INDEX_URL
    payload["mayoralListingUrl"] = MERAI_URL
    write_json(written_path, payload)

    stats = dict(stats)
    stats["municipalities"] = len(district_urls)
    stats["mayoral_listing_candidates"] = len(listing_mayoral)
    stats["mayoral_only_in_listing"] = len(listing_mayoral - walked_mayoral)
    stats["mayoral_only_in_district_walk"] = len(walked_mayoral - listing_mayoral)
    return written_path, stats
