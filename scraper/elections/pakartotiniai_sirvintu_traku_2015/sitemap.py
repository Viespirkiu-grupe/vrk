from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import time
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.seimo_zirmunu_2015.sitemap import (
    clean_candidate_name,
    normalize_space,
    resolve_candidate_url,
    utc_now_iso,
)
from scraper.shared.files import slugify, write_json
from scraper.shared.http import fetch_text

ELECTION_ID = "2015-birzelio-7-pakartotiniai-sirvintos-trakai"
# One VRK election (452) across two districts with different shapes: Širvintos
# repeated only the member-mayor vote, Trakai both the mayor and the council.
# The district ids are counterintuitive — 7911 is Trakai, 7921 Širvintos.
DISTRICT_URLS = [
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/452_lt"
    "/Apygardos/Apygarda7921/KandidataiApygardos7921.html",
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/452_lt"
    "/Apygardos/Apygarda7911/KandidataiApygardos7911.html",
]

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

FETCH_PAUSE_SECONDS = 0.3

CANDIDATE_ANKETA_PATTERN = re.compile(r"Kandidato(\d+)Anketa\.html$")
PARTY_LIST_LINK_PATTERN = re.compile(r"Apygarda(\d+)Partijos(\d+)Kandidatai\.html$")
DISTRICT_URL_ID_PATTERN = re.compile(r"KandidataiApygardos(\d+)\.html$")
# The dual-candidacy marker as the 2015 list pages spell it.
MAYOR_MARKER_PATTERN = re.compile(r"\(kandidatas į savivaldybės tarybos narius - merus\)")


def _district_id_from_url(url: str) -> str:
    match = DISTRICT_URL_ID_PATTERN.search(url)
    return match.group(1) if match else slugify(url)[-24:]


def _district_sample_path(samples_dir: Path, district_url: str) -> Path:
    return samples_dir / f"district-{_district_id_from_url(district_url)}.html"


def _list_sample_path(samples_dir: Path, list_url: str) -> Path:
    match = PARTY_LIST_LINK_PATTERN.search(list_url)
    if match:
        name = f"list-{match.group(1)}-{match.group(2)}.html"
    else:
        name = f"list-{slugify(list_url)[-40:]}.html"
    return samples_dir / "lists" / name


def _extract_party_list_links(soup: BeautifulSoup) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        if not PARTY_LIST_LINK_PATTERN.search(href):
            continue
        # The mayoral rows link the nominating party's list page too; only the
        # list-index rows carry the list number as text before the anchor.
        row_text = normalize_space(anchor.parent.get_text(" ", strip=True)) if anchor.parent else ""
        number_match = re.match(r"^(\d+)\s", row_text)
        if number_match is None:
            continue
        url = resolve_candidate_url(href)
        if url in seen:
            continue
        seen.add(url)
        links.append(
            {
                "url": url,
                "partyList": normalize_space(anchor.get_text(" ", strip=True)),
                "listNumber": int(number_match.group(1)),
            }
        )
    return links


def fetch_listing_sample(
    samples_dir: Path = DEFAULT_SAMPLES_DIR,
    district_urls: list[str] | None = None,
) -> Path:
    # Fetches every district page and every party-list page under it, skipping
    # files already on disk so an interrupted capture resumes.
    if district_urls is None:
        district_urls = DISTRICT_URLS

    samples_dir.mkdir(parents=True, exist_ok=True)
    for district_url in district_urls:
        district_path = _district_sample_path(samples_dir, district_url)
        if district_path.exists():
            html = district_path.read_text(encoding="utf-8")
        else:
            html = fetch_text(district_url)
            district_path.write_text(html, encoding="utf-8")
            time.sleep(FETCH_PAUSE_SECONDS)

        soup = BeautifulSoup(html, "lxml")
        for link in _extract_party_list_links(soup):
            list_path = _list_sample_path(samples_dir, link["url"])
            if list_path.exists():
                continue
            list_path.parent.mkdir(parents=True, exist_ok=True)
            list_path.write_text(fetch_text(link["url"]), encoding="utf-8")
            time.sleep(FETCH_PAUSE_SECONDS)

    return samples_dir


def _municipality_name(soup: BeautifulSoup) -> str:
    heading = soup.find("h3")
    return normalize_space(heading.get_text(" ", strip=True)) if heading else ""


