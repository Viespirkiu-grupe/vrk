from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.shared.files import slugify, write_json
from scraper.shared.http import fetch_text
from scraper.shared.values import candidate_status_note

ELECTION_ID = "2016-seimo"
LISTING_URL = (
    "https://www.vrk.lt/2016-seimo/kandidatai"
    "?srcUrl=/rinkimai/102/rnk426/kandidatai/lrsKandidataiPilnasSarasas.html"
)
VRK_STATINIAI_BASE = "https://www.vrk.lt/statiniai/puslapiai/"

DEFAULT_SAMPLE_PATH = Path("samples/html/2016-seimo/list.html")
DEFAULT_WRAPPER_SAMPLE_PATH = Path("samples/html/2016-seimo/page.html")
DEFAULT_SITEMAP_PATH = Path("sitemaps/2016-seimo.json")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def clean_candidate_name(raw_name: str) -> str:
    name = normalize_space(raw_name)
    # Remove cancellation marker explicitly requested by user.
    name = re.sub(
        r"\s*\(panaikinta kandidato registracija\)\s*$",
        "",
        name,
        flags=re.IGNORECASE,
    )
    # Remove trailing short or status-like parenthetical markers, e.g. (D), (V).
    while True:
        cleaned = re.sub(r"\s*\([^()]{1,64}\)\s*$", "", name).strip()
        if cleaned == name:
            break
        name = cleaned
    return name


def extract_candidate_note(raw_name: str) -> str:
    """The status note `clean_candidate_name` strips, kept (issue #164).

    Two candidates of this election carry one -- "(panaikinta kandidato
    registracija)" on Kęstas Komskis, "(mirė)" on Juras Požela -- and both
    were stripped while nothing kept them, so the corpus said a candidate who
    died before polling day and one whose registration was revoked were
    ordinary losing candidates. The candidate page leaves that line blank.

    Only a *status* marker is kept. This listing also parenthesises the
    constituency an elected member won in, `(D)` or `(V)`, on 141 of its
    1,415 rows -- a fact about the ballot, already carried by the elected
    flags, and reading it here would put a role letter in `candidateNote` on
    a tenth of the election.
    """
    return candidate_status_note(raw_name)


def resolve_candidate_url(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href

    if href.startswith("?srcUrl="):
        src_url = href.split("?srcUrl=", 1)[1]
        return urljoin(VRK_STATINIAI_BASE, src_url.lstrip("/"))

    return urljoin(VRK_STATINIAI_BASE, href.lstrip("/"))


def _extract_src_url(listing_url: str) -> str | None:
    parsed = urlparse(listing_url)
    query = parse_qs(parsed.query)
    src_urls = query.get("srcUrl")
    if not src_urls:
        return None
    return src_urls[0]


def fetch_listing_sample(sample_path: Path = DEFAULT_SAMPLE_PATH) -> Path:
    wrapper_html = fetch_text(LISTING_URL)
    DEFAULT_WRAPPER_SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_WRAPPER_SAMPLE_PATH.write_text(wrapper_html, encoding="utf-8")

    src_url = _extract_src_url(LISTING_URL)
    if src_url:
        resolved_data_url = urljoin(VRK_STATINIAI_BASE, src_url.lstrip("/"))
        html = fetch_text(resolved_data_url)
    else:
        html = wrapper_html

    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(html, encoding="utf-8")
    return sample_path


def _select_candidate_rows(soup: BeautifulSoup) -> list[Any]:
    table = (
        soup.select_one("table.partydata")
        or soup.select_one("table#table3.partydata")
        or soup.select_one("table#table3")
    )
    if table is None:
        return []

    body = table.find("tbody")
    if body is not None:
        return body.find_all("tr")

    return table.find_all("tr")


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    if sample_path is None:
        sample_path = DEFAULT_SAMPLE_PATH

    html = sample_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    rows = _select_candidate_rows(soup)
    provisional_entries: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    base_id_counter: Counter[str] = Counter()

    for row_index, row in enumerate(rows, start=1):
        cells = row.find_all("td")
        if not cells:
            skipped.append({"rowIndex": row_index, "reason": "no-cells"})
            continue

        name_cell = cells[0]
        link = name_cell.find("a", href=True)
        if link is None:
            skipped.append(
                {
                    "rowIndex": row_index,
                    "reason": "missing-link",
                    "rawCellText": normalize_space(name_cell.get_text(" ", strip=True)),
                }
            )
            continue

        raw_candidate_name = link.get_text(" ", strip=True)
        candidate_name = clean_candidate_name(raw_candidate_name)
        candidate_note = extract_candidate_note(raw_candidate_name)
        if not candidate_name:
            skipped.append({"rowIndex": row_index, "reason": "empty-name"})
            continue

        href = normalize_space(link["href"])
        if not href:
            skipped.append({"rowIndex": row_index, "reason": "empty-href"})
            continue

        candidate_id = slugify(candidate_name)
        if not candidate_id:
            skipped.append(
                {
                    "rowIndex": row_index,
                    "reason": "bad-candidate-id",
                    "candidateName": candidate_name,
                }
            )
            continue

        base_id_counter[candidate_id] += 1
        provisional_entries.append(
            {
                "candidateName": candidate_name,
                # Only where there is one: two of the 1,415 rows carry a
                # status marker, and a `""` on the other 1,413 would put a
                # key in every entry that the fixture `index.json` files
                # written before this change do not have -- which
                # tests/test_fixture_sitemap_agreement.py holds equal.
                **({"candidateNote": candidate_note} if candidate_note else {}),
                "candidateId": candidate_id,
                "url": resolve_candidate_url(href),
            }
        )

    # Keep first duplicate as base id, then suffix next ones with -2, -3, ... for sitemap uniqueness.
    seen_counter: Counter[str] = Counter()
    for entry in provisional_entries:
        base_id = entry["candidateId"]
        seen_counter[base_id] += 1
        idx = seen_counter[base_id]
        if base_id_counter[base_id] > 1 and idx > 1:
            entry["candidateId"] = f"{base_id}-{idx}"
        entries.append(entry)

    duplicate_candidate_ids = sum(1 for _, count in base_id_counter.items() if count > 1)

    payload = {
        "electionId": ELECTION_ID,
        "sourceUrl": LISTING_URL,
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": len(rows),
            "extracted": len(entries),
            "skipped": len(skipped),
            "duplicateCandidateIds": duplicate_candidate_ids,
        },
        "entries": entries,
        "skipped": skipped,
    }
    write_json(output_path, payload)

    stats = {
        "rows": len(rows),
        "extracted": len(entries),
        "skipped": len(skipped),
        "duplicate_candidate_ids": duplicate_candidate_ids,
    }
    return output_path, stats
