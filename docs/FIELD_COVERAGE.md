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
python scripts/field_coverage.py --update-baseline  # after a deliberate change
```

One pass over `data/` — about 30 seconds for 113,073 records — resolves every
`docs/concept-map.json` path against every record of the elections that map it.
That is 1,295 cells: 37 concepts across 55 elections.

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

## The two rules

**Zero fill.** A mapped cell no record fills. Every one has to be classified in
the baseline, with a note saying why; a new one, or one still marked
`unexplained`, fails the run. When the concept is filled on a median of more
than 90 % of the elections that map it, the message says so — that is the
2020-seimo shape exactly, and it is a regression until someone proves otherwise.

**Regression.** A fill rate more than `--max-drop` points (default 5) below the
baseline. Re-parsing an election is allowed to change what it recovers; losing
five points of a field without saying so is not.

## Status words

Twenty-four of the 1,295 cells are filled by no record. Each carries one of:

| status | count | meaning |
| --- | --- | --- |
| `ok` | 1,242 | filled at some rate |
| `upstream-absent` | 18 | the source publishes no value here — the label is missing, or printed and left blank |
| `empty-is-the-answer` | 6 | every record carries the key and the empty value is the answer: nobody declared a conviction, nobody had an outstanding loan |
| `parser-gap` | 0 | the source publishes it and the parser does not recover it |
| `unexplained` | 0 | nobody has looked. Fails the run. |

`empty-is-the-answer` is checked, not taken on trust: a cell claiming it whose
key is absent on some records is a finding, because that is a different thing
from an empty answer.

`parser-gap` is the word the `2020-seimo` cell would have needed. That it is
unused today is a claim this file makes and the run checks.

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
- The run says so on stderr when an election is in `data/` and no concept maps
  it. That is how the two elections mapped in issue #85 were found: 10,165
  records the coverage table could not see at all.

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
