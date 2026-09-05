"""Elected status and votes for the 1996-1999 Seimas archive family.

The candidate pages this family parses (`scraper/shared/seimo_archive_1990s.py`)
mark no winner anywhere, so electedness for its six elections lives only in the
`rapgpl` results pages VRK published beside them. They are the same page in
every directory -- `seim96`, `seimpk` and `19990321` -- and simple:

    Naujamiesčio (Nr. 1) apygarda
    1-OJO BALSAVIMO TURO REZULTATAI
    Rinkimai apygardoje įvyko.
    Reikalingas antras rinkimų turas. ...
    Rinkimų apygardos rinkėjų skaičius: 42788
    Rinkimuose dalyvavusių apygardos rinkėjų skaičius: 23258 ( 54.36% ...)
    Kandidatas | Gautų balsų skaičius: Apygardoje | Pašte | Iš viso
    Andrius Kubilius   5868  2035  7903
    ...

A page states one of four verdicts, and every one of them is a *known*
answer -- which is the whole point of reading them: a `neįvyko` election
elected nobody, so `isrinktas` is `false` rather than null.

- "Rinkimai apygardoje neįvyko" -- the turnout threshold failed; nobody
  elected, and the constituency goes to a repeat election.
- "Reikalingas antras rinkimų turas" / "Reikalingas pakartotinis balsavimas"
  -- a runoff decides it, on the round-two page.
- "Seimo nariu išrinktas X" (round two, and the two 1996 constituencies
  decided outright in round one).
- "Į Seimo narius išrinktas X" -- the same verdict in the 1997-03 pages'
  wording.

**The rows carry VRK's candidate id**, `kandvl.htm-<ID>.htm`, the same id the
sitemap's candidate URL carries, so the join is by id rather than by name --
contrary to what issue #79 assumed from the rendered text. The one exception
is the 1998-03-22 pair (`seimpk/rapgpl.htm`, `rapgpl2.htm`), a hand-built
capture whose rows link `kandvl.htm`, `kandvl2.htm`, … with no id at all;
those 11 rows are resolved by name within the constituency, comparing the name
as an unordered token set because the results pages print it given-name-first
and the listing surname-first.

**The 1997-03-23 pages (`seimpk/rapgp20<n>.htm`) are mojibake.** VRK's static
conversion re-encoded that one capture's Windows-1257 bytes as Latin-1 HTML
entities, so "Mečislav Vaškovič" arrives as "Me&egrave;islav Va&eth;kovi&egrave;".
`repair_baltic_text` reverses it, and is applied only when the round trip
actually recovers Lithuanian letters, so a correctly-encoded page is never
touched.

The 1996 general election has a second, better source that the by-elections do
not: `seim96/rsnl.htm-1.htm`, "Kandidatai, išrinkti Seimo nariais", which rows
all 137 members with their anketa link, their nominator and their seat ("pagal
sąrašą", "I ture", "II ture"). `scraper/elections/seimo_1996/results.py` uses
it as the source and this module's page parsers as the cross-checks.
"""

from __future__ import annotations

from collections import Counter
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

VRK_STATINIAI_BASE = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/"

# The candidate-page id, on the results rows and on the sitemap's URLs.
CANDIDATE_ID_PATTERN = re.compile(r"kandvl\.htm-(\d+)\.htm")

