"""Elected status for the 2004 EP election, from VRK's 2004/euro results tree.

The candidate pages mark no winner, so electedness is a join, as for the
2007–2015 family — but the tree is the original 2004 static site
(``rinkimai/2004/euro/rezultatai/``), not a ``<year>_ep_rinkimai`` tree,
and its pages link candidates as ``kand_anketa_l_<ID>.htm``, so the shared
EP builder's id pattern does not apply and the walk is this module's own.
Three page kinds:

- ``rez_isrinkti_l_18_1.htm`` — "Kandidatai gavę mandatus": the 13 elected
  members with anketa links, list number and list. Below the table a
  footnote names the one post-election substitution: a member whose
  mandate VRK declared terminated at her own request (decision Nr. 180 of
  2004-06-21) and the list's next member recognised as elected in her
  place (decision Nr. 181), both linked to the decisions on lrs.lt. Both
  people are recorded as elected — VRK's own page lists both, and calls the
  replacement "išrinktu" — with the substitution on each record, so 14
  records carry the flag for 13 seats.
- ``rez_l_18.htm`` — the national results: each list's votes and mandate
  count (5 + 2 + 2 + 2 + 1 + 1 = 13). The cross-check for the members page.
- ``rez_pirm_l_<list>.htm`` — one per list, the post-preference ranking:
  rank, name (bold for a mandate), pre-election position and preference
  votes for every candidate. The second cross-check (bold rows = members
  page), and the source of every candidate's post-election rank and
  preference votes, joined into the record alongside the elected flag.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.ep_2004.sitemap import ELECTION_ID
from scraper.shared.election_results import (
    fetch_page,
    load_sitemap_entries,
    normalize_space,
    resolve_url,
    utc_now_iso,
    write_results,
)

RESULTS_ROOT = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/euro/rezultatai/"
MEMBERS_PAGE = "rez_isrinkti_l_18_1.htm"
RESULTS_PAGE = "rez_l_18.htm"
PREFERENCE_PAGE_PATTERN = re.compile(r"rez_pirm_l_(\d+)\.htm$")
ANKETA_PATTERN = re.compile(r"kand_anketa_l_(\d+)\.htm$")
DECISION_PATTERN = re.compile(r"VRK\s+\d{4}\s+m\.\s+\S+\s+\d+\s+d\.\s+sprendim\w*\s+Nr\.\s*\d+", re.IGNORECASE)
SEATS = 13

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def _own_rows(table: Tag) -> list[Tag]:
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def _own_cells(tr: Tag) -> list[Tag]:
    return [td for td in tr.find_all("td") if td.find_parent("tr") is tr]


def _anketa_anchor(container: Tag) -> Tag | None:
    for anchor in container.find_all("a", href=True):
        if ANKETA_PATTERN.search(anchor["href"]):
            return anchor
    return None


def parse_members_page(html: str, base_url: str) -> dict[str, Any]:
    """The winners table and the substitution footnote."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="basic")
    members: list[dict[str, Any]] = []
    if table is not None:
        for tr in _own_rows(table):
            cells = _own_cells(tr)
            if not cells:
                continue
            anchor = _anketa_anchor(cells[0])
            if anchor is None:
                continue
            list_number = normalize_space(cells[1].get_text(" ", strip=True)) if len(cells) > 1 else ""
            members.append(
                {
                    "vrkCandidateId": ANKETA_PATTERN.search(anchor["href"]).group(1),
                    "name": normalize_space(anchor.get_text(" ", strip=True)),
                    "listNumber": int(list_number) if list_number.isdigit() else None,
                    "party": normalize_space(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else "",
                    "marked": "***" in normalize_space(cells[0].get_text(" ", strip=True)),
                    "anketaUrl": resolve_url(anchor["href"], base_url),
                }
            )

    # The footnote: everything after the table in its container — the
    # marked member's statement, the terminating decision, the seating
    # decision and the replacement's anketa link.
    note_text = ""
    decisions: list[dict[str, str]] = []
    replacements: list[dict[str, Any]] = []
    statement_urls: list[str] = []
    if table is not None:
        parts: list[str] = []
        for node in table.next_siblings:
            if isinstance(node, Tag):
                parts.append(node.get_text(" ", strip=True))
                for anchor in node.find_all("a", href=True) + ([node] if node.name == "a" else []):
                    href = anchor["href"]
                    label = normalize_space(anchor.get_text(" ", strip=True))
                    if DECISION_PATTERN.search(label):
                        decisions.append({"label": label, "url": resolve_url(href, base_url)})
                    elif ANKETA_PATTERN.search(href):
                        replacements.append(
                            {
                                "vrkCandidateId": ANKETA_PATTERN.search(href).group(1),
                                "name": label,
                                "anketaUrl": resolve_url(href, base_url),
                            }
                        )
                    elif label.lower().startswith("pareiškim"):
                        statement_urls.append(resolve_url(href, base_url))
            else:
                parts.append(str(node))
        note_text = re.sub(r"\s+([,.])", r"\1", normalize_space(" ".join(parts)))

    return {
        "members": members,
        "note": note_text,
        "decisions": decisions,
        "replacements": replacements,
        "statementUrls": statement_urls,
    }


def parse_results_page(html: str) -> list[dict[str, Any]]:
    """Per-list rows of the national results page: list number, name,
    votes and mandates."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        cells = _own_cells(tr)
        if len(cells) < 7:
            continue
        anchor = None
        for candidate in cells[1].find_all("a", href=True):
            if "rez_part_l_" in candidate["href"]:
                anchor = candidate
                break
        if anchor is None:
            continue
        number = normalize_space(cells[0].get_text(" ", strip=True))
        mandates = normalize_space(cells[-1].get_text(" ", strip=True))
        total = normalize_space(cells[4].get_text(" ", strip=True))
        rows.append(
            {
                "listNumber": int(number) if number.isdigit() else None,
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "votes": int(total) if total.isdigit() else None,
                "mandates": int(mandates) if mandates.isdigit() else 0,
            }
        )
    return rows


def parse_preference_page(html: str) -> list[dict[str, Any]]:
    """Post-preference ranking rows: rank, anketa id, pre-election position,
    preference votes, whether the name is bold (a mandate).

    A list not subject to preference ranking — the 2004 Seimas LLRA list,
    "Lietuvos lenkų rinkimų akcijos prašymu jos sąrašas nebuvo
    reitinguojamas" — prints rank and name only; its rows carry the rank
    (the list order) with `ranked: False` and no votes.
    """
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        cells = _own_cells(tr)
        if len(cells) < 2:
            continue
        anchor = _anketa_anchor(cells[1])
        if anchor is None or anchor.find_parent("tr") is not tr:
            continue
        rank = normalize_space(cells[0].get_text(" ", strip=True))
        position = normalize_space(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else ""
        votes = normalize_space(cells[3].get_text(" ", strip=True)) if len(cells) > 3 else ""
        rows.append(
            {
                "vrkCandidateId": ANKETA_PATTERN.search(anchor["href"]).group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "rank": int(rank) if rank.isdigit() else None,
                "listPosition": int(position) if position.isdigit() else None,
                "preferenceVotes": int(votes) if votes.isdigit() else None,
                "mandate": anchor.find("b") is not None or anchor.find_parent("b") is not None,
                "ranked": len(cells) > 3,
            }
        )
    return rows


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    entries = load_sitemap_entries(sitemap_path)
    by_id = {entry["vrkCandidateId"]: entry for entry in entries if entry.get("vrkCandidateId")}

    members_url = RESULTS_ROOT + MEMBERS_PAGE
    page = parse_members_page(fetch_page(results_dir, members_url), members_url)
    results_url = RESULTS_ROOT + RESULTS_PAGE
    list_rows = parse_results_page(fetch_page(results_dir, results_url))

    elected: dict[str, dict[str, Any]] = {}
    not_in_sitemap: list[dict[str, Any]] = []
    for member in page["members"]:
        if member["vrkCandidateId"] not in by_id:
            not_in_sitemap.append(member)
            continue
        elected[member["vrkCandidateId"]] = {
            "seat": "daugiamandate",
            "method": "members-list",
            "sourceUrl": members_url,
            "party": member["party"],
            "listNumber": member["listNumber"],
        }

    # The substitution: the marked members and the replacements the footnote
    # names, paired in page order (one pair in 2004).
    marked = [member for member in page["members"] if member["marked"]]
    substitutions: list[dict[str, Any]] = []
    for index, member in enumerate(marked):
        replacement = page["replacements"][index] if index < len(page["replacements"]) else None
        terminating = page["decisions"][2 * index] if len(page["decisions"]) > 2 * index else None
        seating = page["decisions"][2 * index + 1] if len(page["decisions"]) > 2 * index + 1 else None
        record = {
            "terminated": member["vrkCandidateId"],
            "terminatedName": member["name"],
            "replacement": replacement["vrkCandidateId"] if replacement else None,
            "replacementName": replacement["name"] if replacement else None,
            "terminatingDecision": terminating,
            "seatingDecision": seating,
            "statementUrl": page["statementUrls"][index] if index < len(page["statementUrls"]) else None,
            "note": page["note"],
        }
        substitutions.append(record)
        if member["vrkCandidateId"] in elected:
            elected[member["vrkCandidateId"]]["mandateTerminated"] = {
                "decision": terminating,
                "statementUrl": record["statementUrl"],
                "replacedBy": record["replacement"],
                "note": page["note"],
            }
        if replacement and replacement["vrkCandidateId"] in by_id:
            elected[replacement["vrkCandidateId"]] = {
                "seat": "daugiamandate",
                "method": "vrk-decision-replacement",
                "sourceUrl": members_url,
                "party": member["party"],
                "listNumber": member["listNumber"],
                "replacementFor": member["vrkCandidateId"],
                "decision": seating,
            }
        elif replacement:
            not_in_sitemap.append(replacement)

    # Cross-check one: the national page's mandate counts per list against
    # the members table (before the substitution, which stays in-list).
    mandates_by_list = {row["listNumber"]: row["mandates"] for row in list_rows}
    members_by_list = Counter(member["listNumber"] for member in page["members"])
    list_mismatches = [
        {"listNumber": number, "declared": mandates_by_list.get(number, 0), "listed": members_by_list.get(number, 0)}
        for number in sorted(set(mandates_by_list) | set(members_by_list))
        if mandates_by_list.get(number, 0) != members_by_list.get(number, 0)
    ]

    # Cross-check two, and every candidate's rank and preference votes: the
    # per-list ranking pages, linked "pirm." from the national page.
    ranking: dict[str, dict[str, Any]] = {}
    bold_ids: set[str] = set()
    preference_urls: list[str] = []
    index_html = fetch_page(results_dir, results_url)
    soup = BeautifulSoup(index_html, "lxml")
    for anchor in soup.find_all("a", href=True):
        match = PREFERENCE_PAGE_PATTERN.search(anchor["href"])
        if match is None:
            continue
        url = resolve_url(anchor["href"], results_url)
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
    members_ids = {member["vrkCandidateId"] for member in page["members"]}
    ranked_not_in_sitemap = sorted(vrk_id for vrk_id in ranking if vrk_id not in by_id)
    sitemap_not_ranked = sorted(vrk_id for vrk_id in by_id if vrk_id not in ranking)
    # The ranking page repeats the pre-election position; it must be the
    # listing's.
    position_mismatches = [
        {"vrkCandidateId": vrk_id, "listing": (by_id[vrk_id].get("daugiamandateCandidacy") or {}).get("numerisSarase"), "ranking": row["listPosition"]}
        for vrk_id, row in ranking.items()
        if vrk_id in by_id and (by_id[vrk_id].get("daugiamandateCandidacy") or {}).get("numerisSarase") != row["listPosition"]
    ]

    stats = {
        "seats": SEATS,
        "membersListed": len(page["members"]),
        "membersInSitemap": sum(1 for member in page["members"] if member["vrkCandidateId"] in by_id),
        "membersNotInSitemap": len(not_in_sitemap),
        "substitutions": len(substitutions),
        "elected": len(elected),
        "mandatesDeclared": sum(mandates_by_list.values()),
        "listMandateMismatches": len(list_mismatches),
        "rankingPages": len(preference_urls),
        "candidatesRanked": len(ranking),
        "rankedNotInSitemap": len(ranked_not_in_sitemap),
        "sitemapNotRanked": len(sitemap_not_ranked),
        "boldNotMembers": len(bold_ids - members_ids),
        "membersNotBold": len(members_ids - bold_ids),
        "listPositionMismatches": len(position_mismatches),
    }
    details = {
        "notInSitemap": not_in_sitemap,
        "substitutions": substitutions,
        "mandatesByList": list_rows,
        "listMandateMismatches": list_mismatches,
        "ranking": ranking,
        "rankedNotInSitemap": ranked_not_in_sitemap,
        "sitemapNotRanked": sitemap_not_ranked,
        "listPositionMismatches": position_mismatches,
    }
    write_results(output_path, ELECTION_ID, elected, stats, [members_url, results_url, *preference_urls], details)
    return output_path, stats


def load_ranking(results_path: Path | None) -> dict[str, dict[str, Any]] | None:
    """The per-candidate rank and preference votes of a results file, or
    None when the file is absent."""
    if results_path is None or not results_path.exists():
        return None
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    details = payload.get("details") if isinstance(payload, dict) else None
    ranking = details.get("ranking") if isinstance(details, dict) else None
    return ranking if isinstance(ranking, dict) else None


__all__ = ["build_results", "load_ranking", "parse_members_page", "parse_preference_page", "parse_results_page", "utc_now_iso"]
