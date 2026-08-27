"""Results of the 2003-06-15 new Seimas election — and nobody was elected.

All four constituencies failed on turnout. VRK's own index says so in one
line ("**Pastaba.** * - rinkimai apygardoje neįvyko.", the asterisk on
every constituency), each constituency page repeats it in bold
("Rinkimai apygardoje neįvyko."), there is no members page
(``rez_isrinkti_l_17_1.htm`` is a 404) and no second round (every
``rez_v_apg_l_<APG>_2.htm`` is a 404 too). Senamiesčio came in lowest at
**9.26%** — 3,476 of 37,523.

So `elected` is empty *by measurement*, not by omission, and the parse
stage's join turns that into a known ``isrinktas: false`` for all 27
records rather than a null. The pages are still worth reading: each rows
its candidates by the anketa id the listing uses
(``kand_anketa_l-id=<ID>``, in a link whose path is missing its
``rinkimai/`` segment and so 404s — the id is what is read), which is
what the 2004 Seimas election's constituency pages do *not* do, so this
election's per-candidate votes join and land on ``kandidatavimas.turai``.

    rezultatai/rez_v_apg_sar_l_17_1_1.htm   the index (its ``_1_2`` twin
        is the same page under another sort key)
    rezultatai/rez_v_apg_l_<APG>_1.htm      one constituency's votes
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.elections.seimo_nauji_2003.sitemap import (
    CANDIDATE_ANKETA_PATTERN,
    DISTRICT_HEADING_PATTERN,
    ELECTION_ID,
)
from scraper.shared.election_results import (
    fetch_page,
    load_sitemap_entries,
    normalize_space,
    write_results,
)

RESULTS_ROOT = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2003/seimas/rezultatai/"
INDEX_PAGE = "rez_v_apg_sar_l_17_1_1.htm"
DISTRICT_PAGES = {
    "1476": "rez_v_apg_l_1476_1.htm",
    "1477": "rez_v_apg_l_1477_1.htm",
    "1478": "rez_v_apg_l_1478_1.htm",
    "1479": "rez_v_apg_l_1479_1.htm",
}
ROUND = 1
SEATS = 4

NOT_HELD_MARKER = "rinkimai apygardoje neįvyko"
INDEX_NOTE_MARKER = "* - rinkimai apygardoje neįvyko"

REGISTERED_PATTERN = re.compile(r"rinkimų teisę turinčių piliečių\s*-\s*(\d+)")
TURNOUT_PATTERN = re.compile(r"rinkimuose dalyvavo\s*-\s*(\d+)\s*\(\s*([\d.,]+)%")
INVALID_PATTERN = re.compile(r"negaliojančių biuletenių\s*-\s*(\d+)")
# The summary prints the invalid count first; without the word boundary this
# matches inside "negaliojančių" and both figures come out the same.
VALID_PATTERN = re.compile(r"\bgaliojančių biuletenių\s*-\s*(\d+)")

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")

__all__ = [
    "DISTRICT_PAGES",
    "INDEX_PAGE",
    "RESULTS_ROOT",
    "build_results",
    "load_rounds",
    "parse_district_page",
    "parse_index_page",
]


def _int(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


def _percent(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _votes_table(soup: BeautifulSoup) -> Tag | None:
    for table in soup.find_all("table", class_="smn"):
        if any(CANDIDATE_ANKETA_PATTERN.search(a["href"]) for a in table.find_all("a", href=True)):
            return table
    return None


def parse_index_page(html: str, source_url: str) -> dict[str, Any]:
    """The index: which constituencies it links, and whether it carries the
    footnote that says the vote failed in the ones it stars."""
    soup = BeautifulSoup(html, "lxml")
    text = normalize_space(soup.get_text(" ", strip=True))
    districts: list[str] = []
    for anchor in soup.find_all("a", href=True):
        match = re.search(r"rez_v_apg_l_(\d+)_(\d)\.htm$", anchor["href"])
        if match is not None and match.group(1) not in districts:
            districts.append(match.group(1))
    return {
        "sourceUrl": source_url,
        "districtIds": districts,
        "notHeldNote": INDEX_NOTE_MARKER in text.lower(),
    }


def parse_district_page(html: str, source_url: str) -> dict[str, Any]:
    """One constituency: its heading, the turnout summary, its verdict and
    every candidate's votes, in the page's own (descending) order."""
    soup = BeautifulSoup(html, "lxml")
    text = normalize_space(soup.get_text(" ", strip=True))
    heading = soup.find("h1")
    heading_text = normalize_space(heading.get_text(" ", strip=True)) if heading is not None else ""
    match = DISTRICT_HEADING_PATTERN.match(heading_text)
    turnout = TURNOUT_PATTERN.search(text)

    candidates: list[dict[str, Any]] = []
    table = _votes_table(soup)
    for tr in table.find_all("tr") if table is not None else []:
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue
        anchor = cells[0].find("a", href=True)
        id_match = CANDIDATE_ANKETA_PATTERN.search(anchor["href"]) if anchor is not None else None
        if id_match is None:
            continue
        candidates.append(
            {
                "vrkCandidateId": id_match.group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "vieta": len(candidates) + 1,
                "balsai-apylinkese": _int(normalize_space(cells[1].get_text())),
                "balsai-pastu": _int(normalize_space(cells[2].get_text())),
                "balsai": _int(normalize_space(cells[3].get_text())),
                "procentai-nuo-galiojanciu": _percent(
                    normalize_space(cells[4].get_text()).rstrip("%") if len(cells) > 4 else None
                ),
            }
        )

    valid = VALID_PATTERN.search(text)
    return {
        "sourceUrl": source_url,
        "round": ROUND,
        "constituencyName": normalize_space(match.group(1)) if match else heading_text,
        "constituencyNumber": int(match.group(2)) if match else None,
        "held": NOT_HELD_MARKER not in text.lower(),
        "summary": {
            "rinkeju-skaicius": _int(REGISTERED_PATTERN.search(text).group(1))
            if REGISTERED_PATTERN.search(text)
            else None,
            "dalyvavo": _int(turnout.group(1)) if turnout else None,
            "aktyvumas-procentais": _percent(turnout.group(2)) if turnout else None,
            "negaliojantys-biuleteniai": _int(INVALID_PATTERN.search(text).group(1))
            if INVALID_PATTERN.search(text)
            else None,
            "galiojantys-biuleteniai": _int(valid.group(1)) if valid else None,
        },
        "candidates": candidates,
    }


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    entries = load_sitemap_entries(sitemap_path)
    in_sitemap = {entry["vrkCandidateId"] for entry in entries if entry.get("vrkCandidateId")}

    index_url = RESULTS_ROOT + INDEX_PAGE
    index = parse_index_page(fetch_page(results_dir, index_url), index_url)

    pages: list[dict[str, Any]] = []
    for page in DISTRICT_PAGES.values():
        url = RESULTS_ROOT + page
        pages.append(parse_district_page(fetch_page(results_dir, url), url))

    votes: dict[str, list[dict[str, Any]]] = {}
    rows_not_in_sitemap: list[dict[str, Any]] = []
    for page in pages:
        for row in page["candidates"]:
            if row["vrkCandidateId"] not in in_sitemap:
                rows_not_in_sitemap.append({**row, "sourceUrl": page["sourceUrl"]})
                continue
            votes.setdefault(row["vrkCandidateId"], []).append(
                {
                    "turas": page["round"],
                    "apygardos-numeris": page["constituencyNumber"],
                    "balsai-apylinkese": row["balsai-apylinkese"],
                    "balsai-pastu": row["balsai-pastu"],
                    "balsai": row["balsai"],
                    "procentai-nuo-galiojanciu": row["procentai-nuo-galiojanciu"],
                    "vieta": row["vieta"],
                    "saltinis": page["sourceUrl"],
                }
            )

    # Every page's own votes must add up to the valid ballots it declares —
    # the check that the rows were read whole.
    vote_total_mismatches = sum(
        1
        for page in pages
        if sum(row["balsai"] or 0 for row in page["candidates"])
        != (page["summary"]["galiojantys-biuleteniai"] or -1)
    )

    stats = {
        "seats": SEATS,
        "constituencies": len(pages),
        "constituenciesNotHeld": sum(1 for page in pages if page["held"] is False),
        "indexNotHeldNote": index["notHeldNote"],
        "candidates": len(entries),
        "candidatesWithVotes": len(votes),
        "candidatesWithoutVotes": len(in_sitemap - set(votes)),
        "rowsNotInSitemap": len(rows_not_in_sitemap),
        "voteTotalMismatches": vote_total_mismatches,
        "elected": 0,
    }
    details = {
        "constituencies": [
            {key: value for key, value in page.items() if key != "candidates"} for page in pages
        ],
        "constituencyVotes": votes,
        "rowsNotInSitemap": rows_not_in_sitemap,
        "candidatesWithoutVotes": sorted(in_sitemap - set(votes)),
    }
    write_results(
        output_path,
        ELECTION_ID,
        {},
        stats,
        [index["sourceUrl"], *(page["sourceUrl"] for page in pages)],
        details,
    )
    return output_path, stats


def load_rounds(results_path: Path | None) -> dict[str, list[dict[str, Any]]] | None:
    """Each candidate's vote rows, keyed by VRK candidate id, or None when
    the results file is absent."""
    if results_path is None or not results_path.exists():
        return None
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    details = payload.get("details") if isinstance(payload, dict) else None
    votes = details.get("constituencyVotes") if isinstance(details, dict) else None
    return votes if isinstance(votes, dict) else None
