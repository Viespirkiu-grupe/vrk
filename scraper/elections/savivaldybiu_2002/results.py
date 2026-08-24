"""Elected status, preference votes and the council-term join for the
2002-12-22 municipal general, from VRK's ``rinkimai/2002/savivaldybes``
tree.

The candidate page marks no winner. Per municipality the tree publishes:

- ``rezultatai/rapgpl_<APYG>.htm`` — the list results: voters, turnout,
  valid and invalid ballots, the seat quota, and per list the
  ballot-box, postal and total votes and the mandates ("-" below the
  threshold), with a totals row; each list links its preference page.
  The first column is the list's ballot number, the same number the
  listing pages head the list with.
- ``rezultatai/rikl_<APYG>.htm`` — "Kandidatai, gavę mandatus": every
  seat winner with the anketa link (so the join is by ``asm_kod``),
  the list (linking its preference page) and the post-election rank;
  "Mandatų skaičius: N" above. The ``isrinktas`` source.
- ``rezultatai/rpbapgl_<APYG>_<SEQ>.htm`` — the list's preference
  votes: every candidate's post-election rank, preference votes and
  pre-election number, the winners in bold. ``SEQ`` is VRK's internal
  list id; the page set is discovered from the ``rapgpl`` links and
  mapped back to ballot numbers there.
- ``savtaryb/sav_apg_l_<APYG>_1.htm`` — "Tarybos nariai": the council
  **as it stood when VRK froze the page**, not a union over the term —
  each row a member with the party, the post-election rank, the anketa
  link and "Nuo kada tarybos narys": election day (2002.12.22) for a
  member serving since the election, a later date for a substitute who
  came in when a member left, whose row then replaces the departed
  member's. Every election-day row must be a ``rikl`` winner; a winner
  with no council row is one who left mid-term (562 of the 1,560). The
  dates join the record as ``tarybosNarysNuo`` without touching
  ``isrinktas``.

Cross-checks: the members page's count against its own "Mandatų
skaičius", the list results' mandate column and its totals row; every
member in the sitemap, in the municipality and on the list the sitemap
says; the bold names on the preference pages exactly the members; each
list's members exactly its top ranks; every sitemap candidate ranked,
with the pre-election number the listing's; the election-day council
rows exactly the members, the later rows all sitemap candidates; and
the seat total against the national mandate summary
(``rezultatai/mandatai/mlt_15_1.html``).
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.savivaldybiu_2002.sitemap import (
    ANKETA_PAGE_PATTERN,
    ELECTION_ID,
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

REZULTATAI_ROOT = SITE_ROOT + "rezultatai/"
SAVTARYB_ROOT = SITE_ROOT + "savtaryb/"
RESULTS_INDEX_URL = REZULTATAI_ROOT + "rapgsarl_15.htm"
MANDATE_SUMMARY_URL = REZULTATAI_ROOT + "mandatai/mlt_15_1.html"

RESULTS_PAGE_PATTERN = re.compile(r"rapgpl_(\d+)\.htm$")
PREFERENCE_PAGE_PATTERN = re.compile(r"rpbapgl_(\d+)_(\d+)\.htm$")
COUNCIL_DATE_PATTERN = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})$")

ELECTION_DAY = "2002-12-22"

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
        if ANKETA_PAGE_PATTERN.search(anchor["href"]):
            return anchor
    return None


def _council_date(text: str) -> str | None:
    match = COUNCIL_DATE_PATTERN.match(normalize_space(text))
    if match is None:
        return None
    return "-".join(match.groups())


def parse_municipality_results_page(html: str) -> dict[str, Any]:
    """One rapgpl page: the turnout line, the quota, per list the ballot
    number, votes and mandates (None where the page prints "-"), the
    totals row."""
    soup = BeautifulSoup(html, "lxml")
    text = normalize_space(soup.get_text(" ", strip=True))
    voters = re.search(
        r"Bendras rinkėjų skaičius:\s*(\d+)\s*,\s*rinkimuose dalyvavo:\s*(\d+)\s*\(\s*([\d.,]+)%", text
    )
    ballots = re.search(
        r"Galiojančių biuletenių:\s*(\d+)\s*\(\s*[\d.,]+\s*%\s*\)\s*,\s*negaliojančių:\s*(\d+)", text
    )
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
                continue
            match = PREFERENCE_PAGE_PATTERN.search(anchor["href"])
            lists.append(
                {
                    "listNumber": int(number_text) if number_text.isdigit() else None,
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "apygardosId": match.group(1),
                    "listSeq": match.group(2),
                    "preferenceUrl": resolve_url(anchor["href"], REZULTATAI_ROOT),
                    **row,
                }
            )
        if lists or total:
            break
    return {
        "voters": int(voters.group(1)) if voters else None,
        "turnout": int(voters.group(2)) if voters else None,
        "turnoutPercent": float(voters.group(3).replace(",", ".")) if voters else None,
        "validBallots": int(ballots.group(1)) if ballots else None,
        "invalidBallots": int(ballots.group(2)) if ballots else None,
        "quota": int(quota.group(1)) if quota else None,
        "lists": lists,
        "total": total,
    }


def parse_members_page(html: str) -> dict[str, Any]:
    """One rikl page: the declared seat count and every winner with
    ``asm_kod``, name, list (its preference-page id and name) and
    post-election rank."""
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
            list_match = (
                PREFERENCE_PAGE_PATTERN.search(list_anchor["href"]) if list_anchor is not None else None
            )
            members.append(
                {
                    "vrkCandidateId": ANKETA_PAGE_PATTERN.search(anchor["href"]).group(1),
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "listName": normalize_space(cells[1].get_text(" ", strip=True)),
                    "listSeq": list_match.group(2) if list_match else None,
                    "rank": _int(cells[2].get_text(" ", strip=True)),
                }
            )
        break
    return {"seats": int(seats.group(1)) if seats else None, "members": members}


def parse_preference_page(html: str) -> dict[str, Any]:
    """One rpbapgl page: the list's total votes and per candidate the
    post-election rank, ``asm_kod``, preference votes, pre-election
    number and whether the row is bold (a mandate)."""
    soup = BeautifulSoup(html, "lxml")
    text = normalize_space(soup.get_text(" ", strip=True))
    list_votes = re.search(r"Už partiją/koaliciją paduotų balsų skaičius:\s*(\d+)", text)
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
                    "vrkCandidateId": ANKETA_PAGE_PATTERN.search(anchor["href"]).group(1),
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "preferenceVotes": _int(cells[2].get_text(" ", strip=True)),
                    "listPosition": _int(cells[3].get_text(" ", strip=True)),
                    "mandate": anchor.find("b") is not None or anchor.find_parent("b") is not None,
                }
            )
        break
    return {"listVotes": int(list_votes.group(1)) if list_votes else None, "rows": rows}


def parse_council_page(html: str) -> dict[str, Any]:
    """One sav_apg_l page: the declared seat count and every council
    member of the term with ``asm_kod``, the party the row names, the
    post-election rank and the ISO "member since" date."""
    soup = BeautifulSoup(html, "lxml")
    text = normalize_space(soup.get_text(" ", strip=True))
    seats = re.search(r"Mandatų skaičius\s*:\s*(\d+)", text)
    members: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        if _candidate_anchor(table) is None:
            continue
        for tr in _own_rows(table):
            cells = _own_cells(tr)
            if len(cells) < 4:
                continue
            anchor = _candidate_anchor(cells[2])
            if anchor is None:
                continue
            members.append(
                {
                    "vrkCandidateId": ANKETA_PAGE_PATTERN.search(anchor["href"]).group(1),
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "party": normalize_space(cells[0].get_text(" ", strip=True)),
                    "rank": _int(cells[1].get_text(" ", strip=True)),
                    "nuo": _council_date(cells[3].get_text(" ", strip=True)),
                }
            )
        break
    return {"seats": int(seats.group(1)) if seats else None, "members": members}


def parse_mandate_summary(html: str) -> dict[str, Any]:
    """The national summary: mandates per party/coalition and the total."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    total: int | None = None
    for table in soup.find_all("table"):
        header = normalize_space(table.get_text(" ", strip=True))
        if "mandat" not in header.lower():
            continue
        for tr in _own_rows(table):
            cells = _own_cells(tr)
            if len(cells) < 2:
                continue
            label = normalize_space(cells[0].get_text(" ", strip=True))
            value = _int(cells[-1].get_text(" ", strip=True))
            if not label or value is None:
                continue
            if label.lower().startswith("iš viso"):
                total = value
            elif not label.rstrip(".").isdigit():
                rows.append({"name": label, "mandates": value})
        if rows or total is not None:
            break
    if total is None and rows:
        # The 2002 page prints no totals row; the total is the sum.
        total = sum(row["mandates"] for row in rows)
    return {"parties": rows, "total": total}


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    entries = load_sitemap_entries(sitemap_path)
    by_id = {entry["vrkCandidateId"]: entry for entry in entries if entry.get("vrkCandidateId")}

    index_html = fetch_page(results_dir, RESULTS_INDEX_URL)
    municipalities: list[dict[str, Any]] = []
    seen: set[str] = set()
    soup = BeautifulSoup(index_html, "lxml")
    for anchor in soup.find_all("a", href=True):
        match = RESULTS_PAGE_PATTERN.search(anchor["href"])
        if match is None or match.group(1) in seen:
            continue
        seen.add(match.group(1))
        municipalities.append(
            {
                "apygardosId": match.group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "resultsUrl": resolve_url(anchor["href"], REZULTATAI_ROOT),
            }
        )

    # The listing index gives the municipality numbers the results pages
    # only carry in prose.
    numbers_by_id: dict[str, int | None] = {}
    listing_sample = Path(f"samples/html/{ELECTION_ID}/list.html")
    if listing_sample.exists():
        for row in extract_municipality_links(listing_sample.read_text(encoding="utf-8")):
            numbers_by_id[row["apygardosId"]] = row["number"]

    elected: dict[str, dict[str, Any]] = {}
    ranking: dict[str, dict[str, Any]] = {}
    council: dict[str, dict[str, Any]] = {}
    list_results: dict[str, dict[str, dict[str, Any]]] = {}
    per_municipality: list[dict[str, Any]] = []
    not_in_sitemap: list[dict[str, Any]] = []
    municipality_mismatches: list[dict[str, Any]] = []
    list_mismatches: list[dict[str, Any]] = []
    seat_count_mismatches: list[dict[str, Any]] = []
    council_day_mismatches: list[dict[str, Any]] = []
    council_size_mismatches: list[dict[str, Any]] = []
    substitutes_not_in_sitemap: list[dict[str, Any]] = []
    rank_mismatches = 0
    bold_diff = 0
    top_rank_diff = 0
    position_mismatches = 0
    list_vote_mismatches = 0
    substitutes = 0
    replaced_members = 0
    sources: list[str] = [RESULTS_INDEX_URL]

    for municipality in municipalities:
        apygarda_id = municipality["apygardosId"]
        results_url = municipality["resultsUrl"]
        members_url = f"{REZULTATAI_ROOT}rikl_{apygarda_id}.htm"
        council_url = f"{SAVTARYB_ROOT}sav_apg_l_{apygarda_id}_1.htm"
        page = parse_municipality_results_page(fetch_page(results_dir, results_url))
        sources.append(results_url)
        seq_to_number: dict[str, int | None] = {}
        for row in page["lists"]:
            seq_to_number[row["listSeq"]] = row["listNumber"]
            list_results.setdefault(apygarda_id, {})[str(row["listNumber"])] = {
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

        members_page = parse_members_page(fetch_page(results_dir, members_url))
        sources.append(members_url)
        members = members_page["members"]
        if not (len(members) == members_page["seats"] == mandates_sum == total_mandates):
            seat_count_mismatches.append(
                {
                    "apygardosId": apygarda_id,
                    "members": len(members),
                    "declared": members_page["seats"],
                    "mandatesSum": mandates_sum,
                    "totalsRow": total_mandates,
                }
            )
        member_ids = {member["vrkCandidateId"] for member in members}
        for member in members:
            list_number = seq_to_number.get(member["listSeq"])
            entry = by_id.get(member["vrkCandidateId"])
            if entry is None:
                not_in_sitemap.append({**member, "apygardosId": apygarda_id})
                continue
            if entry["municipality"]["apygardosId"] != apygarda_id:
                municipality_mismatches.append({"member": member, "sitemap": entry["municipality"]})
            if entry["list"]["numeris"] != list_number:
                list_mismatches.append(
                    {"member": member, "listNumber": list_number, "sitemap": entry["list"]}
                )
            elected[member["vrkCandidateId"]] = {
                "seat": "tarybos-narys",
                "sourceUrl": members_url,
                "municipality": municipality["name"],
                "apygardosId": apygarda_id,
                "listName": member["listName"],
                "listNumber": list_number,
                "rank": member["rank"],
            }

        # Every list's preference page.
        bold_ids: set[str] = set()
        for row in page["lists"]:
            url = row["preferenceUrl"]
            sources.append(url)
            preference_page = parse_preference_page(fetch_page(results_dir, url))
            if (
                preference_page["listVotes"] is not None
                and row["total"] is not None
                and preference_page["listVotes"] != row["total"]
            ):
                list_vote_mismatches += 1
            ranked_ids: list[str] = []
            for item in sorted(preference_page["rows"], key=lambda r: r["rank"] or 0):
                ranked_ids.append(item["vrkCandidateId"])
                ranking[item["vrkCandidateId"]] = {
                    "rank": item["rank"],
                    "listPosition": item["listPosition"],
                    "preferenceVotes": item["preferenceVotes"],
                    "mandate": item["mandate"],
                    "apygardosId": apygarda_id,
                    "listNumber": row["listNumber"],
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
            list_member_ids = {
                member["vrkCandidateId"]
                for member in members
                if seq_to_number.get(member["listSeq"]) == row["listNumber"]
            }
            if set(ranked_ids[: row["mandates"] or 0]) != list_member_ids:
                top_rank_diff += 1
        bold_diff += len(bold_ids ^ member_ids)

        # The council as frozen: election-day rows must all be winners;
        # a winner with no row left mid-term and a substitute's row
        # (later date) stands in the departed member's place.
        council_page = parse_council_page(fetch_page(results_dir, council_url))
        sources.append(council_url)
        day_ids: set[str] = set()
        for member in council_page["members"]:
            if member["nuo"] == ELECTION_DAY:
                day_ids.add(member["vrkCandidateId"])
            else:
                substitutes += 1
                if member["vrkCandidateId"] not in by_id:
                    substitutes_not_in_sitemap.append({**member, "apygardosId": apygarda_id})
            council[member["vrkCandidateId"]] = {
                "nuo": member["nuo"],
                "party": member["party"],
                "rank": member["rank"],
                "apygardosId": apygarda_id,
                "sourceUrl": council_url,
            }
        replaced_members += len(member_ids - day_ids)
        if day_ids - member_ids:
            council_day_mismatches.append(
                {
                    "apygardosId": apygarda_id,
                    "electionDayRowsNotMembers": sorted(day_ids - member_ids),
                }
            )
        if len(council_page["members"]) != members_page["seats"]:
            council_size_mismatches.append(
                {
                    "apygardosId": apygarda_id,
                    "councilRows": len(council_page["members"]),
                    "seats": members_page["seats"],
                }
            )

        per_municipality.append(
            {
                "apygardosId": apygarda_id,
                "number": numbers_by_id.get(apygarda_id),
                "name": municipality["name"],
                "voters": page["voters"],
                "turnout": page["turnout"],
                "turnoutPercent": page["turnoutPercent"],
                "validBallots": page["validBallots"],
                "invalidBallots": page["invalidBallots"],
                "quota": page["quota"],
                "seats": members_page["seats"],
                "members": len(members),
                "councilRows": len(council_page["members"]),
                "lists": len(page["lists"]),
                "listsWithSeats": sum(1 for row in page["lists"] if row["mandates"]),
                "resultsUrl": results_url,
                "membersUrl": members_url,
                "councilUrl": council_url,
            }
        )

    summary = parse_mandate_summary(fetch_page(results_dir, MANDATE_SUMMARY_URL))
    sources.append(MANDATE_SUMMARY_URL)

    stats = {
        "municipalities": len(municipalities),
        "councilMembers": len(elected),
        "membersOnPages": len(elected) + len(not_in_sitemap),
        "councilNotInSitemap": len(not_in_sitemap),
        "municipalityMismatches": len(municipality_mismatches),
        "listMismatches": len(list_mismatches),
        "seatCountMismatches": len(seat_count_mismatches),
        "rankMismatches": rank_mismatches,
        "boldNotMembers": bold_diff,
        "listTopRanksNotMembers": top_rank_diff,
        "listVoteMismatches": list_vote_mismatches,
        "candidatesRanked": len(ranking),
        "rankedNotInSitemap": sum(1 for vrk_id in ranking if vrk_id not in by_id),
        "sitemapNotRanked": sum(1 for vrk_id in by_id if vrk_id not in ranking),
        "listPositionMismatches": position_mismatches,
        "councilRows": len(council),
        "councilDayRowsNotMembers": len(council_day_mismatches),
        "councilSizeMismatches": len(council_size_mismatches),
        "replacedMembers": replaced_members,
        "substitutes": substitutes,
        "substitutesNotInSitemap": len(substitutes_not_in_sitemap),
        "mandateSummaryTotal": summary["total"],
        "seats": {"tarybos-narys": len(elected)},
    }
    details = {
        "perMunicipality": per_municipality,
        "councilNotInSitemap": not_in_sitemap,
        "municipalityMismatches": municipality_mismatches,
        "listMismatches": list_mismatches,
        "seatCountMismatches": seat_count_mismatches,
        "councilDayRowsNotMembers": council_day_mismatches,
        "councilSizeMismatches": council_size_mismatches,
        "substitutesNotInSitemap": substitutes_not_in_sitemap,
        "mandateSummary": summary,
        "listResults": list_results,
        "ranking": ranking,
        "council": council,
    }
    write_results(output_path, ELECTION_ID, elected, stats, sources, details)
    return output_path, stats


__all__ = [
    "build_results",
    "parse_council_page",
    "parse_mandate_summary",
    "parse_members_page",
    "parse_municipality_results_page",
    "parse_preference_page",
]
