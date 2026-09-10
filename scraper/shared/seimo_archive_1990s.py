"""Shared parsing for the 1996-1999 archived Seimas election pages.

VRK's pre-2000 Seimas election pages (single-member constituency listings and
candidate detail pages) live under a handful of static-HTML directories --
`seim96` for the 1996 general election, `seimpk` for the 1997-1998 repeat
elections in individual constituencies, and `19990321` for the March 1999 one
-- captured by Teleport Pro from the original Oracle-backed CGI site
(`lrs.lt/cgi-bin/ora7dbcgi/...`). Six elections share this shape: the 1996
general election and the March/December 1997, March/November 1998 and March
1999 by-elections. They differ only in which directory and which "phase"
prefix (the first number in `apgtl.htm-<phase>+<constituency>.htm`) and
constituency numbers they target -- the page markup itself is identical in
structure across all of them.

**A date-named directory says nothing about the page era.** `19990321` follows
the same convention as `20000319` (`savivaldybiu_2000`) and `20001008`
(`seimo_2000`), which are the *next* layout generation -- but its pages are
these. Callers pass the directory in, so the two are independent; check the
markup, not the directory name.

The candidate detail page (`kandvl.htm`) carries a data-corrupting quirk: a
malformed HTML comment (opened by a broken `<!--sql format>` marker left by a
failed backend query, closed by the next stray `-->` much later in the page)
swallows three real fields -- "Gimimo vieta", "Gyvenamoji vieta" and
"Tautybė" -- along with a block of boilerplate eligibility Q&A that is not
real per-candidate data: it always reads the same "Neturi"/"Nėra" answers,
the failed query's default rendering, not an actual answer. The three fields
are recovered with targeted regexes over the raw HTML rather than through the
parsed DOM (a normal HTML parser drops comment contents entirely); the
eligibility junk is discarded on purpose, on the same precedent as the
2015-backlog elected-status investigation: a field that cannot be trusted is
left out and documented, not guessed at.

Below the comment the card prints the rest of its questionnaire as ordinary
paragraphs -- education level, foreign languages, academic degree and title,
bodies previously elected to, main workplace, public activity, marital
status, family members and a free-text "Ką dar norėtų parašyti apie save".
Those share their grammar with the 1997 municipal card, so they are read
through `scraper/shared/archive_1990s_card.py` and land under the corpus's
usual `anketa.*` keys. This whole block went unread until 2026-08-26 (issue
#69): the first pass over these pages read only the candidacies and the
residence, which is also why the birthplace was being inferred from the
biography's prose when the card had published it all along.

The `kpdl.htm` income and asset declaration is fetched alongside the
candidate page and read by `scraper/shared/deklaracija_archive_1990s.py`,
which the 1997 municipal archive family shares. Its shape is unrelated to any
modern-era GPM308 table -- turtas and piniginės lėšos come summed rather than
split -- so it lands in the corpus's usual `turto-ir-pajamu-deklaracijos`
block with the modern split keys null and the combined figures under their
own names; see that module for the mapping and for why section III's total is
not always trusted. The free-text biography page (`biogr.htm`) is still
captured and stored verbatim rather than structured.

Nothing on the candidate page marks a winner. Elected status and votes come
from VRK's `rapgpl` results pages instead, read by
`scraper/shared/seimo_archive_1990s_results.py` and written onto each entry of
`normalized.kandidatavimas` -- per candidacy, because a 1996 candidate could
stand in a constituency and on a party list at once. The join happens here
only when the election's `sitemaps/<id>.results.json` exists; without one the
candidacies keep their pre-#79 shape rather than claiming a false.

Callers pass in the directory, phase and constituency numbers explicitly
rather than importing them, matching `scraper/shared/municipal_sitemap.py`.
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
    bold_values,
    education_record,
    family_concepts,
    family_members,
    previously_elected_record,
)
from scraper.shared.deklaracija_archive_1990s import parse_declaration
from scraper.shared.files import slugify, write_candidate_record, write_json
from scraper.shared.http import fetch_text
from scraper.shared.seimo_archive_1990s_results import (
    apply_results,
    candidate_id_from_url,
    load_results_details,
)
from scraper.shared.values import is_refusal

VRK_STATINIAI_BASE = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/"

# Pause between page fetches during listing/candidate discovery so a capture
# of dozens to hundreds of pages does not hammer VRK's archive.
FETCH_DELAY_SECONDS = 0.2

CONSTITUENCY_NUMBER_PATTERN = re.compile(r"\(Nr\.\s*(\d+)\)")
CONSTITUENCY_URL_NUMBER_PATTERN = re.compile(r"apgtl\.htm-\d+\+(\d+)\.htm")

# The three card fields the malformed `<!--sql format>` comment swallows.
# A DOM parser drops comment contents entirely, so these are the only fields
# on the page that have to be recovered by regex over the raw HTML -- every
# other label sits outside the comment in a real paragraph. Each value is
# `<b>`-delimited on every page that prints it (measured across all 906
# retained cards: 1,730 label occurrences, 1,730 bold captures, 0 empty), so
# the closing tag is an exact stop and no label stop list is needed here.
COMMENTED_FIELD_PATTERNS = {
    label: re.compile(rf"{re.escape(label)}:\s*<b>(.*?)</b>", re.IGNORECASE | re.DOTALL)
    for label in ("Gimimo vieta", "Gyvenamoji vieta", "Tautybė")
}
RESIDENCE_PATTERN = COMMENTED_FIELD_PATTERNS["Gyvenamoji vieta"]

# The labels this card prints outside the comment, each in its own paragraph,
# to the `rawData.personal` key the 1997 municipal family already uses for the
# same field. Measured over all 906 retained cards: no paragraph carries two
# of these labels, so a value runs to the end of its paragraph and the
# municipal family's stop list is not needed on this side -- and every value
# is inside a `<b>`, so `bold_values` reads them without touching the
# surrounding text at all.
CARD_LABEL_KEYS = {
    "Išsilavinimas": "education",
    "Užsienio kalbos": "foreignLanguages",
    "Pagrindinė darbovietė": "mainWorkplace",
    "Visuomeninė veikla": "publicActivity",
    "Šeimyninė padėtis": "familyStatus",
    "Šeimos nariai": "familyMembers",
    "Moksliniai laipsniai": "academicDegree",
    "Moksliniai vardai": "academicTitle",
    PREVIOUSLY_ELECTED_LABEL: "previouslyElected",
    "Ką dar norėtų parašyti apie save": "aboutSelf",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def _clean_text(value: str) -> str:
    return normalize_space(value)


def constituency_url(directory: str, phase: str, constituency: int) -> str:
    return f"{VRK_STATINIAI_BASE}{directory}/apgtl.htm-{phase}+{constituency}.htm"


def parse_constituency_directory(html: str, source_url: str) -> list[dict[str, Any]]:
    """Parse an apgseiml.htm directory page: every constituency's name, number
    and its apgtl.htm link. Used by elections that crawl the whole country
    (the by-elections instead hardcode the handful of constituencies VRK
    names in their announcement, since no such directory page covers only
    them)."""
    soup = BeautifulSoup(html, "lxml")
    entries: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()
    for anchor in soup.find_all("a", href=True):
        number_match = CONSTITUENCY_URL_NUMBER_PATTERN.search(anchor["href"])
        if number_match is None:
            continue
        constituency_number = int(number_match.group(1))
        if constituency_number in seen_numbers:
            continue
        name = _clean_text(anchor.get_text(" ", strip=True))
        if not name:
            continue
        seen_numbers.add(constituency_number)
        entries.append(
            {
                "constituencyName": name,
                "constituencyNumber": constituency_number,
                "url": urljoin(source_url, anchor["href"]),
            }
        )
    return entries


def parse_constituency_page(html: str, source_url: str) -> dict[str, Any]:
    """Parse one apgtl.htm constituency page: name/number plus its direct
    candidate table (name + nominator; no party-list hop, unlike the
    municipal 1997 family)."""
    soup = BeautifulSoup(html, "lxml")

    heading = ""
    for font in soup.find_all("font", attrs={"size": "5"}):
        text = _clean_text(font.get_text(" ", strip=True))
        if "apygarda" in text.lower():
            heading = text
            break

    number_match = CONSTITUENCY_NUMBER_PATTERN.search(heading)
    constituency_number = int(number_match.group(1)) if number_match else None
    constituency_name = re.sub(
        r"\s*\(Nr\.\s*\d+\)\s*apygarda\s*$", "", heading, flags=re.IGNORECASE
    ).strip()

    table = None
    for candidate_table in soup.find_all("table"):
        header_text = _clean_text(candidate_table.get_text(" ", strip=True))
        if "Pavard" in header_text and "Iškėlė" in header_text:
            table = candidate_table
            break

    candidates: list[dict[str, Any]] = []
    if table is not None:
        rows = table.find_all("tr")
        for row in rows[1:]:  # skip the header row
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            name_link = cells[0].find("a", href=True)
            if name_link is None:
                continue
            candidate_name = _clean_text(name_link.get_text(" ", strip=True))
            if not candidate_name:
                continue
            nominator_link = cells[1].find("a", href=True)
            if nominator_link is not None:
                nominator = _clean_text(nominator_link.get_text(" ", strip=True))
                nominator_url = urljoin(source_url, nominator_link["href"])
            else:
                nominator = _clean_text(cells[1].get_text(" ", strip=True))
                nominator_url = ""
            candidates.append(
                {
                    "candidateName": candidate_name,
                    "url": urljoin(source_url, name_link["href"]),
                    "nominator": nominator,
                    "nominatorUrl": nominator_url,
                }
            )

    return {
        "constituencyName": constituency_name,
        "constituencyNumber": constituency_number,
        "sourceUrl": source_url,
        "candidates": candidates,
    }


def _parse_candidacy_paragraph(paragraph: Any, source_url: str) -> dict[str, Any]:
    plain = _clean_text(paragraph.get_text(" ", strip=True))
    raw = str(paragraph)

    apygarda_match = re.search(r"Apygarda:\s*(.*?)\s*Iškėlė:", plain)
    apygarda_full = apygarda_match.group(1).strip() if apygarda_match else ""
    number_match = CONSTITUENCY_NUMBER_PATTERN.search(apygarda_full)
    apygarda_number = int(number_match.group(1)) if number_match else None
    apygarda_name = re.sub(r"\s*\(Nr\.\s*\d+\)\s*$", "", apygarda_full).strip()

    nominator_match = re.search(r"Iškėlė:\s*(.*?)(?:\s*Numeris sąraše:|$)", plain)
    nominator = nominator_match.group(1).strip() if nominator_match else ""

    list_number = None
    list_match = re.search(r"Numeris sąraše:\s*(\d+)", plain)
    if list_match:
        list_number = int(list_match.group(1))

    split_idx = raw.find("Iškėlė")
    before_html = raw[:split_idx] if split_idx >= 0 else raw
    after_html = raw[split_idx:] if split_idx >= 0 else ""

    apygarda_url = ""
    match = re.search(r'href="([^"]+)"', before_html)
    if match:
        apygarda_url = urljoin(source_url, match.group(1))

    nominator_url = ""
    match = re.search(r'href="([^"]+)"', after_html)
    if match:
        nominator_url = urljoin(source_url, match.group(1))

    return {
        "apygardaName": apygarda_name,
        "apygardaNumber": apygarda_number,
        "apygardaUrl": apygarda_url,
        "nominator": nominator,
        "nominatorUrl": nominator_url,
        "listNumber": list_number,
    }


def parse_candidate_detail(html: str, source_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    name = ""
    name_font = soup.select_one("font[size='5']")
    if name_font is not None:
        name = _clean_text(name_font.get_text(" ", strip=True))

    photo_url = ""
    photo_img = soup.find("img", alt=re.compile("nuotrauka", re.IGNORECASE))
    if photo_img is not None and photo_img.get("src"):
        photo_url = urljoin(source_url, photo_img["src"])

    biography_url = ""
    income_declaration_url = ""
    for anchor in soup.find_all("a", href=True):
        label = _clean_text(anchor.get_text())
        if label == "Biografija":
            biography_url = urljoin(source_url, anchor["href"])
        elif "eklaracija" in label:
            income_declaration_url = urljoin(source_url, anchor["href"])

    commented = {
        label: _clean_text(match.group(1)) if (match := pattern.search(html)) else ""
        for label, pattern in COMMENTED_FIELD_PATTERNS.items()
    }
    # Same key names as the 1997 municipal family's `personal` block, so the
    # two archive families' rawData are directly comparable. `residence` is
    # the exception -- it has sat at rawData.residence since this module's
    # first version and stays there.
    personal: dict[str, Any] = {
        "birthPlace": commented["Gimimo vieta"],
        "nationality": commented["Tautybė"],
        "education": "",
        "foreignLanguages": [],
        "academicDegree": "",
        "academicTitle": "",
        "previouslyElected": [],
        "mainWorkplace": "",
        "publicActivity": "",
        "aboutSelf": "",
        "familyStatus": "",
        "familyMembers": [],
    }

    candidacies: list[dict[str, Any]] = []
    for paragraph in soup.find_all("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if text.startswith("Apygarda:"):
            candidacies.append(_parse_candidacy_paragraph(paragraph, source_url))
            continue
        for label, key in CARD_LABEL_KEYS.items():
            if not text.startswith(label):
                continue
            if key == "familyMembers":
                personal[key] = family_members(paragraph)
            else:
                values = [item["value"] for item in bold_values(paragraph)]
                # Everything but the language list is a single value; joining
                # keeps the scalar shape without silently dropping a second
                # <b> if a card ever prints one (none of the 906 retained
                # cards does).
                personal[key] = values if isinstance(personal[key], list) else ", ".join(values)
            break

    return {
        "candidateDisplayName": name,
        "photoUrl": photo_url,
        "biographyUrl": biography_url,
        "incomeDeclarationUrl": income_declaration_url,
        "candidacies": candidacies,
        "residence": commented["Gyvenamoji vieta"],
        "personal": personal,
    }


# Lithuanian month names as they appear in the genitive inside a birth-date
# sentence ("Gimė 1942 m. rugpjūčio 3 d.").
BIOGRAPHY_MONTHS = {
    "sausio": 1,
    "vasario": 2,
    "kovo": 3,
    "balandžio": 4,
    "gegužės": 5,
    "birželio": 6,
    "liepos": 7,
    "rugpjūčio": 8,
    "rugsėjo": 9,
    "spalio": 10,
    "lapkričio": 11,
    "gruodžio": 12,
}
BIOGRAPHY_BIRTH_FULL = re.compile(
    r"Gim[ėe]\s+(\d{4})\s*m\.\s*(" + "|".join(BIOGRAPHY_MONTHS) + r")\s*(\d{1,2})\s*d\.",
    re.IGNORECASE,
)
# "Gimė 1950 m." and the spelled-out "Gimė 1940 metais" (the 2002
# presidential biographies write the latter) both carry a year.
BIOGRAPHY_BIRTH_YEAR = re.compile(r"Gim[ėe]\s+(\d{4})\s*m(?:\.|et)", re.IGNORECASE)


def extract_biography_birth_date(text: str) -> tuple[str | None, int | None]:
    """Recover a birth date from the biography prose.

    These pages publish no birth-date field -- the whole Seimas archive family
    is the corpus's one era without one, which leaves all 906 of its records
    unable to join a person across elections. The biography's opening sentence
    almost always carries it: "Gimė 1942 m. rugpjūčio 3 d. Panevėžyje".

    Returns `(iso_date, year)`. A full day-month-year match yields both; a
    year-only sentence ("Gimė 1950 m.") yields `(None, year)` -- a year alone
    is deliberately never treated as a birth date, because keying identity on
    name plus year would merge namesakes wholesale.

    Only the **first** match is used, and only the full-date pattern is
    trusted for the date: later sentences routinely carry other people's years
    ("Tėvas - Vincas Mickus 1926 m. baigė Dotnuvos žemės ūkio akademiją"),
    so a looser scan would happily return a parent's date.

    Measured over the 879 1996 biographies: 670 full dates (76%), 154
    year-only (18%; three of them "Gimė 1940 metais" spellings the widened
    year pattern reads), 55 neither. Of the 149 full dates whose candidate shares
    a name with a modern candidate who has a published birth date, 133 (89%)
    match it exactly; 13 of the 16 that do not are plainly different people
    (born decades apart), and 3 are genuine disagreements between VRK's own
    two publications rather than parse failures.
    """
    if not text:
        return None, None
    full = BIOGRAPHY_BIRTH_FULL.search(text)
    if full:
        year = int(full.group(1))
        month = BIOGRAPHY_MONTHS[full.group(2).lower()]
        day = int(full.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}", year
    year_only = BIOGRAPHY_BIRTH_YEAR.search(text)
    if year_only:
        return None, int(year_only.group(1))
    return None, None


# The birthplace is printed in the locative ("Kaune", "Klaipėdoje", "Šiaulių
# rajone") while the rest of the corpus stores the nominative. Suffix rules
# alone cannot do the conversion -- "-yje" yields both Panevėžys and
# Radviliškis -- so every candidate a rule produces is checked against
# scraper/shared/vietovardziai.json, the place names the rest of the corpus
# actually uses. That lookup is the precision guard: a mis-parsed fragment
# ("Lietuvė", "1976 m") produces no candidate in the list and is dropped.
LOCATIVE_RULES = (
    ("iuose", "iai"), ("uose", "ai"), ("ose", "os"),
    ("iuje", "ius"), ("uje", "us"),
    ("yje", "ys"), ("yje", "is"),
    ("ijoje", "ija"), ("ėje", "ė"), ("oje", "a"),
    ("je", ""), ("e", "as"), ("e", "is"), ("e", "ys"),
)

_PLACE_VOCABULARY: set[str] | None = None


def place_vocabulary() -> set[str]:
    global _PLACE_VOCABULARY
    if _PLACE_VOCABULARY is None:
        path = Path(__file__).resolve().parent / "vietovardziai.json"
        _PLACE_VOCABULARY = set(json.loads(path.read_text(encoding="utf-8"))["places"])
    return _PLACE_VOCABULARY


# "Gimė ... Lietuvoje" resolves to a real vocabulary entry and says nothing --
# every candidate in this corpus was born somewhere. Worse, it is wrong where
# the sentence names the country before the village: cross-checked against the
# same people's later elections, all three candidates whose recovered value was
# "Lietuva" had a specific birthplace published elsewhere.
TOO_COARSE_PLACES = {"Lietuva", "Lietuvos Respublika"}


def nominative_place(locative: str) -> str | None:
    """The nominative for a locative place name, or None if unrecognised."""
    vocabulary = place_vocabulary() - TOO_COARSE_PLACES
    for suffix, replacement in LOCATIVE_RULES:
        if locative.endswith(suffix) and len(locative) > len(suffix):
            candidate = locative[: -len(suffix)] + replacement
            if candidate in vocabulary:
                return candidate
    return None


# "Gimė 1955 m. rugsėjo 8 d. Klaipėdoje, tarnautojų šeimoje." The place runs
# to the first comma; what follows is the family's background, not a location.
BIOGRAPHY_BIRTH_PLACE = re.compile(
    r"Gim[ėe]\s+\d{4}\s*m\.\s*\w+\s+\d+\s*d\.\s*(.{0,60}?)(?:\.|;)", re.S
)


def extract_biography_birth_place(text: str) -> str | None:
    """Birthplace from the biography's opening sentence, nominative.

    A *fallback*, and a small one. When this was written the card's own
    "Gimimo vieta" was not being read and the biography was these records'
    only birthplace; issue #69 recovered the card field, and 873 of the 950
    archive records take it from there. What is left for this is the 39 with
    no card birthplace whose biography names a place, of which 19 resolve
    against the vocabulary. The other 20 are villages, parishes and
    Soviet-era regions the corpus has no nominative for ("Adutiškio
    parapijoje", "Vakarų Kazachstane", "Nosotkos kaime"), and are left out
    rather than guessed at.

    The docstring here used to say "571 name a place and 453 of those
    resolve (79%)", which described the corpus before #69 (issue #155).
    """
    match = BIOGRAPHY_BIRTH_PLACE.search(text or "")
    if not match:
        return None
    head = match.group(1).split(",")[0].strip()
    # "Gimė ... d. darbininkų šeimoje" names a background, not a place.
    if not head or "šeim" in head:
        return None
    return nominative_place(head)


def parse_biography(html: str) -> dict[str, Any]:
    # The biography text lives in the page's <blockquote>; everything outside
    # it is the shared page header/footer boilerplate ("Puslapius kuria ir
    # palaiko...").
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("blockquote") or soup
    paragraphs = [
        _clean_text(p.get_text(" ", strip=True))
        for p in container.find_all("p")
        if _clean_text(p.get_text(" ", strip=True))
    ]
    text = "\n".join(paragraphs)
    birth_date, birth_year = extract_biography_birth_date(text)
    return {
        "text": text,
        "birthDate": birth_date,
        "birthYear": birth_year,
        "birthPlace": extract_biography_birth_place(text),
    }


def fetch_constituency_samples(
    targets: list[dict[str, Any]],
    samples_dir: Path,
    delay_seconds: float = FETCH_DELAY_SECONDS,
) -> list[Path]:
    """Fetch and save every target constituency's apgtl.htm page.

    `targets` is a list of `{"phase": str, "constituency": int}` (or a
    pre-resolved `{"url": str, "constituency": int}`), supplied by the
    calling election module -- either the full set read back from a directory
    sample (see `parse_constituency_directory`) or the handful VRK names in a
    by-election announcement.
    """
    samples_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    for target in targets:
        constituency = target["constituency"]
        sample_path = samples_dir / f"apgtl-{constituency}.html"
        if sample_path.exists():
            saved_paths.append(sample_path)
            continue
        html = fetch_text(target["url"])
        sample_path.write_text(html, encoding="utf-8")
        saved_paths.append(sample_path)
        time.sleep(delay_seconds)
    return saved_paths


def build_sitemap_from_constituency_samples(
    sample_paths: list[Path],
    output_path: Path,
    election_id: str,
    source_description: str,
) -> tuple[Path, dict[str, int]]:
    entries: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}

    for sample_path in sample_paths:
        html = sample_path.read_text(encoding="utf-8")
        # The saved constituency sample has no reliable source URL of its own
        # (it was read back from disk); the candidate rows' hrefs are
        # resolved against the VRK archive base since every href in these
        # pages is already a full or root-relative statiniai path.
        page = parse_constituency_page(html, source_url=VRK_STATINIAI_BASE)
        for candidate in page["candidates"]:
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
                    "constituencyName": page["constituencyName"],
                    "constituencyNumber": page["constituencyNumber"],
                    "nominator": candidate["nominator"],
                    "nominatorUrl": candidate["nominatorUrl"],
                }
            )

    duplicate_candidate_ids = sum(1 for count in seen_ids.values() if count > 1)

    payload = {
        "electionId": election_id,
        "sourceDescription": source_description,
        "generatedAt": utc_now_iso(),
        "stats": {
            "constituencies": len(sample_paths),
            "candidates": len(entries),
            "duplicateCandidateIds": duplicate_candidate_ids,
        },
        "entries": entries,
    }
    write_json(output_path, payload)
    # cli.py's generic `sitemap` command printing was written against the
    # tabbed elections' row/extracted/skipped/duplicate shape; every
    # constituency row here is either extracted or not present at all (no
    # partial/skipped rows), so "rows" and "extracted" are the same count.
    return output_path, {
        "rows": len(entries),
        "extracted": len(entries),
        "skipped": 0,
        "duplicate_candidate_ids": duplicate_candidate_ids,
    }


def fetch_listing_sample_for_targets(
    targets: list[dict[str, Any]],
    sample_path: Path,
    constituencies_dir: Path,
) -> Path:
    """For by-elections that target a small, explicitly-known set of
    constituencies (no directory page covers only them, unlike the 1996
    general election): fetch each one and write a small manifest at
    `sample_path` recording what was targeted, so `fetch-sample` still has a
    single path to report."""
    fetch_constituency_samples(targets, constituencies_dir)
    write_json(sample_path, {"targets": targets})
    return sample_path


def build_sitemap_from_targets(
    constituencies_dir: Path,
    output_path: Path,
    election_id: str,
    source_description: str,
) -> tuple[Path, dict[str, int]]:
    sample_paths = sorted(
        constituencies_dir.glob("apgtl-*.html"),
        key=lambda p: int(p.stem.split("-")[1]),
    )
    if not sample_paths:
        raise ValueError(f"No constituency samples found under {constituencies_dir}. Run fetch-sample first.")
    return build_sitemap_from_constituency_samples(sample_paths, output_path, election_id, source_description)


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
    """Fetch and save one candidate's kandvl.htm page, plus their biogr.htm
    page if the candidate page links one.

    There is no tab navigation on these pages (unlike every 2016+ election),
    so the result shape below is an analogue of the tab-walking modules'
    result, not a literal one: "tabs" here means "candidate.html" plus the
    optional "biography.html", so `cli.py`'s generic fetch-sample printing
    (written against the tabbed elections) still has the fields it expects.
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
    for label, url, filename in (
        ("Biography", detail["biographyUrl"], "biography.html"),
        ("Declaration", detail["incomeDeclarationUrl"], "declaration.html"),
    ):
        if not url:
            continue
        tab_count += 1
        try:
            (candidate_dir / filename).write_text(fetch_text(url), encoding="utf-8")
            tabs_saved += 1
        except Exception as exc:  # noqa: BLE001 - recorded as an anomaly, not fatal
            anomalies.append(
                build_anomaly_event(
                    event_type=f"{label}FetchFailed",
                    severity="error",
                    stage="fetch",
                    election_id=election_id,
                    candidate_id=entry["candidateId"],
                    source_url=entry["url"],
                    detail={"url": url, "error": str(exc)},
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
    biography: dict[str, Any] | None = None
    biography_path = candidate_dir / "biography.html"
    if detail["biographyUrl"]:
        if biography_path.exists():
            biography = parse_biography(biography_path.read_text(encoding="utf-8"))
        else:
            anomalies.append(
                build_anomaly_event(
                    event_type="BiographySampleMissing",
                    severity="warning",
                    stage="parse",
                    election_id=election_id,
                    candidate_id=candidate_id,
                    source_url=entry["url"],
                    detail={"biographyUrl": detail["biographyUrl"]},
                )
            )

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

    if not detail["candidacies"]:
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
    if not detail["residence"]:
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

    raw_data = {
        "profile": {
            "candidateDisplayName": detail["candidateDisplayName"],
            "photoUrl": detail["photoUrl"],
            "biographyUrl": detail["biographyUrl"],
            "incomeDeclarationUrl": detail["incomeDeclarationUrl"],
        },
        "candidacies": detail["candidacies"],
        "residence": detail["residence"],
        # The questionnaire the card prints below the candidacies: the two
        # fields the malformed comment hides alongside the residence, then
        # every labelled paragraph. Keyed as the 1997 municipal family keys
        # the same fields, and always complete -- a label the candidate left
        # blank reads as "" or [], not as a missing key.
        "personal": detail["personal"],
        "biography": biography,
        "declaration": declaration,
    }

    # These pages publish no birth-date field, so the only birth date this
    # family can have is the one recovered from the biography's opening
    # sentence. It goes under the corpus's usual `anketa.gimimo-data` so the
    # person index, concept map and dashboard resolve it with no special
    # case -- but `gimimo-data-saltinis` records that it came from prose
    # rather than a labelled field, because it is a weaker source than every
    # other era's: VRK's own biography and questionnaire disagree for a
    # measured 3 of 149 checkable people. `gimimo-metai` carries the
    # year-only cases, which are never promoted to a birth date.
    birth_date = biography.get("birthDate") if biography else None
    birth_year = biography.get("birthYear") if biography else None
    anketa: dict[str, Any] = {}
    if birth_date:
        anketa["gimimo-data"] = birth_date
        anketa["gimimo-data-saltinis"] = "biografijos-tekstas"
    if birth_year:
        anketa["gimimo-metai"] = birth_year

    # Birthplace, unlike the birth date, *is* a published field here -- it
    # just sits inside the malformed comment, which is why the first pass over
    # these pages concluded the card had none and fell back to the biography's
    # opening sentence. The card field wins when present (852 of 906 records,
    # against 447 the prose reached), and is written in the same form as the
    # 1997 municipal family's, since it is literally the same field on the
    # same card generation: "Melagėnų k. , Švenčionių raj.".
    #
    # `gimimo-vietos-saltinis` therefore now marks only the fallback. Its
    # presence means "derived from prose, weaker than a published field"; its
    # absence means the card published the value, exactly like every other era.
    personal = detail["personal"]
    prose_birth_place = biography.get("birthPlace") if biography else None
    if personal["birthPlace"]:
        anketa["gimimo-vieta"] = personal["birthPlace"]
    elif prose_birth_place:
        anketa["gimimo-vieta"] = prose_birth_place
        anketa["gimimo-vietos-saltinis"] = "biografijos-tekstas"

    spouse, children = family_concepts(personal["familyMembers"])
    # Assembled in a fixed order so every record of this family carries its
    # anketa keys in one order, whichever labels the candidate filled in.
    card_values: dict[str, Any] = {
        "tautybe": personal["nationality"] or None,
        "issilavinimas": education_record(personal["education"]),
        "mokslo-laipsnis": personal["academicDegree"] or None,
        "pedagoginis-vardas": personal["academicTitle"] or None,
        "uzsienio-kalbos": personal["foreignLanguages"],
        "anksciau-isrinktas": previously_elected_record(personal["previouslyElected"]),
        "pagrindine-darboviete": personal["mainWorkplace"] or None,
        "visuomenine-veikla": personal["publicActivity"] or None,
        "kita-apie-save": personal["aboutSelf"] or None,
        # VRK's refusal token is a word, not punctuation, so `clean_value`
        # leaves it alone by design (`rawData` keeps the published text). It
        # reached `normalized` on 18 of this election's records as a marital
        # status the candidate declined to state (issue #164).
        "seimine-padetis": None if is_refusal(personal["familyStatus"]) else (personal["familyStatus"] or None),
        "sutuoktinio-vardas-pavarde": spouse,
        "vaiku-vardai-pavardes": children,
        "seimos-nariai": personal["familyMembers"],
    }
    # A candidate who answered nothing gets no empty keys at all -- the same
    # rule the birth-date block already followed, so a record's anketa says
    # what the card actually carried. `uzsienio-kalbos` and `seimos-nariai`
    # are lists, so emptiness is `[]` rather than None.
    anketa.update({key: value for key, value in card_values.items() if value not in (None, [])})

    # Normalized keys are kebab-case throughout, matching every other election
    # module: `profilis.vardas-pavarde`, `profilis.nuotrauka` and the rest are
    # the corpus-wide names that docs/concept-map.json and the dashboard's
    # field map both resolve against. `anketa` keeps the corpus's position
    # (right after `profilis`) and is omitted entirely when the biography
    # yielded nothing, rather than sitting there empty.
    normalized = {
        "profilis": {
            "vardas-pavarde": detail["candidateDisplayName"],
            "nuotrauka": detail["photoUrl"] or None,
            "biografijos-nuoroda": detail["biographyUrl"] or None,
            "pajamu-deklaracijos-nuoroda": detail["incomeDeclarationUrl"] or None,
        },
        **({"anketa": anketa} if anketa else {}),
        "kandidatavimas": [
            {
                "apygarda": c["apygardaName"],
                "apygardos-numeris": c["apygardaNumber"],
                "apygardos-nuoroda": c["apygardaUrl"] or None,
                "iskele": c["nominator"],
                "iskele-nuoroda": c["nominatorUrl"] or None,
                "numeris-sarase": c["listNumber"],
            }
            for c in detail["candidacies"]
        ],
        "gyvenamoji-vieta": detail["residence"] or None,
        "biografija": {"tekstas": biography["text"]} if biography else None,
        # Same key the whole corpus declares under, so the person index,
        # concept map and dashboard need no special case for this era.
        **({"turto-ir-pajamu-deklaracijos": declaration} if declaration else {}),
    }

    # Elected status, votes and (1996 only) the list ranking, joined in from
    # VRK's results pages when `python -m scraper build-results <id>` has
    # written the election's results file. Without one the candidacies keep
    # their pre-#79 shape and say nothing about the outcome, rather than
    # claiming a false; with one, every candidacy carries a `isrinktas` that
    # is a read verdict on both sides -- these pages state an outcome for
    # every constituency of the family, `neįvyko` included.
    for problem in apply_results(
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

    # The listing table is headed "Pavardė, vardas" and prints the name
    # surname-first ("Kubilius Andrius"); the candidate page's own heading
    # prints it given-name-first ("Andrius Kubilius"), which is the order
    # every other era in the corpus uses for candidateName. Prefer the page
    # heading so a name is comparable across eras, and keep the listing form
    # in rawData. (candidateId is unaffected -- it is slugified from the
    # listing name at sitemap time, so record filenames stay stable.)
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
    results_data = load_results_details(results_path)

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
        write_candidate_record(
            output_path, record, source_path=samples_root / candidate_id / "candidate.html"
        )

        # No anketa question rows exist on these pages; "rows" here are the
        # scalar identity/candidacy fields, so cli.py's generic row-count
        # print line still means something rather than being a stub 0/0.
        scalar_fields = [
            record["rawData"]["profile"]["candidateDisplayName"],
            record["rawData"]["residence"],
            *[c["nominator"] for c in record["rawData"]["candidacies"]],
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
