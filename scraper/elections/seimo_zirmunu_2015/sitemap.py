from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.shared.files import slugify, write_json
from scraper.shared.http import fetch_text

ELECTION_ID = "2015-kovo-1-seimo-zirmunai"
# The pre-2016 static pages have no Liferay wrapper with a srcUrl parameter;
# the district's candidate listing is the page itself.
LISTING_URL = (
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/448_lt"
    "/Apygardos/Apygarda7822/KandidataiApygardos7822.html"
)
VRK_BASE = "https://www.vrk.lt/"

DEFAULT_SAMPLE_PATH = Path("samples/html/2015-kovo-1-seimo-zirmunai/list.html")
DEFAULT_SITEMAP_PATH = Path("sitemaps/2015-kovo-1-seimo-zirmunai.json")

# 2015-era candidate links use the "Kandidato<ID>Anketa" file stem — the
# genitive form, unlike the "KandidatasAnketa"/"savKandidatasAnketa" stems the
# 2016+ eras share, so the later modules' marker substring cannot match here.
CANDIDATE_LINK_PATTERN = re.compile(r"Kandidato\d+Anketa\.html$")


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


def resolve_candidate_url(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href

    # Hrefs on these pages are root-relative and carry literal "../.."
    # segments ("/statiniai/.../Apygarda7822/../../Kandidatai/..."); urljoin
    # against the site root collapses them. The 2007 by-election template
    # climbs one level too many for its campaign link (five "../" from
    # Kandidatas<ID>/, landing in /statiniai/rinkimai/…, which does not
    # exist); the page the template meant is one level down.
    resolved = urljoin(VRK_BASE, href)
    return resolved.replace("/statiniai/rinkimai/", "/statiniai/puslapiai/rinkimai/", 1)


def fetch_listing_sample(
    sample_path: Path = DEFAULT_SAMPLE_PATH,
    listing_url: str = LISTING_URL,
) -> Path:
    html = fetch_text(listing_url)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(html, encoding="utf-8")
    return sample_path


def _select_candidate_rows(soup: BeautifulSoup) -> list[Any]:
    # The page has several tables — the district-info card, the candidate
    # listing, and on municipal pages a class-less mayoral table and a
    # party-list index. The listing is whichever table holds the most
    # candidate anketa links.
    best_table = None
    best_count = 0
    for candidate_table in soup.find_all("table"):
        count = sum(
            1
            for anchor in candidate_table.find_all("a", href=True)
            if CANDIDATE_LINK_PATTERN.search(anchor["href"])
        )
        if count > best_count:
            best_table = candidate_table
            best_count = count
    table = best_table

    if table is None:
        return []

    body = table.find("tbody")
    if body is not None:
        return body.find_all("tr")

    return table.find_all("tr")


def _select_candidate_link(row: Any) -> Any | None:
    for anchor in row.find_all("a", href=True):
        if CANDIDATE_LINK_PATTERN.search(anchor["href"]):
            return anchor
    return None


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
    election_id: str = ELECTION_ID,
    listing_url: str = LISTING_URL,
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
            # The header row uses <th> cells, so it lands here.
            skipped.append({"rowIndex": row_index, "reason": "no-cells"})
            continue

        link = _select_candidate_link(row)
        if link is None:
            skipped.append(
                {
                    "rowIndex": row_index,
                    "reason": "missing-link",
                    "rawCellText": normalize_space(row.get_text(" ", strip=True)),
                }
            )
            continue

        candidate_name = clean_candidate_name(link.get_text(" ", strip=True))
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
                "candidateId": candidate_id,
                "url": resolve_candidate_url(href),
            }
        )

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
        "electionId": election_id,
        "sourceUrl": listing_url,
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
