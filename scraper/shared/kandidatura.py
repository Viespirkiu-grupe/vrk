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
     "apygarda":               the single-mandate constituency's name, Seimas
                               eras, one name per district across the four
                               label eras (scraper/shared/apygardos.py),
     "apygardos-numeris":      its number in this election,
     "apygarda-raw":           the label the record carries,
     "savivaldybe":            the municipality's official name, municipal/
                               mayoral eras (scraper/municipalities.json),
     "savivaldybe-id":         its registry id, None when no entry claims
                               the published form,
     "savivaldybe-raw":        the form the record carries,
     "sarasas":                the list stood on (name),
     "numeris-sarase":         pre-election list position,
     "porinkiminis-numeris":   post-election list position,
     "isrinktas":              True | False | None -- elected to any office
                               on this ballot,
     "vaidmenys":              every office on this record's ballot,
     "isrinktas-tarybos-nariu": the council seat's own outcome,
     "isrinktas-meru":         the mayoralty's own outcome -- each True |
                               False | None, None where the office was not
                               on the ballot or the record cannot say,
     "pirmumo-balsai":         the candidate's preference votes on the list,
     "pirmumo-balsu-matas":    "pirmumo-balsai" (2000-2015) or
                               "teigiami-balsai" (the 1996 rating system's
                               positive votes; see below),
     "teigiami-balsai", "neigiami-balsai", "reitingo-balai":
                               the 1996 system's three list figures, and the
                               2000/2008/2012 pages' rating points, verbatim,
     "sarasas-balsai":         the LIST's votes in the municipality (2000 and
                               2002 municipal) -- the list's, not the
                               candidate's, hence the separate name,
     "apygardos-turai":        the candidate's showing in each round of the
                               single-winner race, oldest first:
                               [{turas, balsai, procentai, vieta, saltinis}],
     "apygardos-balsai", "apygardos-turas", "apygardos-vieta",
     "apygardos-procentai":    the last round contested, flattened,
     "balsu-saltinis":         the VRK page the vote figures came from}

