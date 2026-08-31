"""Elected status for the 1997 archived municipal-council election pair.

The candidate pages this family parses (`scraper/shared/savivaldybiu_archive_1997.py`)
mark no winner anywhere, so electedness lives only in the results pages VRK
published beside them, two per municipality under the same `19970323`
directory:

- ``rapgpl.htm-<code>.htm`` — "Balsavimo rezultatai": the turnout block and a
  table of every list's ballot-box, postal and total votes and its mandate
  count ("-" where the list won none), with an "Iš viso" totals row. Linked
  from the municipality's own `apgtl` page, which is where ``<code>`` comes
  from — it is VRK's internal id (144–199 for the general election's
  municipalities 1–56, 264 for the Švenčionys repeat), not the municipality
  number.
- ``rikl.htm-<code>.htm`` — "Apygardoje išrinkti kandidatai": one ``<li>`` per
  seat won, linking the member's own candidate page. **The rows carry VRK's
  candidate id**, ``kandvl.htm-<ID>.htm``, the same id the sitemap's candidate
  URL carries, so the join is by id — same as the Seimas archive family
  (issue #79). Each row also names the nominating list (a ``pkal`` link) and
  the member's pre-election number on it, both checked against the sitemap.

One municipality is the reason ``isrinktas`` can be a known `false` here
rather than an unknown: **Švenčionių rajono (Nr. 47), whose March result VRK
invalidated** ("rinkimų rezultatai šioje apygardoje pripažinti
negaliojančiais", decision Nr. 149 of 1997-03-29) and re-ran on 1997-06-29 —
the repeat is its own election in this corpus. Both of the invalidated
municipality's pages print the decision instead of winners, so its March
candidates' `false` is a read verdict, and the record carries the decision
under `rezultatai-negalioja`. No page of this family is mojibake (that is
the 1997-03 *Seimas* capture's problem).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from scraper.shared.election_results import (
    fetch_page,
    normalize_space,
    write_results,
)
from scraper.shared.seimo_archive_1990s_results import (
    CANDIDATE_ID_PATTERN,
    INVALID_BALLOTS_PATTERN,
    REGISTERED_VOTERS_PATTERN,
    VALID_BALLOTS_PATTERN,
    VOTERS_PATTERN,
    candidate_id_from_url,
    load_archive_sitemap,
)

VRK_STATINIAI_BASE = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/19970323/"

SEAT_COUNCIL = "tarybos-narys"

RESULTS_PAGE_PATTERN = re.compile(r"rapgpl\.htm-(\d+)\.htm")
ELECTED_PAGE_PATTERN = re.compile(r"rikl\.htm-(\d+)\.htm")
PARTY_LIST_PATTERN = re.compile(r"pkal\.htm-(\d+)\+(\d+)\.htm")
MUNICIPALITY_HEADING_PATTERN = re.compile(r"^(.*?)\s*\(Nr\.\s*(\d+)\)\s*apygarda\s*$", re.IGNORECASE)
LIST_POSITION_PATTERN = re.compile(r"numeris\s+sąraše\s*-\s*(\d+)")
# VRK's decision voiding one municipality's result; the page prints it in
# place of the winners.
INVALIDATED_PATTERN = re.compile(r"pripažinti\s+negaliojančiais", re.IGNORECASE)

TOTALS_ROW_PREFIX = "Iš viso"


def _int(value: str) -> int | None:
    digits = re.sub(r"[^\d]", "", value or "")
    return int(digits) if digits else None


def _clean(value: str) -> str:
    return normalize_space(value.replace("\xa0", " "))


def _heading(soup: BeautifulSoup) -> tuple[str, int | None]:
    """The "<name> (Nr. <n>) apygarda" heading both page kinds print."""
    for font in soup.find_all("font"):
        text = _clean(font.get_text(" ", strip=True))
        match = MUNICIPALITY_HEADING_PATTERN.match(text)
        if match:
            return match.group(1), int(match.group(2))
    return "", None


def _invalidation_notice(soup: BeautifulSoup) -> str | None:
    for paragraph in soup.find_all("p"):
        text = _clean(paragraph.get_text(" ", strip=True))
        if INVALIDATED_PATTERN.search(text):
            return text
    return None


# ---------------------------------------------------------------------------
# Page parsing
# ---------------------------------------------------------------------------


def parse_list_votes_page(html: str, source_url: str) -> dict[str, Any]:
    """One ``rapgpl.htm-<code>.htm`` page: the municipality, the turnout
    block, every list's votes and mandates, the totals row, the link to the
    elected page — and, on the invalidated municipality, VRK's decision."""
    soup = BeautifulSoup(html, "lxml")
    text = _clean(soup.get_text(" ", strip=True))
    municipality_name, municipality_number = _heading(soup)

    lists: list[dict[str, Any]] = []
    total_votes: int | None = None
    total_mandates: int | None = None
    for table in soup.find_all("table"):
        if "Mandatų skaičius" not in table.get_text(" ", strip=True):
            continue
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) != 6:
                continue
            label = _clean(cells[1].get_text(" ", strip=True))
            numbers = [_int(cell.get_text(" ", strip=True)) for cell in cells[2:5]]
            if label.startswith(TOTALS_ROW_PREFIX):
                total_votes = numbers[2]
                total_mandates = _int(cells[5].get_text(" ", strip=True))
                continue
            if not label or any(number is None for number in numbers):
                continue
            anchor = cells[1].find("a", href=PARTY_LIST_PATTERN)
            party_match = PARTY_LIST_PATTERN.search(anchor["href"]) if anchor else None
            mandates_text = _clean(cells[5].get_text(" ", strip=True))
            lists.append(
                {
                    "listNumber": _int(cells[0].get_text(" ", strip=True)),
                    "name": label,
                    "partyId": party_match.group(2) if party_match else None,
                    "votesBallotBox": numbers[0],
                    "votesPostal": numbers[1],
                    "votes": numbers[2],
                    "mandates": int(mandates_text) if mandates_text.isdigit() else None,
                }
            )
        break

    elected_anchor = soup.find("a", href=ELECTED_PAGE_PATTERN)
    voters_match = VOTERS_PATTERN.search(text)
    return {
        "municipalityName": municipality_name,
        "municipalityNumber": municipality_number,
        "invalidationNotice": _invalidation_notice(soup),
        "turnout": {
            "registeredVoters": _int(REGISTERED_VOTERS_PATTERN.search(text).group(1))
            if REGISTERED_VOTERS_PATTERN.search(text)
            else None,
            "voters": _int(voters_match.group(1)) if voters_match else None,
            "turnoutPercent": float(voters_match.group(2).replace(",", "."))
            if voters_match
            else None,
            "invalidBallots": _int(INVALID_BALLOTS_PATTERN.search(text).group(1))
            if INVALID_BALLOTS_PATTERN.search(text)
            else None,
            "validBallots": _int(VALID_BALLOTS_PATTERN.search(text).group(1))
            if VALID_BALLOTS_PATTERN.search(text)
            else None,
        },
        "lists": lists,
        "totalVotes": total_votes,
        "totalMandates": total_mandates,
        "electedUrl": urljoin(source_url, elected_anchor["href"]) if elected_anchor else None,
        "sourceUrl": source_url,
    }


