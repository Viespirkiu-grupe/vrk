"""Sitemap building for the 2000-10-08 Seimas general election.

VRK's 2000 site is the last of the LRS-ITD Oracle-CGI captures
(``statiniai/puslapiai/n/rinkimai/20001008/``), the same template as the
1996-1998 Seimas archive (``scraper/shared/seimo_archive_1990s.py``) with
the ``kandvl.htm-<ID>.htm`` candidate page, but published through the two
listing structures the 2004, 2008 and 2012 generals have:

- ``partsarl.htm-13.htm`` — the index of the 15 numbered lists and, below
  them without a number, the 13 parties that "kandidatų daugiamandatėje
  apygardoje išvis nekelia arba dalyvauja koalicijoje", all linking a
  ``kandpartl.htm-<ID>.htm`` page. A party's page lists every nominee of
  the party — its list in list order, then its constituency-only nominees
  as unnumbered rows — with the constituency column. A coalition's page
  rows the coalition list with each candidate's member party and position
  on the member party's own list and names the member parties above the
  table; a member party's page names its coalition above its own list and
  carries the coalition position alongside. Which of the unnumbered
  parties are coalition members is said only on those pages (the 2004
  index says it in the number column), so the index's kinds are
  resolved after the pages are read.
- ``kandapgsarl.htm-13.htm`` — the 71 constituencies, each a
  ``kandapgl.htm-13+<number>+<ID>.htm`` page of candidates with the
  nominator (a party, linking its page, or "Išsikėlė pats/pati").

The two structures merge on VRK's candidate id through
``seimo_2004.sitemap.merge_listing_records``, whose record shapes the
readers here produce; the constituency page is the authority on the
single-member candidacy (a list page's constituency column shows only the
same party's nominations).
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from scraper.elections.seimo_2004.sitemap import (
    merge_listing_records,
    write_two_structure_sitemap,
)
from scraper.shared.http import fetch_text
from scraper.shared.seimo_archive_1990s import normalize_space

ELECTION_ID = "2000-seimo"
SITE_ROOT = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/20001008/"
LISTING_URL = SITE_ROOT + "partsarl.htm-13.htm"
DISTRICTS_URL = SITE_ROOT + "kandapgsarl.htm-13.htm"

LISTS_INDEX_NAME = "list.html"
DISTRICTS_INDEX_NAME = "districts.html"

CANDIDATE_PAGE_PATTERN = re.compile(r"kandvl\.htm-(\d+)\.htm$")
LIST_LINK_PATTERN = re.compile(r"kandpartl\.htm-(\d+)\.htm$")
DISTRICT_LINK_PATTERN = re.compile(r"kandapgl\.htm-13\+(\d+)\+(\d+)\.htm$")

COALITION_MEMBERS_MARKER = "dalyvaujančios koalicijoje"
MEMBER_OF_COALITION_MARKER = "koalicija, kurioje partija dalyvauja"

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

FETCH_PAUSE_SECONDS = 0.3

__all__ = [
    "DISTRICTS_URL",
    "ELECTION_ID",
    "LISTING_URL",
    "SITE_ROOT",
    "build_sitemap_from_sample",
    "district_records",
    "extract_district_links",
    "extract_party_links",
    "fetch_listing_sample",
    "party_page_records",
    "resolve_site_url",
]


def resolve_site_url(href: str) -> str:
    return urljoin(SITE_ROOT, normalize_space(href))


# ---------------------------------------------------------------------------
# Page reading
# ---------------------------------------------------------------------------


def _own_rows(table: Tag) -> list[Tag]:
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def _own_cells(tr: Tag) -> list[Tag]:
    return [td for td in tr.find_all("td") if td.find_parent("tr") is tr]


def _header_label(cell: Tag) -> str:
    # "Numeris sąraše *", "Vienmandatė apygarda **": the footnote marks are
    # not part of the column name.
    return normalize_space(cell.get_text(" ", strip=True)).replace("*", "").strip()


def _headed_table(soup: BeautifulSoup, heading: str) -> tuple[Tag | None, list[str]]:
    """The bordered table whose first row's column names include
    `heading`. These pages have no <th>: the header row is the first
    grey-shaded row of bold cells."""
    for table in soup.find_all("table", border="1"):
        rows = _own_rows(table)
        if not rows:
            continue
        headers = [_header_label(td) for td in _own_cells(rows[0])]
        if heading in headers:
            return table, headers
    return None, []


def _keyed_rows(table: Tag, headers: list[str]) -> list[dict[str, Tag]]:
    rows: list[dict[str, Tag]] = []
    for tr in _own_rows(table)[1:]:
        cells = _own_cells(tr)
        if cells:
            rows.append(dict(zip(headers, cells)))
    return rows


def _candidate_anchor(cell: Tag) -> Tag | None:
    for anchor in cell.find_all("a", href=True):
        if CANDIDATE_PAGE_PATTERN.search(anchor["href"]):
            return anchor
    return None


def _int(cell: Tag | None) -> int | None:
    text = normalize_space(cell.get_text(" ", strip=True)) if cell is not None else ""
    text = text.rstrip(".").strip()
    return int(text) if text.isdigit() else None


def extract_party_links(index_html: str) -> list[dict[str, Any]]:
    """Every row of the list index, in page order. A numbered row is a
    list (`sarasas`); an unnumbered row's kind is not known from the index
    — it is a coalition member or a constituency-only party — and is
    settled by `resolve_party_kinds` once the pages are read."""
    soup = BeautifulSoup(index_html, "lxml")
    table, headers = _headed_table(soup, "Pavadinimas")
    links: list[dict[str, Any]] = []
    if table is None:
        return links
    for tr in _own_rows(table)[1:]:
        cells = _own_cells(tr)
        if len(cells) < 2:
            continue
        anchor = None
        for candidate in cells[1].find_all("a", href=True):
            if LIST_LINK_PATTERN.search(candidate["href"]):
                anchor = candidate
                break
        if anchor is None:
            continue
        number = _int(cells[0])
        links.append(
            {
                "listKey": LIST_LINK_PATTERN.search(anchor["href"]).group(1),
                "kind": "sarasas" if number is not None else "nenumeruota",
                "listNumber": number,
                "coalitionListNumber": None,
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                # The 2000 index prints no nominee count.
                "declaredCount": None,
                "url": resolve_site_url(anchor["href"]),
            }
        )
    return links


def extract_district_links(index_html: str) -> list[dict[str, Any]]:
    """The 71 constituencies: number and VRK id from the link itself,
    the name from its text. The index is "N.&nbsp;<a>name</a>" runs."""
    soup = BeautifulSoup(index_html, "lxml")
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = DISTRICT_LINK_PATTERN.search(anchor["href"])
        if match is None:
            continue
        number, district_id = int(match.group(1)), match.group(2)
        if district_id in seen:
            continue
        seen.add(district_id)
        links.append(
            {
                "districtId": district_id,
                "number": number,
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "url": resolve_site_url(anchor["href"]),
            }
        )
    return links


def _list_sample_path(samples_dir: Path, list_key: str) -> Path:
    return samples_dir / "lists" / f"list-{list_key}.html"


def _district_sample_path(samples_dir: Path, district_id: str) -> Path:
    return samples_dir / "districts" / f"district-{district_id}.html"


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
    districts_url: str = DISTRICTS_URL,
) -> Path:
    # Both indexes and every page they link — the 28 party pages and the
    # 71 constituency pages — skipping files already on disk so an
    # interrupted capture resumes.
    samples_dir.mkdir(parents=True, exist_ok=True)
    lists_html = _fetch_once(samples_dir / LISTS_INDEX_NAME, listing_url)
    for link in extract_party_links(lists_html):
        _fetch_once(_list_sample_path(samples_dir, link["listKey"]), link["url"])
    districts_html = _fetch_once(samples_dir / DISTRICTS_INDEX_NAME, districts_url)
    for link in extract_district_links(districts_html):
        _fetch_once(_district_sample_path(samples_dir, link["districtId"]), link["url"])
    return samples_dir


def _linked_list_keys_after(soup: BeautifulSoup, marker: str) -> list[str]:
    """The list keys linked in the paragraph whose text starts with
    `marker` ("Partijos ir politinės organizacijos, dalyvaujančios
    koalicijoje:" on a coalition's page, "Koalicija, kurioje partija
    dalyvauja:" on a member's)."""
    for paragraph in soup.find_all("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True)).lower()
        if marker in text:
            keys: list[str] = []
            for anchor in paragraph.find_all("a", href=True):
                match = LIST_LINK_PATTERN.search(anchor["href"])
                if match is not None:
                    keys.append(match.group(1))
            return keys
    return []


def party_page_coalition(list_html: str) -> dict[str, Any]:
    """What a party page says about coalitions: the member parties it
    lists (a coalition's page) or the coalition it belongs to (a member's)."""
    soup = BeautifulSoup(list_html, "lxml")
    return {
        "memberKeys": _linked_list_keys_after(soup, COALITION_MEMBERS_MARKER),
        "coalitionKeys": _linked_list_keys_after(soup, MEMBER_OF_COALITION_MARKER),
    }


def party_page_records(list_html: str, link: dict[str, Any]) -> list[dict[str, Any]]:
    """The rows of one party or coalition page, in the shape
    `seimo_2004.sitemap.party_page_records` gives: `position` the row's
    number on the page's own list (None for an unnumbered row — a
    constituency-only nominee), `coalitionPosition` the coalition-list
    number a member party's page prints alongside, `memberParty` /
    `memberPartyKey` / `memberPosition` what a coalition's page says about
    each candidate, `districtId` the constituency the row links."""
    soup = BeautifulSoup(list_html, "lxml")
    table, headers = _headed_table(soup, "Pavardė, vardas")
    records: list[dict[str, Any]] = []
    if table is None:
        return records
    has_district_column = "Vienmandatė apygarda" in headers
    for row in _keyed_rows(table, headers):
        anchor = _candidate_anchor(row["Pavardė, vardas"])
        if anchor is None:
            continue
        position_cell = row.get("Numeris sąraše")
        coalition_cell = row.get("Numeris koalicijos sąraše")
        member_position_cell = row.get("Numeris partijos sąraše")
        if position_cell is None and coalition_cell is not None and member_position_cell is not None:
            # A coalition's own page: the coalition number is the position.
            position_cell, coalition_cell = coalition_cell, None
        district_cell = row.get("Vienmandatė apygarda")
        district_anchor = None
        if district_cell is not None:
            for candidate in district_cell.find_all("a", href=True):
                if DISTRICT_LINK_PATTERN.search(candidate["href"]):
                    district_anchor = candidate
                    break
        member_cell = row.get("Iškėlė")
        member_anchor = member_cell.find("a", href=True) if member_cell is not None else None
        records.append(
            {
                "vrkCandidateId": CANDIDATE_PAGE_PATTERN.search(anchor["href"]).group(1),
                "candidateName": normalize_space(anchor.get_text(" ", strip=True)),
                "url": resolve_site_url(anchor["href"]),
                "list": link,
                "position": _int(position_cell),
                "coalitionPosition": _int(coalition_cell),
                "memberParty": normalize_space(member_cell.get_text(" ", strip=True)) if member_cell is not None else None,
                "memberPartyKey": LIST_LINK_PATTERN.search(member_anchor["href"]).group(1)
                if member_anchor is not None and LIST_LINK_PATTERN.search(member_anchor["href"])
                else None,
                "memberPosition": _int(member_position_cell),
                "hasDistrictColumn": has_district_column,
                "districtId": DISTRICT_LINK_PATTERN.search(district_anchor["href"]).group(2)
                if district_anchor is not None
                else None,
            }
        )
    return records


def district_records(district_html: str, district: dict[str, Any]) -> list[dict[str, Any]]:
    """The candidates of one constituency page: name, VRK id, nominator —
    a party (linking its page) or "Išsikėlė pats"/"Išsikėlė pati"."""
    soup = BeautifulSoup(district_html, "lxml")
    table, headers = _headed_table(soup, "Iškėlė")
    records: list[dict[str, Any]] = []
    if table is None:
        return records
    heading = ""
    for font in soup.find_all("font", attrs={"size": "5"}):
        text = normalize_space(font.get_text(" ", strip=True))
        if "apygarda" in text.lower():
            heading = text
            break
    for row in _keyed_rows(table, headers):
        anchor = _candidate_anchor(row["Pavardė, vardas"])
        if anchor is None:
            continue
        nominator_cell = row.get("Iškėlė")
        nominator = normalize_space(nominator_cell.get_text(" ", strip=True)) if nominator_cell is not None else ""
        nominator_anchor = nominator_cell.find("a", href=True) if nominator_cell is not None else None
        records.append(
            {
                "vrkCandidateId": CANDIDATE_PAGE_PATTERN.search(anchor["href"]).group(1),
                "candidateName": normalize_space(anchor.get_text(" ", strip=True)),
                "url": resolve_site_url(anchor["href"]),
                "district": {
                    "pavadinimas": district["name"],
                    "numeris": district["number"],
                    "apygardosId": district["districtId"],
                    "antraste": heading,
                },
                "nominatedBy": nominator,
                "nominatedByKey": LIST_LINK_PATTERN.search(nominator_anchor["href"]).group(1)
                if nominator_anchor is not None and LIST_LINK_PATTERN.search(nominator_anchor["href"])
                else None,
            }
        )
    return records


def resolve_party_kinds(
    party_links: list[dict[str, Any]],
    coalition_facts: dict[str, dict[str, Any]],
) -> dict[str, int]:
    """Settle the unnumbered index rows' kinds from their pages.

    A party whose page names the coalition it belongs to is a
    `koalicijos-nare` (with the coalition's list number); any other
    unnumbered party is `tik-vienmandatese`. Returns the reconciliation
    counts: a member naming a coalition that does not name it back, or a
    coalition naming a member that is not an unnumbered index row.
    """
    by_key = {link["listKey"]: link for link in party_links}
    unreciprocated = 0
    for link in party_links:
        if link["kind"] != "nenumeruota":
            continue
        facts = coalition_facts.get(link["listKey"], {})
        coalition_keys = facts.get("coalitionKeys") or []
        if coalition_keys:
            coalition = by_key.get(coalition_keys[0])
            link["kind"] = "koalicijos-nare"
            link["coalitionListNumber"] = coalition["listNumber"] if coalition else None
            members = (coalition_facts.get(coalition_keys[0], {}).get("memberKeys") if coalition else None) or []
            if link["listKey"] not in members:
                unreciprocated += 1
        else:
            link["kind"] = "tik-vienmandatese"
    members_not_in_index = 0
    for link in party_links:
        for member_key in coalition_facts.get(link["listKey"], {}).get("memberKeys") or []:
            member = by_key.get(member_key)
            if member is None or member["kind"] != "koalicijos-nare":
                members_not_in_index += 1
    return {
        "coalitionLinksUnreciprocated": unreciprocated,
        "coalitionMembersNotInIndex": members_not_in_index,
    }


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
    election_id: str = ELECTION_ID,
    listing_url: str = LISTING_URL,
    districts_url: str = DISTRICTS_URL,
) -> tuple[Path, dict[str, int]]:
    # sample_path keeps the CLI's signature; it names the samples directory.
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    party_links = extract_party_links((samples_dir / LISTS_INDEX_NAME).read_text(encoding="utf-8"))
    districts = extract_district_links((samples_dir / DISTRICTS_INDEX_NAME).read_text(encoding="utf-8"))

    party_rows: dict[str, list[dict[str, Any]]] = {}
    coalition_facts: dict[str, dict[str, Any]] = {}
    for link in party_links:
        html = _list_sample_path(samples_dir, link["listKey"]).read_text(encoding="utf-8")
        party_rows[link["listKey"]] = party_page_records(html, link)
        coalition_facts[link["listKey"]] = party_page_coalition(html)
    kind_stats = resolve_party_kinds(party_links, coalition_facts)

    district_rows: list[dict[str, Any]] = []
    for district in districts:
        district_rows.extend(
            district_records(_district_sample_path(samples_dir, district["districtId"]).read_text(encoding="utf-8"), district)
        )

    entries, merge_stats = merge_listing_records(party_links, party_rows, district_rows)
    merge_stats.update(kind_stats)
    return write_two_structure_sitemap(
        output_path,
        election_id=election_id,
        listing_url=listing_url,
        districts_url=districts_url,
        party_links=party_links,
        districts=districts,
        entries=entries,
        merge_stats=merge_stats,
    )


def load_sitemap_entries(sitemap_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(sitemap_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"No sitemap entries found in {sitemap_path}")
    return entries
