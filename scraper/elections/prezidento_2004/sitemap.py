"""Listing walk of the June 2004 presidential election.

The election — called early after the April 2004 impeachment, held with
the EP election on one day, won by Valdas Adamkus in the June 27 runoff —
is the third member of the 2004 static site family (``rinkimai/2004/
prezidentas/``, the LRS-ITD template of ``ep_2004`` and ``seimo_2004``),
but its candidate publication is one shared page, not a page per person:
``kandidatai_l_19.htm`` lists the five candidates as profile cards, and
each card links the candidate's set —

- ``kand_pajam_l_<ID>.htm`` — the income-and-asset declaration extracts,
  the family's usual page, and the card's only per-candidate HTML. Its
  ``<ID>`` is the card's own anchor (``<a name>``), the id the corpus
  keys on.
- ``patiketiniai_l_<RID>.htm`` — the trustees, under a second id space:
  VRK's registration record id, which the results tree reuses as
  ``rez_kand_l_<RID>_…``. The page itself is a 404 for all five (linked,
  never published — the 2009 presidential trustees again), so the link's
  value is the id mapping, and the results join needs no name matching.
- ``Biografija`` and ``Programa`` — Word 97 ``.doc`` documents, the only
  corpus source published as documents rather than pages
  (``scraper/shared/word_doc.py`` reads them). Auštrevičius published no
  programme.
- ``Pareiškimas`` and ``Sveikatos pažymėjimas`` — scanned GIFs (the
  health certificate is Adamkus's card only), kept as URLs.
- the photo (a thumbnail on the card, the full portrait behind
  ``nuotrauka_<ID>.htm``) and, for four of five, the campaign site.

The card's sentence — "2004 m. gegužės 12 dienos VRK sprendimu Nr. 120
registruotas kandidatu…" — is the registration fact, with the decision
linked on lrs.lt.
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

ELECTION_ID = "2004-prezidento"
LISTING_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2004/prezidentas/kandidatai/kandidatai_l_19.htm"

LISTING_FILE_NAME = "list.html"

DEKLARACIJA_LINK_PATTERN = re.compile(r"kand_pajam_l_(\d+)\.htm$")
PATIKETINIAI_LINK_PATTERN = re.compile(r"patiketiniai_l_(\d+)\.htm$")
NUOTRAUKA_LINK_PATTERN = re.compile(r"nuotrauka_(\d+)\.htm$")
DOC_LINK_PATTERN = re.compile(r"\.doc$", re.IGNORECASE)
GIF_LINK_PATTERN = re.compile(r"\.gif$", re.IGNORECASE)
DECISION_LINK_MARKER = "lrs.lt/cgi-bin"

REGISTRATION_DATE_PATTERN = re.compile(
    r"(\d{4})\s*m\.\s*(" + "|".join(BIOGRAPHY_MONTHS) + r")\s*(\d{1,2})\s*dien",
    re.IGNORECASE,
)

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

__all__ = [
    "ELECTION_ID",
    "LISTING_URL",
    "build_sitemap_from_sample",
    "extract_listing_entries",
    "fetch_listing_sample",
    "resolve_candidate_url",
]


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    samples_dir.mkdir(parents=True, exist_ok=True)
    listing_path = samples_dir / LISTING_FILE_NAME
    listing_path.write_text(fetch_text(LISTING_URL), encoding="utf-8")
    return listing_path


def _card_rows(soup: BeautifulSoup) -> list[Tag]:
    """The candidate rows: each holds the photo cell and the ``div.kand``
    card cell. The heading row and the layout tables around them do not."""
    return [
        holder.find_parent("tr")
        for holder in soup.find_all("div", class_="kand")
        if holder.find_parent("tr") is not None
    ]


def _registration_facts(card: Tag) -> dict[str, Any]:
    """The card's registration sentence, date and linked VRK decision."""
    fragments: list[str] = []
    decision = ""
    decision_url = ""
    for node in card.children:
        if isinstance(node, NavigableString):
            fragments.append(str(node))
            continue
        if not isinstance(node, Tag):
            continue
        if node.name == "br":
            break
        if node.name == "a" and DECISION_LINK_MARKER in (node.get("href") or ""):
            decision = normalize_space(node.get_text(" ", strip=True))
            decision_url = normalize_space(node["href"])
            fragments.append(decision)
    sentence = normalize_space(" ".join(fragments))
    date_match = REGISTRATION_DATE_PATTERN.search(sentence)
    registered = None
    if date_match is not None:
        month = BIOGRAPHY_MONTHS[date_match.group(2).lower()]
        registered = f"{date_match.group(1)}-{month:02d}-{int(date_match.group(3)):02d}"
    return {
        "registration": sentence,
        "registeredDate": registered,
        "decision": decision or None,
        "decisionUrl": decision_url or None,
    }


