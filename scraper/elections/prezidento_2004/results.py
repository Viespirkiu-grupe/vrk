"""Votes and the winner of the 2004 presidential election, both rounds.

The listing marks no winner, so electedness is a results-tree join, as
everywhere in the pre-2016 corpus — but the tree is the 2004 static
site's own (``rinkimai/2004/prezidentas/rezultatai/``), so the walk is
this module's, not the 2015-era presidential builder's. Two pages:

- ``rez_l_19_1.htm`` — the first round (June 13): a summary block
  (stations reporting, electorate, turnout, invalid/valid ballots) and
  one row per candidate — votes at the stations, by post, in total, and
  the two percentages — with the runoff qualifiers' names in bold
  ("Kandidatai, patekę į II ratą, užrašyti paryškintu šriftu").
- ``rez_l_19_2.htm`` — the runoff (June 27), same shape for the two
  qualifiers, closed by the verdict: "Respublikos Prezidentu išrinktas -
  Valdas ADAMKUS", the name linked to the listing's own card anchor
  (``kandidatai_l_19.htm#250279``).

Every join is by id, never by name: a candidate row links
``rez_kand_l_<RID>_<round>_1.htm`` under VRK's registration record id,
which the listing's trustee link put on the sitemap entry
(``vrkRegistrationId``), and the verdict's anchor fragment is the
candidate id itself. The reconciliation demands the round-1 field equal
the sitemap, the bold names equal the runoff field, and each round's
votes sum to its summary's valid ballots.

The per-candidate votes are kept in the results file's details and
joined into each record's ``kandidatavimas.turai`` by the parse stage.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.prezidento_2004.sitemap import ELECTION_ID
from scraper.shared.election_results import (
    fetch_page,
    load_sitemap_entries,
    normalize_space,
    resolve_url,
    write_results,
)

RESULTS_ROOT = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/prezidentas/rezultatai/"
ROUND_PAGES = {1: "rez_l_19_1.htm", 2: "rez_l_19_2.htm"}

CANDIDATE_LINK_PATTERN = re.compile(r"rez_kand_l_(\d+)_(\d)_1\.htm$")
WINNER_ANCHOR_PATTERN = re.compile(r"kandidatai_l_19\.htm#(\d+)$")
WINNER_TEXT_MARKER = "Respublikos Prezidentu išrinktas"

SUMMARY_PATTERNS = {
    "apylinkes": re.compile(r"Apylinkių(?:, atsiuntusių duomenis,)?\s*skaičius\s*-\s*([\d\s]+?)[\s.(]"),
    "rinkeju-skaicius": re.compile(r"rinkimų teisę turinčių piliečių\s*-\s*([\d\s]+?)\s*,"),
    "dalyvavo": re.compile(r"rinkimuose dalyvavo\s*-\s*([\d\s]+?)\s*\("),
    "negaliojantys-biuleteniai": re.compile(r"negaliojančių biuletenių\s*-\s*([\d\s]+?)\s*\("),
    # The lookbehind keeps this off "negaliojančių biuletenių", which
    # contains the valid-ballot label as a substring.
    "galiojantys-biuleteniai": re.compile(r"(?<!ne)galiojančių biuletenių\s*-\s*([\d\s]+?)\s*\("),
}

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

__all__ = ["build_results", "load_rounds", "parse_round_page"]


def _parse_int(value: str) -> int | None:
    digits = re.sub(r"\D", "", value)
    return int(digits) if digits else None


def _parse_percent(value: str) -> float | None:
    match = re.search(r"([\d.,]+)\s*%", value)
    if match is None:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _summary(soup: BeautifulSoup) -> dict[str, int | None]:
    text = normalize_space(soup.get_text(" ", strip=True))
    return {key: _parse_int(pattern.search(text).group(1)) if pattern.search(text) else None for key, pattern in SUMMARY_PATTERNS.items()}


def _own_cells(tr: Tag) -> list[Tag]:
    return [td for td in tr.find_all("td") if td.find_parent("tr") is tr]


def parse_round_page(html: str, base_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    candidates: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        cells = _own_cells(tr)
        if len(cells) < 6:
            continue
        anchor = None
        for link in cells[0].find_all("a", href=True):
            if CANDIDATE_LINK_PATTERN.search(link["href"]):
                anchor = link
                break
        if anchor is None:
            continue
        match = CANDIDATE_LINK_PATTERN.search(anchor["href"])
        candidates.append(
            {
                "vrkRegistrationId": match.group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "bold": anchor.find("b") is not None or anchor.find_parent("b") is not None,
                "candidatePageUrl": resolve_url(anchor["href"], base_url),
                "balsai-apylinkese": _parse_int(cells[1].get_text()),
                "balsai-pastu": _parse_int(cells[2].get_text()),
                "balsai": _parse_int(cells[3].get_text()),
                "procentai-nuo-galiojanciu": _parse_percent(cells[4].get_text()),
                "procentai-nuo-dalyvavusiu": _parse_percent(cells[5].get_text()),
            }
        )

    winner_candidate_id = None
    winner_name = None
    for link in soup.find_all("a", href=True):
        match = WINNER_ANCHOR_PATTERN.search(link["href"])
        if match is not None:
            winner_candidate_id = match.group(1)
            winner_name = normalize_space(link.get_text(" ", strip=True))
            break
    if winner_candidate_id is None and WINNER_TEXT_MARKER in soup.get_text():
        # The verdict is present but its anchor shape changed — surface it
        # instead of silently reporting no winner.
        raise ValueError(f"Winner verdict present but unresolvable on {base_url}")

    return {"summary": _summary(soup), "candidates": candidates, "winnerVrkCandidateId": winner_candidate_id, "winnerName": winner_name}


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    entries = load_sitemap_entries(sitemap_path)
    by_registration_id = {entry.get("vrkRegistrationId"): entry for entry in entries if entry.get("vrkRegistrationId")}
    by_candidate_id = {entry.get("vrkCandidateId"): entry for entry in entries if entry.get("vrkCandidateId")}

    rounds: list[dict[str, Any]] = []
    urls: list[str] = []
    for round_number, page_name in sorted(ROUND_PAGES.items()):
        url = RESULTS_ROOT + page_name
        urls.append(url)
        page = parse_round_page(fetch_page(results_dir, url), url)
        rounds.append({"round": round_number, "sourceUrl": url, **page})

    first, second = rounds[0], rounds[1]
    not_in_sitemap = [
        row["name"] for page in rounds for row in page["candidates"]
        if row["vrkRegistrationId"] not in by_registration_id
    ]
    bold_first = {row["vrkRegistrationId"] for row in first["candidates"] if row["bold"]}
    runoff_ids = {row["vrkRegistrationId"] for row in second["candidates"]}
    vote_sum_mismatches = [
        {"round": page["round"], "votes": votes, "validBallots": page["summary"]["galiojantys-biuleteniai"]}
        for page in rounds
        if (votes := sum(row["balsai"] or 0 for row in page["candidates"])) != page["summary"]["galiojantys-biuleteniai"]
    ]

    elected: dict[str, dict[str, Any]] = {}
    winner_entry = by_candidate_id.get(second["winnerVrkCandidateId"])
    if winner_entry is not None:
        elected[winner_entry["vrkCandidateId"]] = {
            "seat": "prezidentas",
            "method": "verdict",
            "sourceUrl": second["sourceUrl"],
            "round": 2,
        }

    stats = {
        "rounds": len(rounds),
        "candidatesRound1": len(first["candidates"]),
        "candidatesRound2": len(second["candidates"]),
        "candidatesInSitemap": len(entries),
        "notInSitemap": len(not_in_sitemap),
        "boldRound1MatchesRound2": bold_first == runoff_ids,
        "voteSumMismatches": len(vote_sum_mismatches),
        "winnerName": second["winnerName"],
        "winnersResolved": len(elected),
        "unresolved": 0 if elected else 1,
    }
    details = {
        "rounds": rounds,
        "notInSitemap": not_in_sitemap,
        "voteSumMismatches": vote_sum_mismatches,
    }
    write_results(output_path, ELECTION_ID, elected, stats, urls, details)
    return output_path, stats


def load_rounds(results_path: Path | None) -> dict[str, list[dict[str, Any]]] | None:
    """Each candidate's per-round votes, keyed by ``vrkRegistrationId``,
    or None when the results file is absent."""
    if results_path is None or not results_path.exists():
        return None
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    details = payload.get("details") if isinstance(payload, dict) else None
    rounds = details.get("rounds") if isinstance(details, dict) else None
    if not isinstance(rounds, list):
        return None
    by_registration_id: dict[str, list[dict[str, Any]]] = {}
    for page in rounds:
        if not isinstance(page, dict):
            continue
        for row in page.get("candidates", []):
            by_registration_id.setdefault(row["vrkRegistrationId"], []).append(
                {
                    "turas": page.get("round"),
                    "balsai": row.get("balsai"),
                    "balsai-apylinkese": row.get("balsai-apylinkese"),
                    "balsai-pastu": row.get("balsai-pastu"),
                    "procentai-nuo-galiojanciu": row.get("procentai-nuo-galiojanciu"),
                    "procentai-nuo-dalyvavusiu": row.get("procentai-nuo-dalyvavusiu"),
                    "saltinis": page.get("sourceUrl"),
                }
            )
    return by_registration_id
