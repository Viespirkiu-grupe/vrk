"""Resolve every `docs/concept-map.json` path against every record, and gate the fill rates.

Issue #85: `2020-seimo` shipped with candidate income `null` on all 1,753
records, an empty `anomalies.jsonl` and a green test suite. Nothing in this
repository looked at how often a mapped field is actually filled, so the keys
were all present, the values were all `null`, every fixture still passed, and
nothing said a word. That is the shape of every silent regression this corpus
can have.

This is the detector. One pass over `data/` resolves each concept's path for
the elections that map it and reports three counts per cell -- records,
`keyPresent`, `nonNull` -- to `data/coverage.tsv`. The fill rates alone are
checked in, as `docs/coverage-baseline.tsv`, and the run is a gate against
them:

    python scripts/field_coverage.py                    # measure, check, exit non-zero on a finding
    python scripts/field_coverage.py 2020-seimo         # one election's cells
    python scripts/field_coverage.py --update-baseline  # after a deliberate change

Two rules fail the run, and a third is opt-in:

* **zero fill** -- a mapped cell no record fills. Every one of them has to be
  classified in the baseline (`upstream-absent`, `parser-gap`) with a note
  saying why; a new one, or one still marked `unexplained`, is an error. A
  zero whose concept is filled on more than 90 % of the elections that map it
  is called out separately: that is the `2020-seimo` shape exactly, and it is
  a regression until someone proves otherwise.
* **regression** -- a fill rate that fell more than `--max-drop` points below
  the baseline. Re-parsing an election is allowed to change what it recovers;
  losing five points of a field without saying so is not.
* **unmapped fill** (`--unmapped`) -- a concept's own path form that fills on
  at least one percent of an election the map does not give the concept for.
  The dashboard renders an unmapped cell as "this election never published
  this field", and issue #131 found 30 cells saying so over data the record
  on the same page carried (savivaldybe on 27,523 municipal and mayoral
  candidacies, the two declaration concepts on the 1996-1999 archive
  elections). Opt-in because it resolves every form of every concept against
  every election, several times the work of the mapped cells; the suite runs
  it on a sample of each election.

Two resolution rules, both of which a naive walker gets wrong:

* Concept paths are relative to the record's `normalized` section, *except*
  those naming a section of the record itself. `kandidatavimas` is the only
  one today, and it carries `savivaldybe` and two of `iskele`'s shapes -- a
  resolver that only walks `normalized` reports three false zeros
  (`savivaldybe` on `2007-vasario-25`, `savivaldybe` and `iskele` on
  `2000-kovo-19`, each in fact 100 % populated).
* A concept's path for an election can be a *list* of paths -- the municipal
  elections that ask the nominator once per seat. The cell resolves on the
  first alternative that is filled.

"Filled" is not truthiness: `0` is a real declared amount and `False` a real
answer, so only `None`, blank strings and empty containers count as unfilled.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Iterator, NamedTuple

CONCEPT_MAP = Path("docs/concept-map.json")
BASELINE = Path("docs/coverage-baseline.tsv")
REPORT = Path("data/coverage.tsv")

# Concept paths are relative to `normalized`, except the ones naming a section
# of the record itself. `kandidatavimas` is the only one, and it is in *both*
# places: the pre-2016 municipal and results-joined elections hoist the
# candidacy to the record root, and the two 1997 municipal archive elections
# leave it inside `normalized`. So the resolver tries `normalized` and falls
# back to the root rather than deciding from the path's first segment.
RECORD_ROOT_SECTIONS = {"kandidatavimas"}

# A zero-fill cell has to say which of these it is, and why.
EMPTY_IS_THE_ANSWER = "empty-is-the-answer"
ZERO_STATUSES = {
    "upstream-absent": "the source publishes no value here",
    "parser-gap": "the source publishes it and the parser does not recover it",
    EMPTY_IS_THE_ANSWER: "every record carries the key and the empty value is the answer",
}
UNEXPLAINED = "unexplained"
OK = "ok"

# Above this, a concept counts as "filled everywhere", and a zero against it is
# the 2020-seimo shape rather than an era that never asked the question.
FILLED_EVERYWHERE = 90.0

REPORT_COLUMNS = ("concept", "election", "records", "keyPresent", "nonNull", "pct", "status", "note")
BASELINE_COLUMNS = ("concept", "election", "pct", "status", "note")


class Cell(NamedTuple):
    """One concept measured against one election."""

    concept: str
    election: str
    records: int
    key_present: int
    non_null: int

    @property
    def pct(self) -> float:
        return round(100.0 * self.non_null / self.records, 1) if self.records else 0.0


class Baseline(NamedTuple):
    """One checked-in cell: the rate the gate compares against, and its classification."""

    pct: float
    status: str
    note: str


def is_filled(value: Any) -> bool:
    """Whether a resolved value counts as an answer.

    Deliberately not `bool(value)`: `privalomas-registruoti-turtas` is `0` for
    a candidate who registered no property, and that zero is the declaration,
    not its absence. Numbers and booleans always count; strings and containers
    have to hold something.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def _walk(root: Any, segments: list[str]) -> tuple[bool, bool]:
    if not segments:
        return True, is_filled(root)
    # A list met mid-path fans out over its entries: the 1996-1999 Seimas
    # archive family's `kandidatavimas` is a list of candidacies (a candidate
    # could stand in a constituency and on a party list at once), and `iskele`
    # resolves on the first entry that carries it. Same rule as
    # scraper/shared/nominator.py, which walks these paths for the value. A
    # list in leaf position is a value, handled by `is_filled` above.
    if isinstance(root, list):
        present = filled = False
        for entry in root:
            entry_present, entry_filled = _walk(entry, segments)
            present = present or entry_present
            filled = filled or entry_filled
            if filled:
                break
        return present, filled
    if not isinstance(root, dict) or segments[0] not in root:
        return False, False
    return _walk(root[segments[0]], segments[1:])


