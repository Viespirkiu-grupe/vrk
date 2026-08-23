"""Elected status for the 2005 Kėdainiai by-election, from its 2005/seimas tree.

The members page (``rez_isrinkti_l_21_1.htm``, "Išrinkti LR Seimo nariai
2004 - 2008") rows the one winner with the anketa link and the constituency
linking ``rezv_apg_l_<district>_<round>.htm`` — the 2004 Seimas members
page for one seat — so the 2004 module's row reader applies. The round's
own winners page (``rezv_isrinkti_l_21_<round>_1.htm``; the first-round
one is a 404, the seat went to the runoff) is the cross-check. No lists,
so no ranking pages.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_2004.results import _anketa_ids, parse_members_page
from scraper.elections.seimo_kedainiu_2005.sitemap import ELECTION_ID
from scraper.shared.election_results import fetch_page, load_sitemap_entries, write_results

RESULTS_ROOT = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2005/seimas/rezultatai/"
MEMBERS_PAGE = "rez_isrinkti_l_21_1.htm"
ROUND_WINNERS_PAGES = {2: "rezv_isrinkti_l_21_2_1.htm"}
SEATS = 1

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


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
    district_mismatches = 0
    for member in members:
        entry = by_id.get(member["vrkCandidateId"])
        if entry is None or member["seat"] != "vienmandate":
            not_in_sitemap.append(member)
            continue
        if (entry.get("vienmandateCandidacy") or {}).get("apygardosId") != member["districtId"]:
            district_mismatches += 1
        elected[member["vrkCandidateId"]] = {
            "seat": "vienmandate",
            "method": "members-list",
            "sourceUrl": members_url,
            "party": member["party"],
            "round": member["round"],
            "districtId": member["districtId"],
            "districtNumber": member["districtNumber"],
            "districtName": member["districtName"],
        }

    round_urls: list[str] = []
    round_page_diff = 0
    for round_number, page in ROUND_WINNERS_PAGES.items():
        url = RESULTS_ROOT + page
        round_urls.append(url)
        ids = _anketa_ids(fetch_page(results_dir, url))
        expected = {m["vrkCandidateId"] for m in members if m.get("round") == round_number}
        round_page_diff += len(ids ^ expected)

    stats = {
        "seats": SEATS,
        "membersListed": len(members),
        "membersInSitemap": len(elected),
        "membersNotInSitemap": len(not_in_sitemap),
        "districtMismatches": district_mismatches,
        "roundWinnersPageDiff": round_page_diff,
        "decidedInRound": sorted({m.get("round") for m in members}),
    }
    write_results(output_path, ELECTION_ID, elected, stats, [members_url, *round_urls], {"notInSitemap": not_in_sitemap})
    return output_path, stats


__all__ = ["MEMBERS_PAGE", "RESULTS_ROOT", "build_results"]
