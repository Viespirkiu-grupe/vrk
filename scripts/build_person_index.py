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
candidate page, so all 906 of its records group by name alone rather than
name+birth-date — a real, structural gap in this identity key, not a handful
of flagged exceptions. A same-named person appearing only within this family
cannot be told apart from a namesake by this index. The 1997 municipal
archive family (`1997-kovo-23-savivaldybiu-tarybu`,
`1997-birzelio-29-svenciniu-tarybos-pakartotiniai`;
`scraper/shared/savivaldybiu_archive_1997.py`) does publish birth date, under
the corpus's usual `anketa.gimimo-data`, so it needs no special case here.

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

import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

DATA_ROOT = Path("data")
OUTPUT_PATH = Path("dashboard/people.json")

REGISTRY_PATH = Path("scraper/elections.json")


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
    # every one of its records groups by name alone; see docs/DATASET.md.
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
    values: list[float | None] = []
    for field in MONEY_FIELDS:
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


def person_key(name: str | None, birth: str | None) -> str:
    return f"{name or '?'}|{birth or '?'}"


def build_index(data_root: Path, registry: list[dict] | None = None) -> dict:
    registry = load_registry() if registry is None else registry
    people: dict[str, dict] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    total = missing_birth = 0
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
            birth = birth_date_of(record)
            if birth is None:
                missing_birth += 1
            key = person_key(name, birth)
            grouped[key].append(
                {
                    "election": election_id,
                    "candidateId": record.get("candidateId"),
                    "displayName": record.get("candidateName"),
                    "elected": elected_note_of(record),
                    "money": money_of(record),
                    "litas": declared_in_litas(record),
                }
            )

    order = {e["id"]: i for i, e in enumerate(registry)}
    for key, records in grouped.items():
        records.sort(key=lambda r: order.get(r["election"], len(order)))
        name, _, birth = key.rpartition("|")
        people[key] = {
            "k": key,
            "n": records[-1]["displayName"] or name,
            "b": None if birth == "?" else birth,
            # The record file is derivable: data/<id>/<c>-<id>.json.
            # "m" is [privalomas-registruoti-turtas, pinigines-lesos,
            # gautos-pajamos] in euro, nulls where not declared/published;
            # "lt" marks a declaration published in litas and converted.
            "e": [
                {
                    "id": r["election"],
                    "c": r["candidateId"],
                    **({"w": True} if r["elected"] else {}),
                    **({"m": r["money"]} if any(v is not None for v in r["money"]) else {}),
                    **({"lt": True} if r["litas"] and any(v is not None for v in r["money"]) else {}),
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
    return {
        "elections": [e for e in registry if e["id"] in seen_elections],
        "unregisteredElections": sorted(seen_elections - set(order)),
        "stats": {
            "records": total,
            "persons": len(entries),
            "personsInMultipleElections": multi,
            "recordsWithoutBirthDate": missing_birth,
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
    print(f"elections:                {len(index['elections'])} of {len(load_registry())} registered")
    print(f"wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size // 1024} KB)")
    unregistered = index["unregisteredElections"]
    if unregistered:
        print(
            f"\n{len(unregistered)} election(s) have no entry in {REGISTRY_PATH} and will\n"
            "render as raw ids — add them there:",
            file=sys.stderr,
        )
        for eid in unregistered:
            print(f"  {eid}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
