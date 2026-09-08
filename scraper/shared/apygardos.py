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

"Daugiamandatė" -- the 2000-2012 cards' "Apygarda" row for a candidate who
stood on the list alone -- is not a constituency, and reads as None here;
until this module 2,980 rows of the candidacy table shipped it as one.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

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
