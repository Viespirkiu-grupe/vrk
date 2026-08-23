from __future__ import annotations

from pathlib import Path
import re
import time
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

# The 2004 Seimas general election — VRK's original static site
# (rinkimai/2004/seimas/, the LRS-ITD template the 2004 EP election shares)
# — is published through the two listing structures the 2008 and 2012
# generals also have, merged on VRK's candidate id:
#
# - part_sar_l_20.htm: the index of the 15 numbered party and coalition
#   lists, plus the parties that ran in constituencies only ("tik
#   vienmandatėse") and the coalitions' member parties ("koalicijos
#   sąrašas Nr. 6/8"), all linking a kand_part_l_<ID>.htm page. A party's
#   page lists *every* nominee of that party — its list in list order, and
#   below the numbered rows, without a number, the people it nominated in
#   a constituency only — so the index's declared count is the party's
#   nominees, not its list size, and an unnumbered row carries no list
#   candidacy. A coalition's page rows the coalition list with each
#   candidate's member party and position on the member party's own list
#   (and no constituency column); a member party's page rows its own list
#   with the coalition position alongside.
# - vapg_sar_l_20.htm: the index of the 71 single-member constituencies,
#   each an apg_kand_l_<ID>.htm page of candidates with the nominator.
#
# The constituency page is the authority on the single-member candidacy:
# a list page's "Vienmandatė apygarda" column shows only constituencies
# where the *same* party nominated the candidate, so a person on one
# party's list and another party's constituency nominee (the Lietuvos rusų
# sąjunga ran its people in constituencies while they sat on the LLRA
# list) has an empty cell there and a row on the constituency page.
from scraper.elections.ep_2004.sitemap import (
    CANDIDATE_ANKETA_PATTERN,
    LIST_LINK_PATTERN,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import assign_positional_ids
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    clean_candidate_name,
    normalize_space,
    resolve_candidate_url,
    utc_now_iso,
)
from scraper.shared.files import slugify, write_json
from scraper.shared.http import fetch_text

ELECTION_ID = "2004-seimo"
LISTING_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/seimas/kandidatai/part_sar_l_20.htm"
DISTRICTS_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/seimas/kandidatai/vapg_sar_l_20.htm"

LISTS_INDEX_NAME = "list.html"
DISTRICTS_INDEX_NAME = "districts.html"
DISTRICT_LINK_PATTERN = re.compile(r"apg_kand_l_(\d+)\.htm$")

SINGLE_MEMBER_ONLY_MARKER = "tik vienmandatėse"
COALITION_MEMBER_MARKER = "koalicijos sąrašas"
SELF_NOMINATED_MARKER = "išsikėlė"

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

FETCH_PAUSE_SECONDS = 0.3

__all__ = [
    "DISTRICTS_URL",
    "ELECTION_ID",
    "LISTING_URL",
    "build_sitemap_from_sample",
    "extract_district_links",
    "extract_party_links",
    "fetch_listing_sample",
    "resolve_candidate_url",
]


# ---------------------------------------------------------------------------
# Page reading
# ---------------------------------------------------------------------------


def _own_rows(table: Tag) -> list[Tag]:
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def _own_cells(tr: Tag) -> list[Tag]:
    return [td for td in tr.find_all("td") if td.find_parent("tr") is tr]


def _headed_table(soup: BeautifulSoup, heading: str) -> tuple[Tag | None, list[str]]:
    """The bordered table whose column names include `heading` — a
    coalition's page has a members table before the candidates."""
    for table in soup.find_all("table", class_="basic"):
        headers = [normalize_space(th.get_text(" ", strip=True)) for th in table.find_all("th")]
        if heading in headers:
            return table, headers
    return None, []


def _keyed_rows(table: Tag, headers: list[str]) -> list[dict[str, Tag]]:
    rows: list[dict[str, Tag]] = []
    for tr in _own_rows(table):
        cells = _own_cells(tr)
        if cells:
            rows.append(dict(zip(headers, cells)))
    return rows


def _anketa_anchor(cell: Tag) -> Tag | None:
    for anchor in cell.find_all("a", href=True):
        if CANDIDATE_ANKETA_PATTERN.search(anchor["href"]):
            return anchor
    return None


