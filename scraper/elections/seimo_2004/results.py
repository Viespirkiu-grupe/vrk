"""Elected status for the 2004 Seimas election, from VRK's 2004/seimas tree.

The candidate pages mark no winner; the original static site's results
tree (``rinkimai/2004/seimas/rezultatai/``) does, by anketa id:

- ``rez_isrinkti_l_20_1.htm`` — "Išrinkti Lietuvos Respublikos Seimo
  nariais 2004 - 2008": the 141 members, each with the anketa link, the
  seat — "Daugiamandatė", or the constituency's number and name linking
  ``rezv_apg_l_<district>_<round>.htm``, so the constituency id and the
  deciding round are on the row — and the party; a ``***`` marks the five
  constituency seats decided in the first round. The source.
- ``rezd_isrinkti_l_20_1.htm`` (the 70 list seats),
  ``rezv_isrinkti_l_20_1_1.htm`` and ``rezv_isrinkti_l_20_2_1.htm`` (the 5
  first-round and 66 runoff constituency winners): the cross-checks, each
  by id.
- ``rez_l_20.htm`` — the list results: mandates per list (the cross-check
  for the list seats) and the links to the 15 ``rez_pirm_l_<list>.htm``
  ranking pages, which give every list candidate's post-preference rank
  and preference votes, joined into the record as for the 2004 EP election.

The per-constituency results pages row candidates under a results-system
id of their own (``rezv_kand_apg_l_<id>_…``), not the anketa id, so
constituency vote counts are not joined here.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.ep_2004.results import (
    ANKETA_PATTERN,
    PREFERENCE_PAGE_PATTERN,
    _own_cells,
    _own_rows,
    parse_preference_page,
    parse_results_page,
)
from scraper.elections.seimo_2004.sitemap import ELECTION_ID
from scraper.shared.election_results import (
    fetch_page,
    load_sitemap_entries,
    normalize_space,
    resolve_url,
    write_results,
)

RESULTS_ROOT = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/seimas/rezultatai/"
MEMBERS_PAGE = "rez_isrinkti_l_20_1.htm"
LIST_RESULTS_PAGE = "rez_l_20.htm"
LIST_WINNERS_PAGE = "rezd_isrinkti_l_20_1.htm"
CONSTITUENCY_WINNERS_PAGES = {1: "rezv_isrinkti_l_20_1_1.htm", 2: "rezv_isrinkti_l_20_2_1.htm"}
CONSTITUENCY_RESULT_PATTERN = re.compile(r"rezv_apg_l_(\d+)_(\d)\.htm$")
LIST_SEATS = 70
CONSTITUENCY_SEATS = 71

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def _candidate_table(soup: BeautifulSoup) -> Tag | None:
    for table in soup.find_all("table", class_="basic"):
        if any(ANKETA_PATTERN.search(anchor["href"]) for anchor in table.find_all("a", href=True)):
            return table
    return None


def parse_members_page(html: str, base_url: str) -> list[dict[str, Any]]:
    """Rows of the members page: anketa id, name, seat, constituency (id,
    number, name, round) or list, party, first-round marker."""
    soup = BeautifulSoup(html, "lxml")
    table = _candidate_table(soup)
    members: list[dict[str, Any]] = []
    if table is None:
        return members
    for tr in _own_rows(table):
        cells = _own_cells(tr)
        if len(cells) < 4:
            continue
        anchor = None
        for candidate in cells[0].find_all("a", href=True):
            if ANKETA_PATTERN.search(candidate["href"]):
                anchor = candidate
                break
        if anchor is None:
            continue
        number_text = normalize_space(cells[1].get_text(" ", strip=True))
        seat_text = normalize_space(cells[2].get_text(" ", strip=True))
        district_anchor = cells[2].find("a", href=True)
        district_match = (
            CONSTITUENCY_RESULT_PATTERN.search(district_anchor["href"]) if district_anchor is not None else None
        )
        member: dict[str, Any] = {
            "vrkCandidateId": ANKETA_PATTERN.search(anchor["href"]).group(1),
            "name": normalize_space(anchor.get_text(" ", strip=True)),
            "firstRoundMarker": "***" in normalize_space(cells[0].get_text(" ", strip=True)),
            "party": normalize_space(cells[3].get_text(" ", strip=True)),
            "anketaUrl": resolve_url(anchor["href"], base_url),
        }
        if district_match is not None:
            member["seat"] = "vienmandate"
            member["districtId"] = district_match.group(1)
            member["round"] = int(district_match.group(2))
            member["districtNumber"] = int(number_text) if number_text.isdigit() else None
            member["districtName"] = seat_text
        else:
            member["seat"] = "daugiamandate"
        members.append(member)
    return members


def _anketa_ids(html: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    table = _candidate_table(soup)
    if table is None:
        return set()
    return {ANKETA_PATTERN.search(a["href"]).group(1) for a in table.find_all("a", href=True) if ANKETA_PATTERN.search(a["href"])}


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    entries = load_sitemap_entries(sitemap_path)
    by_id = {entry["vrkCandidateId"]: entry for entry in entries if entry.get("vrkCandidateId")}

    members_url = RESULTS_ROOT + MEMBERS_PAGE
    members = parse_members_page(fetch_page(results_dir, members_url), members_url)

    elected: dict[str, dict[str, Any]] = {}
    not_in_sitemap: list[dict[str, Any]] = []
    role_mismatches: list[dict[str, Any]] = []
    district_mismatches: list[dict[str, Any]] = []
    round_marker_mismatches = 0
    for member in members:
        entry = by_id.get(member["vrkCandidateId"])
        if entry is None:
            not_in_sitemap.append(member)
            continue
        record: dict[str, Any] = {
            "seat": member["seat"],
            "method": "members-list",
            "sourceUrl": members_url,
            "party": member["party"],
        }
        if member["seat"] == "vienmandate":
            record["round"] = member["round"]
            record["districtId"] = member["districtId"]
            record["districtNumber"] = member["districtNumber"]
            record["districtName"] = member["districtName"]
            if member["firstRoundMarker"] != (member["round"] == 1):
                round_marker_mismatches += 1
            single = entry.get("vienmandateCandidacy") or {}
            if "vienmandate" not in entry.get("roles", []):
                role_mismatches.append(member)
            elif single.get("apygardosId") != member["districtId"]:
                district_mismatches.append({"member": member, "sitemap": single})
        elif "daugiamandate" not in entry.get("roles", []):
            role_mismatches.append(member)
        elected[member["vrkCandidateId"]] = record

    # Cross-check one: the list-seat page and the two constituency-winner
    # pages, by id, must be exactly the members page's two halves.
    list_winners_url = RESULTS_ROOT + LIST_WINNERS_PAGE
    list_ids = _anketa_ids(fetch_page(results_dir, list_winners_url))
    constituency_ids: dict[int, set[str]] = {}
    constituency_urls: list[str] = []
    for round_number, page in CONSTITUENCY_WINNERS_PAGES.items():
        url = RESULTS_ROOT + page
        constituency_urls.append(url)
        constituency_ids[round_number] = _anketa_ids(fetch_page(results_dir, url))
    member_list_ids = {m["vrkCandidateId"] for m in members if m["seat"] == "daugiamandate"}
    member_round_ids = {
        round_number: {m["vrkCandidateId"] for m in members if m["seat"] == "vienmandate" and m["round"] == round_number}
        for round_number in CONSTITUENCY_WINNERS_PAGES
    }

    # Cross-check two: the list results page's mandate column per list
    # against the list seats per list on the members page (by party name).
    list_results_url = RESULTS_ROOT + LIST_RESULTS_PAGE
    list_results_html = fetch_page(results_dir, list_results_url)
    list_rows = parse_results_page(list_results_html)
    mandates_by_name = {row["name"]: row["mandates"] for row in list_rows}
    seats_by_name = Counter(m["party"] for m in members if m["seat"] == "daugiamandate")
    list_mandate_mismatches = [
        {"list": name, "declared": mandates_by_name.get(name, 0), "listed": seats_by_name.get(name, 0)}
        for name in sorted(set(mandates_by_name) | set(seats_by_name))
        if mandates_by_name.get(name, 0) != seats_by_name.get(name, 0)
    ]

    # Every list candidate's post-preference rank and preference votes.
    ranking: dict[str, dict[str, Any]] = {}
    bold_ids: set[str] = set()
    preference_urls: list[str] = []
    soup = BeautifulSoup(list_results_html, "lxml")
    for anchor in soup.find_all("a", href=True):
        match = PREFERENCE_PAGE_PATTERN.search(anchor["href"])
        if match is None:
            continue
        url = resolve_url(anchor["href"], list_results_url)
        if url in preference_urls:
            continue
        preference_urls.append(url)
        for row in parse_preference_page(fetch_page(results_dir, url)):
            ranking[row["vrkCandidateId"]] = {
                "rank": row["rank"],
                "listPosition": row["listPosition"],
                "preferenceVotes": row["preferenceVotes"],
                "ranked": row["ranked"],
                "listId": match.group(1),
                "sourceUrl": url,
            }
            if row["mandate"]:
                bold_ids.add(row["vrkCandidateId"])
    list_candidates = {vrk_id for vrk_id, entry in by_id.items() if "daugiamandate" in entry.get("roles", [])}
    # The ranking page repeats the pre-election position; it must be the
    # listing's. An unranked list prints the rank alone, which *is* the
    # list order.
    position_mismatches = [
        {"vrkCandidateId": vrk_id, "listing": (by_id[vrk_id].get("daugiamandateCandidacy") or {}).get("numerisSarase"), "ranking": row["listPosition"] if row["ranked"] else row["rank"]}
        for vrk_id, row in ranking.items()
        if vrk_id in by_id
        and (by_id[vrk_id].get("daugiamandateCandidacy") or {}).get("numerisSarase") != (row["listPosition"] if row["ranked"] else row["rank"])
    ]
    unranked_lists = sorted({row["listId"] for row in ranking.values() if not row["ranked"]})

    stats = {
        "seats": LIST_SEATS + CONSTITUENCY_SEATS,
        "membersListed": len(members),
        "membersInSitemap": len(elected),
        "membersNotInSitemap": len(not_in_sitemap),
        "listSeats": len(member_list_ids),
        "constituencySeats": sum(len(ids) for ids in member_round_ids.values()),
        "constituencySeatsFirstRound": len(member_round_ids.get(1, set())),
        "constituencySeatsRunoff": len(member_round_ids.get(2, set())),
        "roleMismatches": len(role_mismatches),
        "districtMismatches": len(district_mismatches),
        "roundMarkerMismatches": round_marker_mismatches,
        "listWinnersPageDiff": len(list_ids ^ member_list_ids),
        "constituencyWinnersPageDiff": sum(len(constituency_ids[r] ^ member_round_ids[r]) for r in CONSTITUENCY_WINNERS_PAGES),
        "mandatesDeclared": sum(mandates_by_name.values()),
        "listMandateMismatches": len(list_mandate_mismatches),
        "rankingPages": len(preference_urls),
        "candidatesRanked": len(ranking),
        "rankedNotInSitemap": sum(1 for vrk_id in ranking if vrk_id not in by_id),
        "listCandidatesNotRanked": len(list_candidates - set(ranking)),
        "boldNotListSeats": len(bold_ids - member_list_ids),
        "listSeatsNotBold": len(member_list_ids - bold_ids),
        "listPositionMismatches": len(position_mismatches),
        "unrankedLists": len(unranked_lists),
        "candidatesOnUnrankedLists": sum(1 for row in ranking.values() if not row["ranked"]),
    }
    details = {
        "unrankedLists": unranked_lists,
        "notInSitemap": not_in_sitemap,
        "roleMismatches": role_mismatches,
        "districtMismatches": district_mismatches,
        "mandatesByList": list_rows,
        "listMandateMismatches": list_mandate_mismatches,
        "ranking": ranking,
        "listPositionMismatches": position_mismatches,
    }
    write_results(
        output_path,
        ELECTION_ID,
        elected,
        stats,
        [members_url, list_winners_url, *constituency_urls, list_results_url, *preference_urls],
        details,
    )
    return output_path, stats


__all__ = ["MEMBERS_PAGE", "RESULTS_ROOT", "build_results", "parse_members_page"]
