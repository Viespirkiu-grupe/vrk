"""Sitemap machinery for municipal general elections.

Every other election in the repository publishes its candidates on one listing
page. The municipal general elections publish them in *two* structures, and
neither is a superset of the other:

    savKandidataiMerai.html    every mayoral candidate, on one page
    savKandidataiSarasai.html  an index of party/committee lists, whose council
                               candidates live one page deeper

A large minority of people stand for both and appear in both structures under
the same VRK candidate id; a smaller group stands only for mayor and appears on
no list. Merging on that id is what makes the union come out equal to the total
VRK publishes on savKandidataiSuvestine.html.

Two elections share this shape so far — 2019 and 2023 — and they differ only in
their base path, their listing URL and the exact prose VRK uses to flag a
candidate standing for both seats. Everything structural is identical: the same
table ids, the same column order, the same `<font color="blue">` marking of a
winner. That is why this lives here rather than being copied per election: the
column-position and carry-forward defects fixed in 2023 would otherwise have to
be found again in every later module.

Callers pass the election-specific pieces in explicitly rather than importing
them, so a module can monkeypatch its own constants and still reach this code.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.shared.files import slugify, write_json
from scraper.shared.http import fetch_text

VRK_STATINIAI_BASE = "https://www.vrk.lt/statiniai/puslapiai/"

CANDIDATE_LINK_MARKER = "KandidatasAnketa"
LIST_LINK_MARKER = "savKandidataiTarNarApygardoje"
MUNICIPALITY_LINK_MARKER = "savKandidataiApygardoje"

LISTS_INDEX_SAMPLE_NAME = "lists-index.html"
LISTS_SAMPLE_DIRNAME = "lists"

# Pause between list-page fetches so a one-off sample capture of several hundred
# pages does not hammer VRK.
LIST_FETCH_DELAY_SECONDS = 0.2

CANDIDATE_ID_PATTERN = re.compile(r"rkndId-(\d+)")
LIST_PAGE_PATTERN = re.compile(r"rpgId-(\d+)_rorgId-(\d+)")
MUNICIPALITY_ID_PATTERN = re.compile(r"rpgId-(\d+)")
NUMBERED_NAME_PATTERN = re.compile(r"^(\d+)\.\s*(.+)$")

# The listing may append a status note to a name, as the 2025 mayoral listing
# does for struck-off candidates.
CANDIDATE_NOTE_PATTERN = re.compile(r"\(([^()]{1,64})\)\s*$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def clean_candidate_name(raw_name: str) -> str:
    name = normalize_space(raw_name)
    while True:
        cleaned = re.sub(r"\s*\([^()]{1,64}\)\s*$", "", name).strip()
        if cleaned == name:
            break
        name = cleaned
    return name


def extract_candidate_note(raw_name: str, mayor_marker: re.Pattern[str]) -> str:
    name = normalize_space(raw_name)
    if mayor_marker.search(name):
        # The mayoral marker is a role flag, not a status note; it is recorded
        # as a role instead so it does not end up in candidateNote.
        return ""
    match = CANDIDATE_NOTE_PATTERN.search(name)
    if match is None:
        return ""
    return normalize_space(match.group(1))


def resolve_candidate_url(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href

    if href.startswith("?srcUrl="):
        src_url = href.split("?srcUrl=", 1)[1]
        return urljoin(VRK_STATINIAI_BASE, src_url.lstrip("/"))

    return urljoin(VRK_STATINIAI_BASE, href.lstrip("/"))


def extract_vrk_candidate_id(href: str) -> str:
    match = CANDIDATE_ID_PATTERN.search(href or "")
    return match.group(1) if match else ""


def extract_src_url(listing_url: str) -> str | None:
    parsed = urlparse(listing_url)
    src_urls = parse_qs(parsed.query).get("srcUrl")
    return src_urls[0] if src_urls else None


def is_elected(anchor: Any) -> bool:
    # VRK marks an elected candidate by colouring the name blue inside the
    # anchor rather than with a field of its own.
    if anchor is None:
        return False
    if anchor.find("font", attrs={"color": "blue"}) is not None:
        return True
    style = str(anchor.get("style") or "")
    return "color: blue" in style or "color:blue" in style


def parse_int(value: str | None) -> int | None:
    # str.isdigit() accepts characters int() rejects — superscripts and other
    # numeric-but-not-decimal forms — so a footnote marker in a position cell
    # would abort the whole build rather than degrade to None.
    text = normalize_space(str(value or ""))
    try:
        return int(text)
    except ValueError:
        return None


def parse_numbered_name(text: str) -> tuple[int | None, str]:
    cleaned = normalize_space(text)
    match = NUMBERED_NAME_PATTERN.match(cleaned)
    if match is None:
        return None, cleaned
    return int(match.group(1)), match.group(2).strip()


def municipality_from_cell(cell: Any) -> dict[str, Any] | None:
    if cell is None:
        return None
    text = normalize_space(cell.get_text(" ", strip=True))
    if not text:
        return None

    anchor = None
    for candidate_anchor in cell.find_all("a", href=True):
        if MUNICIPALITY_LINK_MARKER in candidate_anchor["href"]:
            anchor = candidate_anchor
            break

    number, name = parse_numbered_name(text)
    municipality_id = ""
    if anchor is not None:
        match = MUNICIPALITY_ID_PATTERN.search(anchor["href"])
        if match:
            municipality_id = match.group(1)

    return {"id": municipality_id, "number": number, "name": name}


def list_page_sample_name(rpg_id: str, rorg_id: str) -> str:
    return f"rpgId-{rpg_id}_rorgId-{rorg_id}.html"


def select_data_table(soup: BeautifulSoup, table_id: str, link_marker: str) -> Any | None:
    table = soup.select_one(f"table#{table_id}.partydata") or soup.select_one(f"table#{table_id}")
    if table is not None:
        return table

    best_table = None
    best_count = 0
    for candidate_table in soup.select("table.partydata"):
        count = len(candidate_table.select(f"a[href*='{link_marker}']"))
        if count > best_count:
            best_table = candidate_table
            best_count = count
    return best_table


def table_rows(table: Any | None) -> list[Any]:
    if table is None:
        return []
    body = table.find("tbody")
    if body is not None:
        return body.find_all("tr")
    return table.find_all("tr")


def _row_candidate_anchor(row: Any) -> Any | None:
    for anchor in row.find_all("a", href=True):
        if CANDIDATE_LINK_MARKER in anchor["href"]:
            return anchor
    return None


# ---------------------------------------------------------------------------
# Listing structures
# ---------------------------------------------------------------------------


def extract_list_page_links(lists_index_html: str) -> list[dict[str, Any]]:
    """Municipality/party-list pairs from savKandidataiSarasai.html."""
    soup = BeautifulSoup(lists_index_html, "lxml")
    table = select_data_table(soup, "table2", LIST_LINK_MARKER)

    entries: list[dict[str, Any]] = []
    current_municipality: dict[str, Any] | None = None

    for row in table_rows(table):
        cells = row.find_all("td")
        if not cells:
            continue

        municipality = municipality_from_cell(cells[0])
        if municipality is not None:
            current_municipality = municipality

        list_anchor = None
        for anchor in row.find_all("a", href=True):
            if LIST_LINK_MARKER in anchor["href"]:
                list_anchor = anchor
                break
        if list_anchor is None or current_municipality is None:
            continue

        href = normalize_space(list_anchor["href"])
        match = LIST_PAGE_PATTERN.search(href)
        if match is None:
            continue

        rpg_id, rorg_id = match.group(1), match.group(2)

        # "Sąrašo numeris" is the cell immediately before the one holding the
        # list link. It must be read positionally rather than by scanning for
        # the first numeric cell: on the municipality group-header rows the
        # leading cells carry the municipality's own mandate and list counts,
        # so a scan returns "Mandatų skaičius" instead.
        list_number: int | None = None
        anchor_cell = list_anchor.find_parent("td")
        if anchor_cell is not None and anchor_cell in cells:
            anchor_index = cells.index(anchor_cell)
            if anchor_index > 0:
                list_number = parse_int(cells[anchor_index - 1].get_text(" ", strip=True))

        # The municipality cell is blank on continuation rows, so it is carried
        # forward — but the list URL names its own rpgId, so the carry-forward
        # is checked rather than trusted. Without this, a single unparseable
        # group-header cell would silently re-attribute every list beneath it to
        # the previous municipality with all counts unchanged.
        municipality = current_municipality
        carry_forward_ok = rpg_id == current_municipality["id"]
        if not carry_forward_ok:
            municipality = {"id": rpg_id, "number": None, "name": ""}

        entries.append(
            {
                "municipality": municipality,
                "municipalityCarryForwardOk": carry_forward_ok,
                "partyList": {
                    "id": rorg_id,
                    "number": list_number,
                    "name": normalize_space(list_anchor.get_text(" ", strip=True)),
                },
                # "Kandidatų skaičius sąraše" — the count VRK publishes for this
                # list, used to detect a truncated or partial sample page.
                "expectedCandidates": parse_int(cells[-2].get_text(" ", strip=True))
                if len(cells) >= 2
                else None,
                "url": resolve_candidate_url(href),
                "sampleName": list_page_sample_name(rpg_id, rorg_id),
            }
        )

    return entries


def parse_mayor_rows(mayors_html: str, mayor_marker: re.Pattern[str]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(mayors_html, "lxml")
    table = select_data_table(soup, "table2", CANDIDATE_LINK_MARKER)

    records: list[dict[str, Any]] = []
    current_municipality: dict[str, Any] | None = None

    for row_index, row in enumerate(table_rows(table), start=1):
        cells = row.find_all("td")
        if not cells:
            continue

        municipality = municipality_from_cell(cells[0])
        if municipality is not None:
            current_municipality = municipality

        anchor = _row_candidate_anchor(row)
        if anchor is None:
            continue

        raw_name = anchor.get_text(" ", strip=True)
        href = normalize_space(anchor["href"])
        records.append(
            {
                "rowIndex": row_index,
                "vrkCandidateId": extract_vrk_candidate_id(href),
                "candidateName": clean_candidate_name(raw_name),
                "candidateNote": extract_candidate_note(raw_name, mayor_marker),
                "url": resolve_candidate_url(href),
                "municipality": current_municipality,
                "round": normalize_space(cells[3].get_text(" ", strip=True)) if len(cells) > 3 else "",
                "nominatedBy": normalize_space(cells[4].get_text(" ", strip=True)) if len(cells) > 4 else "",
                "elected": is_elected(anchor),
            }
        )

    return records


def parse_list_page(
    list_html: str, link: dict[str, Any], mayor_marker: re.Pattern[str]
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(list_html, "lxml")
    table = select_data_table(soup, "table3", CANDIDATE_LINK_MARKER)

    records: list[dict[str, Any]] = []
    for row_index, row in enumerate(table_rows(table), start=1):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        anchor = _row_candidate_anchor(row)
        if anchor is None:
            continue

        raw_name = anchor.get_text(" ", strip=True)
        href = normalize_space(anchor["href"])
        post_position_text = (
            normalize_space(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else ""
        )

        records.append(
            {
                "rowIndex": row_index,
                "vrkCandidateId": extract_vrk_candidate_id(href),
                "candidateName": clean_candidate_name(raw_name),
                "candidateNote": extract_candidate_note(raw_name, mayor_marker),
                "url": resolve_candidate_url(href),
                "municipality": link["municipality"],
                "partyList": link["partyList"],
                "listPosition": parse_int(cells[0].get_text(" ", strip=True)),
                "postElectionPosition": parse_int(post_position_text),
                "elected": is_elected(anchor),
                "alsoMayoralCandidate": bool(mayor_marker.search(normalize_space(raw_name))),
            }
        )

    return records


# ---------------------------------------------------------------------------
# Sample capture
# ---------------------------------------------------------------------------


def fetch_listing_sample(
    sample_path: Path,
    wrapper_sample_path: Path,
    listing_url: str,
    mayors_url: str,
    lists_index_url: str,
) -> Path:
    """Download both listing structures plus every party-list page.

    `sample_path` holds the mayoral listing so the module keeps the `list.html`
    convention of the other elections; the council side lands next to it as
    `lists-index.html` plus one file per list under `lists/`. Already-saved list
    pages are left alone, so an interrupted capture resumes cheaply.
    """
    wrapper_html = fetch_text(listing_url)
    wrapper_sample_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper_sample_path.write_text(wrapper_html, encoding="utf-8")

    src_url = extract_src_url(listing_url)
    resolved_mayors_url = (
        urljoin(VRK_STATINIAI_BASE, src_url.lstrip("/")) if src_url else mayors_url
    )
    mayors_html = fetch_text(resolved_mayors_url)

    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(mayors_html, encoding="utf-8")

    samples_root = sample_path.parent
    lists_index_html = fetch_text(lists_index_url)
    (samples_root / LISTS_INDEX_SAMPLE_NAME).write_text(lists_index_html, encoding="utf-8")

    lists_dir = samples_root / LISTS_SAMPLE_DIRNAME
    lists_dir.mkdir(parents=True, exist_ok=True)

    list_links = extract_list_page_links(lists_index_html)
    for index, link in enumerate(list_links, start=1):
        target = lists_dir / link["sampleName"]
        if target.exists() and target.stat().st_size > 0:
            continue
        target.write_text(fetch_text(link["url"]), encoding="utf-8")
        if index % 50 == 0:
            print(f"  fetched {index}/{len(list_links)} party-list pages")
        time.sleep(LIST_FETCH_DELAY_SECONDS)

    return sample_path


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------


def build_candidate_id(candidate_name: str, vrk_candidate_id: str) -> str:
    """Stable, readable, collision-free candidate id.

    A couple of hundred candidates in an election this size share a name slug
    with someone else — four different people are called Mindaugas BALČIŪNAS in
    2023. The other modules disambiguate with a positional `-2`/`-3` suffix,
    which would make the id depend on traversal order; since the batch runner
    treats `data/<candidateId>-<electionId>.json` as its resume marker, an
    ordering change would silently re-attribute those records. VRK's own
    candidate id is already in every URL, so it is used as the suffix instead.
    """
    name_slug = slugify(candidate_name)
    if not name_slug:
        return vrk_candidate_id
    if not vrk_candidate_id:
        return name_slug
    return f"{name_slug}-{vrk_candidate_id}"


def build_sitemap(
    sample_path: Path,
    output_path: Path,
    election_id: str,
    listing_url: str,
    mayor_marker: re.Pattern[str],
) -> tuple[Path, dict[str, int]]:
    samples_root = sample_path.parent
    lists_index_path = samples_root / LISTS_INDEX_SAMPLE_NAME
    lists_dir = samples_root / LISTS_SAMPLE_DIRNAME

    mayor_records = parse_mayor_rows(sample_path.read_text(encoding="utf-8"), mayor_marker)

    list_links: list[dict[str, Any]] = []
    council_records: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    if lists_index_path.exists():
        list_links = extract_list_page_links(lists_index_path.read_text(encoding="utf-8"))
        for link in list_links:
            list_page_path = lists_dir / link["sampleName"]
            if not list_page_path.exists():
                skipped.append(
                    {
                        "reason": "missing-list-sample",
                        "sampleName": link["sampleName"],
                        "municipality": link["municipality"]["name"],
                        "partyList": link["partyList"]["name"],
                    }
                )
                continue

            if not link["municipalityCarryForwardOk"]:
                skipped.append(
                    {
                        "reason": "municipality-carry-forward-mismatch",
                        "sampleName": link["sampleName"],
                        "partyList": link["partyList"]["name"],
                    }
                )

            page_records = parse_list_page(
                list_page_path.read_text(encoding="utf-8"), link, mayor_marker
            )
            council_records.extend(page_records)

            # A present-but-truncated sample parses without error and just
            # yields fewer candidates, so the count VRK publishes for the list
            # is the only thing that catches it.
            expected = link["expectedCandidates"]
            if expected is not None and expected != len(page_records):
                skipped.append(
                    {
                        "reason": "list-candidate-count-mismatch",
                        "sampleName": link["sampleName"],
                        "municipality": link["municipality"]["name"],
                        "partyList": link["partyList"]["name"],
                        "expected": expected,
                        "parsed": len(page_records),
                    }
                )
    else:
        skipped.append({"reason": "missing-lists-index", "path": str(lists_index_path)})

    # Merge the two structures on VRK's candidate id. A candidate running for
    # both mayor and council has one entry carrying both candidacies.
    entries_by_vrk_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def _entry_for(record: dict[str, Any]) -> dict[str, Any] | None:
        vrk_id = record["vrkCandidateId"]
        if not vrk_id:
            skipped.append(
                {
                    "reason": "missing-vrk-candidate-id",
                    "candidateName": record["candidateName"],
                    "url": record["url"],
                }
            )
            return None
        if not record["candidateName"]:
            skipped.append({"reason": "empty-name", "vrkCandidateId": vrk_id})
            return None

        entry = entries_by_vrk_id.get(vrk_id)
        if entry is None:
            entry = {
                "candidateName": record["candidateName"],
                "candidateId": build_candidate_id(record["candidateName"], vrk_id),
                "candidateNote": record["candidateNote"],
                "url": record["url"],
                "vrkCandidateId": vrk_id,
                "municipality": record["municipality"],
                "roles": [],
            }
            entries_by_vrk_id[vrk_id] = entry
            order.append(vrk_id)
        return entry

    for record in council_records:
        entry = _entry_for(record)
        if entry is None:
            continue
        if "tarybos-narys" not in entry["roles"]:
            entry["roles"].append("tarybos-narys")
        entry["councilCandidacy"] = {
            "partyList": record["partyList"],
            "listPosition": record["listPosition"],
            "postElectionPosition": record["postElectionPosition"],
            "elected": record["elected"],
        }

    for record in mayor_records:
        entry = _entry_for(record)
        if entry is None:
            continue
        if "meras" not in entry["roles"]:
            entry["roles"].append("meras")
        entry["mayoralCandidacy"] = {
            "round": record["round"] or None,
            "nominatedBy": record["nominatedBy"] or None,
            "elected": record["elected"],
        }
        if record["candidateNote"] and not entry["candidateNote"]:
            entry["candidateNote"] = record["candidateNote"]

    entries = [entries_by_vrk_id[vrk_id] for vrk_id in order]

    candidate_id_counter: Counter[str] = Counter(entry["candidateId"] for entry in entries)
    duplicate_candidate_ids = sum(1 for _, count in candidate_id_counter.items() if count > 1)

    # Cross-check: the join on VRK's candidate id is what actually decides who
    # ran for both seats, but the listing also flags those rows in prose. The
    # two must agree. They disagree loudly if the marker pattern ever stops
    # matching one of the published spellings — a silent-data-loss failure mode
    # rather than a crash, and one that bites when a later election rewords the
    # marker (2019 says "tarybos narius - merus", 2023 says "savivaldybės
    # merus").
    marker_flagged = {
        record["vrkCandidateId"] for record in council_records if record["alsoMayoralCandidate"]
    }
    joined_dual = {entry["vrkCandidateId"] for entry in entries if len(entry["roles"]) > 1}
    marker_join_mismatch = len(marker_flagged.symmetric_difference(joined_dual))

    elected_council = sum(1 for entry in entries if entry.get("councilCandidacy", {}).get("elected"))
    elected_mayors = sum(1 for entry in entries if entry.get("mayoralCandidacy", {}).get("elected"))
    dual_candidates = sum(1 for entry in entries if len(entry["roles"]) > 1)

    payload = {
        "electionId": election_id,
        "sourceUrl": listing_url,
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": len(mayor_records) + len(council_records),
            "extracted": len(entries),
            "skipped": len(skipped),
            "duplicateCandidateIds": duplicate_candidate_ids,
            "partyLists": len(list_links),
            "mayoralCandidates": len(mayor_records),
            "councilCandidates": len(council_records),
            "dualCandidates": dual_candidates,
            "markerJoinMismatch": marker_join_mismatch,
            "electedMayors": elected_mayors,
            "electedCouncilMembers": elected_council,
        },
        "entries": entries,
        "skipped": skipped,
    }
    write_json(output_path, payload)

    stats = {
        "rows": len(mayor_records) + len(council_records),
        "extracted": len(entries),
        "skipped": len(skipped),
        "duplicate_candidate_ids": duplicate_candidate_ids,
        "party_lists": len(list_links),
        "mayoral_candidates": len(mayor_records),
        "council_candidates": len(council_records),
        "dual_candidates": dual_candidates,
        "marker_join_mismatch": marker_join_mismatch,
        "elected_mayors": elected_mayors,
        "elected_council_members": elected_council,
    }
    return output_path, stats