A candidacy that is both constituency and list (1996–2012 Seimas) is still
one row: `apygarda` and `sarasas` are separate facts and both fill. A
2015/2019/2023 candidate standing for council *and* mayor keeps the council
list fields and takes `vaidmuo` from the mayoral run — the more specific
office — but the two offices have two outcomes, and `isrinktas` is the OR of
them. Reading the office off `vaidmuo` and the outcome off `isrinktas`
shipped 448 council winners who lost the mayoralty as elected mayors (issue
#140); `isrinktas-meru` and `isrinktas-tarybos-nariu` answer per office:
from the 2019/2023 records' per-office `elected` flags, from the seat the
results file named (`isrinktasKaip`) on the 2015 ballots, and from
`isrinktas` alone where the ballot had one office.

The municipality is canonicalised through `scraper/shared/municipalities.py`
(issue #137): the parsers pass each era's wording through — "Vilniaus
miesto" on five elections, "Vilniaus miesto savivaldybė" on three, the
mayoral cards' "Telšių rajono (Nr. 51)" — and left as they were, all 60
municipalities appeared twice in every consumer. `savivaldybe` is the
official name, `savivaldybe-id` the join key, `savivaldybe-raw` what the
record says.

**Votes** (issue #133). 59,275 candidacies across 26 elections carry a vote
or rating figure -- 29.5 million preference votes -- and until this resolver
returned them no consumer could see one. The 2000-2015 root block spells
them `pirmumoBalsai` (with `reitingoBalai` where VRK printed rating points),
`tarybosNarys.sarasoBalsai` (the list's own total), `vienmandatesBalsai`
and `vienmandatesBalsai2` (the constituency's two rounds, `{isViso,
procentai, vieta, saltinis}`) and, on the presidential and 2003 pages,
`turai[]`; the 1996-1999 archive list spells the same facts kebab-case
inside its constituency entry's `turai` and, on the 1996 multi-mandate
entry, the rating system's `teigiami-balsai` / `neigiami-balsai` /
`reitingo-balai`. The 1996 list vote was a rating: a voter marked the
candidates they favoured and those they did not, and the order followed the
points; `pirmumo-balsai` carries the positive votes there with
`pirmumo-balsu-matas` saying so, because that is the era's preference vote,
and the three figures ride verbatim beside it. The 2016-2025 records hold
no votes at all (their results live on pages the corpus does not read), so
every vote key is None there, and `apygarda` is the one thing those eras
do publish about the race.

The constituency is canonicalised through `scraper/shared/apygardos.py`:
the label eras -- "Akmenės - Joniškio", "Akmenės Joniškio", "Aukštaitijos
(Nr. 28)", "33. Aukštaitijos" -- become one name per district and the
number travels separately, and the 2000-2012 cards' "Daugiamandatė" row
(the list, not a district) reads as None rather than as the constituency
of 2,980 list-only candidates.

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

from scraper.shared.apygardos import apygarda as _apygarda
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


PREFERENCE_VOTES = "pirmumo-balsai"
POSITIVE_VOTES = "teigiami-balsai"

VOTE_KEYS = (
    "pirmumo-balsai",
    "pirmumo-balsu-matas",
    "teigiami-balsai",
    "neigiami-balsai",
    "reitingo-balai",
    "sarasas-balsai",
    "apygardos-turai",
    "apygardos-balsai",
    "apygardos-turas",
    "apygardos-vieta",
    "apygardos-procentai",
    "balsu-saltinis",
)


def _empty(role: str | None, elected: Any) -> dict[str, Any]:
    answer: dict[str, Any] = {
        "vaidmuo": role,
        "vaidmenys": [role] if role else [],
        "apygarda": None,
        "apygardos-numeris": None,
        "apygarda-raw": None,
        "savivaldybe": None,
        "savivaldybe-id": None,
        "savivaldybe-raw": None,
        "sarasas": None,
        "numeris-sarase": None,
        "porinkiminis-numeris": None,
        "isrinktas": elected,
        "isrinktas-tarybos-nariu": None,
        "isrinktas-meru": None,
    }
    answer.update(dict.fromkeys(VOTE_KEYS))
    answer["apygardos-turai"] = []
    return answer


def _set_constituency(answer: dict[str, Any], label: Any, number: Any = None) -> None:
    answer.update(_apygarda(_name_of(label), number))


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _int_of(value)
    return value


def _round(turas: Any, balsai: Any, procentai: Any, vieta: Any, saltinis: Any) -> dict[str, Any] | None:
    votes = _number(balsai)
    if votes is None:
        return None
    return {
        "turas": _int_of(turas) or 1,
        "balsai": votes,
        "procentai": _number(procentai),
        "vieta": _int_of(vieta),
        "saltinis": saltinis if isinstance(saltinis, str) else None,
    }


def _rounds_from_turai(turai: Any) -> list[dict[str, Any]]:
    """The `turai` list of the presidential/2003 root block and the archive
    family's constituency entry: kebab-case, one entry per round."""
    rounds = []
    for entry in turai if isinstance(turai, list) else []:
        if not isinstance(entry, dict):
            continue
        one = _round(
            entry.get("turas"),
            entry.get("balsai"),
            entry.get("procentai-nuo-galiojanciu", entry.get("procentai")),
            entry.get("vieta"),
            entry.get("saltinis"),
        )
        if one is not None:
            rounds.append(one)
    return sorted(rounds, key=lambda r: r["turas"])


def _rounds_from_blocks(root: dict[str, Any]) -> list[dict[str, Any]]:
    """The 2000-2015 root block's `vienmandatesBalsai` / `vienmandatesBalsai2`."""
    rounds = []
    for number, key in ((1, "vienmandatesBalsai"), (2, "vienmandatesBalsai2")):
        block = root.get(key)
        if not isinstance(block, dict):
            continue
        one = _round(number, block.get("isViso"), block.get("procentai"), block.get("vieta"), block.get("saltinis"))
        if one is not None:
            rounds.append(one)
    return rounds


def _set_rounds(answer: dict[str, Any], rounds: list[dict[str, Any]]) -> None:
    answer["apygardos-turai"] = rounds
    if not rounds:
        return
    last = rounds[-1]
    answer["apygardos-balsai"] = last["balsai"]
    answer["apygardos-turas"] = last["turas"]
    answer["apygardos-vieta"] = last["vieta"]
    answer["apygardos-procentai"] = last["procentai"]


def _set_source(answer: dict[str, Any], *candidates: Any) -> None:
    """The first page named: the preference page where there are preference
    votes, else the last round's results page."""
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            answer["balsu-saltinis"] = candidate.strip()
            return
    rounds = answer["apygardos-turai"]
    if rounds and rounds[-1]["saltinis"]:
        answer["balsu-saltinis"] = rounds[-1]["saltinis"]


def _offices(root: dict[str, Any], roles: list[Any], kind: str | None, role: str) -> tuple[list[str], Any, Any]:
    """The offices on this record's ballot and each one's outcome:
    (vaidmenys, isrinktas-tarybos-nariu, isrinktas-meru).

    Three sources, in the order the records offer them: the 2019/2023
    `tarybosNarys.elected` / `meras.elected` booleans; on the 2015 ballots,
    where those blocks carry `elected: null`, the seat the results file named
    (`isrinktasKaip`: a dual candidate elected mayor took the mayoral seat and
    the list skipped them, so the council outcome is False, and one elected to
    the council lost the mayoralty); and where the ballot had one office,
    `isrinktas` itself.
    """
    if kind == "mero":
        return [ROLE_MAYOR], None, root.get("isrinktas")
    if kind is not None and kind != "savivaldybiu":
        return [role], None, None
    council_on_ballot = ROLE_COUNCIL in roles or not roles
    mayor_on_ballot = ROLE_MAYOR in roles
    offices = ([ROLE_COUNCIL] if council_on_ballot else []) + ([ROLE_MAYOR] if mayor_on_ballot else [])
    if not offices:
        return [role], None, None
    elected = root.get("isrinktas")
    seat = root.get("isrinktasKaip")

    def outcome(office: str, block: Any) -> Any:
        if office not in offices:
            return None
        if isinstance(block, dict) and isinstance(block.get("elected"), bool):
            return block["elected"]
        if elected is True and len(offices) > 1:
            return (seat == office) if seat in offices else None
        return elected

    return offices, outcome(ROLE_COUNCIL, root.get("tarybosNarys")), outcome(ROLE_MAYOR, root.get("meras"))


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
            # The 1996 rating system: positive and negative votes and the
            # points VRK ranked by. The positive votes are the era's
            # preference vote, and the measure says so.
            for key in ("teigiami-balsai", "neigiami-balsai", "reitingo-balai"):
                if answer[key] is None:
                    answer[key] = _number(entry.get(key))
            if answer["pirmumo-balsai"] is None and answer["teigiami-balsai"] is not None:
                answer["pirmumo-balsai"] = answer["teigiami-balsai"]
                answer["pirmumo-balsu-matas"] = POSITIVE_VOTES
                _set_source(answer, entry.get("reitingo-saltinis"))
        else:
            if answer["apygarda"] is None:
                _set_constituency(answer, entry.get("apygarda"), entry.get("apygardos-numeris"))
            if not answer["apygardos-turai"]:
                _set_rounds(answer, _rounds_from_turai(entry.get("turai")))
    answer["isrinktas"] = elected
    if answer["balsu-saltinis"] is None:
        _set_source(answer)
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
        answer["isrinktas-tarybos-nariu"] = answer["isrinktas"]
        _set_municipality(answer, norm_candidacy.get("savivaldybe"))
        answer["sarasas"] = _name_of(norm_candidacy.get("iskele"))
        answer["numeris-sarase"] = _int_of(norm_candidacy.get("numeris-sarase"))
        return answer  # the 1997 pages publish no vote figures at all

    root = record.get("kandidatavimas")
    root = root if isinstance(root, dict) else {}
    roles = root.get("roles") or []
    role = _ROLE_BY_KIND.get(kind or "")
    if role is None:  # savivaldybiu: council general, mayor where the record says so
        role = ROLE_MAYOR if "meras" in roles else ROLE_COUNCIL
    answer = _empty(role, root.get("isrinktas"))
    answer["vaidmenys"], answer["isrinktas-tarybos-nariu"], answer["isrinktas-meru"] = _offices(
        root, list(roles), kind, role
    )

    _set_municipality(
        answer,
        root.get("savivaldybe") if _name_of(root.get("savivaldybe")) else _kita_value(record, "savivaldybe"),
    )

    single = root.get("vienmandate")
    if isinstance(single, dict):
        _set_constituency(answer, single.get("apygarda"), single.get("apygardosNumeris"))
    if answer["apygarda"] is None and kind == "seimo":
        # The 2004-2024 cards; the 2000-2012 ones print "Daugiamandatė" in
        # this row for a list-only candidate, which apygardos reads as None.
        _set_constituency(answer, _kita_value(record, "vienmandate-apygarda", "apygarda"))

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

    # The votes (issue #133): the 2000-2015 root block's names, joined from
    # the candidate pages (to 2004) and the results trees (2007-2015).
    answer["pirmumo-balsai"] = _number(root.get("pirmumoBalsai"))
    if answer["pirmumo-balsai"] is not None:
        answer["pirmumo-balsu-matas"] = PREFERENCE_VOTES
    answer["reitingo-balai"] = _number(root.get("reitingoBalai"))
    if isinstance(council, dict):
        answer["sarasas-balsai"] = _number(council.get("sarasoBalsai"))
    rounds = _rounds_from_blocks(root)
    if not rounds:
        rounds = _rounds_from_turai(root.get("turai"))
    _set_rounds(answer, rounds)
    _set_source(answer, root.get("pirmumoBalsuSaltinis"))
    return answer
