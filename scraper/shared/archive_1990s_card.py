"""The labelled-card grammar shared by both 1996-1998 archive families.

The Seimas archive (`scraper/shared/seimo_archive_1990s.py`) and the 1997
municipal archive (`scraper/shared/savivaldybiu_archive_1997.py`) are the
same site generation, and their `kandvl.htm` candidate cards print the same
questionnaire grammar:

    <p>Label: <b>value</b></p>
    <p>Užsienio kalbos: <b>Anglų</b> <b>Rusų</b></p>          -- one <b> per value
    <p>Šeimos nariai: <b>Marta</b> - Sutuoktinis/sutuoktinė</p>  -- value plus relation

The two differ only in how densely the labels are packed. The municipal card
runs several labels through one paragraph ("Gimimo data: ... Gimimo vieta:
... Gyvenamoji vieta: ... Tautybė: ..."), so reading a value there means
knowing where the *next* label starts -- that is what `field_value` is for.
The Seimas card gives each questionnaire label its own paragraph (measured:
0 of the 906 retained pages put two of these labels in one paragraph), and
puts three of its fields inside a broken HTML comment instead, so it reads
`<b>` runs directly and recovers the commented ones by regex.

`FIELD_LABELS` is deliberately the *union* of every label either family
prints, not a per-family list. `field_value` stops at whichever other label
comes next, so a label missing from the tuple is not merely unread -- it gets
swallowed into the preceding field's value. The comment on `field_value`
records what that cost the first time.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import NavigableString, Tag

from scraper.shared.values import clean_value, is_refusal


def normalize_space(value: str) -> str:
    return " ".join(value.split())


# Every labelled field either family's card can print, in any paragraph.
# `field_value` stops at whichever of these comes next rather than at a
# caller-named successor: most candidates omit some labels (only 582 of 6,276
# in the 1997 municipal general election print "Gimimo vieta", for instance),
# and a stop list naming just the expected next label silently ran to the end
# of the paragraph whenever that label was absent -- which put
# "1945 04 17 Gyvenamoji vieta: Kaunas Tautybė: Lietuvis (-ė)" into 91% of
# birth-date values.
#
# The last four are the Seimas card's additions. They were missing here until
# 2026-08-26, which cost the municipal family 156 `Moksliniai laipsniai` and
# 112 `Moksliniai vardai` values in the 1997 general election alone -- not
# read wrong, just never read, since on both cards they sit in their own
# paragraphs.
FIELD_LABELS = (
    "Gimimo data",
    "Gimimo vieta",
    "Gyvenamoji vieta",
    "Tautybė",
    "Išsilavinimas",
    "Užsienio kalbos",
    "Pagrindinė darbovietė",
    "Visuomeninė veikla",
    "Šeimyninė padėtis",
    "Šeimos nariai",
    "Moksliniai laipsniai",
    "Moksliniai vardai",
    "Buvo išrinktas",
    "Ką dar norėtų parašyti apie save",
    "Apygarda",
    "Iškėlė",
    "Numeris sąraše",
)

# The "Buvo išrinktas" paragraph spells its label out in full -- "Buvo
# išrinktas į Lietuvos Respublikos Aukščiausiąją Tarybą, Seimą, savivaldybių
# tarybas:" -- so the short prefix in FIELD_LABELS is enough to dispatch a
# paragraph but would never match as a *stop* label, whose pattern expects the
# colon right after. This tail closes that gap; `[^:]*` cannot run past the
# label's own colon, so it stops exactly where the value begins.
LABEL_TAILS = {"Buvo išrinktas": r"[^:]*"}
PREVIOUSLY_ELECTED_LABEL = "Buvo išrinktas"

# Relation vocabulary of the "Šeimos nariai" list, for the two concepts the
# corpus keys separately. Measured over all 906 Seimas-archive cards: Vaikas
# 1,398, Sutuoktinis/sutuoktinė 649, Augintinis (ė) 2, Anūkas (ė) 2 -- the
# last two belong to neither concept and stay in `seimos-nariai` only.
SPOUSE_RELATIONS = {"sutuoktinis/sutuoktinė", "sutuoktinis", "sutuoktinė"}
CHILD_RELATIONS = {"vaikas"}


def field_value(plain: str, label: str) -> str:
    """One label's value out of a paragraph's plain text, stopping at
    whichever *other* label of `FIELD_LABELS` comes next."""
    others = "|".join(
        re.escape(other) + LABEL_TAILS.get(other, "")
        for other in FIELD_LABELS
        if other != label
    )
    pattern = rf"{re.escape(label)}{LABEL_TAILS.get(label, '')}:\s*(.*?)(?:\s*(?:{others}):|$)"
    match = re.search(pattern, plain)
    if match is None:
        return ""
    # The card writes its lists with a separator after the last item as often
    # as not ("...,valdybos narys;"); the corpus-wide value rules take it off
    # here, where a card field is first read (scraper/shared/values.py).
    return clean_value(match.group(1).strip()) or ""


def bold_values(paragraph: Tag) -> list[dict[str, Any]]:
    """Each non-empty `<b>` of a field paragraph with the plain text trailing
    it up to the next `<b>` ("<b>Marta</b> - Sutuoktinis/sutuoktinė").

    Same reader as `scraper/elections/seimo_2000/anketa_parser._bold_values`
    -- the 2000 card is this card's next generation and kept the shape.
    """
    items: list[dict[str, Any]] = []
    for bold in paragraph.find_all("b"):
        value = clean_value(normalize_space(bold.get_text(" ", strip=True)))
        if not value:
            continue
        trail: list[str] = []
        sibling = bold.next_sibling
        while sibling is not None and not (isinstance(sibling, Tag) and sibling.name == "b"):
            if isinstance(sibling, NavigableString):
                trail.append(str(sibling))
            elif isinstance(sibling, Tag) and sibling.name != "br":
                trail.append(sibling.get_text(" ", strip=True))
            sibling = sibling.next_sibling
        note = normalize_space(" ".join(trail)).strip(" -\u2013\u00a0")
        items.append({"value": value, "note": note or None})
    return items


def education_record(education: str) -> dict[str, Any] | None:
    """Wrap this era's one-word education level in the corpus's shape.

    Every election from 2007 on publishes `issilavinimas` as
    `{"aprasas", "irasai": [...]}`, each entry carrying `issilavinimas`,
    `mokymo-istaigos-pavadinimas`, `specialybe` and `baigimo-metai`. Both
    1990s archive cards publish a single level from a controlled list instead
    -- "Aukštasis", "Aukštesnysis", "Specialus vidurinis", "Vidurinis",
    "Nebaigtas aukštasis", "Nebaigtas vidurinis", "Aspirantūra",
    "Doktorantūra" -- which is exactly the modern entry's `issilavinimas`
    field, so it goes there and the three the page does not publish are null.
    Same value, corpus shape, and one less special case downstream.

    Deliberately *not* `aprasas`: that slot is the modern form's free-text
    description of a schooling history, and putting a controlled level in it
    would make the two incomparable.
    """
    if not education:
        return None
    return {
        "aprasas": None,
        "irasai": [
            {
                "issilavinimas": education,
                "mokymo-istaigos-pavadinimas": None,
                "specialybe": None,
                "baigimo-metai": None,
            }
        ],
    }


def previously_elected_record(values: list[str]) -> dict[str, Any] | None:
    """"Buvo išrinktas į ... Aukščiausiąją Tarybą, Seimą, savivaldybių
    tarybas" in the corpus's `anksciau-isrinktas` shape.

    The card names bodies only ("Lietuvos Respublikos Seimas"), one `<b>` per
    body, with no term dates -- so `laikotarpis` is null, exactly as the 2000
    Seimas card's entries are.

    A candidate who wrote VRK's refusal token into this field held no prior
    mandate, and two 1996 records shipped `Nenurodė` as the *name of the body
    they had been elected to* -- the corpus asserting a mandate over a page
    declining to answer (issue #164). A card whose only entry is the refusal
    yields no block at all.
    """
    entries = [value for value in values if not is_refusal(value)]
    if not entries:
        return None
    return {
        "aprasas": None,
        "irasai": [
            {"institucijos-pavadinimas-pareigos": value, "laikotarpis": None} for value in entries
        ],
    }


def family_concepts(members: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """`(sutuoktinio-vardas-pavarde, vaiku-vardai-pavardes)` out of the
    "Šeimos nariai" list, keyed off the relation each entry prints."""
    spouse = [m["name"] for m in members if (m["relation"] or "").lower() in SPOUSE_RELATIONS]
    children = [m["name"] for m in members if (m["relation"] or "").lower() in CHILD_RELATIONS]
    return (", ".join(spouse) or None, ", ".join(children) or None)


def family_members(paragraph: Tag) -> list[dict[str, Any]]:
    """The "Šeimos nariai" paragraph as `[{"name", "relation"}]`."""
    return [
        {"name": item["value"], "relation": item["note"] or ""}
        for item in bold_values(paragraph)
    ]


__all__ = [
    "CHILD_RELATIONS",
    "FIELD_LABELS",
    "PREVIOUSLY_ELECTED_LABEL",
    "SPOUSE_RELATIONS",
    "bold_values",
    "education_record",
    "family_concepts",
    "family_members",
    "field_value",
    "normalize_space",
    "previously_elected_record",
]
