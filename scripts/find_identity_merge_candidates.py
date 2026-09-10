"""Find person entries that may be the same human under a different key.

The person index keys identity by name + birth key, so it splits a person
two ways: one who changed surname between elections (typically marriage),
and one whose pages do not all publish the same birth date. This review
finds the plausible splits without merging anything, in four passes.

**Same birth key, different name.** Within each birth key, persons sharing a
first name but differing in surname are paired and scored, and persons whose
names are the same tokens in a different order are paired regardless of
first name (the 1997 municipal archive stores a few names surname-first).

**A fragment key against its full-date twin** (issue #141). 222 persons are
keyed by name alone (`NAME|?`) or by birth *year* alone (`NAME|~YYYY`),
because the 1996-1999 Seimas archive family publishes no birth date; 147 of
them have exactly one same-named person with a full birth date (and an
agreeing year, where the fragment has one). Those are the same human, split
by the key, with 154 candidacies on the wrong side — VYTAUTAS LANDSBERGIS|?
beside |1932-10-18, EDUARDAS ŠABLINSKAS|~1957 holding two runs while
|1957-10-19 holds seventeen. The old passes could not form a single one of
those pairs: they bucket on the exact birth string and skip a falsy one, so
the dateless persons were invisible and a `~YYYY` bucket can by construction
never hold a full-date person. Running the script printed `1,370 pairs, 0
strong, 1 given-name, 0 undecided` — which reads as a fully reviewed corpus.

**Same birth date, different given name** (issue #141). The first two passes
pair only inside an exact first-name-token match, so 64 pairs sharing a
birth date and a surname were never scored — VIKTOR beside VIKTORAS
USPASKICH, GŽEGOŽ beside GRZEGORZ SAKSON, EDUARD beside EDVARD TRUSEVIČ.
21 of the 64 appear in the *same election*, which settles them the other
way: nobody stands twice on one ballot, so those are namesakes with the same
birthday (siblings, mostly) and the pass marks them so.

**Names that differ only in diacritics.** `score_pair` compared tokens
byte-wise, so JOLANTA BARTKUNIENĖ and JOLANTA BARTKŪNIENĖ on one birth date
scored `weak`. A name identical after NFD folding is the same name.

  strong       the two are one person on the evidence in the index alone:
               a *surname* token links them — the shared token closes one of
               the names or carries a female-surname suffix (the
               double-barrelled married name keeps the maiden name:
               RUTKAUSKAITĖ vs RUTKAUSKAITĖ-NORKŪNIENĖ), or the maiden stem
               matches the married form (-YTĖ/-AITĖ/-UTĖ/-ŪTĖ/-IŪTĖ → -IENĖ
               with a shared stem) — or the names are one token multiset in
               two orders, or identical after diacritic folding, or a
               fragment key whose name has exactly one full-date bearer
  given-name   only a shared *middle* token links them (MARIJA, ALGIRDAS) —
               the token sits mid-name in both and has no surname morphology,
               so it is somebody's second given name, not a kept surname;
               review these with actual evidence, they are the scorer's
               known weak spot
  weak         only the first name and birth key match
  same-ballot  the pair stands in one election, so it is two people whatever
               the names and dates say: nobody is on a ballot twice. The
               discriminator that separates VIKTOR/VIKTORAS USPASKICH from
               the 21 same-birthday namesakes

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
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

INDEX_PATH = Path("dashboard/people.json")
REGISTRY_PATH = Path("scraper/elections.json")
OUTPUT_PATH = Path("dashboard/merge-review.csv")
OVERRIDES_PATH = Path("scraper/person_overrides.json")

MAIDEN_SUFFIXES = ("YTĖ", "AITĖ", "UTĖ", "ŪTĖ", "IŪTĖ")
#: Suffixes that mark a token as a surname wherever it sits in the name —
#: the married -IENĖ plus the maiden forms. A shared mid-name token without
#: one of these (MARIJA, ALGIRDAS, LILIA) is a second given name, and pairs
#: linked only by one are the review's known false-positive shape.
SURNAME_SUFFIXES = MAIDEN_SUFFIXES + ("IENĖ",)


#: A person keyed by name alone, or by birth year alone: the 1996-1999 Seimas
#: archive family publishes no birth date, so `build_person_index` falls back
#: to `NAME|?` and `NAME|~YYYY`. `people.json` renders the first as a falsy
#: `b` and the second as `~YYYY`.
YEAR_ONLY = re.compile(r"^~(\d{4})$")
FULL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fold(text: str) -> str:
    """Upper-case and strip diacritics, for comparing names as names.

    `score_pair` compared tokens byte-wise, so JOLANTA BARTKUNIENĖ and
    JOLANTA BARTKŪNIENĖ on one birth date scored `weak` — a missing macron on
    one page is not a different surname.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", text.upper()) if not unicodedata.combining(c)
    )


