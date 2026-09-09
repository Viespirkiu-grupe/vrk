# Field coverage

An anomaly says a page went wrong. This says a *field stopped arriving* — the
failure that leaves no trace at all.

`2020-seimo` shipped with candidate income `null` on all 1,753 records, an empty
`anomalies.jsonl` and a green test suite. Every key was present, every value was
`null`, every fixture passed, and nothing said a word. Nothing in this
repository looked at how often a mapped field is filled, so nothing could.

```bash
python scripts/field_coverage.py                    # measure, check, exit 1 on a finding
python scripts/field_coverage.py 2020-seimo         # one election's cells
python scripts/field_coverage.py --update-baseline  # after a deliberate change; refuses over a standing finding
python scripts/field_coverage.py --unmapped         # also: a field the map denies an election that has it
```

One pass over `data/` — about 30 seconds for 113,073 records — resolves every
`docs/concept-map.json` path against every record of the elections that map it.
That is 1,394 cells across 55 elections.

## What it produces

`data/coverage.tsv` (gitignored, like everything under `data/`) holds the full
table:

```
concept          election                   records  keyPresent  nonNull  pct   status  note
gautos-pajamos   2020-seimo                    1754        1753     1719  98.0  ok
gimimo-vieta     2000-kovo-19-savivaldybiu…    9879        9879        0   0.0  upstream-absent  The 2000 municipal card…
```

The `keyPresent` / `nonNull` split is the point. A key the parser never wrote
and a key it wrote as `null` are different failures, and the 2020-seimo defect
was the second kind.

`docs/coverage-baseline.tsv` is the checked-in half: one line per cell with the
fill rate, a status word and a note. Only the rate is committed — the counts
move with every scrape and would make the file a diff generator.

## The six rules

**Zero fill.** A mapped cell no record fills. Every one has to be classified in
the baseline, with a note saying why; a new one, or one still marked
`unexplained`, fails the run. When the concept is filled on a median of more
than 90 % of the elections that map it, the message says so — that is the
2020-seimo shape exactly, and it is a regression until someone proves otherwise.