def extract_listing_entries(listing_html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(listing_html, "lxml")
    entries: list[dict[str, Any]] = []
    for row in _card_rows(soup):
        holder = row.find("div", class_="kand")
        card = holder.find_parent("td")
        anchor = holder.find("a", attrs={"name": True})
        name = normalize_space(holder.get_text(" ", strip=True))
        entry: dict[str, Any] = {
            "candidateName": name,
            "candidateId": slugify(name),
            "vrkCandidateId": normalize_space(anchor["name"]) if anchor else "",
            "url": LISTING_URL,
            "deklaracijaUrl": None,
            "vrkRegistrationId": "",
            "patiketiniaiUrl": None,
            "biografijaUrl": None,
            "programaUrl": None,
            "pareiskimasUrl": None,
            "sveikatosPazymejimasUrl": None,
            "nuotraukaPageUrl": None,
            "photoUrl": None,
            "websiteUrl": None,
        }
        entry.update(_registration_facts(card))

        # The photo cell precedes the card cell in the same row.
        image = row.find("img")
        if image is not None and image.get("src"):
            entry["photoUrl"] = resolve_candidate_url(normalize_space(image["src"]))
        photo_anchor = image.find_parent("a") if image is not None else None
        if photo_anchor is not None and NUOTRAUKA_LINK_PATTERN.search(photo_anchor.get("href", "")):
            entry["nuotraukaPageUrl"] = resolve_candidate_url(normalize_space(photo_anchor["href"]))

        for link in card.find_all("a", href=True):
            href = normalize_space(link["href"])
            label = normalize_space(link.get_text(" ", strip=True)).lower()
            if DEKLARACIJA_LINK_PATTERN.search(href):
                entry["deklaracijaUrl"] = resolve_candidate_url(href)
                continue
            match = PATIKETINIAI_LINK_PATTERN.search(href)
            if match is not None:
                entry["vrkRegistrationId"] = match.group(1)
                entry["patiketiniaiUrl"] = resolve_candidate_url(href)
                continue
            if DOC_LINK_PATTERN.search(href):
                key = "biografijaUrl" if label.startswith("biografija") else "programaUrl"
                entry[key] = resolve_candidate_url(href)
                continue
            if GIF_LINK_PATTERN.search(href):
                key = "pareiskimasUrl" if label.startswith("pareiškimas") else "sveikatosPazymejimasUrl"
                entry[key] = resolve_candidate_url(href)
                continue
            if href.startswith("http") and DECISION_LINK_MARKER not in href:
                entry["websiteUrl"] = href
        entries.append(entry)
    return entries


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    root = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    listing_path = root / LISTING_FILE_NAME if root.is_dir() else root
    entries = extract_listing_entries(listing_path.read_text(encoding="utf-8"))

    problems: list[str] = []
    seen_ids: set[str] = set()
    for entry in entries:
        for key in ("vrkCandidateId", "vrkRegistrationId", "deklaracijaUrl", "biografijaUrl", "nuotraukaPageUrl", "photoUrl", "registeredDate", "decision"):
            if not entry[key]:
                problems.append(f"{entry['candidateId']}: no {key}")
        # The declaration link and the card anchor must be the same id —
        # they are the one id space the record keys on.
        deklaracija = DEKLARACIJA_LINK_PATTERN.search(entry["deklaracijaUrl"] or "")
        if deklaracija is not None and deklaracija.group(1) != entry["vrkCandidateId"]:
            problems.append(f"{entry['candidateId']}: card anchor {entry['vrkCandidateId']} vs declaration id {deklaracija.group(1)}")
        if entry["candidateId"] in seen_ids:
            problems.append(f"duplicate candidate id {entry['candidateId']}")
        seen_ids.add(entry["candidateId"])
    if not entries:
        problems.append("no candidate cards found")
    if problems:
        raise ValueError("Listing did not parse cleanly: " + "; ".join(problems))

    payload = {
        "electionId": ELECTION_ID,
        "sourceUrl": LISTING_URL,
        "generatedAt": utc_now_iso(),
        # rows/extracted/skipped/duplicate_candidate_ids are the keys the
        # cli.py sitemap command reports for every election; the reconcile
        # above raises rather than skipping, so the last two are zero by
        # construction.
        "stats": {
            "rows": len(entries),
            "extracted": len(entries),
            "skipped": 0,
            "duplicate_candidate_ids": 0,
            "withPrograma": sum(1 for entry in entries if entry["programaUrl"]),
            "withWebsite": sum(1 for entry in entries if entry["websiteUrl"]),
        },
        "entries": entries,
    }
    write_json(output_path, payload)
    return output_path, dict(payload["stats"])