def parse_elected_page(html: str, source_url: str) -> dict[str, Any]:
    """One ``rikl.htm-<code>.htm`` page: every elected candidate with VRK's
    id, the nominating list and the pre-election list position — or VRK's
    invalidation decision where the March result was voided."""
    soup = BeautifulSoup(html, "lxml")
    municipality_name, municipality_number = _heading(soup)
    members: list[dict[str, Any]] = []
    for item in soup.find_all("li"):
        anchor = item.find("a", href=CANDIDATE_ID_PATTERN)
        if anchor is None:
            continue
        text = _clean(item.get_text(" ", strip=True))
        nominator_anchor = item.find("a", href=PARTY_LIST_PATTERN)
        position_match = LIST_POSITION_PATTERN.search(text)
        members.append(
            {
                "vrkCandidateId": candidate_id_from_url(anchor["href"]),
                "name": _clean(anchor.get_text(" ", strip=True)),
                "nominator": _clean(nominator_anchor.get_text(" ", strip=True))
                if nominator_anchor
                else None,
                "nominatorUrl": urljoin(source_url, nominator_anchor["href"])
                if nominator_anchor
                else None,
                "listPosition": int(position_match.group(1)) if position_match else None,
            }
        )
    return {
        "municipalityName": municipality_name,
        "municipalityNumber": municipality_number,
        "invalidationNotice": _invalidation_notice(soup),
        "members": members,
        "sourceUrl": source_url,
    }


