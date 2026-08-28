"""Listing walk of the 2003-06-15 new Seimas election (GitHub issue #29).

Four seats fell vacant in the 2000-2004 Seimas and VRK ran one vote for
all of them on June 15, 2003 — Senamiesčio Nr. 2, Antakalnio Nr. 3,
Šeškinės Nr. 6 and Nevėžio Nr. 26. Twenty-seven candidates, every one
nominated by a party (nobody self-nominated), no list seats and so no
multi-member candidacy.

The tree is ``rinkimai/2003/seimas/``, the 2004 static site one year
early: the same page furniture, but the pages are the servlet's own
names (``w3_smn_kand.<view>_l-id=<ID>.htm``) rather than 2004's
``<view>_l_<ID>.htm``, and the candidate table is ``table.smn`` with
``<th>`` headings rather than ``table.basic``. Two listing structures,
neither of which adds a fact the other lacks:

    kandidatai/w3_smn_kand.kand_vien_l-p_ri_id=17.htm   the four constituencies
    kandidatai/w3_smn_kand.apg_kand_vien_l-id=<APG>.htm one constituency:
        name linking the anketa, "Iškėlė" linking the party
    kandidatai/w3_smn_kand.part_sar_l-p_ri_id=17.htm    the 12 parties
    kandidatai/w3_smn_kand.kand_part_l-id=<ORG>.htm     one party's nominees,
        each with the constituency they stood in

So the constituencies are the source and the party pages the cross-check:
the two sets of (candidate, constituency, party) triples must agree
exactly, which is what ``partyPageDiff`` counts.
"""
from __future__ import annotations

from pathlib import Path
import re
import time
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import assign_positional_ids
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    clean_candidate_name,
    normalize_space,
    resolve_candidate_url,
    utc_now_iso,
)
from scraper.shared.files import slugify, write_json
from scraper.shared.http import fetch_text

ELECTION_ID = "2003-birzelio-15-seimo-nauji"
SITE_ROOT = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2003/seimas/"
CANDIDATES_ROOT = SITE_ROOT + "kandidatai/"
DISTRICTS_URL = CANDIDATES_ROOT + "w3_smn_kand.kand_vien_l-p_ri_id=17.htm"
PARTIES_URL = CANDIDATES_ROOT + "w3_smn_kand.part_sar_l-p_ri_id=17.htm"
LISTING_URL = DISTRICTS_URL

DISTRICTS_INDEX_NAME = "districts.html"
PARTIES_INDEX_NAME = "list.html"

DISTRICT_LINK_PATTERN = re.compile(r"apg_kand_vien_l-id=(\d+)\.htm$")
PARTY_LINK_PATTERN = re.compile(r"kand_part_l-id=(\d+)\.htm$")
CANDIDATE_ANKETA_PATTERN = re.compile(r"kand_anketa_l-id=(\d+)\.htm$")
# "Senamiesčio (Nr. 2) apygarda" — the constituency page's own heading, and
# "Senamiesčio (Nr.2)" as the party pages and the profile card write it.
DISTRICT_HEADING_PATTERN = re.compile(r"^(.*?)\s*\(Nr\.\s*(\d+)\)")

SELF_NOMINATED_MARKER = "išsikėlė"

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

FETCH_PAUSE_SECONDS = 0.3

__all__ = [
    "CANDIDATE_ANKETA_PATTERN",
    "DISTRICTS_URL",
    "ELECTION_ID",
    "LISTING_URL",
    "PARTIES_URL",
    "SITE_ROOT",
    "build_sitemap_from_sample",
    "district_records",
    "extract_district_links",
    "extract_party_links",
    "fetch_listing_sample",
    "party_page_records",
    "resolve_candidate_url",
]


# ---------------------------------------------------------------------------
# Index pages
# ---------------------------------------------------------------------------


def _candidate_table(soup: BeautifulSoup, heading: str) -> tuple[Tag | None, list[str]]:
    """The bordered ``table.smn`` whose ``<th>`` headings include `heading`."""
    for table in soup.find_all("table", class_="smn"):
        headers = [normalize_space(th.get_text(" ", strip=True)) for th in table.find_all("th")]
        if heading in headers:
            return table, headers
    return None, []


