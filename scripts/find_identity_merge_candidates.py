"""Find person entries that may be the same human under a changed surname.

The person index keys identity by name + birth date, which splits anyone who
changed their surname between elections (typically marriage). This review
finds the plausible splits without merging anything: within each birth date,
persons sharing a first name but differing in surname are paired and scored.

  strong  one surname appears inside the other (double-barrelled married name
          keeps the maiden name: RUTKAUSKAITĖ vs RUTKAUSKAITĖ-NORKŪNIENĖ),
          or the maiden stem matches the married form (-YTĖ/-AITĖ/-UTĖ/-ŪTĖ/
          -IŪTĖ → -IENĖ with a shared stem)
  weak    only the first name and birth date match

Run from the repo root after building the index:

    python scripts/build_person_index.py
    python scripts/find_identity_merge_candidates.py

Writes dashboard/merge-review.csv (gitignored) and prints the counts plus the
strong pairs. Review is manual by design — a merge belongs in analysis, not
in the corpus.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

INDEX_PATH = Path("dashboard/people.json")
OUTPUT_PATH = Path("dashboard/merge-review.csv")

MAIDEN_SUFFIXES = ("YTĖ", "AITĖ", "UTĖ", "ŪTĖ", "IŪTĖ")


def split_name(name: str) -> tuple[str, str]:
    parts = name.split()
    if len(parts) < 2:
        return name, ""
    return parts[0], " ".join(parts[1:])


def maiden_stem(surname: str) -> str | None:
    for suffix in MAIDEN_SUFFIXES:
        if surname.endswith(suffix):
            return surname[: -len(suffix)]
    return None


def score_pair(surname_a: str, surname_b: str) -> str:
    tokens_a = set(re.split(r"[-\s]", surname_a))
    tokens_b = set(re.split(r"[-\s]", surname_b))
    if tokens_a & tokens_b:
        return "strong"
    for maiden, married in ((surname_a, surname_b), (surname_b, surname_a)):
        stem = maiden_stem(maiden.split("-")[0])
        if stem and any(
            token.endswith("IENĖ") and token.startswith(stem)
            for token in re.split(r"[-\s]", married)
        ):
            return "strong"
    return "weak"


def main() -> int:
    if not INDEX_PATH.exists():
        print(f"No {INDEX_PATH} — build it first.", file=sys.stderr)
        return 1
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    by_birth: dict[str, list[dict]] = defaultdict(list)
    for person in index["people"]:
        if person.get("b"):
            by_birth[person["b"]].append(person)

    pairs = []
    for birth, persons in by_birth.items():
        if len(persons) < 2:
            continue
        by_first: dict[str, list[dict]] = defaultdict(list)
        for person in persons:
            first, surname = split_name(person["n"].upper())
            by_first[first].append({"person": person, "surname": surname})
        for first, group in by_first.items():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a["surname"] == b["surname"]:
                        continue
                    pairs.append(
                        {
                            "score": score_pair(a["surname"], b["surname"]),
                            "birth": birth,
                            "name_a": a["person"]["n"],
                            "name_b": b["person"]["n"],
                            "elections_a": ";".join(e["id"] for e in a["person"]["e"]),
                            "elections_b": ";".join(e["id"] for e in b["person"]["e"]),
                        }
                    )

    pairs.sort(key=lambda p: (p["score"] != "strong", p["birth"]))
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["score", "birth", "name_a", "name_b", "elections_a", "elections_b"],
        )
        writer.writeheader()
        writer.writerows(pairs)

    strong = [p for p in pairs if p["score"] == "strong"]
    print(f"pairs sharing birth date + first name: {len(pairs)}")
    print(f"strong (surname morphology links them): {len(strong)}")
    for p in strong:
        print(f"  {p['birth']}  {p['name_a']}  <->  {p['name_b']}")
    print(f"wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
