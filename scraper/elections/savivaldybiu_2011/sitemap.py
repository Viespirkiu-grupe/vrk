from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import time
from typing import Any

from bs4 import BeautifulSoup

from scraper.elections.pakartotiniai_sirvintu_traku_2015.sitemap import (
    CANDIDATE_ANKETA_PATTERN,
    PARTY_LIST_LINK_PATTERN,
    _council_records,
    _district_sample_path,
    _extract_party_list_links,
    _list_sample_path,
    _municipality_name,
    fetch_listing_sample as _fetch_listing_sample,
)
from scraper.elections.savivaldybiu_2015.sitemap import extract_district_urls
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    clean_candidate_name,
    normalize_space,
    resolve_candidate_url,
    utc_now_iso,
)
from scraper.shared.municipal_sitemap import build_candidate_id
from scraper.shared.files import write_json
from scraper.shared.http import fetch_text

ELECTION_ID = "2011-vasario-27-savivaldybiu"

# VRK election 409, the last municipal general election before mayors were
# elected directly: council seats only. The listing is the 2015 shape — an
# index of 60 municipality pages, each a ballot of numbered rows — but a
# row is one of two things here. A party, a party coalition or a coalition
# of self-nominated candidates links its list page; a self-nominated
# individual (2011 is the only general election in which people stood for
# the council on their own, at one seat each) links the candidate page
# directly. The 2015 machinery reads a direct candidate link on the
# municipality page as a mayoral candidacy, which is the one thing it cannot
# be here, so this module walks the same files with its own row reader.
INDEX_URL = (
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/409_lt/Kandidatai/index.html"
)
# VRK's own roll-ups, used to cross-check the walk and to tell the list
# kinds apart: every self-nominated candidate by municipality — the
# individuals and the members of the self-nominated coalitions alike, 505
# in all — the party coalitions and the coalitions of self-nominated
# candidates, each with its declared member count. A list on neither
# coalition page is a party's.
ISSIKELE_URL = (
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/409_lt/Kandidatai/KandidataiIssikele.html"
)
KOALICIJOS_URL = (
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/409_lt/Kandidatai/KandidataiKoalicijos1.html"
)
ISSIKELE_KOALICIJOS_URL = (
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/409_lt/Kandidatai/KandidataiIssikeleKoalicijos.html"
)

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

INDEX_SAMPLE_NAME = "index.html"
ISSIKELE_SAMPLE_NAME = "issikele.html"
KOALICIJOS_SAMPLE_NAME = "koalicijos.html"
ISSIKELE_KOALICIJOS_SAMPLE_NAME = "issikele-koalicijos.html"

LIST_KIND_PARTY = "partija"
LIST_KIND_PARTY_COALITION = "partiju-koalicija"
LIST_KIND_SELF_NOMINATED_COALITION = "issikelusiu-kandidatu-koalicija"

FETCH_PAUSE_SECONDS = 0.3


def title_case_name(name: str) -> str:
    """"VALDEMARAS STANČIKAS" → "Valdemaras Stančikas": the list pages print
    the whole name in capitals while the municipality pages (and so the
    self-nominated individuals) print it in title case, which is also the
    form the other municipal sitemaps of the corpus keep."""
    return " ".join(part.title() for part in name.split())


def _fetch_into(samples_dir: Path, name: str, url: str) -> str:
    path = samples_dir / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    html = fetch_text(url)
    path.write_text(html, encoding="utf-8")
    time.sleep(FETCH_PAUSE_SECONDS)
    return html


def _read_district_urls(samples_dir: Path) -> list[str]:
    index_path = samples_dir / INDEX_SAMPLE_NAME
    if not index_path.exists():
        raise FileNotFoundError(
            f"Missing municipality index sample: {index_path}. Run fetch-sample first."
        )
    return extract_district_urls(index_path.read_text(encoding="utf-8"))


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    samples_dir.mkdir(parents=True, exist_ok=True)
    index_html = _fetch_into(samples_dir, INDEX_SAMPLE_NAME, INDEX_URL)
    _fetch_into(samples_dir, ISSIKELE_SAMPLE_NAME, ISSIKELE_URL)
    _fetch_into(samples_dir, KOALICIJOS_SAMPLE_NAME, KOALICIJOS_URL)
    _fetch_into(samples_dir, ISSIKELE_KOALICIJOS_SAMPLE_NAME, ISSIKELE_KOALICIJOS_URL)
    district_urls = extract_district_urls(index_html)
    # The 2015 walker fetches every municipality page and every list page
    # under it, resuming past files already on disk; a direct candidate link
    # on the municipality page is not a list link, so it fetches nothing for
    # the individuals, whose pages are candidate samples.
    return _fetch_listing_sample(samples_dir=samples_dir, district_urls=district_urls)


