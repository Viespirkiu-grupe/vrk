from __future__ import annotations

from collections import Counter
import errno
from pathlib import Path
import re
import time
from typing import Any

from bs4 import BeautifulSoup

from scraper.elections.pakartotiniai_sirvintu_traku_2015.sitemap import (
    PARTY_LIST_LINK_PATTERN,
    _council_records,
    _district_sample_path,
    _extract_party_list_links,
    _list_sample_path,
    _municipality_name,
    fetch_listing_sample as _fetch_listing_sample,
)
from scraper.elections.savivaldybiu_2011.sitemap import title_case_name
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    normalize_space,
    resolve_candidate_url,
    utc_now_iso,
)
from scraper.shared.municipal_sitemap import build_candidate_id
from scraper.shared.files import write_json
from scraper.shared.http import fetch_text

ELECTION_ID = "2007-vasario-25-savivaldybiu"

# VRK election 3 — the oldest municipal general election with candidate
# pages, the same year as the Dzūkija Seimo by-election (396) and one tree
# older than the 2008 Seimo general: the path has no "_lt" suffix. Council
# seats only, and only parties (and coalitions of parties) could nominate —
# no self-nominated candidate of any kind stood, so every candidate is on a
# list. The listing is the 2011/2015 shape one rename away: an index of the
# 60 municipality pages ("Pagal apygardą", Apygardoje<ID>DalyvaujanciosPartijos
# rather than KandidataiApygardos<ID>) and of the 24 parties ("Pagal
# partiją"), each municipality page a ballot of numbered list rows, each
# list page the numbered candidates. The 2015 walker's fetcher, list reader
# and sample-file naming do the work; this module reads the index and the
# by-party pages, which the later trees do not have.
INDEX_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/3/Kandidatai/index.html"

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

INDEX_SAMPLE_NAME = "index.html"
PARTIES_SAMPLE_DIR = "parties"

DISTRICT_LINK_PATTERN = re.compile(r"Apygardoje(\d+)DalyvaujanciosPartijos\.html$")
PARTY_PAGE_PATTERN = re.compile(r"Partijos(\d+)Apygardos\.html$")

LIST_KIND_PARTY = "partija"
LIST_KIND_PARTY_COALITION = "partiju-koalicija"

FETCH_PAUSE_SECONDS = 0.3


def municipality_from_heading(heading: str) -> str:
    """"Elektrėnų rinkimų apygarda" → "Elektrėnų savivaldybė": the 2007
    municipality page is headed as the electoral district it also is; the
    corpus's municipal sitemaps name the municipality."""
    name = re.sub(r"\s+rinkimų apygarda\s*$", "", normalize_space(heading))
    return f"{name} savivaldybė" if name else heading


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


def extract_parties(index_html: str) -> list[dict[str, Any]]:
    """The index's "Pagal partiją" table: ballot number, name and page of
    each of the parties that nominated lists anywhere."""
    soup = BeautifulSoup(index_html, "lxml")
    parties: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        match = PARTY_PAGE_PATTERN.search(href)
        if match is None or match.group(1) in seen:
            continue
        seen.add(match.group(1))
        row = anchor.find_parent("tr")
        cells = [normalize_space(td.get_text(" ", strip=True)) for td in row.find_all("td")] if row else []
        number = next((cell for cell in cells if cell.isdigit()), "")
        parties.append(
            {
                "partyId": match.group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "number": int(number) if number else None,
                "url": resolve_candidate_url(href),
            }
        )
    return parties


def _party_sample_path(samples_dir: Path, party_id: str) -> Path:
    return samples_dir / PARTIES_SAMPLE_DIR / f"party-{party_id}.html"


