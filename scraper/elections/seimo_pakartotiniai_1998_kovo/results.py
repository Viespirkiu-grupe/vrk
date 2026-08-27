"""Elected status and votes for the 1998-03-22 Seimo repeat election.

Both constituencies failed their turnout threshold in the only round held —
`rapgpl.htm` gives Naujosios Vilnios (Nr. 10) 14,522 of 39,910 (36.39%) and
`rapgpl2.htm` gives Vilniaus Trakų (Nr. 57) 10,742 of 38,135 (28.17%), each
closing "Rinkimai apygardoje neįvyko." Nobody was elected, so all 11 records
carry a known `isrinktas: false` rather than a null.

**This pair is the family's one results capture with no candidate ids.** Its
rows link `kandvl.htm`, `kandvl2.htm`, `kandvl3.htm` … — a hand-built page,
not the database's `kandvl.htm-<ID>.htm` — so these 11 rows are the only ones
in the family joined by name rather than by id, matched within the
constituency's own field as an unordered token set (the results pages print
the name given-name-first, the listing surname-first).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_pakartotiniai_1998_kovo.sitemap import ELECTION_ID
from scraper.shared.seimo_archive_1990s_results import (
    VRK_STATINIAI_BASE,
    build_constituency_results,
)

RESULTS_ROOT = f"{VRK_STATINIAI_BASE}seimpk/"
PAGES = [
    {"url": f"{RESULTS_ROOT}rapgpl.htm", "round": 1},
    {"url": f"{RESULTS_ROOT}rapgpl2.htm", "round": 1},
]

DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")
DEFAULT_RESULTS_DIR = Path(f"samples/results/{ELECTION_ID}")
DEFAULT_RESULTS_PATH = Path(f"sitemaps/{ELECTION_ID}.results.json")


def build_results(
    sitemap_path: Path = DEFAULT_SITEMAP_PATH,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    output_path: Path = DEFAULT_RESULTS_PATH,
) -> tuple[Path, dict[str, Any]]:
    return build_constituency_results(ELECTION_ID, PAGES, sitemap_path, results_dir, output_path)
