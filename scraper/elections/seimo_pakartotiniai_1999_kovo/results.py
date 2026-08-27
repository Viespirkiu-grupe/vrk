"""Elected status and votes for the 1999-03-21 Seimo repeat election.

Three constituencies, one round each, all three below the turnout threshold —
Naujosios Vilnios (Nr. 10) 7,967 of 40,215 (**19.81%**, the lowest in the
family), Nevėžio (Nr. 26) 12,997 of 38,307 (33.93%) and Vilniaus Trakų
(Nr. 57) 7,432 of 38,887 (19.11%). Each page closes "Rinkimai apygardoje
neįvyko", so all 22 records carry a known `isrinktas: false`.

The pages live under the date-named `19990321` directory rather than
`seimpk`, the same split the candidate pages have; the shared reader takes
full URLs, so nothing about the directory matters here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_pakartotiniai_1999_kovo.sitemap import ELECTION_ID
from scraper.shared.seimo_archive_1990s_results import (
    VRK_STATINIAI_BASE,
    build_constituency_results,
)

RESULTS_ROOT = f"{VRK_STATINIAI_BASE}19990321/"
PAGES = [
    {"url": f"{RESULTS_ROOT}rapgpl.htm-394+1.htm", "round": 1},
    {"url": f"{RESULTS_ROOT}rapgpl.htm-397+1.htm", "round": 1},
    {"url": f"{RESULTS_ROOT}rapgpl.htm-395+1.htm", "round": 1},
]

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    return build_constituency_results(ELECTION_ID, PAGES, sitemap_path, results_dir, output_path)
