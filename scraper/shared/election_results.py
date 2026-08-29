"""Elected status for the 2012-2015 page family, derived from VRK's results trees.

The pre-2016 candidate pages mark no winner anywhere — no ``(V)`` suffix, no
blue anchor, no elected note — so electedness for that family lives only in
the static results trees VRK published next to them
(``statiniai/puslapiai/<year>_<type>_rinkimai/output_lt/``). This module
walks those trees, resolves every winner to the VRK candidate id the
corpus keys on, and writes one ``sitemaps/<election-id>.results.json`` per
election that the parse stage joins on. Four page families:

- **Seimas members list** (2012): ``rinkimu_diena/isrinkti_seimo_nariai_kadencijaik.html``
  rows every elected member with an anketa link (so the id is on the page)
  and the seat type — ``Daugiamandatė`` or a numbered constituency.
- **Seimas constituencies** (2013, both 2015 by-elections; cross-check for
  2012): one page per constituency and round. Round one names the winner
  in prose (``Seimo nariu išrinktas …``) or declares a runoff; round two is
  a separate tree whose constituency ids and ``rezultatai_sm_kand<ID>``
  row ids are *re-issued* — they do not match the candidate pages — so a
  winner is resolved by name within the constituency's own field. A round
  two page that states no verdict is read by the statutory rule: the
  candidate with more votes in the two-candidate runoff.
- **European Parliament** (2014): ``rezultatai/rezultatai.html`` lists the
  eleven elected members with anketa links. (``ep_nariai.html`` next to it
  is the *current* composition, with replacements; it is not used.)
- **Presidential** (2014): the final-results page states
  ``Respublikos Prezidente išrinkta …``; resolved by name within the field
  of seven.
- **Municipal councils and mayors** (2015 general, the three repeat
  elections): the municipality results page gives each list's mandate
  count and links the list's post-preference ranking page, whose rows link
  every candidate's anketa (id on the page) and mark the mayor-elect with
  ``išrinktas(-a) meru(-e)``. The council seats are the list's top-M ranks,
  skipping the mayor-elect, whose seat is the mayoral one. The mayor is
  the verdict of the round-one page or, after a runoff, of the round-two
  page (a separate tree with re-issued ids), resolved by name within the
  municipality's mayoral field. VRK's ``savivaldybiu_tarybu_sudetis``
  composition pages are deliberately *not* the source — they are a
  snapshot taken a year later, with replacements seated — but they are
  fetched and used as a cross-check: every derived winner should appear
  there unless the page's early-termination table explains the absence.
- **Municipal councils, 2007** (the oldest tree, no ``output_lt`` level):
  ``balsu_uz_partijas_skaiciavimas/rinkimu_apygardos.html`` indexes the
  municipality pages (``rapgpl_<ID>``), each of which gives the lists'
  mandate counts and links a "Mandatus gavę kandidatai" page
  (``kand_mand_rapyg<ID>``) that rows every winner with an anketa link —
  the id is on the page and no ranking arithmetic is needed. The list
  mandate total on the results page and the ``Mandatų skaičius`` of the
  composition page (``lt/savivaldybes/rapg_<ID>``, a 2010 snapshot) are
  the cross-checks.

Every derivation carries its source URL and method, and every builder
reports reconciliation stats; a result set with unresolved winners or a
seat-count mismatch is a finding, not a shippable file.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any
import unicodedata
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from scraper.shared.files import write_json
from scraper.shared.http import fetch_text

VRK_BASE = "https://www.vrk.lt/"
STATIC_BASE = "https://www.vrk.lt/statiniai/puslapiai/"


def tree_root(tree: str) -> str:
    """The URL under which a results tree's pages live. Every tree from 2008
    on keeps them under ``<tree>/output_lt/``; the 2007 by-election tree has
    no output_lt level, which its module says by passing the name with a
    trailing slash ("2007_seimo_rinkimai/")."""
    if tree.endswith("/"):
        return f"{STATIC_BASE}{tree.rstrip('/')}"
    return f"{STATIC_BASE}{tree}/output_lt"
FETCH_PAUSE_SECONDS = 0.3

ANKETA_ID_PATTERN = re.compile(r"Kandidato(\d+)Anketa\.html")
RESULT_DISTRICT_PATTERN = re.compile(r"apygardos_rezultatai(\d+)\.html$")
SEIMO_DISTRICT_PATTERN = re.compile(r"rezultatai_vienmanate_apygarda(\d+)aktyvumasdesc(\d)turas\.html$")
LIST_RANKING_PATTERN = re.compile(r"apygardos(\d+)_partijos(\d+)_pirmumo_balsai\.html$")
COMPOSITION_PATTERN = re.compile(r"rapg_(\d+)\.html$")
# A self-nominated individual's own results row (2011, the one municipal
# general election in which individuals stood for the council on their own,
# listed on the ballot among the lists).
SELF_NOMINATED_RESULT_PATTERN = re.compile(r"savkand(\d+)_gauti_balsai_apygardoje\d+\.html$")
MAYOR_ELECT_MARKER = "išrinktas(-a) meru(-e)"

# The 2016-2025 candidate pages publish no results tree the scraper walks;
# their only elected signal is the profile's prose note ("Išrinktas pagal
# sąrašą", "Išrinkta vienmandatėje Zanavykų (Nr.64) apygardoje II ture",
# "Išrinktas Kupiškio rajono (Nr.23) savivaldybėje II ture", "Išrinktas II
# ture"). Measured across the corpus, the notes name the complete winner
# set — 141 of 141 Seimas seats in 2016, 2020 and 2024, 11 of 11 EP seats
# in 2019 and 2024 — so a record without one is a real non-winner, not a
# gap, and `isrinktas` may say `false`. Each prose form determines the
# seat; first match wins.
ELECTED_NOTE_SEAT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bvienmandatėje\b"), "vienmandate"),
    (re.compile(r"\bpagal\b.+\bsąrašą\b"), "daugiamandate"),
    (re.compile(r"\bsavivaldybėje\b"), "meras"),
    (re.compile(r"^Išrinkt(?:as|a) I{1,2} ture$"), "prezidentas"),
)


def candidacy_from_elected_note(pastaba: Any) -> dict[str, Any]:
    """A minimal `kandidatavimas` block — `isrinktas` and `isrinktasKaip` —
    derived from `profilis.pastaba` for the elections whose pages carry
    elected status only as that prose (docs/OUTPUT_SCHEMA.md). A note the
    seat table does not recognise still counts the winner, with the seat
    left unknown rather than guessed."""
    note = normalize_space(str(pastaba or ""))
    if not note.startswith("Išrink"):
        return {"isrinktas": False}
    for pattern, seat in ELECTED_NOTE_SEAT_PATTERNS:
        if pattern.search(note):
            return {"isrinktas": True, "isrinktasKaip": seat}
    return {"isrinktas": True, "isrinktasKaip": None}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def normalize_person_name(value: str) -> str:
    """Name key for matching a results page against the sitemap: NFC,
    upper-cased, whitespace-collapsed, diacritics kept (both sides are VRK's
    own spelling of the same person)."""
    text = unicodedata.normalize("NFC", value or "")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s*-\s*", "-", text)
    return " ".join(text.upper().split())


def resolve_url(href: str, base: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href.replace("http://www.vrk.lt/", "https://www.vrk.lt/", 1)
    return urljoin(base, href)


# ---------------------------------------------------------------------------
# Fetch / cache
# ---------------------------------------------------------------------------


def page_path(results_dir: Path, url: str) -> Path:
    """One file per fetched results page, named by its path under output_lt."""
    tail = url.split("/output_lt/", 1)[-1] if "/output_lt/" in url else "/".join(url.rsplit("/", 2)[-2:])
    tail = tail.replace("../", "").replace("/", "__")
    return results_dir / tail


def fetch_page(results_dir: Path, url: str) -> str:
    """Fetch a results page once; later calls read the saved copy."""
    path = page_path(results_dir, url)
    if path.exists():
        return path.read_text(encoding="utf-8")
    html = fetch_text(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    time.sleep(FETCH_PAUSE_SECONDS)
    return html


def page_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    return normalize_space(soup.get_text(" ", strip=True))


def find_links(html: str, base_url: str, pattern: re.Pattern[str]) -> list[tuple[str, str, re.Match[str]]]:
    """(absolute url, anchor text, match) for every anchor whose href matches."""
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    links: list[tuple[str, str, re.Match[str]]] = []
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor["href"])
        match = pattern.search(href)
        if match is None:
            continue
        url = resolve_url(href, base_url)
        if url in seen:
            continue
        seen.add(url)
        links.append((url, normalize_space(anchor.get_text(" ", strip=True)), match))
    return links


# ---------------------------------------------------------------------------
# Sitemap lookups
# ---------------------------------------------------------------------------


def load_sitemap_entries(sitemap_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(sitemap_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"No sitemap entries in {sitemap_path}")
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry = dict(entry)
        if not entry.get("vrkCandidateId"):
            match = ANKETA_ID_PATTERN.search(str(entry.get("url", "")))
            entry["vrkCandidateId"] = match.group(1) if match else None
        normalized.append(entry)
    return normalized


def resolve_name(
    name: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """The one sitemap entry whose name matches; None when zero or several do."""
    key = normalize_person_name(name)
    hits = [entry for entry in candidates if normalize_person_name(entry.get("candidateName", "")) == key]
    if len(hits) == 1:
        return hits[0]
    return None


# ---------------------------------------------------------------------------
# Seimas constituencies (rounds)
# ---------------------------------------------------------------------------

SEIMO_WINNER_PATTERN = re.compile(
    r"Seimo nari[ua]\s+išrinkt(?:as|a)\s+(.+?)(?:\.\s|\s+Pastaba|\s+Rūšiuoti|$)"
)
RUNOFF_PATTERN = re.compile(r"reikalingas pakartotinis balsavimas", re.IGNORECASE)
DISTRICT_ROW_PATTERN = re.compile(r"rezultatai_(?:sm|prezidento)_kand\d+")


def seimo_district_pages(results_dir: Path, tree: str, round_number: int) -> list[dict[str, Any]]:
    """The constituency pages of one round: url, constituency id, label."""
    folder = "rezultatai_vienmand_apygardose" + ("" if round_number == 1 else "2")
    index_url = f"{tree_root(tree)}/{folder}/rezultatai_vienmand_apygardose{round_number}turas.html"
    try:
        index_html = fetch_page(results_dir, index_url)
    except Exception:
        if round_number == 1:
            return []
        # The 2007 by-election tree keeps its round-two index and pages in
        # the round-one folder.
        index_url = f"{tree_root(tree)}/rezultatai_vienmand_apygardose/rezultatai_vienmand_apygardose{round_number}turas.html"
        try:
            index_html = fetch_page(results_dir, index_url)
        except Exception:
            return []
    pages: list[dict[str, Any]] = []
    for url, label, match in find_links(index_html, index_url, SEIMO_DISTRICT_PATTERN):
        pages.append({"url": url, "resultDistrictId": match.group(1), "label": label, "round": round_number})
    return pages


def parse_seimo_district_page(html: str) -> dict[str, Any]:
    """Verdict and candidate rows (name, votes) of one constituency/round page."""
    text = page_text(html)
    verdict = None
    runoff = bool(RUNOFF_PATTERN.search(text))
    match = SEIMO_WINNER_PATTERN.search(text)
    if match:
        verdict = normalize_space(match.group(1)).rstrip(".")
    rows: list[dict[str, Any]] = []
    soup = BeautifulSoup(html, "lxml")
    for anchor in soup.find_all("a", href=True):
        # The candidate row pages are "rezultatai_sm_kand<ID>…" from 2012
        # on; the 2009 and 2011 by-election trees reuse the presidential
        # template's "rezultatai_prezidento_kand<ID>…" stem for them; the
        # 2007 tree links each row straight to the candidate's anketa.
        if not (DISTRICT_ROW_PATTERN.search(anchor["href"]) or ANKETA_ID_PATTERN.search(anchor["href"])):
            continue
        tr = anchor.find_parent("tr")
        cells = [normalize_space(td.get_text(" ", strip=True)) for td in tr.find_all("td")] if tr else []
        total = None
        # name | apylinkėse | paštu | iš viso | % | %
        if len(cells) >= 4:
            digits = cells[3].replace(" ", "")
            total = int(digits) if digits.isdigit() else None
        rows.append({"name": normalize_space(anchor.get_text(" ", strip=True)), "votes": total})
    # Constituency heading: "Biržų - Kupiškio rinkimų apygarda" / "Nr. 48" appear in the page text.
    number_match = re.search(r"apygard[ao]s? Nr\.?\s*(\d+)|Nr\.\s*(\d+)", text)
    number = None
    if number_match:
        number = int(number_match.group(1) or number_match.group(2))
    return {"verdictName": verdict, "runoff": runoff, "rows": rows, "number": number, "text": text}


FIRST_ROUND_ELECTED_PAGE = "rezultatai_vienmand_apygardose/isrinkti_seimo_nariai.html"


def first_round_elected_by_label(results_dir: Path, tree: str) -> dict[str, dict[str, Any]]:
    """The tree's first-round elected-members page, keyed by constituency
    label ("56. Vilniaus - Šalčininkų"). The 2008 and 2009 trees publish it
    (a constituency decided outright in round one gets no verdict sentence
    on its own page and no round-two page); the 2011 and 2013 trees do not,
    and a missing page is simply an empty map."""
    url = f"{tree_root(tree)}/{FIRST_ROUND_ELECTED_PAGE}"
    try:
        html = fetch_page(results_dir, url)
    except Exception:
        return {}
    by_label: dict[str, dict[str, Any]] = {}
    for member in parse_elected_members_page(html, url):
        label = member["cells"][1] if len(member["cells"]) > 1 else ""
        if label:
            by_label[label] = {**member, "sourceUrl": url}
    return by_label


def seimo_constituency_winners(results_dir: Path, tree: str) -> list[dict[str, Any]]:
    """One record per constituency: the winner's name, the deciding round and
    how it was read (verdict sentence or runoff plurality)."""
    winners: list[dict[str, Any]] = []
    round_one = seimo_district_pages(results_dir, tree, 1)
    round_two = seimo_district_pages(results_dir, tree, 2)
    # Round-two pages are matched to round-one constituencies by label
    # (e.g. "48. Biržų - Kupiškio"); their ids are re-issued.
    round_two_by_label = {page["label"]: page for page in round_two}
    first_round_elected = first_round_elected_by_label(results_dir, tree)
    for page in round_one:
        parsed = parse_seimo_district_page(fetch_page(results_dir, page["url"]))
        record: dict[str, Any] = {
            "constituencyLabel": page["label"],
            "constituencyNumber": parsed["number"],
            "resultDistrictId": page["resultDistrictId"],
            "field": [row["name"] for row in parsed["rows"]],
            "winnerName": None,
            "round": None,
            "method": None,
            "sourceUrl": None,
        }
        if parsed["verdictName"]:
            record.update(winnerName=parsed["verdictName"], round=1, method="verdict", sourceUrl=page["url"])
        elif page["label"] in first_round_elected:
            member = first_round_elected[page["label"]]
            record.update(winnerName=member["name"], round=1, method="first-round-list", sourceUrl=member["sourceUrl"])
        else:
            second = round_two_by_label.get(page["label"])
            if second is None and len(round_two) == 1 and len(round_one) == 1:
                second = round_two[0]
            if second is not None:
                parsed_two = parse_seimo_district_page(fetch_page(results_dir, second["url"]))
                if parsed_two["verdictName"]:
                    record.update(winnerName=parsed_two["verdictName"], round=2, method="verdict", sourceUrl=second["url"])
                else:
                    ranked = [row for row in parsed_two["rows"] if row["votes"] is not None]
                    ranked.sort(key=lambda row: -row["votes"])
                    if len(ranked) >= 2 and ranked[0]["votes"] > ranked[1]["votes"]:
                        record.update(
                            winnerName=ranked[0]["name"], round=2, method="runoff-plurality", sourceUrl=second["url"]
                        )
        winners.append(record)
    return winners


# ---------------------------------------------------------------------------
# Elected-member lists (2012 Seimas, 2014 EP)
# ---------------------------------------------------------------------------


def parse_elected_members_page(html: str, base_url: str) -> list[dict[str, Any]]:
    """Rows of an elected-members page: anketa id, name, the other cells."""
    soup = BeautifulSoup(html, "lxml")
    members: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = ANKETA_ID_PATTERN.search(anchor["href"])
        if match is None:
            continue
        vrk_id = match.group(1)
        if vrk_id in seen:
            continue
        seen.add(vrk_id)
        tr = anchor.find_parent("tr")
        cells = [normalize_space(td.get_text(" ", strip=True)) for td in tr.find_all("td")] if tr else []
        members.append(
            {
                "vrkCandidateId": vrk_id,
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "cells": cells,
                "anketaUrl": resolve_url(anchor["href"], base_url),
            }
        )
    return members


# ---------------------------------------------------------------------------
# Municipal councils and mayors
# ---------------------------------------------------------------------------

# "Meru išrinktas …" / "Mere išrinkta …" — the noun inflects with the winner.
MAYOR_WINNER_PATTERN = re.compile(r"Mer[ue] išrinkt(?:as|a)\s+(.+?)(?:\.\s|\.$|\s+Kandidatas|$)")


def municipal_index_pages(results_dir: Path, tree: str, round_number: int) -> list[dict[str, Any]]:
    if round_number == 1:
        index_url = f"{tree_root(tree)}/rezultatai_daugiamand_apygardose/rezultatai_daugiamand_apygardose1turas.html"
    else:
        index_url = f"{tree_root(tree)}/rezultatai_vienmand_apygardose2/rezultatai_vienmand_apygardose2turas.html"
    try:
        index_html = fetch_page(results_dir, index_url)
    except Exception:
        return []
    pages: list[dict[str, Any]] = []
    for url, label, match in find_links(index_html, index_url, RESULT_DISTRICT_PATTERN):
        pages.append({"url": url, "resultDistrictId": match.group(1), "label": label, "round": round_number})
    return pages


def _row_mandates(cells: list[str]) -> int | None:
    # The mandate count is the row's last cell on every vintage of the page:
    # Rinkimų Nr. | list | "pirm." | apylinkėse | paštu | iš viso | % [| % su
    # pirmumo] | Mandatų skaičius — 2015 has the extra percentage, 2011 not.
    if not cells:
        return None
    last = cells[-1].replace(" ", "")
    return int(last) if last.isdigit() else None


def parse_municipality_results_page(html: str, url: str) -> dict[str, Any]:
    """Per-list mandate counts with ranking-page links, the self-nominated
    individuals' rows, the mayoral field and verdict, of one municipality's
    round-one results page."""
    soup = BeautifulSoup(html, "lxml")
    text = page_text(html)
    lists: list[dict[str, Any]] = []
    individuals: list[dict[str, Any]] = []
    results_table = None
    for anchor in soup.find_all("a", href=True):
        match = LIST_RANKING_PATTERN.search(anchor["href"])
        if match is None:
            continue
        tr = anchor.find_parent("tr")
        if tr is None:
            continue
        if results_table is None:
            results_table = tr.find_parent("table")
        cells = [normalize_space(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        lists.append(
            {
                "listName": cells[1] if len(cells) > 1 else normalize_space(anchor.get_text(" ", strip=True)),
                "listId": match.group(2),
                "rankingUrl": resolve_url(anchor["href"], url),
                "mandates": _row_mandates(cells),
            }
        )
    for anchor in soup.find_all("a", href=True):
        match = SELF_NOMINATED_RESULT_PATTERN.search(anchor["href"])
        if match is None:
            continue
        tr = anchor.find_parent("tr")
        if tr is None:
            continue
        cells = [normalize_space(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        individuals.append(
            {
                "vrkCandidateId": match.group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "mandates": _row_mandates(cells),
            }
        )
    mayoral_field: list[str] = []
    for anchor in soup.find_all("a", href=True):
        if "rezultatai_sav_kand" in anchor["href"]:
            mayoral_field.append(normalize_space(anchor.get_text(" ", strip=True)))
    verdict = None
    match = MAYOR_WINNER_PATTERN.search(text)
    if match:
        verdict = normalize_space(match.group(1)).rstrip(".")
    # The seats the page distributes: the results table's own "Iš viso" row,
    # whose last cell is the mandate column's total (individuals' seats
    # included, in 2011). The table is the one the ranking links live in.
    mandates_total = None
    if results_table is not None:
        for tr in results_table.find_all("tr"):
            cells = [normalize_space(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
            if cells and cells[0].lower().startswith("iš viso"):
                mandates_total = _row_mandates([cell for cell in cells if cell])
                break
    if mandates_total is None:
        total_match = re.search(r"Iš viso:?\s*(?:\d[\d\s]*\s+){3}[\d,]+%\s+[\d,]+%\s+(\d+)", text)
        mandates_total = int(total_match.group(1)) if total_match else None
    return {
        "lists": lists,
        "individuals": individuals,
        "mayoralField": list(dict.fromkeys(mayoral_field)),
        "mayorVerdictName": verdict,
        "listMandatesTotal": mandates_total,
    }


def parse_list_ranking_page(html: str, url: str) -> list[dict[str, Any]]:
    """Post-preference ranking rows: rank, anketa id, name, mayor-elect marker."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for anchor in soup.find_all("a", href=True):
        match = ANKETA_ID_PATTERN.search(anchor["href"])
        if match is None:
            continue
        tr = anchor.find_parent("tr")
        if tr is None:
            continue
        cells = tr.find_all("td")
        rank_text = normalize_space(cells[0].get_text(" ", strip=True)) if cells else ""
        # rank | name (+ mayor-elect marker) | pre-election position | preference votes
        pre_text = normalize_space(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else ""
        name_cell_text = normalize_space(anchor.parent.get_text(" ", strip=True)) if anchor.parent else ""
        rows.append(
            {
                "rank": int(rank_text) if rank_text.isdigit() else None,
                "preElectionPosition": int(pre_text) if pre_text.isdigit() else None,
                "vrkCandidateId": match.group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "mayorElect": MAYOR_ELECT_MARKER in name_cell_text,
            }
        )
    rows.sort(key=lambda row: (row["rank"] is None, row["rank"] or 0))
    return rows


def parse_composition_page(html: str) -> dict[str, Any]:
    """The council composition snapshot: mandates, members with recognition
    dates, and the early-termination table (names only)."""
    soup = BeautifulSoup(html, "lxml")
    text = page_text(html)
    # "Mandatų skaičius, įskaitant merą: 25" once mayors were elected
    # directly (2015); "Mandatų skaičius: 51" before that (2011).
    mandates_match = re.search(r"Mandatų skaičius(?:, įskaitant merą)?:\s*(\d+)", text)
    members: list[dict[str, Any]] = []
    for anchor in soup.find_all("a", href=True):
        match = ANKETA_ID_PATTERN.search(anchor["href"])
        if match is None:
            continue
        tr = anchor.find_parent("tr")
        cells = [normalize_space(td.get_text(" ", strip=True)) for td in tr.find_all("td")] if tr else []
        date = next((cell for cell in cells if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cell)), None)
        members.append(
            {
                "vrkCandidateId": match.group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "recognized": date,
                "mayor": "(MERAS)" in (cells[1] if len(cells) > 1 else "") or "(MERĖ)" in (cells[1] if len(cells) > 1 else ""),
            }
        )
    return {
        "mandates": int(mandates_match.group(1)) if mandates_match else None,
        "members": members,
    }