# ---------------------------------------------------------------------------
# Targets from the retained municipality pages
# ---------------------------------------------------------------------------


def municipal_results_targets(municipalities_dir: Path) -> list[dict[str, Any]]:
    """Each retained ``apgtl-<n>.html`` municipality page's own link to its
    results page. Read from the samples rather than derived, because the
    ``rapgpl`` suffix is VRK's internal id (144 for municipality 1), not the
    municipality number — the page is the only place the mapping is stated.
    """
    sample_paths = sorted(
        municipalities_dir.glob("apgtl-*.html"),
        key=lambda path: int(path.stem.split("-")[1]),
    )
    if not sample_paths:
        raise ValueError(
            f"No municipality samples under {municipalities_dir}. Run fetch-sample first."
        )
    targets: list[dict[str, Any]] = []
    for sample_path in sample_paths:
        soup = BeautifulSoup(sample_path.read_text(encoding="utf-8"), "lxml")
        municipality_name, municipality_number = _heading(soup)
        anchor = soup.find("a", href=RESULTS_PAGE_PATTERN)
        if anchor is None:
            raise ValueError(f"No rapgpl results link on {sample_path}")
        expected_number = int(sample_path.stem.split("-")[1])
        if municipality_number != expected_number:
            raise ValueError(
                f"{sample_path} heads municipality {municipality_number}, expected {expected_number}"
            )
        targets.append(
            {
                "municipalityName": municipality_name,
                "municipalityNumber": municipality_number,
                "resultsUrl": urljoin(VRK_STATINIAI_BASE, anchor["href"]),
            }
        )
    return targets


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_municipal_results(
    election_id: str,
    targets: list[dict[str, Any]],
    sitemap_path: Path,
    results_dir: Path,
    output_path: Path,
) -> tuple[Path, dict[str, Any]]:
    """Fetch and reconcile every municipality's results pair, and write the
    election's results file.

    The elected page is the source; the votes page and the sitemap are the
    cross-checks: each municipality's member count must equal its own mandate
    column and totals row, and each member must be in the sitemap, in the
    municipality, on the list and at the position the sitemap says.
    """
    entries = load_archive_sitemap(sitemap_path)
    by_vrk_id = {entry["vrkCandidateId"]: entry for entry in entries if entry["vrkCandidateId"]}

    elected: dict[str, dict[str, Any]] = {}
    per_municipality: list[dict[str, Any]] = []
    list_results: dict[str, list[dict[str, Any]]] = {}
    invalidated: list[dict[str, Any]] = []
    not_in_sitemap: list[dict[str, Any]] = []
    member_mismatches: list[dict[str, Any]] = []
    seat_count_mismatches: list[dict[str, Any]] = []
    sources: list[str] = []

    for target in targets:
        results_url = target["resultsUrl"]
        votes_page = parse_list_votes_page(fetch_page(results_dir, results_url), results_url)
        sources.append(results_url)
        if votes_page["municipalityNumber"] != target["municipalityNumber"]:
            raise ValueError(
                f"{results_url} heads municipality {votes_page['municipalityNumber']}, "
                f"expected {target['municipalityNumber']}"
            )
        list_results[str(target["municipalityNumber"])] = [
            {**row, "sourceUrl": results_url} for row in votes_page["lists"]
        ]

        # The voided municipality's votes page prints the decision and no
        # mandate column, and links no elected page at all; the mandates were
        # never handed out, so there are no members to read and `false` for
        # its candidates is VRK's own verdict rather than a silence.
        if votes_page["invalidationNotice"]:
            invalidated.append(
                {
                    "municipalityName": votes_page["municipalityName"],
                    "municipalityNumber": votes_page["municipalityNumber"],
                    "notice": votes_page["invalidationNotice"],
                    "sourceUrl": results_url,
                }
            )
            per_municipality.append(
                {
                    "municipalityName": votes_page["municipalityName"],
                    "municipalityNumber": votes_page["municipalityNumber"],
                    "invalidated": True,
                    "members": 0,
                    "mandatesSum": None,
                    "totalMandates": votes_page["totalMandates"],
                    "turnout": votes_page["turnout"],
                    "resultsUrl": results_url,
                    "electedUrl": None,
                }
            )
            continue

        # The elected page, from the votes page's own link (every non-voided
        # page carries one; the rikl/rapgpl codes also match, but the link is
        # what VRK states).
        elected_url = votes_page["electedUrl"]
        if elected_url is None:
            raise ValueError(f"No elected-page link on {results_url}")
        elected_page = parse_elected_page(fetch_page(results_dir, elected_url), elected_url)
        sources.append(elected_url)
        if elected_page["municipalityNumber"] != target["municipalityNumber"]:
            raise ValueError(
                f"{elected_url} heads municipality {elected_page['municipalityNumber']}, "
                f"expected {target['municipalityNumber']}"
            )

        mandates_sum = sum(row["mandates"] or 0 for row in votes_page["lists"])
        members = elected_page["members"]
        if not (len(members) == mandates_sum == votes_page["totalMandates"]):
            seat_count_mismatches.append(
                {
                    "municipalityNumber": target["municipalityNumber"],
                    "members": len(members),
                    "mandatesSum": mandates_sum,
                    "totalsRow": votes_page["totalMandates"],
                }
            )

        for member in members:
            vrk_id = member["vrkCandidateId"]
            entry = by_vrk_id.get(vrk_id)
            if entry is None:
                not_in_sitemap.append(
                    {**member, "municipalityNumber": target["municipalityNumber"]}
                )
            else:
                # The sitemap's own facts about the member, row by row.
                diffs = {
                    key: {"page": page_value, "sitemap": entry.get(sitemap_key)}
                    for key, page_value, sitemap_key in (
                        ("municipality", target["municipalityNumber"], "municipalityNumber"),
                        ("nominator", member["nominator"], "nominator"),
                        ("listPosition", member["listPosition"], "listNumber"),
                    )
                    if page_value != entry.get(sitemap_key)
                }
                if diffs:
                    member_mismatches.append(
                        {
                            "vrkCandidateId": vrk_id,
                            "name": member["name"],
                            "municipalityNumber": target["municipalityNumber"],
                            "diffs": diffs,
                        }
                    )
            if vrk_id:
                elected[vrk_id] = {
                    "seat": SEAT_COUNCIL,
                    "method": "elected-page",
                    "sourceUrl": elected_url,
                    "municipality": votes_page["municipalityName"],
                    "municipalityNumber": votes_page["municipalityNumber"],
                    "nominator": member["nominator"],
                    "listPosition": member["listPosition"],
                }

        per_municipality.append(
            {
                "municipalityName": votes_page["municipalityName"],
                "municipalityNumber": votes_page["municipalityNumber"],
                "invalidated": False,
                "members": len(members),
                "mandatesSum": mandates_sum,
                "totalMandates": votes_page["totalMandates"],
                "turnout": votes_page["turnout"],
                "resultsUrl": results_url,
                "electedUrl": elected_url,
            }
        )

    in_sitemap = set(by_vrk_id)
    stats = {
        "municipalities": len(targets),
        "invalidatedMunicipalities": len(invalidated),
        "candidates": len(entries),
        "elected": len(elected),
        "electedNotInSitemap": len(not_in_sitemap),
        "memberMismatches": len(member_mismatches),
        "seatCountMismatches": len(seat_count_mismatches),
        "candidatesNotElected": len(in_sitemap - set(elected)),
        "seats": {SEAT_COUNCIL: len(elected)},
    }
    details = {
        "perMunicipality": per_municipality,
        "invalidated": invalidated,
        "electedNotInSitemap": not_in_sitemap,
        "memberMismatches": member_mismatches,
        "seatCountMismatches": seat_count_mismatches,
        "listResults": list_results,
    }
    write_results(output_path, election_id, elected, stats, sources, details)
    return output_path, stats