def _fetch_into(path: Path, url: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    html = fetch_text(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    time.sleep(FETCH_PAUSE_SECONDS)
    return html


def _read_index(samples_dir: Path) -> str:
    index_path = samples_dir / INDEX_SAMPLE_NAME
    if not index_path.exists():
        raise FileNotFoundError(
            errno.ENOENT,
            "Missing municipality index sample (run fetch-sample first)",
            str(index_path),
        )
    return index_path.read_text(encoding="utf-8")


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    samples_dir.mkdir(parents=True, exist_ok=True)
    index_html = _fetch_into(samples_dir / INDEX_SAMPLE_NAME, INDEX_URL)
    for party in extract_parties(index_html):
        _fetch_into(_party_sample_path(samples_dir, party["partyId"]), party["url"])
    # The 2015 walker fetches every municipality page and every list page
    # under it, resuming past files already on disk.
    return _fetch_listing_sample(samples_dir=samples_dir, district_urls=extract_district_urls(index_html))


def _party_page_list_urls(samples_dir: Path, party_id: str) -> set[str]:
    """The list pages a party's own page links — one per municipality it
    nominated a list in."""
    path = _party_sample_path(samples_dir, party_id)
    if not path.exists():
        return set()
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
    urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        if PARTY_LIST_LINK_PATTERN.search(href):
            urls.add(resolve_candidate_url(href))
    return urls


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    # sample_path keeps the CLI's signature; it names the samples directory.
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    index_html = _read_index(samples_dir)
    district_urls = extract_district_urls(index_html)
    parties = extract_parties(index_html)
    party_ids = {party["partyId"] for party in parties}
    party_names = {party["partyId"]: party["name"] for party in parties}
    party_page_lists: set[str] = set()
    party_page_lists_by_party: dict[str, set[str]] = {}
    for party in parties:
        party_page_lists_by_party[party["partyId"]] = _party_page_list_urls(samples_dir, party["partyId"])
        party_page_lists |= party_page_lists_by_party[party["partyId"]]

    list_records: list[dict[str, Any]] = []
    list_kinds: Counter[str] = Counter()
    walked_lists: set[str] = set()
    walked_party_lists: set[str] = set()
    coalitions: list[dict[str, Any]] = []

    for district_url in district_urls:
        district_path = _district_sample_path(samples_dir, district_url)
        soup = BeautifulSoup(district_path.read_text(encoding="utf-8"), "lxml")
        municipality = municipality_from_heading(_municipality_name(soup))

        for link in _extract_party_list_links(soup):
            list_match = PARTY_LIST_LINK_PATTERN.search(link["url"])
            list_id = list_match.group(2) if list_match else ""
            # A list whose id is a party's is that party's list; any other
            # list on the ballot is a coalition of parties, registered under
            # an id of its own and on no party's page.
            kind = LIST_KIND_PARTY if list_id in party_ids else LIST_KIND_PARTY_COALITION
            list_kinds[kind] += 1
            walked_lists.add(link["url"])
            if kind == LIST_KIND_PARTY:
                walked_party_lists.add(link["url"])
            else:
                coalitions.append(
                    {
                        "listId": list_id,
                        "name": link["partyList"],
                        "municipality": municipality,
                        "districtId": list_match.group(1) if list_match else None,
                        "listNumber": link["listNumber"],
                        "memberParties": [],
                    }
                )
            list_path = _list_sample_path(samples_dir, link["url"])
            members = _council_records(list_path.read_text(encoding="utf-8"), link, municipality)
            for record in members:
                record["candidateName"] = title_case_name(record["candidateName"])
                record["listKind"] = kind
                list_records.append(record)

    # Merge on VRK's own candidate id, as the sibling municipal modules do.
    # Nobody stood twice in 2007; the stat says whether the guard ever fired.
    entries_by_vrk_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for record in list_records:
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
        entry["councilCandidacy"] = {
            "partyList": record["partyList"],
            "listKind": record["listKind"],
            "listNumber": record["listNumber"],
            "listPosition": record["listPosition"],
            "selfNominated": False,
        }

    entries = [entries_by_vrk_id[vrk_id] for vrk_id in order]
    duplicate_candidate_ids = sum(
        1 for _, count in Counter(entry["candidateId"] for entry in entries).items() if count > 1
    )

    # A party that stood in a coalition has, on its own page, a link to a
    # list under its own id in that municipality — a page with a heading
    # and no candidates, since the ballot carries the coalition's list
    # instead. Those links are not lists to walk; they name the coalition's
    # members, which nothing else on the listing does.
    coalitions_by_district = {c["districtId"]: c for c in coalitions}
    member_party_shells: set[str] = set()
    for party_id, urls in party_page_lists_by_party.items():
        for url in urls - walked_lists:
            list_match = PARTY_LIST_LINK_PATTERN.search(url)
            coalition = coalitions_by_district.get(list_match.group(1)) if list_match else None
            if coalition is None:
                continue
            coalition["memberParties"].append(party_names[party_id])
            member_party_shells.add(url)
    for coalition in coalitions:
        coalition["memberParties"].sort()

    payload = {
        "electionId": ELECTION_ID,
        "sourceUrl": INDEX_URL,
        "districtUrls": district_urls,
        "parties": [
            {"partyId": party["partyId"], "number": party["number"], "name": party["name"]}
            for party in parties
        ],
        "coalitions": coalitions,
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": len(list_records),
            "extracted": len(entries),
            "skipped": 0,
            "duplicateCandidateIds": duplicate_candidate_ids,
            "municipalities": len(district_urls),
            "parties": len(parties),
            "partyLists": sum(list_kinds.values()),
            "listKinds": dict(list_kinds),
            "listCandidates": len(list_records),
            "candidatesOnSeveralLists": len(list_records) - len(entries),
            # The by-party pages are VRK's own roll-up of where each party
            # stood: every party list walked should be on its party's page,
            # and every party-page link either walked or a coalition
            # member's empty shell. Both remainders should be empty.
            "partyPageLists": len(party_page_lists),
            "coalitionMemberShells": len(member_party_shells),
            "partyPageListsUnexplained": len(party_page_lists - walked_lists - member_party_shells),
            "walkedPartyListsNotOnPartyPages": len(walked_party_lists - party_page_lists),
        },
        "entries": entries,
        "skipped": [],
    }
    write_json(output_path, payload)

    stats = {
        "rows": len(list_records),
        "extracted": len(entries),
        "skipped": 0,
        "duplicate_candidate_ids": duplicate_candidate_ids,
        "municipalities": len(district_urls),
        "parties": len(parties),
        "party_lists": payload["stats"]["partyLists"],
        "list_kinds": dict(list_kinds),
        "list_candidates": len(list_records),
        "candidates_on_several_lists": payload["stats"]["candidatesOnSeveralLists"],
        "party_page_lists": len(party_page_lists),
        "coalition_member_shells": len(member_party_shells),
        "party_page_lists_unexplained": payload["stats"]["partyPageListsUnexplained"],
        "walked_party_lists_not_on_party_pages": payload["stats"]["walkedPartyListsNotOnPartyPages"],
    }
    return output_path, stats
