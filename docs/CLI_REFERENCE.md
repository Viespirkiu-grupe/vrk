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
- `2023-rugsejo-3-seimo-raseiniai-kedainiai` (2023-09-03 early Seimo by-election in Raseiniai–Kėdainiai No. 42)
- `2025-kovo-16-meru` (2025-03-16 early mayoral elections in Jonava, Joniškis and Panevėžys)
- `2017-balandzio-23-meru` (2017-04-23 new mayoral elections in Jonava and Šakiai districts)
- `2017-rugsejo-10-marijampoles-mero` (2017-09-10 new Marijampolė municipality mayoral election)
- `2021-spalio-10-meru` (2021-10-10 new mayoral elections in Kelmė and Trakai districts)

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

## Seimo by-election (`2023-rugsejo-3-seimo-raseiniai-kedainiai`) Workflow

The 2023-09-03 early Seimo by-election in the single-member Raseiniai–Kėdainiai
constituency (No. 42) fielded eight candidates, so the fixture set is the
complete field. Unlike the 2023 mayoral pages, these carry none of that
election's layout quirks: the listing is the `2024-seimo` full-list shape (stats
tables `table1`/`table2` followed by the candidate table `table3`, name link in
the first cell, winner marked with a `(V)` suffix), and tab bodies follow the tab
navigation as siblings, so the 2024 page parsers apply directly.

Two details differ from `2024-seimo`:

- the biography questionnaire keeps the 2023 numbering (nationality is Q2, so
  education and work history shift by one), shared with
  `2023-spalio-8-kupiskio-mero`;
- Q8 asks for a single membership and is answered inline rather than with a
  membership table.

Candidates run either their own campaign (`Savarankiškas`, publishing all five
campaign tabs) or a party-represented one (`Atstovaujamasis`, donations only).

```bash
python -m scraper fetch-sample 2023-rugsejo-3-seimo-raseiniai-kedainiai
python -m scraper sitemap 2023-rugsejo-3-seimo-raseiniai-kedainiai
python -m scraper fetch-candidate-samples 2023-rugsejo-3-seimo-raseiniai-kedainiai --candidate-id matas-skamarakas --allow-new-samples
python -m scraper parse-anketa-samples 2023-rugsejo-3-seimo-raseiniai-kedainiai
```

## Municipal mayor (`2025-kovo-16-meru`) Workflow

The 2025-03-16 early mayoral elections cover three municipalities — Jonavos
rajono, Joniškio rajono and Panevėžio miesto — with fourteen candidates, so the
fixture set is the complete field.

The listing is the mayoral shape shared with `2023-spalio-8-kupiskio-mero`
(stats table `table1` plus candidate table `table2`, anketa anchor picked by the
`KandidatasAnketa` marker because the municipality cell carries its own link),
but the candidate pages are pure 2024 layout: tab bodies follow the tab
navigation as siblings, Q8 is answered with a membership table, and the biography
questionnaire has no nationality question. The anketa itself is the mayoral
Q6–Q14 set, with no EP or presidential eligibility questions.

Two election-specific details:

- The listing appends a status note to the name of a candidate whose
  registration was revoked — `Povilas BEIŠYS(išbrauktas - Seimo nutarimu)`. The
  note is split from the name into `candidateNote` rather than discarded; the
  candidate page itself leaves that line blank. All four Jonava candidates
  carry it.
- Struck-off candidates publish five tabs instead of six (no campaign tab), so
  the campaign tab is fetched when present but is not an expected tab.

```bash
python -m scraper fetch-sample 2025-kovo-16-meru
python -m scraper sitemap 2025-kovo-16-meru
python -m scraper fetch-candidate-samples 2025-kovo-16-meru --candidate-id gediminas-cepulis --allow-new-samples
python -m scraper parse-anketa-samples 2025-kovo-16-meru
```

## Municipal mayor (`2017-balandzio-23-meru`) Workflow

