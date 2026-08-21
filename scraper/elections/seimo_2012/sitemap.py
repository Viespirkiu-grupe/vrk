from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup

import time

from scraper.elections.ep_2014.sitemap import (
    FETCH_PAUSE_SECONDS,
    LIST_LINK_PATTERN,
    _list_sample_path,
    collect_list_records,
    fetch_listing_sample as _fetch_lists_sample,
    list_candidacy,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import (
    DISTRICT_LINK_PATTERN,
    assign_positional_ids,
    collect_district_records,
    fetch_listing_sample as _fetch_districts_sample,
)
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    normalize_space,
    resolve_candidate_url,
    utc_now_iso,
)
from scraper.shared.files import slugify, write_json
from scraper.shared.http import fetch_text

ELECTION_ID = "2012-seimo"
# VRK election 416, the pre-2016 static layout family, published through two
# listing structures that merge on VRK's own candidate id:
#
# - KandidatuSarasai/index.html: the 18 numbered party and coalition lists
#   (the multi-member constituency), each a page of candidates in list
#   order. The same table also rows the coalition's member parties
#   ("koalicijos sąrašas Nr. 10", subsets of list 10) and the parties that
#   ran only in single-member constituencies ("tik vienmandatėse", with the
#   self-nominated under RinkimuOrganizacija_Issikele.html); neither is a
#   list of its own, and both are used here only as cross-checks.
# - Kandidatai/index.html: the 71 single-member constituencies, each a page
#   of candidates with the nominating party.
#
# Most list candidates also stood in a constituency and most constituency
# candidates were on a list; one sitemap entry carries both candidacies.
LISTING_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/416_lt/KandidatuSarasai/index.html"
DISTRICTS_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/416_lt/Kandidatai/index.html"

LISTS_INDEX_NAME = "list.html"
DISTRICTS_INDEX_NAME = "districts.html"

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

SINGLE_MEMBER_ONLY_MARKER = "tik vienmandatėse"
COALITION_MEMBER_MARKER = "koalicijos sąrašas"
COALITION_MEMBER_LINK_PATTERN = re.compile(r"RinkimuOrganizacija(\d+)_3\.html$")
SELF_NOMINATED_PAGE = "RinkimuOrganizacija_Issikele.html"
# Any constituency link, including the empty "Apygardanull" one a list page
# renders for a list-only candidate; its presence says the page has a
# constituency column at all (the coalition list page does not).
ANY_DISTRICT_LINK_PATTERN = re.compile(r"KandidataiApygardos(\d+|null)\.html$")


def fetch_listing_sample(
    samples_dir: Path = DEFAULT_SAMPLES_DIR,
) -> Path:
    _fetch_lists_sample(samples_dir=samples_dir, listing_url=LISTING_URL, index_name=LISTS_INDEX_NAME)
    _fetch_districts_sample(
        samples_dir=samples_dir, listing_url=DISTRICTS_URL, index_name=DISTRICTS_INDEX_NAME
    )
    fetch_side_pages(samples_dir, (samples_dir / LISTS_INDEX_NAME).read_text(encoding="utf-8"))
    return samples_dir


def _side_list_key(href: str) -> str:
    if href.endswith(SELF_NOMINATED_PAGE):
        return "issikele"
    match = LIST_LINK_PATTERN.search(href)
    if match is None:
        return slugify(href)[-40:]
    return match.group(1) if match.group(2) is None else f"{match.group(1)}-{match.group(2)}"


def extract_side_links(index_html: str) -> list[dict[str, Any]]:
    """The index rows that are not lists of their own: coalition member
    parties (subsets of the coalition's list) and the parties that ran only
    in single-member constituencies, with the counts VRK declares."""
    soup = BeautifulSoup(index_html, "lxml")
    links: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        label = normalize_space(cells[0].get_text(" ", strip=True))
        if label.startswith(COALITION_MEMBER_MARKER):
            kind = "koalicijos-nare"
        elif label.startswith(SINGLE_MEMBER_ONLY_MARKER):
            kind = "tik-vienmandatese"
        else:
            continue
        anchor = tr.find("a", href=True)
        if anchor is None:
            continue
        href = normalize_space(anchor["href"])
        count_text = normalize_space(cells[2].get_text(" ", strip=True))
        number_match = re.search(r"Nr\.\s*(\d+)", label)
        links.append(
            {
                "kind": kind,
                "listKey": _side_list_key(href),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "coalitionListNumber": int(number_match.group(1)) if number_match else None,
                "declaredCount": int(count_text) if count_text.isdigit() else None,
                "url": resolve_candidate_url(href),
            }
        )
    return links


