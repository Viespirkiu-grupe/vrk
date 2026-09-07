"""The municipality join: one id per municipal body, every published spelling an alias.

The corpus has no municipality identifier that crosses elections. The 2019 and
2023 listings carry VRK's numeric `id` for the municipality, the 2000 and 2002
cards a different `savivaldybesId`, and the other eras a name alone -- and the
name is worded per era: 'Vilniaus miesto' on the 1997/2000/2002/2019/2023
cards, 'Vilniaus miesto savivaldybė' on 2007/2011/2015, 'Palangos savivaldybė'
in 2011 alone, 'Birštono miesto' in 1997 when Birštonas was still a city
municipality. Passed through verbatim (issue #137), all 60 municipalities
appeared twice in the dashboard facet and in the shipped `municipality`
column, 98,045 of 99,594 candidacies under a split name.

`scraper/municipalities.json` is the registry, built the way the party
registry was (issue #82): one entry per body, the official name, and every
form the corpus publishes as an alias. Matching never guesses -- a form is
normalised (whitespace, the mayoral cards' constituency number suffix) and
then has to be an entry's exact alias; anything else is None and a red test
(`tests/test_municipality_registry.py` holds `docs/municipality-forms.tsv`,
the measured form table, to exactly one entry each).

`savivaldybe(raw)` is what `scraper/shared/kandidatura.py` calls for every
record: the id, the canonical name, and the published string it started from.
The records themselves are never rewritten.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "scraper" / "municipalities.json"

#: The constituency number the mayoral-election profile cards append to the
#: municipality ("Telšių rajono (Nr. 51)", "Jonavos rajono (10)"), which the
#: municipal generals' own field never carries.
_NUMBER_SUFFIX = re.compile(r"\s*\((Nr\.\s*)?\d+\)\s*$")

KINDS = ("miesto", "rajono", "savivaldybe")


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def entries() -> dict[str, dict[str, Any]]:
    return load_registry()["entries"]


def entry(municipality_id: str) -> dict[str, Any]:
    return entries()[municipality_id]


def normalize_form(text: str) -> str:
    """The published string with nothing but presentation removed: NFC,
    whitespace collapsed, the mayoral cards' number suffix stripped. No case
    folding and no de-inflection -- the aliases are explicit."""
    folded = unicodedata.normalize("NFC", text).replace("\xa0", " ")
    folded = " ".join(folded.split())
    return _NUMBER_SUFFIX.sub("", folded).strip()


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for municipality_id, data in entries().items():
        for form in (data["name"], *data.get("aliases", [])):
            key = normalize_form(form)
            if key in index and index[key] != municipality_id:
                raise ValueError(f"{form!r} is claimed by both {index[key]} and {municipality_id}")
            index[key] = municipality_id
    return index


def match(raw: Any) -> str | None:
    """The registry id the published form belongs to, or None when no entry
    claims it. Accepts the {id, number, name} dict of the 2019/2023 listings
    as well as the plain string of every other era."""
    if isinstance(raw, dict):
        raw = raw.get("name")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _alias_index().get(normalize_form(raw))


def savivaldybe(raw: Any) -> dict[str, Any]:
    """The derived municipality concept for one published value:

        {"savivaldybe-id":  registry id or None,
         "savivaldybe":     the canonical official name, or the published
                            form with the number suffix stripped when no
                            entry claims it (so a new spelling still joins
                            with itself, and the test catches it),
         "savivaldybe-raw": the string as the record carries it}
    """
    if isinstance(raw, dict):
        raw = raw.get("name")
    if not isinstance(raw, str) or not raw.strip():
        return {"savivaldybe-id": None, "savivaldybe": None, "savivaldybe-raw": None}
    municipality_id = match(raw)
    return {
        "savivaldybe-id": municipality_id,
        "savivaldybe": entry(municipality_id)["name"] if municipality_id else normalize_form(raw),
        "savivaldybe-raw": raw.strip(),
    }