def birth_year(birth: str | None) -> str | None:
    """The year a birth key pins, however coarsely, or None for name-only."""
    if not birth:
        return None
    match = YEAR_ONLY.match(str(birth))
    return match.group(1) if match else str(birth)[:4]


def is_fragment(person: dict) -> bool:
    """Is this person keyed by something less than a birth date?"""
    return not FULL_DATE.match(str(person.get("b") or ""))


def elections_of(person: dict) -> set[str]:
    return {entry["id"] for entry in person.get("e", [])}


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
    if fold(surname_a) == fold(surname_b):
        # The same surname with a diacritic missing on one page.
        return "strong"
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


def score_given_names(first_a: str, first_b: str, a: dict, b: dict) -> str:
    """Two persons with one birth date and one surname, by their given names.

    The discriminator is the ballot, not the spelling: nobody stands twice in
    one election, so a pair that shares one is two people whatever else
    agrees — which is what separates VIKTOR/VIKTORAS USPASKICH from the 21
    same-birthday namesakes among the 64 pairs this pass forms.
    """
    if elections_of(a) & elections_of(b):
        return "same-ballot"
    folded_a, folded_b = fold(first_a), fold(first_b)
    if folded_a == folded_b:
        return "strong"
    # A Lithuanian inflection of a foreign name — one is the other's stem:
    # VIKTOR/VIKTORAS, VLADIMIR/VLADIMIRAS, JAN/JANAS.
    if folded_a.startswith(folded_b) or folded_b.startswith(folded_a):
        return "strong"
    # A transliteration of one name — one letter apart: EDUARD/EDVARD,
    # WALDEMAR/VALDEMAR, ČESLOVAS/ČESLAVAS, LAIMONAS/LAIMONDAS. Two letters
    # apart is worth a look but not a claim (GŽEGOŽ/GRZEGORZ). The threshold
    # is a distance, not a prefix: a prefix rule misses every substitution in
    # the first four characters, which is where a transliteration differs.
    distance = edit_distance(folded_a, folded_b)
    longest = max(len(folded_a), len(folded_b))
    if distance <= 1:
        return "strong"
    if distance <= 2 and longest and distance / longest <= 0.34:
        return "given-name"
    return "weak"


def edit_distance(a: str, b: str, limit: int = 3) -> int:
    """Levenshtein distance, giving up at `limit` (returns limit then).

    Only the small distances matter here — a name three edits from another is
    a different name — so the row-by-row computation stops early.
    """
    if abs(len(a) - len(b)) > limit:
        return limit
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        if min(current) >= limit:
            return limit
        previous = current
    return min(previous[-1], limit)


#: Youngest anyone may stand for the Seimas or a council. A pair whose
#: full-date half was under this at an election its other half stood in is
#: two people, whatever the names agree on.
CANDIDACY_MIN_AGE_YEARS = 18


def too_young(birth: str, elections: set[str], held_on: dict[str, str]) -> str | None:
    """The election at which `birth` makes a candidate a minor, or None."""
    try:
        born = date.fromisoformat(birth)
    except ValueError:
        return None
    for election in sorted(elections):
        held = held_on.get(election)
        if not held:
            continue
        try:
            polling_day = date.fromisoformat(held)
        except ValueError:
            continue
        if (polling_day - born).days / 365.25 < CANDIDACY_MIN_AGE_YEARS:
            return election
    return None


