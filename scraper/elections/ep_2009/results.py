from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.ep_2009.sitemap import ELECTION_ID
from scraper.shared.election_results import build_ep_results

# VRK's elected-members page (12 seats, anketa ids on the page). The 2009
# tree files it as rezultatai/index.html, where 2014's is
# rezultatai/rezultatai.html.
RESULTS_TREE = "2009_ep_rinkimai"
MEMBERS_PAGE = "rezultatai/index.html"

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    return build_ep_results(
        ELECTION_ID,
        RESULTS_TREE,
        sitemap_path,
        results_dir,
        output_path,
        members_page=MEMBERS_PAGE,
    )
