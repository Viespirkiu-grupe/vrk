"""Elected status for the 1997-03-23 municipal council general election.

Each of the 56 municipality pages already retained under
`samples/html/<id>/municipalities/` links its own `rapgpl.htm-<code>.htm`
results page, which in turn links the `rikl.htm-<code>.htm` elected page —
so the target list is read off the samples rather than derived (the code is
VRK's internal id, 144–199, not the municipality number). One municipality
returns no winners: Švenčionių rajono (Nr. 47), whose March result VRK
invalidated and re-ran on 1997-06-29 (`svencioniu_tarybos_1997`); its
candidates' `isrinktas` is a known `false` by VRK's own decision, which the
records carry under `rezultatai-negalioja`. See
`scraper/shared/savivaldybiu_archive_1997_results.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.savivaldybiu_1997.sitemap import (
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