**Stale excuse** (issue #165). The zero-fill rule read backwards: a cell the
baseline classifies as legitimately empty that now *fills*. A classified zero
used to be skipped before any other rule saw it, in both directions, so a note
saying VRK publishes nothing here could go on saying it over values that had
since arrived — and six lines of `docs/candidacy-baseline.tsv` did, over the
35,507 post-election rankings issue #99's results join recovered. That is not
merely an untrue file: it is the excuse that would have covered the values'
*loss*, because `--update-baseline` re-files a zero under the classification
already there. The rule closes the window in which the two can drift apart:
the note is reported false the first time the gate runs after the values
arrive.

This is the one finding that does not block `--update-baseline`. Re-measuring
is the fix — `classify` drops an excuse a filled cell no longer needs, so the
row rewrites itself as `ok` and a zero that comes back has to be explained
afresh. Blocking would leave `--force` as the only way through, and `--force`
signs off every *other* finding in the same run.

**Regression.** A fill rate more than `--max-drop` points (default 5) below the
baseline. Re-parsing an election is allowed to change what it recovers; losing
five points of a field without saying so is not.

**Below its peers** (issue #135). A filled cell more than `--max-below-peers`
points (default 25) under the concept's median across the *other* elections
that map it, where that median is above 90 %. The zero-fill and regression
rules cannot see a new election's regression: it has no baseline row to fall
from, and 8 % is not
zero — on a mirror with a synthetic 1,740-record `2027-seimo` whose birth
dates were nulled on 1,600 records, the gate wrote `ok` at 8.0 % and exited 0.
The concept's median elsewhere was already computed inside the gate to
decorate the zero-fill message; now it is a rule. Such a cell carries
`partly-published` or `partly-answered` with a note (below), or it is a
finding. The 46 cells the rule flags on the
2026-09-08 corpus are all
classified, each checked against the retained pages: the archive by-elections
whose declaration extracts VRK holds for one candidate in twenty, the 2004
static site printing „-“ in a loan row nobody filled, the archive cards that
recover a birth date from the biography's first sentence, the 2019 municipal
questionnaire whose optional questions a third of candidates skipped.

**Unmapped election** (issue #135). An election with records under `data/`
that no concept maps. The coverage table cannot see it at all, and five of the
candidacy table's 52 columns come out empty for it; until this rule the run
mentioned it on stderr — under a docstring that said "not a rule" — and exited
0. An election legitimately left out carries a `*` row in the baseline
(`*<TAB><election-id><TAB>0.0<TAB>not-mapped<TAB>why`).

**Peer gap** (issue #135). A *new* election — one with no baseline row yet —
that maps fewer concepts than the closest already-mapped election of the same
`kind` (nearest by date, from `scraper/elections.json`). Each concept the peer
maps and the new election does not is a finding until it is mapped or recorded
as a `not-mapped` row with a note. This is the rule that catches a new module
whose author forgot half the concept map: the fixture tests pass, the cells
that exist all read 100 %, and the missing ones are simply not there to fail.

**Unmapped fill** (`--unmapped`, the opt-in seventh). A concept's own path
form that fills on at least one percent of the records of an election the map
does *not* give the concept for. The dashboard renders an unmapped cell as
"Šių rinkimų anketa šio lauko neskelbė" — this election never published this
field — and issue #131 found 30 cells saying so over data the record on the
same page carried: `savivaldybe` on 27,523 candidacies of the 2019/2023
municipal generals and seven mayoral elections, `gautos-pajamos` and
`sumoketas-pajamu-mokestis` on the eight 1996–1999 archive elections,
`turtas-ir-vertybiniai-popieriai` on 2003. Opt-in because it resolves every
form of every concept against every election, several times the work of the
mapped cells; `tests/test_field_coverage.py` runs it on a 300-record sample of
each election, which catches every systematic omission at a fraction of the
cost. The one-percent floor is what keeps two deliberate exclusions out:
`anketa.pomegiai` holds a value on 1 of 10,138 records of 2002-gruodzio-22 and
`anketa.kita-apie-save` on 3 of 9,879 of 2000-kovo-19 — stray records on forms
that do not ask the question, recorded as such in the map's `verified` note.

## Status words

Twenty-four of the 1,394 cells are filled by no record, and 46 more are filled
far below the concept's other elections. Each carries one of:

| status | count | meaning |
| --- | --- | --- |
| `ok` | 1,324 | filled at some rate, in line with the concept's other elections |
| `upstream-absent` | 18 | the source publishes no value here — the label is missing, or printed and left blank |
| `empty-is-the-answer` | 6 | every record carries the key and the empty value is the answer: nobody declared a conviction, nobody had an outstanding loan |
| `parser-gap` | 0 | the source publishes it and the parser does not recover it |
| `partly-published` | 29 | filled, but the source prints the field on only some of the election's records: the key is absent on the rest (a birth date recovered from prose where the card has none, a declaration extract VRK's archive holds for one candidate in twenty) |
| `partly-answered` | 17 | filled, but far below the peers with the key on every record: the question was asked and left blank, or answered with the „-“ the 2004 forms print for "none" |
| `not-mapped` | 0 | a `*` row for an election under `data/` that no concept maps, or a concept row for one the closest peer election maps and this one does not, each with a note saying why |
| `unexplained` | 0 | nobody has looked. Fails the run. |

`empty-is-the-answer` is checked, not taken on trust: a cell claiming it whose
key is absent on some records is a finding, because that is a different thing
from an empty answer. The `partly-*` pair is checked the same way: the
checked-in file's own rates say which cells are below their peers, and
`tests/test_field_coverage.py` fails if one of them reads `ok`, or if a cell
carries a `partly-*` word it no longer needs.

`parser-gap` is the word the `2020-seimo` cell would have needed. That it is
unused today is a claim this file makes and the run checks.

## `--update-baseline` is additive and loud

It used to rewrite all 1,336 rows and exit 0 whatever it found: on a mirror
where a real 74-point drop on one election made the plain run exit 1, the
update printed `Baseline rewritten` and the next plain run said `No findings`
— and it was the first command the new-election checklist gave (issue #135).
Now:

- it **refuses** — writes nothing, exits 1 — while a finding stands on a row
  the baseline already has (a regression, a zero that used to be filled), or
  on a new election's concept set (an unmapped election, a peer gap). Fix or
  classify those first; `--force` rewrites regardless. A stale excuse is the
  one exception (issue #165): re-measuring answers it, so it is written
  through rather than refused over;
- it **reports** what it did: `N row(s) added, M changed, K down more than 5
  points`;
- it **exits 1** while any zero or below-peers cell it wrote is still
  `unexplained`, listing each with the facts a reviewer needs (`8.0 % filled
  (140 of 1,740) against a median 100.0 %; the key is present on every record,
  1,600 left it blank`), like the candidacy table's gate always has. A new
  election's first update therefore ends with the list of cells its author has
  to classify — by editing the status word in the row, not by re-running.

`scripts/build_candidacy_table.py --update-baseline` follows the same
contract, and inherits a below-peers classification from the concept its
column projects (`COLUMN_CONCEPTS`) so the same fact is classified once.

## Three resolution rules a naive walker gets wrong

* Concept paths are relative to the record's `normalized` section, **except**
  the ones naming a section of the record itself. `kandidatavimas` is in both
  places at once: the pre-2016 municipal and results-joined elections hoist the
  candidacy to the record root, and the two 1997 municipal archive elections
  leave it inside `normalized`. Walking only one of them reports four
  100 %-populated cells as zeros.
* A concept's path for an election can be a **list** of paths — an ordered
  resolution: the cell resolves on the first alternative that is filled. The
  `iskele` concept leans on this hardest: its lists are the per-election
  resolution order `scraper/shared/nominator.py` walks for the value
  (issue #82), so the coverage gate and the resolver measure the same thing.
* A **list met mid-path fans out** over its entries, first filled entry wins —
  the 1996–1999 Seimas archive family's `kandidatavimas` is a list of
  candidacies, and its `iskele` lives inside the entries. A list in leaf
  position is a value, not a fan-out.

"Filled" is not truthiness. `privalomas-registruoti-turtas` is `0` for a
candidate who registered no property, and that zero is the declaration. Numbers
and booleans always count; strings and containers have to hold something.

## Keeping it honest

- `tests/test_field_coverage.py` pins the resolver against real parsed records,
  both rules against the shapes the corpus produced, and the checked-in baseline
  against `concept-map.json` — mapping a new election without measuring it fails
  the suite, not just the gate.
- An election in `data/` that no concept maps fails the run (the
  unmapped-election rule). That is how the two elections mapped in issue #85
  were found — 10,165 records the coverage table could not see at all — when
  it was still a stderr note.

## See also

- [ANOMALY_DETECTION.md](ANOMALY_DETECTION.md) — the other detector.
- [ADDING_AN_ELECTION.md](ADDING_AN_ELECTION.md) — the pre-PR step that makes an
  author paste their election's fill rates into the PR body.
- `scripts/reparse_diff.py` — the third gate: the corpus equals what the parsers
  produce.
- `tests/test_corpus_value_hygiene.py` — the fourth: a field that *is* filled
  can still be filled wrongly. It walks every record for the value shapes issue
  #101 removed — a trailing separator, money as a string, a column that is
  `int` here and `float` there — which coverage counts as filled.