CONSTITUENCY_HEADING_PATTERN = re.compile(r"^(.*?)\s*\(Nr\.\s*(\d+)\)\s*apygarda\s*$", re.IGNORECASE)
ROUND_PATTERN = re.compile(r"(\d)\s*-\s*OJO\s+BALSAVIMO\s+TURO\s+REZULTATAI", re.IGNORECASE)
HELD_PATTERN = re.compile(r"Rinkimai\s+apygardoje\s+(ne)?įvyko", re.IGNORECASE)
RUNOFF_PATTERN = re.compile(
    r"Reikalingas\s+(?:antras\s+rinkimų\s+turas|pakartotinis\s+balsavimas)", re.IGNORECASE
)
# "Seimo nariu išrinktas X." (1996, 1997-12, the 1997-04 runoff) and
# "Į Seimo narius išrinktas X." (the 1997-03 first-round pages). The verb is
# printed in the masculine whoever won -- "Seimo nariu išrinktas Danutė
# Aleksiūnienė" -- so the pattern does not try to agree with it.
WINNER_PATTERN = re.compile(
    r"(?:Į\s+Seimo\s+narius|Seimo\s+nariu)\s+išrinkt\w*\s+(.+?)\s*\.", re.IGNORECASE
)
REGISTERED_VOTERS_PATTERN = re.compile(r"Rinkimų apygardos rinkėjų skaičius:\s*(\d+)")
VOTERS_PATTERN = re.compile(
    r"Rinkimuose dalyvavusių apygardos rinkėjų skaičius:\s*(\d+)\s*\(\s*([\d.,]+)\s*%"
)
INVALID_BALLOTS_PATTERN = re.compile(r"Apygardoje negaliojančių biuletenių skaičius:\s*(\d+)")
VALID_BALLOTS_PATTERN = re.compile(r"Apygardoje galiojančių biuletenių skaičius:\s*(\d+)")

TOTALS_ROW_PREFIX = "Iš viso"

# ---------------------------------------------------------------------------
# The 1997-03-23 capture's mojibake
# ---------------------------------------------------------------------------

# Lithuanian's own letters. Recovering them is what tells `repair_baltic_text`
# that a round trip through cp1257 found real text rather than mangling it.
LITHUANIAN_LETTERS = frozenset("ąčęėįšųūžĄČĘĖĮŠŲŪŽ")


def _lithuanian_letter_count(value: str) -> int:
    return sum(1 for char in value if char in LITHUANIAN_LETTERS)


def repair_baltic_text(value: str) -> str:
    """Undo the Latin-1-for-Windows-1257 mangling of the 1997-03 pages.

    Those four pages went through VRK's static conversion as cp1257 bytes
    rendered into Latin-1 HTML entities, so the byte 0xE8 ("č") arrives as
    `&egrave;` and parses to U+00E8. Encoding back to Latin-1 and decoding as
    cp1257 restores the original text.

    The repair is applied only when it *increases* the number of Lithuanian
    letters, so it is a no-op on the family's other pages: their text carries
    real "ė"/"š"/"ų", which have no Latin-1 encoding at all, and the round trip
    raises rather than damaging them.
    """
    try:
        repaired = value.encode("latin-1").decode("cp1257")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    if _lithuanian_letter_count(repaired) > _lithuanian_letter_count(value):
        return repaired
    return value


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------


def name_key(value: str) -> tuple[str, ...]:
    """A name as an unordered, case-folded token set.

    The results pages print "Artūras Paulauskas" and the listing "Paulauskas
    Artūras" -- the same person in the two orders VRK uses -- so a name join
    has to ignore the order. Used only inside one constituency's own field, and
    the caller checks that exactly one entry matches.
    """
    cleaned = normalize_space(value.replace("\xa0", " ").replace("-", " "))
    return tuple(sorted(part.casefold() for part in cleaned.split() if part))


