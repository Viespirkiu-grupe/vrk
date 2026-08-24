"""Votes and the winner of the 2002 presidential election, both rounds.

The listing marks no winner, so electedness is a results-tree join. The
tree is the 2002 site's own (Teleport-style mangled names):

- ``rezultatai/rezl.htm-14+1.htm`` — the first round (December 22): a
  summary paragraph (stations, electorate, turnout, invalid/valid
  ballots) and one row per candidate, sorted by votes — at the
  stations, by post, in total, and the two percentages. Unlike 2004,
  no bold marks the runoff qualifiers; the runoff page's own field is
  the authority on who advanced.
- ``rezultatai/rezl.htm-14+2.htm`` — the runoff (January 5, 2003),
  same shape for the two qualifiers, plus an "Iš viso" totals row. The
  page states the statute, not a verdict.
- ``rezultatai/protokolas/index.html`` — the verdict: "… 2003 metų
  sausio 5 dieną … išrinko Rolandą Paksą Respublikos Prezidentu". The
  name is in the accusative, so it is resolved against the two runoff
  candidates by word-stem prefix — unambiguous here, and a mismatch
  raises rather than guesses.

Candidate rows link ``rezkapgl.htm-<RID>+<round>.htm`` under VRK's
registration record id, which the sitemap carries from the trustee
index (``vrkRegistrationId``), so the votes join is by id. The
per-candidate votes are kept in the results file's details and joined
into each record's ``kandidatavimas.turai`` by the parse stage —
``prezidento_2004.results.load_rounds`` reads them, the shape is one
and the same.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.prezidento_2002.sitemap import ELECTION_ID, SITE_ROOT
from scraper.elections.prezidento_2004.results import load_rounds
from scraper.shared.election_results import (
    fetch_page,
    load_sitemap_entries,
    normalize_space,
    resolve_url,
    write_results,
)

ROUND_PAGES = {1: "rezultatai/rezl.htm-14+1.htm", 2: "rezultatai/rezl.htm-14+2.htm"}
PROTOCOL_PAGE = "rezultatai/protokolas/index.html"

CANDIDATE_LINK_PATTERN = re.compile(r"rezkapgl\.htm-(\d+)\+(\d)\.htm$")
VERDICT_PATTERN = re.compile(r"išrinko\s+(.{3,60}?)\s+Respublikos Prezidentu", re.DOTALL)

SUMMARY_PATTERNS = {
    "apylinkes": re.compile(r"Iš viso apylinkių\s*-\s*([\d\s]+?)\s*,"),
    "rinkeju-skaicius": re.compile(r"sąrašuose yra\s*([\d\s]+?)\s*rinkėjų"),
    "dalyvavo": re.compile(r"rinkimuose dalyvavo\s*([\d\s]+?)\s*\("),
    "negaliojantys-biuleteniai": re.compile(r"Negaliojančių biuletenių\s*-\s*([\d\s]+?)\s*\("),
    # The lookbehind keeps this off "negaliojančių biuletenių", which
    # contains the valid-ballot label as a substring.
    "galiojantys-biuleteniai": re.compile(r"(?<!Ne)(?<!ne)galiojančių biuletenių\s*-\s*([\d\s]+?)\s*\("),
}

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

__all__ = ["build_results", "load_rounds", "parse_protocol_winner", "parse_round_page", "resolve_verdict_name"]


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
    return {
        key: _parse_int(pattern.search(text).group(1)) if pattern.search(text) else None
        for key, pattern in SUMMARY_PATTERNS.items()
    }


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
                "candidatePageUrl": resolve_url(anchor["href"], base_url),
                "balsai-apylinkese": _parse_int(cells[1].get_text()),
                "balsai-pastu": _parse_int(cells[2].get_text()),
                "balsai": _parse_int(cells[3].get_text()),
                "procentai-nuo-galiojanciu": _parse_percent(cells[4].get_text()),
                "procentai-nuo-dalyvavusiu": _parse_percent(cells[5].get_text()),
            }
        )
    return {"summary": _summary(soup), "candidates": candidates}


def parse_protocol_winner(html: str) -> str | None:
    """The verdict's name as printed — the accusative "Rolandą Paksą"."""
    text = normalize_space(BeautifulSoup(html, "lxml").get_text(" ", strip=True))
    match = VERDICT_PATTERN.search(text)
    return normalize_space(match.group(1)) if match else None


