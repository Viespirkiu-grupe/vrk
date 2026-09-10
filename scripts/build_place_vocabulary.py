"""Regenerate scraper/shared/vietovardziai.json from the corpus.

The 1996-1999 archive biographies print a birthplace in the locative
("Kaune", "Klaipėdoje", "Šiaulių rajone"); the rest of the corpus stores the
nominative. Suffix rules generate candidates and cannot decide between them
-- "-yje" yields both Panevėžys and Radviliškis -- so a candidate is accepted
only if it appears in this vocabulary. That lookup is the whole safety of the
conversion: a mis-parsed fragment produces no candidate here and is dropped
rather than written (`scraper/shared/seimo_archive_1990s.nominative_place`).

    python scripts/build_place_vocabulary.py --check      # does the tracked file match?
    python scripts/build_place_vocabulary.py --dry-run    # what would change
    python scripts/build_place_vocabulary.py              # rewrite it

**It is a whitelist, so it takes only names.** Built from `gimimo-vieta`
across every non-archive election, keeping values seen at least
`--min-count` times *and* shaped like a nominative place name (see
`looks_like_a_name`). Without that filter the rebuild adds 364 free-text
questionnaire answers to a precision whitelist -- `AKMENĖS RAJ.`,
`Akmenių k., Lazdijų r.`, `Ariogala,Raseinių raj.`, `BALTARUSIJA`
(issue #155).

The filter also *removes* 778 of the 1,100 entries the file has carried since
issue #63, and that costs nothing: measured over every archive record that
depends on this vocabulary, the surviving names resolve every one of the 18
that all 1,100 did. They could not have done otherwise -- a suffix rule
rewrites the *last* word of a locative head, so a comma-qualified,
parenthesised, all-caps or lower-cased entry can never be the result.
1,100 → 335 (322 kept plus 13 the corpus has gained since), and one record
more resolves: `rumbauskas-vitalijus`, "Irkutsko srityje" → "Irkutsko
sritis".

**How much this vocabulary now does.** 18 records, not 453. The file's header
claimed "1,357 of 21,951 distinct names, which resolves 454 of the archive's
571 birthplaces" and none of the five figures was ever reproducible -- the
file held 1,100 entries at its own commit. But the drift is not the whole
story: when issue #63 built this, the archive card's own `Gimimo vieta` field
was not being read, so the biography fallback was the only birthplace those
records had. Issue #69 then recovered the card field, and 873 of the 950
archive records take their birthplace from it. What is left for the locative
conversion is the 39 records with no card birthplace whose biography names a
place, of which 19 now resolve -- 9 of them through a multi-word nominative
("Krasnojarsko kraštas", "Vilniaus rajonas", "Kauno miestas") -- and the
other 20 are villages, parishes and Soviet-era regions no lookup would settle
("Adutiškio parapijoje", "Vakarų Kazachstane", "Nosotkos kaime").

`--check` is what keeps the file from drifting again: `tests/test_place_vocabulary.py`
runs it, so the tracked vocabulary is gated the way `docs/coverage-baseline.tsv`
is. Until issue #155 the script had no `--check`, no `--dry-run` and no
`--repo-root`, wrote on sight, and no test named it -- and it had been run
once, while the corpus grew from ~20 elections to 55.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

DATA_ROOT = Path("data")
OUTPUT_PATH = Path("scraper/shared/vietovardziai.json")

# The Seimas archive family, whose biography prose is the birthplace fallback
# for the records whose card leaves "Gimimo vieta" blank (see issue #69);
# converting that prose from the locative is what the vocabulary serves.
ARCHIVE_ELECTIONS = {
    "1996-spalio-20-seimo",
    "1997-kovo-23-seimo-pakartotiniai",
    "1997-gruodzio-21-seimo-pakartotiniai",
    "1998-kovo-22-seimo-pakartotiniai",
    "1998-lapkricio-15-seimo-pakartotiniai",
    "1999-kovo-21-seimo-pakartotiniai",
}

#: The abbreviated administrative qualifiers a questionnaire answer carries
#: and a nominative place name does not: `Alytaus r.`, `Akmenės raj.`,
#: `Adutiškio k.`, `Rumšiškių mst.`, `Irkutsko sr.`. Matched as a standalone
#: token with the full stop *optional*, because VRK's answers drop it as
#: often as not (`Alytaus r`, `Kauno m`, `Klaipėdos raj`) — requiring the
#: stop let 12 of them through. The spelled-out forms (`rajonas`, `miestas`,
#: `sritis`) are real nominative names and stay, which is why the token has
#: to end: `m` in `miestas` is not a qualifier.
_QUALIFIER = re.compile(r"(?:^|\s)(?:r|raj|sav|k|km|mst|m|apyl|sen|sr|apskr)\.?(?=\s|$)")


def looks_like_a_name(value: str) -> bool:
    """Is this a nominative place name rather than a questionnaire answer?

    The rejections, each measured against the 1,100 tracked entries and the
    1,464 the corpus offers: a comma (`Alsėdžiai, Plungės r.` — two places,
    not one name), a digit (`Alytaus raj. Punia 2`), an abbreviated
    administrative qualifier, a parenthetical (`Marijampolė (Kapsukas)`), and
    a capitalisation the suffix rules can never produce — all-caps (`AKMENĖ`)
    or lower (`alytus`), both of which are `Akmenė` and `Alytus` as a
    data-entry form shouted or whispered them.

    A *space* is not a rejection, deliberately. `Krasnojarsko kraštas`,
    `Vilniaus rajonas`, `Kauno miestas` and `Irkutsko sritis` are the
    multi-word nominatives this vocabulary exists for: those are exactly the
    conversions the archive biographies need ("Krasnojarsko krašte",
    "Vilniaus rajone"), and 9 of the 19 records it resolves are one of them.
    """
    letters = [c for c in value if c.isalpha()]
    return not (
        "," in value
        or "(" in value
        or any(character.isdigit() for character in value)
        or _QUALIFIER.search(value)
        or value.isupper()
        or (letters and letters[0].islower())
    )


def measure(data_root: Path, min_count: int) -> tuple[list[str], int, int]:
    """(the vocabulary, distinct names seen, names above the count floor)."""
    counts: collections.Counter[str] = collections.Counter()
    for election_dir in sorted(p for p in data_root.iterdir() if p.is_dir()):
        if election_dir.name in ARCHIVE_ELECTIONS:
            continue
        for path in election_dir.glob("*.json"):
            normalized = json.loads(path.read_text(encoding="utf-8")).get("normalized") or {}
            for section in ("anketa", "biografija"):
                data = normalized.get(section)
                place = data.get("gimimo-vieta") if isinstance(data, dict) else None
                if isinstance(place, str) and place.strip():
                    counts[place.strip()] += 1
    frequent = [name for name, count in counts.items() if count >= min_count]
    return sorted(n for n in frequent if looks_like_a_name(n)), len(counts), len(frequent)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--min-count", type=int, default=3)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--check", action="store_true", help="Exit 1 if the tracked file differs. Writes nothing."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would change. Writes nothing."
    )
    args = parser.parse_args()

    data_root = args.repo_root / DATA_ROOT
    output_path = args.repo_root / OUTPUT_PATH
    if not data_root.is_dir():
        print(f"No {data_root}/ here — run from the repo root.", file=sys.stderr)
        return 1

    places, distinct, frequent = measure(data_root, args.min_count)
    existing = json.loads(output_path.read_text(encoding="utf-8"))
    tracked = existing.get("places", [])
    added = sorted(set(places) - set(tracked))
    dropped = sorted(set(tracked) - set(places))

    print(
        f"{distinct} distinct names seen; {frequent} at count>={args.min_count};"
        f" {len(places)} of those are names"
    )
    if args.check or args.dry_run:
        if not added and not dropped:
            print(f"{output_path} matches the rebuild ({len(tracked)} entries).")
            return 0
        print(
            f"\n{output_path} differs from the rebuild:"
            f" {len(added)} to add, {len(dropped)} to drop",
            file=sys.stderr,
        )
        for name in added[:30]:
            print(f"    + {name}", file=sys.stderr)
        if len(added) > 30:
            print(f"    ... and {len(added) - 30} more to add", file=sys.stderr)
        for name in dropped[:30]:
            print(f"    - {name}", file=sys.stderr)
        if len(dropped) > 30:
            print(f"    ... and {len(dropped) - 30} more to drop", file=sys.stderr)
        print(
            "\nRun `python scripts/build_place_vocabulary.py` to rewrite it, then"
            " re-parse the 1996-1999 archive family so the change reaches the corpus.",
            file=sys.stderr,
        )
        return 1

    existing["places"] = places
    output_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {output_path}: {len(added)} added, {len(dropped)} dropped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
