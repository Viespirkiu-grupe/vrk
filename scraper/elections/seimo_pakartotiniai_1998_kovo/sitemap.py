"""Sitemap building for the 1998-03-22 Seimo repeat election.

VRK re-ran the vote in two constituencies at once -- Naujosios Vilnios
(No. 10) and Vilniaus Trakų (No. 57) -- and the `seimpk` by-elections index
page (https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seimpk/index.html)
names them as **one** election, not two:

    1998 m. kovo 22 d. pakartotiniai rinkimai Naujosios Vilnios ir
    Vilniaus-Trakų apygardose

So this is one module over both, exactly as `seimo_pakartotiniai_1997_kovo`
covers its four. (GitHub carried the two constituencies as separate tickets,
#21 and #22; #22 was closed as a duplicate on that reading.) No directory page
covers only these two, so they are hardcoded here rather than crawled. The
candidate pages are the same 1996-1998 Seimas archive layout
(`scraper/shared/seimo_archive_1990s.py`), under the `seimpk` directory and
phase prefix `8` (`apgtl.htm-8+<constituency>.htm`).

Two things about this election that look like scrape failures and are not:

- **Only 2 of the 11 cards link a declaration.** Every one links `biogr.htm`;
  `kpdl.htm` is the exception here, where the other by-elections of this era
  are 11/11 (1998-11-15) and 22/22 (1999-03-21). So most records carry no
  `turto-ir-pajamu-deklaracijos` block at all.
- **Both constituencies failed the turnout threshold.** `rapgpl.htm` gives
  Nr. 10 14,522 of 39,910 (36.39%) and `rapgpl2.htm` gives Nr. 57 10,742 of
  38,135 (28.17%), each closing "Rinkimai apygardoje neįvyko." No one was
  elected, so `isrinktas` is a known `false` -- but this family publishes no
  elected marker on the pages it parses, and adding a results reader is a
  decision for the family rather than for one module; see `docs/DATASET.md`.
"""

from __future__ import annotations

from pathlib import Path

from scraper.shared.seimo_archive_1990s import (
    build_sitemap_from_targets,
    constituency_url,
    fetch_listing_sample_for_targets,
)

ELECTION_ID = "1998-kovo-22-seimo-pakartotiniai"
DIRECTORY = "seimpk"
PHASE = "8"
CONSTITUENCIES = [10, 57]

DEFAULT_SAMPLE_PATH = Path(f"samples/html/{ELECTION_ID}/list.html")
DEFAULT_CONSTITUENCIES_DIR = Path(f"samples/html/{ELECTION_ID}/constituencies")
DEFAULT_SITEMAP_PATH = Path(f"sitemaps/{ELECTION_ID}.json")

TARGETS = [
    {"constituency": number, "url": constituency_url(DIRECTORY, PHASE, number)}
    for number in CONSTITUENCIES
]


def fetch_listing_sample(sample_path: Path = DEFAULT_SAMPLE_PATH) -> Path:
    return fetch_listing_sample_for_targets(TARGETS, sample_path, DEFAULT_CONSTITUENCIES_DIR)


def build_sitemap_from_sample(
    sample_path: Path | None = None,
    output_path: Path = DEFAULT_SITEMAP_PATH,
) -> tuple[Path, dict[str, int]]:
    del sample_path  # unused: see fetch_listing_sample's docstring
    return build_sitemap_from_targets(
        DEFAULT_CONSTITUENCIES_DIR,
        output_path,
        election_id=ELECTION_ID,
        source_description=(
            "Naujosios Vilnios (10) and Vilniaus Trakų (57) constituencies, named as one "
            "election on https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/seimpk/index.html"
        ),
    )
