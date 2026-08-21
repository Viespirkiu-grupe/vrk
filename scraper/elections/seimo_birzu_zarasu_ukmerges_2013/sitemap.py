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

ELECTION_ID = "2013-kovo-3-seimo-birzai-zarasai-ukmerge"
# VRK election 421: the 2012 general election's results were annulled in
# Biržų-Kupiškio (No. 48) and Zarasų-Visagino (No. 52), and Ukmergės (No. 61)
# fell vacant, so all three voted again on one day. The pages are the
# pre-2016 static layout family; unlike the single-district 2015 by-elections
# the entry point is an index of constituencies, each with its own candidate
# page, so the sitemap walks the index rather than one listing.
LISTING_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/421_lt/Kandidatai/index.html"

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

FETCH_PAUSE_SECONDS = 0.3

CANDIDATE_ANKETA_PATTERN = re.compile(r"Kandidato(\d+)Anketa\.html$")
DISTRICT_LINK_PATTERN = re.compile(r"KandidataiApygardos(\d+)\.html$")


def _district_sample_path(samples_dir: Path, district_id: str) -> Path:
    return samples_dir / "districts" / f"district-{district_id}.html"


def extract_district_links(index_html: str) -> list[dict[str, Any]]:
    """The constituency index: "<number>. <a>Name</a>" entries under dl.electionarea."""
    soup = BeautifulSoup(index_html, "lxml")
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        match = DISTRICT_LINK_PATTERN.search(href)
        if match is None:
            continue
        district_id = match.group(1)
        if district_id in seen:
            continue
        seen.add(district_id)
        container = anchor.parent if isinstance(anchor.parent, Tag) else None
        container_text = normalize_space(container.get_text(" ", strip=True)) if container else ""
        number_match = re.match(r"^(\d+)\.", container_text)
        links.append(
            {
                "districtId": district_id,
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "number": int(number_match.group(1)) if number_match else None,
                "url": resolve_candidate_url(href),
            }
        )
    return links


def fetch_listing_sample(
    samples_dir: Path = DEFAULT_SAMPLES_DIR,
    listing_url: str = LISTING_URL,
) -> Path:
    # Fetches the constituency index and every constituency's candidate page,
    # skipping files already on disk so an interrupted capture resumes.
    samples_dir.mkdir(parents=True, exist_ok=True)
    index_path = samples_dir / "list.html"
    if index_path.exists():
        index_html = index_path.read_text(encoding="utf-8")
    else:
        index_html = fetch_text(listing_url)
        index_path.write_text(index_html, encoding="utf-8")
        time.sleep(FETCH_PAUSE_SECONDS)

    for link in extract_district_links(index_html):
        district_path = _district_sample_path(samples_dir, link["districtId"])
        if district_path.exists():
            continue
        district_path.parent.mkdir(parents=True, exist_ok=True)
        district_path.write_text(fetch_text(link["url"]), encoding="utf-8")
        time.sleep(FETCH_PAUSE_SECONDS)

    return samples_dir


def _candidate_table(soup: BeautifulSoup) -> Tag | None:
    # The constituency page has the district-info card and the candidate
    # table; the candidate table is the one holding the anketa links.
    best_table = None
    best_count = 0
    for table in soup.find_all("table"):
        count = sum(
            1 for anchor in table.find_all("a", href=True) if CANDIDATE_ANKETA_PATTERN.search(anchor["href"])
        )
        if count > best_count:
            best_table, best_count = table, count
    return best_table