def resolve(record: dict[str, Any], path: str) -> tuple[bool, bool]:
    """Resolve one dotted path in one record. Returns (key present, filled)."""
    segments = path.split(".")
    present, filled = _walk(record.get("normalized"), segments)
    if not present and segments[0] in RECORD_ROOT_SECTIONS:
        return _walk(record, segments)
    return present, filled


def resolve_any(record: dict[str, Any], path: str | list[str]) -> tuple[bool, bool]:
    """Resolve a concept's mapping, which may be a list of alternative paths.

    The municipal elections that elect a council and a mayor on one card ask
    the nominator once per seat and fill whichever the candidate stood for, so
    the cell resolves on the first alternative that carries an answer.
    """
    if isinstance(path, str):
        return resolve(record, path)
    present = filled = False
    for alternative in path:
        alternative_present, alternative_filled = resolve(record, alternative)
        present = present or alternative_present
        filled = filled or alternative_filled
        if filled:
            break
    return present, filled


def _walk_value(root: Any, segments: list[str]) -> Any:
    if not segments:
        return root if is_filled(root) else None
    if isinstance(root, list):
        for entry in root:
            value = _walk_value(entry, segments)
            if value is not None:
                return value
        return None
    if not isinstance(root, dict) or segments[0] not in root:
        return None
    return _walk_value(root[segments[0]], segments[1:])


def concept_value(record: dict[str, Any], path: str | list[str]) -> Any:
    """The first filled value a concept path (or ordered path list) resolves
    to — the value twin of `resolve`/`resolve_any`, with their exact
    semantics: paths are relative to `normalized`, falling back to the record
    root for the sections hoisted there, and a list met mid-path fans out
    over its entries. The dashboard's `resolveConcept` mirrors this rule set
    in JS, and tests/test_dashboard_concept_rows.py holds the two together."""
    paths = [path] if isinstance(path, str) else path
    for alternative in paths:
        segments = alternative.split(".")
        value = _walk_value(record.get("normalized"), segments)
        if value is None and segments[0] in RECORD_ROOT_SECTIONS:
            value = _walk_value(record, segments)
        if value is not None:
            return value
    return None


