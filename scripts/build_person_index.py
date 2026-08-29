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
`scraper/elections.json` -- id, first-round date, official Lithuanian name,
short label -- and are copied into people.json so the dashboard carries no
election list of its own. An election directory with no registry entry is
reported by the run and falls back to its raw id in the UI.

Run from the repo root:

    python scripts/build_person_index.py

Reads data/<election-id>/*.json and scraper/elections.json, writes
dashboard/people.json, and prints the audit counts so a run is its own sanity
check.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.shared.deklaracijos import (  # noqa: E402
    INCOME_EMPLOYMENT,
    deklaruotos_pajamos,
)
from scraper.shared.parties import entry as party_entry  # noqa: E402
from scraper.shared.parties import partija  # noqa: E402

DATA_ROOT = Path("data")
OUTPUT_PATH = Path("dashboard/people.json")

REGISTRY_PATH = Path("scraper/elections.json")
OVERRIDES_PATH = Path("scraper/person_overrides.json")


def load_registry(path: Path = REGISTRY_PATH) -> list[dict]:
    """Read scraper/elections.json, chronologically ordered.

    The file is stored sorted by date, but the order is re-derived here so a
    mis-sorted hand edit cannot quietly change the dashboard's chronology.
    The sort is stable and keyed on the date alone, so elections held on the
    same day -- 2015-06-07 ran a Seimas by-election and two repeat municipal
    votes -- keep the order the file lists them in, there being no other.
    """
    entries = json.loads(path.read_text(encoding="utf-8"))["elections"]
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


def elected_note_of(record: dict) -> str | None:
    normalized = record.get("normalized") or {}
    profilis = normalized.get("profilis")
    if isinstance(profilis, dict):
        note = profilis.get("pastaba")
        if isinstance(note, str) and note.startswith("Išrink"):
            return note
    # The 2012-2015 pages mark no winner; their electedness is joined in from
    # VRK's results tree as kandidatavimas.isrinktas (true/false, or null
    # when no results file was built). The 2019/2023 municipal modules set
    # the same flag from their listings, alongside the page's own note.
    candidacy = record.get("kandidatavimas")
    if isinstance(candidacy, dict) and candidacy.get("isrinktas") is True:
        seat = candidacy.get("isrinktasKaip")
        return f"Išrinktas ({seat})" if seat else "Išrinktas"
    # The 1996-1999 Seimas archive family carries the same flag, but its
    # candidacy is a *list* under `normalized` — a 1996 candidate could stand
    # in a constituency and on a party list at once — so the record is elected
    # if any one of its candidacies is, and the seat is that candidacy's.
    for entry in normalized.get("kandidatavimas") or []:
        if isinstance(entry, dict) and entry.get("isrinktas") is True:
            seat = entry.get("isrinktas-kaip")
            return f"Išrinktas ({seat})" if seat else "Išrinktas"
    return None


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

# The 2012-2015 pages declare in litas (`turto-ir-pajamu-deklaracijos.valiuta`
# is "Lt"); everything from 2016 on is in euro. The index converts at the
# irrevocable LTL/EUR conversion rate fixed for the 2015-01-01 changeover so
# that one person's series is comparable across the switch, and flags the
# candidacy so the dashboard can say the figure was converted.
LITAS_PER_EURO = 3.4528


def declared_in_litas(record: dict) -> bool:
    declarations = (record.get("normalized") or {}).get("turto-ir-pajamu-deklaracijos")
    return isinstance(declarations, dict) and declarations.get("valiuta") == "Lt"


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
        if isinstance(raw, (int, float)):
            values.append(round(float(raw) / divisor, 2))
        elif isinstance(raw, str):
            try:
                values.append(round(float(raw.replace(" ", "").replace(",", ".")) / divisor, 2))
            except ValueError:
                values.append(None)
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
) -> dict:
    registry = load_registry() if registry is None else registry
    overrides = load_overrides() if overrides is None else overrides
    people: dict[str, dict] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    total = missing_birth = year_only = 0
    seen_elections: set[str] = set()

    for election_dir in sorted(p for p in data_root.iterdir() if p.is_dir()):
        election_id = election_dir.name
        seen_elections.add(election_id)
        for path in sorted(election_dir.glob("*.json")):
            if path.name == "anomalies.jsonl":
                continue
            record = json.loads(path.read_text(encoding="utf-8"))
            total += 1
            name = normalize_name(record.get("candidateName"))
            birth = birth_key_of(record)
            if birth is None:
                missing_birth += 1
            elif birth.startswith("~"):
                year_only += 1
            key = person_key(name, birth)
            grouped[key].append(
                {
                    "election": election_id,
                    "candidateId": record.get("candidateId"),
                    "displayName": record.get("candidateName"),
                    "birthKey": birth,
                    "elected": elected_note_of(record),
                    "money": money_of(record),
                    "litas": declared_in_litas(record),
                    "employmentIncome": income_is_employment_only(record),
                    # The canonical nominator (issue #82): the registry id the
                    # record's raw nominator string joins to, None on the
                    # presidential elections that publish none. The raw string
                    # stays in the record file; the id is what groups one
                    # party's candidacies across its dash glyphs and renames.
                    "party": partija(record, election_id)["partija-id"],
                }
            )

    order = {e["id"]: i for i, e in enumerate(registry)}
    former, unmatched_override_keys = apply_merges(grouped, overrides, order)
    pid_of: dict[str, str] = {}

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
            # "m" is [privalomas-registruoti-turtas, pinigines-lesos,
            # gautos-pajamos] in euro, nulls where not declared/published;
            # "lt" marks a declaration published in litas and converted, and
            # "ds" an income figure that is the 1990s form's employment row
            # rather than a declared total (the `deklaruotos-pajamos` concept).
            "e": [
                {
                    "id": r["election"],
                    "c": r["candidateId"],
                    **({"w": True} if r["elected"] else {}),
                    **({"m": r["money"]} if any(v is not None for v in r["money"]) else {}),
                    **({"lt": True} if r["litas"] and any(v is not None for v in r["money"]) else {}),
                    **({"ds": True} if r["employmentIncome"] else {}),
                    **({"p": r["party"]} if r["party"] else {}),
                }
                for r in records
            ],
        }

    entries = sorted(people.values(), key=lambda p: (-len(p["e"]), p["n"] or ""))
    multi = sum(1 for p in entries if len({e["id"] for e in p["e"]}) > 1)
    # Only the elections actually present are carried into people.json; the
    # dashboard reads its labels and chronology from this list and nothing
    # else. An unregistered directory keeps its raw id as its own label, and
    # is reported so it gets a registry entry rather than shipping as a slug.
    # The registry rows for every party id the index actually uses, so the
    # dashboard can label a candidacy's "p" without carrying scraper/parties.json.
    used_party_ids = sorted({e["p"] for p in entries for e in p["e"] if "p" in e})
    parties = {}
    for pid in used_party_ids:
        data = party_entry(pid)
        parties[pid] = {
            "n": data.get("shortName") or data["name"],
            "t": data["type"],
        }

    return {
        "elections": [e for e in registry if e["id"] in seen_elections],
        "unregisteredElections": sorted(seen_elections - set(order)),
        "unmatchedOverrideKeys": sorted(unmatched_override_keys),
        "parties": parties,
        "stats": {
            "records": total,
            "persons": len(entries),
            "personsInMultipleElections": multi,
            "recordsWithoutBirthDate": missing_birth,
            "recordsWithBirthYearOnly": year_only,
            "mergedPersons": len(former),
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
    print(f"records:                  {stats['records']}")
    print(f"distinct persons:         {stats['persons']}")
    print(f"in multiple elections:    {stats['personsInMultipleElections']}")
    print(f"records w/o birth date:   {stats['recordsWithoutBirthDate']} (grouped by name alone)")
    print(f"records w/ year only:     {stats['recordsWithBirthYearOnly']} (grouped by name + ~year)")
    print(f"override-merged persons:  {stats['mergedPersons']} ({OVERRIDES_PATH})")
    print(f"nominators used:          {len(index['parties'])} registry entries")
    print(f"elections:                {len(index['elections'])} of {len(load_registry())} registered")
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
