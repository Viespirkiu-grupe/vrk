"""Elected status and votes for the 1998-11-15 Seimo repeat election.

One constituency, one round: `rapgpl.htm-392+1.htm` records 11,651 of 38,358
voters in Nevėžio (Nr. 26) — 30.37% — and closes "Rinkimai apygardoje
neįvyko." No second round was held and nobody was elected, so all 11 records
carry a known `isrinktas: false`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_nevezio_1998_lapkricio.sitemap import ELECTION_ID
from scraper.shared.seimo_archive_1990s_results import (
    VRK_STATINIAI_BASE,
    build_constituency_results,
)

RESULTS_ROOT = f"{VRK_STATINIAI_BASE}seimpk/"
PAGES = [{"url": f"{RESULTS_ROOT}rapgpl.htm-392+1.htm", "round": 1}]

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    return build_constituency_results(ELECTION_ID, PAGES, sitemap_path, results_dir, output_path)