def fetch_side_pages(samples_dir: Path, index_html: str) -> None:
    for link in extract_side_links(index_html):
        path = _list_sample_path(samples_dir, link["listKey"])
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fetch_text(link["url"]), encoding="utf-8")
        time.sleep(FETCH_PAUSE_SECONDS)


def side_page_candidate_ids(samples_dir: Path, link: dict[str, Any]) -> list[str]:
    html = _list_sample_path(samples_dir, link["listKey"]).read_text(encoding="utf-8")
    ids: list[str] = []
    for vrk_id in re.findall(r"Kandidato(\d+)Anketa\.html", html):
        if vrk_id not in ids:
            ids.append(vrk_id)
    return ids


def _coalition_member_from_row(row: Any) -> str | None:
    # The coalition list page's last column links the member party that put
    # the candidate on the joint list.
    if row is None:
        return None
    for anchor in row.find_all("a", href=True):
        if COALITION_MEMBER_LINK_PATTERN.search(anchor["href"]):
            return normalize_space(anchor.get_text(" ", strip=True)) or None
    return None


def _row_has_district_column(row: Any) -> bool:
    if row is None:
        return False
    return any(ANY_DISTRICT_LINK_PATTERN.search(anchor["href"]) for anchor in row.find_all("a", href=True))


