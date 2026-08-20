# Scraping Plan

## Goal

Collect structured election and candidate data from VRK election pages, while keeping the workflow reliable and easy to extend election-by-election. The corpus began with the 2016 Seimo election and now reaches back to 2015 — the pre-2016 pages are their own layout family, documented in `docs/PLAN_2015_ELECTIONS.md`.

The current implementation is intentionally focused on one election module and fixture-driven parser development.

## Stack

- Use Python for the scraper codebase.
- Use `requests` + `beautifulsoup4` + `lxml` for fetching and parsing current pages.
- Use simple HTTP fetching first whenever a page can be downloaded directly.
- Keep parsing and file writing plain and explicit.

Current default path:

1. Fetch page content.
2. Save HTML samples for reproducible parser work.
3. Parse saved samples into structured JSON.
4. Emit anomalies for layout and data-shape issues.

If a site can be scraped without a browser, do not add browser automation.

## File Layout

The repository currently uses one JSON file per candidate-election pair and keeps fixtures versioned.

Candidate identity is represented by a slug in the form `name-surname`.
If the source already contains a stable identifier, we can store it too, but the filename will rely on the human-readable name slug.

Current layout:

- `data/<election_id>/<candidate_id>-<election_id>.json`
- `data/<election_id>/anomalies.jsonl`
- `samples/html/<election_id>/list.html`
- `samples/html/<election_id>/<candidate_id>/anketa.html`
- `samples/html/<election_id>/<candidate_id>/<tab>.html`
- `samples/html/<election_id>/<candidate_id>/campaigns/<campaign-key>/<tab>.html`
- `sitemaps/<election_id>.json`

Example record file:

- `data/2024-seimo/jonas-jonaitis-2024-seimo.json`

The JSON file name encodes person and election for traceability and reruns.

Each election owns its own schema.
There is no global record schema across all elections, so each election folder owns its own parser rules and output shape.
The stable convention is file naming and one-record-per-candidate-election.

Each election scraper is also maintained independently.
When editing one election parser (for example `2020-seimo`), do not change another election parser (for example `2016-seimo`) unless the task explicitly requires cross-election work.
This is required because VRK HTML structure and field layout differ by election.

## JSON Schema

The current 2016 Seimo output keeps both raw and normalized sections.

Each candidate-election JSON file contains election-specific payloads.

Current top-level fields include:

- `candidateId` as the name-based slug
- `electionId`
- `candidateName`
- `source` (contains `candidateSourceUrl`)
- `rawData`
- `normalized`

2016 Seimo currently stores:

- `rawData.profile`, `rawData.anketa`, and parsed subpages (`biografija`, `turtoIrPajamuDeklaracijos`, `privaciuInteresuDeklaracija`, `kita`, optional `politinesKampanijosDalyvioDuomenys`)
- `normalized` sections keyed close to source semantics in Lithuanian (`profilis`, `anketa`, `biografija`, `turto-ir-pajamu-deklaracijos`, `privaciu-interesu-deklaracija`, `kita`, optional `politines-kampanijos-dalyvio-duomenys`)

See the dedicated schema document for field-level details: `docs/OUTPUT_SCHEMA.md`.

## Sitemap Building

Each election uses its own discovery step and sitemap file.

Current workflow:

1. Launch the election tool for one election.
2. Build a sitemap for that election.
3. Fetch selected candidate samples from the sitemap.
4. Parse samples into candidate JSON records.

The sitemap is an internal crawl plan, not a public website sitemap.

Suggested sitemap layout:

- `sitemaps/<election_id>.json`

This keeps discovery separate from scraping and avoids spamming the archive listing pages.

## Raw HTML Samples

Keep a small set of raw HTML samples in the repo for parser development and regression testing.

Use them for:

- parser development
- fixture-based tests
- checking layout changes when a site breaks

Current fixture structure (2016 Seimo):

- `samples/html/<election_id>/list.html`
- `samples/html/<election_id>/page.html`
- `samples/html/<election_id>/<candidate_id>/anketa.html`
- `samples/html/<election_id>/<candidate_id>/<tab>.html`
- `samples/html/<election_id>/<candidate_id>/index.json`
- `samples/html/<election_id>/<candidate_id>/campaigns/<campaign-key>/index.json`

Fixture policy and allowlist constraints are documented in `docs/FIXTURE_SAMPLES.md`.

## Build And Run

The scraper is runnable from a single command entrypoint.

Current implementation supports 2016 Seimo commands via `python -m scraper`.

Implemented commands:

- `fetch-sample <election_id>`
- `sitemap <election_id> [--sample <path>]`
- `fetch-first-candidate-samples <election_id> [--sitemap ...] [--samples-root ...] [--allow-new-samples]`
- `fetch-candidate-samples <election_id> --candidate-id <id> ... [--allow-new-samples]`
- `parse-anketa-samples <election_id> [--candidate-id <id> ...] [--samples-root ...] [--output-root ...] [--anomalies-path ...]`

Full CLI usage and examples are documented in `docs/CLI_REFERENCE.md`.

Batch execution helper:

- `scripts/run_election_batches.sh <election-id>` iterates sitemap IDs, fetches temporary samples, parses candidates, appends anomalies, and tracks run state under `.run-state/<election-id>/`.

## Testing

Testing is fixture-first and parser-focused.

Current suite includes:

1. `tests/test_seimo_2016_sample_allowlist.py` for fixture directory allowlist.
2. `tests/test_seimo_2016_candidate_samples.py` for sample fetching behavior.
3. `tests/test_seimo_2016_campaign_parser.py` for campaign tab parsing and normalization.
4. `tests/test_seimo_2016_anomaly_detection.py` for structural anomaly events.
5. `tests/test_seimo_2016_anketa_split_merge.py` for split-row anketa merging.
6. `tests/test_seimo_2016_privaciu_normalization.py` for private-interest normalization.
7. `tests/test_seimo_2016_turto_normalization.py` for asset/income normalization.

Run with `pytest tests/` or a focused subset while iterating.

## Code Structure

The codebase is organized around elections.

Current structure:

- `scraper/cli.py` for the command-line entrypoint
- `scraper/elections/<election_id>/sitemap.py` for discovery and sitemap building
- `scraper/elections/<election_id>/candidate_samples.py` for candidate and tab sample capture
- `scraper/elections/<election_id>/anketa_parser.py` for parsing sampled HTML into JSON payloads
- `scraper/shared/http.py` for shared fetch helpers
- `scraper/shared/files.py` for JSON and sample file writing
- `scraper/shared/anomalies.py` for anomaly event payloads and JSONL writing
- `samples/html/<election_id>/...` for saved HTML fixtures
- `data/<election_id>/...` for scraped JSON outputs

Each election module should stay self-contained so new election parsers can be added with minimal coupling.
In practice, this means parser and fixture changes for one election should not modify another election module unless explicitly planned.

## Launch Strategy

Current workflow supports:

- one-off manual fixture capture and parsing
- targeted candidate parsing by ID
- resumable batch processing via `scripts/run_election_batches.sh`

As additional election modules are introduced, keep command semantics consistent while preserving per-election parsing schemas.