def municipal_winners(
    results_dir: Path,
    tree: str,
    composition_tree: str | None = None,
) -> dict[str, Any]:
    """Per municipality: the mayor-elect (name, round, method) and the
    elected council members (ids, from the list rankings), with the
    composition-page cross-check when that tree is given."""
    round_one = municipal_index_pages(results_dir, tree, 1)
    round_two = municipal_index_pages(results_dir, tree, 2)
    round_two_by_label = {page["label"]: page for page in round_two}

    composition_by_label: dict[str, str] = {}
    if composition_tree:
        index_url = f"{tree_root(composition_tree)}/savivaldybiu_tarybu_sudetis/savivaldybes.html"
        try:
            index_html = fetch_page(results_dir, index_url)
            for url, label, _ in find_links(index_html, index_url, COMPOSITION_PATTERN):
                composition_by_label[label] = url
        except Exception:
            composition_by_label = {}

    municipalities: list[dict[str, Any]] = []
    for page in round_one:
        html = fetch_page(results_dir, page["url"])
        parsed = parse_municipality_results_page(html, page["url"])
        record: dict[str, Any] = {
            "label": page["label"],
            "resultDistrictId": page["resultDistrictId"],
            "sourceUrl": page["url"],
            "mayoralField": parsed["mayoralField"],
            "mayor": None,
            "lists": [],
            "individuals": parsed["individuals"],
            "council": [],
            "listMandatesTotal": parsed["listMandatesTotal"],
        }
        if parsed["mayorVerdictName"]:
            record["mayor"] = {"name": parsed["mayorVerdictName"], "round": 1, "method": "verdict", "sourceUrl": page["url"]}
        else:
            second = round_two_by_label.get(page["label"])
            if second is not None:
                second_html = fetch_page(results_dir, second["url"])
                second_parsed = parse_municipality_results_page(second_html, second["url"])
                if second_parsed["mayorVerdictName"]:
                    record["mayor"] = {
                        "name": second_parsed["mayorVerdictName"],
                        "round": 2,
                        "method": "verdict",
                        "sourceUrl": second["url"],
                    }
                    record["mayoralField"] = list(dict.fromkeys(record["mayoralField"] + second_parsed["mayoralField"]))
        mayor_elect_ids: list[str] = []
        for list_info in parsed["lists"]:
            ranking = parse_list_ranking_page(fetch_page(results_dir, list_info["rankingUrl"]), list_info["rankingUrl"])
            mandates = list_info["mandates"] or 0
            elected_rows: list[dict[str, Any]] = []
            for row in ranking:
                if row["mayorElect"]:
                    mayor_elect_ids.append(row["vrkCandidateId"])
                    continue
                if len(elected_rows) < mandates:
                    elected_rows.append(row)
            record["lists"].append(
                {
                    "listName": list_info["listName"],
                    "listId": list_info["listId"],
                    "mandates": mandates,
                    "rankingUrl": list_info["rankingUrl"],
                    "rankedCandidates": len(ranking),
                    "electedIds": [row["vrkCandidateId"] for row in elected_rows],
                    "electedShort": max(0, mandates - len(elected_rows)),
                }
            )
            record["council"].extend(
                {
                    "vrkCandidateId": row["vrkCandidateId"],
                    "name": row["name"],
                    "listName": list_info["listName"],
                    "rank": row["rank"],
                    "preElectionPosition": row["preElectionPosition"],
                    "sourceUrl": list_info["rankingUrl"],
                }
                for row in elected_rows
            )
        # A self-nominated individual wins a seat on the mandate column of
        # the results table itself — there is no ranking page to walk.
        record["council"].extend(
            {
                "vrkCandidateId": individual["vrkCandidateId"],
                "name": individual["name"],
                "listName": None,
                "rank": None,
                "preElectionPosition": None,
                "selfNominated": True,
                "sourceUrl": page["url"],
            }
            for individual in parsed["individuals"]
            if individual["mandates"]
        )
        record["mayorElectIdsFromRankings"] = mayor_elect_ids
        if composition_by_label.get(page["label"]):
            comp = parse_composition_page(fetch_page(results_dir, composition_by_label[page["label"]]))
            record["composition"] = {
                "sourceUrl": composition_by_label[page["label"]],
                "mandates": comp["mandates"],
                "memberIds": [member["vrkCandidateId"] for member in comp["members"]],
                "memberNames": [member["name"] for member in comp["members"]],
                "mayorIds": [member["vrkCandidateId"] for member in comp["members"] if member["mayor"]],
            }
        municipalities.append(record)
    return {"municipalities": municipalities, "roundOnePages": len(round_one), "roundTwoPages": len(round_two)}