The 2017-04-23 new mayoral elections cover Jonavos and Šakių rajonai — eleven
candidates, so the fixture set is the complete field. This is the oldest
election in the repository and predates the 2024 page layout entirely:

- the anketa is split across sibling tables with standalone record tables
  between them, and sub-questions are numbered without a trailing dot
  (`8.2 Ar nesate ...`), which the strict question-number pattern reads as
  question `8`. Both are the 2019 EP shape, so that module's profile and anketa
  parsers are reused;
- Q9 quotes the statute it refers to in a row of its own and the answer is
  rendered on that continuation row, not on the question row;
- photos are base64 data URIs, the private-interest declaration uses the
  `ID001x` section blocks, and the income summary is taken from the GPM308 form,
  whose labels name their own field numbers — so the asset/income aliases are
  local to this module;
- candidate pages link every campaign participant through the treasurer page
  (`savarankiskasIzdininkas_pkdId-...`), but party-represented participants have
  no treasurer page and that link 404s upstream. The fetcher falls back to
  `atstovaujamasis_pkdId-...`, which recovers the campaign data for four of the
  eleven candidates.

```bash
python -m scraper fetch-sample 2017-balandzio-23-meru
python -m scraper sitemap 2017-balandzio-23-meru
python -m scraper fetch-candidate-samples 2017-balandzio-23-meru --candidate-id eugenijus-sabutis --allow-new-samples
python -m scraper parse-anketa-samples 2017-balandzio-23-meru
```

## Municipal mayor (`2017-rugsejo-10-marijampoles-mero`) Workflow

The 2017-09-10 new Marijampolė municipality mayoral election fielded eight
candidates, so the fixture set is the complete field. Its pages are the same
vintage as `2017-balandzio-23-meru` — same question numbering, same Q9
continuation row, same GPM308 income labels, same base64 photos — so this module
reuses that one's parsing rules and only carries its own election id, listing URL
and paths.

One difference in the campaign data: candidates whose campaign is run by their
party have a participant page with no tab navigation at all, so only the
participant metadata is recorded and the donation sections stay empty. The
treasurer-link fallback of the April election is reused for the rest.

```bash
python -m scraper fetch-sample 2017-rugsejo-10-marijampoles-mero
python -m scraper sitemap 2017-rugsejo-10-marijampoles-mero
python -m scraper fetch-candidate-samples 2017-rugsejo-10-marijampoles-mero --candidate-id irena-lunskiene --allow-new-samples
python -m scraper parse-anketa-samples 2017-rugsejo-10-marijampoles-mero
```

## Municipal mayor (`2021-spalio-10-meru`) Workflow

The 2021-10-10 new mayoral elections cover Kelmės and Trakų rajonai — fourteen
candidates, so the fixture set is the complete field. The pages sit between the
two eras already in the repository: the profile card, the `<div>`-wrapped tab
bodies and the biography questionnaire match `2023-spalio-8-kupiskio-mero`
(whose helpers this module reuses), while the anketa is numbered like the 2020
Seimo one — Q6.x contacts, Q7.x position and membership — with the municipal
36 str. 11 d. declarations under Q8.x, the conviction questions under Q9.x and
the former-USSR question as Q10.

Two details are specific to this election:

- Q7.1 is written without a trailing dot, which the strict question-number
  pattern reads as question `7` — the position question — so numbers are
  re-derived with the tolerant pattern;
- the Q9.1 conviction table names its columns after the sub-question numbers
  (`9.1.1. Apkaltinamojo nuosprendžio (sprendimo) data:`), which are mapped to
  the field names the other elections use.

```bash
python -m scraper fetch-sample 2021-spalio-10-meru
python -m scraper sitemap 2021-spalio-10-meru
python -m scraper fetch-candidate-samples 2021-spalio-10-meru --candidate-id stasys-jokubauskas --allow-new-samples
python -m scraper parse-anketa-samples 2021-spalio-10-meru
```

## Helpful Checks

```bash
python -m scraper --help
python -m scraper parse-anketa-samples --help
pytest tests/
```
