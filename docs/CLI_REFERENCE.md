# CLI Reference

This project currently exposes one election module through a shared CLI entrypoint.

Run all commands from repository root:

```bash
python -m scraper <command> [args]
```

## Supported Election IDs

- `2016-seimo`
- `2020-seimo`
- `2024-seimo`
- `2019-ep` (European Parliament)
- `2024-ep` (European Parliament)
- `2019-prezidento` (Presidential)
- `2024-prezidento` (Presidential)
- `2023-spalio-8-kupiskio-mero` (2023-10-08 early Kupiškis district mayoral election)

## Election Separation

Each election ID uses its own parser module, HTML samples, sitemap, and output folder.
Running or editing workflows for `2020-seimo` should not require touching `2016-seimo`, and vice versa, because election HTML layouts differ.
The election ID in each command is the isolation boundary that selects the correct scraper implementation.

## Commands

### `fetch-sample`

Download and save the listing HTML sample for an election.

```bash
python -m scraper fetch-sample 2016-seimo
```

Output:

- Updates the listing sample file under `samples/html/2016-seimo/`.

### `sitemap`

Build sitemap JSON from a saved listing sample.

```bash
python -m scraper sitemap 2016-seimo
python -m scraper sitemap 2016-seimo --sample samples/html/2016-seimo/list.html
```

Options:

- `--sample <path>`: Override source HTML sample path.

Output:

- Writes `sitemaps/2016-seimo.json`.
- Prints row/extraction stats.

### `fetch-first-candidate-samples`

Download first sitemap candidate page and tab pages into sample fixtures.

```bash
python -m scraper fetch-first-candidate-samples 2016-seimo
```

Options:

- `--sitemap <path>`: Defaults to `sitemaps/2016-seimo.json`.
- `--samples-root <path>`: Defaults to `samples/html/2016-seimo`.
- `--allow-new-samples`: Allows creating new candidate directories. Disabled by default.

Output:

- Creates/updates `anketa.html`, tab pages, and `index.json` under candidate sample directory.

### `fetch-candidate-samples`

Download selected candidates and all candidate tabs.

```bash
python -m scraper fetch-candidate-samples 2016-seimo --candidate-id agne-sirinskiene
python -m scraper fetch-candidate-samples 2016-seimo --candidate-id agne-sirinskiene --candidate-id gabrielius-landsbergis
```

Options:

- `--candidate-id <id>`: Required. Repeatable.
- `--sitemap <path>`: Defaults to `sitemaps/2016-seimo.json`.
- `--samples-root <path>`: Defaults to `samples/html/2016-seimo`.
- `--allow-new-samples`: Allows creating new candidate directories. Disabled by default.

Output:

- Updates candidate sample directories and prints per-candidate tab stats.

### `parse-anketa-samples`

Parse saved candidate samples into output JSON records.

```bash
python -m scraper parse-anketa-samples 2016-seimo
python -m scraper parse-anketa-samples 2016-seimo --candidate-id regina-ablom
python -m scraper parse-anketa-samples 2020-seimo --candidate-id agne-sirinskiene
```

Options:

- `--candidate-id <id>`: Optional, repeatable. If omitted, parse all sampled candidates.
- `--samples-root <path>`: Defaults to `samples/html/2016-seimo`.
- `--output-root <path>`: Defaults to `data/2016-seimo`.
- `--anomalies-path <path>`: Optional. Defaults to `<output-root>/anomalies.jsonl`.

Output:

- Writes one JSON file per parsed candidate in output root.
- Writes anomalies JSONL summary file.
- Prints parsed row counts and anomaly summary.

## European Parliament (`2019-ep`) Workflow

The 2019 EP election uses the same command surface as the Seimo modules; only
the election ID changes. Its candidate pages differ structurally from the Seimo
pages (the anketa is split across several sibling tables and the private
interest tab is pluralised), but the output schema is kept parallel.