def _keyed_rows(table: Tag, headers: list[str]) -> list[dict[str, Tag]]:
    rows: list[dict[str, Tag]] = []
    for tr in table.find_all("tr"):
        cells = [td for td in tr.find_all("td") if td.find_parent("tr") is tr]
        if cells:
            rows.append(dict(zip(headers, cells)))
    return rows


def _district_facts(name: str, number_text: str) -> dict[str, Any]:
    return {
        "name": normalize_space(name),
        "number": int(number_text) if number_text.isdigit() else None,
    }


def extract_district_links(index_html: str) -> list[dict[str, Any]]:
    """The four constituencies of the index.

    The index is a one-row table of "N&nbsp;<a><b>name</b></a>" cells — the
    number is the text run before the link, with no trailing dot (2004's
    index writes "N."), so it is stripped either way.
    """
    soup = BeautifulSoup(index_html, "lxml")
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = DISTRICT_LINK_PATTERN.search(anchor["href"])
        if match is None or match.group(1) in seen:
            continue
        seen.add(match.group(1))
        previous = anchor.previous_sibling
        number_text = normalize_space(str(previous)) if isinstance(previous, NavigableString) else ""
        number_text = number_text.rstrip(".").strip()
        facts = _district_facts(anchor.get_text(" ", strip=True), number_text)
        links.append(
            {
                "districtId": match.group(1),
                "number": facts["number"],
                "name": facts["name"],
                "url": resolve_candidate_url(normalize_space(anchor["href"])),
            }
        )
    return links


def extract_party_links(index_html: str) -> list[dict[str, Any]]:
    """The 12 nominating parties. The index states no candidate counts —
    that is what the party pages are read for."""
    soup = BeautifulSoup(index_html, "lxml")
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = PARTY_LINK_PATTERN.search(anchor["href"])
        if match is None or match.group(1) in seen:
            continue
        seen.add(match.group(1))
        links.append(
            {
                "listKey": match.group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "url": resolve_candidate_url(normalize_space(anchor["href"])),
            }
        )
    return links


# ---------------------------------------------------------------------------
# Candidate rows
# ---------------------------------------------------------------------------


def district_records(district_html: str, district: dict[str, Any]) -> list[dict[str, Any]]:
    """The candidates of one constituency page: name, VRK id, nominator."""
    soup = BeautifulSoup(district_html, "lxml")
    table, headers = _candidate_table(soup, "Vardas, pavardė")
    records: list[dict[str, Any]] = []
    if table is None:
        return records
    heading = soup.find("h1")
    heading_text = normalize_space(heading.get_text(" ", strip=True)) if heading else ""
    for row in _keyed_rows(table, headers):
        cell = row.get("Vardas, pavardė")
        anchor = _anketa_anchor(cell) if cell is not None else None
        if anchor is None:
            continue
        nominator_cell = row.get("Iškėlė")
        nominator = normalize_space(nominator_cell.get_text(" ", strip=True)) if nominator_cell is not None else ""
        nominator_anchor = nominator_cell.find("a", href=True) if nominator_cell is not None else None
        records.append(
            {
                "vrkCandidateId": CANDIDATE_ANKETA_PATTERN.search(anchor["href"]).group(1),
                "candidateName": clean_candidate_name(anchor.get_text(" ", strip=True)),
                "url": resolve_candidate_url(normalize_space(anchor["href"])),
                "district": {
                    "pavadinimas": district["name"],
                    "numeris": district["number"],
                    "apygardosId": district["districtId"],
                    "antraste": heading_text,
                },
                "nominatedBy": nominator,
                "nominatedByKey": PARTY_LINK_PATTERN.search(nominator_anchor["href"]).group(1)
                if nominator_anchor is not None and PARTY_LINK_PATTERN.search(nominator_anchor["href"])
                else None,
            }
        )
    return records


def party_page_records(party_html: str, link: dict[str, Any]) -> list[dict[str, Any]]:
    """One party's nominees: name, VRK id and the constituency they stood
    in ("Senamiesčio (Nr.2)", linking the constituency page)."""
    soup = BeautifulSoup(party_html, "lxml")
    table, headers = _candidate_table(soup, "Vardas, pavardė")
    records: list[dict[str, Any]] = []
    if table is None:
        return records
    for row in _keyed_rows(table, headers):
        cell = row.get("Vardas, pavardė")
        anchor = _anketa_anchor(cell) if cell is not None else None
        if anchor is None:
            continue
        district_cell = row.get("Vienmandatė apygarda")
        district_anchor = district_cell.find("a", href=True) if district_cell is not None else None
        district_id = None
        if district_anchor is not None:
            match = DISTRICT_LINK_PATTERN.search(district_anchor["href"])
            district_id = match.group(1) if match else None
        records.append(
            {
                "vrkCandidateId": CANDIDATE_ANKETA_PATTERN.search(anchor["href"]).group(1),
                "candidateName": clean_candidate_name(anchor.get_text(" ", strip=True)),
                "listKey": link["listKey"],
                "party": link["name"],
                "apygardosId": district_id,
            }
        )
    return records


