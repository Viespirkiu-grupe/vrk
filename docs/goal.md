# Scraping Plan

## Goal

Collect structured election and candidate data from many different election sites, starting as simply as possible and keeping the pipeline easy to extend.

The first version should prioritize reliability and fast iteration over deduplication or heavy normalization.

## Stack

- Use Python for the scraper codebase.
- Use Playwright only when a site needs a real browser, JavaScript execution, or Cloudflare-style protection.
- Use simple HTTP fetching first whenever a page can be downloaded directly.
- Keep parsing and file writing plain and explicit.

This means the default path is:

1. Fetch page content.
2. Parse the page.
3. Normalize to a small JSON record.
4. Save the record immediately.

If a site can be scraped without a browser, do not use Playwright for it.

## File Layout

We will save one JSON file per candidate-election pair.

Candidate identity will be represented by a slug built from the person name, usually in the form `name-surname`.
If the source already contains a stable identifier, we can store it too, but the filename will rely on the human-readable name slug.

Recommended layout:

- `data/<election_id>/<candidate_id>-<election_id>.json`
- `data/<election_id>/manifest.json`
- `samples/html/<election_id>/...` for HTML samples used during development and testing

Example record file name:

- `data/2024-seimo/jonas-jonaitis-2024-seimo.json`

The JSON file name should encode the person and election so it is easy to trace and re-run.

Each election has its own schema.
There is no global record schema across all elections, so each election folder owns its own parser rules and output shape.
The only thing that stays consistent is the file naming convention and the fact that each JSON record belongs to one candidate in one election.

## JSON Schema

Keep the first version simple and permissive.

Each candidate-election JSON file should contain the schema for that specific election.

At minimum, every record should include:

- `candidateId` as the name-based slug
- `electionId`
- `scrapedAt`
- `sourceUrl`
- `candidateName`

Everything else can vary by election and be stored in whatever shape best matches that election.
If needed, the election-specific JSON can also include `rawFields`, `normalizedFields`, `notes`, `flags`, or any election-only fields.

Do not try to dedupe aggressively in the scraper layer yet.
Save everything that looks useful, even if it is redundant.

## Sitemap Building

There is no global sitemap or reliable master listing for all elections.
Each election needs its own discovery step.

The workflow should be:

1. Launch the election tool for one election.
2. Build a sitemap for that election.
3. Crawl that sitemap instead of repeatedly probing archive listings.
4. Parse the discovered pages into candidate records.

That sitemap can be a simple JSON file that lists the pages to visit for the election.
It does not need to be a public website sitemap; it is just an internal crawl plan.

Suggested sitemap layout:

- `sitemaps/<election_id>.json`

This keeps discovery separate from scraping and avoids spamming the archive listing pages.

## Raw HTML Samples

Keep a small set of raw HTML samples in the repo for development and regression testing.

Use them for:

- parser development
- fixture-based tests
- checking layout changes when a site breaks

Suggested structure:

- `samples/html/<election_id>/page.html`
- `samples/html/<election_id>/list.html`
- `samples/html/<election_id>/candidate.html`

These samples should be small, representative, and easy to refresh.

## Build And Run

The scrapers should be runnable from a single command entrypoint.

There will be a global controller plus one module per election.
The global controller can run one election, or all elections.
Each election module contains its own sitemap builder, parser, and runner.

Suggested modes:

- run one election by id
- run all elections
- run a development mode against stored HTML samples
- build only the sitemap for one election

Examples of usage:

- `python -m scraper run <election_id>`
- `python -m scraper run all`
- `python -m scraper sitemap <election_id>`
- `python -m scraper test <election_id>`

## Testing

Testing should start with the smallest useful layer:

1. Parser tests against saved HTML samples.
2. Schema validation for emitted JSON.
3. A small end-to-end smoke test for one site.

The goal is to catch breakage early without making the scraper too complicated.

## Code Structure

The codebase should be organized around elections, not around a single global schema.

Suggested structure:

- `scraper/cli.py` for the command-line entrypoint
- `scraper/controller.py` for selecting one election or all elections
- `scraper/elections/<election_id>/sitemap.py` for discovery and sitemap building
- `scraper/elections/<election_id>/parser.py` for parsing that election's HTML
- `scraper/elections/<election_id>/runner.py` for fetching, parsing, and writing files
- `scraper/shared/http.py` for shared fetch helpers
- `scraper/shared/browser.py` for Playwright helpers when needed
- `scraper/shared/files.py` for JSON and sample file writing
- `samples/html/<election_id>/...` for saved HTML fixtures
- `data/<election_id>/...` for scraped JSON outputs

Each election module should be self-contained enough that new elections can be added without changing older ones.
The global controller should only coordinate which election module to run.

## Launch Strategy

The scraper should support:

- one-off manual runs
- full site runs
- resume/retry behavior later if needed

At the beginning, launching should be simple and direct.
We can add orchestration, deduplication, and smarter retries later once the basic pipeline is stable.