def _district_id_from_row(row: Any) -> str | None:
    # The list pages' fourth column links the candidate's single-member
    # constituency ("68. Vilkaviškio"), or an empty "Apygardanull" link when
    # the candidate stood on the list only.
    if row is None:
        return None
    for anchor in row.find_all("a", href=True):
        match = DISTRICT_LINK_PATTERN.search(anchor["href"])
        if match and match.group(1).isdigit():
            return match.group(1)
    return None


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
    election_id: str = ELECTION_ID,
) -> tuple[Path, dict[str, int]]:
    # sample_path keeps the CLI's signature; it names the samples directory.
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR

    lists, list_rows = collect_list_records(samples_dir, index_name=LISTS_INDEX_NAME)
    districts, district_rows = collect_district_records(samples_dir, index_name=DISTRICTS_INDEX_NAME)
    side_links = extract_side_links((samples_dir / LISTS_INDEX_NAME).read_text(encoding="utf-8"))

    # Merge on VRK's own candidate id — one entry carries both candidacies.
    entries_by_vrk_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    skipped: list[dict[str, Any]] = []

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

    # What each list page says about the candidate's constituency, for the
    # cross-check against the constituency pages.
    list_claimed_district: dict[str, str | None] = {}
    list_rows_without_district_column = 0
    duplicate_list_rows = 0
    for record in list_rows:
        if not record["vrkCandidateId"]:
            skipped.append({"reason": "missing-vrk-id", "candidateName": record["candidateName"]})
            continue
        entry = _entry_for(record)
        if "daugiamandate" in entry["roles"]:
            duplicate_list_rows += 1
            continue
        entry["roles"].append("daugiamandate")
        candidacy = list_candidacy(record)
        member = _coalition_member_from_row(record.get("row"))
        if member is not None:
            candidacy["koalicijosPartija"] = member
        entry["daugiamandateCandidacy"] = candidacy
        if _row_has_district_column(record.get("row")):
            list_claimed_district[record["vrkCandidateId"]] = _district_id_from_row(record.get("row"))
        else:
            list_rows_without_district_column += 1

    duplicate_district_rows = 0
    for record in district_rows:
        if not record["vrkCandidateId"]:
            skipped.append({"reason": "missing-vrk-id", "candidateName": record["candidateName"]})
            continue
        entry = _entry_for(record)
        if "vienmandate" in entry["roles"]:
            duplicate_district_rows += 1
            continue
        entry["roles"].append("vienmandate")
        entry["vienmandateCandidacy"] = {
            "apygarda": record["district"]["pavadinimas"],
            "apygardosNumeris": record["district"]["numeris"],
            "apygardosId": record["district"]["apygardosId"],
            "iskele": record["nominatedBy"] or None,
        }

    entries = [entries_by_vrk_id[vrk_id] for vrk_id in order]
    duplicate_candidate_ids = assign_positional_ids(entries)

    # Cross-checks against what VRK's own index declares.
    declared_list_total = sum(link["declaredCount"] or 0 for link in lists)
    list_count_mismatches = 0
    for link in lists:
        walked = sum(1 for record in list_rows if record["list"]["listKey"] == link["listKey"])
        if link["declaredCount"] is not None and walked != link["declaredCount"]:
            list_count_mismatches += 1
    single_member_only = sum(1 for entry in entries if entry["roles"] == ["vienmandate"])
    dual = sum(1 for entry in entries if len(entry["roles"]) == 2)
    list_only = sum(1 for entry in entries if entry["roles"] == ["daugiamandate"])
    # The list pages name each candidate's constituency; the constituency
    # pages must agree, both ways.
    join_mismatch = 0
    for entry in entries:
        if entry["vrkCandidateId"] not in list_claimed_district:
            continue
        claimed = list_claimed_district[entry["vrkCandidateId"]]
        actual = (entry.get("vienmandateCandidacy") or {}).get("apygardosId")
        if claimed != actual:
            join_mismatch += 1

    # The "tik vienmandatėse" side pages (and the self-nominated page) are
    # VRK's own statement of who stood in a constituency only. Their unique
    # ids, less the few who also hold a list seat (a self-nominated
    # constituency candidate can be on a party's list), must equal the
    # district-only count the merge produced. The index's declared counts
    # are not used for this: the self-nominated page declares more than it
    # lists, the withdrawn having been removed from the page but not from
    # the count.
    side_ids: list[str] = []
    side_declared = 0
    side_ids_not_on_districts = 0
    district_vrk_ids = {record["vrkCandidateId"] for record in district_rows}
    for link in side_links:
        if link["kind"] != "tik-vienmandatese":
            continue
        side_declared += link["declaredCount"] or 0
        for vrk_id in side_page_candidate_ids(samples_dir, link):
            if vrk_id not in side_ids:
                side_ids.append(vrk_id)
            if vrk_id not in district_vrk_ids:
                side_ids_not_on_districts += 1
    side_ids_on_lists = sum(
        1 for vrk_id in side_ids if "daugiamandate" in entries_by_vrk_id.get(vrk_id, {}).get("roles", [])
    )
    district_only_reconciled = single_member_only == len(side_ids) - side_ids_on_lists

    payload = {
        "electionId": election_id,
        "sourceUrl": LISTING_URL,
        "districtsUrl": DISTRICTS_URL,
        "listUrls": [link["url"] for link in lists],
        "districtUrls": [district["url"] for district in districts],
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": len(list_rows) + len(district_rows),
            "extracted": len(entries),
            "skipped": len(skipped),
            "duplicateCandidateIds": duplicate_candidate_ids,
            "lists": len(lists),
            "districts": len(districts),
            "listCandidacies": len(list_rows),
            "districtCandidacies": len(district_rows),
            "declaredListCandidates": declared_list_total,
            "listCountMismatches": list_count_mismatches,
            "dualCandidates": dual,
            "listOnlyCandidates": list_only,
            "districtOnlyCandidates": single_member_only,
            "sidePageDistrictOnlyDeclared": side_declared,
            "sidePageDistrictOnlyIds": len(side_ids),
            "sidePageIdsAlsoOnLists": side_ids_on_lists,
            "sidePageIdsNotOnDistrictPages": side_ids_not_on_districts,
            "districtOnlyReconciled": district_only_reconciled,
            "listRowsWithoutDistrictColumn": list_rows_without_district_column,
            "listDistrictJoinMismatch": join_mismatch,
            "duplicateListRows": duplicate_list_rows,
            "duplicateDistrictRows": duplicate_district_rows,
        },
        "sideLinks": side_links,
        "entries": entries,
        "skipped": skipped,
    }
    write_json(output_path, payload)

    stats = {
        "rows": payload["stats"]["rows"],
        "extracted": len(entries),
        "skipped": len(skipped),
        "duplicate_candidate_ids": duplicate_candidate_ids,
        "lists": len(lists),
        "districts": len(districts),
        "list_candidacies": len(list_rows),
        "district_candidacies": len(district_rows),
        "declared_list_candidates": declared_list_total,
        "list_count_mismatches": list_count_mismatches,
        "dual_candidates": dual,
        "list_only_candidates": list_only,
        "district_only_candidates": single_member_only,
        "side_page_district_only_declared": side_declared,
        "side_page_district_only_ids": len(side_ids),
        "side_page_ids_also_on_lists": side_ids_on_lists,
        "side_page_ids_not_on_district_pages": side_ids_not_on_districts,
        "district_only_reconciled": int(district_only_reconciled),
        "list_rows_without_district_column": list_rows_without_district_column,
        "list_district_join_mismatch": join_mismatch,
        "duplicate_list_rows": duplicate_list_rows,
        "duplicate_district_rows": duplicate_district_rows,
    }
    return output_path, stats