def extract_party_links(index_html: str) -> list[dict[str, Any]]:
    """Every row of the list index: the numbered lists, the constituency-only
    parties and the coalition member parties, each with its kind."""
    soup = BeautifulSoup(index_html, "lxml")
    table, headers = _headed_table(soup, "Pavadinimas")
    links: list[dict[str, Any]] = []
    if table is None:
        return links
    for tr in _own_rows(table):
        cells = _own_cells(tr)
        if len(cells) < 3:
            continue
        anchor = None
        for candidate in cells[1].find_all("a", href=True):
            if LIST_LINK_PATTERN.search(candidate["href"]):
                anchor = candidate
                break
        if anchor is None:
            continue
        number_text = normalize_space(cells[0].get_text(" ", strip=True))
        count_text = normalize_space(cells[2].get_text(" ", strip=True))
        if number_text.isdigit():
            kind, list_number, coalition_number = "sarasas", int(number_text), None
        elif SINGLE_MEMBER_ONLY_MARKER in number_text.lower():
            kind, list_number, coalition_number = "tik-vienmandatese", None, None
        elif COALITION_MEMBER_MARKER in number_text.lower():
            match = re.search(r"(\d+)", number_text)
            kind, list_number, coalition_number = "koalicijos-nare", None, int(match.group(1)) if match else None
        else:
            continue
        links.append(
            {
                "listKey": LIST_LINK_PATTERN.search(anchor["href"]).group(1),
                "kind": kind,
                "listNumber": list_number,
                "coalitionListNumber": coalition_number,
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "declaredCount": int(count_text) if count_text.isdigit() else None,
                "url": resolve_candidate_url(normalize_space(anchor["href"])),
            }
        )
    return links


