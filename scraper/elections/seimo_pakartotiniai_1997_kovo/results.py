"""Elected status and votes for the 1997-03-23 Seimo repeat election.

VRK's `seimpk` index links this election's results through `rapgsarl.htm`,
which names one page per constituency — `rapgp201.htm` … `rapgp204.htm`, a
filename this election alone uses. **Those four pages are mojibake**: that
capture's Windows-1257 bytes were re-encoded as Latin-1 HTML entities, so
"Mečislav Vaškovič" arrives as "Me&egrave;islav Va&eth;kovi&egrave;"; the shared
parser repairs it (see `scraper/shared/seimo_archive_1990s_results.py`). They
also head their table "Paduotų balsų skaičius / balsadėžėse rastų / paštu
gautų / iš viso" instead of the family's usual "Gautų balsų skaičius /
Apygardoje / Pašte / Iš viso", and carry no round heading at all — the round
is supplied here.

**This election elected two people**, which no earlier note on the family
recorded: Jan Senkevič outright in Vilniaus-Šalčininkų (Nr. 56), where the
page closes "Į Seimo narius išrinktas Jan Senkevič", and Danutė Aleksiūnienė
in the Trakų (Nr. 58) runoff held three weeks later on 1997-04-13
(`rapgpl.htm-204+2.htm`, "Seimo nariu išrinktas Danutė Aleksiūnienė"). The
`seimpk` index lists that runoff as its own item; it is the second round of
this election, so it is read here. Naujosios Vilnios (Nr. 10) and Vilniaus
Trakų (Nr. 57) failed their turnout threshold and went to the 1998-03-22
repeat.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.elections.seimo_pakartotiniai_1997_kovo.sitemap import ELECTION_ID
from scraper.shared.seimo_archive_1990s_results import (
    VRK_STATINIAI_BASE,
    build_constituency_results,
)

RESULTS_ROOT = f"{VRK_STATINIAI_BASE}seimpk/"
PAGES = [
    {"url": f"{RESULTS_ROOT}rapgp201.htm", "round": 1},
    {"url": f"{RESULTS_ROOT}rapgp202.htm", "round": 1},
    {"url": f"{RESULTS_ROOT}rapgp203.htm", "round": 1},
    {"url": f"{RESULTS_ROOT}rapgp204.htm", "round": 1},
    {"url": f"{RESULTS_ROOT}rapgpl.htm-204+2.htm", "round": 2},
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