```bash
python -m scraper fetch-sample 2019-ep
python -m scraper sitemap 2019-ep
python -m scraper fetch-candidate-samples 2019-ep --candidate-id petras-austrevicius --allow-new-samples
python -m scraper parse-anketa-samples 2019-ep --candidate-id petras-austrevicius
```

Resumable batch processing helper:

- `scripts/run_ep_2019_batches.sh` mirrors the Seimo batch scripts, tracking run
  state under `.run-state/ep-2019/`.

## European Parliament (`2024-ep`) Workflow

The 2024 EP election shares the 2024-era page layout with `2024-seimo`
(candidate anketa links use the `KandidatasAnketa_rkndId-*` stem and tab
content sits directly after the tab navigation), while keeping the EP tab set
of `2019-ep`. Candidate pages carry no campaign tab — campaigns were run by
the party lists.

```bash
python -m scraper fetch-sample 2024-ep
python -m scraper sitemap 2024-ep
python -m scraper fetch-candidate-samples 2024-ep --candidate-id vitalijus-mitrofanovas --allow-new-samples
python -m scraper parse-anketa-samples 2024-ep --candidate-id vitalijus-mitrofanovas
```

Resumable batch processing helper:

- `scripts/run_ep_2024_batches.sh` mirrors the other batch scripts, tracking
  run state under `.run-state/ep-2024/`.

## Presidential (`2024-prezidento`) Workflow

The 2024 presidential election shares the 2024-era page layout with `2024-ep`
(candidate anketa links use the `KandidatasAnketa_rkndId-*` stem and tab content
sits directly after the tab navigation) and the same five-tab set (no trustees
tab and no campaign tab, unlike `2019-prezidento`). The listing keeps the
presidential shape: a stats table (`table1`) plus a candidate table (`table2`)
whose name cell follows a leading photo cell. The anketa reuses the EP Q6–Q14
declarations but swaps in the presidential eligibility questions for Q15–Q18
(dual citizenship, foreign oath, citizen by origin, three-year residency).

```bash
python -m scraper fetch-sample 2024-prezidento
python -m scraper sitemap 2024-prezidento
python -m scraper fetch-candidate-samples 2024-prezidento --candidate-id gitanas-nauseda --allow-new-samples
python -m scraper parse-anketa-samples 2024-prezidento --candidate-id gitanas-nauseda
```

## Municipal mayor (`2023-spalio-8-kupiskio-mero`) Workflow

The 2023-10-08 early Kupiškis district mayoral election is a five-candidate
single-municipality race, so the fixture set is the complete field. Its pages
mix layouts: the anketa follows the 2024 form (Q6–Q8 plus the Rinkimų kodekso
76 str. declarations Q9–Q14, with no EP or presidential extras), while the
biography keeps the 2020 Seimo numbering (nationality is Q2, so education and
work history shift by one). Three page-level quirks are handled by this module
only:

- some anketa questions are numbered with a space before the dot (`10 .`), which
  the shared strict question-number regex rejects;
- the Q13.4 conviction detail table separates label from value with a plain
  hyphen instead of the 2024 en dash;
- declaration and "Kita" tab bodies are wrapped in their own `<div>` instead of
  following the tab navigation as siblings.

The listing keeps the mayoral shape: a stats table (`table1`) plus a candidate
table (`table2`) whose municipality cell carries its own link, so the anketa
anchor is selected by the `KandidatasAnketa` marker. Candidate pages do carry a
campaign tab.

```bash
python -m scraper fetch-sample 2023-spalio-8-kupiskio-mero
python -m scraper sitemap 2023-spalio-8-kupiskio-mero
python -m scraper fetch-candidate-samples 2023-spalio-8-kupiskio-mero --candidate-id algirdas-raslanas --allow-new-samples
python -m scraper parse-anketa-samples 2023-spalio-8-kupiskio-mero
```

## Helpful Checks

```bash
python -m scraper --help
python -m scraper parse-anketa-samples --help
pytest tests/
```
