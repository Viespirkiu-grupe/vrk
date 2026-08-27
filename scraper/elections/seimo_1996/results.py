"""Elected status, votes and list ranking for the 1996-10-20 Seimas election.

The 1996 general election is the only one of the 1996-1999 archive family
whose seats were not all decided constituency by constituency: 71 single-member
seats over two rounds *and* 70 list seats. VRK published all of it under
`seim96`, and — unlike the by-elections — it published the answer directly:

- `rsnl.htm-1.htm` — "Kandidatai, išrinkti Seimo nariais": the 137 members
  seated on election night, each with their `kandvl.htm-<ID>.htm` link (so the
  join is by id), their nominator and their seat, which reads "pagal sąrašą",
  "I ture" or "II ture". **The source.** 137 rather than 141 because four
  constituencies failed their turnout threshold and went to the 1997-03-23
  repeat election, which this module cross-checks.
- `rapgs1l.htm` / `rapgs2l.htm` — the round-one and round-two indexes, linking
  71 and 65 `rapgpl.htm-<apygarda>+<round>.htm` constituency pages. They are
  the cross-check for the 67 constituency winners (2 decided in round one, 65
  in the runoff) and the source of every candidate's votes.
- `rdl.htm` — the list results: votes, share and mandate count per list (the
  cross-check for the 70 list seats), and the link to each list's
  `rkreitl.htm-<list>.htm` ranking page.
- `rkreitl.htm-<list>.htm` — the list in its post-election order, with each
  candidate's positive and negative preference votes and the rating points VRK
  ordered them by. Joined into the record for every list candidate, and the
  cross-check for the allocation itself: strike the list's constituency winners
  and the top *M* of what is left is exactly the members page's list winners
  for that list — verified for all five lists that won mandates.

The corpus's 879 records are the candidates who stood in a constituency (the
sitemap is built from the constituency listings), so the 17 members elected on
a list alone are named on the members page and have no record to carry the
flag; they are reported rather than silently dropped.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup

from scraper.elections.seimo_1996.sitemap import ELECTION_ID
from scraper.shared.election_results import fetch_page, resolve_url, write_results
from scraper.shared.seimo_archive_1990s_results import (
    collect_constituency_votes,
    count_seats,
    load_archive_sitemap,
    parse_elected_members,
    parse_list_results,
    parse_ranking_page,
    read_constituency_pages,
    resolve_page_winners,
)

RESULTS_ROOT = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seim96/"
MEMBERS_PAGE = "rsnl.htm-1.htm"
LIST_RESULTS_PAGE = "rdl.htm"
ROUND_INDEX_PAGES = {1: "rapgs1l.htm", 2: "rapgs2l.htm"}
CONSTITUENCY_PAGE_PATTERN = re.compile(r"rapgpl\.htm-(\d+)\+(\d)\.htm$")
LIST_SEATS = 70
CONSTITUENCY_SEATS = 71

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def constituency_page_urls(results_dir: Path) -> list[dict[str, Any]]:
    """Every constituency results page, from the two round indexes."""
    pages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for round_number, index_page in ROUND_INDEX_PAGES.items():
        index_url = RESULTS_ROOT + index_page
        soup = BeautifulSoup(fetch_page(results_dir, index_url), "lxml")
        for anchor in soup.find_all("a", href=CONSTITUENCY_PAGE_PATTERN):
            url = resolve_url(anchor["href"], index_url)
            if url in seen:
                continue
            seen.add(url)
            pages.append({"url": url, "round": round_number, "indexUrl": index_url})
    return pages


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    entries = load_archive_sitemap(sitemap_path)
    in_sitemap = {entry["vrkCandidateId"] for entry in entries if entry["vrkCandidateId"]}

    members_url = RESULTS_ROOT + MEMBERS_PAGE
    members = parse_elected_members(fetch_page(results_dir, members_url), members_url)

    pages = read_constituency_pages(constituency_page_urls(results_dir), results_dir)
    votes, unresolved_rows = collect_constituency_votes(pages, entries)
    page_winners, unresolved_winners = resolve_page_winners(pages, entries)

    # Every list's mandate count and ranking page.
    list_results_url = RESULTS_ROOT + LIST_RESULTS_PAGE
    lists = parse_list_results(fetch_page(results_dir, list_results_url), list_results_url)
    ranking: dict[str, dict[str, Any]] = {}
    ranking_by_list: dict[str, list[dict[str, Any]]] = {}
    ranking_urls: list[str] = []
    for row in lists:
        if not row["rankingUrl"]:
            continue
        ranking_urls.append(row["rankingUrl"])
        list_rows = parse_ranking_page(fetch_page(results_dir, row["rankingUrl"]), row["rankingUrl"])
        ranking_by_list[row["listId"]] = list_rows
        for entry in list_rows:
            ranking.setdefault(entry["vrkCandidateId"], {})[row["listId"]] = {
                "listId": row["listId"],
                "list": row["name"],
                "rank": entry["rank"],
                "listPosition": entry["listPosition"],
                "positiveVotes": entry["positiveVotes"],
                "negativeVotes": entry["negativeVotes"],
                "ratingPoints": entry["ratingPoints"],
                "sourceUrl": entry["sourceUrl"],
            }

    # The members page is the source; the constituency it names is taken from
    # the constituency pages, which are also the cross-check on the seat.
    elected: dict[str, dict[str, Any]] = {}
    members_not_in_sitemap: list[dict[str, Any]] = []
    seat_mismatches: list[dict[str, Any]] = []
    for member in members:
        winner = page_winners.get(member["vrkCandidateId"])
        record: dict[str, Any] = {
            "seat": member["seat"],
            "method": "members-list",
            "sourceUrl": members_url,
            "nominator": member["nominator"],
            "selfNominated": member["selfNominated"],
        }
        if member["seat"] == "vienmandate":
            if winner is None:
                seat_mismatches.append({"member": member, "reason": "no-constituency-verdict"})
            else:
                record["round"] = winner["round"]
                record["constituency"] = winner["constituency"]
                record["constituencyNumber"] = winner["constituencyNumber"]
                record["constituencySourceUrl"] = winner["sourceUrl"]
                if member["round"] is not None and member["round"] != winner["round"]:
                    seat_mismatches.append(
                        {"member": member, "reason": "round-mismatch", "page": winner}
                    )
        elif winner is not None:
            seat_mismatches.append({"member": member, "reason": "list-seat-won-a-constituency"})
        if member["vrkCandidateId"] not in in_sitemap:
            members_not_in_sitemap.append(member)
            continue
        elected[member["vrkCandidateId"]] = record

    # Cross-check one: the constituency pages' own verdicts against the
    # members page, by id.
    member_constituency_ids = {m["vrkCandidateId"] for m in members if m["seat"] == "vienmandate"}
    constituency_page_diff = sorted(set(page_winners) ^ member_constituency_ids)

    # Cross-check two: the mandate column of the list results page against the
    # list seats the members page hands each list, by list name.
    mandates_by_list = {row["name"]: row["mandates"] for row in lists}
    seats_by_list = Counter(m["nominator"] for m in members if m["seat"] == "daugiamandate")
    list_mandate_mismatches = [
        {
            "list": name,
            "declared": mandates_by_list.get(name, 0),
            "listed": seats_by_list.get(name, 0),
        }
        for name in sorted(set(mandates_by_list) | set(seats_by_list))
        if mandates_by_list.get(name, 0) != seats_by_list.get(name, 0)
    ]

    # Cross-check three: the allocation itself. A candidate who won a
    # constituency seat is struck from their list, and the mandates go to the
    # top of what is left of the post-preference order.
    list_winner_ids = {m["vrkCandidateId"] for m in members if m["seat"] == "daugiamandate"}
    allocation_mismatches: list[dict[str, Any]] = []
    allocations_checked = 0
    for row in lists:
        if not row["mandates"] or row["listId"] not in ranking_by_list:
            continue
        allocations_checked += 1
        order = [
            entry["vrkCandidateId"]
            for entry in ranking_by_list[row["listId"]]
            if entry["vrkCandidateId"] not in member_constituency_ids
        ]
        derived = set(order[: row["mandates"]])
        published = {
            entry["vrkCandidateId"]
            for entry in ranking_by_list[row["listId"]]
            if entry["vrkCandidateId"] in list_winner_ids
        }
        if derived != published:
            allocation_mismatches.append(
                {
                    "list": row["name"],
                    "listId": row["listId"],
                    "derivedOnly": sorted(derived - published),
                    "publishedOnly": sorted(published - derived),
                }
            )

    not_held = [page for page in pages if page["held"] is False]
    ranked_not_in_sitemap = sum(1 for vrk_id in ranking if vrk_id not in in_sitemap)

    stats = {
        "seats": LIST_SEATS + CONSTITUENCY_SEATS,
        "membersListed": len(members),
        "membersInSitemap": len(elected),
        "membersNotInSitemap": len(members_not_in_sitemap),
        "seatsByType": count_seats(elected),
        "listSeats": len(list_winner_ids),
        "constituencySeats": len(member_constituency_ids),
        "constituencySeatsFirstRound": sum(
            1 for m in members if m["seat"] == "vienmandate" and m["round"] == 1
        ),
        "constituencySeatsRunoff": sum(
            1 for m in members if m["seat"] == "vienmandate" and m["round"] == 2
        ),
        "constituencyPages": len(pages),
        "constituenciesNotHeld": len(not_held),
        # Each page's own round heading against the index page that linked it.
        "roundMismatches": sum(1 for page in pages if page["roundMismatch"]),
        "constituencyPageDiff": len(constituency_page_diff),
        "seatMismatches": len(seat_mismatches),
        "candidatesWithVotes": len(votes),
        "candidatesWithoutVotes": len(in_sitemap - set(votes)),
        "unresolvedRows": len(unresolved_rows),
        "unresolvedWinners": len(unresolved_winners),
        "mandatesDeclared": sum(row["mandates"] for row in lists),
        "listMandateMismatches": len(list_mandate_mismatches),
        "rankingPages": len(ranking_urls),
        "candidatesRanked": len(ranking),
        "rankedNotInSitemap": ranked_not_in_sitemap,
        "allocationsChecked": allocations_checked,
        "allocationMismatches": len(allocation_mismatches),
    }
    details = {
        "membersNotInSitemap": members_not_in_sitemap,
        "seatMismatches": seat_mismatches,
        "constituencyPageDiff": constituency_page_diff,
        "constituenciesNotHeld": [
            {
                "constituency": page["constituencyName"],
                "constituencyNumber": page["constituencyNumber"],
                "sourceUrl": page["sourceUrl"],
            }
            for page in not_held
        ],
        "constituencies": [
            {key: value for key, value in page.items() if key != "candidates"} for page in pages
        ],
        "constituencyVotes": votes,
        "unresolvedRows": unresolved_rows,
        "unresolvedWinners": unresolved_winners,
        "lists": lists,
        "listMandateMismatches": list_mandate_mismatches,
        "allocationMismatches": allocation_mismatches,
        "ranking": ranking,
    }
    write_results(
        output_path,
        ELECTION_ID,
        elected,
        stats,
        [members_url, list_results_url, *ranking_urls, *(page["sourceUrl"] for page in pages)],
        details,
    )
    return output_path, stats


__all__ = ["MEMBERS_PAGE", "RESULTS_ROOT", "build_results", "constituency_page_urls"]
