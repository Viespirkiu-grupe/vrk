"""The single-mandate constituency, one name per district across four label eras.

`kandidatura()` resolves the constituency a Seimas candidate stood in from
whichever field the era's page carries, and the eras spell it four ways
(issue #133 measured 315 distinct labels over 9,309 candidacies):

    1996-1999 archive     "Akmenės Joniškio"              no dash at all
    2000-2012 cards       "Akmenės - Joniškio"            spaced hyphen, and
                          "Aukštaitijos (Nr. 28)"         a number in brackets
    2016 profile cards    "Aukštaitijos Nr. 33"           bare number
    2020-2024 cards       "33. Aukštaitijos"              number first
    a 2023 by-election    "Raseinių–Kėdainių( 42)"        VRK's own typo

The name is the district; the number is the district's *number in that
election*, and it moves (Aukštaitijos was Nr. 28 until 2012 and Nr. 33 from
2016). So the two are separated: `normalize_name` strips every number
decoration and writes every dash form as VRK's own en dash without spaces,
and `number_of` reads the number. The sixteen archive-era labels that drop
the dash altogether ("Akmenės Joniškio") are an explicit alias table,
because no rule tells "Akmenės Joniškio" (two districts joined) from
"Šiaulių kaimiškoji" (one district, two words).

What this does not do is claim that a name is one boundary: Kėdainių in
2000 and Kėdainių in 2020 are the same name on different maps, and the
2016 reform renamed most districts outright (Kelmės–Šilalės, Sėlos rytinė).
A consumer who needs the boundary joins on (election, number); the name is
for reading and for the dashboard's facet, where 315 raw forms become 136
districts by name. `docs/constituency-forms.tsv` is the measured table of
every published form and what it resolves to.

A name can now map to more than one entry (issue #219). Where two
consecutive maps a name was used in share no municipality, the name was
reused for a different place, and the facet splits it into eras: Dainavos was
a Kaunas city district through 2016 and is the Alytaus r., Prienų r. and
Birštonas district from 2020, so its candidacies go to "Dainavos (iki 2016)"
or "Dainavos (nuo 2020)". `entry_of(name, election_id)` is that step, by the
map the election ran on (a by-election's is its term's general election,
scraper/elections.json `parent`); every other name is its own one entry.
`normalize_name` and the `apygarda` field stay the plain name VRK prints.

`counties_of(name)` is the one place a name gets a county (issue #217):
scraper/constituency_counties.json, derived from VRK's per-election precinct
lists by scripts/build_constituency_counties.py -- every county any map of
that entry reached, since the facet is a name across maps -- and `groups_of`
the filter groups it is listed in, a big city's for every map whose precincts
lie mostly in that city, the counties for the other maps.

"Daugiamandatė" -- the 2000-2012 cards' "Apygarda" row for a candidate who
stood on the list alone -- is not a constituency, and reads as None here;
until this module 2,980 rows of the candidacy table shipped it as one.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

COUNTIES_PATH = Path(__file__).resolve().parents[2] / "scraper" / "constituency_counties.json"
ELECTIONS_PATH = Path(__file__).resolve().parents[2] / "scraper" / "elections.json"

#: A number in any of the label positions: "4. Žirmūnų", "Žirmūnų (Nr. 4)",
#: "Žirmūnų (Nr.4)", "Žirmūnų Nr. 4", "Raseinių–Kėdainių( 42)".
_LEADING_NUMBER = re.compile(r"^\s*(\d+)\.\s*")
_BRACKETED_NUMBER = re.compile(r"\s*\(\s*(?:Nr\.?\s*)?(\d+)\s*\)\s*$")
_TRAILING_NUMBER = re.compile(r"\s+Nr\.?\s*(\d+)\s*$")
_TRAILING_WORD = re.compile(r"\s+apygard(a|oje|os)\s*$", re.IGNORECASE)
_DASH = re.compile(r"\s*[-‐‑‒–—]\s*")

#: The multi-mandate marker the 2000-2012 cards print in the constituency row
#: of a list-only candidate ("Daugiamandatė", "Daugiamandatė, šioje
#: apygardoje išrinktas Seimo nariu.").
_MULTI_MANDATE = "daugiamandat"

#: The 1996-1999 archive's constituency names with the dash dropped: two
#: districts joined, spelled as two words. Explicit, because the rule that
#: would join them cannot tell these from a one-district two-word name.
DASHLESS_ARCHIVE: dict[str, str] = {
    "Akmenės Joniškio": "Akmenės–Joniškio",
    "Aleksoto Vilijampolės": "Aleksoto–Vilijampolės",
    "Anykščių Kupiškio": "Anykščių–Kupiškio",
    "Biržų Kupiškio": "Biržų–Kupiškio",
    "Ignalinos Švenčionių": "Ignalinos–Švenčionių",
    "Kauno Kėdainių": "Kauno–Kėdainių",
    "Lazdijų Druskininkų": "Lazdijų–Druskininkų",
    "Molėtų Švenčionių": "Molėtų–Švenčionių",
    "Pakruojo Joniškio": "Pakruojo–Joniškio",
    "Pasvalio Panevėžio": "Pasvalio–Panevėžio",
    "Skuodo Mažeikių": "Skuodo–Mažeikių",
    "Varėnos Eišiškių": "Varėnos–Eišiškių",
    "Vilniaus Trakų": "Vilniaus–Trakų",
    "Vilniaus Šalčininkų": "Vilniaus–Šalčininkų",
    "Šilalės Šilutės": "Šilalės–Šilutės",
    "Širvintų Vilniaus": "Širvintų–Vilniaus",
}


def _clean(text: Any) -> str | None:
    if not isinstance(text, str):
        return None
    folded = unicodedata.normalize("NFC", text).replace("\xa0", " ")
    folded = " ".join(folded.split())
    return folded or None


def is_multi_mandate(text: Any) -> bool:
    """Whether a constituency row says "the list" rather than naming a district."""
    cleaned = _clean(text)
    return bool(cleaned) and cleaned.casefold().startswith(_MULTI_MANDATE)


def number_of(text: Any) -> int | None:
    """The district number the label carries, in any of its positions."""
    cleaned = _clean(text)
    if not cleaned:
        return None
    for pattern in (_LEADING_NUMBER, _BRACKETED_NUMBER, _TRAILING_NUMBER):
        match = pattern.search(cleaned)
        if match:
            return int(match.group(1))
    return None


def normalize_name(text: Any) -> str | None:
    """The district's name alone: numbers and the word "apygarda" stripped,
    every dash form written as an unspaced en dash, the archive's dashless
    spellings joined. None for nothing, and for the multi-mandate marker."""
    cleaned = _clean(text)
    if not cleaned or is_multi_mandate(cleaned):
        return None
    name = _LEADING_NUMBER.sub("", cleaned)
    name = _BRACKETED_NUMBER.sub("", name)
    name = _TRAILING_NUMBER.sub("", name)
    name = _TRAILING_WORD.sub("", name)
    name = _DASH.sub("–", name).strip()
    name = " ".join(name.split())
    return DASHLESS_ARCHIVE.get(name, name) or None


def apygarda(raw: Any, numeris: Any = None) -> dict[str, Any]:
    """The derived constituency for one published label:

        {"apygarda":         the district's name, None for a list-only row,
         "apygardos-numeris": the number -- the record's own field where the
                              era carries one, else the one in the label,
         "apygarda-raw":     the label as published}
    """
    cleaned = _clean(raw)
    number = numeris if isinstance(numeris, int) and not isinstance(numeris, bool) else None
    if number is None and isinstance(numeris, str) and numeris.strip().isdigit():
        number = int(numeris.strip())
    if number is None:
        number = number_of(cleaned)
    name = normalize_name(cleaned)
    return {
        "apygarda": name,
        "apygardos-numeris": number if name is not None else None,
        "apygarda-raw": cleaned,
    }


@lru_cache(maxsize=1)
def load_counties() -> dict[str, Any]:
    return json.loads(COUNTIES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _map_years() -> dict[str, str]:
    """Every election id -> the year of the precinct-list map it ran on: a
    general election's own, a by-election's through its `parent`."""
    sources = {source["election"]: year for year, source in load_counties()["sources"].items()}
    registry = json.loads(ELECTIONS_PATH.read_text(encoding="utf-8"))["elections"]
    return {
        entry["id"]: sources[entry.get("parent") or entry["id"]]
        for entry in registry
        if (entry.get("parent") or entry["id"]) in sources
    }


def entry_of(name: str | None, election_id: str | None) -> str | None:
    """The facet entry a candidacy's constituency belongs to: the name
    itself, or -- for a name reused for a different place (`eras` in
    scraper/constituency_counties.json) -- the era whose maps include the
    one `election_id` ran on. A split name on an election no source map
    covers raises, so a new map is a red build, not a silent guess."""
    if not name:
        return None
    labels = load_counties().get("eras", {}).get(name)
    if not labels:
        return name
    year = _map_years().get(election_id or "")
    for label in labels:
        if year in load_counties()["entries"][label]["maps"]:
            return label
    raise ValueError(f"{name!r} is split into eras {labels}, and {election_id!r} ran on none of their maps")


def counties_of(name: str | None) -> list[str]:
    """The counties (apskritys) the named entry (`entry_of`) lies in, in the municipality
    registry's population order; more than one for a district that crossed a
    county line on any map, and empty for a name the file gives no county
    (Pasaulio lietuvių, the district abroad) or does not know."""
    entry = load_counties()["entries"].get(name) if name else None
    return list(entry["counties"]) if entry else []


def groups_of(name: str | None) -> list[str]:
    """The filter groups the named entry (`entry_of`) is listed in (issue #217), decided
    per map: "Kauno miestas" for a map whose precincts lie mostly in Kaunas
    city, "Kauno apskritis" (and every other county touched) for any other
    map; the union over the name's maps. Empty where the file has no county."""
    entry = load_counties()["entries"].get(name) if name else None
    return list(entry["groups"]) if entry else []


def group_order() -> list[str]:
    """Every filter group in display order: each big city's just ahead of its
    county's, the counties in the municipality registry's population order."""
    return list(load_counties()["groupOrder"])
