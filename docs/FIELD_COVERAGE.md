# Field coverage

An anomaly says a page went wrong. This gate says a *field stopped arriving*:
every key present, every value `null`, every test green.

```bash
python scripts/field_coverage.py                    # measure, check, exit 1 on a finding
python scripts/field_coverage.py 2020-seimo         # one election's cells
python scripts/field_coverage.py --update-baseline  # after a deliberate change; refuses over a standing finding
python scripts/field_coverage.py --unmapped         # also: a field the map denies an election that has it
```

One pass over `data/` resolves every `docs/concept-map.json` path against every
record of the elections that map it: one cell per (concept, election). The
candidacy table ships the matrix as `coverage.tsv` and the `coverage` table of
`vrk.sqlite`, and the dashboard draws it as **▦ Aprėptis**.

## What it produces

`data/coverage.tsv` (gitignored) holds the full table:

```
concept          election                   records  keyPresent  nonNull  pct   status  note
gautos-pajamos   2020-seimo                    1754        1753     1753  99.9  ok
gimimo-vieta     2000-kovo-19-savivaldybiu…    9879        9879        0   0.0  upstream-absent  The 2000 municipal card…
```

`keyPresent` and `nonNull` are separate because a key never written and a key
written as `null` are different failures.

`docs/coverage-baseline.tsv` is checked in: one line per cell with the fill
rate, a status word and a note. Counts are not committed; they move with every
scrape.

## The rules

1. **Zero fill.** A mapped cell no record fills must be classified in the
   baseline with a note. A new one, or one marked `unexplained`, fails.
2. **Stale excuse.** A cell classified as legitimately empty that now fills.
   Reported, but does not block `--update-baseline`: re-measuring rewrites the
   row as `ok`.
3. **Regression.** A fill rate more than `--max-drop` points (default 5) below
   the baseline.
4. **Below its peers.** A filled cell more than `--max-below-peers` points
   (default 25) under the concept's median across the other elections that map
   it, where that median is above 90 %. It must carry `partly-published` or
   `partly-answered` with a note.
5. **Unmapped election.** An election under `data/` that no concept maps. A
   deliberate exclusion is a `*` row:
   `*<TAB><election-id><TAB>0.0<TAB>not-mapped<TAB>why`.
6. **Peer gap.** A new election (no baseline row) that maps fewer concepts
   than the nearest-dated mapped election of the same `kind` in
   `scraper/elections.json`. Each missing concept is mapped or recorded as a
   `not-mapped` row.
7. **Unmapped fill** (`--unmapped`, opt-in). A concept's path that fills on at
   least 1 % of the records of an election the map does not give it for. The
   dashboard would otherwise say that election never published the field.
   `tests/test_field_coverage.py` runs it on a 300-record sample per election.

## Status words

| status | count | meaning |
| --- | --- | --- |
| `ok` | 1,324 | filled at some rate, in line with the concept's other elections |
| `upstream-absent` | 18 | the source publishes no value here — the label is missing, or printed and left blank |
| `empty-is-the-answer` | 6 | every record carries the key and the empty value is the answer: nobody declared a conviction, nobody had an outstanding loan |
| `parser-gap` | 0 | the source publishes it and the parser does not recover it |
| `partly-published` | 29 | filled, but the source prints the field on only some records; the key is absent on the rest |
| `partly-answered` | 17 | filled, but far below the peers with the key on every record: asked and left blank, or answered „-“ |
| `not-mapped` | 0 | a deliberate exclusion, with a note saying why |
| `unexplained` | 0 | nobody has looked. Fails the run. |

These are checked: an `empty-is-the-answer` cell whose key is absent on some
records is a finding, and `tests/test_field_coverage.py` fails if a
below-peers cell reads `ok` or a `partly-*` word is no longer needed.

## `--update-baseline`

- **Refuses** (writes nothing, exits 1) while a regression, a lost zero, an
  unmapped election or a peer gap stands. Fix or classify first; `--force`
  rewrites regardless. A stale excuse is written through.
- **Reports** `N row(s) added, M changed, K down more than 5 points`.
- **Exits 1** while any zero or below-peers cell it wrote is `unexplained`,
  listing each with its facts. Classify by editing the status word in the row.

`scripts/build_candidacy_table.py --update-baseline` follows the same contract
and inherits a below-peers classification from the concept its column projects
(`COLUMN_CONCEPTS`).

## Resolution rules

- Paths are relative to `normalized`, except those naming a top-level section.
  `kandidatavimas` sits at the record root in the pre-2016 municipal and
  results-joined elections and inside `normalized` in the two 1997 municipal
  archive elections; check both.
- A path can be a **list** of paths, resolved in order; the first filled one
  wins. `iskele`'s lists are the order `scraper/shared/nominator.py` walks.
- A **list met mid-path fans out** over its entries, first filled entry wins.
  A list in leaf position is a value.
- "Filled" is not truthiness: numbers and booleans always count (a `0` is a
  declaration); strings and containers must hold something.

## Related gates

- [ANOMALY_DETECTION.md](ANOMALY_DETECTION.md): pages that went wrong.
- `scripts/reparse_diff.py`: the corpus equals what the parsers produce.
- `tests/test_corpus_value_hygiene.py`: filled values with the wrong shape.
- `tests/test_field_coverage.py`: the resolver, the rules, and the baseline
  against `concept-map.json`.
