"""Find person entries that may be the same human under a changed name.

The person index keys identity by name + birth key, which splits anyone who
changed their surname between elections (typically marriage). This review
finds the plausible splits without merging anything: within each birth key,
persons sharing a first name but differing in surname are paired and scored,
and persons whose names are the same tokens in a different order are paired
regardless of first name (the 1997 municipal archive stores a few names
surname-first).

  strong       a *surname* token links the two — the shared token closes one
               of the names or carries a female-surname suffix (the
               double-barrelled married name keeps the maiden name:
               RUTKAUSKAITĖ vs RUTKAUSKAITĖ-NORKŪNIENĖ), or the maiden stem
               matches the married form (-YTĖ/-AITĖ/-UTĖ/-ŪTĖ/-IŪTĖ → -IENĖ
               with a shared stem), or the names are one token multiset in
               two orders
  given-name   only a shared *middle* token links them (MARIJA, ALGIRDAS) —
               the token sits mid-name in both and has no surname morphology,
               so it is somebody's second given name, not a kept surname;
               review these with actual evidence, they are the scorer's
               known weak spot
  weak         only the first name and birth key match

A pair whose one surname is literally the other plus hyphenated or appended
tokens is additionally marked `extension` — those needed no judgement in the
issue #96 review, only confirmation.

Decisions do not belong here: an accepted merge or a rejected pair is an
entry in scraper/person_overrides.json (checked in, applied by
scripts/build_person_index.py). This script joins that file back in, so a
reviewed pair prints as decided and only the undecided remainder demands
attention. A merged pair disappears from people.json and therefore from this
report; a `distinct` pair stays but is marked.

Run from the repo root after building the index:

    python scripts/build_person_index.py
    python scripts/find_identity_merge_candidates.py

Writes dashboard/merge-review.csv (gitignored — it is derived output; the
record of decisions is the override file) and prints the counts plus any
undecided strong pairs.
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
OVERRIDES_PATH = Path("scraper/person_overrides.json")

MAIDEN_SUFFIXES = ("YTĖ", "AITĖ", "UTĖ", "ŪTĖ", "IŪTĖ")
#: Suffixes that mark a token as a surname wherever it sits in the name —
#: the married -IENĖ plus the maiden forms. A shared mid-name token without
#: one of these (MARIJA, ALGIRDAS, LILIA) is a second given name, and pairs
#: linked only by one are the review's known false-positive shape.
SURNAME_SUFFIXES = MAIDEN_SUFFIXES + ("IENĖ",)


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


def tokens_of(surname: str) -> list[str]:
    return [t for t in re.split(r"[-\s]+", surname) if t]


def score_pair(surname_a: str, surname_b: str) -> str:
    tokens_a, tokens_b = tokens_of(surname_a), tokens_of(surname_b)
    shared = set(tokens_a) & set(tokens_b)
    finals = {tokens_a[-1] if tokens_a else "", tokens_b[-1] if tokens_b else ""}
    if any(t in finals or t.endswith(SURNAME_SUFFIXES) for t in shared):
        return "strong"
    for maiden, married in ((surname_a, surname_b), (surname_b, surname_a)):
        stem = maiden_stem(maiden.split("-")[0])
        if stem and any(
            token.endswith("IENĖ") and token.startswith(stem)
            for token in tokens_of(married)
        ):
            return "strong"
    if shared:
        return "given-name"
    return "weak"


def is_extension(name_a: str, name_b: str) -> bool:
    """One full name is the other plus extra tokens, order preserved.

    Catches the no-judgement shapes of the issue #96 review: the hyphenated
    married addition (MORKŪNAITĖ → MORKŪNAITĖ-MIKULĖNIENĖ), the prefixed
    maiden name (MOGENIENĖ → VYSKUPAITYTĖ-MOGENIENĖ), the space-appended
    surname (VITKAUSKAITĖ → VITKAUSKAITĖ BERNARD) and the middle name
    present on one side only (ANTANAS PETUŠKA → ANTANAS JUOZAS PETUŠKA).
    """
    tokens_a = [t for t in re.split(r"[-\s]+", name_a.upper()) if t]
    tokens_b = [t for t in re.split(r"[-\s]+", name_b.upper()) if t]
    if len(tokens_a) == len(tokens_b):
        return False
    short, long = sorted((tokens_a, tokens_b), key=len)
    it = iter(long)
    return all(token in it for token in short)


def load_decisions(path: Path = OVERRIDES_PATH) -> dict[frozenset[str], str]:
    if not path.exists():
        return {}
    overrides = json.loads(path.read_text(encoding="utf-8"))
    return {
        frozenset(d["keys"]): d["decision"]
        for d in overrides.get("decisions", [])
    }


def main() -> int:
    if not INDEX_PATH.exists():
        print(f"No {INDEX_PATH} — build it first.", file=sys.stderr)
        return 1
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    decisions = load_decisions()

    by_birth: dict[str, list[dict]] = defaultdict(list)
    for person in index["people"]:
        if person.get("b"):
            by_birth[person["b"]].append(person)

    def pair_row(a: dict, b: dict, score: str) -> dict:
        keys = frozenset((a["k"], b["k"]))
        return {
            "score": score,
            "extension": "extension" if is_extension(a["n"], b["n"]) else "",
            "decision": decisions.get(keys, ""),
            "birth": a["b"],
            "name_a": a["n"],
            "name_b": b["n"],
            "key_a": a["k"],
            "key_b": b["k"],
            "elections_a": ";".join(e["id"] for e in a["e"]),
            "elections_b": ";".join(e["id"] for e in b["e"]),
        }

    pairs = []
    for birth, persons in by_birth.items():
        if len(persons) < 2:
            continue
        by_first: dict[str, list[dict]] = defaultdict(list)
        for person in persons:
            first, surname = split_name(person["n"].upper())
            by_first[first].append({"person": person, "surname": surname})
        seen: set[frozenset[str]] = set()
        for first, group in by_first.items():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a["surname"] == b["surname"]:
                        continue
                    seen.add(frozenset((a["person"]["k"], b["person"]["k"])))
                    pairs.append(
                        pair_row(
                            a["person"],
                            b["person"],
                            score_pair(a["surname"], b["surname"]),
                        )
                    )
        # Same tokens in a different order — the surname-first archive names.
        # These share no leading first name, so the loop above never sees
        # them.
        by_tokens: dict[frozenset[str], list[dict]] = defaultdict(list)
        for person in persons:
            by_tokens[frozenset(person["n"].upper().split())].append(person)
        for group in by_tokens.values():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if frozenset((a["k"], b["k"])) in seen:
                        continue
                    pairs.append(pair_row(a, b, "strong"))

    rank = {"strong": 0, "given-name": 1, "weak": 2}
    pairs.sort(key=lambda p: (rank[p["score"]], p["birth"]))
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pairs[0]) if pairs else ["score"])
        writer.writeheader()
        writer.writerows(pairs)

    strong = [p for p in pairs if p["score"] == "strong"]
    given = [p for p in pairs if p["score"] == "given-name"]
    undecided = [p for p in strong + given if not p["decision"]]
    print(f"pairs sharing birth key + first name: {len(pairs)}")
    print(f"strong (surname morphology links them): {len(strong)}")
    print(f"given-name only (review with evidence): {len(given)}")
    print(f"decided in {OVERRIDES_PATH}: {sum(1 for p in pairs if p['decision'])}")
    print(f"undecided strong/given-name: {len(undecided)}")
    for p in undecided:
        print(f"  [{p['score']}] {p['birth']}  {p['name_a']}  <->  {p['name_b']}")
    print(f"wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