def extract_district_links(index_html: str) -> list[dict[str, Any]]:
    """The 71 constituencies of the index: number, name, page.

    The index is not a table but two cells of "N.&nbsp;<a>name</a><br />"
    runs, so each link's number is the text run right before it.
    """
    soup = BeautifulSoup(index_html, "lxml")
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        if not DISTRICT_LINK_PATTERN.search(anchor["href"]):
            continue
        district_id = DISTRICT_LINK_PATTERN.search(anchor["href"]).group(1)
        if district_id in seen:
            continue
        seen.add(district_id)
        previous = anchor.previous_sibling
        number_text = normalize_space(str(previous)) if isinstance(previous, NavigableString) else ""
        number_text = number_text.rstrip(".").strip()
        links.append(
            {
                "districtId": district_id,
                "number": int(number_text) if number_text.isdigit() else None,
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "url": resolve_candidate_url(normalize_space(anchor["href"])),
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
    # Both indexes and every page they link — the 22 party pages and the 71
    # constituency pages — skipping files already on disk so an interrupted
    # capture resumes.
    samples_dir.mkdir(parents=True, exist_ok=True)
    lists_html = _fetch_once(samples_dir / LISTS_INDEX_NAME, listing_url)
    for link in extract_party_links(lists_html):
        _fetch_once(_list_sample_path(samples_dir, link["listKey"]), link["url"])
    districts_html = _fetch_once(samples_dir / DISTRICTS_INDEX_NAME, districts_url)
    for link in extract_district_links(districts_html):
        _fetch_once(_district_sample_path(samples_dir, link["districtId"]), link["url"])
    return samples_dir


def party_page_records(list_html: str, link: dict[str, Any]) -> list[dict[str, Any]]:
    """The rows of one party or coalition page.

    `position` is the row's number on the page's own list (None for an
    unnumbered row — a constituency-only nominee); `coalitionPosition` the
    coalition-list number a member party's page prints alongside;
    `memberParty`/`memberPosition` what a coalition's page says about each
    candidate's member party and position there; `districtId` the
    constituency the row links, None where the page has no such column
    (a coalition page) or the cell is empty.
    """
    soup = BeautifulSoup(list_html, "lxml")
    table, headers = _headed_table(soup, "Vardas, pavardė")
    records: list[dict[str, Any]] = []
    if table is None:
        return records
    has_district_column = "Vienmandatė apygarda" in headers
    for row in _keyed_rows(table, headers):
        anchor = _anketa_anchor(row["Vardas, pavardė"])
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

        def _int(cell: Tag | None) -> int | None:
            text = normalize_space(cell.get_text(" ", strip=True)) if cell is not None else ""
            return int(text) if text.isdigit() else None

        records.append(
            {
                "vrkCandidateId": CANDIDATE_ANKETA_PATTERN.search(anchor["href"]).group(1),
                "candidateName": clean_candidate_name(anchor.get_text(" ", strip=True)),
                "url": resolve_candidate_url(normalize_space(anchor["href"])),
                "list": link,
                "position": _int(position_cell),
                "coalitionPosition": _int(coalition_cell),
                "memberParty": normalize_space(member_cell.get_text(" ", strip=True)) if member_cell is not None else None,
                "memberPartyKey": LIST_LINK_PATTERN.search(member_anchor["href"]).group(1)
                if member_anchor is not None and LIST_LINK_PATTERN.search(member_anchor["href"])
                else None,
                "memberPosition": _int(member_position_cell),
                "hasDistrictColumn": has_district_column,
                "districtId": DISTRICT_LINK_PATTERN.search(district_anchor["href"]).group(1)
                if district_anchor is not None
                else None,
            }
        )
    return records


def district_records(district_html: str, district: dict[str, Any]) -> list[dict[str, Any]]:
    """The candidates of one constituency page: name, VRK id, nominator —
    a party (linking its page) or "Išsikėlė pats"/"Išsikėlė pati"."""
    soup = BeautifulSoup(district_html, "lxml")
    table, headers = _headed_table(soup, "Vardas, pavardė")
    records: list[dict[str, Any]] = []
    if table is None:
        return records
    heading = soup.find("h4")
    heading_text = normalize_space(heading.get_text(" ", strip=True)) if heading else ""
    for row in _keyed_rows(table, headers):
        anchor = _anketa_anchor(row["Vardas, pavardė"])
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
                "nominatedByKey": LIST_LINK_PATTERN.search(nominator_anchor["href"]).group(1)
                if nominator_anchor is not None and LIST_LINK_PATTERN.search(nominator_anchor["href"])
                else None,
            }
        )
    return records


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
    by_key = {link["listKey"]: link for link in party_links}

    party_rows: dict[str, list[dict[str, Any]]] = {}
    for link in party_links:
        party_rows[link["listKey"]] = party_page_records(
            _list_sample_path(samples_dir, link["listKey"]).read_text(encoding="utf-8"), link
        )
    district_rows: list[dict[str, Any]] = []
    for district in districts:
        district_rows.extend(
            district_records(_district_sample_path(samples_dir, district["districtId"]).read_text(encoding="utf-8"), district)
        )

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
                "roles": [],
            }
            entries_by_vrk_id[vrk_id] = entry
            order.append(vrk_id)
        return entry

    # The numbered lists give the multi-member candidacy: numbered rows
    # only. A coalition's page names the member party and the member
    # position; the member party's own page repeats the coalition position,
    # which is the cross-check.
    declared_mismatches = 0
    unnumbered_on_lists: list[str] = []
    unnumbered_not_in_district: list[str] = []
    member_position_mismatches = 0
    list_claimed_district: dict[str, str | None] = {}
    district_ids_on_pages = {record["vrkCandidateId"] for record in district_rows}
    member_pages_rows: dict[str, dict[str, dict[str, Any]]] = {}
    for link in party_links:
        rows = party_rows[link["listKey"]]
        if link["declaredCount"] is not None and len(rows) != link["declaredCount"]:
            declared_mismatches += 1
        if link["kind"] == "koalicijos-nare":
            member_pages_rows[link["listKey"]] = {row["vrkCandidateId"]: row for row in rows}
    for link in party_links:
        if link["kind"] != "sarasas":
            continue
        for record in party_rows[link["listKey"]]:
            if record["position"] is None:
                unnumbered_on_lists.append(record["vrkCandidateId"])
                if record["vrkCandidateId"] not in district_ids_on_pages:
                    unnumbered_not_in_district.append(record["vrkCandidateId"])
                continue
            entry = _entry_for(record)
            entry["roles"].append("daugiamandate")
            candidacy: dict[str, Any] = {
                "sarasas": link["name"],
                "sarasoNumeris": link["listNumber"],
                "sarasoId": link["listKey"],
                "numerisSarase": record["position"],
            }
            if record["memberParty"]:
                candidacy["koalicijosPartija"] = record["memberParty"]
                candidacy["numerisPartijosSarase"] = record["memberPosition"]
                member_rows = member_pages_rows.get(record["memberPartyKey"] or "", {})
                member_row = member_rows.get(record["vrkCandidateId"])
                if member_row is None or member_row["coalitionPosition"] != record["position"] or member_row["position"] != record["memberPosition"]:
                    member_position_mismatches += 1
            entry["daugiamandateCandidacy"] = candidacy
            if record["hasDistrictColumn"]:
                list_claimed_district[record["vrkCandidateId"]] = record["districtId"]

    duplicate_district_rows = 0
    self_nominated = 0
    for record in district_rows:
        entry = _entry_for(record)
        if "vienmandate" in entry["roles"]:
            duplicate_district_rows += 1
            continue
        entry["roles"].append("vienmandate")
        if SELF_NOMINATED_MARKER in record["nominatedBy"].lower():
            self_nominated += 1
        entry["vienmandateCandidacy"] = {
            "apygarda": record["district"]["pavadinimas"],
            "apygardosNumeris": record["district"]["numeris"],
            "apygardosId": record["district"]["apygardosId"],
            "iskele": record["nominatedBy"] or None,
        }

    entries = [entries_by_vrk_id[vrk_id] for vrk_id in order]
    duplicate_candidate_ids = assign_positional_ids(entries)

    dual = sum(1 for entry in entries if len(entry["roles"]) == 2)
    list_only = sum(1 for entry in entries if entry["roles"] == ["daugiamandate"])
    district_only = sum(1 for entry in entries if entry["roles"] == ["vienmandate"])

    # The list page's constituency column against the constituency pages:
    # a claimed constituency must be the one the candidate is listed in; an
    # empty cell with a constituency row is a nomination by another party
    # (or self-nomination), counted separately because it is the source's
    # own shape, not an error.
    claimed_wrong = 0
    other_party_constituency = 0
    for vrk_id, claimed in list_claimed_district.items():
        actual = (entries_by_vrk_id[vrk_id].get("vienmandateCandidacy") or {}).get("apygardosId")
        if claimed is None and actual is not None:
            other_party_constituency += 1
        elif claimed != actual:
            claimed_wrong += 1

    # District-only candidates are the constituency-only parties' nominees
    # not on any list, the self-nominated not on any list, and the coalition
    # member parties' constituency-only nominees; all three are read from the
    # pages, so the sum must equal the merge's count.
    side_ids: set[str] = set()
    member_only_ids: set[str] = set()
    for link in party_links:
        for record in party_rows[link["listKey"]]:
            if link["kind"] == "tik-vienmandatese":
                side_ids.add(record["vrkCandidateId"])
            elif link["kind"] == "koalicijos-nare" and record["coalitionPosition"] is None:
                member_only_ids.add(record["vrkCandidateId"])
    on_lists = {vrk_id for vrk_id, entry in entries_by_vrk_id.items() if "daugiamandate" in entry["roles"]}
    side_not_on_lists = len(side_ids - on_lists)
    member_only_not_on_lists = len(member_only_ids - on_lists)
    self_nominated_district_only = sum(
        1
        for record in district_rows
        if SELF_NOMINATED_MARKER in record["nominatedBy"].lower()
        and entries_by_vrk_id[record["vrkCandidateId"]]["roles"] == ["vienmandate"]
    )
    # Constituency-only nominees of the numbered-list parties (their
    # unnumbered rows) that are not otherwise accounted for.
    numbered_party_only = sum(
        1
        for vrk_id in unnumbered_on_lists
        if entries_by_vrk_id.get(vrk_id, {}).get("roles") == ["vienmandate"]
        and vrk_id not in side_ids
        and vrk_id not in member_only_ids
    )
    district_only_reconciled = district_only == (
        side_not_on_lists + member_only_not_on_lists + self_nominated_district_only + numbered_party_only
    )

    payload = {
        "electionId": election_id,
        "sourceUrl": listing_url,
        "districtsUrl": districts_url,
        "listUrls": [link["url"] for link in party_links if link["kind"] == "sarasas"],
        "sidePageUrls": [link["url"] for link in party_links if link["kind"] != "sarasas"],
        "districtUrls": [district["url"] for district in districts],
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": sum(len(rows) for rows in party_rows.values()) + len(district_rows),
            "extracted": len(entries),
            "duplicateCandidateIds": duplicate_candidate_ids,
            "lists": sum(1 for link in party_links if link["kind"] == "sarasas"),
            "sidePages": sum(1 for link in party_links if link["kind"] != "sarasas"),
            "districts": len(districts),
            "dual": dual,
            "listOnly": list_only,
            "districtOnly": district_only,
            "declaredCountMismatches": declared_mismatches,
            "unnumberedRowsOnLists": len(unnumbered_on_lists),
            "unnumberedRowsNotInAnyConstituency": len(unnumbered_not_in_district),
            "memberPositionMismatches": member_position_mismatches,
            "listColumnConstituencyWrong": claimed_wrong,
            "constituencyByAnotherNominator": other_party_constituency,
            "duplicateDistrictRows": duplicate_district_rows,
            "selfNominated": self_nominated,
            "districtOnlyReconciled": district_only_reconciled,
        },
        "entries": entries,
    }
    write_json(output_path, payload)
    stats = dict(payload["stats"])
    # The CLI's summary line reads these three by the era's names.
    stats["skipped"] = len(unnumbered_not_in_district)
    stats["duplicate_candidate_ids"] = duplicate_candidate_ids
    return output_path, stats