def _individual_records(soup: BeautifulSoup, municipality: str) -> list[dict[str, Any]]:
    """The self-nominated individuals on a municipality page: the ballot rows
    that link a candidate page rather than a list page."""
    records: list[dict[str, Any]] = []
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        match = CANDIDATE_ANKETA_PATTERN.search(href)
        if match is None:
            continue
        cell = anchor.find_parent("td")
        row_text = normalize_space(cell.get_text(" ", strip=True)) if cell else ""
        number_match = re.match(r"^(\d+)\s", row_text)
        records.append(
            {
                "vrkCandidateId": match.group(1),
                "candidateName": title_case_name(clean_candidate_name(anchor.get_text(" ", strip=True))),
                "url": resolve_candidate_url(href),
                "municipality": municipality,
                "ballotNumber": int(number_match.group(1)) if number_match else None,
            }
        )
    return records


def _coalition_list_sizes(samples_dir: Path, name: str) -> dict[str, int | None]:
    """List id → the member count a coalition roll-up declares for it
    (Savivaldybė | coalition | Kandidatų skaičius)."""
    path = samples_dir / name
    if not path.exists():
        return {}
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
    sizes: dict[str, int | None] = {}
    for anchor in soup.find_all("a", href=True):
        match = PARTY_LIST_LINK_PATTERN.search(normalize_space(anchor["href"]))
        if match is None:
            continue
        row = anchor.find_parent("tr")
        cells = [normalize_space(td.get_text(" ", strip=True)) for td in row.find_all("td")] if row else []
        declared = cells[-1] if cells else ""
        sizes[match.group(2)] = int(declared) if declared.isdigit() else None
    return sizes


