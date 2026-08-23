"""Sitemap building for the 2000-03-19 municipal council general election.

VRK's ``statiniai/puslapiai/n/rinkimai/20000319/`` tree is the 1997
municipal archive (``scraper/shared/savivaldybiu_archive_1997.py``) three
years on — the same Teleport capture of the LRS-ITD Oracle-CGI site
(``tppabs`` attributes and all) and the same three-hop listing:

    apgl.htm-12+<number>.htm   (municipality)  -- the lists standing there,
                                                  with the VRK registration
                                                  decision per list
    pkal.htm-<id>+<list>.htm   (party list)    -- the numbered candidates
    kandvl.htm-<ID>.htm        (candidate)     -- one page, the 2000 Seimas
                                                  document for the municipal
                                                  form

with two differences from 1997. The municipality directory the index
links (``apgsarl.htm-12.htm``) is served as a 403 by vrk.lt, so the 60
municipalities are enumerated from the results index
(``rapgsarl.htm-12.htm``: number, name and the municipality's id, which
the ``pkal``/``rapgpl`` pages key on while ``apgl`` keys on the number).
And the site adds a by-party roll-up — ``psarl.htm-12.htm`` lists the 29
parties, each ``papgsarl.htm-<party>.htm`` the municipalities it stood in,
**its own list in bold, a coalition it joined in plain type** — which is
both the cross-check for the walk (every ``pkal`` page a party links must
be one the municipality pages list, and vice versa) and the only source
of a coalition's member parties.

Candidate ids are ``<name-slug>-<vrk id>`` as for the 2007–2023 municipal
generals: at this scale name slugs collide and the batch runner resumes
on the output filename.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from scraper.shared.files import write_json
from scraper.shared.http import fetch_text
from scraper.shared.municipal_sitemap import build_candidate_id
from scraper.shared.savivaldybiu_archive_1997 import (
    normalize_space,
    parse_party_candidates_page,
)

ELECTION_ID = "2000-kovo-19-savivaldybiu-tarybu"
SITE_ROOT = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/20000319/"
LISTING_URL = SITE_ROOT + "psarl.htm-12.htm"
MUNICIPALITIES_URL = SITE_ROOT + "rapgsarl.htm-12.htm"

LISTS_INDEX_NAME = "list.html"
MUNICIPALITIES_INDEX_NAME = "municipalities.html"

CANDIDATE_PAGE_PATTERN = re.compile(r"kandvl\.htm-(\d+)\.htm$")
PARTY_PAGE_PATTERN = re.compile(r"papgsarl\.htm-(\d+)\.htm$")
MUNICIPALITY_RESULTS_PATTERN = re.compile(r"rapgpl\.htm-(\d+)\.htm$")
LIST_PAGE_PATTERN = re.compile(r"pkal\.htm-(\d+)\+(\d+)\.htm$")
MUNICIPALITY_NUMBER_PATTERN = re.compile(r"\(Nr\.\s*(\d+)\)")

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

FETCH_PAUSE_SECONDS = 0.3

__all__ = [
    "ELECTION_ID",
    "LISTING_URL",
    "MUNICIPALITIES_URL",
    "SITE_ROOT",
    "build_sitemap_from_sample",
    "extract_municipality_links",
    "extract_party_links",
    "fetch_listing_sample",
    "load_sitemap_entries",
    "municipality_page_url",
    "parse_municipality_page",
    "parse_party_page",
    "resolve_site_url",
]


def resolve_site_url(href: str) -> str:
    return urljoin(SITE_ROOT, normalize_space(href))


def municipality_page_url(number: int) -> str:
    return f"{SITE_ROOT}apgl.htm-12+{number}.htm"


# ---------------------------------------------------------------------------
# Index pages
# ---------------------------------------------------------------------------


def extract_municipality_links(index_html: str) -> list[dict[str, Any]]:
    """The 60 municipalities of the results index: "N. <a>name</a> (k/n)"
    runs, each linking rapgpl.htm-<id>.htm — the number from the text
    before the link, the id from the link."""
    soup = BeautifulSoup(index_html, "lxml")
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = MUNICIPALITY_RESULTS_PATTERN.search(anchor["href"])
        if match is None:
            continue
        municipality_id = match.group(1)
        if municipality_id in seen:
            continue
        seen.add(municipality_id)
        # "1.&nbsp; <b><a>Akmenės rajono</a> (16/16)</b>": the number is the
        # text run before the bold holding the link.
        holder = anchor.parent if anchor.parent is not None and anchor.parent.name == "b" else anchor
        previous = holder.previous_sibling
        while previous is not None and isinstance(previous, Tag):
            previous = previous.previous_sibling
        number_text = normalize_space(str(previous)) if previous is not None else ""
        number_match = re.search(r"(\d+)\.\s*$", number_text)
        links.append(
            {
                "municipalityId": municipality_id,
                "number": int(number_match.group(1)) if number_match else None,
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "resultsUrl": resolve_site_url(anchor["href"]),
                "url": municipality_page_url(int(number_match.group(1))) if number_match else None,
            }
        )
    return links


def extract_party_links(index_html: str) -> list[dict[str, Any]]:
    """The party index: VRK's number and name per party, linking the
    party's by-municipality page."""
    soup = BeautifulSoup(index_html, "lxml")
    links: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [td for td in tr.find_all("td") if td.find_parent("tr") is tr]
            if len(cells) < 2:
                continue
            anchor = None
            for candidate in cells[1].find_all("a", href=True):
                if PARTY_PAGE_PATTERN.search(candidate["href"]):
                    anchor = candidate
                    break
            if anchor is None:
                continue
            number_text = normalize_space(cells[0].get_text(" ", strip=True)).rstrip(".")
            links.append(
                {
                    "partyId": PARTY_PAGE_PATTERN.search(anchor["href"]).group(1),
                    "number": int(number_text) if number_text.isdigit() else None,
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "url": resolve_site_url(anchor["href"]),
                }
            )
        if links:
            break
    return links