def fragment_pairs(people: list[dict], pair_row, held_on: dict[str, str]) -> list[dict]:
    """Every fragment key beside the full-date persons who share its name.

    A fragment is `NAME|?` or `NAME|~YYYY` — the 1996-1999 Seimas archive
    family publishes no birth date. `strong` when the name has exactly one
    full-date bearer whose year agrees (or the fragment pins no year) and the
    two never stood in the same election; `same-ballot` when they did;
    `given-name` when the name has several bearers, which is a real
    ambiguity and needs a human.

    `impossible` is the third hard discriminator, beside the ballot: a
    full-date half who was under 18 at an election the fragment stood in is
    somebody else. It caught exactly one of the 147 pairs, and it was the
    same one whose two birthplaces contradicted — VYTAUTAS ASTRAUSKAS, born
    1982-09-11 on his 2019 municipal card and 14 years old at the 1996 Seimas
    election his namesake contested.
    """
    by_name: dict[str, list[dict]] = defaultdict(list)
    for person in people:
        if not is_fragment(person):
            by_name[fold(person["n"])].append(person)
    rows = []
    for fragment in people:
        if not is_fragment(fragment):
            continue
        year = birth_year(fragment.get("b"))
        bearers = [
            candidate
            for candidate in by_name.get(fold(fragment["n"]), [])
            if year is None or birth_year(candidate["b"]) == year
        ]
        for bearer in bearers:
            minor_at = too_young(
                str(bearer["b"]), elections_of(fragment) | elections_of(bearer), held_on
            )
            if elections_of(fragment) & elections_of(bearer):
                score = "same-ballot"
            elif minor_at:
                score = "impossible"
            elif len(bearers) == 1:
                score = "strong"
            else:
                score = "given-name"
            row = pair_row(fragment, bearer, score)
            row["note"] = f"under {CANDIDACY_MIN_AGE_YEARS} at {minor_at}" if minor_at else ""
            rows.append(row)
    return rows


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
            "note": "",
            "birth": a.get("b") or "",
            "birth_b": b.get("b") or "",
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

        # Same birth date, same surname, different given name (issue #141).
        # The two loops above pair only inside an exact first-name match, so
        # VIKTOR beside VIKTORAS USPASKICH was never formed.
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                a, b = persons[i], persons[j]
                if frozenset((a["k"], b["k"])) in seen:
                    continue
                first_a, surname_a = split_name(a["n"].upper())
                first_b, surname_b = split_name(b["n"].upper())
                if fold(surname_a) != fold(surname_b) or first_a == first_b:
                    continue
                seen.add(frozenset((a["k"], b["k"])))
                pairs.append(pair_row(a, b, score_given_names(first_a, first_b, a, b)))

    # A fragment key against the one full-date bearer of its name (#141).
    held_on = {
        entry["id"]: entry["date"]
        for entry in json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["elections"]
    }
    pairs.extend(fragment_pairs(index["people"], pair_row, held_on))

    rank = {"strong": 0, "given-name": 1, "same-ballot": 2, "impossible": 3, "weak": 4}
    pairs.sort(key=lambda p: (rank[p["score"]], p["birth"], p["name_a"]))
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pairs[0]) if pairs else ["score"])
        writer.writeheader()
        writer.writerows(pairs)

    strong = [p for p in pairs if p["score"] == "strong"]
    given = [p for p in pairs if p["score"] == "given-name"]
    same_ballot = [p for p in pairs if p["score"] == "same-ballot"]
    impossible = [p for p in pairs if p["score"] == "impossible"]
    undecided = [p for p in strong + given if not p["decision"]]

    # What the passes could *not* look at. Printed because "0 undecided" read
    # as "the corpus is reviewed" while 147 pairs the passes cannot form sat
    # in people.json (issue #141), and the same silence would come back the
    # moment a new key shape appears.
    fragments = [p for p in index["people"] if is_fragment(p)]
    paired_keys = {k for p in pairs for k in (p["key_a"], p["key_b"])}
    unpaired = [p for p in fragments if p["k"] not in paired_keys]

    print(f"pairs formed: {len(pairs)}")
    print(f"  strong (one person on the index's own evidence): {len(strong)}")
    print(f"  given-name only (review with evidence):          {len(given)}")
    print(f"  same-ballot (two people; nobody stands twice):   {len(same_ballot)}")
    print(f"  impossible (a minor at an election it stood in): {len(impossible)}")
    for p in impossible:
        print(f"      {p['name_a']} <-> {p['name_b']}: {p['note']}")
    print(f"  weak:                                            {len(pairs) - len(strong) - len(given) - len(same_ballot) - len(impossible)}")
    print(f"decided in {OVERRIDES_PATH}: {sum(1 for p in pairs if p['decision'])}")
    print(f"undecided strong/given-name: {len(undecided)}")
    for p in undecided[:60]:
        print(f"  [{p['score']}] {p['birth'] or '?':11} {p['name_a']}  <->  {p['name_b']}")
    if len(undecided) > 60:
        print(f"  ... and {len(undecided) - 60} more, in {OUTPUT_PATH}")
    print(
        f"fragment keys (NAME|? or NAME|~YYYY): {len(fragments)},"
        f" of which {len(unpaired)} have no same-named full-date person for this"
        " review to pair them with — nothing here says whether those are"
        " whole people or halves of one."
    )
    print(f"wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
