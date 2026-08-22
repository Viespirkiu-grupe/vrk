from __future__ import annotations

from pathlib import Path
import re
import time
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import (
    assign_positional_ids,
)
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    clean_candidate_name,
    normalize_space,
    resolve_candidate_url,
    utc_now_iso,
)
from scraper.shared.files import slugify, write_json
from scraper.shared.http import fetch_text

ELECTION_ID = "2014-ep"
# VRK election 426, the pre-2016 static layout family. The entry point is an
# index of the party lists (number, name, candidate count), each linking a
# RinkimuOrganizacija<ID>.html page that lists the candidates in list order;
# there are no constituencies. The sitemap walks the index and every list.
LISTING_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/426_lt/KandidatuSarasai/index.html"

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

FETCH_PAUSE_SECONDS = 0.3

CANDIDATE_ANKETA_PATTERN = re.compile(r"Kandidato(\d+)Anketa\.html$")
LIST_LINK_PATTERN = re.compile(r"RinkimuOrganizacija(\d+)(?:_(\d+))?\.html$")


def _list_sample_path(samples_dir: Path, list_key: str) -> Path:
    return samples_dir / "lists" / f"list-{list_key}.html"


def _list_key(href: str, list_link_pattern: re.Pattern[str] = LIST_LINK_PATTERN) -> str:
    match = list_link_pattern.search(href)
    if match is None:
        return slugify(href)[-40:]
    return "-".join(group for group in match.groups() if group)


def extract_list_links(
    index_html: str,
    list_link_pattern: re.Pattern[str] = LIST_LINK_PATTERN,
) -> list[dict[str, Any]]:
    """The numbered list rows of the index: list number, name, declared count.

    Rows whose first cell is not a number are skipped — the 2012 Seimo index
    also lists coalition member parties ("koalicijos sąrašas Nr. 10") and
    single-member-only parties ("tik vienmandatėse") under the same table,
    and those are not lists of their own.

    The link patterns are parameters because the 2004 EP tree — the same
    index-and-lists shape on VRK's original static site — names its pages
    `kand_part_l_<ID>.htm` and `kand_anketa_l_<ID>.htm`.
    """
    soup = BeautifulSoup(index_html, "lxml")
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        anchor = None
        for candidate in tr.find_all("a", href=True):
            if list_link_pattern.search(candidate["href"]) and candidate.find_parent("tr") is tr:
                anchor = candidate
                break
        if anchor is None:
            continue
        number_text = normalize_space(cells[0].get_text(" ", strip=True))
        if not number_text.isdigit():
            continue
        href = normalize_space(anchor["href"])
        key = _list_key(href, list_link_pattern)
        if key in seen:
            continue
        seen.add(key)
        count_text = normalize_space(cells[-1].get_text(" ", strip=True)) if len(cells) > 2 else ""
        links.append(
            {
                "listKey": key,
                "listNumber": int(number_text),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "declaredCount": int(count_text) if count_text.isdigit() else None,
                "url": resolve_candidate_url(href),
            }
        )
    return links


def fetch_listing_sample(
    samples_dir: Path = DEFAULT_SAMPLES_DIR,
    listing_url: str = LISTING_URL,
    index_name: str = "list.html",
    list_link_pattern: re.Pattern[str] = LIST_LINK_PATTERN,
) -> Path:
    # Fetches the list index and every list page, skipping files already on
    # disk so an interrupted capture resumes.
    samples_dir.mkdir(parents=True, exist_ok=True)
    index_path = samples_dir / index_name
    if index_path.exists():
        index_html = index_path.read_text(encoding="utf-8")
    else:
        index_html = fetch_text(listing_url)
        index_path.write_text(index_html, encoding="utf-8")
        time.sleep(FETCH_PAUSE_SECONDS)

    for link in extract_list_links(index_html, list_link_pattern):
        list_path = _list_sample_path(samples_dir, link["listKey"])
        if list_path.exists():
            continue
        list_path.parent.mkdir(parents=True, exist_ok=True)
        list_path.write_text(fetch_text(link["url"]), encoding="utf-8")
        time.sleep(FETCH_PAUSE_SECONDS)

    return samples_dir