# ---------------------------------------------------------------------------
# Municipality, party and list pages
# ---------------------------------------------------------------------------


def parse_municipality_page(html: str) -> dict[str, Any]:
    """One apgl.htm page: name, number, voters, seats, and the lists
    standing there — list number, name, the pkal link (municipality id
    and list id) and VRK's registration decision, blank for a coalition."""
    soup = BeautifulSoup(html, "lxml")
    heading = ""
    for font in soup.find_all("font", attrs={"size": "5"}):
        text = normalize_space(font.get_text(" ", strip=True))
        if "apygarda" in text.lower():
            heading = text
            break
    number_match = MUNICIPALITY_NUMBER_PATTERN.search(heading)
    text = normalize_space(soup.get_text(" ", strip=True))
    voters = re.search(r"Rinkėjų skaičius:\s*(\d+)", text)
    seats = re.search(r"Mandatų skaičius:\s*(\d+)", text)

    lists: list[dict[str, Any]] = []
    municipality_id = None
    for table in soup.find_all("table"):
        header = normalize_space(table.get_text(" ", strip=True))
        if "Sąrašo" not in header or "Partija" not in header:
            continue
        for tr in table.find_all("tr")[1:]:
            cells = [td for td in tr.find_all("td") if td.find_parent("tr") is tr]
            if len(cells) < 2:
                continue
            anchor = None
            for candidate in cells[1].find_all("a", href=True):
                if LIST_PAGE_PATTERN.search(candidate["href"]):
                    anchor = candidate
                    break
            if anchor is None:
                continue
            match = LIST_PAGE_PATTERN.search(anchor["href"])
            municipality_id = municipality_id or match.group(1)
            number_text = normalize_space(cells[0].get_text(" ", strip=True)).rstrip(".")
            decision = normalize_space(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else ""
            lists.append(
                {
                    "listNumber": int(number_text) if number_text.isdigit() else None,
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "listId": match.group(2),
                    "municipalityId": match.group(1),
                    "url": resolve_site_url(anchor["href"]),
                    "vrkDecision": decision or None,
                }
            )
        break
    return {
        "name": re.sub(r"\s*\(Nr\.\s*\d+\)\s*apygarda\s*$", "", heading, flags=re.IGNORECASE).strip(),
        "number": int(number_match.group(1)) if number_match else None,
        "municipalityId": municipality_id,
        "voters": int(voters.group(1)) if voters else None,
        "seats": int(seats.group(1)) if seats else None,
        "lists": lists,
    }


def parse_party_page(html: str) -> list[dict[str, Any]]:
    """One papgsarl.htm page: every pkal link the party claims, with
    whether it is the party's own list (bold) or a coalition it joined
    (plain)."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for anchor in soup.find_all("a", href=True):
        match = LIST_PAGE_PATTERN.search(anchor["href"])
        if match is None:
            continue
        own = anchor.find("b") is not None or anchor.find_parent("b") is not None
        rows.append(
            {
                "municipalityId": match.group(1),
                "listId": match.group(2),
                "municipalityName": normalize_space(anchor.get_text(" ", strip=True)),
                "ownList": own,
                "url": resolve_site_url(anchor["href"]),
            }
        )
    return rows


def parse_list_page(html: str) -> dict[str, Any]:
    """One pkal.htm page: the list's name, its representatives and the
    numbered candidates (the 1997 reader)."""
    soup = BeautifulSoup(html, "lxml")
    name = ""
    for font in soup.find_all("font", attrs={"size": "5"}):
        name = normalize_space(font.get_text(" ", strip=True))
        break
    text = normalize_space(soup.get_text(" ", strip=True))
    representatives = re.search(r"Atstovas\(-ai\) rinkimams:\s*(.*?)\s*Kandidatų sąrašas", text)
    return {
        "name": name,
        "representatives": normalize_space(representatives.group(1)) if representatives else None,
        "candidates": parse_party_candidates_page(html, source_url=SITE_ROOT),
    }


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def _municipality_sample_path(samples_dir: Path, number: int) -> Path:
    return samples_dir / "municipalities" / f"municipality-{number}.html"


def _party_sample_path(samples_dir: Path, party_id: str) -> Path:
    return samples_dir / "parties" / f"party-{party_id}.html"


def _list_sample_path(samples_dir: Path, municipality_id: str, list_id: str) -> Path:
    return samples_dir / "lists" / f"list-{municipality_id}-{list_id}.html"


def _fetch_once(path: Path, url: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    html = fetch_text(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    time.sleep(FETCH_PAUSE_SECONDS)
    return html


def fetch_listing_sample(
    samples_dir: Path = DEFAULT_SAMPLES_DIR,
    listing_url: str = LISTING_URL,
    municipalities_url: str = MUNICIPALITIES_URL,
) -> Path:
    """Both indexes, the 60 municipality pages, every list page they link
    and the 29 party pages — skipping files already on disk so an
    interrupted capture resumes."""
    samples_dir.mkdir(parents=True, exist_ok=True)
    municipalities_html = _fetch_once(samples_dir / MUNICIPALITIES_INDEX_NAME, municipalities_url)
    for municipality in extract_municipality_links(municipalities_html):
        if municipality["number"] is None:
            continue
        page = parse_municipality_page(_fetch_once(_municipality_sample_path(samples_dir, municipality["number"]), municipality["url"]))
        for entry in page["lists"]:
            _fetch_once(_list_sample_path(samples_dir, entry["municipalityId"], entry["listId"]), entry["url"])
    lists_html = _fetch_once(samples_dir / LISTS_INDEX_NAME, listing_url)
    for party in extract_party_links(lists_html):
        _fetch_once(_party_sample_path(samples_dir, party["partyId"]), party["url"])
    return samples_dir


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    # sample_path keeps the CLI's signature; it names the samples directory.
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    municipalities = extract_municipality_links((samples_dir / MUNICIPALITIES_INDEX_NAME).read_text(encoding="utf-8"))
    parties = extract_party_links((samples_dir / LISTS_INDEX_NAME).read_text(encoding="utf-8"))

    # The party pages: which (municipality, list) pairs each party claims,
    # as its own list or as a coalition it joined.
    own_claims: dict[tuple[str, str], list[str]] = {}
    coalition_claims: dict[tuple[str, str], list[str]] = {}
    for party in parties:
        for row in parse_party_page(_party_sample_path(samples_dir, party["partyId"]).read_text(encoding="utf-8")):
            key = (row["municipalityId"], row["listId"])
            (own_claims if row["ownList"] else coalition_claims).setdefault(key, []).append(party["name"])

    entries: list[dict[str, Any]] = []
    walked: set[tuple[str, str]] = set()
    municipality_pages: list[dict[str, Any]] = []
    missing_list_samples = 0
    list_count = 0
    coalition_lists = 0
    own_claim_name_mismatches = 0
    municipality_id_mismatches = 0
    for municipality in municipalities:
        if municipality["number"] is None:
            continue
        page = parse_municipality_page(_municipality_sample_path(samples_dir, municipality["number"]).read_text(encoding="utf-8"))
        if page["municipalityId"] != municipality["municipalityId"]:
            municipality_id_mismatches += 1
        municipality_pages.append(
            {
                "municipalityId": municipality["municipalityId"],
                "number": page["number"],
                "name": page["name"],
                "voters": page["voters"],
                "seats": page["seats"],
                "lists": len(page["lists"]),
            }
        )
        for entry in page["lists"]:
            list_count += 1
            key = (entry["municipalityId"], entry["listId"])
            walked.add(key)
            list_path = _list_sample_path(samples_dir, entry["municipalityId"], entry["listId"])
            if not list_path.exists():
                missing_list_samples += 1
                continue
            list_page = parse_list_page(list_path.read_text(encoding="utf-8"))
            members = coalition_claims.get(key, [])
            owners = own_claims.get(key, [])
            kind = "koalicija" if members and not owners else "partija"
            if kind == "koalicija":
                coalition_lists += 1
            if owners and owners[0] != entry["name"]:
                own_claim_name_mismatches += 1
            for candidate in list_page["candidates"]:
                vrk_match = CANDIDATE_PAGE_PATTERN.search(candidate["url"])
                vrk_id = vrk_match.group(1) if vrk_match else ""
                entries.append(
                    {
                        "candidateName": candidate["candidateName"],
                        "candidateId": build_candidate_id(candidate["candidateName"], vrk_id),
                        "url": candidate["url"],
                        "vrkCandidateId": vrk_id,
                        "municipality": {
                            "pavadinimas": page["name"],
                            "numeris": page["number"],
                            "savivaldybesId": entry["municipalityId"],
                            "mandatai": page["seats"],
                        },
                        "list": {
                            "pavadinimas": entry["name"],
                            "rusis": kind,
                            "numeris": entry["listNumber"],
                            "sarasoId": entry["listId"],
                            "vrkSprendimas": entry["vrkDecision"],
                            **({"koalicijosPartijos": members} if kind == "koalicija" else {}),
                        },
                        "listPosition": candidate["listNumber"],
                    }
                )

    claimed = set(own_claims) | set(coalition_claims)
    by_vrk = {}
    for entry in entries:
        by_vrk.setdefault(entry["vrkCandidateId"], []).append(entry)
    duplicate_vrk_ids = sum(1 for rows in by_vrk.values() if len(rows) > 1)
    duplicate_candidate_ids = sum(1 for _, count in Counter(e["candidateId"] for e in entries).items() if count > 1)

    stats = {
        "rows": list_count,
        "extracted": len(entries),
        "skipped": missing_list_samples,
        "duplicate_candidate_ids": duplicate_candidate_ids,
        "municipalities": len(municipality_pages),
        "partyLists": list_count,
        "coalitionLists": coalition_lists,
        "missingPartyListSamples": missing_list_samples,
        "parties": len(parties),
        "listsClaimedByParties": len(claimed),
        "claimedNotWalked": len(claimed - walked),
        "walkedNotClaimed": len(walked - claimed),
        "ownClaimNameMismatches": own_claim_name_mismatches,
        "municipalityIdMismatches": municipality_id_mismatches,
        "duplicateVrkIds": duplicate_vrk_ids,
        "duplicateCandidateIds": duplicate_candidate_ids,
        "seatsDeclared": sum(m["seats"] or 0 for m in municipality_pages),
    }
    payload = {
        "electionId": ELECTION_ID,
        "sourceUrl": LISTING_URL,
        "municipalitiesUrl": MUNICIPALITIES_URL,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "stats": {k: v for k, v in stats.items() if k not in ("rows", "extracted", "skipped", "duplicate_candidate_ids")},
        "municipalities": municipality_pages,
        "entries": entries,
    }
    write_json(output_path, payload)
    return output_path, stats


def load_sitemap_entries(sitemap_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(sitemap_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"No sitemap entries found in {sitemap_path}")
    return entries
