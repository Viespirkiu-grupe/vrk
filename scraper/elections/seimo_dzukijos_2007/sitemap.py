from __future__ import annotations

import json
from pathlib import Path
import re

# VRK election 396 — the oldest election of the pre-2016 static layout
# family, one year older than the 2008 general. The Kandidatai/index.html
# the ticket names is a meta-refresh to the one constituency's candidate
# page, so as for the 2015 single-constituency by-elections the district
# page itself is the listing and the March 2015 Žirmūnai machinery runs
# with this module's constants. The path has no "_lt" suffix (rinkimai/396/).
from scraper.elections.seimo_birzu_zarasu_ukmerges_2013.sitemap import district_records
from scraper.elections.seimo_zirmunu_2015.sitemap import (
    build_sitemap_from_sample as _build_sitemap_from_sample,
    fetch_listing_sample as _fetch_listing_sample,
    resolve_candidate_url,
)
from scraper.shared.files import write_json

ELECTION_ID = "2007-spalio-7-seimo-dzukija"
LISTING_URL = (
    "https://www.vrk.lt/statiniai/puslapiai/rinkimai/396"
    "/Apygardos/Apygarda6838/KandidataiApygardos6838.html"
)
# The one constituency, as the 2013 module's walk would record it from an
# index; there is no index here, so the facts are constants.
DISTRICT = {"name": "Dzūkijos", "number": 69, "districtId": "6838"}

DEFAULT_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/list.html")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")


def given_first_name(name: str) -> str:
    """"ONA BALEVIČIŪTĖ" → "Ona BALEVIČIŪTĖ": this listing alone prints the
    whole name in capitals; every other listing of the corpus, and this
    election's own results pages, write the given names in title case and
    the surname in capitals, and the corpus keeps that form."""
    parts = name.split()
    if len(parts) < 2:
        return name
    return " ".join([part.title() for part in parts[:-1]] + [parts[-1]])


def fetch_listing_sample(sample_path: Path = DEFAULT_SAMPLE_PATH) -> Path:
    return _fetch_listing_sample(sample_path=sample_path, listing_url=LISTING_URL)


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    if sample_path is None:
        sample_path = DEFAULT_SAMPLE_PATH
    output_path, stats = _build_sitemap_from_sample(
        sample_path=sample_path,
        output_path=output_path,
        election_id=ELECTION_ID,
        listing_url=LISTING_URL,
    )
    # The era builder records name, id and url; the 2013 module's district
    # row reader adds VRK's candidate id and the nominator from the same
    # listing, so the entries carry the Seimo candidacy block the 2008-2013
    # records have.
    by_vrk_id = {
        record["vrkCandidateId"]: record
        for record in district_records(sample_path.read_text(encoding="utf-8"), DISTRICT)
    }
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    for entry in payload["entries"]:
        entry["candidateName"] = given_first_name(entry["candidateName"])
        match = re.search(r"Kandidato(\d+)Anketa", entry["url"])
        record = by_vrk_id.get(match.group(1)) if match else None
        if record is None:
            continue
        entry["vrkCandidateId"] = record["vrkCandidateId"]
        entry["roles"] = ["vienmandate"]
        entry["vienmandateCandidacy"] = {
            "apygarda": DISTRICT["name"],
            "apygardosNumeris": DISTRICT["number"],
            "apygardosId": DISTRICT["districtId"],
            "iskele": record["nominatedBy"] or None,
        }
    write_json(output_path, payload)
    return output_path, stats
