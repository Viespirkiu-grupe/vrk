# VRK election corpus

[![tests](https://github.com/Viespirkiu-grupe/vrk/actions/workflows/tests.yml/badge.svg)](https://github.com/Viespirkiu-grupe/vrk/actions/workflows/tests.yml)

A scraper for the candidate pages of the Lithuanian Central Electoral
Commission (VRK), and the corpus it produces: **113,002 candidate records
across 51 elections, 1996–2025** — questionnaires, asset and income
declarations, private-interest declarations and campaign finance data, one
JSON file per candidacy.

The corpus itself is not version controlled (`data/`, `sitemaps/` and all but
a fixture subset of `samples/` are gitignored); it is reproduced by running the
scrapers, and
every election's raw HTML is retained so parser fixes land by offline
re-parse. `python scripts/reparse_diff.py` is the check that they did: it
re-parses every election and diffs the result against `data/`, and exits
non-zero if any record no longer matches the parser that claims to produce
it.

Getting the tests to run takes a clone and three dependencies:

```bash
pip install -r requirements-dev.txt
pytest
```

`samples/` carries a fixture subset — every unit at most 1 MiB, at least one
candidate per election — so about 1,000 tests run on a machine that has never
scraped anything. The rest skip, each naming the command that would produce
what it wanted; `docs/FIXTURE_SAMPLES.md` explains the rule and
`.github/workflows/tests.yml` runs the suite on every push and pull request.

Where to start:

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