def resolve_by_name(name: str, entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    key = name_key(name)
    hits = [entry for entry in entries if name_key(entry.get("candidateName", "")) == key]
    return hits[0] if len(hits) == 1 else None


def candidate_id_from_url(url: str) -> str | None:
    match = CANDIDATE_ID_PATTERN.search(url or "")
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Page parsing
# ---------------------------------------------------------------------------


def _int(value: str) -> int | None:
    digits = re.sub(r"[^\d]", "", value or "")
    return int(digits) if digits else None


def _percent(value: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)", value or "")
    return float(match.group(1).replace(",", ".")) if match else None


def _candidate_table(soup: BeautifulSoup) -> Tag | None:
    for table in soup.find_all("table"):
        if "Kandidatas" in table.get_text(" ", strip=True):
            return table
    return None


def parse_constituency_results(html: str, source_url: str) -> dict[str, Any]:
    """One `rapgpl`/`rapgp20<n>` constituency results page.

    Returns the constituency, the round, the verdict, the turnout block and
    every candidate row in the page's own order (which is descending by total
    votes, so the row index is the placing).
    """
    soup = BeautifulSoup(html, "lxml")
    raw_text = normalize_space(soup.get_text(" ", strip=True).replace("\xa0", " "))
    text = repair_baltic_text(raw_text)
    mojibake = text != raw_text

    def clean(value: str) -> str:
        cleaned = normalize_space(value.replace("\xa0", " "))
        return repair_baltic_text(cleaned) if mojibake else cleaned

    heading = ""
    for font in soup.find_all("font", attrs={"size": "5"}):
        candidate_heading = clean(font.get_text(" ", strip=True))
        if "apygarda" in candidate_heading.lower():
            heading = candidate_heading
            break
    heading_match = CONSTITUENCY_HEADING_PATTERN.match(heading)
    constituency_name = heading_match.group(1) if heading_match else heading
    constituency_number = int(heading_match.group(2)) if heading_match else None

    round_match = ROUND_PATTERN.search(text)
    held_match = HELD_PATTERN.search(text)
    winner_match = WINNER_PATTERN.search(text)

    candidates: list[dict[str, Any]] = []
    winner_id: str | None = None
    table = _candidate_table(soup)
    if table is not None:
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) != 4:
                continue
            label = clean(cells[0].get_text(" ", strip=True))
            if not label or label.startswith(TOTALS_ROW_PREFIX):
                continue
            numbers = [_int(cell.get_text(" ", strip=True)) for cell in cells[1:]]
            if any(number is None for number in numbers):
                continue
            anchor = cells[0].find("a", href=True)
            candidates.append(
                {
                    "vrkCandidateId": candidate_id_from_url(anchor["href"]) if anchor else None,
                    "name": label,
                    "votesDistrict": numbers[0],
                    "votesPostal": numbers[1],
                    "votes": numbers[2],
                    "rank": len(candidates) + 1,
                }
            )

    if winner_match:
        winner_name = clean(winner_match.group(1))
        # The verdict sentence links the winner on every page that has ids at
        # all, so their id comes off the sentence itself rather than off a name
        # match against the table.
        for anchor in soup.find_all("a", href=CANDIDATE_ID_PATTERN):
            if clean(anchor.get_text(" ", strip=True)) == winner_name:
                winner_id = candidate_id_from_url(anchor["href"])
                break
        if winner_id is None:
            for candidate in candidates:
                if name_key(candidate["name"]) == name_key(winner_name):
                    winner_id = candidate["vrkCandidateId"]
                    break
    else:
        winner_name = None

    voters_match = VOTERS_PATTERN.search(text)
    turnout = {
        "registeredVoters": _int(REGISTERED_VOTERS_PATTERN.search(text).group(1))
        if REGISTERED_VOTERS_PATTERN.search(text)
        else None,
        "voters": _int(voters_match.group(1)) if voters_match else None,
        "turnoutPercent": _percent(voters_match.group(2)) if voters_match else None,
        "invalidBallots": _int(INVALID_BALLOTS_PATTERN.search(text).group(1))
        if INVALID_BALLOTS_PATTERN.search(text)
        else None,
        "validBallots": _int(VALID_BALLOTS_PATTERN.search(text).group(1))
        if VALID_BALLOTS_PATTERN.search(text)
        else None,
    }

    return {
        "constituencyName": constituency_name,
        "constituencyNumber": constituency_number,
        # The 1997-03 first-round pages are headed "Balsavimo rezultatai" with
        # no round at all; the caller supplies it from the page's place in the
        # election.
        "round": int(round_match.group(1)) if round_match else None,
        "held": (held_match.group(1) is None) if held_match else None,
        "runoffRequired": RUNOFF_PATTERN.search(text) is not None,
        "winnerName": winner_name,
        "winnerVrkCandidateId": winner_id,
        "turnout": turnout,
        "candidates": candidates,
        "sourceUrl": source_url,
        "mojibakeRepaired": mojibake,
    }


