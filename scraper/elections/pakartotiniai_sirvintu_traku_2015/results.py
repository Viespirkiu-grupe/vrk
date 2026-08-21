from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.pakartotiniai_sirvintu_traku_2015.sitemap import ELECTION_ID
from scraper.shared.election_results import build_municipal_results

# Širvintos: the mayor only (round one). Trakai: mayor (round two) and the
# 24 council seats. The composition tree is the March election's, whose
# Trakai page describes this June council.
RESULTS_TREE = "2015_2_savivaldybiu_tarybu_rinkimai"
COMPOSITION_TREE = "2015_savivaldybiu_tarybu_rinkimai"

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
