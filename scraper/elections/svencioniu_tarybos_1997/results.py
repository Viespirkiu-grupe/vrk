"""Elected status for the 1997-06-29 Švenčionys council repeat election.

One municipality, so one results pair: the retained `apgtl-47.html` (phase
5) links `rapgpl.htm-264.htm`, which links `rikl.htm-264.htm` — the 25
council members actually seated in Švenčionys, replacing the invalidated
March result. See `scraper/shared/savivaldybiu_archive_1997_results.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.svencioniu_tarybos_1997.sitemap import (
    DEFAULT_MUNICIPALITIES_DIR,
    ELECTION_ID,
)
from scraper.shared.savivaldybiu_archive_1997_results import (
    build_municipal_results,
    municipal_results_targets,
)

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    targets = municipal_results_targets(DEFAULT_MUNICIPALITIES_DIR)
    return build_municipal_results(
        ELECTION_ID, targets, sitemap_path, results_dir, output_path
    )