# ---------------------------------------------------------------------------
# Results file
# ---------------------------------------------------------------------------


def write_results(
    output_path: Path,
    election_id: str,
    elected: dict[str, dict[str, Any]],
    stats: dict[str, Any],
    sources: list[str],
    details: dict[str, Any] | None = None,
) -> Path:
    payload = {
        "electionId": election_id,
        "generatedAt": utc_now_iso(),
        "sources": sources,
        "stats": stats,
        "elected": elected,
    }
    if details:
        payload["details"] = details
    write_json(output_path, payload)
    return output_path


def load_results_lookup(results_path: Path | None) -> dict[str, dict[str, Any]] | None:
    """The elected map of a results file, or None when the file is absent —
    the parse stage then leaves `isrinktas` unknown rather than false."""
    if results_path is None or not results_path.exists():
        return None
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    elected = payload.get("elected") if isinstance(payload, dict) else None
    return elected if isinstance(elected, dict) else None


def count_stats(elected: dict[str, dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(entry.get("seat", "?") for entry in elected.values()))


# ---------------------------------------------------------------------------
# Builders, one per page family
# ---------------------------------------------------------------------------


def _winner_entry(seat: str, source_url: str, method: str, **extra: Any) -> dict[str, Any]:
    entry = {"seat": seat, "method": method, "sourceUrl": source_url}
    entry.update(extra)
    return entry


def build_seimo_constituency_results(
    election_id: str,
    tree: str,
    sitemap_path: Path,
    results_dir: Path,
    output_path: Path,
) -> tuple[Path, dict[str, Any]]:
    """Seimo elections decided constituency by constituency (2013, the 2015
    by-elections): one winner per constituency, resolved by name within the
    constituency's candidates."""
    entries = load_sitemap_entries(sitemap_path)
    winners = seimo_constituency_winners(results_dir, tree)
    elected: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, Any]] = []
    for record in winners:
        if not record["winnerName"]:
            unresolved.append({"constituency": record["constituencyLabel"], "reason": "no-verdict"})
            continue
        # The constituency's own field first (the sitemap carries the
        # constituency number for multi-constituency elections), then the
        # whole election when it has a single constituency.
        field = [
            entry
            for entry in entries
            if record["constituencyNumber"] is None
            or (entry.get("vienmandateCandidacy") or {}).get("apygardosNumeris") in (None, record["constituencyNumber"])
        ]
        hit = resolve_name(record["winnerName"], field)
        if hit is None or not hit.get("vrkCandidateId"):
            unresolved.append(
                {"constituency": record["constituencyLabel"], "winnerName": record["winnerName"], "reason": "name-not-resolved"}
            )
            continue
        elected[hit["vrkCandidateId"]] = _winner_entry(
            "vienmandate",
            record["sourceUrl"],
            record["method"],
            round=record["round"],
            constituency=record["constituencyLabel"],
        )
    stats = {
        "constituencies": len(winners),
        "winnersResolved": len(elected),
        "unresolved": len(unresolved),
        "decidedInRoundTwo": sum(1 for record in winners if record["round"] == 2),
        "byRunoffPlurality": sum(1 for record in winners if record["method"] == "runoff-plurality"),
    }
    sources = [record["sourceUrl"] for record in winners if record["sourceUrl"]]
    write_results(output_path, election_id, elected, stats, sources, {"unresolved": unresolved, "constituencies": winners})
    return output_path, stats