def parse_elected_members(html: str, source_url: str) -> list[dict[str, Any]]:
    """`seim96/rsnl.htm-1.htm` -- "Kandidatai, išrinkti Seimo nariais".

    One `<li>` per member: the anketa link (so the id is on the page), the
    nominator (a `partr2l` link, or the words "pats(-i)" for a self-nominated
    candidate) and the seat -- "pagal sąrašą", "I ture" or "II ture".
    """
    soup = BeautifulSoup(html, "lxml")
    members: list[dict[str, Any]] = []
    for item in soup.find_all("li"):
        anchor = item.find("a", href=CANDIDATE_ID_PATTERN)
        if anchor is None:
            continue
        text = normalize_space(item.get_text(" ", strip=True).replace("\xa0", " "))
        seat_match = re.search(r"išrinktas\(-a\)\s+(.+?)\s*$", text)
        nominator_match = re.search(r"(iškėlė|išsikėlė)\s+(.*?)\s*,\s*išrinktas\(-a\)", text)
        seat_label = seat_match.group(1) if seat_match else ""
        round_match = re.match(r"(I{1,2})\s+ture", seat_label)
        members.append(
            {
                "vrkCandidateId": candidate_id_from_url(anchor["href"]),
                "name": normalize_space(anchor.get_text(" ", strip=True).replace("\xa0", " ")),
                "seatLabel": seat_label,
                "seat": "daugiamandate" if seat_label.startswith("pagal sąrašą") else "vienmandate",
                "round": len(round_match.group(1)) if round_match else None,
                "selfNominated": bool(nominator_match) and nominator_match.group(1) == "išsikėlė",
                "nominator": nominator_match.group(2) if nominator_match else "",
                "sourceUrl": source_url,
            }
        )
    return members


LIST_RANKING_PATTERN = re.compile(r"rkreitl\.htm-(\d+)\.htm")


