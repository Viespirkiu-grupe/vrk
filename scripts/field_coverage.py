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

Five rules fail the run, and a sixth is opt-in:

* **zero fill** -- a mapped cell no record fills. Every one of them has to be
  classified in the baseline (`upstream-absent`, `parser-gap`) with a note
  saying why; a new one, or one still marked `unexplained`, is an error. A
  zero whose concept is filled on more than 90 % of the elections that map it
  is called out separately: that is the `2020-seimo` shape exactly, and it is
  a regression until someone proves otherwise.
* **regression** -- a fill rate that fell more than `--max-drop` points below
  the baseline. Re-parsing an election is allowed to change what it recovers;
  losing five points of a field without saying so is not.
* **below its peers** (issue #135) -- a filled cell more than
  `--max-below-peers` points (default 25) under the concept's median across
  the other elections that map it, where that median is above 90 %. The two
  rules above cannot see a *new* election's regression: it has no baseline
  row to fall from, and 8 % is not zero. Measured on a mirror with a
  synthetic 1,740-record 2027-seimo whose birth dates were nulled on 1,600
  records, the gate wrote `ok` at 8.0 %. The median of the concept's other
  elections is the yardstick a reviewer would reach for, so it is the rule:
  such a cell has to carry `partly-published` (the source prints the field on
  only some records) or `partly-answered` (asked everywhere, left blank by
  many) with a note, or it is a finding. The 46 cells the rule flags on the
  2026-09-08 corpus are classified in the baseline, each against the retained
  pages.
* **unmapped election** (issue #135) -- an election with records under
  `data/` that no concept maps. The coverage table cannot see it at all, and
  five of the candidacy table's columns come out empty for it; until this
  rule the run mentioned it on stderr and exited 0. An election legitimately
  left out carries a `*` row in the baseline with the status `not-mapped` and
  a note.
* **peer gap** (issue #135) -- a *new* election (one with no baseline row
  yet) that maps fewer concepts than the closest already-mapped election of
  the same kind. A concept the peer maps and the new election does not is a
  finding until it is mapped or recorded as a `not-mapped` row with a note.
* **unmapped fill** (`--unmapped`) -- a concept's own path form that fills on
  at least one percent of an election the map does not give the concept for.
  The dashboard renders an unmapped cell as "this election never published
  this field", and issue #131 found 30 cells saying so over data the record
  on the same page carried (savivaldybe on 27,523 municipal and mayoral
  candidacies, the two declaration concepts on the 1996-1999 archive
  elections). Opt-in because it resolves every form of every concept against
  every election, several times the work of the mapped cells; the suite runs
  it on a sample of each election.

`--update-baseline` is additive and loud (issue #135): it refuses to write
while any finding stands on a row the baseline already has -- a real 74-point
drop on one election used to be signed off by the same command that added a
new election's rows -- unless `--force` says so; it reports what it did
(`N rows added, M changed, K down more than --max-drop`); and it exits 1 when
a zero or below-peers cell it wrote is still `unexplained`, like the
candidacy table's gate always has.

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
from collections import defaultdict
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

# A filled cell far below the concept's other elections has to say which of
# these it is, and why (issue #135). The `keyPresent` count decides between
# them: a key absent on the unfilled records means the source did not print
# the field there; a key present with a null value means it was asked and
# left blank.
LOW_STATUSES = {
    "partly-published": "the source prints the field on only some of the election's records",
    "partly-answered": "the field is on every record; the candidates who left it blank are the gap",
}

# A baseline row for something the concept map deliberately leaves out: a
# (concept, election) cell the closest peer election maps and this one does
# not, or -- with `*` for the concept -- a whole election under data/ that no
# concept maps. Both need a note; both are what the peer-gap and unmapped-
# election rules accept as an answer.
NOT_MAPPED = "not-mapped"
EVERY_CONCEPT = "*"

# Above this, a concept counts as "filled everywhere", and a zero against it is
# the 2020-seimo shape rather than an era that never asked the question.
FILLED_EVERYWHERE = 90.0

#: Points below the concept's median (across the other elections that map it)
#: at which a filled cell becomes a finding. 25 flags 46 of the 1,394 cells on
#: the 2026-09-08 corpus -- every one an era that prints the field for a
#: minority, or a small election whose candidates skipped it -- and both
#: regressions issue #135 injected (8.0 % and 2.3 %) by a wide margin.
DEFAULT_MAX_BELOW_PEERS = 25.0

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

    What the zero-fill rule's second sentence and the below-peers rule are
    measured against. Median rather than mean so that a concept with a
    handful of documented upstream absences -- most of them have some --
    still reads as "filled everywhere", and a new zero still stands out
    against it.
    """
    others = [cell.pct for cell in cells if cell.concept == concept and cell.election != exclude]
    return statistics.median(others) if others else None


def peer_medians(cells: list[Cell]) -> dict[tuple[str, str], float | None]:
    """`concept_fill_rate` for every cell at once: (concept, election) -> the
    median fill rate of the concept's *other* elections, None for a concept
    mapped to one election only."""
    by_concept: dict[str, list[Cell]] = defaultdict(list)
    for cell in cells:
        by_concept[cell.concept].append(cell)
    medians: dict[tuple[str, str], float | None] = {}
    for concept, group in by_concept.items():
        for cell in group:
            others = [other.pct for other in group if other.election != cell.election]
            medians[(cell.concept, cell.election)] = statistics.median(others) if others else None
    return medians


def below_peers(cell: Cell, elsewhere: float | None, max_below: float = DEFAULT_MAX_BELOW_PEERS) -> bool:
    """The below-peers rule's test: filled, but more than `max_below` points
    under a concept that is filled everywhere else."""
    return (
        bool(cell.records)
        and cell.non_null > 0
        and elsewhere is not None
        and elsewhere > FILLED_EVERYWHERE
        and cell.pct < elsewhere - max_below
    )


def low_fill_facts(cell: Cell, elsewhere: float) -> str:
    """What a reviewer needs to classify a below-peers cell: the fill, the
    yardstick, and whether the unfilled records carry the key at all."""
    absent = cell.records - cell.key_present
    presence = (
        f"the key is present on every record; {cell.records - cell.non_null} carry no value"
        if absent == 0
        else f"the key is absent on {absent} of {cell.records} records"
    )
    return (
        f"{cell.pct:.1f}% filled ({cell.non_null} of {cell.records}) against a median"
        f" {elsewhere:.1f}% across the other elections that map the concept;"
        f" {presence}"
    )


def classify(
    cell: Cell,
    prior: Baseline | None,
    elsewhere: float | None = None,
    max_below: float = DEFAULT_MAX_BELOW_PEERS,
) -> tuple[str, str]:
    """The status word and reason a cell carries, given what was checked in.

    A filled cell keeps no excuse it no longer needs: a cell that stopped
    being a zero loses its classification, so a zero that comes back has to
    be explained again rather than inheriting an old one; a cell that climbed
    back to its peers loses its `partly-*` word the same way. `elsewhere` is
    the concept's median across the other elections (peer_medians); without
    it the below-peers half of the rule is not applied.
    """
    if not cell.non_null:
        if prior is not None and prior.status in ZERO_STATUSES:
            return prior.status, prior.note
        return UNEXPLAINED, ""
    if below_peers(cell, elsewhere, max_below):
        if prior is not None and prior.status in LOW_STATUSES:
            return prior.status, prior.note
        return UNEXPLAINED, ""
    return OK, ""


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


def baseline_rows(
    cells: list[Cell],
    previous: dict[tuple[str, str], Baseline],
    max_below: float = DEFAULT_MAX_BELOW_PEERS,
) -> dict[tuple[str, str], Baseline]:
    """What the baseline holds after this run: one row per measured cell,
    classified against what was checked in, plus the `not-mapped` rows that
    still describe something the map leaves out -- a `*` row for an election
    none of these cells belongs to, a concept row for a cell that was not
    measured. A `not-mapped` row whose cell has since been mapped is dropped:
    the measured cell replaces it."""
    medians = peer_medians(cells)
    measured = {(cell.concept, cell.election) for cell in cells}
    elections = {cell.election for cell in cells}
    rows: dict[tuple[str, str], Baseline] = {}
    for key, row in previous.items():
        if row.status != NOT_MAPPED:
            continue
        concept, election = key
        if concept == EVERY_CONCEPT and election not in elections:
            rows[key] = row
        elif concept != EVERY_CONCEPT and key not in measured:
            rows[key] = row
    for cell in cells:
        key = (cell.concept, cell.election)
        status, note = classify(cell, previous.get(key), medians[key], max_below)
        rows[key] = Baseline(cell.pct, status, note)
    return rows


def write_baseline(
    path: Path,
    cells: list[Cell],
    previous: dict[tuple[str, str], Baseline],
    max_below: float = DEFAULT_MAX_BELOW_PEERS,
) -> dict[tuple[str, str], Baseline]:
    """Rewrite the checked-in baseline, carrying every classification forward.

    Only the fill rate and the classification are checked in. The counts move
    with every scrape and would make the file a diff generator; the rates are
    what the gate compares and what a reviewer can read. Returns the rows
    written, keyed like `read_baseline` reads them.
    """
    rows = baseline_rows(cells, previous, max_below)
    lines = ["\t".join(BASELINE_COLUMNS)]
    for (concept, election), row in sorted(rows.items()):
        lines.append("\t".join([concept, election, f"{row.pct:.1f}", row.status, row.note]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def write_report(
    path: Path,
    cells: list[Cell],
    baseline: dict[tuple[str, str], Baseline],
    max_below: float = DEFAULT_MAX_BELOW_PEERS,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    medians = peer_medians(cells)
    lines = ["\t".join(REPORT_COLUMNS)]
    for cell in cells:
        key = (cell.concept, cell.election)
        status, note = classify(cell, baseline.get(key), medians[key], max_below)
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
    max_below: float = DEFAULT_MAX_BELOW_PEERS,
) -> list[str]:
    """The three per-cell rules -- zero fill, regression, below its peers.
    Returns one tab-separated line per finding (concept, election, what),
    empty when the corpus is clean."""
    findings: list[str] = []
    medians = peer_medians(cells)
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

        if prior is not None and prior.status != NOT_MAPPED and cell.pct < prior.pct - max_drop:
            findings.append(
                f"{cell.concept}\t{cell.election}\t"
                f"{cell.pct:.1f}% filled, was {prior.pct:.1f}%"
                f" -- a drop of {prior.pct - cell.pct:.1f} points"
            )
            continue

        elsewhere = medians[(cell.concept, cell.election)]
        if below_peers(cell, elsewhere, max_below):
            if prior is not None and prior.status in LOW_STATUSES and prior.note.strip():
                continue
            status = prior.status if prior is not None and prior.status in LOW_STATUSES else UNEXPLAINED
            findings.append(
                f"{cell.concept}\t{cell.election}\t"
                f"{low_fill_facts(cell, elsewhere)} ({status}; classify it as one of"
                f" {', '.join(sorted(LOW_STATUSES))} with a note, or fix the parser)"
            )
    return findings


def finding_key(finding: str) -> tuple[str, str]:
    """The (concept, election) a finding line is about."""
    concept, election, _ = finding.split("\t", 2)
    return concept, election


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


def _record_count(data_root: Path, election_id: str) -> int:
    return sum(1 for path in (data_root / election_id).glob("*.json") if path.name != "anomalies.jsonl")


def unmapped_elections(data_root: Path, paths_by_concept: dict[str, dict[str, Any]]) -> list[str]:
    """Elections with records under data/ that no concept resolves against.

    A directory holding only an anomaly log is not an election here: the
    records are what the coverage table reads, and there are none to miss.
    """
    mapped = {election for paths in paths_by_concept.values() for election in paths}
    present = {
        child.name
        for child in data_root.iterdir()
        if child.is_dir() and child.name not in mapped and _record_count(data_root, child.name)
    }
    return sorted(present)


def unmapped_election_findings(
    data_root: Path,
    paths_by_concept: dict[str, dict[str, Any]],
    baseline: dict[tuple[str, str], Baseline],
) -> list[str]:
    """The unmapped-election rule (issue #135): an election in data/ the map
    does not cover is a finding unless the baseline carries its opt-out --
    a `*` row with the status `not-mapped` and a note. Until this rule the
    run said so on stderr and exited 0, and a mirror with a synthetic
    2027-seimo shipped five empty candidacy-table columns past it."""
    findings = []
    for election_id in unmapped_elections(data_root, paths_by_concept):
        prior = baseline.get((EVERY_CONCEPT, election_id))
        if prior is not None and prior.status == NOT_MAPPED and prior.note.strip():
            continue
        findings.append(
            f"{EVERY_CONCEPT}\t{election_id}\t{_record_count(data_root, election_id)} records"
            " under data/ and no concept maps this election, so this run cannot see"
            " it; map it in docs/concept-map.json, or record the opt-out as a"
            f" `{EVERY_CONCEPT}` row with the status {NOT_MAPPED} and a note"
        )
    return findings


def new_elections(
    election_ids: list[str], baseline: dict[tuple[str, str], Baseline]
) -> list[str]:
    """The elections with no measured baseline row yet -- what `--update-baseline`
    is about to add, and what the peer-gap rule checks."""
    baselined = {election for (_, election), row in baseline.items() if row.status != NOT_MAPPED}
    return [eid for eid in election_ids if eid not in baselined]


def closest_peer(
    election_id: str, registry_by_id: dict[str, dict[str, Any]], candidates: list[str]
) -> str | None:
    """The already-mapped election of the same `kind` nearest in date --
    the one whose concept set a new election is measured against. Ties go
    to the earlier election, which is the one the new module was most
    likely built from."""
    entry = registry_by_id.get(election_id)
    if entry is None:
        return None
    peers = [
        other
        for other in candidates
        if other != election_id
        and other in registry_by_id
        and registry_by_id[other].get("kind") == entry.get("kind")
    ]
    if not peers:
        return None

    def distance(other: str) -> tuple[int, str]:
        gap = abs(_days(registry_by_id[other]["date"]) - _days(entry["date"]))
        return gap, registry_by_id[other]["date"]

    return min(peers, key=distance)


def _days(iso_date: str) -> int:
    year, month, day = (int(part) for part in iso_date.split("-"))
    return year * 372 + month * 31 + day


def peer_gap_findings(
    paths_by_concept: dict[str, dict[str, Any]],
    registry: list[dict[str, Any]] | None,
    election_ids: list[str],
    baseline: dict[tuple[str, str], Baseline],
) -> list[str]:
    """The peer-gap rule (issue #135): a new election maps every concept the
    closest already-mapped election of its kind maps, or says why not with
    a `not-mapped` row. On the mirror that motivated it, an unmapped copy of
    2024-seimo lost five candidacy-table columns (birth_date, birth_place,
    party_id, party_name_raw, nomination_kind) and nothing said so."""
    fresh = new_elections(election_ids, baseline)
    if not fresh:
        return []
    if registry is None:
        return [
            f"{EVERY_CONCEPT}\t{eid}\tnew election, and scraper/elections.json is not at hand"
            " to choose a peer for the concept-set check"
            for eid in fresh
        ]
    registry_by_id = {entry["id"]: entry for entry in registry}
    mapped = {election for paths in paths_by_concept.values() for election in paths}
    baselined = sorted(
        {election for (_, election), row in baseline.items() if row.status != NOT_MAPPED} & mapped
    )
    findings: list[str] = []
    for eid in fresh:
        if eid not in registry_by_id:
            findings.append(
                f"{EVERY_CONCEPT}\t{eid}\tnew election with no scraper/elections.json entry,"
                " so no peer of its kind can be chosen for the concept-set check"
            )
            continue
        peer = closest_peer(eid, registry_by_id, baselined)
        if peer is None:
            continue
        for concept, paths in sorted(paths_by_concept.items()):
            if peer not in paths or eid in paths:
                continue
            prior = baseline.get((concept, eid))
            if prior is not None and prior.status == NOT_MAPPED and prior.note.strip():
                continue
            findings.append(
                f"{concept}\t{eid}\tthe closest mapped {registry_by_id[eid].get('kind')}"
                f" election, {peer}, maps this concept and {eid} does not; map it, or"
                f" record why not as a {NOT_MAPPED} row with a note"
            )
    return findings


def load_registry(repo_root: Path) -> list[dict[str, Any]] | None:
    path = repo_root / "scraper" / "elections.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))["elections"]


def update_baseline(
    path: Path,
    cells: list[Cell],
    previous: dict[tuple[str, str], Baseline],
    cell_findings: list[str],
    election_findings: list[str] = (),
    *,
    force: bool = False,
    max_drop: float = 5.0,
    max_below: float = DEFAULT_MAX_BELOW_PEERS,
    out: Any = None,
) -> int:
    """Rewrite the baseline additively and loudly (issue #135).

    Refuses -- writes nothing, exits 1 -- while a finding stands on a row
    the baseline already has (a regression, a zero that used to be filled)
    or on the concept set of a new election (a peer gap, an unmapped
    election): those are things to fix or to classify, not to sign off by
    re-measuring. `force` writes anyway. Then it reports the rows added and
    changed and how many fell more than `max_drop`, and exits 1 while any
    zero or below-peers cell it wrote is `unexplained`, so the first run over
    a new election ends with the list of cells a human has to classify.
    """
    out = out or sys.stderr
    # `cell_findings` are check()'s: blocking where the row already exists (a
    # new election's zeros and low cells are written unexplained instead,
    # below). `election_findings` -- an unmapped election, a peer gap -- are
    # about what is *not* measured, so writing rows cannot answer them and
    # they always block.
    blocking = [f for f in cell_findings if finding_key(f) in previous] + list(election_findings)
    if blocking and not force:
        print(f"--update-baseline refused: {len(blocking)} finding(s) stand on what is already", file=out)
        print("checked in, or on a new election's concept set. Fix or classify them first;", file=out)
        print("--force rewrites the baseline regardless.", file=out)
        for finding in blocking[:40]:
            print(f"    {finding}", file=out)
        return 1

    rows = write_baseline(path, cells, previous, max_below)
    added = [key for key in rows if key not in previous]
    changed = [
        key
        for key, row in rows.items()
        if key in previous
        and (abs(row.pct - previous[key].pct) >= 0.05 or row.status != previous[key].status)
    ]
    down = [key for key in rows if key in previous and rows[key].pct < previous[key].pct - max_drop]
    print(
        f"Baseline rewritten: {path} -- {len(added)} row(s) added, {len(changed)} changed,"
        f" {len(down)} down more than {max_drop:g} points"
        + (" (forced)" if blocking else "")
    )
    unexplained = sorted(key for key, row in rows.items() if row.status == UNEXPLAINED)
    if unexplained:
        medians = peer_medians(cells)
        by_key = {(cell.concept, cell.election): cell for cell in cells}
        print(
            f"{len(unexplained)} cell(s) written {UNEXPLAINED}. A zero takes one of"
            f" {', '.join(sorted(ZERO_STATUSES))}, a below-peers cell one of"
            f" {', '.join(sorted(LOW_STATUSES))}, each with a note:",
            file=out,
        )
        for key in unexplained[:40]:
            cell = by_key[key]
            facts = (
                f"0 of {cell.records} records fill it"
                if not cell.non_null
                else low_fill_facts(cell, medians[key] or 0.0)
            )
            print(f"    {key[0]}\t{key[1]}\t{facts}", file=out)
        return 1
    return 0


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
        "--max-below-peers",
        type=float,
        default=DEFAULT_MAX_BELOW_PEERS,
        help=(
            "Points a filled cell may sit under its concept's median across the other"
            f" elections before it needs a classification (default {DEFAULT_MAX_BELOW_PEERS:g})."
        ),
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help=(
            "Rewrite docs/coverage-baseline.tsv from this run, keeping every classification."
            " Refuses while a finding stands on a row already checked in (see --force)."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --update-baseline: rewrite even over standing findings.",
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
    if not election_ids:
        # Nothing to measure. Writing the (empty) report would create data/
        # on a clone, after which every whole-corpus test read an existing
        # data/ as a corpus and failed against nothing (issue #145).
        print(
            f"No election under {data_root}: the corpus is scraped, not cloned"
            " (docs/CLI_REFERENCE.md). Nothing measured, nothing written.",
            file=sys.stderr,
        )
        return 2

    baseline_path = repo_root / BASELINE
    baseline = read_baseline(baseline_path)

    if args.update_baseline and args.election_id:
        parser.error("--update-baseline rewrites the whole file, so it cannot take election ids")

    cells = measure(data_root, paths_by_concept, election_ids)
    report_path = args.report_path or (repo_root / REPORT)
    write_report(report_path, cells, baseline, args.max_below_peers)

    zero = [cell for cell in cells if cell.records and cell.non_null == 0]
    print(f"{len(cells)} mapped cell(s) across {len(election_ids)} election(s) -> {report_path}")
    print(f"{len(zero)} cell(s) no record fills")

    findings = check(cells, baseline, args.max_drop, args.max_below_peers)
    # The two election-level rules (issue #135) run on the whole data/ tree
    # and against the whole registry: an election the map does not cover,
    # and a new election mapping less than its closest peer.
    election_findings = unmapped_election_findings(data_root, paths_by_concept, baseline)
    election_findings.extend(
        peer_gap_findings(paths_by_concept, load_registry(repo_root), election_ids, baseline)
    )

    if args.update_baseline:
        return update_baseline(
            baseline_path,
            cells,
            baseline,
            findings,
            election_findings,
            force=args.force,
            max_drop=args.max_drop,
            max_below=args.max_below_peers,
        )

    findings.extend(election_findings)
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
