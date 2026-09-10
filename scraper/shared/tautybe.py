"""Declared nationality (tautybė), folded from its 117 spellings to one name per group.

The questionnaire asks it on 30 years of forms -- `anketa.tautybe` up to 2019,
`biografija.tautybe` from 2020 -- and the candidates answer in their own
words: 89,154 answers in 117 spellings, measured 2026-09-11 (issue #162).
Nearly all of the variety is form, not substance: the grammatical gender
("Lietuvis", "Lietuvė"), the case ("LENKĖ", "lenkė"), and the "(-ė)" the
2016-on form prints after a masculine answer ("Lietuvis (-ė)"). Folded, they
are 45 groups.

Each group is named the way Statistics Lithuania names a nationality in the
census -- the plural nominative, lower case: "lietuviai", "lenkai",
"ukrainiečiai". Two answers are kept as their own groups rather than folded
into a larger one, because folding would say more than the candidate did:
"žemaitis" (Samogitian, an ethnographic group of Lithuanians, 15 answers) and
the one "Indijos ir Pakistano tautybės". "Čigonas" is named "romai
(čigonai)", the census's own wording.

The record keeps the candidate's spelling; this is the derived layer the
candidacy table and the dashboard aggregate on, and the minority-representation
series the corpus can answer across 1996-2025. It is ethnic-origin data, a
special category of personal data: docs/PERSONAL_DATA.md records what is
surfaced and why.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

#: group id -> (display name, the spellings that fold to it once
#: `fold_spelling` has lower-cased them and dropped the "(-ė)").
GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "lietuviai": ("lietuviai", ("lietuvis", "lietuvė")),
    "zemaiciai": ("žemaičiai", ("žemaitis",)),
    "lenkai": ("lenkai", ("lenkas", "lenkė")),
    "rusai": ("rusai", ("rusas", "rusė")),
    "baltarusiai": ("baltarusiai", ("baltarusis", "baltarusė", "baltarusas")),
    "ukrainieciai": ("ukrainiečiai", ("ukrainietis", "ukrainietė")),
    "zydai": ("žydai", ("žydas", "žydė")),
    "latviai": ("latviai", ("latvis", "latvė")),
    "vokieciai": ("vokiečiai", ("vokietis", "vokietė")),
    "totoriai": ("totoriai", ("totorius", "totorė")),
    "karaimai": ("karaimai", ("karaimas", "karaimė")),
    "armenai": ("armėnai", ("armėnas", "armėnė")),
    "gruzinai": ("gruzinai", ("gruzinas", "gruzinė", "grusė")),
    "azerbaidzanieciai": ("azerbaidžaniečiai", ("azerbaidžanietis",)),
    "lezginai": ("lezginai", ("lezginas",)),
    "talysai": ("talyšai", ("talyšas",)),
    "ingusai": ("ingušai", ("ingušas",)),
    "kazachai": ("kazachai", ("kazachas",)),
    "uzbekai": ("uzbekai", ("uzbekas", "uzbekė")),
    "baskirai": ("baškirai", ("baškiras",)),
    "ciuvasai": ("čiuvašai", ("čiuvašas",)),
    "udmurtai": ("udmurtai", ("udmurtas",)),
    "mariai": ("mariai", ("mari",)),
    "komiai": ("komiai", ("komė",)),
    "moldavai": ("moldavai", ("moldavas", "moldava")),
    "estai": ("estai", ("estas", "estė")),
    "suomiai": ("suomiai", ("suomis",)),
    "vengrai": ("vengrai", ("vengras",)),
    "cekai": ("čekai", ("čekas",)),
    "slovakai": ("slovakai", ("slovakė",)),
    "graikai": ("graikai", ("graikas", "graikė")),
    "italai": ("italai", ("italas",)),
    "ispanai": ("ispanai", ("ispanas", "ispanė")),
    "prancuzai": ("prancūzai", ("prancūzas",)),
    "anglai": ("anglai", ("anglas", "anglė")),
    "airiai": ("airiai", ("airis",)),
    "turkai": ("turkai", ("turkas",)),
    "libanieciai": ("libaniečiai", ("libanietis",)),
    "vietnamieciai": ("vietnamiečiai", ("vietnamietis",)),
    "etiopai": ("etiopai", ("etiopė",)),
    "afrikaneriai": ("afrikaneriai", ("afrikanerė",)),
    "cilieciai": ("čiliečiai", ("čilietis",)),
    "kolumbieciai": ("kolumbiečiai", ("kolumbietis",)),
    "romai": ("romai (čigonai)", ("čigonas",)),
    "indijos-ir-pakistano": ("Indijos ir Pakistano tautybės", ("indijos ir pakistano tautybės",)),
}

#: spelling -> group id, built once from GROUPS.
_GROUP_OF = {spelling: group for group, (_, spellings) in GROUPS.items() for spelling in spellings}

#: The "(-ė)" suffix the 2016-on form prints after a masculine answer, in any
#: of its three printings: "(-ė)", "( -ė)" and "(-ė)" glued to the word.
_FEMININE_SUFFIX = re.compile(r"\(\s*-\s*ė\s*\)")


def fold_spelling(value: str) -> str:
    """"Lietuvis (-ė)", "LIETUVIS" and "lietuvis" -> "lietuvis"."""
    text = unicodedata.normalize("NFC", value).casefold()
    text = _FEMININE_SUFFIX.sub(" ", text)
    return " ".join(text.split())


def tautybe(value: Any) -> dict[str, str] | None:
    """{"id", "label"} of the group a declared nationality belongs to.

    None for no answer. An answer no group claims yet returns id None and the
    folded spelling as its label, so it is shown rather than hidden. The
    person index build reports it as a problem, because until GROUPS gets the
    spelling it would be a facet row of its own.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    folded = fold_spelling(value)
    group = _GROUP_OF.get(folded)
    if group is None:
        return {"id": None, "label": folded}
    return {"id": group, "label": GROUPS[group][0]}
