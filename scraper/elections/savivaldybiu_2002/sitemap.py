"""Listing walk of the 2002-12-22 municipal council general election.

VRK's ``rinkimai/2002/savivaldybes/`` tree is the 2002 LRS-ITD template
(the site generation of ``prezidento_2002``, held the same day) with a
two-structure listing:

    kandidatai/                                the 60 municipalities
    kandidatai/kandidatai_apygardoje_jsp_ri_id_15_apyg_id_<APYG>.htm
        one municipality: the candidates grouped under bold
        "N. <list name>" headings, one row per candidate — position,
        name linking the anketa page, a "pajamų deklaracijos" link —
        both per-candidate pages keyed by ``asm_kod``, VRK's person id.
    partijos/                                  the 25 parties
    partijos/kandidatai_apygardose_jsp_ri_id_15_org_ri_id_<ORG>.htm
        one party: the municipalities it stood in.
    partijos/<ORG>/kandidatai_apygardoje_jsp_ri_id_15_apyg_id_<APYG>_org_ri_id_<ORG>.htm
        the party's candidates in one municipality — the same document
        as the constituency page, narrowed to the party's own people.

Neither structure contains the other's facts: the constituency pages
carry every list (a coalition included — A. Zuoko koalicija in Vilnius
is a heading there and no party of the index), the party pages say
which member party nominated each of a coalition's candidates, and a
list's kind falls out of the overlay: a heading exactly one party
claims under its own name is that party's list, a heading claimed by
several parties is their coalition. The heading's number is the list's
ballot number, constant across municipalities (the party index's own
numbering), which is also how the results tree names lists.

Candidate ids are ``<name-slug>-<asm_kod>`` as for the 2000–2023
municipal generals: at this scale name slugs collide and the batch
runner resumes on the output filename.
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
from scraper.shared.municipal_sitemap import build_candidate_id, normalize_space

ELECTION_ID = "2002-gruodzio-22-savivaldybiu-tarybu"
SITE_ROOT = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2002/savivaldybes/"
LISTING_URL = SITE_ROOT + "kandidatai/"
PARTIES_URL = SITE_ROOT + "partijos/"

LISTING_FILE_NAME = "list.html"
PARTIES_FILE_NAME = "parties.html"

MUNICIPALITY_PAGE_PATTERN = re.compile(
    r"kandidatai_apygardoje_jsp_ri_id_15_apyg_id_(\d+)\.htm$"
)
PARTY_PAGE_PATTERN = re.compile(
    r"kandidatai_apygardose_jsp_ri_id_15_org_ri_id_(\d+)\.htm$"
)
PARTY_MUNICIPALITY_PAGE_PATTERN = re.compile(
    r"kandidatai_apygardoje_jsp_ri_id_15_apyg_id_(\d+)_org_ri_id_(\d+)\.htm$"
)
ANKETA_PAGE_PATTERN = re.compile(r"kandidatai_anketa_jsp_ri_id_15_asm_kod_(\d+)\.htm$")
DEKLARACIJA_PAGE_PATTERN = re.compile(
    r"kandidatai_deklaracija_jsp_ri_id_15_asm_kod_(\d+)\.htm$"
)
LIST_HEADING_PATTERN = re.compile(r"^(\d+)\.\s*(.+)$")
MUNICIPALITY_HEADING_PATTERN = re.compile(
    r"^Kandidatai\s+(.+?)\s+rinkimų\s+apygardoje$"
)

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

FETCH_PAUSE_SECONDS = 0.3

__all__ = [
    "ELECTION_ID",
    "LISTING_URL",
    "PARTIES_URL",
    "SITE_ROOT",
    "build_sitemap_from_sample",
    "extract_municipality_links",
    "extract_party_links",
    "fetch_listing_sample",
    "load_sitemap_entries",
    "parse_apygarda_page",
    "resolve_site_url",
]


def resolve_site_url(href: str) -> str:
    return urljoin(SITE_ROOT, normalize_space(href))


# ---------------------------------------------------------------------------
# Index pages
# ---------------------------------------------------------------------------


def extract_municipality_links(index_html: str) -> list[dict[str, Any]]:
    """The 60 municipalities of the constituency index: "N.&nbsp;
    <a>name</a>" runs, the number from the text before the link, the
    apygarda id from the link."""
    soup = BeautifulSoup(index_html, "lxml")
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = MUNICIPALITY_PAGE_PATTERN.search(anchor["href"])
        if match is None:
            continue
        apygarda_id = match.group(1)
        if apygarda_id in seen:
            continue
        seen.add(apygarda_id)
        previous = anchor.previous_sibling
        while previous is not None and isinstance(previous, Tag):
            previous = previous.previous_sibling
        number_text = normalize_space(str(previous)) if previous is not None else ""
        number_match = re.search(r"(\d+)\.\s*$", number_text)
        links.append(
            {
                "apygardosId": apygarda_id,
                "number": int(number_match.group(1)) if number_match else None,
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "url": resolve_site_url(anchor["href"]),
            }
        )
    return links


def extract_party_links(index_html: str) -> list[dict[str, Any]]:
    """The party index: VRK's ballot number and name per party, linking
    the party's by-municipality page. The numbering has gaps (no 7) —
    a registered list that never stood keeps its number."""
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
                    "orgId": PARTY_PAGE_PATTERN.search(anchor["href"]).group(1),
                    "number": int(number_text) if number_text.isdigit() else None,
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "url": resolve_site_url(anchor["href"]),
                }
            )
        if links:
            break
    return links


def extract_party_municipality_links(party_html: str) -> list[dict[str, Any]]:
    """One party's by-municipality index: every (apygarda, org) page it
    links."""
    soup = BeautifulSoup(party_html, "lxml")
    links: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for anchor in soup.find_all("a", href=True):
        match = PARTY_MUNICIPALITY_PAGE_PATTERN.search(anchor["href"])
        if match is None:
            continue
        key = (match.group(1), match.group(2))
        if key in seen:
            continue
        seen.add(key)
        links.append(
            {
                "apygardosId": match.group(1),
                "orgId": match.group(2),
                "municipalityName": normalize_space(anchor.get_text(" ", strip=True)),
                "url": resolve_site_url(anchor["href"]),
            }
        )
    return links


# ---------------------------------------------------------------------------
# Candidate listing pages
# ---------------------------------------------------------------------------


def parse_apygarda_page(html: str) -> dict[str, Any]:
    """One candidate-listing page — the constituency page and a party's
    per-municipality page are the same document (the latter narrowed to
    the party's own candidates, a coalition's heading and positions
    unchanged): under each bold "N. <list>" heading, one row per
    candidate with the position, the anketa link and the declaration
    link."""
    soup = BeautifulSoup(html, "lxml")
    heading = soup.find("h1")
    municipality = ""
    if heading is not None:
        match = MUNICIPALITY_HEADING_PATTERN.match(
            normalize_space(heading.get_text(" ", strip=True))
        )
        if match:
            municipality = match.group(1)
    lists: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for tr in soup.find_all("tr"):
        cells = [td for td in tr.find_all("td") if td.find_parent("tr") is tr]
        if not cells:
            continue
        if len(cells) == 1 and cells[0].get("colspan"):
            text = normalize_space(cells[0].get_text(" ", strip=True))
            match = LIST_HEADING_PATTERN.match(text)
            if match:
                current = {
                    "listNumber": int(match.group(1)),
                    "name": normalize_space(match.group(2)),
                    "candidates": [],
                }
                lists.append(current)
            continue
        anchor = None
        for candidate in tr.find_all("a", href=True):
            if ANKETA_PAGE_PATTERN.search(candidate["href"]):
                anchor = candidate
                break
        if anchor is None or current is None:
            continue
        deklaracija_url = None
        for candidate in tr.find_all("a", href=True):
            if DEKLARACIJA_PAGE_PATTERN.search(candidate["href"]):
                deklaracija_url = resolve_site_url(candidate["href"])
                break
        position_text = normalize_space(cells[0].get_text(" ", strip=True)).rstrip(".")
        current["candidates"].append(
            {
                "listPosition": int(position_text) if position_text.isdigit() else None,
                "candidateName": normalize_space(anchor.get_text(" ", strip=True)),
                "vrkCandidateId": ANKETA_PAGE_PATTERN.search(anchor["href"]).group(1),
                "url": resolve_site_url(anchor["href"]),
                "deklaracijaUrl": deklaracija_url,
            }
        )
    return {"municipalityName": municipality, "lists": lists}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def _municipality_sample_path(samples_dir: Path, apygarda_id: str) -> Path:
    return samples_dir / "municipalities" / f"municipality-{apygarda_id}.html"


def _party_sample_path(samples_dir: Path, org_id: str) -> Path:
    return samples_dir / "parties" / f"party-{org_id}.html"


def _party_list_sample_path(samples_dir: Path, apygarda_id: str, org_id: str) -> Path:
    return samples_dir / "party-lists" / f"list-{apygarda_id}-{org_id}.html"


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
    parties_url: str = PARTIES_URL,
) -> Path:
    """Both indexes, the 60 constituency pages, the 25 party pages and
    every party-municipality page they link — skipping files already on
    disk so an interrupted capture resumes."""
    samples_dir.mkdir(parents=True, exist_ok=True)
    listing_html = _fetch_once(samples_dir / LISTING_FILE_NAME, listing_url)
    for municipality in extract_municipality_links(listing_html):
        _fetch_once(
            _municipality_sample_path(samples_dir, municipality["apygardosId"]),
            municipality["url"],
        )
    parties_html = _fetch_once(samples_dir / PARTIES_FILE_NAME, parties_url)
    for party in extract_party_links(parties_html):
        party_html = _fetch_once(_party_sample_path(samples_dir, party["orgId"]), party["url"])
        for link in extract_party_municipality_links(party_html):
            _fetch_once(
                _party_list_sample_path(samples_dir, link["apygardosId"], link["orgId"]),
                link["url"],
            )
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
    municipalities = extract_municipality_links(
        (samples_dir / LISTING_FILE_NAME).read_text(encoding="utf-8")
    )
    parties = extract_party_links((samples_dir / PARTIES_FILE_NAME).read_text(encoding="utf-8"))
    parties_by_number = {party["number"]: party for party in parties}

    # The party pages' overlay: which member party nominated each
    # candidate, and which parties claim each (municipality, list).
    nominations: dict[tuple[str, str], dict[str, Any]] = {}
    claims: dict[tuple[str, int], list[str]] = {}
    double_nominations = 0
    party_position_mismatches = 0
    for party in parties:
        party_html = _party_sample_path(samples_dir, party["orgId"]).read_text(encoding="utf-8")
        for link in extract_party_municipality_links(party_html):
            page = parse_apygarda_page(
                _party_list_sample_path(samples_dir, link["apygardosId"], link["orgId"]).read_text(
                    encoding="utf-8"
                )
            )
            for party_list in page["lists"]:
                key = (link["apygardosId"], party_list["listNumber"])
                claimants = claims.setdefault(key, [])
                if party["name"] not in claimants:
                    claimants.append(party["name"])
                for candidate in party_list["candidates"]:
                    nomination_key = (link["apygardosId"], candidate["vrkCandidateId"])
                    if nomination_key in nominations:
                        double_nominations += 1
                        continue
                    nominations[nomination_key] = {
                        "party": party["name"],
                        "orgId": party["orgId"],
                        "listNumber": party_list["listNumber"],
                        "listPosition": candidate["listPosition"],
                    }

    entries: list[dict[str, Any]] = []
    municipality_pages: list[dict[str, Any]] = []
    heading_name_mismatches = 0
    unclaimed_candidates = 0
    list_count = 0
    coalition_lists = 0
    for municipality in municipalities:
        page = parse_apygarda_page(
            _municipality_sample_path(samples_dir, municipality["apygardosId"]).read_text(
                encoding="utf-8"
            )
        )
        municipality_pages.append(
            {
                "apygardosId": municipality["apygardosId"],
                "number": municipality["number"],
                "name": page["municipalityName"] or municipality["name"],
                "lists": len(page["lists"]),
                "candidates": sum(len(entry["candidates"]) for entry in page["lists"]),
            }
        )
        for party_list in page["lists"]:
            list_count += 1
            claimants = claims.get((municipality["apygardosId"], party_list["listNumber"]), [])
            registered = parties_by_number.get(party_list["listNumber"])
            # One claimant standing under its own name is that party's
            # list; anything else — several claimants, or a heading that
            # is not the claimant's name (A. Zuoko koalicija under the
            # Liberals' number) — is a coalition of the claimants.
            if len(claimants) == 1 and claimants[0] == party_list["name"]:
                kind = "partija"
            else:
                kind = "koalicija"
                coalition_lists += 1
            if registered is not None and kind == "partija" and registered["name"] != party_list["name"]:
                heading_name_mismatches += 1
            list_block: dict[str, Any] = {
                "pavadinimas": party_list["name"],
                "rusis": kind,
                "numeris": party_list["listNumber"],
            }
            if kind == "koalicija":
                list_block["koalicijosPartijos"] = list(claimants)
            for candidate in party_list["candidates"]:
                nomination = nominations.get(
                    (municipality["apygardosId"], candidate["vrkCandidateId"])
                )
                if nomination is None:
                    unclaimed_candidates += 1
                elif nomination["listPosition"] != candidate["listPosition"]:
                    party_position_mismatches += 1
                entry: dict[str, Any] = {
                    "candidateName": candidate["candidateName"],
                    "candidateId": build_candidate_id(
                        candidate["candidateName"], candidate["vrkCandidateId"]
                    ),
                    "url": candidate["url"],
                    "deklaracijaUrl": candidate["deklaracijaUrl"],
                    "vrkCandidateId": candidate["vrkCandidateId"],
                    "municipality": {
                        "pavadinimas": page["municipalityName"] or municipality["name"],
                        "numeris": municipality["number"],
                        "apygardosId": municipality["apygardosId"],
                    },
                    "list": dict(list_block),
                    "listPosition": candidate["listPosition"],
                }
                if kind == "koalicija" and nomination is not None:
                    entry["koalicijosPartija"] = nomination["party"]
                entries.append(entry)

    by_vrk: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_vrk.setdefault(entry["vrkCandidateId"], []).append(entry)
    duplicate_vrk_ids = sum(1 for rows in by_vrk.values() if len(rows) > 1)
    duplicate_candidate_ids = sum(
        1 for _, count in Counter(e["candidateId"] for e in entries).items() if count > 1
    )

    problems: list[str] = []
    if len(municipalities) != 60:
        problems.append(f"{len(municipalities)} municipalities")
    if not entries:
        problems.append("no candidates found")
    if duplicate_candidate_ids:
        problems.append(f"{duplicate_candidate_ids} duplicate candidate ids")
    if problems:
        raise ValueError("Listing did not parse cleanly: " + "; ".join(problems))

    stats = {
        "rows": list_count,
        "extracted": len(entries),
        "skipped": 0,
        "duplicate_candidate_ids": duplicate_candidate_ids,
        "municipalities": len(municipalities),
        "partyLists": list_count,
        "coalitionLists": coalition_lists,
        "parties": len(parties),
        "candidatesClaimedByParties": len(nominations),
        "unclaimedCandidates": unclaimed_candidates,
        "doubleNominations": double_nominations,
        "partyPositionMismatches": party_position_mismatches,
        "headingNameMismatches": heading_name_mismatches,
        "duplicateVrkIds": duplicate_vrk_ids,
        "missingDeklaracijaLinks": sum(1 for e in entries if not e["deklaracijaUrl"]),
    }
    payload = {
        "electionId": ELECTION_ID,
        "sourceUrl": LISTING_URL,
        "partiesUrl": PARTIES_URL,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "stats": {
            k: v
            for k, v in stats.items()
            if k not in ("rows", "extracted", "skipped", "duplicate_candidate_ids")
        },
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