def parse_list_results(html: str, source_url: str) -> list[dict[str, Any]]:
    """`seim96/rdl.htm` -- every list's votes, share and mandate count, plus
    the link to its `rkreitl` ranking page. A list that won no mandate prints
    "-", and a list VRK did not rank has no ranking link."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    table = None
    for candidate_table in soup.find_all("table"):
        if "Mandat" in candidate_table.get_text(" ", strip=True):
            table = candidate_table
            break
    if table is None:
        return rows
    for row in table.find_all("tr"):
        cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
        if len(cells) < 4 or _int(cells[1]) is None:
            continue
        anchor = row.find("a", href=LIST_RANKING_PATTERN)
        list_id = LIST_RANKING_PATTERN.search(anchor["href"]).group(1) if anchor else None
        rows.append(
            {
                "listId": list_id,
                "name": cells[0],
                "votes": _int(cells[1]),
                "percent": _percent(cells[2]),
                "mandates": _int(cells[3]) or 0,
                "rankingUrl": urljoin(source_url, anchor["href"]) if anchor else None,
            }
        )
    return rows


def parse_ranking_page(html: str, source_url: str) -> list[dict[str, Any]]:
    """One `seim96/rkreitl.htm-<list>.htm` page: the list in its post-election
    order, each candidate with their pre-election number on the list, the
    positive and negative preference votes cast for them and the rating points
    VRK computed from the two. The order the page is printed in *is* the order
    mandates were handed out in."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for row in soup.find_all("tr"):
        anchor = row.find("a", href=CANDIDATE_ID_PATTERN)
        if anchor is None:
            continue
        cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
        if len(cells) < 5:
            continue
        rows.append(
            {
                "vrkCandidateId": candidate_id_from_url(anchor["href"]),
                "name": normalize_space(anchor.get_text(" ", strip=True).replace("\xa0", " ")),
                "listPosition": _int(cells[0]),
                "rank": len(rows) + 1,
                "positiveVotes": _int(cells[2]),
                "negativeVotes": _int(cells[3]),
                "ratingPoints": _int(cells[4]),
                "sourceUrl": source_url,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Sitemap side
# ---------------------------------------------------------------------------


def load_archive_sitemap(sitemap_path: Path) -> list[dict[str, Any]]:
    """The sitemap entries with VRK's candidate id resolved off each URL.

    `election_results.load_sitemap_entries` reads the modern
    `Kandidato<ID>Anketa.html` form, which this family's `kandvl.htm-<ID>.htm`
    URLs do not match, so the id is taken here instead.
    """
    payload = json.loads(sitemap_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"No sitemap entries in {sitemap_path}")
    resolved: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry = dict(entry)
        entry["vrkCandidateId"] = candidate_id_from_url(str(entry.get("url", "")))
        resolved.append(entry)
    return resolved


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def read_constituency_pages(
    pages: list[dict[str, Any]],
    results_dir: Path,
) -> list[dict[str, Any]]:
    """Fetch and parse every results page of an election.

    `pages` is `[{"url": ..., "round": 1|2}]`; the round is supplied because
    the 1997-03 first-round pages carry no round heading of their own. A page
    that does carry one has to agree with it.
    """
    parsed: list[dict[str, Any]] = []
    for page in pages:
        record = parse_constituency_results(fetch_page(results_dir, page["url"]), page["url"])
        record["declaredRound"] = record["round"]
        record["round"] = record["round"] or page["round"]
        record["roundMismatch"] = (
            record["declaredRound"] is not None and record["declaredRound"] != page["round"]
        )
        parsed.append(record)
    return parsed


def collect_constituency_votes(
    pages: list[dict[str, Any]],
    entries: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Every candidate's per-round vote rows, keyed by VRK candidate id.

    A row carrying an id joins on it; the 1998-03 pair carries none, so those
    rows resolve by name within the page's own constituency. A row that
    resolves to neither is returned as an unresolved finding rather than
    dropped silently.
    """
    votes: dict[str, list[dict[str, Any]]] = {}
    unresolved: list[dict[str, Any]] = []
    for page in pages:
        field = [
            entry
            for entry in entries
            if page["constituencyNumber"] is None
            or entry.get("constituencyNumber") == page["constituencyNumber"]
        ]
        for row in page["candidates"]:
            vrk_id = row["vrkCandidateId"]
            if vrk_id is None:
                hit = resolve_by_name(row["name"], field)
                vrk_id = hit["vrkCandidateId"] if hit else None
            if vrk_id is None:
                unresolved.append(
                    {
                        "name": row["name"],
                        "constituency": page["constituencyName"],
                        "constituencyNumber": page["constituencyNumber"],
                        "sourceUrl": page["sourceUrl"],
                    }
                )
                continue
            votes.setdefault(vrk_id, []).append(
                {
                    "turas": page["round"],
                    "apygardos-numeris": page["constituencyNumber"],
                    "balsai-apygardoje": row["votesDistrict"],
                    "balsai-pastu": row["votesPostal"],
                    "balsai": row["votes"],
                    "vieta": row["rank"],
                    "saltinis": page["sourceUrl"],
                }
            )
    for rows in votes.values():
        rows.sort(key=lambda row: row["turas"] or 0)
    return votes, unresolved


def resolve_page_winners(
    pages: list[dict[str, Any]],
    entries: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """The winner named by each page, resolved to a VRK candidate id."""
    elected: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, Any]] = []
    for page in pages:
        if not page["winnerName"]:
            continue
        vrk_id = page["winnerVrkCandidateId"]
        if vrk_id is None:
            field = [
                entry
                for entry in entries
                if page["constituencyNumber"] is None
                or entry.get("constituencyNumber") == page["constituencyNumber"]
            ]
            hit = resolve_by_name(page["winnerName"], field)
            vrk_id = hit["vrkCandidateId"] if hit else None
        if vrk_id is None:
            unresolved.append(
                {
                    "winnerName": page["winnerName"],
                    "constituency": page["constituencyName"],
                    "sourceUrl": page["sourceUrl"],
                }
            )
            continue
        elected[vrk_id] = {
            "seat": "vienmandate",
            "method": "constituency-verdict",
            "sourceUrl": page["sourceUrl"],
            "round": page["round"],
            "constituency": page["constituencyName"],
            "constituencyNumber": page["constituencyNumber"],
        }
    return elected, unresolved


def build_constituency_results(
    election_id: str,
    pages: list[dict[str, Any]],
    sitemap_path: Path,
    results_dir: Path,
    output_path: Path,
) -> tuple[Path, dict[str, Any]]:
    """The by-elections' results file: the constituency pages are the source.

    Five of the family's six elections were fought in a handful of
    constituencies with no list seats and no members page, so each page's own
    verdict is the whole answer -- a winner, or a stated `neįvyko`/runoff that
    makes `isrinktas` a known `false` for everyone on it.
    """
    entries = load_archive_sitemap(sitemap_path)
    parsed = read_constituency_pages(pages, results_dir)
    votes, unresolved_rows = collect_constituency_votes(parsed, entries)
    elected, unresolved_winners = resolve_page_winners(parsed, entries)

    in_sitemap = {entry["vrkCandidateId"] for entry in entries if entry["vrkCandidateId"]}
    stats = {
        "pages": len(parsed),
        "constituencies": len({page["constituencyNumber"] for page in parsed}),
        "candidates": len(entries),
        "candidatesWithVotes": len(votes),
        "candidatesWithoutVotes": len(in_sitemap - set(votes)),
        "unresolvedRows": len(unresolved_rows),
        "elected": len(elected),
        "electedNotInSitemap": len(set(elected) - in_sitemap),
        "unresolvedWinners": len(unresolved_winners),
        "constituenciesNotHeld": sum(1 for page in parsed if page["held"] is False),
        "roundMismatches": sum(1 for page in parsed if page["roundMismatch"]),
        "mojibakePages": sum(1 for page in parsed if page["mojibakeRepaired"]),
    }
    details = {
        "constituencies": [
            {key: value for key, value in page.items() if key != "candidates"} for page in parsed
        ],
        "constituencyVotes": votes,
        "unresolvedRows": unresolved_rows,
        "unresolvedWinners": unresolved_winners,
        "candidatesWithoutVotes": sorted(in_sitemap - set(votes)),
    }
    write_results(
        output_path,
        election_id,
        elected,
        stats,
        [page["sourceUrl"] for page in parsed],
        details,
        # Every constituency page read and every one of them `neįvyko`: the
        # 1998-1999 by-elections, whose candidates are a known `false`. An
        # empty map for any other reason is refused by write_results
        # (issue #134).
        nobody_elected=bool(parsed) and stats["constituenciesNotHeld"] == stats["constituencies"],
    )
    return output_path, stats


# ---------------------------------------------------------------------------
# The parse-stage join
# ---------------------------------------------------------------------------

MULTI_MEMBER_CONSTITUENCY = "Daugiamandatė"


def load_results_details(results_path: Path | None) -> dict[str, Any]:
    """The `elected`, `constituencyVotes` and `ranking` maps of a results file,
    or three empty maps when the file is absent -- the parse stage then leaves
    `isrinktas` out entirely rather than claiming a false."""
    if results_path is None or not results_path.exists():
        return {}
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    details = payload.get("details")
    details = details if isinstance(details, dict) else {}
    return {
        "elected": payload.get("elected") if isinstance(payload.get("elected"), dict) else {},
        "constituencyVotes": details.get("constituencyVotes")
        if isinstance(details.get("constituencyVotes"), dict)
        else {},
        "ranking": details.get("ranking") if isinstance(details.get("ranking"), dict) else {},
    }


def _list_id(candidacy: dict[str, Any]) -> str | None:
    match = re.search(r"partr2l\.htm-(\d+)\.htm", candidacy.get("iskele-nuoroda") or "")
    return match.group(1) if match else None


def apply_results(
    candidacies: list[dict[str, Any]],
    vrk_candidate_id: str | None,
    results: dict[str, Any],
) -> list[dict[str, Any]]:
    """Write `isrinktas` (and the votes) onto every candidacy of one record.

    This family's `kandidatavimas` is a list -- a 1996 candidate could stand in
    a constituency *and* on a list, and 51 of them were nominated twice over by
    a coalition and one of its member parties, giving four rows for two real
    candidacies. So the flag is per candidacy, and the seat the results name
    decides which rows carry it: a constituency seat marks every row for that
    constituency (both of a double-nominated pair -- they describe the same
    won seat), a list seat marks every `Daugiamandatė` row.

    Every other candidacy gets `false`, not null: the results pages state an
    outcome for every constituency in this family, so "not elected" is known
    rather than unread.
    """
    problems: list[dict[str, Any]] = []
    if not results:
        return problems

    winner = results["elected"].get(vrk_candidate_id or "")
    votes = results["constituencyVotes"].get(vrk_candidate_id or "") or []
    ranking = results["ranking"].get(vrk_candidate_id or "") or {}

    matched = 0
    for candidacy in candidacies:
        multi_member = candidacy.get("apygarda") == MULTI_MEMBER_CONSTITUENCY
        elected = False
        if winner is not None:
            if winner["seat"] == "daugiamandate":
                elected = multi_member
            else:
                elected = not multi_member and (
                    winner.get("constituencyNumber") is None
                    or winner["constituencyNumber"] == candidacy.get("apygardos-numeris")
                )
        candidacy["isrinktas"] = elected
        if elected:
            matched += 1
            candidacy["isrinktas-kaip"] = winner["seat"]
            candidacy["rezultatu-saltinis"] = winner["sourceUrl"]
            if winner.get("round"):
                candidacy["rezultatu-turas"] = winner["round"]

        if not multi_member:
            rounds = [
                row
                for row in votes
                if row.get("apygardos-numeris") in (None, candidacy.get("apygardos-numeris"))
            ]
            if rounds:
                candidacy["turai"] = rounds
        else:
            row = ranking.get(_list_id(candidacy) or "")
            if row:
                # `rank` is the post-preference order the seats were handed
                # out in; the ranking page also reprints the pre-election
                # number, which has to be the card's own -- a disagreement
                # would mean the two pages describe different list places.
                candidacy["porinkiminis-numeris-sarase"] = row.get("rank")
                candidacy["teigiami-balsai"] = row.get("positiveVotes")
                candidacy["neigiami-balsai"] = row.get("negativeVotes")
                candidacy["reitingo-balai"] = row.get("ratingPoints")
                candidacy["reitingo-saltinis"] = row.get("sourceUrl")
                if row.get("listPosition") != candidacy.get("numeris-sarase"):
                    problems.append(
                        {
                            "eventType": "ListPositionMismatch",
                            "detail": {
                                "list": row.get("list"),
                                "card": candidacy.get("numeris-sarase"),
                                "ranking": row.get("listPosition"),
                                "sourceUrl": row.get("sourceUrl"),
                            },
                        }
                    )

    if winner is not None and matched == 0:
        problems.append(
            {
                "eventType": "ElectedCandidacyUnmatched",
                "detail": {
                    "seat": winner["seat"],
                    "constituencyNumber": winner.get("constituencyNumber"),
                    "candidacies": [
                        {
                            "apygarda": candidacy.get("apygarda"),
                            "apygardos-numeris": candidacy.get("apygardos-numeris"),
                        }
                        for candidacy in candidacies
                    ],
                },
            }
        )
    return problems


def count_seats(elected: dict[str, dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(entry.get("seat", "?") for entry in elected.values()))


__all__ = [
    "CANDIDATE_ID_PATTERN",
    "MULTI_MEMBER_CONSTITUENCY",
    "VRK_STATINIAI_BASE",
    "apply_results",
    "build_constituency_results",
    "candidate_id_from_url",
    "collect_constituency_votes",
    "count_seats",
    "load_archive_sitemap",
    "load_results_details",
    "name_key",
    "parse_constituency_results",
    "parse_elected_members",
    "parse_list_results",
    "parse_ranking_page",
    "read_constituency_pages",
    "repair_baltic_text",
    "resolve_by_name",
    "resolve_page_winners",
]