def build_seimo_members_results(
    election_id: str,
    tree: str,
    sitemap_path: Path,
    results_dir: Path,
    output_path: Path,
    members_page: str = "rinkimu_diena/isrinkti_seimo_nariai_kadencijaik.html",
) -> tuple[Path, dict[str, Any]]:
    """A Seimo general election with VRK's elected-members page (2012): ids
    come from the page's anketa links; the seat type from its constituency
    column. The constituency pages are walked too, as the cross-check that
    every constituency winner on the list is the one the constituency page
    names."""
    entries = load_sitemap_entries(sitemap_path)
    by_id = {entry["vrkCandidateId"]: entry for entry in entries if entry.get("vrkCandidateId")}
    url = f"{tree_root(tree)}/{members_page}"
    members = parse_elected_members_page(fetch_page(results_dir, url), url)
    elected: dict[str, dict[str, Any]] = {}
    not_in_sitemap: list[dict[str, Any]] = []
    for member in members:
        seat_cell = member["cells"][1] if len(member["cells"]) > 1 else ""
        seat = "daugiamandate" if seat_cell.lower().startswith("daugiamandat") else "vienmandate"
        if member["vrkCandidateId"] not in by_id:
            not_in_sitemap.append(member)
            continue
        elected[member["vrkCandidateId"]] = _winner_entry(
            seat, url, "members-list", constituency=None if seat == "daugiamandate" else seat_cell, party=member["cells"][2] if len(member["cells"]) > 2 else None
        )
    # Cross-check against the constituency pages.
    winners = seimo_constituency_winners(results_dir, tree)
    agree = disagree = unresolved = 0
    disagreements: list[dict[str, Any]] = []
    for record in winners:
        if not record["winnerName"]:
            unresolved += 1
            continue
        field = [
            entry for entry in entries
            if (entry.get("vienmandateCandidacy") or {}).get("apygardosNumeris") == record["constituencyNumber"]
        ]
        hit = resolve_name(record["winnerName"], field)
        if hit is None:
            unresolved += 1
            disagreements.append({"constituency": record["constituencyLabel"], "winnerName": record["winnerName"], "reason": "name-not-resolved"})
            continue
        if elected.get(hit["vrkCandidateId"], {}).get("seat") == "vienmandate":
            agree += 1
        else:
            disagree += 1
            disagreements.append({"constituency": record["constituencyLabel"], "winnerName": record["winnerName"], "vrkCandidateId": hit["vrkCandidateId"], "reason": "not-on-members-list-as-constituency-winner"})
    stats = {
        "membersListed": len(members),
        "membersInSitemap": len(elected),
        "membersNotInSitemap": len(not_in_sitemap),
        "seats": count_stats(elected),
        "constituencyPages": len(winners),
        "constituencyWinnersAgree": agree,
        "constituencyWinnersDisagree": disagree,
        "constituencyWinnersUnresolved": unresolved,
    }
    write_results(output_path, election_id, elected, stats, [url], {"notInSitemap": not_in_sitemap, "disagreements": disagreements, "constituencies": winners})
    return output_path, stats


