"""Ask whether a value is *possible*, and gate the answers.

Three commands check the corpus and none of them asks this. `reparse_diff.py`
asks whether the corpus is what the parsers produce — it is, and a faithfully
parsed impossibility is still an impossibility. `field_coverage.py` asks
whether a field arrived — `gimimo-data` arrives on 99.8 % of records, and one
of them says a candidate was 1.4 years old. `anomalies-report` reads back what
the scrapers recorded going wrong, and of its 9,018 events across ten types
not one is about a value's plausibility (issue #152).

So this is the fourth question, in the same shape as the other three: one pass
over `data/`, a rule set, and a checked-in register of the findings that have
been looked at — `docs/plausibility-register.tsv`. A new finding fails the
run; a finding in the register with a reason does not.

    python scripts/value_plausibility.py              # measure, check, exit 1 on a new finding
    python scripts/value_plausibility.py --update     # after reviewing what it found
    python scripts/value_plausibility.py 2016-seimo   # one election

**The rules, and what each is calibrated against.**

`date-out-of-range` — an ISO date inside `normalized` whose year is outside
1900–2100. 39 values across six elections: `1111-11-11` five times,
`9999-12-31` six times, `0005-07-12`, `3003-05-20`, and a run of 2004
declarations whose `Pildymo data` reads `0204.05.04`. Every one of the 42
findings this gate reports was traced *verbatim* to its own record's
`rawData`, so all of them are VRK's typing carried faithfully rather than
parse damage — which is why they are registered rather than fixed.

`age-below-statutory-minimum` — a birth date putting a candidate under the
age the office requires on polling day. This fires **once**, and that is the
point: the age distribution is otherwise exact. The youngest candidate of
every large election sits on the statutory floor to within a tenth of a year
— Seimas 25.0–25.2 before the 2022 amendment and 21.0 after it, presidential
40.1–42.8, EP 21.1–23.9, municipal 18.1 and 20.0 — so a single record at
**1.4** is the one outlier in a flawless distribution, and it is the field
the person index keys identity on. `damanskis-adolfas`
(`1996-spalio-20-seimo`) carries `gimimo-data` 1995-05-22; the biography on
the same page names parents born 1908 and 1917.

`income-total-above-its-own-row` — a declaration whose total income exceeds
its own employment-income row by more than 10,000×. The archive parser's
`trusted()` guard already refuses a total the page's row 1 *contradicts from
below*, with a sub-litas tolerance for the era's truncation; the other
direction was unchecked. The threshold is read off the corpus rather than
picked: the two figures it flags are 29,603× and 12,383×, and the next
highest ratio in 112,218 declarations is 1,511× — a candidate with 170 Lt of
employment income and 257,170 Lt of total income, which is a business owner
and not an error. A threshold anywhere between those two numbers separates
them; 10,000 is the round one.

**What is deliberately not a rule.** The year-start / year-end asset pair
gets no ratio check. The two figures are a year apart and may legitimately
differ by any factor: the corpus holds a candidate whose year-start assets
were 0.01 Lt and whose year-end were 196,272, which is a house, not a
defect. A ratio there flags 60 records to catch one, and that one
(`korotajeva-nina`, 355,397,021 Lt against a year-start of 3,553 and no
declared income, occupation *bedarbė*) is already in
`build_candidacy_table.SOURCE_ERRORS`, which is where a reviewed money
outlier belongs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterator, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REGISTER = Path("docs/plausibility-register.tsv")
REGISTER_COLUMNS = ("rule", "election", "candidate", "path", "value", "why")

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: A year outside this is not a date anybody typed on purpose.
MIN_YEAR, MAX_YEAR = 1900, 2100

#: The age each office requires on polling day, and when it changed. The
#: Seimas floor was 25 until Lithuania's 2022 constitutional amendment
#: lowered it to 21, which the 2024 general is the first election under —
#: 21 of its 1,740 candidates are between 21.0 and 24.3, so a single flat
#: floor of 25 would report them all and a flat 21 would miss the one real
#: finding by a factor of fifteen.
STATUTORY_MIN_AGE: dict[str, tuple[tuple[str, int], ...]] = {
    "seimo": (("2022-01-01", 21), ("0001-01-01", 25)),
    "prezidento": (("0001-01-01", 40),),
    "ep": (("0001-01-01", 21),),
    "savivaldybiu": (("0001-01-01", 18),),
    "mero": (("0001-01-01", 18),),
}

#: Slack on the age floor, in years. VRK publishes the date and not the
#: minute, and a candidate whose birthday falls on polling day rounds either
#: way; the smallest real gap in the corpus is 1.4 against 21, so half a year
#: is generous and still cannot hide anything.
AGE_TOLERANCE_YEARS = 0.5

#: The ratio at which a declaration's total income stops being large and
#: starts being impossible. See the module docstring for why 10,000.
INCOME_RATIO_LIMIT = 10_000

DECLARATION_KEY = "turto-ir-pajamu-deklaracijos"
INCOME_TOTAL_KEY = "gautos-pajamos"
INCOME_ROW_KEY = "gautos-pajamos-darbo-santykiu"


class Finding(NamedTuple):
    rule: str
    election: str
    candidate: str
    path: str
    value: str
    facts: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.rule, self.election, self.candidate, self.path)

    def line(self) -> str:
        return f"{self.rule}\t{self.election}\t{self.candidate}\t{self.path}\t{self.value}\t{self.facts}"


def iso_dates(node: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Every ISO-shaped date string inside a record, with its dotted path."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from iso_dates(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for value in node:
            yield from iso_dates(value, f"{path}[]")
    elif isinstance(node, str) and ISO_DATE.match(node.strip()):
        yield path, node.strip()


def statutory_min_age(kind: str, election_date: str) -> int | None:
    """The age `kind` requires on a polling day of `election_date`."""
    for effective_from, floor in STATUTORY_MIN_AGE.get(kind, ()):
        if election_date >= effective_from:
            return floor
    return None


def age_on(birth: str, election_date: str) -> float | None:
    try:
        return (date.fromisoformat(election_date) - date.fromisoformat(birth)).days / 365.25
    except ValueError:
        return None


def birth_date(record: dict[str, Any]) -> str | None:
    for section in ("anketa", "biografija"):
        data = (record.get("normalized") or {}).get(section) or {}
        value = data.get("gimimo-data")
        if isinstance(value, str) and ISO_DATE.match(value.strip()):
            return value.strip()
    return None


def declaration(record: dict[str, Any]) -> dict[str, Any] | None:
    block = (record.get("normalized") or {}).get(DECLARATION_KEY)
    return block if isinstance(block, dict) else None


def check_record(
    record: dict[str, Any], election: dict[str, Any], candidate: str
) -> list[Finding]:
    findings: list[Finding] = []
    eid = election["id"]

    for path, value in iso_dates(record.get("normalized"), "normalized"):
        if not MIN_YEAR <= int(value[:4]) <= MAX_YEAR:
            findings.append(
                Finding(
                    "date-out-of-range", eid, candidate, path, value,
                    f"year {int(value[:4])} is outside {MIN_YEAR}-{MAX_YEAR}",
                )
            )

    born = birth_date(record)
    floor = statutory_min_age(election["kind"], election["date"])
    if born and floor is not None:
        age = age_on(born, election["date"])
        if age is not None and age < floor - AGE_TOLERANCE_YEARS:
            findings.append(
                Finding(
                    "age-below-statutory-minimum", eid, candidate,
                    "normalized.*.gimimo-data", born,
                    f"aged {age:.1f} on {election['date']}, and a {election['kind']}"
                    f" candidate must be {floor}",
                )
            )

    block = declaration(record)
    if block:
        total, row = block.get(INCOME_TOTAL_KEY), block.get(INCOME_ROW_KEY)
        if (
            isinstance(total, (int, float))
            and isinstance(row, (int, float))
            and row > 0
            and total > row * INCOME_RATIO_LIMIT
        ):
            findings.append(
                Finding(
                    "income-total-above-its-own-row", eid, candidate,
                    f"normalized.{DECLARATION_KEY}.{INCOME_TOTAL_KEY}", f"{total:.2f}",
                    f"{total / row:.0f}x its own {INCOME_ROW_KEY} of {row:.2f}",
                )
            )
    return findings


def scan(repo_root: Path, election_ids: list[str] | None = None) -> list[Finding]:
    registry = {
        entry["id"]: entry
        for entry in json.loads(
            (repo_root / "scraper" / "elections.json").read_text(encoding="utf-8")
        )["elections"]
    }
    findings: list[Finding] = []
    for eid in sorted(election_ids or registry):
        directory = repo_root / "data" / eid
        if not directory.is_dir() or eid not in registry:
            continue
        for path in sorted(directory.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            findings.extend(check_record(record, registry[eid], path.stem))
    return findings


def read_register(path: Path) -> dict[tuple[str, str, str, str], str]:
    if not path.exists():
        return {}
    register: dict[tuple[str, str, str, str], str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = (line.split("\t") + [""] * 6)[:6]
        if fields[0] == REGISTER_COLUMNS[0]:
            continue
        register[(fields[0], fields[1], fields[2], fields[3])] = fields[5]
    return register


def write_register(path: Path, findings: list[Finding]) -> None:
    lines = ["\t".join(REGISTER_COLUMNS)]
    lines += [finding.line() for finding in sorted(findings, key=lambda f: f.key)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("election_id", nargs="*", help="Subset to scan. Defaults to all.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rewrite the register from this run, keeping each finding's reason.",
    )
    args = parser.parse_args()

    findings = scan(args.repo_root, args.election_id or None)
    register_path = args.repo_root / REGISTER
    register = read_register(register_path)

    by_rule = Counter(finding.rule for finding in findings)
    keys = {finding.key for finding in findings}
    print(
        f"{len(findings)} implausible value(s) across {len(by_rule)} rule(s),"
        f" under {len(keys)} register key(s):"
    )
    for rule, count in sorted(by_rule.items()):
        print(f"    {rule}: {count}")
    if len(keys) < len(findings):
        # A key is (rule, election, candidate, path) and a list path
        # collapses its indices, so two identical values in one list share
        # a row -- reviewing it signs off both.
        print(f"    ({len(findings) - len(keys)} value(s) share a key with another)")

    if args.update:
        if args.election_id:
            parser.error("--update rewrites the whole register, so it cannot take election ids")
        kept = [
            finding._replace(facts=register.get(finding.key) or finding.facts)
            for finding in findings
        ]
        write_register(register_path, kept)
        gone = sorted(set(register) - {f.key for f in findings})
        print(f"wrote {REGISTER} — {len(kept)} row(s)" + (f", {len(gone)} dropped" if gone else ""))
        for key in gone[:20]:
            print(f"    dropped: {' '.join(key)}")
        unreviewed = [f for f in kept if not register.get(f.key)]
        if unreviewed:
            print(
                f"\n{len(unreviewed)} row(s) carry the measurement as their reason. Replace"
                " each with what you found — whose error it is, and what the page says:",
                file=sys.stderr,
            )
            for finding in unreviewed[:20]:
                print(f"    {finding.election}/{finding.candidate} {finding.path}", file=sys.stderr)
            return 1
        return 0

    new = [finding for finding in findings if finding.key not in register]
    if not new:
        print("Nothing new against the register.")
        return 0
    print(f"\n{len(new)} finding(s) not in {REGISTER}:", file=sys.stderr)
    for finding in new[:40]:
        print(f"    {finding.rule}\t{finding.election}/{finding.candidate}\t{finding.path}"
              f"\t{finding.value}\t{finding.facts}", file=sys.stderr)
    if len(new) > 40:
        print(f"    ... and {len(new) - 40} more", file=sys.stderr)
    print(
        f"\nEach is either a defect to fix or VRK's own typing to record."
        f" `--update` writes them into {REGISTER} for you to give a reason.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
