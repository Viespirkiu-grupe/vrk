from __future__ import annotations

from pathlib import Path
from typing import Any

# The November 2005 Kėdainiai by-election (GitHub issue #33) — the seat
# Viktor Uspaskich gave up — is the 2004 Seimas tree one year on
# (rinkimai/2005/seimas/, the same original static site): one constituency
# page of candidates with their nominators, a party index that only
# restates them (five parties, one nominee each), and the same candidate
# pages. The 2004 Seimas module's constituency reader runs with this
# election's one district; there are no lists.
from scraper.elections.seimo_2004.sitemap import (
    DISTRICTS_INDEX_NAME,
    _district_sample_path,
    _fetch_once,
    district_records,
    extract_district_links,
)
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import assign_positional_ids
from scraper.elections.seimo_zirmunu_2015.sitemap import resolve_candidate_url, utc_now_iso
from scraper.shared.files import slugify, write_json

ELECTION_ID = "2005-lapkricio-20-seimo-kedainiai"
DISTRICTS_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2005/seimas/kandidatai/vapg_sar_l_21.htm"
LISTING_URL = DISTRICTS_URL
PARTIES_URL = "https://www.vrk.lt/statiniai/puslapiai/rinkimai/2005/seimas/kandidatai/part_sar_l_21.htm"
PARTIES_INDEX_NAME = "list.html"

DEFAULT_SAMPLES_DIR = Path(f"samples/html/{ELECTION_ID}")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

__all__ = [
    "DISTRICTS_URL",
    "ELECTION_ID",
    "LISTING_URL",
    "PARTIES_URL",
    "build_sitemap_from_sample",
    "fetch_listing_sample",
    "resolve_candidate_url",
]


def fetch_listing_sample(samples_dir: Path = DEFAULT_SAMPLES_DIR) -> Path:
    # The constituency index and its one constituency page, plus the party
    # index (the declared counts are the cross-check).
    samples_dir.mkdir(parents=True, exist_ok=True)
    districts_html = _fetch_once(samples_dir / DISTRICTS_INDEX_NAME, DISTRICTS_URL)
    for link in extract_district_links(districts_html):
        _fetch_once(_district_sample_path(samples_dir, link["districtId"]), link["url"])
    _fetch_once(samples_dir / PARTIES_INDEX_NAME, PARTIES_URL)
    return samples_dir


def _declared_party_nominees(parties_html: str) -> int:
    from bs4 import BeautifulSoup

    from scraper.elections.seimo_2004.sitemap import _headed_table, _keyed_rows

    soup = BeautifulSoup(parties_html, "lxml")
    table, headers = _headed_table(soup, "Pavadinimas")
    if table is None:
        return 0
    total = 0
    for row in _keyed_rows(table, headers):
        cell = row.get("Kandidatų skaičius")
        text = cell.get_text(" ", strip=True) if cell is not None else ""
        if text.isdigit():
            total += int(text)
    return total


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    samples_dir = sample_path if sample_path is not None else DEFAULT_SAMPLES_DIR
    districts = extract_district_links((samples_dir / DISTRICTS_INDEX_NAME).read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for district in districts:
        records.extend(
            district_records(_district_sample_path(samples_dir, district["districtId"]).read_text(encoding="utf-8"), district)
        )
    entries: list[dict[str, Any]] = []
    for record in records:
        entries.append(
            {
                "candidateName": record["candidateName"],
                "candidateId": slugify(record["candidateName"]),
                "url": record["url"],
                "vrkCandidateId": record["vrkCandidateId"],
                "roles": ["vienmandate"],
                "vienmandateCandidacy": {
                    "apygarda": record["district"]["pavadinimas"],
                    "apygardosNumeris": record["district"]["numeris"],
                    "apygardosId": record["district"]["apygardosId"],
                    "iskele": record["nominatedBy"] or None,
                },
            }
        )
    duplicate_candidate_ids = assign_positional_ids(entries)
    parties_path = samples_dir / PARTIES_INDEX_NAME
    declared = _declared_party_nominees(parties_path.read_text(encoding="utf-8")) if parties_path.exists() else None
    payload = {
        "electionId": ELECTION_ID,
        "sourceUrl": DISTRICTS_URL,
        "districtsUrl": DISTRICTS_URL,
        "partiesUrl": PARTIES_URL,
        "districtUrls": [district["url"] for district in districts],
        "generatedAt": utc_now_iso(),
        "stats": {
            "rows": len(records),
            "extracted": len(entries),
            "duplicateCandidateIds": duplicate_candidate_ids,
            "districts": len(districts),
            "partyNomineesDeclared": declared,
            "selfNominated": sum(1 for entry in entries if "išsikėlė" in (entry["vienmandateCandidacy"]["iskele"] or "").lower()),
        },
        "entries": entries,
    }
    write_json(output_path, payload)
    stats = dict(payload["stats"])
    stats["skipped"] = 0
    stats["duplicate_candidate_ids"] = duplicate_candidate_ids
    return output_path, stats
