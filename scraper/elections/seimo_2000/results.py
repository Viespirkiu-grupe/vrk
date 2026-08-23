"""Elected status and votes for the 2000 Seimas election, from VRK's
``rinkimai/20001008`` tree.

The candidate card marks the winners ("šioje apygardoje išrinktas Seimo
nariu"), the one static era that does; the results tree is still the
source, with the card's note a per-candidate cross-check in the parser:

- ``ril.htm-13+2.htm`` — "Seimo nariai": the 141 members, each with the
  candidate page link (so the join is by VRK's id), the seat —
  "Daugiamandatė", or the constituency's number and name linking
  ``rvapgl.htm-<district>.htm`` — and the nominator. The source.
- ``rdl.htm-13.htm`` — the list results: votes, percentage and mandates
  per list (the cross-check for the 70 list seats) and the links to the
  15 ``rdpbl.htm-<list>.htm`` preference pages, which give every list
  candidate's post-election rank, pre-election number, preference votes
  ("rinkiminis reitingas"), the party rating VRK computed from the
  pre-election number and the list's size, and their product (the rating
  points the post-election order follows); joined into the record as for
  the 2004 elections, with the two 2000-only ratings alongside.
- ``rvapgl.htm-<district>.htm`` — the 71 constituency pages, each the
  candidates in descending vote order with ballot-box, postal and total
  votes and the share of valid ballots, rowed under the candidate page's
  own id (the 2004 tree used a separate results id, so there the
  constituency votes could not be joined; here they are). The 2000
  election decided every constituency in one round by plurality
  ("Seimo nariu išrinktas kandidatas, už kurį paduota daugiausia
  balsų"), so the first row is the winner, cross-checked against the
  members page.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.seimo_2000.sitemap import (
    CANDIDATE_PAGE_PATTERN,
    ELECTION_ID,
    SITE_ROOT,
    normalize_space,
)
from scraper.shared.election_results import (
    fetch_page,
    load_sitemap_entries,
    resolve_url,
    write_results,
)

MEMBERS_PAGE = "ril.htm-13+2.htm"
LIST_RESULTS_PAGE = "rdl.htm-13.htm"
CONSTITUENCY_RESULTS_INDEX = "rvapgsarl.htm-13.htm"
PREFERENCE_PAGE_PATTERN = re.compile(r"rdpbl\.htm-(\d+)\.htm$")
CONSTITUENCY_RESULT_PATTERN = re.compile(r"rvapgl\.htm-(\d+)\.htm$")
LIST_SEATS = 70
CONSTITUENCY_SEATS = 71

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


def _percent(text: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*%", text)
    return float(match.group(1).replace(",", ".")) if match else None


def _candidate_table(soup: BeautifulSoup) -> Tag | None:
    for table in soup.find_all("table"):
        if any(CANDIDATE_PAGE_PATTERN.search(a["href"]) for a in table.find_all("a", href=True)):
            return table
    return None


def _candidate_anchor(cell: Tag) -> Tag | None:
    for anchor in cell.find_all("a", href=True):
        if CANDIDATE_PAGE_PATTERN.search(anchor["href"]):
            return anchor
    return None


def parse_members_page(html: str, base_url: str) -> list[dict[str, Any]]:
    """Rows of the members page: VRK id, name, seat, constituency (id,
    number, name) or list, nominator."""
    soup = BeautifulSoup(html, "lxml")
    table = _candidate_table(soup)
    members: list[dict[str, Any]] = []
    if table is None:
        return members
    for tr in _own_rows(table):
        cells = _own_cells(tr)
        if len(cells) < 4:
            continue
        anchor = _candidate_anchor(cells[0])
        if anchor is None:
            continue
        number_text = normalize_space(cells[1].get_text(" ", strip=True)).rstrip(".")
        seat_text = normalize_space(cells[2].get_text(" ", strip=True))
        district_anchor = cells[2].find("a", href=True)
        district_match = (
            CONSTITUENCY_RESULT_PATTERN.search(district_anchor["href"]) if district_anchor is not None else None
        )
        member: dict[str, Any] = {
            "vrkCandidateId": CANDIDATE_PAGE_PATTERN.search(anchor["href"]).group(1),
            "name": normalize_space(anchor.get_text(" ", strip=True)),
            "party": normalize_space(cells[3].get_text(" ", strip=True)),
            "candidateUrl": resolve_url(anchor["href"], base_url),
        }
        if district_match is not None:
            member["seat"] = "vienmandate"
            member["districtId"] = district_match.group(1)
            member["districtNumber"] = int(number_text) if number_text.isdigit() else None
            member["districtName"] = seat_text
        else:
            member["seat"] = "daugiamandate"
        members.append(member)
    return members


def parse_list_results_page(html: str) -> list[dict[str, Any]]:
    """The list results: number, name, list key, votes, share, mandates."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        anchors = [a for a in table.find_all("a", href=True) if PREFERENCE_PAGE_PATTERN.search(a["href"])]
        if not anchors:
            continue
        for tr in _own_rows(table):
            cells = _own_cells(tr)
            if len(cells) < 5:
                continue
            anchor = None
            for candidate in cells[1].find_all("a", href=True):
                if PREFERENCE_PAGE_PATTERN.search(candidate["href"]):
                    anchor = candidate
                    break
            if anchor is None:
                continue
            rows.append(
                {
                    "listNumber": _int(cells[0].get_text(" ", strip=True)),
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "listId": PREFERENCE_PAGE_PATTERN.search(anchor["href"]).group(1),
                    "votes": _int(cells[2].get_text(" ", strip=True)),
                    "percent": _percent(cells[3].get_text(" ", strip=True)),
                    "mandates": _int(cells[4].get_text(" ", strip=True)),
                }
            )
        break
    return rows