def _stem(word: str) -> str:
    # "Rolandą" / "Rolandas" → "Roland": the accusative and nominative
    # share everything but the ending.
    return re.sub(r"(?:ias|ius|as|is|us|ys|ą|į|ų|ę|ė|a|e|i|o|u)$", "", word)


def resolve_verdict_name(verdict_name: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The runoff candidate whose name matches the accusative verdict
    name stem for stem — exactly one, or None."""
    verdict_stems = [_stem(word) for word in verdict_name.split()]
    hits = [
        candidate
        for candidate in candidates
        if all(
            any(candidate_word.startswith(stem) for candidate_word in candidate["name"].split())
            for stem in verdict_stems
            if stem
        )
    ]
    return hits[0] if len(hits) == 1 else None


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    entries = load_sitemap_entries(sitemap_path)
    by_registration_id = {entry.get("vrkRegistrationId"): entry for entry in entries if entry.get("vrkRegistrationId")}

    rounds: list[dict[str, Any]] = []
    urls: list[str] = []
    for round_number, page_name in sorted(ROUND_PAGES.items()):
        url = SITE_ROOT + page_name
        urls.append(url)
        page = parse_round_page(fetch_page(results_dir, url), url)
        rounds.append({"round": round_number, "sourceUrl": url, **page})

    protocol_url = SITE_ROOT + PROTOCOL_PAGE
    urls.append(protocol_url)
    verdict_name = parse_protocol_winner(fetch_page(results_dir, protocol_url))

    first, second = rounds[0], rounds[1]
    not_in_sitemap = [
        row["name"] for page in rounds for row in page["candidates"]
        if row["vrkRegistrationId"] not in by_registration_id
    ]
    runoff_ids = {row["vrkRegistrationId"] for row in second["candidates"]}
    top_two_ids = {
        row["vrkRegistrationId"]
        for row in sorted(first["candidates"], key=lambda row: row["balsai"] or 0, reverse=True)[:2]
    }
    vote_sum_mismatches = [
        {"round": page["round"], "votes": votes, "validBallots": page["summary"]["galiojantys-biuleteniai"]}
        for page in rounds
        if (votes := sum(row["balsai"] or 0 for row in page["candidates"])) != page["summary"]["galiojantys-biuleteniai"]
    ]

    winner_row = resolve_verdict_name(verdict_name, second["candidates"]) if verdict_name else None
    if verdict_name and winner_row is None:
        raise ValueError(f"Protocol verdict {verdict_name!r} resolves to no unique runoff candidate")
    vote_leader = max(second["candidates"], key=lambda row: row["balsai"] or 0, default=None)

    elected: dict[str, dict[str, Any]] = {}
    winner_entry = by_registration_id.get(winner_row["vrkRegistrationId"]) if winner_row else None
    if winner_entry is not None:
        elected[winner_entry["vrkCandidateId"]] = {
            "seat": "prezidentas",
            "method": "verdict",
            "sourceUrl": protocol_url,
            "round": 2,
        }

    stats = {
        "rounds": len(rounds),
        "candidatesRound1": len(first["candidates"]),
        "candidatesRound2": len(second["candidates"]),
        "candidatesInSitemap": len(entries),
        "notInSitemap": len(not_in_sitemap),
        "runoffIsRound1TopTwo": runoff_ids == top_two_ids,
        "voteSumMismatches": len(vote_sum_mismatches),
        "winnerName": winner_row["name"] if winner_row else verdict_name,
        "verdictMatchesVoteLeader": bool(
            winner_row and vote_leader and winner_row["vrkRegistrationId"] == vote_leader["vrkRegistrationId"]
        ),
        "winnersResolved": len(elected),
        "unresolved": 0 if elected else 1,
    }
    details = {
        "rounds": rounds,
        "verdictName": verdict_name,
        "notInSitemap": not_in_sitemap,
        "voteSumMismatches": vote_sum_mismatches,
    }
    write_results(output_path, ELECTION_ID, elected, stats, urls, details)
    return output_path, stats