def _self_nominated_listing_ids(samples_dir: Path) -> set[str]:
    path = samples_dir / ISSIKELE_SAMPLE_NAME
    if not path.exists():
        return set()
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
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
    # sample_path keeps the CLI's signature; it names the samples directory.
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    district_urls = _read_district_urls(samples_dir)
    party_coalitions = _coalition_list_sizes(samples_dir, KOALICIJOS_SAMPLE_NAME)
    self_nominated_coalitions = _coalition_list_sizes(samples_dir, ISSIKELE_KOALICIJOS_SAMPLE_NAME)

    list_records: list[dict[str, Any]] = []
    individual_records: list[dict[str, Any]] = []
    list_kinds: Counter[str] = Counter()
    walked_list_sizes: dict[str, int] = {}

    for district_url in district_urls:
        district_path = _district_sample_path(samples_dir, district_url)
        soup = BeautifulSoup(district_path.read_text(encoding="utf-8"), "lxml")
        municipality = _municipality_name(soup)

        individual_records.extend(_individual_records(soup, municipality))

        for link in _extract_party_list_links(soup):
            list_match = PARTY_LIST_LINK_PATTERN.search(link["url"])
            list_id = list_match.group(2) if list_match else ""
            if list_id in self_nominated_coalitions:
                kind = LIST_KIND_SELF_NOMINATED_COALITION
            elif list_id in party_coalitions:
                kind = LIST_KIND_PARTY_COALITION
            else:
                kind = LIST_KIND_PARTY
            list_kinds[kind] += 1
            list_path = _list_sample_path(samples_dir, link["url"])
            members = _council_records(list_path.read_text(encoding="utf-8"), link, municipality)
            walked_list_sizes[list_id] = len(members)
            for record in members:
                record["candidateName"] = title_case_name(record["candidateName"])
                record["listKind"] = kind
                list_records.append(record)

    # Merge on VRK's own candidate id, as the 2015 modules do. Nobody can be
    # on a list and stand alone in the same election, so the merge is a
    # guard rather than a feature here; the stat says whether it ever fired.
    entries_by_vrk_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def _entry_for(record: dict[str, Any]) -> dict[str, Any]:
        vrk_id = record["vrkCandidateId"]
        entry = entries_by_vrk_id.get(vrk_id)
        if entry is None:
            entry = {
                "candidateName": record["candidateName"],
                "candidateId": build_candidate_id(record["candidateName"], vrk_id),
                "url": record["url"],
                "vrkCandidateId": vrk_id,
                "municipality": record["municipality"],
                "roles": ["tarybos-narys"],
            }
            entries_by_vrk_id[vrk_id] = entry
            order.append(vrk_id)
        return entry

    for record in list_records:
        entry = _entry_for(record)
        entry["councilCandidacy"] = {
            "partyList": record["partyList"],
            "listKind": record["listKind"],
            "listNumber": record["listNumber"],
            "listPosition": record["listPosition"],
            "selfNominated": False,
        }
    for record in individual_records:
        entry = _entry_for(record)
        if "councilCandidacy" in entry:
            continue
        entry["councilCandidacy"] = {
            "partyList": None,
            "listKind": None,
            # The individual's own number on the ballot, in the one sequence
            # the lists are numbered in.
            "listNumber": record["ballotNumber"],
            "listPosition": None,
            "selfNominated": True,
        }

    entries = [entries_by_vrk_id[vrk_id] for vrk_id in order]
    duplicate_candidate_ids = sum(
        1 for _, count in Counter(entry["candidateId"] for entry in entries).items() if count > 1
    )

    # The self-nominated roll-up is every candidate who nominated themself:
    # the individuals and the members of the self-nominated coalitions (505
    # = 143 + 362). Both sides of the check should be empty.
    walked_individuals = {record["vrkCandidateId"] for record in individual_records}
    coalition_members = {
        record["vrkCandidateId"]
        for record in list_records
        if record["listKind"] == LIST_KIND_SELF_NOMINATED_COALITION
    }
    walked_self_nominated = walked_individuals | coalition_members
    listing_self_nominated = _self_nominated_listing_ids(samples_dir)
    both_ways = sum(
        1 for vrk_id in walked_individuals
        if any(record["vrkCandidateId"] == vrk_id for record in list_records)
    )
    # Each coalition roll-up declares the member count of every coalition it
    # lists; the walked list pages should agree, list for list.
    coalition_sizes = party_coalitions | self_nominated_coalitions
    coalition_size_mismatches = sum(
        1 for list_id, declared in coalition_sizes.items()
        if declared is not None and walked_list_sizes.get(list_id) != declared
    )

    payload = {
        "electionId": ELECTION_ID,
        "sourceUrl": INDEX_URL,
        "selfNominatedListingUrl": ISSIKELE_URL,
        "districtUrls": district_urls,
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": len(list_records) + len(individual_records),
            "extracted": len(entries),
            "skipped": 0,
            "duplicateCandidateIds": duplicate_candidate_ids,
            "municipalities": len(district_urls),
            "partyLists": sum(list_kinds.values()),
            "listKinds": dict(list_kinds),
            "listCandidates": len(list_records),
            "selfNominatedCandidates": len(individual_records),
            "selfNominatedCoalitionMembers": len(coalition_members),
            "selfNominatedListingCandidates": len(listing_self_nominated),
            "selfNominatedOnlyInListing": len(listing_self_nominated - walked_self_nominated),
            "selfNominatedOnlyInDistrictWalk": len(walked_self_nominated - listing_self_nominated),
            "selfNominatedAlsoOnList": both_ways,
            "coalitionListsNotWalked": len(set(coalition_sizes) - set(walked_list_sizes)),
            "coalitionSizeMismatches": coalition_size_mismatches,
        },
        "entries": entries,
        "skipped": [],
    }
    write_json(output_path, payload)

    stats = {
        "rows": payload["stats"]["rows"],
        "extracted": len(entries),
        "skipped": 0,
        "duplicate_candidate_ids": duplicate_candidate_ids,
        "municipalities": len(district_urls),
        "party_lists": payload["stats"]["partyLists"],
        "list_kinds": dict(list_kinds),
        "list_candidates": len(list_records),
        "self_nominated_candidates": len(individual_records),
        "self_nominated_coalition_members": len(coalition_members),
        "self_nominated_listing_candidates": len(listing_self_nominated),
        "self_nominated_only_in_listing": payload["stats"]["selfNominatedOnlyInListing"],
        "self_nominated_only_in_district_walk": payload["stats"]["selfNominatedOnlyInDistrictWalk"],
        "self_nominated_also_on_list": both_ways,
        "coalition_lists_not_walked": payload["stats"]["coalitionListsNotWalked"],
        "coalition_size_mismatches": coalition_size_mismatches,
    }
    return output_path, stats
