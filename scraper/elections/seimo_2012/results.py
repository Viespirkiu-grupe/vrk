from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_2012.sitemap import ELECTION_ID
from scraper.shared.election_results import build_seimo_members_results

# VRK's elected-members page (139 members: 70 list seats and 69
# constituency seats — the two annulled constituencies, Biržų-Kupiškio and
# Zarasų-Visagino, voted again in March 2013), cross-checked against all 71
# constituency pages.
RESULTS_TREE = "2012_seimo_rinkimai"

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    return build_seimo_members_results(
        ELECTION_ID,
        RESULTS_TREE,
        sitemap_path,
        results_dir,
        output_path,
    )