def _mayoral_records(soup: BeautifulSoup, municipality: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        match = CANDIDATE_ANKETA_PATTERN.search(href)
        if match is None:
            continue
        cell = anchor.find_parent("td")
        row_text = normalize_space(cell.get_text(" ", strip=True)) if cell else ""
        raw_name = anchor.get_text(" ", strip=True)
        # Rows read "Name - iškėlė Party[, Party]" or "Name - išsikėlė pats".
        nominated_by = ""
        if " - " in row_text:
            nominated_by = row_text.split(" - ", 1)[1]
            if nominated_by.startswith("iškėlė "):
                nominated_by = nominated_by[len("iškėlė "):]
        records.append(
            {
                "vrkCandidateId": match.group(1),
                "candidateName": clean_candidate_name(raw_name),
                "url": resolve_candidate_url(href),
                "municipality": municipality,
                "nominatedBy": normalize_space(nominated_by),
            }
        )
    return records


def _council_records(
    list_html: str, link: dict[str, Any], municipality: str
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(list_html, "lxml")
    records: list[dict[str, Any]] = []
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        match = CANDIDATE_ANKETA_PATTERN.search(href)
        if match is None:
            continue
        cell = anchor.find_parent("td")
        row_text = normalize_space(cell.get_text(" ", strip=True)) if cell else ""
        position_match = re.match(r"^(\d+)\s", row_text)
        records.append(
            {
                "vrkCandidateId": match.group(1),
                "candidateName": clean_candidate_name(anchor.get_text(" ", strip=True)),
                "url": resolve_candidate_url(href),
                "municipality": municipality,
                "partyList": link["partyList"],
                "listNumber": link["listNumber"],
                "listPosition": int(position_match.group(1)) if position_match else None,
                "alsoMayoralCandidate": bool(MAYOR_MARKER_PATTERN.search(row_text)),
            }
        )
    return records


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
    election_id: str = ELECTION_ID,
    district_urls: list[str] | None = None,
) -> tuple[Path, dict[str, int]]:
    # sample_path keeps the CLI's signature; it names the samples directory.
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    if district_urls is None:
        district_urls = DISTRICT_URLS

    mayor_records: list[dict[str, Any]] = []
    council_records: list[dict[str, Any]] = []
    party_list_count = 0

    for district_url in district_urls:
        district_path = _district_sample_path(samples_dir, district_url)
        soup = BeautifulSoup(district_path.read_text(encoding="utf-8"), "lxml")
        municipality = _municipality_name(soup)

        mayor_records.extend(_mayoral_records(soup, municipality))

        for link in _extract_party_list_links(soup):
            party_list_count += 1
            list_path = _list_sample_path(samples_dir, link["url"])
            council_records.extend(
                _council_records(list_path.read_text(encoding="utf-8"), link, municipality)
            )

    # Merge on VRK's own candidate id — one entry carries both candidacies.
    entries_by_vrk_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def _entry_for(record: dict[str, Any]) -> dict[str, Any]:
        vrk_id = record["vrkCandidateId"]
        entry = entries_by_vrk_id.get(vrk_id)
        if entry is None:
            entry = {
                "candidateName": record["candidateName"],
                "candidateId": slugify(record["candidateName"]),
                "url": record["url"],
                "vrkCandidateId": vrk_id,
                "municipality": record["municipality"],
                "roles": [],
            }
            entries_by_vrk_id[vrk_id] = entry
            order.append(vrk_id)
        return entry

    for record in mayor_records:
        entry = _entry_for(record)
        if "meras" not in entry["roles"]:
            entry["roles"].append("meras")
        # No 2015 page marks the winner, so there is no elected flag to carry.
        entry["mayoralCandidacy"] = {
            "nominatedBy": record["nominatedBy"] or None,
        }

    for record in council_records:
        entry = _entry_for(record)
        if "tarybos-narys" not in entry["roles"]:
            entry["roles"].append("tarybos-narys")
        entry["councilCandidacy"] = {
            "partyList": record["partyList"],
            "listNumber": record["listNumber"],
            "listPosition": record["listPosition"],
        }

    entries = [entries_by_vrk_id[vrk_id] for vrk_id in order]

    # Name-slug ids stay unique at this scale; a duplicate gets the positional
    # suffix the small by-election modules use.
    base_counter: Counter[str] = Counter(entry["candidateId"] for entry in entries)
    seen_counter: Counter[str] = Counter()
    for entry in entries:
        base_id = entry["candidateId"]
        seen_counter[base_id] += 1
        if base_counter[base_id] > 1 and seen_counter[base_id] > 1:
            entry["candidateId"] = f"{base_id}-{seen_counter[base_id]}"
    duplicate_candidate_ids = sum(1 for _, count in base_counter.items() if count > 1)

    # The listing flags dual candidacies in prose; the id join must agree.
    marker_flagged = {
        record["vrkCandidateId"] for record in council_records if record["alsoMayoralCandidate"]
    }
    joined_dual = {entry["vrkCandidateId"] for entry in entries if len(entry["roles"]) > 1}
    marker_join_mismatch = len(marker_flagged.symmetric_difference(joined_dual))
    dual_candidates = sum(1 for entry in entries if len(entry["roles"]) > 1)

    payload = {
        "electionId": election_id,
        "sourceUrl": district_urls[0],
        "districtUrls": district_urls,
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": len(mayor_records) + len(council_records),
            "extracted": len(entries),
            "skipped": 0,
            "duplicateCandidateIds": duplicate_candidate_ids,
            "partyLists": party_list_count,
            "mayoralCandidates": len(mayor_records),
            "councilCandidates": len(council_records),
            "dualCandidates": dual_candidates,
            "markerJoinMismatch": marker_join_mismatch,
        },
        "entries": entries,
        "skipped": [],
    }
    write_json(output_path, payload)

    stats = {
        "rows": len(mayor_records) + len(council_records),
        "extracted": len(entries),
        "skipped": 0,
        "duplicate_candidate_ids": duplicate_candidate_ids,
        "party_lists": party_list_count,
        "mayoral_candidates": len(mayor_records),
        "council_candidates": len(council_records),
        "dual_candidates": dual_candidates,
        "marker_join_mismatch": marker_join_mismatch,
    }
    return output_path, stats
