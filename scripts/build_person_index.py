"""Build the cross-election person index the dashboard reads.

One person appears in many elections under no shared VRK identifier — the
per-election rkndId is a registration id, not a person id — so identity is
resolved by normalized name + birth date. Measured over the 33,119-record
corpus: birth date is present on 33,118 records, the pair collides for zero
same-election record pairs, and 305 names are shared by people with distinct
birth dates, which name-only matching would have wrongly merged. A record
without a birth date groups by name alone and is flagged; there were two
before the 1996-1998 Seimas archive family was added, and the second is a
known duplicate rather than a second person. VRK issued Marija Puč two
candidate ids in the 2015 Trakai repeat election and published the council
one as an unfilled "Rengiama" page, so that record has a name and no birth
date and splits off from her real entry. Merging it on name alone is exactly
what the birth-date key exists to prevent, so it is left split and recorded
here instead — see docs/DATASET.md.

The 1996-1998 Seimas archive family (`1996-spalio-20-seimo`,
`1997-kovo-23-seimo-pakartotiniai`, `1997-gruodzio-21-seimo-pakartotiniai`;
`scraper/shared/seimo_archive_1990s.py`) publishes no birth date on any
candidate page, so its records cannot use the full name+birth-date key — a
real, structural gap in this identity key, not a handful of flagged
exceptions. Most of them do carry a birth *year* recovered from the
biography's opening sentence (`anketa.gimimo-metai`), and those group by
name + `~year` — measured over the corpus: 170 of the 234 records without a
birth date. The rest group by name alone. A same-named same-aged person
appearing only within this family still cannot be told apart from a namesake
by this index. The 1997 municipal archive family
(`1997-kovo-23-savivaldybiu-tarybu`,
`1997-birzelio-29-svenciniu-tarybos-pakartotiniai`;
`scraper/shared/savivaldybiu_archive_1997.py`) does publish birth date, under
the corpus's usual `anketa.gimimo-data`, so it needs no special case here.

Identity (issue #96) is carried two ways on top of that join:

- Every person gets a **pid** — `"p"` + blake2s of the natural
  `name|birth` key, 12 hex digits — emitted into people.json and used by the
  dashboard as the deep-link hash. For a merged person the pid derives from
  the natural key of the fragment holding the chronologically earliest
  candidacy, so the id survives both a rebuild and a new election (elections
  are only added at the recent end; the corpus's historical sweep is done).
  The builder fails on a pid collision rather than shipping two persons
  under one id.
- `scraper/person_overrides.json` is the checked-in, hand-reviewed record of
  identity decisions the key cannot make on its own — a person who changed
  surname between elections is two natural keys forever, and the corpus
  proves many such pairs are one human (shared birthplace, school, a marital
  status that flips exactly across the split). Each entry lists the natural
  keys of a reviewed pair and a decision: `"merge"` folds the fragments into
  one person (the non-canonical keys land in the entry's `"ak"` so old
  deep links keep resolving); `"distinct"` records that the pair was
  reviewed and is genuinely two people, so
  `scripts/find_identity_merge_candidates.py` stops resurfacing it. A merge
  key that matches nothing (a rescrape changed the name, say) fails the
  build — the override file must never rot silently.

Election names and chronology come from the one registry,
`scraper/elections.json` -- id, first-round date, kind, official Lithuanian
name, short label, and for a by-election, repeat or re-vote the `parent`
general election whose term it fills (issue #122) -- and are copied whole
into people.json so the dashboard carries no election list of its own: the
`parent` field is what lets its election filter fold the 2017-2019
seat-fills under `2016 Seimas`. An election directory with no registry entry
is reported by the run and falls back to its raw id in the UI.

Run from the repo root:

    python scripts/build_person_index.py

Reads data/<election-id>/*.json and scraper/elections.json, writes
dashboard/people.json, and prints the audit counts so a run is its own sanity
check.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper.shared.deklaracijos import (  # noqa: E402
    INCOME_EMPLOYMENT,
    LITAS_PER_EURO,
    deklaruotos_pajamos,
)
from scraper.shared.education import LEVELS as EDUCATION_LEVELS  # noqa: E402
from scraper.shared.education import issilavinimas  # noqa: E402
from scraper.shared.kandidatura import ROLE_MAYOR, kandidatura  # noqa: E402
from scraper.shared.parties import entry as party_entry  # noqa: E402
from scraper.shared.parties import partija  # noqa: E402
from scraper.shared.provenance import parser_commit, utc_now_iso  # noqa: E402

import field_coverage  # noqa: E402

DATA_ROOT = Path("data")
OUTPUT_PATH = Path("dashboard/people.json")

REGISTRY_PATH = Path("scraper/elections.json")
OVERRIDES_PATH = Path("scraper/person_overrides.json")
CONCEPT_MAP_PATH = Path("docs/concept-map.json")

#: The employment concepts folded into each candidacy's search string ("wp"),
#: resolved through docs/concept-map.json rather than a path list of this
#: file's own -- the eras split them (einamos-pareigos is the 2020-on
#: question, pagrindine-darboviete everything before), and the map, not this
#: builder, is where that split is recorded. First concept that answers wins.
WORKPLACE_CONCEPTS = ("einamos-pareigos", "pagrindine-darboviete")

#: Lithuanian display labels for scraper/shared/education.py's 13-tier
#: ordinal, in rank order. The slugs are ASCII-folded, so de-slugging them in
#: the page would drop the diacritics ("Aukstasis"); the labels ride in
#: people.json instead, and build_index() fails if a tier lacks one.
EDUCATION_LEVEL_LABELS = {
    "pradinis": "Pradinis",
    "pagrindinis": "Pagrindinis",
    "nebaigtas-vidurinis": "Nebaigtas vidurinis",
    "vidurinis": "Vidurinis",
    "profesinis-vidurinis": "Profesinis vidurinis",
    "aukstesnysis": "Aukštesnysis",
    "nebaigtas-aukstasis": "Nebaigtas aukštasis",
    "aukstasis-nedetalizuotas": "Aukštasis (nedetalizuota)",
    "aukstasis-neuniversitetinis": "Aukštasis neuniversitetinis",
    "aukstasis-universitetinis": "Aukštasis universitetinis",
    "aukstasis-bakalauras": "Aukštasis (bakalauras)",
    "aukstasis-magistras": "Aukštasis (magistras)",
    "doktorantura": "Doktorantūra",
}


def load_registry(path: Path = REGISTRY_PATH) -> list[dict]:
    """Read scraper/elections.json, chronologically ordered.

    The file is stored sorted by date, but the order is re-derived here so a
    mis-sorted hand edit cannot quietly change the dashboard's chronology.
    The sort is stable and keyed on the date alone, so elections held on the
    same day -- 2015-06-07 ran a Seimas by-election and two repeat municipal
    votes -- keep the order the file lists them in, there being no other.
    """
    entries = json.loads(path.read_text(encoding="utf-8"))["elections"]
    # A `parent` that names nothing would leave its by-election a top-level
    # row in the dashboard and outside its general's selection -- the very
    # gap issue #122 closes -- so the registry fails to load rather than rot.
    ids = {e["id"] for e in entries}
    for entry in entries:
        parent = entry.get("parent")
        if parent is not None and parent not in ids:
            raise ValueError(f"{path}: {entry['id']} names an unregistered parent {parent!r}")
    return sorted(entries, key=lambda e: e["date"])


def normalize_name(name: str | None) -> str | None:
    if not name:
        return None
    return " ".join(unicodedata.normalize("NFC", name).upper().split())


def birth_date_of(record: dict) -> str | None:
    normalized = record.get("normalized") or {}
    # anketa carries it in the 2016-2019 page eras, biografija from 2020 on.
    for section in ("anketa", "biografija"):
        data = normalized.get(section)
        if isinstance(data, dict) and data.get("gimimo-data"):
            return str(data["gimimo-data"])
    # The 1997 municipal archive family also lands in `anketa.gimimo-data`,
    # so it needs no case of its own. The 1996-1998 Seimas archive family
    # (scraper/shared/seimo_archive_1990s.py) publishes no birth date at all —
    # its records fall through to the birth-year key; see docs/DATASET.md.
    return None


def birth_key_of(record: dict) -> str | None:
    """The birth half of the identity key: ISO date, `~year`, or None.

    The 1996-1998 Seimas archive family publishes no birth date but usually a
    birth year (`anketa.gimimo-metai`, recovered from the biography's opening
    sentence and never promoted to a date). `~1936` keys those records so two
    same-named archive candidates born in different years stay apart — with a
    date they would have. The `~` keeps a year from ever colliding with an
    ISO date and says in people.json's `b` that the year is all we have.
    """
    date = birth_date_of(record)
    if date:
        return date
    normalized = record.get("normalized") or {}
    for section in ("anketa", "biografija"):
        data = normalized.get(section)
        if isinstance(data, dict) and data.get("gimimo-metai"):
            return f"~{data['gimimo-metai']}"
    return None


# Elected status resolves through scraper/shared/kandidatura.py, the one
# resolver over the corpus's five kandidatavimas shapes. Its `isrinktas` is
# tri-state -- True, False, or None where no results exist (2000-kovo-19's
# five unpublished municipalities; the 1997 municipal pair was the larger
# gap until issue #92 joined its elected pages) -- and people.json carries
# all three: `"w": true`, `"w": false`, or no key. The index used to emit
# `"w"` only when won, which made "lost" and "no results data" the same
# absence, and the dashboard read 7,192 unknown outcomes as losses
# (issue #87).


# The asset/income fields carried into the index so the dashboard can chart
# and rank without fetching 47k records. The first three are the keys every
# election from 2007 on normalizes under. The fourth is the 1996-1997 form's
# combined turtas + piniginės lėšos: that era does not split them, so it
# leaves the first two null and would otherwise contribute no turtas at all.
#
# ORDER MATTERS: people.json's "m" array follows this order, and the
# dashboard's MONEY_SERIES and Biggest movers picker index into it.
MONEY_FIELDS = (
    "privalomas-registruoti-turtas",
    "pinigines-lesos",
    "gautos-pajamos",
    "turtas-ir-pinigines-lesos-metu-pabaigoje",
)

#: Which of those the `deklaruotos-pajamos` concept resolves rather than the
#: record answering directly. The 1990s form prints rows 1 and 20 of its income
#: section and row 20 is not always trustworthy -- it fails by rendering 0
#: against a non-zero row 1, so the parser refuses it and `gautos-pajamos` is
#: null on 4,463 of `1997-kovo-23-savivaldybiu-tarybu`'s 6,276 records, and on
#: 165 more across `2000-kovo-19`, `1996-spalio-20-seimo`, `2000-seimo` and the
#: 1997 Švenčionys repeat — 4,628 records in all. Row 1 is published on every
#: one of them, and until issue #98 nothing downstream substituted it, so those
#: candidacies charted as declaring no income at all.
#: The concept returns it with `saltinis` saying what it is; a candidacy
#: resolved that way is flagged `"ds"` so the dashboard can say the figure is
#: employment income and not a total.
INCOME_FIELD_INDEX = MONEY_FIELDS.index("gautos-pajamos")

# The pre-2016 pages declare in litas (`turto-ir-pajamu-deklaracijos.valiuta`
# is "Lt"); everything from 2016 on is in euro. The index converts at the
# irrevocable changeover rate (`LITAS_PER_EURO`, from
# scraper/shared/deklaracijos.py) so that one person's series is comparable
# across the switch, and flags the candidacy so the dashboard can say the
# figure was converted.


def declared_in_litas(record: dict) -> bool:
    declarations = (record.get("normalized") or {}).get("turto-ir-pajamu-deklaracijos")
    return isinstance(declarations, dict) and declarations.get("valiuta") == "Lt"


#: The one money-string rule, shared verbatim with the page's `parseMoney`
#: (dashboard/index.html) and held together by the fixture list in
#: tests/test_dashboard_money_rendering.py. After stripping the euro sign and
#: whitespace (NBSP included), the string must be a plain number with at most
#: one decimal separator, comma or dot. A multi-separator string
#: ("1.234.567,89") is refused rather than guessed at: the two sides used to
#: disagree on exactly those — Python raised and stored None while
#: parseFloat's prefix parse read 1.234 — and no money field in the corpus is
#: a string today, so refusal costs nothing and removes the divergence.
_MONEY_TEXT = re.compile(r"-?\d+(?:[.,]\d+)?")


def parse_money_text(text: str) -> float | None:
    cleaned = re.sub(r"[€\s]", "", text)
    if not _MONEY_TEXT.fullmatch(cleaned):
        return None
    return float(cleaned.replace(",", "."))


def money_of(record: dict) -> list[float | None]:
    declarations = (record.get("normalized") or {}).get("turto-ir-pajamu-deklaracijos")
    divisor = LITAS_PER_EURO if declared_in_litas(record) else 1.0
    income = deklaruotos_pajamos(declarations)
    values: list[float | None] = []
    for index, field in enumerate(MONEY_FIELDS):
        if index == INCOME_FIELD_INDEX:
            raw = income["suma"]
        else:
            raw = declarations.get(field) if isinstance(declarations, dict) else None
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            values.append(round(float(raw) / divisor, 2))
        elif isinstance(raw, str):
            parsed = parse_money_text(raw)
            values.append(round(parsed / divisor, 2) if parsed is not None else None)
        else:
            values.append(None)
    return values


def income_is_employment_only(record: dict) -> bool:
    """Whether the charted income is row 1 rather than a declared total."""
    declarations = (record.get("normalized") or {}).get("turto-ir-pajamu-deklaracijos")
    return deklaruotos_pajamos(declarations)["saltinis"] == INCOME_EMPLOYMENT


def person_key(name: str | None, birth: str | None) -> str:
    return f"{name or '?'}|{birth or '?'}"


def person_pid(key: str) -> str:
    """The persistent person id: `p` + 12 hex digits over the natural key.

    Deterministic — a rebuild, a new election, or a fresh checkout all yield
    the same id for the same person — and short enough for a URL hash. 48
    bits over ~61k persons puts an accidental collision around 1e-6; the
    builder still checks rather than trusts.
    """
    return "p" + hashlib.blake2s(key.encode("utf-8"), digest_size=6).hexdigest()


def load_overrides(path: Path = OVERRIDES_PATH) -> dict:
    """Read the hand-reviewed identity decisions, tolerating absence.

    Absence is a valid state (a fresh fork, a synthetic test corpus); a
    present-but-malformed file is not, so no try/except — a JSON error
    should stop the build.
    """
    if not path.exists():
        return {"decisions": []}
    return json.loads(path.read_text(encoding="utf-8"))


def load_concept_map(path: Path = CONCEPT_MAP_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_merges(
    grouped: dict[str, list[dict]], overrides: dict, order: dict[str, int]
) -> tuple[dict[str, list[str]], list[str]]:
    """Fold override-merged fragments together, in place.

    Returns (former keys by canonical key, override keys that matched no
    person). The canonical key is the one whose fragment holds the
    chronologically earliest candidacy, so the merged person's pid does not
    move when a new (necessarily recent) election is scraped. Keys already
    merged away resolve through their canonical key, so a three-way merge
    written as two pair entries still lands in one person.
    """
    canonical_of: dict[str, str] = {}
    former: dict[str, list[str]] = defaultdict(list)
    unmatched: list[str] = []
    for decision in overrides.get("decisions", []):
        if decision.get("decision") != "merge":
            continue
        keys = [canonical_of.get(k, k) for k in decision["keys"]]
        present = sorted({k for k in keys if k in grouped})
        unmatched.extend(k for k in keys if k not in grouped)
        if len(present) < 2:
            continue

        def earliest(key: str) -> int:
            return min(order.get(r["election"], len(order)) for r in grouped[key])

        canonical = min(present, key=lambda k: (earliest(k), k))
        for key in present:
            if key == canonical:
                continue
            grouped[canonical].extend(grouped.pop(key))
            former[canonical].append(key)
            former[canonical].extend(former.pop(key, []))
            canonical_of[key] = canonical
            for alias, target in canonical_of.items():
                if target == key:
                    canonical_of[alias] = canonical
    return former, unmatched


def build_index(
    data_root: Path,
    registry: list[dict] | None = None,
    overrides: dict | None = None,
    concept_map: dict | None = None,
) -> dict:
    registry = load_registry() if registry is None else registry
    overrides = load_overrides() if overrides is None else overrides
    concept_map = load_concept_map() if concept_map is None else concept_map
    workplace_paths = [
        concept_map["concepts"][name]["paths"] for name in WORKPLACE_CONCEPTS
    ]
    kind_of = {e["id"]: e.get("kind") for e in registry}
    people: dict[str, dict] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    total = missing_birth = year_only = 0
    newest_parse = ""
    seen_elections: set[str] = set()
    municipalities: set[str] = set()
    unresolved_municipalities: set[str] = set()

    for election_dir in sorted(p for p in data_root.iterdir() if p.is_dir()):
        election_id = election_dir.name
        seen_elections.add(election_id)
        for path in sorted(election_dir.glob("*.json")):
            if path.name == "anomalies.jsonl":
                continue
            record = json.loads(path.read_text(encoding="utf-8"))
            total += 1
            # The corpus's own vintage: the newest record `provenance.parsedAt`
            # (issue #89). ISO-8601 UTC strings compare as timestamps.
            provenance = record.get("provenance")
            if isinstance(provenance, dict):
                parsed_at = provenance.get("parsedAt")
                if isinstance(parsed_at, str) and parsed_at > newest_parse:
                    newest_parse = parsed_at
            name = normalize_name(record.get("candidateName"))
            birth = birth_key_of(record)
            if birth is None:
                missing_birth += 1
            elif birth.startswith("~"):
                year_only += 1
            key = person_key(name, birth)
            # The candidacy itself — office, municipality, elected — resolves
            # through scraper/shared/kandidatura.py, the one resolver over the
            # corpus's five kandidatavimas shapes (issue #93).
            candidacy = kandidatura(record, kind_of.get(election_id))
            if candidacy["savivaldybe"]:
                municipalities.add(candidacy["savivaldybe"])
                if candidacy["savivaldybe-id"] is None:
                    # A wording scraper/municipalities.json does not claim
                    # (issue #137): it still gets a facet row of its own, so
                    # nothing is hidden, and the run reports it so the
                    # registry gets the alias rather than the facet a twin.
                    unresolved_municipalities.add(candidacy["savivaldybe-raw"])
            workplace = None
            for paths in workplace_paths:
                mapped = paths.get(election_id)
                if mapped is None:
                    continue
                value = field_coverage.concept_value(record, mapped)
                if isinstance(value, str) and value.strip():
                    workplace = value.strip()
                    break
            grouped[key].append(
                {
                    "election": election_id,
                    "candidateId": record.get("candidateId"),
                    "displayName": record.get("candidateName"),
                    "birthKey": birth,
                    "elected": candidacy["isrinktas"],
                    "money": money_of(record),
                    "litas": declared_in_litas(record),
                    "employmentIncome": income_is_employment_only(record),
                    # The canonical nominator (issue #82): the registry id the
                    # record's raw nominator string joins to, None on the
                    # presidential elections that publish none. The raw string
                    # stays in the record file; the id is what groups one
                    # party's candidacies across its dash glyphs and renames.
                    "party": partija(record, election_id)["partija-id"],
                    "municipality": candidacy["savivaldybe"],
                    # The kind decides the office for every other election, so
                    # the flag is only carried where the ballot had two.
                    "mayor": candidacy["vaidmuo"] == ROLE_MAYOR
                    and kind_of.get(election_id) == "savivaldybiu",
                    "workplace": workplace,
                    "educationRank": issilavinimas(record, election_id)["rangas"],
                }
            )

    order = {e["id"]: i for i, e in enumerate(registry)}
    former, unmatched_override_keys = apply_merges(grouped, overrides, order)
    pid_of: dict[str, str] = {}
    # Municipality names are interned: the corpus writes ~100k of them, so
    # each candidacy carries an index into the top-level "municipalities"
    # list instead of the string. The names are the registry's official ones
    # (scraper/municipalities.json, issue #137): the 127 published wordings
    # are 62 bodies, and the facet used to list all 127.
    municipality_list = sorted(municipalities)
    municipality_index = {name: i for i, name in enumerate(municipality_list)}

    def best_birth(records: list[dict]) -> str | None:
        # Like the display name, the shown birth follows the latest word:
        # within a merged person the fragments can disagree — the 1996
        # archive's prose-recovered date is a day off VRK's labelled field
        # for Edmund Šot — and the later, labelled publication is the
        # stronger source. A full date beats a bare ~year from any era.
        for wanted in ("date", "year"):
            for r in reversed(records):
                b = r["birthKey"]
                if b and (wanted == "date") != b.startswith("~"):
                    return b
        return None

    for key, records in grouped.items():
        records.sort(key=lambda r: order.get(r["election"], len(order)))
        name = key.rpartition("|")[0]
        pid = person_pid(key)
        if pid in pid_of:
            raise ValueError(
                f"pid collision: {key!r} and {pid_of[pid]!r} both hash to {pid}"
            )
        pid_of[pid] = key
        people[key] = {
            "k": key,
            "pid": pid,
            # The natural keys merged into this person (issue #96) — the
            # dashboard resolves an old deep link through them and folds
            # their names into search, so a maiden-name search still finds
            # the person whose display name is the married one.
            **({"ak": sorted(former[key])} if key in former else {}),
            "n": records[-1]["displayName"] or name,
            "b": best_birth(records),
            # The record file is derivable: data/<id>/<c>-<id>.json.
            # "w" is the tri-state elected flag: true, false, or no key where
            # no results exist — three states the dashboard renders apart.
            # "m" is [privalomas-registruoti-turtas, pinigines-lesos,
            # gautos-pajamos] in euro, nulls where not declared/published;
            # "lt" marks a declaration published in litas and converted, and
            # "ds" an income figure that is the 1990s form's employment row
            # rather than a declared total (the `deklaruotos-pajamos` concept).
            # "p" is the canonical nominator id, "sv" an index into the
            # top-level municipalities list, "r": "m" a mayoral run on a
            # council-and-mayor ballot (the kind decides every other office),
            # "wp" the workplace/position string the search box matches, and
            # "ed" the education rank in scraper/shared/education.py's
            # 13-tier ordinal (the top-level educationLevels list).
            "e": [
                {
                    "id": r["election"],
                    "c": r["candidateId"],
                    **({"w": r["elected"]} if r["elected"] is not None else {}),
                    **({"m": r["money"]} if any(v is not None for v in r["money"]) else {}),
                    **({"lt": True} if r["litas"] and any(v is not None for v in r["money"]) else {}),
                    **({"ds": True} if r["employmentIncome"] else {}),
                    **({"p": r["party"]} if r["party"] else {}),
                    **(
                        {"sv": municipality_index[r["municipality"]]}
                        if r["municipality"]
                        else {}
                    ),
                    **({"r": "m"} if r["mayor"] else {}),
                    **({"wp": r["workplace"]} if r["workplace"] else {}),
                    **({"ed": r["educationRank"]} if r["educationRank"] else {}),
                }
                for r in records
            ],
        }

    entries = sorted(people.values(), key=lambda p: (-len(p["e"]), p["n"] or ""))
    multi = sum(1 for p in entries if len({e["id"] for e in p["e"]}) > 1)
    # Only the elections actually present are carried into people.json; the
    # dashboard reads its labels, chronology and term grouping (`parent`)
    # from this list and nothing else. An unregistered directory keeps its
    # raw id as its own label, and is reported so it gets a registry entry
    # rather than shipping as a slug.
    # The registry rows for every party id the index actually uses, so the
    # dashboard can label a candidacy's "p" without carrying scraper/parties.json.
    # "pr" is the entry's `predecessors` (issue #123): the organisations it
    # continues -- the merged parties behind TS-LKD, the committee and the
    # 2011 coalition behind the Vieningas Kaunas party -- which the party
    # facet offers as one lineage row beside the entry's own. The list is
    # the registry's whole; an id a subset build lacks is not offered.
    used_party_ids = sorted({e["p"] for p in entries for e in p["e"] if "p" in e})
    parties = {}
    for pid in used_party_ids:
        data = party_entry(pid)
        parties[pid] = {
            "n": data.get("shortName") or data["name"],
            "t": data["type"],
            # The full name too where "n" is a short one, so the search box
            # can match either ("valstiečių" finds LVŽS).
            **(
                {"f": data["name"]}
                if data.get("shortName") and data["shortName"] != data["name"]
                else {}
            ),
            **({"pr": list(data["predecessors"])} if data.get("predecessors") else {}),
        }

    missing_labels = [t for t in EDUCATION_LEVELS if t not in EDUCATION_LEVEL_LABELS]
    stale_labels = [t for t in EDUCATION_LEVEL_LABELS if t not in EDUCATION_LEVELS]
    if missing_labels or stale_labels:
        raise ValueError(
            f"EDUCATION_LEVEL_LABELS out of step with education.LEVELS: "
            f"missing {missing_labels}, stale {stale_labels}"
        )

    won = sum(1 for p in entries for e in p["e"] if e.get("w") is True)
    lost = sum(1 for p in entries for e in p["e"] if e.get("w") is False)

    return {
        "elections": [e for e in registry if e["id"] in seen_elections],
        "unregisteredElections": sorted(seen_elections - set(order)),
        "unmatchedOverrideKeys": sorted(unmatched_override_keys),
        "unresolvedMunicipalities": sorted(unresolved_municipalities),
        "parties": parties,
        "municipalities": municipality_list,
        # The 13-tier education ordinal, rank order ("ed" is a 1-based index
        # into it); labels ride here because the slugs are ASCII-folded and
        # would de-slug without their diacritics.
        "educationLevels": [
            {"id": t, "label": EDUCATION_LEVEL_LABELS[t]} for t in EDUCATION_LEVELS
        ],
        "stats": {
            # What this index is a snapshot *of* (issue #89): when it was
            # built, by parsers at which commit, over a corpus whose newest
            # record was parsed when. Two builds that disagree now say why.
            "generatedAt": utc_now_iso(),
            "parserCommit": parser_commit(),
            "corpusParsedAt": newest_parse or None,
            "records": total,
            "persons": len(entries),
            "personsInMultipleElections": multi,
            "recordsWithoutBirthDate": missing_birth,
            "recordsWithBirthYearOnly": year_only,
            "mergedPersons": len(former),
            "candidaciesWon": won,
            "candidaciesLost": lost,
            "candidaciesWithoutResultsData": total - won - lost,
        },
        "people": entries,
    }


def main() -> int:
    if not DATA_ROOT.is_dir():
        print(f"No {DATA_ROOT}/ here — run from the repo root.", file=sys.stderr)
        return 1
    index = build_index(DATA_ROOT)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    stats = index["stats"]
    print(f"vintage:                  corpus parsed ≤ {stats['corpusParsedAt']}, index built by {stats['parserCommit']}")
    print(f"records:                  {stats['records']}")
    print(f"distinct persons:         {stats['persons']}")
    print(f"in multiple elections:    {stats['personsInMultipleElections']}")
    print(f"records w/o birth date:   {stats['recordsWithoutBirthDate']} (grouped by name alone)")
    print(f"records w/ year only:     {stats['recordsWithBirthYearOnly']} (grouped by name + ~year)")
    print(f"override-merged persons:  {stats['mergedPersons']} ({OVERRIDES_PATH})")
    print(f"nominators used:          {len(index['parties'])} registry entries")
    print(
        f"elected:                  {stats['candidaciesWon']} won, "
        f"{stats['candidaciesLost']} lost, "
        f"{stats['candidaciesWithoutResultsData']} without results data"
    )
    print(f"municipalities:           {len(index['municipalities'])} (scraper/municipalities.json bodies)")
    generals = sum(1 for e in index["elections"] if "parent" not in e)
    print(
        f"elections:                {len(index['elections'])} of {len(load_registry())} registered "
        f"({generals} general, {len(index['elections']) - generals} grouped under a parent)"
    )
    print(f"wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size // 1024} KB)")
    failed = False
    unregistered = index["unregisteredElections"]
    if unregistered:
        print(
            f"\n{len(unregistered)} election(s) have no entry in {REGISTRY_PATH} and will\n"
            "render as raw ids — add them there:",
            file=sys.stderr,
        )
        for eid in unregistered:
            print(f"  {eid}", file=sys.stderr)
        failed = True
    unresolved = index["unresolvedMunicipalities"]
    if unresolved:
        print(
            f"\n{len(unresolved)} municipality wording(s) no entry of scraper/municipalities.json claims —\n"
            "each is a facet row of its own until the registry gets the alias:",
            file=sys.stderr,
        )
        for form in unresolved:
            print(f"  {form}", file=sys.stderr)
        failed = True
    stale = index["unmatchedOverrideKeys"]
    if stale:
        print(
            f"\n{len(stale)} override key(s) in {OVERRIDES_PATH} match no person —\n"
            "the corpus moved under the override file; fix the keys:",
            file=sys.stderr,
        )
        for key in stale:
            print(f"  {key}", file=sys.stderr)
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
