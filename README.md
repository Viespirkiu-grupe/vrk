# VRK election corpus

A scraper for the candidate pages of the Lithuanian Central Electoral
Commission (VRK), and the corpus it produces: **60,366 candidate records
across 40 elections, 1996–2025** — questionnaires, asset and income
declarations, private-interest declarations and campaign finance data, one
JSON file per candidacy.

The corpus itself is not version controlled (`data/`, `sitemaps/` and
`samples/` are gitignored); it is reproduced by running the scrapers, and
every election's raw HTML is retained so parser fixes land by offline
re-parse.

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