def _anketa_anchor(cell: Tag) -> Tag | None:
    for anchor in cell.find_all("a", href=True):
        if CANDIDATE_ANKETA_PATTERN.search(anchor["href"]):
            return anchor
    return None


# ---------------------------------------------------------------------------
# Sample capture
# ---------------------------------------------------------------------------


def _district_sample_path(samples_dir: Path, district_id: str) -> Path:
    return samples_dir / "districts" / f"district-{district_id}.html"


def _list_sample_path(samples_dir: Path, list_key: str) -> Path:
    return samples_dir / "lists" / f"list-{list_key}.html"


def _fetch_once(path: Path, url: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    html = fetch_text(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    time.sleep(FETCH_PAUSE_SECONDS)
    return html


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    # Both indexes and every page they link — four constituencies and 12
    # parties — skipping files already on disk so an interrupted capture
    # resumes.
    samples_dir.mkdir(parents=True, exist_ok=True)
    districts_html = _fetch_once(samples_dir / DISTRICTS_INDEX_NAME, DISTRICTS_URL)
    for link in extract_district_links(districts_html):
        _fetch_once(_district_sample_path(samples_dir, link["districtId"]), link["url"])
    parties_html = _fetch_once(samples_dir / PARTIES_INDEX_NAME, PARTIES_URL)
    for link in extract_party_links(parties_html):
        _fetch_once(_list_sample_path(samples_dir, link["listKey"]), link["url"])
    return samples_dir


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, Any]]:
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    districts = extract_district_links((samples_dir / DISTRICTS_INDEX_NAME).read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for district in districts:
        records.extend(
            district_records(
                _district_sample_path(samples_dir, district["districtId"]).read_text(encoding="utf-8"),
                district,
            )
        )

    entries: list[dict[str, Any]] = []
    for record in records:
        entries.append(
            {
                "candidateName": record["candidateName"],
                "candidateId": slugify(record["candidateName"]),
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

    parties_path = samples_dir / PARTIES_INDEX_NAME
    parties = extract_party_links(parties_path.read_text(encoding="utf-8")) if parties_path.exists() else []
    party_rows: list[dict[str, Any]] = []
    for link in parties:
        path = _list_sample_path(samples_dir, link["listKey"])
        if path.exists():
            party_rows.extend(party_page_records(path.read_text(encoding="utf-8"), link))

    # The cross-check: the same (candidate, constituency, party) triples,
    # read off the other structure. Anything in one set and not the other
    # is a listing the walk has misread.
    from_districts = {
        (record["vrkCandidateId"], record["district"]["apygardosId"], record["nominatedBy"])
        for record in records
    }
    from_parties = {(row["vrkCandidateId"], row["apygardosId"], row["party"]) for row in party_rows}

    payload = {
        "electionId": ELECTION_ID,
        "sourceUrl": DISTRICTS_URL,
        "districtsUrl": DISTRICTS_URL,
        "partiesUrl": PARTIES_URL,
        "districtUrls": [district["url"] for district in districts],
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": len(records),
            "extracted": len(entries),
            "duplicateCandidateIds": duplicate_candidate_ids,
            "districts": len(districts),
            "parties": len(parties),
            "partyPageRows": len(party_rows),
            "partyPageDiff": len(from_districts ^ from_parties),
            "selfNominated": sum(
                1
                for entry in entries
                if SELF_NOMINATED_MARKER in (entry["vienmandateCandidacy"]["iskele"] or "").lower()
            ),
        },
        "entries": entries,
    }
    write_json(output_path, payload)
    stats = dict(payload["stats"])
    stats["skipped"] = 0
    stats["duplicate_candidate_ids"] = duplicate_candidate_ids
    return output_path, stats