# ---------------------------------------------------------------------------
# The parse-stage join
# ---------------------------------------------------------------------------


def load_municipal_results(results_path: Path | None) -> dict[str, Any]:
    """The `elected` map and the invalidated municipalities of a results
    file, or an empty dict when the file is absent — the parse stage then
    leaves `isrinktas` out entirely rather than claiming a false."""
    if results_path is None or not results_path.exists():
        return {}
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    details = payload.get("details")
    details = details if isinstance(details, dict) else {}
    invalidated = details.get("invalidated")
    return {
        "elected": payload.get("elected") if isinstance(payload.get("elected"), dict) else {},
        "invalidated": {
            row["municipalityNumber"]: row
            for row in (invalidated if isinstance(invalidated, list) else [])
            if isinstance(row, dict)
        },
    }


def apply_municipal_results(
    candidacy: dict[str, Any],
    vrk_candidate_id: str | None,
    results: dict[str, Any],
) -> list[dict[str, Any]]:
    """Write `isrinktas` onto one record's `kandidatavimas` dict.

    Every candidate gets `true` or `false`, never a missing key: the elected
    pages name every seat and the one municipality without them is voided by
    VRK's own decision, which the record then carries under
    `rezultatai-negalioja`. The winner's own row is cross-checked against the
    card — a page naming a winner in another municipality or at another list
    position would mean the join keyed on the wrong id.
    """
    problems: list[dict[str, Any]] = []
    if not results:
        return problems

    winner = results["elected"].get(vrk_candidate_id or "")
    candidacy["isrinktas"] = winner is not None
    if winner is not None:
        candidacy["isrinktas-kaip"] = winner["seat"]
        candidacy["rezultatu-saltinis"] = winner["sourceUrl"]
        diffs = {
            key: {"card": candidacy.get(card_key), "results": winner.get(key)}
            for key, card_key in (
                ("municipalityNumber", "savivaldybes-numeris"),
                ("listPosition", "numeris-sarase"),
            )
            if winner.get(key) != candidacy.get(card_key)
        }
        if diffs:
            problems.append({"eventType": "ElectedCandidacyMismatch", "detail": diffs})

    voided = results["invalidated"].get(candidacy.get("savivaldybes-numeris"))
    if voided:
        candidacy["rezultatai-negalioja"] = {
            "pastaba": voided["notice"],
            "saltinis": voided["sourceUrl"],
        }
    return problems


__all__ = [
    "SEAT_COUNCIL",
    "VRK_STATINIAI_BASE",
    "apply_municipal_results",
    "build_municipal_results",
    "load_municipal_results",
    "municipal_results_targets",
    "parse_elected_page",
    "parse_list_votes_page",
]
