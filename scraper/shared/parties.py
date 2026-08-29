"""The canonical party join: 427 measured surface forms, one id per organisation.

The corpus has no cross-election party identifier -- issue #82 measured every
candidate id VRK publishes and none is shared between two elections -- so
party identity is created here rather than recovered. `scraper/parties.json`
holds one entry per organisation (parties, coalitions, electoral committees,
self-nomination), bootstrapped from the 427 distinct nominator strings the
corpus records, each of which is an exact alias of exactly one entry. The
registry, not the corpus, carries renames (one entry, the old name an alias:
LVŽS spans its 2001 and 2006 names) and mergers (a new entry with the merged
organisations as `predecessors`: TS-LKD points at Tėvynės sąjunga and LKD).

Matching never guesses:

1. exact -- the string is an entry's name, shortName or alias;
2. folded -- equal after `fold`, which unifies the glyph noise VRK itself
   varies on: NFC, dash characters to a plain hyphen with no spaces around
   it, every quote glyph to `"`, case, runs of whitespace, a trailing period.
   One party's 16,268 candidacies split three ways on nothing but the dash
   between the words before this;
3. unmatched -- None. A form no entry claims is reported by
   `scripts/nominator_report.py` into the registry's `unmatched` block, and
   tests/test_party_registry.py asserts that block is empty, so a new surface
   form upstream is a red test, not a silent new party.

`partija(record)` is the derived concept the concept map documents: the
record's raw nominator string and the registry id it joins to. The records
themselves are never rewritten.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from scraper.shared.nominator import resolve_nominator

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "scraper" / "parties.json"

#: Every dash glyph the corpus writes between words that are one name.
DASHES = "‒–—−"
#: Every quote glyph, curly and straight, single and double.
QUOTES = "„“”\"'’‘`´«»"

ENTRY_TYPES = ("partija", "koalicija", "komitetas", "issikelimas")

_DASH_SPACING = re.compile(r"\s*-\s*")


def fold(text: str) -> str:
    """The punctuation/case fold behind matching rule 2. Never de-inflects:
    grammatical case ("...partijos") is an explicit alias, because a generic
    de-genitiver cannot tell an inflection from a different name."""
    folded = unicodedata.normalize("NFC", text)
    for dash in DASHES:
        folded = folded.replace(dash, "-")
    for quote in QUOTES:
        folded = folded.replace(quote, '"')
    folded = _DASH_SPACING.sub("-", folded)
    folded = " ".join(folded.split())
    folded = folded.rstrip(".")
    return folded.casefold()


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def entries() -> dict[str, dict[str, Any]]:
    return load_registry()["entries"]


def entry(party_id: str) -> dict[str, Any]:
    return entries()[party_id]


@lru_cache(maxsize=1)
def _indexes() -> tuple[dict[str, str], dict[str, str]]:
    """(exact, folded) alias indexes. Built once; the registry's invariant --
    no two entries claim the same alias, even folded -- is a test, so a
    collision here would already be a red suite, not a quiet coin toss."""
    exact: dict[str, str] = {}
    folded: dict[str, str] = {}
    for party_id, data in entries().items():
        keys = [data["name"], *data.get("aliases", [])]
        if data.get("shortName"):
            keys.append(data["shortName"])
        for key in keys:
            exact.setdefault(key, party_id)
            folded.setdefault(fold(key), party_id)
    return exact, folded


def match(raw: str | None) -> str | None:
    """The registry id for one nominator surface form, or None. Never guesses:
    a form that is neither an exact nor a folded alias is unmatched."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    exact, folded = _indexes()
    name = raw.strip()
    return exact.get(name) or folded.get(fold(name))


def partija(record: dict[str, Any], election_id: str | None = None) -> dict[str, Any]:
    """The derived party concept for one corpus record.

        {"partija-id": "ts-lkd",
         "partija-vardas-raw": "Tėvynės sąjunga-Lietuvos krikščionys demokratai",
         "tipas": "partija"}

    `partija-vardas-raw` is the string the record actually carries, resolved
    by scraper/shared/nominator.py; `partija-id` its registry entry, None for
    the elections that publish no nominator and for any form the registry
    does not claim; `tipas` the entry's kind, so a consumer can keep
    committees and coalitions apart from parties without a second lookup.
    """
    raw = resolve_nominator(record, election_id)
    party_id = match(raw)
    return {
        "partija-id": party_id,
        "partija-vardas-raw": raw,
        "tipas": entry(party_id)["type"] if party_id else None,
    }
