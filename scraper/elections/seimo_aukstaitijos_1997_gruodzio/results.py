"""Elected status and votes for the 1997-12-21 Seimo repeat election.

One constituency, two rounds, both linked from VRK's `seimpk` index:
`rapgpl.htm-324+1.htm` sent Aukštaitijos (Nr. 28) to a runoff ("Rinkimai
apygardoje įvyko. Reikalingas antras rinkimų turas."), and
`rapgpl.htm-324+2.htm` closes "Seimo nariu išrinktas Virmantas Velikonis." —
the one by-election of this family that seated somebody on its own second
round.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_aukstaitijos_1997_gruodzio.sitemap import ELECTION_ID
from scraper.shared.seimo_archive_1990s_results import (
    VRK_STATINIAI_BASE,
    build_constituency_results,
)

RESULTS_ROOT = f"{VRK_STATINIAI_BASE}seimpk/"
PAGES = [
    {"url": f"{RESULTS_ROOT}rapgpl.htm-324+1.htm", "round": 1},
    {"url": f"{RESULTS_ROOT}rapgpl.htm-324+2.htm", "round": 2},
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