def district_records(district_html: str, district: dict[str, Any]) -> list[dict[str, Any]]:
    """The candidates of one constituency page: name, VRK id, nominator."""
    soup = BeautifulSoup(district_html, "lxml")
    table = _candidate_table(soup)
    records: list[dict[str, Any]] = []
    if table is None:
        return records

    heading = soup.find("h3")
    heading_text = normalize_space(heading.get_text(" ", strip=True)) if heading else ""

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        anchor = None
        for candidate in tr.find_all("a", href=True):
            if CANDIDATE_ANKETA_PATTERN.search(candidate["href"]):
                anchor = candidate
                break
        if anchor is None:
            continue
        match = CANDIDATE_ANKETA_PATTERN.search(anchor["href"])
        nominated_by = normalize_space(cells[1].get_text(" ", strip=True)) if len(cells) > 1 else ""
        records.append(
            {
                "vrkCandidateId": match.group(1) if match else "",
                "candidateName": clean_candidate_name(anchor.get_text(" ", strip=True)),
                "url": resolve_candidate_url(normalize_space(anchor["href"])),
                "district": {
                    "pavadinimas": district["name"],
                    "numeris": district["number"],
                    "apygardosId": district["districtId"],
                    "antraste": heading_text,
                },
                "nominatedBy": nominated_by,
            }
        )
    return records


def collect_district_records(samples_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index_html = (samples_dir / "list.html").read_text(encoding="utf-8")
    districts = extract_district_links(index_html)
    records: list[dict[str, Any]] = []
    for district in districts:
        district_path = _district_sample_path(samples_dir, district["districtId"])
        records.extend(district_records(district_path.read_text(encoding="utf-8"), district))
    return districts, records


def assign_positional_ids(entries: list[dict[str, Any]]) -> int:
    """Name-slug ids, disambiguated by traversal position as the 2016 Seimo
    module does; returns the number of slugs that collided."""
    base_counter: Counter[str] = Counter(entry["candidateId"] for entry in entries)
    seen_counter: Counter[str] = Counter()
    for entry in entries:
        base_id = entry["candidateId"]
        seen_counter[base_id] += 1
        if base_counter[base_id] > 1 and seen_counter[base_id] > 1:
            entry["candidateId"] = f"{base_id}-{seen_counter[base_id]}"
    return sum(1 for _, count in base_counter.items() if count > 1)


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
    election_id: str = ELECTION_ID,
    listing_url: str = LISTING_URL,
) -> tuple[Path, dict[str, int]]:
    # sample_path keeps the CLI's signature; it names the samples directory.
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    districts, records = collect_district_records(samples_dir)

    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_vrk_ids: set[str] = set()
    for record in records:
        if not record["vrkCandidateId"]:
            skipped.append({"reason": "missing-vrk-id", "candidateName": record["candidateName"]})
            continue
        if record["vrkCandidateId"] in seen_vrk_ids:
            # One VRK id is one candidacy here; a repeat would be a listing
            # defect worth seeing, not merging.
            skipped.append({"reason": "duplicate-vrk-id", "vrkCandidateId": record["vrkCandidateId"]})
            continue
        seen_vrk_ids.add(record["vrkCandidateId"])
        candidate_id = slugify(record["candidateName"])
        if not candidate_id:
            skipped.append({"reason": "bad-candidate-id", "candidateName": record["candidateName"]})
            continue
        entries.append(
            {
                "candidateName": record["candidateName"],
                "candidateId": candidate_id,
                "url": record["url"],
                "vrkCandidateId": record["vrkCandidateId"],
                "roles": ["vienmandate"],
                "vienmandateCandidacy": {
                    "apygarda": record["district"]["pavadinimas"],
                    "apygardosNumeris": record["district"]["numeris"],
                    "apygardosId": record["district"]["apygardosId"],
                    "iskele": record["nominatedBy"] or None,
                },
            }
        )

    duplicate_candidate_ids = assign_positional_ids(entries)

    payload = {
        "electionId": election_id,
        "sourceUrl": listing_url,
        "districtUrls": [district["url"] for district in districts],
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": len(records),
            "extracted": len(entries),
            "skipped": len(skipped),
            "duplicateCandidateIds": duplicate_candidate_ids,
            "districts": len(districts),
        },
        "entries": entries,
        "skipped": skipped,
    }
    write_json(output_path, payload)

    stats = {
        "rows": len(records),
        "extracted": len(entries),
        "skipped": len(skipped),
        "duplicate_candidate_ids": duplicate_candidate_ids,
        "districts": len(districts),
    }
    return output_path, stats