def concept_paths(concept_map: dict[str, Any]) -> dict[str, dict[str, str | list[str]]]:
    return {name: concept["paths"] for name, concept in concept_map["concepts"].items()}


def election_records(data_root: Path, election_id: str) -> Iterator[dict[str, Any]]:
    for path in sorted((data_root / election_id).glob("*.json")):
        yield json.loads(path.read_text(encoding="utf-8"))


def measure(
    data_root: Path,
    paths_by_concept: dict[str, dict[str, str | list[str]]],
    election_ids: list[str],
) -> list[Cell]:
    """One pass per election, resolving every concept mapped to it.

    Per election rather than per concept: the records are the expensive part
    (113,073 files), and every concept mapped to an election is answered from
    the record already in hand.
    """
    cells: list[Cell] = []
    for election_id in election_ids:
        concepts = sorted(
            (name, paths[election_id])
            for name, paths in paths_by_concept.items()
            if election_id in paths
        )
        if not concepts:
            continue
        records = 0
        present = {name: 0 for name, _ in concepts}
        filled = {name: 0 for name, _ in concepts}
        for record in election_records(data_root, election_id):
            records += 1
            for name, path in concepts:
                key_present, value_filled = resolve_any(record, path)
                present[name] += key_present
                filled[name] += value_filled
        cells.extend(
            Cell(name, election_id, records, present[name], filled[name]) for name, _ in concepts
        )
    return sorted(cells, key=lambda cell: (cell.concept, cell.election))


def concept_fill_rate(cells: list[Cell], concept: str, exclude: str) -> float | None:
    """A concept's median fill rate across the other elections that map it.

    What the zero-fill rule's second sentence is measured against. Median
    rather than mean so that a concept with a handful of documented upstream
    absences -- most of them have some -- still reads as "filled everywhere",
    and a new zero still stands out against it.
    """
    others = [cell.pct for cell in cells if cell.concept == concept and cell.election != exclude]
    return statistics.median(others) if others else None


def classify(cell: Cell, prior: Baseline | None) -> tuple[str, str]:
    """The status word and reason a cell carries, given what was checked in.

    A filled cell needs no excuse and keeps none: a cell that stopped being a
    zero loses its classification, so a zero that comes back has to be
    explained again rather than inheriting an old one.
    """
    if cell.non_null:
        return OK, ""
    if prior is not None and prior.status in ZERO_STATUSES:
        return prior.status, prior.note
    return UNEXPLAINED, ""


def read_baseline(path: Path) -> dict[tuple[str, str], Baseline]:
    if not path.exists():
        return {}
    baseline: dict[tuple[str, str], Baseline] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = (line.split("\t") + ["", "", "", "", ""])[:5]
        if fields[0] == BASELINE_COLUMNS[0]:
            continue
        concept, election, pct, status, note = fields
        baseline[(concept, election)] = Baseline(float(pct or 0.0), status, note)
    return baseline


