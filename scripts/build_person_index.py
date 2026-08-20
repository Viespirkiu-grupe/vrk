"""Build the cross-election person index the dashboard reads.

One person appears in many elections under no shared VRK identifier — the
per-election rkndId is a registration id, not a person id — so identity is
resolved by normalized name + birth date. Measured over the 33,119-record
corpus: birth date is present on 33,118 records, the pair collides for zero
same-election record pairs, and 305 names are shared by people with distinct
birth dates, which name-only matching would have wrongly merged. A record
without a birth date groups by name alone and is flagged; there are two, and
the second is a known duplicate rather than a second person. VRK issued Marija
Puč two candidate ids in the 2015 Trakai repeat election and published the
council one as an unfilled "Rengiama" page, so that record has a name and no
birth date and splits off from her real entry. Merging it on name alone is
exactly what the birth-date key exists to prevent, so it is left split and
recorded here instead — see docs/DATASET.md.

Run from the repo root:

    python scripts/build_person_index.py

Reads data/<election-id>/*.json, writes dashboard/people.json, and prints the
audit counts so a run is its own sanity check.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

DATA_ROOT = Path("data")
OUTPUT_PATH = Path("dashboard/people.json")

# Chronological order; the dashboard renders whatever appears here and sorts
# unknown election ids after these.
ELECTION_ORDER = [
    "2015-kovo-1-savivaldybiu",
    "2015-kovo-1-seimo-zirmunai",
    "2015-birzelio-7-seimo-varena-eisiskes",
    "2015-birzelio-7-pakartotiniai-sirvintos-trakai",
    "2015-birzelio-21-pakartotiniai-silutes",
    "2015-lapkricio-8-telsiu-mero",
    "2016-seimo",
    "2017-balandzio-23-meru",
    "2017-balandzio-23-seimo-anyksciai-panevezys",
    "2017-rugsejo-10-marijampoles-mero",
    "2018-rugsejo-16-seimo-zanavykai",
    "2019-kovo-3-savivaldybiu-tarybu",
    "2019-prezidento",
    "2019-ep",
    "2019-rugsejo-8-seimo",
    "2020-seimo",
    "2021-balandzio-11-radviliskio-mero",
    "2021-spalio-10-meru",
    "2023-kovo-5-savivaldybiu-tarybu-ir-meru",
    "2023-geguzes-7-visagino-mero",
    "2023-rugsejo-3-seimo-raseiniai-kedainiai",
    "2023-spalio-8-kupiskio-mero",
    "2024-prezidento",
    "2024-ep",
    "2024-seimo",
    "2025-kovo-16-meru",
]


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
    return None


def elected_note_of(record: dict) -> str | None:
    normalized = record.get("normalized") or {}
    profilis = normalized.get("profilis")
    if isinstance(profilis, dict):
        note = profilis.get("pastaba")
        if isinstance(note, str) and note.startswith("Išrink"):
            return note
    return None


# The three asset/income fields every election module normalizes under the
# same keys. Carried into the index so the dashboard can chart and rank
# without fetching 33k records.
MONEY_FIELDS = ("privalomas-registruoti-turtas", "pinigines-lesos", "gautos-pajamos")


def money_of(record: dict) -> list[float | None]:
    declarations = (record.get("normalized") or {}).get("turto-ir-pajamu-deklaracijos")
    values: list[float | None] = []
    for field in MONEY_FIELDS:
        raw = declarations.get(field) if isinstance(declarations, dict) else None
        if isinstance(raw, (int, float)):
            values.append(float(raw))
        elif isinstance(raw, str):
            try:
                values.append(float(raw.replace(" ", "").replace(",", ".")))
            except ValueError:
                values.append(None)
        else:
            values.append(None)
    return values


def person_key(name: str | None, birth: str | None) -> str:
    return f"{name or '?'}|{birth or '?'}"


def build_index(data_root: Path) -> dict:
    people: dict[str, dict] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    total = missing_birth = 0

    for election_dir in sorted(p for p in data_root.iterdir() if p.is_dir()):
        election_id = election_dir.name
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
                }
            )

    order = {eid: i for i, eid in enumerate(ELECTION_ORDER)}
    for key, records in grouped.items():
        records.sort(key=lambda r: order.get(r["election"], len(order)))
        name, _, birth = key.rpartition("|")
        people[key] = {
            "k": key,
            "n": records[-1]["displayName"] or name,
            "b": None if birth == "?" else birth,
            # The record file is derivable: data/<id>/<c>-<id>.json.
            # "m" is [privalomas-registruoti-turtas, pinigines-lesos,
            # gautos-pajamos], nulls where not declared/published.
            "e": [
                {
                    "id": r["election"],
                    "c": r["candidateId"],
                    **({"w": True} if r["elected"] else {}),
                    **({"m": r["money"]} if any(v is not None for v in r["money"]) else {}),
                }
                for r in records
            ],
        }

    entries = sorted(people.values(), key=lambda p: (-len(p["e"]), p["n"] or ""))
    multi = sum(1 for p in entries if len({e["id"] for e in p["e"]}) > 1)
    return {
        "electionOrder": ELECTION_ORDER,
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
    print(f"wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
