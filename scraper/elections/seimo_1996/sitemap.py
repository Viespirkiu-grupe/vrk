"""Sitemap building for the 1996-10-20 Seimas general election.

The candidate pages are the 1996-1998 Seimas archive layout (see
`scraper/shared/seimo_archive_1990s.py`): a directory page enumerates all 71
single-member constituencies, and each constituency page lists its
candidates directly (no party-list hop). This module supplies the directory
URL and directory-parsing loop; the shared module does the actual page
parsing.
"""

from __future__ import annotations

from pathlib import Path

from scraper.shared.http import fetch_text
from scraper.shared.seimo_archive_1990s import (
    build_sitemap_from_constituency_samples,
    fetch_constituency_samples,
    parse_constituency_directory,
)

ELECTION_ID = "1996-spalio-20-seimo"
DIRECTORY_URL = "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seim96/apgseiml.htm-1.htm"

DEFAULT_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/list.html")
DEFAULT_CONSTITUENCIES_DIR = Path(f"samples/html/{ELECTION_ID}/constituencies")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")


def fetch_listing_sample(sample_path: Path = DEFAULT_SAMPLE_PATH) -> Path:
    html = fetch_text(DIRECTORY_URL)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(html, encoding="utf-8")

    directory_entries = parse_constituency_directory(html, DIRECTORY_URL)
    targets = [
        {"constituency": entry["constituencyNumber"], "url": entry["url"]}
        for entry in directory_entries
    ]
    fetch_constituency_samples(targets, DEFAULT_CONSTITUENCIES_DIR)
    return sample_path


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    del sample_path  # the directory sample only names the constituencies;
    # the per-constituency samples already saved by fetch_listing_sample are
    # what actually gets read back here.
    sample_paths = sorted(
        DEFAULT_CONSTITUENCIES_DIR.glob("apgtl-*.html"),
        key=lambda p: int(p.stem.split("-")[1]),
    )
    if not sample_paths:
        raise ValueError(
            f"No constituency samples found under {DEFAULT_CONSTITUENCIES_DIR}. "
            "Run fetch-sample first."
        )
    return build_sitemap_from_constituency_samples(
        sample_paths,
        output_path,
        election_id=ELECTION_ID,
        source_description=f"71 single-member constituencies from {DIRECTORY_URL}",
    )
