"""Shared parsing for the 1997 archived municipal-council election pages.

VRK's 1997 municipal-council election pages live under the static-HTML
directory `19970323` -- the same directory hosts both the 1997-03-23 general
election (candidate lists filed under phase prefix `3`, e.g.
`apgtl.htm-3+47.htm`) and the 1997-06-29 Švenčionys repeat election (phase
prefix `5`, `apgtl.htm-5+47.htm`): same municipality, same page layout,
different filing dates on the party-list rows, confirmed by diffing the two
pages for Švenčionys. Elections built on this module supply the phase prefix
and municipality numbers explicitly; nothing here is hardcoded to one
election.

Unlike the Seimas archive (`scraper/shared/seimo_archive_1990s.py`), listing
candidates here is a *three*-hop crawl, and no single-mandate table exists:

    apgtl.htm  (municipality)   -- table of parties/coalitions, one row per
                                    list, linking to that list's candidates
    pkal.htm   (party list)     -- numbered candidates for one party in one
                                    municipality
    kandvl.htm (candidate)      -- full candidate detail

The candidate detail page is uncorrupted (no malformed-comment quirk here)
and considerably richer than the Seimas family's: birth date/place,
residence, nationality, education, foreign languages, main workplace, public
activity, family status and family members are all present as plain labelled
paragraphs. The income declaration (`kpdl.htm`) is fetched alongside and read
by `scraper/shared/deklaracija_archive_1990s.py`, shared with the Seimas
archive family. Note that this election's declaration pages are the ones whose
section III total renders 0 against a non-zero row 1 -- see that module for
the measurement and for what is published instead.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.shared.anomalies import build_anomaly_event
from scraper.shared.archive_1990s_card import (
    PREVIOUSLY_ELECTED_LABEL,
    FIELD_LABELS as CARD_FIELD_LABELS,
    bold_values,
    education_record,
    family_concepts,
    family_members,
    field_value,
    previously_elected_record,
)
from scraper.shared.deklaracija_archive_1990s import parse_declaration
from scraper.shared.files import slugify, write_candidate_record, write_json
from scraper.shared.http import fetch_text
from scraper.shared.savivaldybiu_archive_1997_results import (
    apply_municipal_results,
    load_municipal_results,
)
from scraper.shared.seimo_archive_1990s_results import candidate_id_from_url

VRK_STATINIAI_BASE = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/19970323/"

# Pause between page fetches during listing/candidate discovery. The full
# municipal general election is thousands of pages, so this stays polite.
FETCH_DELAY_SECONDS = 0.2

MUNICIPALITY_NUMBER_PATTERN = re.compile(r"\(Nr\.\s*(\d+)\)")
MUNICIPALITY_URL_NUMBER_PATTERN = re.compile(r"apgtl\.htm-\d+\+(\d+)\.htm")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def _clean_text(value: str) -> str:
    return normalize_space(value)


def municipality_url(phase: str, municipality: int) -> str:
    return f"{VRK_STATINIAI_BASE}apgtl.htm-{phase}+{municipality}.htm"


def parse_municipality_directory(html: str, source_url: str) -> list[dict[str, Any]]:
    """Parse an apgsavl.htm directory page: every municipality's name and its
    apgtl.htm link. Used by the general election, which crawls the whole
    country; the Švenčionys repeat instead hardcodes its one municipality,
    since no directory page covers only it."""
    soup = BeautifulSoup(html, "lxml")
    entries: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()
    for anchor in soup.find_all("a", href=True):
        number_match = MUNICIPALITY_URL_NUMBER_PATTERN.search(anchor["href"])
        if number_match is None:
            continue
        municipality_number = int(number_match.group(1))
        if municipality_number in seen_numbers:
            continue
        name = _clean_text(anchor.get_text(" ", strip=True))
        if not name:
            continue
        seen_numbers.add(municipality_number)
        entries.append(
            {
                "municipalityName": name,
                "municipalityNumber": municipality_number,
                "url": urljoin(source_url, anchor["href"]),
            }
        )
    return entries


def parse_municipality_page(html: str, source_url: str) -> dict[str, Any]:
    """Parse one apgtl.htm municipality page: name/number/mandate count plus
    the parties/coalitions fielding candidates there (each linking one hop
    deeper to its pkal.htm candidate list)."""
    soup = BeautifulSoup(html, "lxml")

    heading = ""
    for font in soup.find_all("font", attrs={"size": "5"}):
        text = _clean_text(font.get_text(" ", strip=True))
        if "apygarda" in text.lower():
            heading = text
            break

    number_match = MUNICIPALITY_NUMBER_PATTERN.search(heading)
    municipality_number = int(number_match.group(1)) if number_match else None
    municipality_name = re.sub(
        r"\s*\(Nr\.\s*\d+\)\s*apygarda\s*$", "", heading, flags=re.IGNORECASE
    ).strip()

    mandate_count = None
    mandate_match = re.search(r"Mandatų\s+skaičius:\s*(\d+)", soup.get_text(" ", strip=True))
    if mandate_match:
        mandate_count = int(mandate_match.group(1))

    table = None
    for candidate_table in soup.find_all("table"):
        header_text = _clean_text(candidate_table.get_text(" ", strip=True))
        if "Sąrašo" in header_text and ("Partija" in header_text or "koalicija" in header_text):
            table = candidate_table
            break

    parties: list[dict[str, Any]] = []
    if table is not None:
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            list_number_text = _clean_text(cells[0].get_text(" ", strip=True)).rstrip(".")
            list_number = int(list_number_text) if list_number_text.isdigit() else None
            party_link = cells[1].find("a", href=True)
            if party_link is None:
                continue
            party_name = _clean_text(party_link.get_text(" ", strip=True))
            if not party_name:
                continue
            parties.append(
                {
                    "listNumber": list_number,
                    "partyName": party_name,
                    "url": urljoin(source_url, party_link["href"]),
                }
            )

    return {
        "municipalityName": municipality_name,
        "municipalityNumber": municipality_number,
        "mandateCount": mandate_count,
        "sourceUrl": source_url,
        "parties": parties,
    }


def parse_party_candidates_page(html: str, source_url: str) -> list[dict[str, Any]]:
    """Parse one pkal.htm party-list page: the numbered candidates that party
    fields in that municipality."""
    soup = BeautifulSoup(html, "lxml")

    table = None
    for candidate_table in soup.find_all("table"):
        header_text = _clean_text(candidate_table.get_text(" ", strip=True))
        if "Numeris" in header_text and "Pavard" in header_text:
            table = candidate_table
            break

    candidates: list[dict[str, Any]] = []
    if table is not None:
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            list_number_text = _clean_text(cells[0].get_text(" ", strip=True)).rstrip(".")
            list_number = int(list_number_text) if list_number_text.isdigit() else None
            name_link = cells[1].find("a", href=True)
            if name_link is None:
                continue
            candidate_name = _clean_text(name_link.get_text(" ", strip=True))
            if not candidate_name:
                continue
            candidates.append(
                {
                    "listNumber": list_number,
                    "candidateName": candidate_name,
                    "url": urljoin(source_url, name_link["href"]),
                }
            )
    return candidates


BIRTH_DATE_PATTERN = re.compile(r"^(\d{4})[\s.\-/](\d{1,2})[\s.\-/](\d{1,2})$")

# The label list and the stop-list reader moved to
# `scraper/shared/archive_1990s_card.py` when the Seimas archive family
# started reading the same card (issue #69); it carries the union of both
# cards' labels and the comment recording why the stop list has to name every
# one of them. Re-exported here under their old names so existing callers and
# tests are unaffected.
FIELD_LABELS = CARD_FIELD_LABELS
_field = field_value


def normalize_birth_date(value: str) -> str:
    """`1945 04 17` -> `1945-04-17`, the ISO-ish form every era from 2015 on
    writes into `anketa.gimimo-data`. Without this the cross-election person
    index keys on `NAME|1945 04 17` and can never match `NAME|1945-04-17`,
    so a person appearing here and in a later election stays split in two.
    Anything that is not a plain Y/M/D triple is returned unchanged."""
    match = BIRTH_DATE_PATTERN.match(value.strip())
    if not match:
        return value.strip()
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def parse_candidate_detail(html: str, source_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    name = ""
    name_font = soup.select_one("font[size='5']")
    if name_font is not None:
        name = _clean_text(name_font.get_text(" ", strip=True))

    income_declaration_url = ""
    for anchor in soup.find_all("a", href=True):
        if "eklaracija" in _clean_text(anchor.get_text()):
            income_declaration_url = urljoin(source_url, anchor["href"])
            break

    paragraphs = soup.find_all("p")

    candidacy = {
        "municipalityName": "",
        "municipalityNumber": None,
        "municipalityUrl": "",
        "nominator": "",
        "nominatorUrl": "",
        "listNumber": None,
    }
    personal: dict[str, Any] = {
        "birthDate": "",
        "birthPlace": "",
        "residence": "",
        "nationality": "",
        "education": "",
        "foreignLanguages": [],
        "mainWorkplace": "",
        "publicActivity": "",
        "familyStatus": "",
        "familyMembers": [],
        # Absent from the label list until 2026-08-26 (issue #69), so this
        # card's academic degree and title were never read: 156 and 112 of
        # them in the 1997 general election, none in the Švenčionys repeat.
        # `previouslyElected` and `aboutSelf` are the Seimas card's labels --
        # no municipal page prints either (0 of 6,380) -- and are read here
        # only so the two families share one reader.
        "academicDegree": "",
        "academicTitle": "",
        "previouslyElected": [],
        "aboutSelf": "",
    }

    for paragraph in paragraphs:
        plain = _clean_text(paragraph.get_text(" ", strip=True))
        raw = str(paragraph)

        if plain.startswith("Apygarda:"):
            municipality_match = re.search(r"Apygarda:\s*(.*?)\s*Iškėlė:", plain)
            municipality_full = municipality_match.group(1).strip() if municipality_match else ""
            number_match = MUNICIPALITY_NUMBER_PATTERN.search(municipality_full)
            candidacy["municipalityNumber"] = int(number_match.group(1)) if number_match else None
            candidacy["municipalityName"] = re.sub(
                r"\s*\(Nr\.\s*\d+\)\s*$", "", municipality_full
            ).strip()
            candidacy["nominator"] = _field(plain, "Iškėlė")
            list_match = re.search(r"Numeris sąraše:\s*(\d+)", plain)
            candidacy["listNumber"] = int(list_match.group(1)) if list_match else None

            split_idx = raw.find("Iškėlė")
            before_html = raw[:split_idx] if split_idx >= 0 else raw
            after_html = raw[split_idx:] if split_idx >= 0 else ""
            match = re.search(r'href="([^"]+)"', before_html)
            if match:
                candidacy["municipalityUrl"] = urljoin(source_url, match.group(1))
            match = re.search(r'href="([^"]+)"', after_html)
            if match:
                candidacy["nominatorUrl"] = urljoin(source_url, match.group(1))

        elif plain.startswith("Gimimo data:"):
            personal["birthDate"] = normalize_birth_date(_field(plain, "Gimimo data"))
            personal["birthPlace"] = _field(plain, "Gimimo vieta")
            personal["residence"] = _field(plain, "Gyvenamoji vieta")
            personal["nationality"] = _field(plain, "Tautybė")

        elif plain.startswith("Išsilavinimas:"):
            personal["education"] = _field(plain, "Išsilavinimas")

        elif plain.startswith("Užsienio kalbos:"):
            personal["foreignLanguages"] = [
                _clean_text(tag.get_text(" ", strip=True)) for tag in paragraph.find_all("b")
            ]

        elif plain.startswith("Pagrindinė darbovietė:"):
            personal["mainWorkplace"] = _field(plain, "Pagrindinė darbovietė")

        elif plain.startswith("Visuomeninė veikla:"):
            personal["publicActivity"] = _field(plain, "Visuomeninė veikla")

        elif plain.startswith("Šeimyninė padėtis:"):
            personal["familyStatus"] = _field(plain, "Šeimyninė padėtis")

        elif plain.startswith("Šeimos nariai:"):
            personal["familyMembers"] = family_members(paragraph)

        elif plain.startswith("Moksliniai laipsniai:"):
            personal["academicDegree"] = _field(plain, "Moksliniai laipsniai")

        elif plain.startswith("Moksliniai vardai:"):
            personal["academicTitle"] = _field(plain, "Moksliniai vardai")

        elif plain.startswith(PREVIOUSLY_ELECTED_LABEL):
            # "Buvo išrinktas į Lietuvos Respublikos Aukščiausiąją Tarybą,
            # Seimą, savivaldybių tarybas:" -- one <b> per body, so the value
            # is a list rather than the one string _field would return.
            personal["previouslyElected"] = [
                item["value"] for item in bold_values(paragraph)
            ]

        elif plain.startswith("Ką dar norėtų parašyti apie save:"):
            personal["aboutSelf"] = _field(plain, "Ką dar norėtų parašyti apie save")

    return {
        "candidateDisplayName": name,
        "incomeDeclarationUrl": income_declaration_url,
        "candidacy": candidacy,
        "personal": personal,
    }


def fetch_municipality_samples(
    targets: list[dict[str, Any]],
    samples_dir: Path,
    delay_seconds: float = FETCH_DELAY_SECONDS,
) -> list[Path]:
    """Fetch and save every target municipality's apgtl.htm page.

    `targets` is a list of `{"url": str, "municipality": int}` supplied by
    the calling election module -- either the full set read back from a
    directory sample, or the handful (often one) VRK names in a by-election
    announcement.
    """
    samples_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    for target in targets:
        municipality = target["municipality"]
        sample_path = samples_dir / f"apgtl-{municipality}.html"
        if sample_path.exists():
            saved_paths.append(sample_path)
            continue
        html = fetch_text(target["url"])
        sample_path.write_text(html, encoding="utf-8")
        saved_paths.append(sample_path)
        time.sleep(delay_seconds)
    return saved_paths


def fetch_party_list_samples(
    municipality_sample_paths: list[Path],
    lists_dir: Path,
    delay_seconds: float = FETCH_DELAY_SECONDS,
) -> list[Path]:
    """For every saved municipality page, fetch and save every party's
    pkal.htm candidate-list page."""
    lists_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    for municipality_sample_path in municipality_sample_paths:
        html = municipality_sample_path.read_text(encoding="utf-8")
        page = parse_municipality_page(html, source_url=VRK_STATINIAI_BASE)
        for party in page["parties"]:
            file_name = f"pkal-{page['municipalityNumber']}-{party['listNumber']}.html"
            sample_path = lists_dir / file_name
            if sample_path.exists():
                saved_paths.append(sample_path)
                continue
            party_html = fetch_text(party["url"])
            sample_path.write_text(party_html, encoding="utf-8")
            saved_paths.append(sample_path)
            time.sleep(delay_seconds)
    return saved_paths


def build_sitemap_from_samples(
    municipality_sample_paths: list[Path],
    lists_dir: Path,
    output_path: Path,
    election_id: str,
    source_description: str,
) -> tuple[Path, dict[str, int]]:
    entries: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    party_count = 0
    missing_list_samples = 0

    for municipality_sample_path in municipality_sample_paths:
        municipality_html = municipality_sample_path.read_text(encoding="utf-8")
        municipality_page = parse_municipality_page(municipality_html, source_url=VRK_STATINIAI_BASE)

        for party in municipality_page["parties"]:
            party_count += 1
            file_name = f"pkal-{municipality_page['municipalityNumber']}-{party['listNumber']}.html"
            list_sample_path = lists_dir / file_name
            if not list_sample_path.exists():
                missing_list_samples += 1
                continue
            list_html = list_sample_path.read_text(encoding="utf-8")
            candidates = parse_party_candidates_page(list_html, source_url=VRK_STATINIAI_BASE)

            for candidate in candidates:
                base_id = slugify(candidate["candidateName"])
                seen_ids[base_id] = seen_ids.get(base_id, 0) + 1
                candidate_id = base_id
                if seen_ids[base_id] > 1:
                    candidate_id = f"{base_id}-{seen_ids[base_id]}"
                entries.append(
                    {
                        "candidateName": candidate["candidateName"],
                        "candidateId": candidate_id,
                        "url": candidate["url"],
                        "municipalityName": municipality_page["municipalityName"],
                        "municipalityNumber": municipality_page["municipalityNumber"],
                        "listNumber": candidate["listNumber"],
                        "nominator": party["partyName"],
                        "nominatorUrl": party["url"],
                    }
                )

    duplicate_candidate_ids = sum(1 for count in seen_ids.values() if count > 1)

    payload = {
        "electionId": election_id,
        "sourceDescription": source_description,
        "generatedAt": utc_now_iso(),
        "stats": {
            "municipalities": len(municipality_sample_paths),
            "partyLists": party_count,
            "missingPartyListSamples": missing_list_samples,
            "candidates": len(entries),
            "duplicateCandidateIds": duplicate_candidate_ids,
        },
        "entries": entries,
    }
    write_json(output_path, payload)
    # cli.py's generic `sitemap` command printing was written against the
    # tabbed elections' row/extracted/skipped/duplicate shape; a "row" here
    # is a party list, "skipped" is a party list whose pkal.htm sample was
    # never fetched (so its candidates cannot be in this sitemap yet).
    return output_path, {
        "rows": party_count,
        "extracted": len(entries),
        "skipped": missing_list_samples,
        "duplicate_candidate_ids": duplicate_candidate_ids,
    }


def fetch_listing_sample_for_targets(
    targets: list[dict[str, Any]],
    sample_path: Path,
    municipalities_dir: Path,
    lists_dir: Path,
) -> Path:
    """For a repeat election that targets a small, explicitly-known set of
    municipalities (no directory page covers only them): fetch each
    municipality page, then every party list on it, and write a small
    manifest at `sample_path` recording what was targeted, so `fetch-sample`
    still has a single path to report."""
    municipality_sample_paths = fetch_municipality_samples(targets, municipalities_dir)
    fetch_party_list_samples(municipality_sample_paths, lists_dir)
    write_json(sample_path, {"targets": targets})
    return sample_path


def build_sitemap_from_target_samples(
    municipalities_dir: Path,
    lists_dir: Path,
    output_path: Path,
    election_id: str,
    source_description: str,
) -> tuple[Path, dict[str, int]]:
    sample_paths = sorted(
        municipalities_dir.glob("apgtl-*.html"),
        key=lambda p: int(p.stem.split("-")[1]),
    )
    if not sample_paths:
        raise ValueError(f"No municipality samples found under {municipalities_dir}. Run fetch-sample first.")
    return build_sitemap_from_samples(
        sample_paths, lists_dir, output_path, election_id=election_id, source_description=source_description
    )


def _load_sitemap_entries(sitemap_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(sitemap_path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"No sitemap entries found in {sitemap_path}")
    return entries


def _load_sitemap_entries_by_candidate_id(sitemap_path: Path) -> dict[str, dict[str, Any]]:
    return {entry["candidateId"]: entry for entry in _load_sitemap_entries(sitemap_path)}


def fetch_candidate_sample(
    entry: dict[str, Any],
    samples_root: Path,
    allow_new_candidate_dir: bool,
    election_id: str = "",
) -> dict[str, Any]:
    """Fetch and save one candidate's kandvl.htm page and its declaration.

    There is no tab navigation on these pages (unlike every 2016+ election)
    and no separate biography page (unlike the Seimas 1996-1998 family), so
    the "tab" count below is the candidate page plus the `kpdl.htm`
    declaration where the page links one -- an analogue of the tabbed
    modules' count, kept so `cli.py`'s generic fetch-sample printing still
    has the fields it expects.
    """
    candidate_dir = samples_root / entry["candidateId"]
    if not candidate_dir.exists() and not allow_new_candidate_dir:
        raise ValueError(
            f"Refusing to create new sample candidate directory {candidate_dir}. "
            "Samples are fixture-only by default. Pass --allow-new-samples to "
            "enable one-time fixture capture."
        )
    candidate_dir.mkdir(parents=True, exist_ok=True)

    candidate_html = fetch_text(entry["url"])
    candidate_path = candidate_dir / "candidate.html"
    candidate_path.write_text(candidate_html, encoding="utf-8")

    detail = parse_candidate_detail(candidate_html, entry["url"])
    tab_count = 1
    tabs_saved = 1
    anomalies: list[dict[str, Any]] = []
    if detail["incomeDeclarationUrl"]:
        tab_count += 1
        try:
            (candidate_dir / "declaration.html").write_text(
                fetch_text(detail["incomeDeclarationUrl"]), encoding="utf-8"
            )
            tabs_saved += 1
        except Exception as exc:  # noqa: BLE001 - recorded as an anomaly, not fatal
            anomalies.append(
                build_anomaly_event(
                    event_type="DeclarationFetchFailed",
                    severity="error",
                    stage="fetch",
                    election_id=election_id,
                    candidate_id=entry["candidateId"],
                    source_url=entry["url"],
                    detail={"url": detail["incomeDeclarationUrl"], "error": str(exc)},
                )
            )

    index_path = candidate_dir / "index.json"
    index_payload = {
        "candidate": entry,
        "anketaPath": str(candidate_path),
        "tabCount": tab_count,
        "tabsSaved": tabs_saved,
        "anomalies": anomalies,
    }
    write_json(index_path, index_payload)

    return {
        "candidate": entry,
        "candidate_dir": candidate_dir,
        "anketa_path": candidate_path,
        "tab_count": tab_count,
        "tabs_saved": tabs_saved,
        "missing_expected_tabs": [],
        "anomalies": anomalies,
        "index_path": index_path,
    }


def fetch_candidates_samples(
    candidate_ids: list[str],
    sitemap_path: Path,
    samples_root: Path,
    allow_new_candidate_dir: bool = False,
    election_id: str = "",
) -> dict[str, Any]:
    if not candidate_ids:
        raise ValueError("At least one candidate id must be provided")
    entries_by_id = _load_sitemap_entries_by_candidate_id(sitemap_path)
    missing_ids = [cid for cid in candidate_ids if cid not in entries_by_id]
    if missing_ids:
        raise ValueError("Candidate IDs not found in sitemap: " + ", ".join(sorted(set(missing_ids))))

    results = [
        fetch_candidate_sample(entries_by_id[candidate_id], samples_root, allow_new_candidate_dir, election_id)
        for candidate_id in candidate_ids
    ]
    return {"count": len(results), "results": results}


def fetch_first_candidate_sample(
    sitemap_path: Path,
    samples_root: Path,
    allow_new_candidate_dir: bool = False,
    election_id: str = "",
) -> dict[str, Any]:
    entry = _load_sitemap_entries(sitemap_path)[0]
    return fetch_candidate_sample(entry, samples_root, allow_new_candidate_dir, election_id)


def card_anketa(personal: dict[str, Any]) -> dict[str, Any]:
    """The `normalized.anketa` block for one parsed card.

    Its own function so `scripts/backfill_1997_card_fields.py` can rebuild an
    already-stored record's anketa through exactly this code -- that script
    exists because the general election's retained samples hold no
    declaration pages, so it must patch records in place rather than re-parse
    them.

    The per-candidate facts live under `anketa` with the corpus's kebab-case
    concept keys -- `gimimo-data`, `issilavinimas`, `uzsienio-kalbos`,
    `pagrindine-darboviete`, `seimine-padetis` and the rest are the same names
    the 2015 and 2016 eras use, so docs/concept-map.json, the dashboard's
    field map and scripts/build_person_index.py all resolve them with no
    election-specific special case. (The source page's label reads "Šeimyninė
    padėtis"; the corpus concept key is `seimine-padetis`, so that is what is
    written here.)
    """
    # `sutuoktinio-vardas-pavarde` and `vaiku-vardai-pavardes` are the two
    # family-member roles the corpus keys separately; the rest of the list
    # (two "Augintinis (ė)", two "Anūkas (ė)" across the whole archive era)
    # belongs to neither and stays in `seimos-nariai` only.
    spouse, children = family_concepts(personal["familyMembers"])
    return {
        "gimimo-data": personal["birthDate"] or None,
        "gimimo-vieta": personal["birthPlace"] or None,
        "gyvenamoji-vieta": personal["residence"] or None,
        "tautybe": personal["nationality"] or None,
        "issilavinimas": education_record(personal["education"]),
        "mokslo-laipsnis": personal["academicDegree"] or None,
        "pedagoginis-vardas": personal["academicTitle"] or None,
        "uzsienio-kalbos": personal["foreignLanguages"],
        "anksciau-isrinktas": previously_elected_record(personal["previouslyElected"]),
        "pagrindine-darboviete": personal["mainWorkplace"] or None,
        "visuomenine-veikla": personal["publicActivity"] or None,
        "kita-apie-save": personal["aboutSelf"] or None,
        "seimine-padetis": personal["familyStatus"] or None,
        "sutuoktinio-vardas-pavarde": spouse,
        "vaiku-vardai-pavardes": children,
        "seimos-nariai": personal["familyMembers"],
    }


def build_candidate_record(
    candidate_id: str,
    entry: dict[str, Any],
    samples_root: Path,
    election_id: str,
    results: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidate_dir = samples_root / candidate_id
    candidate_html = (candidate_dir / "candidate.html").read_text(encoding="utf-8")
    detail = parse_candidate_detail(candidate_html, entry["url"])

    anomalies: list[dict[str, Any]] = []

    declaration: dict[str, Any] | None = None
    declaration_path = candidate_dir / "declaration.html"
    if detail["incomeDeclarationUrl"]:
        if declaration_path.exists():
            parsed = parse_declaration(declaration_path.read_text(encoding="utf-8"))
            declaration = parsed["declaration"]
            for event in parsed["anomalies"]:
                anomalies.append(
                    build_anomaly_event(
                        event_type=event["eventType"],
                        severity=event["severity"],
                        stage="parse",
                        election_id=election_id,
                        candidate_id=candidate_id,
                        source_url=detail["incomeDeclarationUrl"],
                        detail=event["detail"],
                    )
                )
        else:
            anomalies.append(
                build_anomaly_event(
                    event_type="DeclarationSampleMissing",
                    severity="warning",
                    stage="parse",
                    election_id=election_id,
                    candidate_id=candidate_id,
                    source_url=entry["url"],
                    detail={"incomeDeclarationUrl": detail["incomeDeclarationUrl"]},
                )
            )

    if not detail["candidacy"]["municipalityName"]:
        anomalies.append(
            build_anomaly_event(
                event_type="NoCandidacyFound",
                severity="error",
                stage="parse",
                election_id=election_id,
                candidate_id=candidate_id,
                source_url=entry["url"],
            )
        )
    if not detail["personal"]["residence"]:
        anomalies.append(
            build_anomaly_event(
                event_type="ResidenceMissing",
                severity="warning",
                stage="parse",
                election_id=election_id,
                candidate_id=candidate_id,
                source_url=entry["url"],
            )
        )

    personal = detail["personal"]
    candidacy = detail["candidacy"]

    raw_data = {
        "profile": {
            "candidateDisplayName": detail["candidateDisplayName"],
            "incomeDeclarationUrl": detail["incomeDeclarationUrl"],
        },
        "candidacy": candidacy,
        "personal": personal,
        "declaration": declaration,
    }

    normalized = {
        "profilis": {
            "vardas-pavarde": detail["candidateDisplayName"],
            "pajamu-deklaracijos-nuoroda": detail["incomeDeclarationUrl"] or None,
        },
        "kandidatavimas": {
            "savivaldybe": candidacy["municipalityName"],
            "savivaldybes-numeris": candidacy["municipalityNumber"],
            "savivaldybes-nuoroda": candidacy["municipalityUrl"] or None,
            "iskele": candidacy["nominator"],
            "iskele-nuoroda": candidacy["nominatorUrl"] or None,
            "numeris-sarase": candidacy["listNumber"],
        },
        "anketa": card_anketa(personal),
        # Same key the whole corpus declares under, so the person index,
        # concept map and dashboard need no special case for this era.
        **({"turto-ir-pajamu-deklaracijos": declaration} if declaration else {}),
    }

    # Elected status, joined in from VRK's per-municipality results pages
    # when `python -m scraper build-results <id>` has written the election's
    # results file (issue #92). Without one the candidacy keeps its old shape
    # and says nothing about the outcome, rather than claiming a false; with
    # one, `isrinktas` is a read verdict on both sides -- the elected pages
    # name every seat, and the one municipality without them (the voided
    # March Švenčionys result) is a `false` by VRK's own decision, carried
    # under `rezultatai-negalioja`.
    for problem in apply_municipal_results(
        normalized["kandidatavimas"],
        candidate_id_from_url(entry["url"]),
        results or {},
    ):
        anomalies.append(
            build_anomaly_event(
                event_type=problem["eventType"],
                severity="warning",
                stage="parse",
                election_id=election_id,
                candidate_id=candidate_id,
                source_url=entry["url"],
                detail=problem["detail"],
            )
        )

    # Same as the Seimas archive: the party-list page prints the name
    # surname-first ("Laužadis Šarūnas") while the candidate page heading
    # prints it given-name-first ("Šarūnas Laužadis"), which is the order the
    # rest of the corpus uses. Prefer the page heading; the listing form stays
    # in rawData, and candidateId is untouched.
    record = {
        "electionId": election_id,
        "candidateId": candidate_id,
        "candidateName": detail["candidateDisplayName"] or entry["candidateName"],
        "source": {"candidateSourceUrl": entry["url"]},
        "rawData": raw_data,
        "normalized": normalized,
    }
    return record, anomalies


def parse_anketa_samples(
    election_id: str,
    candidate_ids: list[str] | None,
    sitemap_path: Path,
    samples_root: Path,
    output_root: Path,
    results_path: Path | None = None,
) -> list[dict[str, Any]]:
    # anomalies.jsonl is written by cli.py's generic parse-anketa-samples
    # handler (same as every other election module) from the `anomalies` key
    # in each returned result, not here.
    entries_by_id = _load_sitemap_entries_by_candidate_id(sitemap_path)
    results_data = load_municipal_results(results_path)

    if candidate_ids:
        target_ids = candidate_ids
    else:
        target_ids = sorted(
            child.name
            for child in samples_root.iterdir()
            if child.is_dir() and (child / "candidate.html").exists()
        )

    results: list[dict[str, Any]] = []
    for candidate_id in target_ids:
        entry = entries_by_id.get(candidate_id)
        if entry is None:
            raise ValueError(f"Candidate id not found in sitemap: {candidate_id}")
        record, anomalies = build_candidate_record(
            candidate_id, entry, samples_root, election_id, results_data
        )
        output_path = output_root / f"{candidate_id}-{election_id}.json"
        write_candidate_record(output_path, record)

        # No anketa question rows exist on these pages; "rows" here are the
        # scalar identity/candidacy/personal fields, so cli.py's generic
        # row-count print line still means something rather than a stub 0/0.
        personal = record["rawData"]["personal"]
        scalar_fields = [
            record["rawData"]["profile"]["candidateDisplayName"],
            record["rawData"]["candidacy"]["nominator"],
            personal["birthDate"],
            personal["birthPlace"],
            personal["residence"],
            personal["nationality"],
            personal["education"],
            personal["mainWorkplace"],
            personal["publicActivity"],
            personal["familyStatus"],
        ]
        row_count = len(scalar_fields)
        answered_row_count = sum(1 for value in scalar_fields if value)

        results.append(
            {
                "candidateId": candidate_id,
                "candidateName": record["candidateName"],
                "outputPath": str(output_path),
                "rowCount": row_count,
                "answeredRowCount": answered_row_count,
                "anomalies": anomalies,
            }
        )

    return results