def parse_preference_page(html: str) -> list[dict[str, Any]]:
    """Rows of one list's preference page: post-election rank, VRK id,
    name, pre-election number, preference votes, party rating, rating
    points."""
    soup = BeautifulSoup(html, "lxml")
    table = _candidate_table(soup)
    rows: list[dict[str, Any]] = []
    if table is None:
        return rows
    for tr in _own_rows(table):
        cells = _own_cells(tr)
        if len(cells) < 6:
            continue
        anchor = _candidate_anchor(cells[1])
        if anchor is None:
            continue
        rows.append(
            {
                "rank": _int(cells[0].get_text(" ", strip=True)),
                "vrkCandidateId": CANDIDATE_PAGE_PATTERN.search(anchor["href"]).group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "listPosition": _int(cells[2].get_text(" ", strip=True)),
                "preferenceVotes": _int(cells[3].get_text(" ", strip=True)),
                "partyRating": _int(cells[4].get_text(" ", strip=True)),
                "ratingPoints": _int(cells[5].get_text(" ", strip=True)),
            }
        )
    return rows


def parse_constituency_page(html: str) -> dict[str, Any]:
    """One constituency's results: the turnout line, the status sentence
    and the candidates in the page's (descending-vote) order with their
    ballot-box, postal and total votes and share."""
    soup = BeautifulSoup(html, "lxml")
    heading = ""
    for font in soup.find_all("font", attrs={"size": "5"}):
        text = normalize_space(font.get_text(" ", strip=True))
        if "apygarda" in text.lower():
            heading = text
            break
    text = normalize_space(soup.get_text(" ", strip=True))
    status_match = re.search(r"(Rinkimai apygardoje[^.]*\.(?:[^.]*\.)?)", text)
    voters = re.search(r"rinkėjų skaičius:\s*(\d+)\s*,\s*iš jų rinkimuose dalyvavo:\s*(\d+)\s*\(\s*([\d.,]+)%", text)
    table = _candidate_table(soup)
    candidates: list[dict[str, Any]] = []
    if table is not None:
        for tr in _own_rows(table):
            cells = _own_cells(tr)
            if len(cells) < 5:
                continue
            anchor = _candidate_anchor(cells[0])
            if anchor is None:
                continue
            candidates.append(
                {
                    "vrkCandidateId": CANDIDATE_PAGE_PATTERN.search(anchor["href"]).group(1),
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "ballotBox": _int(cells[1].get_text(" ", strip=True)),
                    "postal": _int(cells[2].get_text(" ", strip=True)),
                    "total": _int(cells[3].get_text(" ", strip=True)),
                    "percent": _percent(cells[4].get_text(" ", strip=True)),
                }
            )
    return {
        "heading": heading,
        "status": normalize_space(status_match.group(1)) if status_match else None,
        "voters": int(voters.group(1)) if voters else None,
        "turnout": int(voters.group(2)) if voters else None,
        "turnoutPercent": float(voters.group(3).replace(",", ".")) if voters else None,
        "candidates": candidates,
    }


