from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.savivaldybiu_2015.sitemap import ELECTION_ID
from scraper.shared.election_results import build_municipal_results

# Sixty municipalities: 57 mayors (Širvintos, Šilutė and Trakai elected
# none that stood) and 1,464 council seats, of which the 48 in Šilutė and
# Trakai were annulled by VRK decision before anyone was seated and are
# flagged as such (the June repeat elections carry the real winners).
RESULTS_TREE = "2015_savivaldybiu_tarybu_rinkimai"
COMPOSITION_TREE = "2015_savivaldybiu_tarybu_rinkimai"

# Results VRK declared void after publishing them; see the decisions named.
ANNULMENTS = {
    "47. Šilutės rajono": {"scope": "all", "decision": "VRK 2015-03-21 sprendimas Sp-126 (rinkimų rezultatai Šilutės rajono savivaldybėje pripažinti negaliojančiais)"},
    "52. Trakų rajono": {"scope": "all", "decision": "VRK 2015-03-08 sprendimas Sp-101 (rinkimų rezultatai Trakų rajono savivaldybėje pripažinti negaliojančiais)"},
    "48. Širvintų rajono": {"scope": "mayor", "decision": "VRK 2015-03-21 sprendimas Sp-121 (mero rinkimų rezultatai Širvintų rajono apygardoje Nr. 48 pripažinti negaliojančiais)"},
}

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
        annulments=ANNULMENTS,
    )