def build_ep_results(
    election_id: str,
    tree: str,
    sitemap_path: Path,
    results_dir: Path,
    output_path: Path,
    members_page: str = "rezultatai/rezultatai.html",
) -> tuple[Path, dict[str, Any]]:
    entries = load_sitemap_entries(sitemap_path)
    by_id = {entry["vrkCandidateId"]: entry for entry in entries if entry.get("vrkCandidateId")}
    url = f"{tree_root(tree)}/{members_page}"
    members = parse_elected_members_page(fetch_page(results_dir, url), url)
    elected: dict[str, dict[str, Any]] = {}
    not_in_sitemap: list[dict[str, Any]] = []
    for member in members:
        if member["vrkCandidateId"] not in by_id:
            not_in_sitemap.append(member)
            continue
        elected[member["vrkCandidateId"]] = _winner_entry(
            "daugiamandate", url, "members-list", party=member["cells"][1] if len(member["cells"]) > 1 else None
        )
    stats = {"membersListed": len(members), "membersInSitemap": len(elected), "membersNotInSitemap": len(not_in_sitemap)}
    write_results(output_path, election_id, elected, stats, [url], {"notInSitemap": not_in_sitemap})
    return output_path, stats


# The name runs up to and including its upper-cased surname token: 2014's
# page closes the sentence with a period, 2009's runs straight into the next
# heading ("… išrinkta Dalia GRYBAUSKAITĖ Balsavimo rezultatai …"), and the
# collapsed page text keeps no line break between them.
PRESIDENT_WINNER_PATTERN = re.compile(
    r"Respublikos Prezident[eu] išrinkt(?:as|a)\s+((?:\S+\s+)*?[^\s.]*[A-ZĄČĘĖĮŠŲŪŽ]{2,}[^\s.,;]*)"
)


