"""One resolver for the nominator, over the eleven paths the corpus spreads it across.

Who put a candidate on the ballot -- the party, coalition, committee, or the
candidate themself -- is recorded on 99.8 % of all records, but never in one
place. The 1996-1999 archive keeps it in a *list* of candidacies under
`normalized.kandidatavimas`; the 2000-2014 municipal elections hoist a
`kandidatavimas` section to the record root, where `tarybosNarys.partyList` is
a bare string in 2000/2002 and a dict with a `name` in 2019/2023; the profile
card publishes it under six different `profilis.kita` keys depending on the
era and the seat; and the 2011/2015-era pages mark a self-nominated candidate
with a *label* ("Išsikėlęs kandidatas") whose value is empty. Issue #82
measured what walking any one of those paths costs: the documented single
paths reached 63.5 % of the corpus, and the gap was invisible, because a
missing path and a genuinely non-partisan candidate both read as null.

So the resolution order is data, not code: `docs/concept-map.json` maps the
`iskele` concept to an *ordered list* of paths per election, and this module
walks them, first non-empty string wins. Resolved against every record on
2026-08-30: 113,028 of 113,028 records of the 51 non-presidential elections
(and 2024-prezidento, whose card names the nominator) return a value; the
remaining four presidential elections and 2019-prezidento publish no
nominator at all and map no paths, so they resolve to None -- which there
means self-nominated by law, not a gap.

Path semantics, shared with `scripts/field_coverage.py`:

* paths resolve against `normalized`, falling back to the record root for the
  `kandidatavimas` section the pre-2016 eras hoist there;
* a list met mid-path fans out over its entries in order -- the 1996-1999
  archive's candidacy list, where a candidate could stand in a constituency
  and on a party list at once;
* only a non-empty string is a value. `partyList` as a dict is a container,
  not an answer; its `name` is a separate path.

The canonical-party join for the resolved string is `scraper/shared/parties.py`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONCEPT_MAP = REPO_ROOT / "docs" / "concept-map.json"

#: The concept whose per-election paths are the resolution order.
NOMINATOR_CONCEPT = "iskele"

#: Sections a path may name on the record root rather than under `normalized`.
#: Kept equal to scripts/field_coverage.py's RECORD_ROOT_SECTIONS.
RECORD_ROOT_SECTIONS = {"kandidatavimas"}


@lru_cache(maxsize=1)
def nominator_paths() -> dict[str, tuple[str, ...]]:
    """The `iskele` resolution order per election id, from the concept map.

    The concept map writes a single path where one suffices and an ordered
    list where it does not; both come back as tuples here so the resolver
    has one shape to walk.
    """
    concept_map = json.loads(CONCEPT_MAP.read_text(encoding="utf-8"))
    paths = concept_map["concepts"][NOMINATOR_CONCEPT]["paths"]
    return {
        election_id: (path,) if isinstance(path, str) else tuple(path)
        for election_id, path in paths.items()
    }


def _walk(node: Any, segments: tuple[str, ...]) -> str | None:
    """First non-empty string at `segments` under `node`; lists fan out in order."""
    if isinstance(node, list):
        for entry in node:
            value = _walk(entry, segments)
            if value is not None:
                return value
        return None
    if not segments:
        if isinstance(node, str) and node.strip():
            return node.strip()
        return None
    if not isinstance(node, dict) or segments[0] not in node:
        return None
    return _walk(node[segments[0]], segments[1:])


def resolve_nominator(record: dict[str, Any], election_id: str | None = None) -> str | None:
    """The nominator string for one corpus record, or None.

    `election_id` defaults to the record's own `electionId`. None means the
    election maps no nominator (the presidential elections whose candidates
    self-nominate by law and whose pages name no nominator) or -- on a mapped
    election -- a record none of its paths fill, which the corpus assertion in
    tests/test_corpus_nominators.py keeps at zero.
    """
    election_id = election_id or record.get("electionId")
    paths = nominator_paths().get(election_id)
    if not paths:
        return None
    for path in paths:
        segments = tuple(path.split("."))
        value = _walk(record.get("normalized"), segments)
        if value is None and segments[0] in RECORD_ROOT_SECTIONS:
            value = _walk(record, segments)
        if value is not None:
            return value
    return None