def _links(html: str, base_url: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    seen: list[str] = []
    out: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        match = pattern.search(anchor["href"])
        if match is None:
            continue
        url = resolve_url(anchor["href"], base_url)
        if url in seen:
            continue
        seen.append(url)
        out.append((url, match.group(1)))
    return out


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    entries = load_sitemap_entries(sitemap_path)
    by_id = {entry["vrkCandidateId"]: entry for entry in entries if entry.get("vrkCandidateId")}

    members_url = SITE_ROOT + MEMBERS_PAGE
    members = parse_members_page(fetch_page(results_dir, members_url), members_url)

    elected: dict[str, dict[str, Any]] = {}
    not_in_sitemap: list[dict[str, Any]] = []
    role_mismatches: list[dict[str, Any]] = []
    district_mismatches: list[dict[str, Any]] = []
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
            record["districtId"] = member["districtId"]
            record["districtNumber"] = member["districtNumber"]
            record["districtName"] = member["districtName"]
            single = entry.get("vienmandateCandidacy") or {}
            if "vienmandate" not in entry.get("roles", []):
                role_mismatches.append(member)
            elif single.get("apygardosId") != member["districtId"]:
                district_mismatches.append({"member": member, "sitemap": single})
        elif "daugiamandate" not in entry.get("roles", []):
            role_mismatches.append(member)
        elected[member["vrkCandidateId"]] = record
    member_list_ids = {m["vrkCandidateId"] for m in members if m["seat"] == "daugiamandate"}
    member_district_winner = {m["districtId"]: m["vrkCandidateId"] for m in members if m["seat"] == "vienmandate"}

    # The list results page's mandate column against the members page's
    # list seats per nominator.
    list_results_url = SITE_ROOT + LIST_RESULTS_PAGE
    list_results_html = fetch_page(results_dir, list_results_url)
    list_rows = parse_list_results_page(list_results_html)
    mandates_by_name = {row["name"]: row["mandates"] for row in list_rows}
    seats_by_name = Counter(m["party"] for m in members if m["seat"] == "daugiamandate")
    list_mandate_mismatches = [
        {"list": name, "declared": mandates_by_name.get(name, 0), "listed": seats_by_name.get(name, 0)}
        for name in sorted(set(mandates_by_name) | set(seats_by_name))
        if mandates_by_name.get(name, 0) != seats_by_name.get(name, 0)
    ]

    # Every list candidate's rank, preference votes and ratings.
    ranking: dict[str, dict[str, Any]] = {}
    preference_urls: list[str] = []
    for url, list_id in _links(list_results_html, list_results_url, PREFERENCE_PAGE_PATTERN):
        preference_urls.append(url)
        for row in parse_preference_page(fetch_page(results_dir, url)):
            ranking[row["vrkCandidateId"]] = {
                "rank": row["rank"],
                "listPosition": row["listPosition"],
                "preferenceVotes": row["preferenceVotes"],
                "partyRating": row["partyRating"],
                "ratingPoints": row["ratingPoints"],
                "listId": list_id,
                "sourceUrl": url,
            }
    list_candidates = {vrk_id for vrk_id, entry in by_id.items() if "daugiamandate" in entry.get("roles", [])}
    position_mismatches = [
        {"vrkCandidateId": vrk_id, "listing": (by_id[vrk_id].get("daugiamandateCandidacy") or {}).get("numerisSarase"), "ranking": row["listPosition"]}
        for vrk_id, row in ranking.items()
        if vrk_id in by_id and (by_id[vrk_id].get("daugiamandateCandidacy") or {}).get("numerisSarase") != row["listPosition"]
    ]
    # The list seats go to each list's top `mandates` ranks, passing over
    # the candidates who took a constituency seat (a member holds one
    # seat; 54 of the 2000 constituency winners also ranked high enough
    # on their list). Derived that way, the seats must be exactly the
    # members page's list half.
    member_district_ids = {m["vrkCandidateId"] for m in members if m["seat"] == "vienmandate"}
    seats_by_rank: set[str] = set()
    for row in list_rows:
        ranked = sorted(
            (r["rank"], vrk_id) for vrk_id, r in ranking.items() if r["listId"] == row["listId"] and r["rank"] is not None
        )
        eligible = [vrk_id for _, vrk_id in ranked if vrk_id not in member_district_ids]
        seats_by_rank.update(eligible[: row["mandates"] or 0])
    rank_seat_mismatches = len(seats_by_rank ^ member_list_ids)

    # Every constituency's votes, by the candidate page id.
    index_url = SITE_ROOT + CONSTITUENCY_RESULTS_INDEX
    constituency_votes: dict[str, dict[str, Any]] = {}
    constituency_urls: list[str] = []
    constituency_pages: list[dict[str, Any]] = []
    winner_mismatches: list[dict[str, Any]] = []
    votes_not_in_sitemap = 0
    statuses: Counter[str] = Counter()
    for url, district_id in _links(fetch_page(results_dir, index_url), index_url, CONSTITUENCY_RESULT_PATTERN):
        constituency_urls.append(url)
        page = parse_constituency_page(fetch_page(results_dir, url))
        statuses[page["status"] or ""] += 1
        constituency_pages.append(
            {
                "districtId": district_id,
                "heading": page["heading"],
                "status": page["status"],
                "voters": page["voters"],
                "turnout": page["turnout"],
                "turnoutPercent": page["turnoutPercent"],
                "candidates": len(page["candidates"]),
                "sourceUrl": url,
            }
        )
        ordered = sorted(page["candidates"], key=lambda c: -(c["total"] or 0))
        for rank, candidate in enumerate(ordered, start=1):
            if candidate["vrkCandidateId"] not in by_id:
                votes_not_in_sitemap += 1
            constituency_votes[candidate["vrkCandidateId"]] = {
                "districtId": district_id,
                "ballotBox": candidate["ballotBox"],
                "postal": candidate["postal"],
                "total": candidate["total"],
                "percent": candidate["percent"],
                "rank": rank,
                "sourceUrl": url,
            }
        top = ordered[0]["vrkCandidateId"] if ordered else None
        if member_district_winner.get(district_id) != top:
            winner_mismatches.append({"districtId": district_id, "topOfPage": top, "member": member_district_winner.get(district_id)})
    district_candidates = {vrk_id for vrk_id, entry in by_id.items() if "vienmandate" in entry.get("roles", [])}
    district_claimed_wrong = sum(
        1
        for vrk_id, row in constituency_votes.items()
        if vrk_id in by_id and (by_id[vrk_id].get("vienmandateCandidacy") or {}).get("apygardosId") != row["districtId"]
    )

    stats = {
        "seats": LIST_SEATS + CONSTITUENCY_SEATS,
        "membersListed": len(members),
        "membersInSitemap": len(elected),
        "membersNotInSitemap": len(not_in_sitemap),
        "listSeats": len(member_list_ids),
        "constituencySeats": len(member_district_winner),
        "roleMismatches": len(role_mismatches),
        "districtMismatches": len(district_mismatches),
        "mandatesDeclared": sum(row["mandates"] or 0 for row in list_rows),
        "listMandateMismatches": len(list_mandate_mismatches),
        "rankingPages": len(preference_urls),
        "candidatesRanked": len(ranking),
        "rankedNotInSitemap": sum(1 for vrk_id in ranking if vrk_id not in by_id),
        "listCandidatesNotRanked": len(list_candidates - set(ranking)),
        "listPositionMismatches": len(position_mismatches),
        "rankSeatMismatches": rank_seat_mismatches,
        "constituencyPages": len(constituency_urls),
        "constituencyCandidatesWithVotes": len(constituency_votes),
        "constituencyVotesNotInSitemap": votes_not_in_sitemap,
        "constituencyCandidatesWithoutVotes": len(district_candidates - set(constituency_votes)),
        "constituencyVotesDistrictWrong": district_claimed_wrong,
        "constituencyWinnerMismatches": len(winner_mismatches),
        "constituencyStatuses": dict(statuses),
    }
    details = {
        "notInSitemap": not_in_sitemap,
        "roleMismatches": role_mismatches,
        "districtMismatches": district_mismatches,
        "mandatesByList": list_rows,
        "listMandateMismatches": list_mandate_mismatches,
        "ranking": ranking,
        "listPositionMismatches": position_mismatches,
        "constituencyPages": constituency_pages,
        "constituencyWinnerMismatches": winner_mismatches,
        "constituencyVotes": constituency_votes,
    }
    write_results(
        output_path,
        ELECTION_ID,
        elected,
        stats,
        [members_url, list_results_url, *preference_urls, index_url, *constituency_urls],
        details,
    )
    return output_path, stats


__all__ = [
    "MEMBERS_PAGE",
    "build_results",
    "parse_constituency_page",
    "parse_list_results_page",
    "parse_members_page",
    "parse_preference_page",
]
