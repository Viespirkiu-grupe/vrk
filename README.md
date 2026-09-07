# VRK election corpus

[![tests](https://github.com/Viespirkiu-grupe/vrk/actions/workflows/tests.yml/badge.svg)](https://github.com/Viespirkiu-grupe/vrk/actions/workflows/tests.yml)

A scraper for the candidate pages of the Lithuanian Central Electoral
Commission (VRK), and the corpus it produces: **113,073 candidate records
across 55 elections, 1996–2025** — questionnaires, asset and income
declarations, private-interest declarations and campaign finance data, one
JSON file per candidacy.

The corpus itself is not version controlled (`data/`, `sitemaps/` and all but
a fixture subset of `samples/` are gitignored); it ships as [release
assets](https://github.com/Viespirkiu-grupe/vrk/releases) tagged
`corpus-YYYY-MM-DD` — the flat comparison table and the full corpus as one
SQLite database, with a manifest naming the parser commit — or is reproduced
by running the scrapers, and
every election's raw HTML, and every portrait it links, is retained so
parser fixes land by offline re-parse.

Three commands check that a change left the corpus in one piece, and each
answers a question the other two cannot:

```bash
python scripts/reparse_diff.py       # is the corpus what the parsers produce?
python scripts/field_coverage.py     # did a field stop arriving?
python -m scraper anomalies-report   # did a page go wrong?
```

`reparse_diff.py` re-parses every election and diffs the result against
`data/`. `field_coverage.py` resolves every `docs/concept-map.json` path
against every record and gates the fill rates against a checked-in baseline —
`2020-seimo` once shipped with income `null` on all 1,753 records and a green
suite ([docs/FIELD_COVERAGE.md](docs/FIELD_COVERAGE.md)).
`anomalies-report` reads back what the scrapers recorded going wrong and diffs
that against its own baseline
([docs/ANOMALY_DETECTION.md](docs/ANOMALY_DETECTION.md)). All three exit
non-zero on a finding.

Getting the tests to run takes a clone and three dependencies:

```bash
pip install -r requirements-dev.txt
pytest
```

`samples/` and `sitemaps/` carry a fixture subset — every unit at most 1 MiB,
at least one candidate per election, every sitemap but the municipal
generals' — so about 1,680 tests run on a machine that has never scraped
anything. The rest skip, each naming the command that would produce what it
wanted, and only when the whole unit it needs is absent: a path missing inside
a fixture that is present is a failure, not a skip (issue #145).
`docs/FIXTURE_SAMPLES.md` explains the rule and `.github/workflows/tests.yml`
runs the suite on every push and pull request.

Where to start:

- **Getting the data** — the latest
  [`corpus-YYYY-MM-DD` release](https://github.com/Viespirkiu-grupe/vrk/releases):
  `candidacies.csv.gz` for the comparison surface, `vrk-corpus.sqlite.gz`
  for every record, portrait and anomaly log in one queryable file
  ([docs/CANDIDACIES.md](docs/CANDIDACIES.md#distribution));
  `python scripts/build_distribution.py` rebuilds and checksums the assets.
- **One comparable table** — [docs/CANDIDACIES.md](docs/CANDIDACIES.md):
  `python scripts/build_candidacy_table.py` projects the corpus into
  `dist/candidacies.csv.gz` + `dist/vrk.sqlite`, one row per (person,
  election) — education on one ordinal, money EUR-converted with its
  measure named, canonical party ids, typed absences — gated by per-column
  fill rates so a field cannot silently stop arriving.
- **Consuming the data** — [docs/DATA_GUIDE.md](docs/DATA_GUIDE.md): record
  anatomy, the cross-election invariants, the concept→path era map, how to
  join people across elections, and the traps.
- **State of the corpus** — [docs/DATASET.md](docs/DATASET.md): the
  inventory, run history and analysis caveats;
  [docs/OUTPUT_SCHEMA.md](docs/OUTPUT_SCHEMA.md) for per-election schema
  detail.
- **Contributing an election module** —
  [docs/ADDING_AN_ELECTION.md](docs/ADDING_AN_ELECTION.md) for the route from
  a VRK listing URL to a scraped election, and [docs/goal.md](docs/goal.md)
  for the project's ground rules.
- **Browsing** — `dashboard/` is a local person-centric browser over the
  corpus ([docs/DASHBOARD.md](docs/DASHBOARD.md)).