def build_presidential_results(
    election_id: str,
    tree: str,
    sitemap_path: Path,
    results_dir: Path,
    output_path: Path,
    results_page: str = "rinkimu_diena/rezultatai_isankstiniai2.html",
) -> tuple[Path, dict[str, Any]]:
    entries = load_sitemap_entries(sitemap_path)
    url = f"{tree_root(tree)}/{results_page}"
    text = page_text(fetch_page(results_dir, url))
    match = PRESIDENT_WINNER_PATTERN.search(text)
    elected: dict[str, dict[str, Any]] = {}
    winner_name = normalize_space(match.group(1)) if match else None
    hit = resolve_name(winner_name, entries) if winner_name else None
    if hit is not None and hit.get("vrkCandidateId"):
        elected[hit["vrkCandidateId"]] = _winner_entry("prezidentas", url, "verdict", round=2 if "2" in results_page else 1)
    stats = {"winnerName": winner_name, "winnersResolved": len(elected), "unresolved": 0 if elected else 1}
    write_results(output_path, election_id, elected, stats, [url])
    return output_path, stats


def build_municipal_results(
    election_id: str,
    tree: str,
    sitemap_path: Path,
    results_dir: Path,
    output_path: Path,
    composition_tree: str | None = None,
    municipality_filter: Any = None,
    annulments: dict[str, dict[str, str]] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Municipal councils and mayors (2015). The mayor is resolved by name
    within the municipality's mayoral candidates in the sitemap; council
    members come with their ids from the ranking pages.

    `annulments` names municipalities whose published results VRK later
    declared void — `{"47. Šilutės rajono": {"scope": "all", "decision":
    "…"}}` with scope ``all`` (council and mayor) or ``mayor``. Their winners
    stay in the file, flagged `annulled`, and the parse stage writes them
    as not elected: the results page did name them, the decision unmade it,
    and the repeat election's own records carry the seats actually won.
    """
    entries = load_sitemap_entries(sitemap_path)
    annulments = annulments or {}
    by_id = {entry["vrkCandidateId"]: entry for entry in entries if entry.get("vrkCandidateId")}
    has_roles = any(entry.get("roles") for entry in entries)
    walked = municipal_winners(results_dir, tree, composition_tree=composition_tree)
    elected: dict[str, dict[str, Any]] = {}
    per_municipality: list[dict[str, Any]] = []
    unresolved_mayors: list[dict[str, Any]] = []
    council_not_in_sitemap: list[dict[str, Any]] = []
    seat_mismatches: list[dict[str, Any]] = []
    composition_checked = composition_agree = composition_missing_total = 0
    for muni in walked["municipalities"]:
        if municipality_filter is not None and not municipality_filter(muni["label"]):
            continue
        mayor_id = None
        annulment = annulments.get(muni["label"])
        if muni["mayor"]:
            mayoral_field = [
                entry for entry in entries
                if (not has_roles or "meras" in (entry.get("roles") or []))
                and _municipality_matches(entry.get("municipality"), muni["label"])
            ]
            hit = resolve_name(muni["mayor"]["name"], mayoral_field)
            if hit is None:
                # Fall back to the ranking pages' own marker when it is unique.
                marker_ids = [vrk_id for vrk_id in muni["mayorElectIdsFromRankings"] if vrk_id in by_id]
                if len(set(marker_ids)) == 1:
                    hit = by_id[marker_ids[0]]
            if hit is not None and hit.get("vrkCandidateId"):
                mayor_id = hit["vrkCandidateId"]
                elected[mayor_id] = _winner_entry(
                    "meras", muni["mayor"]["sourceUrl"], muni["mayor"]["method"], round=muni["mayor"]["round"], municipality=muni["label"]
                )
                if annulment:
                    elected[mayor_id]["annulled"] = annulment["decision"]
            else:
                unresolved_mayors.append({"municipality": muni["label"], "mayorName": muni["mayor"]["name"]})
        council_ids: list[str] = []
        council_candidates = [
            entry for entry in entries
            if "tarybos-narys" in (entry.get("roles") or []) and _municipality_matches(entry.get("municipality"), muni["label"])
        ]
        for member in muni["council"]:
            vrk_id = member["vrkCandidateId"]
            resolved_by = "id"
            if vrk_id not in by_id:
                # A candidate who also stood for mayor holds two VRK ids; the
                # listings (and so the sitemap) use one, the ranking pages the
                # other. Resolve by name within the municipality's council
                # candidates, on the same list.
                same_list = [
                    entry for entry in council_candidates
                    if normalize_person_name((entry.get("councilCandidacy") or {}).get("partyList") or "")
                    == normalize_person_name(member["listName"])
                ]
                same_position = [
                    entry for entry in same_list
                    if (entry.get("councilCandidacy") or {}).get("listPosition") == member.get("preElectionPosition")
                ]
                hit = (
                    resolve_name(member["name"], same_position)
                    or resolve_name(member["name"], same_list)
                    or resolve_name(member["name"], council_candidates)
                )
                if hit is None or not hit.get("vrkCandidateId"):
                    council_not_in_sitemap.append({"municipality": muni["label"], **member})
                    continue
                vrk_id = hit["vrkCandidateId"]
                resolved_by = "name-and-list"
            council_ids.append(vrk_id)
            existing = elected.get(vrk_id)
            if existing and existing["seat"] == "meras":
                # Cannot happen by construction (the mayor-elect is skipped
                # in the rankings) but keep the mayoral seat if it did.
                continue
            if member.get("selfNominated"):
                entry = _winner_entry(
                    "tarybos-narys", member["sourceUrl"], "self-nominated", municipality=muni["label"]
                )
            else:
                entry = _winner_entry(
                    "tarybos-narys", member["sourceUrl"], "list-ranking", municipality=muni["label"], listName=member["listName"], rank=member["rank"]
                )
            if resolved_by != "id":
                entry["resolvedBy"] = resolved_by
                entry["vrkCandidateIdOnResultsPage"] = member["vrkCandidateId"]
            if annulment and annulment.get("scope") == "all":
                entry["annulled"] = annulment["decision"]
            elected[vrk_id] = entry
        derived_total = len(council_ids) + (1 if mayor_id else 0)
        # The mayor's seat is on top of the list mandates only where a mayor
        # was elected at all — the page then carries a mayoral field. 2011
        # elected none, and its mandate total is the whole council.
        mayoral_seat = 1 if (muni["mayor"] or muni["mayoralField"]) else 0
        expected_total = (muni["listMandatesTotal"] + mayoral_seat) if muni["listMandatesTotal"] is not None else None
        short_lists = [lst for lst in muni["lists"] if lst["electedShort"]]
        muni_stats = {
            "municipality": muni["label"],
            "mayorResolved": mayor_id is not None,
            "mayorRound": (muni["mayor"] or {}).get("round"),
            "councilElected": len(council_ids),
            "listMandatesTotal": muni["listMandatesTotal"],
            "derivedTotal": derived_total,
            "expectedTotal": expected_total,
            "listsShort": [(lst["listName"], lst["electedShort"]) for lst in short_lists],
        }
        if expected_total is not None and derived_total != expected_total:
            seat_mismatches.append(muni_stats)
        comp = muni.get("composition")
        if comp and comp["memberIds"]:
            # The composition page links both the seated members and the
            # early-terminated ones by anketa id; a derived winner must be in
            # one of the two, under either of the ids a dual candidate holds.
            composition_checked += 1
            derived_ids: list[tuple[str, ...]] = []
            for vrk_id in council_ids:
                entry = elected.get(vrk_id) or {}
                derived_ids.append(tuple(x for x in (vrk_id, entry.get("vrkCandidateIdOnResultsPage")) if x))
            if mayor_id:
                derived_ids.append(tuple(x for x in (mayor_id, *muni["mayorElectIdsFromRankings"]) if x))
            comp_ids = set(comp["memberIds"])
            # The composition page can link a person under yet another VRK
            # id (Telšiai's mayor holds three), so a name match — surname
            # first there, given name first in the sitemap — backs the ids.
            comp_names = {_name_tokens(name) for name in comp["memberNames"]}
            missing = set()
            for ids in derived_ids:
                if any(x in comp_ids for x in ids):
                    continue
                entry_name = (by_id.get(ids[0]) or {}).get("candidateName", "")
                if _name_tokens(entry_name) in comp_names:
                    continue
                missing.add(ids[0])
            muni_stats["compositionMandates"] = comp["mandates"]
            muni_stats["compositionMembers"] = len(comp["memberIds"])
            muni_stats["derivedNotInComposition"] = len(missing)
            composition_missing_total += len(missing)
            if not missing:
                composition_agree += 1
        per_municipality.append(muni_stats)
    stats = {
        "municipalities": len(per_municipality),
        "roundTwoPages": walked["roundTwoPages"],
        "mayorsResolved": sum(1 for m in per_municipality if m["mayorResolved"]),
        "mayorsUnresolved": len(unresolved_mayors),
        "mayorsDecidedInRoundTwo": sum(1 for m in per_municipality if m["mayorRound"] == 2),
        "councilMembers": sum(m["councilElected"] for m in per_municipality),
        "councilNotInSitemap": len(council_not_in_sitemap),
        "councilResolvedByNameAndList": sum(1 for e in elected.values() if e.get("resolvedBy") == "name-and-list"),
        "councilSelfNominated": sum(1 for e in elected.values() if e.get("method") == "self-nominated"),
        "seatCountMismatches": len(seat_mismatches),
        "compositionPagesChecked": composition_checked,
        "compositionFullyContainsDerived": composition_agree,
        "derivedNotInComposition": composition_missing_total,
        "seats": count_stats(elected),
        "annulledWinners": sum(1 for e in elected.values() if e.get("annulled")),
    }
    details = {
        "annulments": annulments,
        "perMunicipality": per_municipality,
        "unresolvedMayors": unresolved_mayors,
        "councilNotInSitemap": council_not_in_sitemap,
        "seatCountMismatches": seat_mismatches,
    }
    sources = [muni["sourceUrl"] for muni in walked["municipalities"]]
    write_results(output_path, election_id, elected, stats, sources, details)
    return output_path, stats


# ---------------------------------------------------------------------------
# Municipal councils, 2007: the mandates page
# ---------------------------------------------------------------------------

MUNICIPAL_2007_INDEX_PAGE = "balsu_uz_partijas_skaiciavimas/rinkimu_apygardos.html"
MUNICIPAL_2007_COMPOSITION_INDEX_PAGE = "lt/savivaldybes.html"
MUNICIPAL_2007_DISTRICT_PATTERN = re.compile(r"rapgpl_(\d+)\.html$")
MUNICIPAL_2007_LIST_PATTERN = re.compile(r"rapg_kand(\d+)_(\d+)\.html$")
MANDATES_PAGE_PATTERN = re.compile(r"kand_mand_rapyg(\d+)\.html$")


def parse_municipality_results_page_2007(html: str, url: str) -> dict[str, Any]:
    """The lists' mandate counts, the table's "Iš viso" total and the
    mandates-page link of one 2007 municipality results page."""
    soup = BeautifulSoup(html, "lxml")
    lists: list[dict[str, Any]] = []
    results_table = None
    for anchor in soup.find_all("a", href=True):
        match = MUNICIPAL_2007_LIST_PATTERN.search(anchor["href"])
        if match is None:
            continue
        tr = anchor.find_parent("tr")
        if tr is None:
            continue
        if results_table is None:
            results_table = tr.find_parent("table")
        cells = [normalize_space(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        lists.append(
            {
                "listName": normalize_space(anchor.get_text(" ", strip=True)),
                "listId": match.group(2),
                "mandates": _row_mandates(cells),
            }
        )
    mandates_total = None
    if results_table is not None:
        # The 2007 total row is <th> cells, the first of them blank.
        for tr in results_table.find_all("tr"):
            cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
            cells = [cell for cell in cells if cell]
            if cells and cells[0].lower().startswith("iš viso"):
                mandates_total = _row_mandates(cells)
                break
    mandates_page = None
    for page_url, _, _ in find_links(html, url, MANDATES_PAGE_PATTERN):
        mandates_page = page_url
        break
    return {"lists": lists, "listMandatesTotal": mandates_total, "mandatesPageUrl": mandates_page}


def parse_mandates_page_2007(html: str) -> list[dict[str, Any]]:
    """The winners of one municipality: surname-first name, list, and
    post-election number on the list, each with VRK's candidate id from
    the anketa link."""
    soup = BeautifulSoup(html, "lxml")
    winners: list[dict[str, Any]] = []
    for anchor in soup.find_all("a", href=True):
        match = ANKETA_ID_PATTERN.search(anchor["href"])
        if match is None:
            continue
        tr = anchor.find_parent("tr")
        cells = [normalize_space(td.get_text(" ", strip=True)) for td in tr.find_all("td")] if tr else []
        rank = cells[-1] if cells else ""
        winners.append(
            {
                "vrkCandidateId": match.group(1),
                "name": normalize_space(anchor.get_text(" ", strip=True)),
                "listName": cells[1] if len(cells) > 2 else None,
                "rank": int(rank) if rank.isdigit() else None,
            }
        )
    return winners


def build_municipal_mandates_results(
    election_id: str,
    tree: str,
    sitemap_path: Path,
    results_dir: Path,
    output_path: Path,
) -> tuple[Path, dict[str, Any]]:
    """Municipal councils from VRK's per-municipality "Mandatus gavę
    kandidatai" pages (2007). Every winner is on the page with an anketa
    link, so the join is by id; the results table's mandate total and the
    composition page's mandate count are the cross-checks."""
    entries = load_sitemap_entries(sitemap_path)
    by_id = {entry["vrkCandidateId"]: entry for entry in entries if entry.get("vrkCandidateId")}
    index_url = f"{tree_root(tree)}/{MUNICIPAL_2007_INDEX_PAGE}"
    index_html = fetch_page(results_dir, index_url)
    composition_index_url = f"{tree_root(tree)}/{MUNICIPAL_2007_COMPOSITION_INDEX_PAGE}"
    composition_by_id: dict[str, str] = {}
    try:
        for url, _, match in find_links(fetch_page(results_dir, composition_index_url), composition_index_url, COMPOSITION_PATTERN):
            composition_by_id[match.group(1)] = url
    except Exception:
        composition_by_id = {}

    elected: dict[str, dict[str, Any]] = {}
    per_municipality: list[dict[str, Any]] = []
    council_not_in_sitemap: list[dict[str, Any]] = []
    seat_mismatches: list[dict[str, Any]] = []
    municipality_mismatches: list[dict[str, Any]] = []
    sources: list[str] = []
    for page_url, label, match in find_links(index_html, index_url, MUNICIPAL_2007_DISTRICT_PATTERN):
        district_id = match.group(1)
        parsed = parse_municipality_results_page_2007(fetch_page(results_dir, page_url), page_url)
        winners: list[dict[str, Any]] = []
        if parsed["mandatesPageUrl"]:
            winners = parse_mandates_page_2007(fetch_page(results_dir, parsed["mandatesPageUrl"]))
            sources.append(parsed["mandatesPageUrl"])
        resolved = 0
        for winner in winners:
            vrk_id = winner["vrkCandidateId"]
            entry = by_id.get(vrk_id)
            if entry is None:
                council_not_in_sitemap.append({"municipality": label, **winner})
                continue
            # The id is VRK's own, so the join is exact; the municipality
            # the sitemap places the candidate in should still be this one.
            if not _municipality_matches(entry.get("municipality"), label):
                municipality_mismatches.append({"municipality": label, "sitemapMunicipality": entry.get("municipality"), **winner})
            resolved += 1
            elected[vrk_id] = _winner_entry(
                "tarybos-narys",
                parsed["mandatesPageUrl"],
                "mandates-page",
                municipality=label,
                listName=winner["listName"],
                rank=winner["rank"],
            )
        list_mandates_sum = sum(lst["mandates"] or 0 for lst in parsed["lists"])
        muni_stats: dict[str, Any] = {
            "municipality": label,
            "resultDistrictId": district_id,
            "winnersOnPage": len(winners),
            "councilElected": resolved,
            "listMandatesTotal": parsed["listMandatesTotal"],
            "listMandatesSum": list_mandates_sum,
            "lists": len(parsed["lists"]),
        }
        if parsed["listMandatesTotal"] is None or len(winners) != parsed["listMandatesTotal"] or list_mandates_sum != parsed["listMandatesTotal"]:
            seat_mismatches.append(muni_stats)
        composition_url = composition_by_id.get(district_id)
        if composition_url:
            comp = parse_composition_page(fetch_page(results_dir, composition_url))
            muni_stats["compositionMandates"] = comp["mandates"]
            muni_stats["compositionMembers"] = len(comp["members"])
            # The 2010 snapshot seats replacements; the winners it still
            # lists are a floor, its mandate count the whole council.
            muni_stats["winnersStillSeated"] = sum(1 for w in winners if w["vrkCandidateId"] in {m["vrkCandidateId"] for m in comp["members"]})
        per_municipality.append(muni_stats)
    stats = {
        "municipalities": len(per_municipality),
        "councilMembers": len(elected),
        "winnersOnPages": sum(m["winnersOnPage"] for m in per_municipality),
        "councilNotInSitemap": len(council_not_in_sitemap),
        "municipalityMismatches": len(municipality_mismatches),
        "seatCountMismatches": len(seat_mismatches),
        "compositionPagesChecked": sum(1 for m in per_municipality if "compositionMandates" in m),
        "compositionMandateMismatches": sum(
            1 for m in per_municipality if "compositionMandates" in m and m["compositionMandates"] != m["listMandatesTotal"]
        ),
        "seats": count_stats(elected),
    }
    details = {
        "perMunicipality": per_municipality,
        "councilNotInSitemap": council_not_in_sitemap,
        "municipalityMismatches": municipality_mismatches,
        "seatCountMismatches": seat_mismatches,
    }
    write_results(output_path, election_id, elected, stats, sources, details)
    return output_path, stats


def _name_tokens(name: str) -> tuple[str, ...]:
    return tuple(sorted(normalize_person_name(re.sub(r"\((?:MERAS|MERĖ)\)", "", name or "")).split()))


def _municipality_matches(sitemap_municipality: Any, results_label: str) -> bool:
    """'Akmenės rajono savivaldybė' (sitemap) vs '1. Akmenės rajono' (results)."""
    if not sitemap_municipality:
        return True
    left = normalize_person_name(re.sub(r"^\d+\.\s*", "", results_label))
    right = normalize_person_name(str(sitemap_municipality))
    return left in right or right in left
