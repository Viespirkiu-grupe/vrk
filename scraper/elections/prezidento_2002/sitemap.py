"""Listing walk of the December 2002 presidential election.

The 2002-12-22 presidential election (17 candidates; Rolandas Paksas
beat Valdas Adamkus in the January 5, 2003 runoff) is published on
VRK's 2002 site (``rinkimai/2002/Prezidentas/`` — capital P — the
LRS-ITD template one generation before the 2004 static site), held with
the municipal general on one day. Like 2004, one shared listing page of
profile cards, not a page per candidate; unlike 2004, most of the
per-candidate record is **scanned images**:

- the card: photo (``docs/<Name>_nuotrauka.jpg``), the candidate's name
  in a ``span.h*``, two ``<a name>`` anchors — the card's position and
  **VRK's candidate id** — and the registration sentence ("2002 m
  spalio 29 dienos VRK sprendimu Nr. 91 registruotas kandidatu…", the
  decision linked on lrs.lt; note "m" without the dot).
- parseable sub-pages: the biography as **HTML**
  (``docs/Biografijos/<Name>_biografija.htm``) and the programme as a
  Word 97 ``.doc`` (``docs/Programos/…``, read by
  ``scraper/shared/word_doc.py``).
- scans, kept as archived files and URLs — the era's paper forms
  photographed, which no honest OCR turns into corpus data: the
  pretender's statement (``_pareiskimas.jpg``), the two-page data
  questionnaire (``_anketa1/_anketa2.jpg``; Dagys's first page is
  ``_anketa.jpg``), the asset-and-income declaration
  (``_deklaracija.jpg`` — the link label states the form: "Šeimos" or
  "Gyventojo turto pajamų deklaracija") and, on five cards, the health
  certificate (Šerėnas's is two pages).
- the campaign site for eleven (V. A. Matulevičius's card links two).

The trustees index (``patiketiniai/kandidatu_patiketiniai.jsp-…``)
survives, but every per-candidate trustee page behind it is a 404 —
linked, never mirrored — so its value is the id mapping: each name
links ``asm_rduom_id=<RID>``, VRK's registration record id, the id
space the results pages key on (``rezkapgl.htm-<RID>+<round>.htm``).
The sitemap joins the two pages on the candidate's name (unique among
the 17 on both) so every entry carries both ids and the results join
stays exact.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper.elections.seimo_zirmunu_2015.sitemap import (
    normalize_space,
    resolve_candidate_url,
    utc_now_iso,
)
from scraper.shared.files import slugify, write_json
from scraper.shared.http import fetch_text
from scraper.shared.seimo_archive_1990s import BIOGRAPHY_MONTHS

ELECTION_ID = "2002-prezidento"
SITE_ROOT = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2002/Prezidentas/"
LISTING_URL = SITE_ROOT + "kandidatai.htm"
PATIKETINIAI_INDEX_URL = SITE_ROOT + "patiketiniai/kandidatu_patiketiniai.jsp-ri_id=14.htm"

LISTING_FILE_NAME = "list.html"
PATIKETINIAI_FILE_NAME = "patiketiniai-index.html"

BIOGRAFIJA_LINK_PATTERN = re.compile(r"/Biografijos/[^/]+\.htm$")
PROGRAMA_LINK_PATTERN = re.compile(r"/Programos/[^/]+\.doc$", re.IGNORECASE)
PAREISKIMAS_LINK_PATTERN = re.compile(r"_pareiskimas\.jpg$", re.IGNORECASE)
ANKETA_SCAN_LINK_PATTERN = re.compile(r"_anketa\d*\.jpg$", re.IGNORECASE)
DEKLARACIJA_LINK_PATTERN = re.compile(r"_deklaracija\.jpg$", re.IGNORECASE)
SVEIKATA_LINK_PATTERN = re.compile(r"_sveikata\d*\.jpg$", re.IGNORECASE)
PATIKETINIAI_LINK_PATTERN = re.compile(r"kandidato_patiketiniai\.jsp-ri_id=14&asm_rduom_id=(\d+)\.htm$")
DECISION_LINK_MARKER = "lrs.lt/cgi-bin"

# "2002 m spalio 29 dienos" — this era prints "m" without the dot.
REGISTRATION_DATE_PATTERN = re.compile(
    r"(\d{4})\s*m\.?\s*(" + "|".join(BIOGRAPHY_MONTHS) + r")\s*(\d{1,2})\s*dien",
    re.IGNORECASE,
)

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

__all__ = [
    "ELECTION_ID",
    "LISTING_URL",
    "PATIKETINIAI_INDEX_URL",
    "build_sitemap_from_sample",
    "extract_listing_entries",
    "extract_registration_ids",
    "fetch_listing_sample",
    "resolve_candidate_url",
]


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    samples_dir.mkdir(parents=True, exist_ok=True)
    listing_path = samples_dir / LISTING_FILE_NAME
    listing_path.write_text(fetch_text(LISTING_URL), encoding="utf-8")
    (samples_dir / PATIKETINIAI_FILE_NAME).write_text(
        fetch_text(PATIKETINIAI_INDEX_URL), encoding="utf-8"
    )
    return listing_path


def _card_lines(card: Tag) -> list[list[Any]]:
    """The card cell's children segmented at ``<br>`` into lines."""
    lines: list[list[Any]] = [[]]
    for node in card.children:
        if isinstance(node, Tag) and node.name == "br":
            lines.append([])
            continue
        lines[-1].append(node)
    return [line for line in lines if any(_node_text(node) or isinstance(node, Tag) for node in line)]


