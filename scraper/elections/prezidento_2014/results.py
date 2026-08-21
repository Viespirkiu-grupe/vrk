from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.prezidento_2014.sitemap import ELECTION_ID
from scraper.shared.election_results import build_presidential_results

# The final-results page's own sentence, after the second round.
RESULTS_TREE = "2014_prezidento_rinkimai"

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    return build_presidential_results(
        ELECTION_ID,
        RESULTS_TREE,
        sitemap_path,
        results_dir,
        output_path,
    )
