"""What one record says about *the candidacy itself*, across every page era.

`kandidatavimas` is the least uniform part of the corpus (issue #93): a
camelCase dict at the record root in the 2000–2015 and municipal-general
families, a kebab-case dict under `normalized` in the 1997 municipal archive,
a kebab-case *list* in the 1996–1999 Seimas archive (a candidate could stand
in a constituency and on a party list at once), and — in the 2016–2025 era —
a root stub holding only `isrinktas`, with the candidacy facts living in
`profilis.kita` instead. The municipal `partyList` and `savivaldybe` are a
plain string in seven elections and a `{id, number, name}` dict in 2019/2023.

This resolver flattens all of that into one answer per record:

    {"vaidmuo":     "seimo-narys" | "tarybos-narys" | "meras"
                    | "prezidentas" | "ep-narys",
     "apygarda":               the single-mandate constituency, Seimas eras,
     "savivaldybe":            the municipality's official name, municipal/
                               mayoral eras (scraper/municipalities.json),
     "savivaldybe-id":         its registry id, None when no entry claims
                               the published form,
     "savivaldybe-raw":        the form the record carries,
     "sarasas":                the list stood on (name),
     "numeris-sarase":         pre-election list position,
     "porinkiminis-numeris":   post-election list position,
     "isrinktas":              True | False | None}

A candidacy that is both constituency and list (1996–2012 Seimas) is still
one row: `apygarda` and `sarasas` are separate facts and both fill. A
2019/2023 candidate standing for council *and* mayor keeps the council list
fields and takes `vaidmuo` from the mayoral run — the more specific office.

The municipality is canonicalised through `scraper/shared/municipalities.py`
(issue #137): the parsers pass each era's wording through — "Vilniaus
miesto" on five elections, "Vilniaus miesto savivaldybė" on three, the
mayoral cards' "Telšių rajono (Nr. 51)" — and left as they were, all 60
municipalities appeared twice in every consumer. `savivaldybe` is the
official name, `savivaldybe-id` the join key, `savivaldybe-raw` what the
record says.

`isrinktas` is the corpus-wide elected flag: the root `kandidatavimas` value
everywhere it exists (joined from VRK's results trees for the eras whose
pages mark no winner, prose-derived for 2016–2025 — see DATA_GUIDE), any()
over the archive family's candidacy list, and None only where no results
exist: the five 2000 municipalities whose results tree VRK does not publish.
(The 1997 municipal pair used to be the other gap; issue #92 joined its
per-municipality elected pages, so its dict shape now carries a bool too.)
"""

from __future__ import annotations

from typing import Any

from scraper.shared.municipalities import savivaldybe as _savivaldybe

ROLE_SEIMAS = "seimo-narys"
ROLE_COUNCIL = "tarybos-narys"
ROLE_MAYOR = "meras"
ROLE_PRESIDENT = "prezidentas"
ROLE_MEP = "ep-narys"

#: election `kind` (scraper/elections.json) → the office where the kind alone
#: decides it. `savivaldybiu` is the one kind with two offices on one ballot;
#: its records say which via `roles`.
_ROLE_BY_KIND = {
    "seimo": ROLE_SEIMAS,
    "ep": ROLE_MEP,
    "prezidento": ROLE_PRESIDENT,
    "mero": ROLE_MAYOR,
}