def list_records(
    list_html: str,
    link: dict[str, Any],
    candidate_pattern: re.Pattern[str] = CANDIDATE_ANKETA_PATTERN,
) -> list[dict[str, Any]]:
    """The candidates of one list page in list order."""
    soup = BeautifulSoup(list_html, "lxml")
    records: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        # The 2004 pages lay the whole page out in nested tables, so an
        # outer layout row contains every candidate anchor too; only the
        # row the anchor sits in directly is a candidate row. (The 2009 and
        # 2014 list tables are flat, where this is a no-op.)
        anchor = None
        for candidate in tr.find_all("a", href=True):
            if candidate_pattern.search(candidate["href"]) and candidate.find_parent("tr") is tr:
                anchor = candidate
                break
        if anchor is None:
            continue
        cells = tr.find_all("td")
        position_text = normalize_space(cells[0].get_text(" ", strip=True)) if cells else ""
        match = candidate_pattern.search(anchor["href"])
        records.append(
            {
                "vrkCandidateId": match.group(1) if match else "",
                "candidateName": clean_candidate_name(anchor.get_text(" ", strip=True)),
                "url": resolve_candidate_url(normalize_space(anchor["href"])),
                "list": link,
                "listPosition": int(position_text) if position_text.isdigit() else None,
                "row": tr,
            }
        )
    return records


def collect_list_records(
    samples_dir: Path,
    index_name: str = "list.html",
    list_link_pattern: re.Pattern[str] = LIST_LINK_PATTERN,
    candidate_pattern: re.Pattern[str] = CANDIDATE_ANKETA_PATTERN,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index_html = (samples_dir / index_name).read_text(encoding="utf-8")
    lists = extract_list_links(index_html, list_link_pattern)
    records: list[dict[str, Any]] = []
    for link in lists:
        list_path = _list_sample_path(samples_dir, link["listKey"])
        records.extend(list_records(list_path.read_text(encoding="utf-8"), link, candidate_pattern))
    return lists, records


def list_candidacy(record: dict[str, Any]) -> dict[str, Any]:
    link = record["list"]
    return {
        "sarasas": link["name"],
        "sarasoNumeris": link["listNumber"],
        "sarasoId": link["listKey"],
        "numerisSarase": record["listPosition"],
    }


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
    election_id: str = ELECTION_ID,
    listing_url: str = LISTING_URL,
    list_link_pattern: re.Pattern[str] = LIST_LINK_PATTERN,
    candidate_pattern: re.Pattern[str] = CANDIDATE_ANKETA_PATTERN,
) -> tuple[Path, dict[str, int]]:
    # sample_path keeps the CLI's signature; it names the samples directory.
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    lists, records = collect_list_records(
        samples_dir,
        list_link_pattern=list_link_pattern,
        candidate_pattern=candidate_pattern,
    )

    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_vrk_ids: set[str] = set()
    for record in records:
        if not record["vrkCandidateId"]:
            skipped.append({"reason": "missing-vrk-id", "candidateName": record["candidateName"]})
            continue
        if record["vrkCandidateId"] in seen_vrk_ids:
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
                "roles": ["daugiamandate"],
                "daugiamandateCandidacy": list_candidacy(record),
            }
        )

    duplicate_candidate_ids = assign_positional_ids(entries)

    # The index declares each list's size; the walked pages must agree.
    declared_total = sum(link["declaredCount"] or 0 for link in lists)
    per_list_mismatch = 0
    for link in lists:
        walked = sum(1 for record in records if record["list"]["listKey"] == link["listKey"])
        if link["declaredCount"] is not None and walked != link["declaredCount"]:
            per_list_mismatch += 1

    payload = {
        "electionId": election_id,
        "sourceUrl": listing_url,
        "listUrls": [link["url"] for link in lists],
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": len(records),
            "extracted": len(entries),
            "skipped": len(skipped),
            "duplicateCandidateIds": duplicate_candidate_ids,
            "lists": len(lists),
            "declaredCandidates": declared_total,
            "listCountMismatches": per_list_mismatch,
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
        "lists": len(lists),
        "declared_candidates": declared_total,
        "list_count_mismatches": per_list_mismatch,
    }
    return output_path, stats