def write_baseline(
    path: Path, cells: list[Cell], previous: dict[tuple[str, str], Baseline]
) -> None:
    """Rewrite the checked-in baseline, carrying every classification forward.

    Only the fill rate and the classification are checked in. The counts move
    with every scrape and would make the file a diff generator; the rates are
    what the gate compares and what a reviewer can read.
    """
    lines = ["\t".join(BASELINE_COLUMNS)]
    for cell in cells:
        status, note = classify(cell, previous.get((cell.concept, cell.election)))
        lines.append("\t".join([cell.concept, cell.election, f"{cell.pct:.1f}", status, note]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(
    path: Path, cells: list[Cell], baseline: dict[tuple[str, str], Baseline]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(REPORT_COLUMNS)]
    for cell in cells:
        status, note = classify(cell, baseline.get((cell.concept, cell.election)))
        lines.append(
            "\t".join(
                [
                    cell.concept,
                    cell.election,
                    str(cell.records),
                    str(cell.key_present),
                    str(cell.non_null),
                    f"{cell.pct:.1f}",
                    status,
                    note,
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def check(
    cells: list[Cell],
    baseline: dict[tuple[str, str], Baseline],
    max_drop: float,
) -> list[str]:
    """The two rules. Returns one line per finding, empty when the corpus is clean."""
    findings: list[str] = []
    for cell in cells:
        if not cell.records:
            continue
        prior = baseline.get((cell.concept, cell.election))

        if cell.non_null == 0:
            status = prior.status if prior else UNEXPLAINED
            note = prior.note if prior else ""
            if status == EMPTY_IS_THE_ANSWER and cell.key_present < cell.records:
                # The claim is that the parser answered everywhere and the
                # answer was empty. A missing key is a different thing, and
                # the status would hide it.
                findings.append(
                    f"{cell.concept}\t{cell.election}\t"
                    f"classified empty-is-the-answer, but the key is absent on"
                    f" {cell.records - cell.key_present} of {cell.records} records"
                )
                continue
            if status in ZERO_STATUSES and note.strip():
                continue
            elsewhere = concept_fill_rate(cells, cell.concept, cell.election)
            shape = (
                f"; the concept is filled at a median {elsewhere:.1f}% across the other"
                " elections that map it, which is the 2020-seimo shape"
                if elsewhere is not None and elsewhere > FILLED_EVERYWHERE
                else ""
            )
            findings.append(
                f"{cell.concept}\t{cell.election}\t"
                f"0 of {cell.records} records fill a mapped path ({status}){shape}"
            )
            continue

        if prior is not None and cell.pct < prior.pct - max_drop:
            findings.append(
                f"{cell.concept}\t{cell.election}\t"
                f"{cell.pct:.1f}% filled, was {prior.pct:.1f}%"
                f" -- a drop of {prior.pct - cell.pct:.1f} points"
            )
    return findings


#: The unmapped-fill rule's floor: below this share of an election's records a
#: filled path form is a stray record on a form that does not ask the
#: question (anketa.pomegiai on 1 of 10,138 records of 2002-gruodzio-22,
#: anketa.kita-apie-save on 3 of 9,879 of 2000-kovo-19), not a missing mapping.
UNMAPPED_FLOOR_PCT = 1.0


def path_forms(paths_by_concept: dict[str, dict[str, str | list[str]]]) -> dict[str, list[str]]:
    """Every distinct path a concept is mapped through, per concept."""
    return {
        concept: sorted({path for mapping in paths.values() for path in ([mapping] if isinstance(mapping, str) else mapping)})
        for concept, paths in paths_by_concept.items()
    }


def unmapped_fills(
    data_root: Path,
    paths_by_concept: dict[str, dict[str, str | list[str]]],
    election_ids: list[str],
    *,
    sample: int | None = None,
    floor_pct: float = UNMAPPED_FLOOR_PCT,
) -> list[str]:
    """The third rule: a concept's own path form filling an election the map
    does not give the concept for. One line per finding.

    `sample` caps the records read per election (the suite's use); None reads
    them all. A form that fills below `floor_pct` of the records read is a
    stray, not a mapping gap.
    """
    forms = path_forms(paths_by_concept)
    findings: list[str] = []
    for election_id in election_ids:
        candidates = [
            (concept, form)
            for concept, concept_forms in forms.items()
            if election_id not in paths_by_concept[concept]
            for form in concept_forms
        ]
        if not candidates:
            continue
        records = 0
        filled = {key: 0 for key in candidates}
        for record in election_records(data_root, election_id):
            records += 1
            for key in candidates:
                if resolve(record, key[1])[1]:
                    filled[key] += 1
            if sample is not None and records >= sample:
                break
        for (concept, form), count in filled.items():
            if records and count and 100.0 * count / records >= floor_pct:
                findings.append(
                    f"{concept}\t{election_id}\t{form} fills {count} of {records} records"
                    f" ({100.0 * count / records:.1f}%), and the map does not give this"
                    " election the concept"
                )
    return findings


def unmapped_elections(data_root: Path, paths_by_concept: dict[str, dict[str, Any]]) -> list[str]:
    """Elections whose records no concept resolves against.

    Not a rule -- an election can legitimately publish nothing the map covers
    -- but the coverage table cannot see these at all, so the run says so
    rather than reporting on a corpus it silently only half read.
    """
    mapped = {election for paths in paths_by_concept.values() for election in paths}
    present = {child.name for child in data_root.iterdir() if child.is_dir()}
    return sorted(present - mapped)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "election_id",
        nargs="*",
        help="Elections to measure. Defaults to every election the concept map covers.",
    )
    parser.add_argument(
        "--max-drop",
        type=float,
        default=5.0,
        help="Points a fill rate may fall below the baseline before it is an error (default 5).",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Rewrite docs/coverage-baseline.tsv from this run, keeping every classification.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Checkout holding data/ and docs/. Defaults to the cwd.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Where the full table is written. Defaults to <repo-root>/data/coverage.tsv.",
    )
    parser.add_argument("--top", type=int, default=40, help="Findings to list (default 40).")
    parser.add_argument(
        "--unmapped",
        action="store_true",
        help="Also apply the unmapped-fill rule: a concept's path form filling an election the map does not give it.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root
    concept_map = json.loads((repo_root / CONCEPT_MAP).read_text(encoding="utf-8"))
    paths_by_concept = concept_paths(concept_map)
    data_root = repo_root / "data"

    all_ids = sorted({election for paths in paths_by_concept.values() for election in paths})
    unknown = [eid for eid in args.election_id if eid not in all_ids]
    if unknown:
        parser.error("no concept maps this election: " + ", ".join(unknown))
    election_ids = [eid for eid in (args.election_id or all_ids) if (data_root / eid).is_dir()]

    baseline_path = repo_root / BASELINE
    baseline = read_baseline(baseline_path)

    cells = measure(data_root, paths_by_concept, election_ids)
    report_path = args.report_path or (repo_root / REPORT)
    write_report(report_path, cells, baseline)

    zero = [cell for cell in cells if cell.records and cell.non_null == 0]
    print(f"{len(cells)} mapped cell(s) across {len(election_ids)} election(s) -> {report_path}")
    print(f"{len(zero)} cell(s) no record fills")

    for election_id in unmapped_elections(data_root, paths_by_concept):
        count = sum(1 for _ in (data_root / election_id).glob("*.json"))
        print(
            f"note: {election_id} is in data/ ({count} records) and no concept maps it,"
            " so this run cannot see it",
            file=sys.stderr,
        )

    if args.update_baseline:
        if args.election_id:
            parser.error("--update-baseline rewrites the whole file, so it cannot take election ids")
        write_baseline(baseline_path, cells, baseline)
        print(f"Baseline rewritten: {baseline_path}")
        unexplained = [
            cell
            for cell in zero
            if (baseline.get((cell.concept, cell.election)) or Baseline(0.0, UNEXPLAINED, "")).status
            not in ZERO_STATUSES
        ]
        if unexplained:
            print(
                f"{len(unexplained)} zero-fill cell(s) still {UNEXPLAINED}."
                f" Classify each as one of: {', '.join(sorted(ZERO_STATUSES))}, with a note.",
                file=sys.stderr,
            )
        return 0

    findings = check(cells, baseline, args.max_drop)
    if args.unmapped:
        findings.extend(unmapped_fills(data_root, paths_by_concept, election_ids))
    if not findings:
        print("No findings.")
        return 0

    print(f"\n{len(findings)} finding(s):", file=sys.stderr)
    for finding in findings[: args.top]:
        print(f"    {finding}", file=sys.stderr)
    if len(findings) > args.top:
        print(f"    ... and {len(findings) - args.top} more, in {report_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
