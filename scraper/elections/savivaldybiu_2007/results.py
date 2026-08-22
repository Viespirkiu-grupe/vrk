from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.savivaldybiu_2007.sitemap import ELECTION_ID
from scraper.shared.election_results import build_municipal_mandates_results

# Sixty municipalities, council seats only, decided in one round. The tree
# is the family's oldest: no output_lt level (the trailing slash says so),
# and instead of per-list ranking pages to count down, each municipality
# publishes a "Mandatus gavę kandidatai" page that names every winner with
# an anketa link — so the seats are read, not derived.
RESULTS_TREE = "2007_savivaldybiu_tarybu_rinkimai/"

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    return build_municipal_mandates_results(
        ELECTION_ID,
        RESULTS_TREE,
        sitemap_path,
        results_dir,
        output_path,
    )
