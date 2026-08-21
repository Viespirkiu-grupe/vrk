from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.prezidento_2009.sitemap import ELECTION_ID
from scraper.shared.election_results import build_presidential_results

# 2009 was decided in the first round (Grybauskaitė, 69.09% of valid
# ballots), so there is no "rezultatai_isankstiniai2" page as in 2014. The
# tree's "Galutiniai rinkimų rezultatai" page (rezultatai/index.html) is a
# certificate-style sentence with the winner's name declined ("išrinko Dalią
# Grybauskaitę Respublikos Prezidente"), which the shared pattern does not
# read; the nationwide vote table one level down ends with the canonical
# "Respublikos Prezidente išrinkta Dalia GRYBAUSKAITĖ" line, so that is the
# page walked.
RESULTS_TREE = "2009_prezidento_rinkimai"
RESULTS_PAGE = "rezultatai_vienmand_apygardose/rezultatai_vienmand_apygardose1turas.html"

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
        results_page=RESULTS_PAGE,
    )
