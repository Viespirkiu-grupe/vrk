from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.savivaldybiu_2011.sitemap import ELECTION_ID
from scraper.shared.election_results import build_municipal_results

# Sixty municipalities, council seats only — no mayor was elected directly
# before 2015, so there is no mayoral field on any results page and the
# municipality's mandate total is the whole council. Seats go to each
# list's top-M post-preference ranks, as in 2015, and to the self-nominated
# individuals whose own row on the results table carries a mandate.
RESULTS_TREE = "2011_savivaldybiu_tarybu_rinkimai"
COMPOSITION_TREE = "2011_savivaldybiu_tarybu_rinkimai"

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    return build_municipal_results(
        ELECTION_ID,
        RESULTS_TREE,
        sitemap_path,
        results_dir,
        output_path,
        composition_tree=COMPOSITION_TREE,
    )
