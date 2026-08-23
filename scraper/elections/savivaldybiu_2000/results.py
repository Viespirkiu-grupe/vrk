"""Elected status and preference votes for the 2000 municipal council
election, from VRK's ``rinkimai/20000319`` tree.

The candidate page marks no winner. Per municipality the tree publishes:

- ``rapgpl.htm-<municipality>.htm`` — the list results: voters, turnout,
  the seat quota, and per list the ballot-box, postal and total votes
  and the mandates ("-" below the threshold), with a totals row; each
  list links its preference page.
- ``rikl.htm-<municipality>.htm`` — "Kandidatai, gavę mandatus": every
  council member with the candidate page link (so the join is by VRK's
  id), the list (linking its preference page) and the post-election
  rank; "Mandatų skaičius: N" above. The source.
- ``rpbapgl.htm-<municipality>+<list>.htm`` — the list's preference votes:
  every candidate's post-election rank, preference votes and pre-election
  number, the winners in bold.

Cross-checks: the members page's count against its own "Mandatų
skaičius", the list results' mandate column and its totals row; every
member in the sitemap, in the municipality and on the list the sitemap
says; the bold names on the preference pages exactly the members; each
list's members exactly its top ranks; every sitemap candidate ranked,
with the pre-election number the listing's.

Five municipalities — Jurbarko, Kelmės, Radviliškio, Raseinių and
Vilkaviškio rajono — were captured only as far as the list results: their
``rapgpl`` page prints the votes and mandates per list as plain text,
links the live CGI for the members page and nothing for the preference
pages, and none of those URLs exists statically. For them the tree says
which lists won how many seats and nothing about which candidates took
them, so their candidates' ``isrinktas`` stays unknown (null) — the
results file names them under ``details.resultsUnavailable`` and carries
the list-level figures for every municipality under
``details.listResults`` so each record still gets its list's votes and
mandates. Where a members page is missing but the preference pages are
not, the members would be their bold rows (checked against the top
ranks); no 2000 municipality is in that state.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag
import requests

from scraper.elections.savivaldybiu_2000.sitemap import (
    CANDIDATE_PAGE_PATTERN,
    ELECTION_ID,
    MUNICIPALITIES_URL,
    SITE_ROOT,
    extract_municipality_links,
    normalize_space,
)
from scraper.shared.election_results import (
    fetch_page,
    load_sitemap_entries,
    resolve_url,
    write_results,
)

PREFERENCE_PAGE_PATTERN = re.compile(r"rpbapgl\.htm-(\d+)\+(\d+)\.htm$")
MEMBERS_PAGE_PATTERN = re.compile(r"rikl\.htm-(\d+)\.htm$")

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def _own_rows(table: Tag) -> list[Tag]:
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def _own_cells(tr: Tag) -> list[Tag]:
    return [td for td in tr.find_all("td") if td.find_parent("tr") is tr]


def _int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _candidate_anchor(cell: Tag) -> Tag | None:
    for anchor in cell.find_all("a", href=True):
        if CANDIDATE_PAGE_PATTERN.search(anchor["href"]):
            return anchor
    return None


def parse_municipality_results_page(html: str) -> dict[str, Any]:
    """One rapgpl.htm page: the turnout line, the quota, per list the
    votes and mandates (None where the page prints "-"), the totals row."""
    soup = BeautifulSoup(html, "lxml")
    text = normalize_space(soup.get_text(" ", strip=True))
    voters = re.search(r"Bendras rinkėjų skaičius:\s*(\d+)\s*,\s*rinkimuose dalyvavo:\s*(\d+)\s*\(\s*([\d.,]+)%", text)
    quota = re.search(r"Mandatų skirstymo kvota:\s*(\d+)", text)
    lists: list[dict[str, Any]] = []
    total: dict[str, Any] | None = None
    for table in soup.find_all("table"):
        header = normalize_space(table.get_text(" ", strip=True))
        if "Mandatų skaičius" not in header or "Sąrašo" not in header:
            continue
        for tr in _own_rows(table):
            cells = _own_cells(tr)
            if len(cells) < 6:
                continue
            label = normalize_space(cells[1].get_text(" ", strip=True))
            anchor = None
            for candidate in cells[1].find_all("a", href=True):
                if PREFERENCE_PAGE_PATTERN.search(candidate["href"]):
                    anchor = candidate
                    break
            mandates_text = normalize_space(cells[5].get_text(" ", strip=True))
            row = {
                "ballotBox": _int(cells[2].get_text(" ", strip=True)),
                "postal": _int(cells[3].get_text(" ", strip=True)),
                "total": _int(cells[4].get_text(" ", strip=True)),
                "mandates": int(mandates_text) if mandates_text.isdigit() else None,
            }
            number_text = normalize_space(cells[0].get_text(" ", strip=True)).rstrip(".")
            if anchor is None:
                if label.lower().startswith("iš viso"):
                    total = row
                elif number_text.isdigit():
                    # The five municipalities captured without preference
                    # pages print the list rows unlinked.
                    lists.append({"listNumber": int(number_text), "name": label, "municipalityId": None, "listId": None, "preferenceUrl": None, **row})
                continue
            match = PREFERENCE_PAGE_PATTERN.search(anchor["href"])
            lists.append(
                {
                    "listNumber": int(number_text) if number_text.isdigit() else None,
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "municipalityId": match.group(1),
                    "listId": match.group(2),
                    "preferenceUrl": resolve_url(anchor["href"], SITE_ROOT),
                    **row,
                }
            )
        if lists or total:
            break
    return {
        "voters": int(voters.group(1)) if voters else None,
        "turnout": int(voters.group(2)) if voters else None,
        "turnoutPercent": float(voters.group(3).replace(",", ".")) if voters else None,
        "quota": int(quota.group(1)) if quota else None,
        "lists": lists,
        "total": total,
    }


def parse_members_page(html: str) -> dict[str, Any]:
    """One rikl.htm page: the declared seat count and every member with
    VRK id, name, list (id and name) and post-election rank."""
    soup = BeautifulSoup(html, "lxml")
    text = normalize_space(soup.get_text(" ", strip=True))
    seats = re.search(r"Mandatų skaičius:\s*(\d+)", text)
    members: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        if _candidate_anchor(table) is None:
            continue
        for tr in _own_rows(table):
            cells = _own_cells(tr)
            if len(cells) < 3:
                continue
            anchor = _candidate_anchor(cells[0])
            if anchor is None:
                continue
            list_anchor = None
            for candidate in cells[1].find_all("a", href=True):
                if PREFERENCE_PAGE_PATTERN.search(candidate["href"]):
                    list_anchor = candidate
                    break
            list_match = PREFERENCE_PAGE_PATTERN.search(list_anchor["href"]) if list_anchor is not None else None
            members.append(
                {
                    "vrkCandidateId": CANDIDATE_PAGE_PATTERN.search(anchor["href"]).group(1),
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "listName": normalize_space(cells[1].get_text(" ", strip=True)),
                    "listId": list_match.group(2) if list_match else None,
                    "rank": _int(cells[2].get_text(" ", strip=True)),
                }
            )
        break
    return {"seats": int(seats.group(1)) if seats else None, "members": members}


def parse_preference_page(html: str) -> list[dict[str, Any]]:
    """One rpbapgl.htm page: rank, VRK id, name, preference votes,
    pre-election number, whether the row is bold (a mandate)."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        if _candidate_anchor(table) is None:
            continue
        for tr in _own_rows(table):
            cells = _own_cells(tr)
            if len(cells) < 4:
                continue
            anchor = _candidate_anchor(cells[1])
            if anchor is None:
                continue
            rows.append(
                {
                    "rank": _int(cells[0].get_text(" ", strip=True)),
                    "vrkCandidateId": CANDIDATE_PAGE_PATTERN.search(anchor["href"]).group(1),
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "preferenceVotes": _int(cells[2].get_text(" ", strip=True)),
                    "listPosition": _int(cells[3].get_text(" ", strip=True)),
                    "mandate": anchor.find("b") is not None or anchor.find_parent("b") is not None,
                }
            )
        break
    return rows


