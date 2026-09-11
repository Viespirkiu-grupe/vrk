"""The questionnaire's declarations block (pareiškimai): which answers depart from the usual one.

Every form from 2000 on asks a block of yes/no declarations beside the
conviction question -- another state's citizenship, military service, an
office incompatible with the seat, membership of another state's elected
body, secret collaboration with foreign or Soviet special services, a
mandate lost for violations -- and until issue #162 the corpus's answers to
them reached no consumer. They are concepts in docs/concept-map.json now,
marked `"grupe": "pareiskimai"`, one concept per question with the era-split
keys chained under it.

What makes one answer worth showing is not "Taip". The answer word echoes the
question's verb -- Taip/Ne, Esu/Nesu, Turiu/Neturiu, Einu/Neinu, Yra/Nėra --
and some eras ask in the negative ("Ar neturite nebaigtos atlikti ...
bausmės?"), while the presidential eligibility questions ("Ar esate Lietuvos
Respublikos pilietis pagal kilmę?") expect "Taip". So each concept names its
usual answer class in the map (`iprastas-atsakymas`: `neigiamas` or
`teigiamas`), and an answer outside that class is flagged, word for word as
the candidate gave it. The dashboard's declarations row reads the same two
fields from the same file (`declarationsCell`), and
tests/test_pareiskimai.py holds the two readings together.
"""

from __future__ import annotations

from typing import Any, Callable

GROUP = "pareiskimai"

#: The answer words, lower-cased, by class. A string in neither class is
#: something the candidate wrote instead, and is flagged as given.
NEGATIVE_ANSWERS = frozenset(
    {"ne", "nesu", "neturiu", "neturi", "neinu", "nėra", "nebuvo", "nebuvau", "nesu/nebuvau", "neapribota"}
)
AFFIRMATIVE_ANSWERS = frozenset({"taip", "esu", "turiu", "turi", "einu", "yra", "buvo", "buvau", "esu/buvau"})

#: The states of the candidacy table's `declarations_status`.
NOT_ASKED = "neklausta"
ALL_USUAL = "iprasti"
SOME_FLAGGED = "nukrypstantys"


def answer_class(value: Any) -> str | None:
    """`neigiamas`, `teigiamas`, or None for an answer that is neither."""
    if not isinstance(value, str):
        return None
    word = value.strip().lower()
    if word in NEGATIVE_ANSWERS:
        return "neigiamas"
    if word in AFFIRMATIVE_ANSWERS:
        return "teigiamas"
    return None


def declaration_concepts(concept_map: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """The declaration concepts, in the map's order."""
    return [
        (name, spec)
        for name, spec in concept_map["concepts"].items()
        if spec.get("grupe") == GROUP
    ]


def flagged(
    record: dict[str, Any],
    election_id: str,
    declarations: list[tuple[str, dict[str, Any]]],
    resolve: Callable[[dict[str, Any], Any], Any],
) -> dict[str, str] | None:
    """{concept: answer} for every declaration answered outside its usual class.

    `declarations` is `declaration_concepts(map)`; `resolve` is the concept
    resolver (scripts/field_coverage.concept_value). None when the
    election's form asks none of the declarations (the 1990s archive cards,
    the elections with no questionnaire): "not asked" is not "nothing to
    declare", and the two must not read alike. {} when it asks and every
    answer is the usual one.
    """
    asked = False
    out: dict[str, str] = {}
    for name, spec in declarations:
        path = spec["paths"].get(election_id)
        if path is None:
            continue
        asked = True
        value = resolve(record, path)
        if value is None:
            continue
        usual = spec.get("iprastas-atsakymas", "neigiamas")
        if answer_class(value) != usual:
            out[name] = value.strip() if isinstance(value, str) else str(value)
    return out if asked else None


def status(flags: dict[str, str] | None) -> str:
    """The candidacy table's `declarations_status` for a `flagged` result."""
    if flags is None:
        return NOT_ASKED
    return SOME_FLAGGED if flags else ALL_USUAL
