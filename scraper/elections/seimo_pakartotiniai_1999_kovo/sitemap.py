"""Sitemap building for the 1999-03-21 Seimo repeat election.

VRK re-ran the vote in three constituencies at once -- Naujosios Vilnios
(No. 10), Nevėžio (No. 26) and Vilniaus Trakų (No. 57) -- named as one
election on this election's own index page,
https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/19990321/index.html:

    1999 m. kovo 21 d. pakartotiniai rinkimai Naujosios Vilnios, Nevėžio ir
    Vilniaus-Trakų apygardose

**This is the family's first directory outside `seim96`/`seimpk`.** The
directory is date-named -- `19990321`, the convention `savivaldybiu_2000`
(`20000319`) and `seimo_2000` (`20001008`) also follow -- but the *pages* are
still the 1996-1998 archive layout, not the 2000 one:
`apgtl.htm-<phase>+<constituency>.htm` listings with `Pavardė, vardas` /
`Iškėlė` columns, `kandvl.htm-<ID>.htm` cards with the malformed
`<!--sql format>` comment, `partr2l.htm` nominators. The shared module takes
the directory as a parameter, so it needed no change: a date-named directory
says nothing about which layout family a page belongs to, and this election is
the counter-example that proves it.

Phase prefix `11` (`apgtl.htm-11+<constituency>.htm`). All 22 cards link both
a biography and a declaration -- the most complete of the four by-elections of
this era.

All three constituencies failed the turnout threshold; Nr. 10 drew 7,967 of
40,215 (19.81%), the lowest of any election in this family. Each `rapgpl` page
closes "Rinkimai apygardoje neįvyko", so `isrinktas` is a known `false` for
all 22 -- but this family publishes no elected marker on the pages it parses;
see `docs/DATASET.md` for where that decision stands.
"""

from __future__ import annotations

from pathlib import Path

from scraper.shared.seimo_archive_1990s import (
    build_sitemap_from_targets,
    constituency_url,
    fetch_listing_sample_for_targets,
)

ELECTION_ID = "1999-kovo-21-seimo-pakartotiniai"
DIRECTORY = "19990321"
PHASE = "11"
CONSTITUENCIES = [10, 26, 57]

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
            "Naujosios Vilnios (10), Nevėžio (26) and Vilniaus Trakų (57) constituencies, "
            "named as one election on "
            "https://www.vrk.lt/statiniai/puslapiai/n/rinkimai/19990321/index.html"
        ),
    )