def _name_of(value: Any) -> str | None:
    """A field that is a plain string in some eras and `{name: ...}` in others
    — `savivaldybe` and `tarybosNarys.partyList` (issue #93's type split)."""
    if isinstance(value, dict):
        value = value.get("name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _set_municipality(answer: dict[str, Any], value: Any) -> None:
    """Resolve the published municipality -- a plain string, or the 2019/2023
    `{id, number, name}` dict -- through the registry. The mayoral cards'
    constituency number ("Telšių rajono (Nr. 51)") is stripped there, and the
    era's wording joins to the one official name."""
    answer.update(_savivaldybe(_name_of(value)))


def _int_of(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _kita_value(record: dict[str, Any], *keys: str) -> Any:
    """`profilis.kita.<key>.reiksme`, first key that answers."""
    profilis = (record.get("normalized") or {}).get("profilis") or {}
    kita = profilis.get("kita")
    if not isinstance(kita, dict):
        return None
    for key in keys:
        entry = kita.get(key)
        if isinstance(entry, dict):
            value = entry.get("reiksme")
            if value not in (None, ""):
                return value
    return None


def _empty(role: str | None, elected: Any) -> dict[str, Any]:
    return {
        "vaidmuo": role,
        "apygarda": None,
        "savivaldybe": None,
        "savivaldybe-id": None,
        "savivaldybe-raw": None,
        "sarasas": None,
        "numeris-sarase": None,
        "porinkiminis-numeris": None,
        "isrinktas": elected,
    }


def _from_archive_list(entries: list[Any], kind: str | None) -> dict[str, Any]:
    """The 1996–1999 Seimas archive family: one entry per candidacy.

    The multi-mandate entry names its `apygarda` "Daugiamandatė" with no
    number; the constituency entry carries the number and the round results.
    The list stood on is the multi-mandate entry's own nominator — those
    ballots had no list name apart from who fielded it.
    """
    answer = _empty(_ROLE_BY_KIND.get(kind or "seimo", ROLE_SEIMAS), None)
    elected: bool | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("isrinktas") is True:
            elected = True
        elif entry.get("isrinktas") is False and elected is None:
            elected = False
        multi_mandate = entry.get("numeris-sarase") is not None or (
            isinstance(entry.get("apygarda"), str)
            and entry["apygarda"].startswith("Daugiamandat")
        )
        if multi_mandate:
            answer["sarasas"] = answer["sarasas"] or _name_of(entry.get("iskele"))
            answer["numeris-sarase"] = answer["numeris-sarase"] or _int_of(
                entry.get("numeris-sarase")
            )
            answer["porinkiminis-numeris"] = answer["porinkiminis-numeris"] or _int_of(
                entry.get("porinkiminis-numeris-sarase")
            )
        else:
            answer["apygarda"] = answer["apygarda"] or _name_of(entry.get("apygarda"))
    answer["isrinktas"] = elected
    return answer


def kandidatura(record: dict[str, Any], kind: str | None = None) -> dict[str, Any]:
    """The one candidacy answer for one corpus record.

    `kind` is the election's kind from `scraper/elections.json`
    (`seimo`/`savivaldybiu`/`prezidento`/`ep`/`mero`); it decides the office
    wherever the record itself does not carry roles.
    """
    normalized = record.get("normalized") or {}

    norm_candidacy = normalized.get("kandidatavimas")
    if isinstance(norm_candidacy, list):
        return _from_archive_list(norm_candidacy, kind)
    if isinstance(norm_candidacy, dict):
        # The 1997 municipal archive pair. `isrinktas` is joined in from
        # VRK's per-municipality elected pages (issue #92) and is a bool on
        # every record; a record parsed without the results file carries no
        # key, and the absence stays None rather than reading as false.
        answer = _empty(ROLE_COUNCIL, norm_candidacy.get("isrinktas"))
        _set_municipality(answer, norm_candidacy.get("savivaldybe"))
        answer["sarasas"] = _name_of(norm_candidacy.get("iskele"))
        answer["numeris-sarase"] = _int_of(norm_candidacy.get("numeris-sarase"))
        return answer

    root = record.get("kandidatavimas")
    root = root if isinstance(root, dict) else {}
    roles = root.get("roles") or []
    role = _ROLE_BY_KIND.get(kind or "")
    if role is None:  # savivaldybiu: council general, mayor where the record says so
        role = ROLE_MAYOR if "meras" in roles else ROLE_COUNCIL
    answer = _empty(role, root.get("isrinktas"))

    _set_municipality(
        answer,
        root.get("savivaldybe") if _name_of(root.get("savivaldybe")) else _kita_value(record, "savivaldybe"),
    )

    single = root.get("vienmandate")
    if isinstance(single, dict):
        answer["apygarda"] = _name_of(single.get("apygarda"))
    if answer["apygarda"] is None and kind == "seimo":
        answer["apygarda"] = _name_of(
            _kita_value(record, "vienmandate-apygarda", "apygarda")
        )

    multi = root.get("daugiamandate")
    council = root.get("tarybosNarys")
    if isinstance(multi, dict):
        answer["sarasas"] = _name_of(multi.get("sarasas"))
        answer["numeris-sarase"] = _int_of(multi.get("numerisSarase"))
    elif isinstance(council, dict):
        answer["sarasas"] = _name_of(council.get("partyList"))
        answer["numeris-sarase"] = _int_of(council.get("listPosition"))
    if answer["sarasas"] is None:
        answer["sarasas"] = _name_of(_kita_value(record, "sarasas"))
    if answer["numeris-sarase"] is None:
        answer["numeris-sarase"] = _int_of(
            _kita_value(record, "numeris-sarase", "priesrinkiminis-numeris-sarase")
        )

    answer["porinkiminis-numeris"] = _int_of(root.get("porinkiminisNumerisSarase"))
    if answer["porinkiminis-numeris"] is None and isinstance(council, dict):
        answer["porinkiminis-numeris"] = _int_of(council.get("postElectionPosition"))
    if answer["porinkiminis-numeris"] is None:
        answer["porinkiminis-numeris"] = _int_of(
            _kita_value(
                record, "porinkiminis-eiles-numeris", "porinkiminis-numeris-sarase"
            )
        )
    return answer
