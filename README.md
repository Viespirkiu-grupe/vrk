# VRK election corpus

[![tests](https://github.com/Viespirkiu-grupe/vrk/actions/workflows/tests.yml/badge.svg)](https://github.com/Viespirkiu-grupe/vrk/actions/workflows/tests.yml)

A scraper for the candidate pages of the Lithuanian Central Electoral
Commission (VRK), and the corpus it produces: **113,073 candidate records
across 55 elections, 1996–2025** — questionnaires, asset and income
declarations, private-interest declarations and campaign finance data, one
JSON file per candidacy.

The corpus is not version controlled (`data/`, `sitemaps/` and all but a
fixture subset of `samples/` are gitignored). It ships as [release
assets](https://github.com/Viespirkiu-grupe/vrk/releases) tagged
`corpus-YYYY-MM-DD`, or is reproduced by running the scrapers. Raw HTML is
retained as fetched, and linked portraits are archived by a second pass over
the finished scrape (`scripts/run_all_elections.sh` runs both), so parser
fixes land by offline re-parse.

## Get the data

```bash
gh release download --pattern 'vrk-corpus.sqlite.gz' --pattern 'vrk-photos-*.sqlite'
gunzip vrk-corpus.sqlite.gz
python scripts/unpack_corpus.py vrk-corpus.sqlite   # writes ./data
```

- `candidacies.csv.gz`: one comparable row per (person, election).
- `vrk-corpus.sqlite.gz`: every record and anomaly log.
- `vrk-photos-N.sqlite`: the portraits.

## Run the tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tracked fixtures run about 1,680 tests on a fresh clone. The rest skip
and name the command that produces what they need
([docs/FIXTURE_SAMPLES.md](docs/FIXTURE_SAMPLES.md)).

## Check the corpus

Each command exits non-zero on a finding:

```bash
python scripts/reparse_diff.py         # is the corpus what the parsers produce?
python scripts/field_coverage.py       # did a field stop arriving?
python -m scraper anomalies-report     # did a page go wrong?
python scripts/value_plausibility.py   # is a value possible at all?
```

## Docs

- [DATA_GUIDE.md](docs/DATA_GUIDE.md): record anatomy, invariants, joining
  people across elections, traps.
- [CANDIDACIES.md](docs/CANDIDACIES.md): the comparison table and the
  release assets.
- [DATASET.md](docs/DATASET.md): inventory and analysis caveats.
- [OUTPUT_SCHEMA.md](docs/OUTPUT_SCHEMA.md): per-election schema.
- [CLI_REFERENCE.md](docs/CLI_REFERENCE.md): commands and scripts.
- [ADDING_AN_ELECTION.md](docs/ADDING_AN_ELECTION.md): from a VRK listing
  URL to a scraped election.
- [FIELD_COVERAGE.md](docs/FIELD_COVERAGE.md),
  [ANOMALY_DETECTION.md](docs/ANOMALY_DETECTION.md): the corpus gates.
- [DASHBOARD.md](docs/DASHBOARD.md): the Astro browser in `frontend/`.
- [DEPLOY.md](docs/DEPLOY.md): production (Docker behind Cloudflare).

## Licence, data terms and personal data

The code is MIT-licensed ([LICENSE](LICENSE)). The corpus — the release
assets, the record files, the person index in `dashboard/` — is a compilation
of VRK's public candidate pages published under **CC BY 4.0**;
[DATA_TERMS.md](DATA_TERMS.md) states the required attribution and how to ask
for a person's record to be removed or corrected.
[docs/PERSONAL_DATA.md](docs/PERSONAL_DATA.md) lists which fields are about
whom, and which the public release drops.