def ranking_source_for(page: dict[str, Any], list_id: str | None) -> str | None:
    for row in page["lists"]:
        if row["listId"] == list_id:
            return row["preferenceUrl"]
    return None


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    entries = load_sitemap_entries(sitemap_path)
    by_id = {entry["vrkCandidateId"]: entry for entry in entries if entry.get("vrkCandidateId")}

    municipalities = extract_municipality_links(fetch_page(results_dir, MUNICIPALITIES_URL))

    elected: dict[str, dict[str, Any]] = {}
    ranking: dict[str, dict[str, Any]] = {}
    per_municipality: list[dict[str, Any]] = []
    not_in_sitemap: list[dict[str, Any]] = []
    municipality_mismatches: list[dict[str, Any]] = []
    list_mismatches: list[dict[str, Any]] = []
    seat_count_mismatches: list[dict[str, Any]] = []
    members_page_missing: list[dict[str, Any]] = []
    results_unavailable: list[dict[str, Any]] = []
    rank_mismatches = 0
    bold_diff = 0
    top_rank_diff = 0
    position_mismatches = 0
    sources: list[str] = [MUNICIPALITIES_URL]
    # The sitemap's lists per municipality, to resolve the unlinked rows.
    sitemap_lists: dict[str, dict[int, dict[str, Any]]] = {}
    for entry in entries:
        sitemap_lists.setdefault(entry["municipality"]["savivaldybesId"], {}).setdefault(entry["list"]["numeris"], entry["list"])
    list_results: dict[str, dict[str, dict[str, Any]]] = {}
    unresolved_list_rows = 0
    for municipality in municipalities:
        results_url = municipality["resultsUrl"]
        municipality_id = municipality["municipalityId"]
        members_url = f"{SITE_ROOT}rikl.htm-{municipality_id}.htm"
        page = parse_municipality_results_page(fetch_page(results_dir, results_url))
        sources.append(results_url)
        for row in page["lists"]:
            if row["listId"] is None:
                known = sitemap_lists.get(municipality_id, {}).get(row["listNumber"])
                if known is None or known["pavadinimas"] != row["name"]:
                    unresolved_list_rows += 1
                    continue
                row["municipalityId"] = municipality_id
                row["listId"] = known["sarasoId"]
            list_results.setdefault(municipality_id, {})[row["listId"]] = {
                "listNumber": row["listNumber"],
                "name": row["name"],
                "ballotBox": row["ballotBox"],
                "postal": row["postal"],
                "total": row["total"],
                "mandates": row["mandates"],
                "sourceUrl": results_url,
            }
        mandates_sum = sum(row["mandates"] or 0 for row in page["lists"])
        total_mandates = (page["total"] or {}).get("mandates")
        captured = all(row["preferenceUrl"] for row in page["lists"])
        try:
            members_page = parse_members_page(fetch_page(results_dir, members_url))
            sources.append(members_url)
            method = "mandates-page"
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            members_page = {"seats": total_mandates if total_mandates is not None else mandates_sum, "members": []}
            members_url = None
            if not captured:
                # Neither the members page nor the preference pages exist:
                # the seats are known per list, the members are not.
                results_unavailable.append(
                    {
                        "municipalityId": municipality_id,
                        "name": municipality["name"],
                        "membersUrl": f"{SITE_ROOT}rikl.htm-{municipality_id}.htm",
                        "seats": mandates_sum,
                        "lists": len(page["lists"]),
                        "listsWithSeats": sum(1 for row in page["lists"] if row["mandates"]),
                    }
                )
                per_municipality.append(
                    {
                        "municipalityId": municipality_id,
                        "number": municipality["number"],
                        "name": municipality["name"],
                        "voters": page["voters"],
                        "turnout": page["turnout"],
                        "turnoutPercent": page["turnoutPercent"],
                        "quota": page["quota"],
                        "seats": mandates_sum,
                        "members": None,
                        "lists": len(page["lists"]),
                        "listsWithSeats": sum(1 for row in page["lists"] if row["mandates"]),
                        "resultsUrl": results_url,
                        "membersUrl": None,
                    }
                )
                continue
            # The members page alone missing: the members are the bold
            # rows of the preference pages, checked below against the
            # top ranks.
            method = "preference-page"
            derived_members: list[dict[str, Any]] = []
            for row in page["lists"]:
                for item in parse_preference_page(fetch_page(results_dir, row["preferenceUrl"])):
                    if item["mandate"]:
                        derived_members.append({"vrkCandidateId": item["vrkCandidateId"], "name": item["name"], "listName": row["name"], "listId": row["listId"], "rank": item["rank"]})
            members_page["members"] = derived_members
            members_page_missing.append({"municipalityId": municipality_id, "name": municipality["name"], "derivedMembers": len(derived_members)})
        members = members_page["members"]
        if not (len(members) == members_page["seats"] == mandates_sum == total_mandates):
            seat_count_mismatches.append(
                {
                    "municipalityId": municipality["municipalityId"],
                    "members": len(members),
                    "declared": members_page["seats"],
                    "mandatesSum": mandates_sum,
                    "totalsRow": total_mandates,
                }
            )
        member_ids = {m["vrkCandidateId"] for m in members}
        for member in members:
            entry = by_id.get(member["vrkCandidateId"])
            if entry is None:
                not_in_sitemap.append({**member, "municipalityId": municipality["municipalityId"]})
                continue
            if entry["municipality"]["savivaldybesId"] != municipality["municipalityId"]:
                municipality_mismatches.append({"member": member, "sitemap": entry["municipality"]})
            if entry["list"]["sarasoId"] != member["listId"]:
                list_mismatches.append({"member": member, "sitemap": entry["list"]})
            elected[member["vrkCandidateId"]] = {
                "seat": "tarybos-narys",
                "method": method,
                "sourceUrl": members_url or ranking_source_for(page, member["listId"]),
                "municipality": municipality["name"],
                "municipalityId": municipality["municipalityId"],
                "listName": member["listName"],
                "listId": member["listId"],
                "rank": member["rank"],
            }
        # Every list's preference page.
        bold_ids: set[str] = set()
        for row in page["lists"]:
            url = row["preferenceUrl"]
            sources.append(url)
            rows = parse_preference_page(fetch_page(results_dir, url))
            ranked_ids: list[str] = []
            for item in sorted(rows, key=lambda r: r["rank"] or 0):
                ranked_ids.append(item["vrkCandidateId"])
                ranking[item["vrkCandidateId"]] = {
                    "rank": item["rank"],
                    "listPosition": item["listPosition"],
                    "preferenceVotes": item["preferenceVotes"],
                    "mandate": item["mandate"],
                    "municipalityId": row["municipalityId"],
                    "listId": row["listId"],
                    "sourceUrl": url,
                }
                if item["mandate"]:
                    bold_ids.add(item["vrkCandidateId"])
                entry = by_id.get(item["vrkCandidateId"])
                if entry is not None and entry.get("listPosition") != item["listPosition"]:
                    position_mismatches += 1
                member_rank = elected.get(item["vrkCandidateId"], {}).get("rank")
                if member_rank is not None and member_rank != item["rank"]:
                    rank_mismatches += 1
            list_members = {m["vrkCandidateId"] for m in members if m["listId"] == row["listId"]}
            if set(ranked_ids[: row["mandates"] or 0]) != list_members:
                top_rank_diff += 1
        bold_diff += len(bold_ids ^ member_ids)
        per_municipality.append(
            {
                "municipalityId": municipality["municipalityId"],
                "number": municipality["number"],
                "name": municipality["name"],
                "voters": page["voters"],
                "turnout": page["turnout"],
                "turnoutPercent": page["turnoutPercent"],
                "quota": page["quota"],
                "seats": members_page["seats"],
                "members": len(members),
                "lists": len(page["lists"]),
                "listsWithSeats": sum(1 for row in page["lists"] if row["mandates"]),
                "resultsUrl": results_url,
                "membersUrl": members_url,
            }
        )

    unavailable_ids = {row["municipalityId"] for row in results_unavailable}
    candidates_without_results = sum(1 for entry in entries if entry["municipality"]["savivaldybesId"] in unavailable_ids)
    stats = {
        "municipalities": len(municipalities),
        "municipalitiesWithResults": len(municipalities) - len(results_unavailable),
        "resultsUnavailable": len(results_unavailable),
        "candidatesWithoutResults": candidates_without_results,
        "seatsWithoutMembers": sum(row["seats"] for row in results_unavailable),
        "membersPagesMissing": len(members_page_missing),
        "unresolvedListRows": unresolved_list_rows,
        "councilMembers": len(elected),
        "membersOnPages": len(elected) + len(not_in_sitemap),
        "councilNotInSitemap": len(not_in_sitemap),
        "municipalityMismatches": len(municipality_mismatches),
        "listMismatches": len(list_mismatches),
        "seatCountMismatches": len(seat_count_mismatches),
        "rankMismatches": rank_mismatches,
        "boldNotMembers": bold_diff,
        "listTopRanksNotMembers": top_rank_diff,
        "candidatesRanked": len(ranking),
        "rankedNotInSitemap": sum(1 for vrk_id in ranking if vrk_id not in by_id),
        "sitemapNotRanked": sum(1 for vrk_id, entry in by_id.items() if vrk_id not in ranking and entry["municipality"]["savivaldybesId"] not in unavailable_ids),
        "listPositionMismatches": position_mismatches,
        "seats": {"tarybos-narys": len(elected)},
    }
    details = {
        "perMunicipality": per_municipality,
        "councilNotInSitemap": not_in_sitemap,
        "municipalityMismatches": municipality_mismatches,
        "listMismatches": list_mismatches,
        "seatCountMismatches": seat_count_mismatches,
        "membersPagesMissing": members_page_missing,
        "resultsUnavailable": results_unavailable,
        "listResults": list_results,
        "ranking": ranking,
    }
    write_results(output_path, ELECTION_ID, elected, stats, sources, details)
    return output_path, stats


__all__ = [
    "build_results",
    "parse_members_page",
    "parse_municipality_results_page",
    "parse_preference_page",
]
