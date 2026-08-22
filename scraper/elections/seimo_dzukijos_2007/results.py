from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_dzukijos_2007.sitemap import ELECTION_ID
from scraper.shared.election_results import build_seimo_constituency_results

# One constituency, decided in round two by plurality (the 2007 pages state
# no verdict). The tree has no output_lt level and keeps its round-two
# index and page in the round-one folder; the trailing slash tells the
# walker the first, and it falls back for the second.
RESULTS_TREE = "2007_seimo_rinkimai/"

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    return build_seimo_constituency_results(
        ELECTION_ID,
        RESULTS_TREE,
        sitemap_path,
        results_dir,
        output_path,
    )