def _node_text(node: Any) -> str:
    if isinstance(node, NavigableString):
        return normalize_space(str(node))
    if isinstance(node, Tag):
        return normalize_space(node.get_text(" ", strip=True))
    return ""


def _line_text(line: list[Any]) -> str:
    return normalize_space(" ".join(filter(None, (_node_text(node) for node in line))))


def _line_anchors(line: list[Any]) -> list[Tag]:
    anchors: list[Tag] = []
    for node in line:
        if isinstance(node, Tag):
            if node.name == "a" and node.get("href"):
                anchors.append(node)
            else:
                anchors.extend(node.find_all("a", href=True))
    return anchors


def extract_listing_entries(listing_html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(listing_html, "lxml")
    entries: list[dict[str, Any]] = []
    for span in soup.find_all("span", class_=re.compile(r"^h\d?$")):
        card = span.find_parent("td")
        if card is None:
            continue
        row = card.find_parent("tr")
        name = normalize_space(span.get_text(" ", strip=True))
        # Two bare anchors precede the name: the card's position (one or
        # two digits) and VRK's candidate id (six).
        anchor_ids = [
            normalize_space(anchor["name"])
            for anchor in card.find_all("a", attrs={"name": True})
            if normalize_space(anchor.get("name", "")).isdigit()
        ]
        vrk_id = max(anchor_ids, key=len) if anchor_ids else ""

        entry: dict[str, Any] = {
            "candidateName": name,
            "candidateId": slugify(name),
            "vrkCandidateId": vrk_id,
            "url": LISTING_URL,
            "vrkRegistrationId": "",
            "patiketiniaiUrl": None,
            "registration": "",
            "registeredDate": None,
            "decision": None,
            "decisionUrl": None,
            "biografijaUrl": None,
            "programaUrl": None,
            "pareiskimasUrl": None,
            "anketosSkenaiUrls": [],
            "deklaracijaUrl": None,
            "deklaracijaLabel": None,
            "sveikatosSkenaiUrls": [],
            "photoUrl": None,
            "websiteUrls": [],
        }

        image = row.find("img") if row is not None else None
        if image is not None and image.get("src"):
            entry["photoUrl"] = resolve_candidate_url(normalize_space(image["src"]))

        for line in _card_lines(card):
            text = _line_text(line)
            anchors = _line_anchors(line)
            if "registruot" in text and REGISTRATION_DATE_PATTERN.search(text):
                entry["registration"] = text
                date_match = REGISTRATION_DATE_PATTERN.search(text)
                month = BIOGRAPHY_MONTHS[date_match.group(2).lower()]
                entry["registeredDate"] = f"{date_match.group(1)}-{month:02d}-{int(date_match.group(3)):02d}"
                for anchor in anchors:
                    if DECISION_LINK_MARKER in anchor["href"]:
                        entry["decision"] = normalize_space(anchor.get_text(" ", strip=True))
                        entry["decisionUrl"] = normalize_space(anchor["href"])
                continue
            for anchor in anchors:
                href = normalize_space(anchor["href"])
                if BIOGRAFIJA_LINK_PATTERN.search(href):
                    entry["biografijaUrl"] = resolve_candidate_url(href)
                elif PROGRAMA_LINK_PATTERN.search(href):
                    entry["programaUrl"] = resolve_candidate_url(href)
                elif PAREISKIMAS_LINK_PATTERN.search(href):
                    entry["pareiskimasUrl"] = resolve_candidate_url(href)
                elif ANKETA_SCAN_LINK_PATTERN.search(href):
                    entry["anketosSkenaiUrls"].append(resolve_candidate_url(href))
                elif DEKLARACIJA_LINK_PATTERN.search(href):
                    entry["deklaracijaUrl"] = resolve_candidate_url(href)
                    entry["deklaracijaLabel"] = normalize_space(anchor.get_text(" ", strip=True))
                elif SVEIKATA_LINK_PATTERN.search(href):
                    entry["sveikatosSkenaiUrls"].append(resolve_candidate_url(href))
                elif href.startswith("http") and DECISION_LINK_MARKER not in href:
                    entry["websiteUrls"].append(href)
        entries.append(entry)
    return entries


def extract_registration_ids(patiketiniai_html: str) -> dict[str, str]:
    """Candidate name → VRK registration record id, from the trustee
    index's per-candidate links (the pages themselves are 404)."""
    soup = BeautifulSoup(patiketiniai_html, "lxml")
    ids: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        match = PATIKETINIAI_LINK_PATTERN.search(anchor["href"])
        if match is None:
            continue
        name = normalize_space(anchor.get_text(" ", strip=True))
        if name:
            ids[name] = match.group(1)
    return ids


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    root = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    listing_path = root / LISTING_FILE_NAME if root.is_dir() else root
    entries = extract_listing_entries(listing_path.read_text(encoding="utf-8"))

    patiketiniai_path = listing_path.parent / PATIKETINIAI_FILE_NAME
    registration_ids = (
        extract_registration_ids(patiketiniai_path.read_text(encoding="utf-8"))
        if patiketiniai_path.exists()
        else {}
    )
    for entry in entries:
        rid = registration_ids.get(entry["candidateName"])
        if rid:
            entry["vrkRegistrationId"] = rid
            entry["patiketiniaiUrl"] = (
                SITE_ROOT + f"patiketiniai/kandidato_patiketiniai.jsp-ri_id=14&asm_rduom_id={rid}.htm"
            )

    problems: list[str] = []
    seen_ids: set[str] = set()
    for entry in entries:
        for key in (
            "vrkCandidateId", "vrkRegistrationId", "registeredDate", "decision",
            "biografijaUrl", "programaUrl", "pareiskimasUrl", "deklaracijaUrl", "photoUrl",
        ):
            if not entry[key]:
                problems.append(f"{entry['candidateId']}: no {key}")
        if len(entry["anketosSkenaiUrls"]) != 2:
            problems.append(f"{entry['candidateId']}: {len(entry['anketosSkenaiUrls'])} anketa scans")
        if entry["candidateId"] in seen_ids:
            problems.append(f"duplicate candidate id {entry['candidateId']}")
        seen_ids.add(entry["candidateId"])
    if len(registration_ids) != len(entries):
        problems.append(f"{len(registration_ids)} trustee-index names for {len(entries)} cards")
    if not entries:
        problems.append("no candidate cards found")
    if problems:
        raise ValueError("Listing did not parse cleanly: " + "; ".join(problems))

    payload = {
        "electionId": ELECTION_ID,
        "sourceUrl": LISTING_URL,
        "generatedAt": utc_now_iso(),
        # rows/extracted/skipped/duplicate_candidate_ids are the keys the
        # cli.py sitemap command reports; the reconcile above raises rather
        # than skipping, so the last two are zero by construction.
        "stats": {
            "rows": len(entries),
            "extracted": len(entries),
            "skipped": 0,
            "duplicate_candidate_ids": 0,
            "withSveikata": sum(1 for entry in entries if entry["sveikatosSkenaiUrls"]),
            "withWebsite": sum(1 for entry in entries if entry["websiteUrls"]),
        },
        "entries": entries,
    }
    write_json(output_path, payload)
    return output_path, dict(payload["stats"])
