# CLI Reference

Run every command from the repository root:

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
- `2023-kovo-5-savivaldybiu-tarybu-ir-meru` (2023-03-05 municipal councils and mayors, all 60 municipalities)
- `2019-kovo-3-savivaldybiu-tarybu` (2019-03-03 municipal councils, all 60 municipalities)
- `2023-spalio-8-kupiskio-mero` (2023-10-08 early Kupiškis mayoral election)
- `2023-geguzes-7-visagino-mero` (2023-05-07 repeat Visaginas mayoral vote)
- `2023-rugsejo-3-seimo-raseiniai-kedainiai` (2023-09-03 Seimo by-election, Raseiniai–Kėdainiai No. 42)
- `2025-kovo-16-meru` (2025-03-16 early mayoral elections in Jonava, Joniškis and Panevėžys)
- `2017-balandzio-23-meru` (2017-04-23 mayoral elections in Jonava and Šakiai)
- `2017-rugsejo-10-marijampoles-mero` (2017-09-10 Marijampolė mayoral election)
- `2021-spalio-10-meru` (2021-10-10 mayoral elections in Kelmė and Trakai)
- `2021-balandzio-11-radviliskio-mero` (2021-04-11 Radviliškis mayoral election)
- `2017-balandzio-23-seimo-anyksciai-panevezys` (2017-04-23 Seimo by-election, Anykščiai–Panevėžys No. 49)
- `2018-rugsejo-16-seimo-zanavykai` (2018-09-16 Seimo election, Zanavykai No. 64)
- `2019-rugsejo-8-seimo` (2019-09-08 Seimo elections in Žirmūnai No. 4, Gargždai No. 31 and Žiemgala No. 46)
- `2015-kovo-1-seimo-zirmunai` (2015-03-01 Seimo by-election, Žirmūnai No. 4)
- `2015-birzelio-7-seimo-varena-eisiskes` (2015-06-07 Seimo by-election, Varėna–Eišiškės No. 70)
- `2015-lapkricio-8-telsiu-mero` (2015-11-08 Telšiai council member-mayor election)
- `2015-birzelio-7-pakartotiniai-sirvintos-trakai` (2015-06-07 repeat Širvintos mayor and Trakai council/mayor elections)
- `2015-birzelio-21-pakartotiniai-silutes` (2015-06-21 repeat Šilutė council election)
- `2015-kovo-1-savivaldybiu` (2015-03-01 municipal councils and the first direct mayoral elections, all 60 municipalities)
- `2011-vasario-27-savivaldybiu` (2011-02-27 municipal councils, all 60 municipalities)
- `2007-vasario-25-savivaldybiu` (2007-02-25 municipal councils, all 60 municipalities)
- `1996-spalio-20-seimo` (1996-10-20 Seimas general election, 71 constituencies)
- `1997-kovo-23-seimo-pakartotiniai` (1997-03-23 Seimo repeat election, four Vilnius-region constituencies)
- `1997-gruodzio-21-seimo-pakartotiniai` (1997-12-21 Seimo repeat election, Aukštaitijos No. 28)
- `1998-kovo-22-seimo-pakartotiniai` (1998-03-22 Seimo repeat elections, Naujosios Vilnios No. 10 and Vilniaus Trakų No. 57)
- `1998-lapkricio-15-seimo-pakartotiniai` (1998-11-15 Seimo repeat election, Nevėžio No. 26)
- `1999-kovo-21-seimo-pakartotiniai` (1999-03-21 Seimo repeat elections, Naujosios Vilnios No. 10, Nevėžio No. 26 and Vilniaus Trakų No. 57)
- `1997-kovo-23-savivaldybiu-tarybu` (1997-03-23 municipal councils, all 56 municipalities)
- `1997-birzelio-29-svenciniu-tarybos-pakartotiniai` (1997-06-29 Švenčionys council repeat election)
- `2007-spalio-7-seimo-dzukija` (2007-10-07 Seimo election, Dzūkijos No. 69)
- `2008-seimo` (2008-10-12 Seimas general election)
- `2009-prezidento` (2009-05-17 presidential election)
- `2009-ep` (2009-06-07 European Parliament election)
- `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai` (2009-11-15 Seimo elections, Šilalės–Šilutės No. 33 and Vilniaus–Šalčininkų No. 56)
- `2011-vasario-13-seimo-marijampole` (2011-02-13 Seimo election, Marijampolės No. 29)
- `2012-seimo` (2012-10-14 Seimas general election)
- `2013-kovo-3-seimo-birzai-zarasai-ukmerge` (2013-03-03 Seimo elections, Biržų–Kupiškio No. 48, Zarasų–Visagino No. 52 and Ukmergės No. 61)
- `2014-prezidento` (2014-05-11 presidential election)
- `2014-ep` (2014-05-25 European Parliament election)
- `2002-prezidento` (2002-12-22 presidential election, runoff 2003-01-05)
- `2002-gruodzio-22-savivaldybiu-tarybu` (2002-12-22 municipal councils, all 60 municipalities)
- `2003-birzelio-15-seimo-nauji` (2003-06-15 Seimo elections in four constituencies; nobody elected)
- `2004-ep` (2004-06-13 European Parliament election)
- `2004-prezidento` (2004-06-13 presidential election, runoff June 27)
- `2004-seimo` (2004-10-10 Seimas general election)
- `2005-lapkricio-20-seimo-kedainiai` (2005-11-20 Seimo election, Kėdainių No. 43)
- `2000-seimo` (2000-10-08 Seimas general election)
- `2000-kovo-19-savivaldybiu-tarybu` (2000-03-19 municipal councils, all 60 municipalities)

Each election id selects its own parser module, samples, sitemap and output
folder. Changing one election's module should not touch another's.

## Fetching

Every request goes through `scraper/shared/http.py`:

- **Pacing.** `VRK_MIN_REQUEST_INTERVAL` (seconds, default `0.15`) is the
  minimum gap between two requests from one process. Set `0` against a local
  stub.
- **Decoding.** The charset comes from the response's declaration, else
  UTF-8; anything else is reported as a guess.
- **Retries.** A truncated body is retried. A bot-check page served as 200 is
  refused. A 403 is not retried.

## Commands

### `fetch-sample`

Save an election's listing HTML under `samples/html/<election-id>/`.

```bash
python -m scraper fetch-sample 2016-seimo
```

- `--allow-fixture-overwrite`: fetch even though `samples/html/<election-id>/`
  exists. Without it the command refuses, because the listing samples are
  tracked fixtures. Use it to refresh fixtures or to complete untracked
  listing pages on a fresh clone.

Municipal generals also fetch every district and party-list page. Pages
already saved are skipped, so an interrupted run resumes.

### `sitemap`

Build `sitemaps/<election-id>.json` from the saved listing and print stats.

```bash
python -m scraper sitemap 2016-seimo
python -m scraper sitemap 2016-seimo --sample samples/html/2016-seimo/list.html
```

- `--sample <path>`: override the listing sample.

### `fetch-first-candidate-samples`

Fetch the first sitemap candidate's page and tabs into the samples.

```bash
python -m scraper fetch-first-candidate-samples 2016-seimo
```

- `--sitemap <path>`: default `sitemaps/<election-id>.json`.
- `--samples-root <path>`: default `samples/html/<election-id>`.
- `--allow-new-samples`: allow creating new candidate directories.

### `fetch-candidate-samples`

Fetch selected candidates and all their tabs.

```bash
python -m scraper fetch-candidate-samples 2016-seimo --candidate-id agne-sirinskiene
python -m scraper fetch-candidate-samples 2016-seimo --candidate-id agne-sirinskiene --candidate-id gabrielius-landsbergis
```

- `--candidate-id <id>`: required, repeatable.
- `--sitemap <path>`, `--samples-root <path>`, `--allow-new-samples`: as above.
- `--anomalies-path <path>`: write the fetch stage's events
  (`TabDownloadFailed`, `MissingExpectedTab`, `CampaignRootFetchFailed`, …)
  there as JSONL. No default: the file is written whole, so pointing it at an
  election's `anomalies.jsonl` would truncate it. Without the flag the events
  are printed and dropped, which is why 8,980 of the corpus's 9,027 anomaly
  events say `stage: "parse"`. The 47 that say `"fetch"` come from the portrait
  backfill (`PortraitFetchFailed`) and the batch runner
  (`CandidateFetchFailed`), which pass a per-candidate path and append.

### `build-results`

For elections whose candidate pages mark no winner (every static-page family,
1996–2015), fetch VRK's results pages and write
`sitemaps/<election-id>.results.json`. `parse-anketa-samples` joins it into
`kandidatavimas.isrinktas`.

```bash
python -m scraper build-results 2012-seimo
python -m scraper parse-anketa-samples 2012-seimo --samples-root samples-full/2012-seimo
```

- Pages are cached under `samples/results/<election-id>/`, so a re-run is
  offline.
- Read the printed stats before trusting the file: `unresolved`,
  `*NotInSitemap` and `seatCountMismatches` should be 0 or explained.
- Exit 1, and no file, when a results page could not be fetched or no winner
  was resolved. A 404 for a page the tree does not publish counts as absent.
- Elections where nobody was elected carry `"nobodyElected": true`. An empty
  map without it means "no results", and `isrinktas` stays `null`.
- `scripts/run_election_batches.sh` runs it before the first batch when the
  results file is missing.

The walkers and their traps are documented in
`scraper/shared/election_results.py` and
`scraper/shared/seimo_archive_1990s_results.py`; each module's `results.py`
is its configuration.

### `parse-anketa-samples`

Parse saved candidate samples into one JSON record per candidate.

```bash
python -m scraper parse-anketa-samples 2016-seimo
python -m scraper parse-anketa-samples 2016-seimo --candidate-id regina-ablom
```

- `--candidate-id <id>`: optional, repeatable; default all sampled candidates.
- `--samples-root <path>`: default `samples/html/<election-id>`.
- `--output-root <path>`: default `data/<election-id>`.
- `--anomalies-path <path>`: default `<output-root>/anomalies.jsonl`. The run
  replaces only its own `parse`-stage events for the candidates it parsed and
  keeps every other line.

Campaign tab paths in each candidate's `index.json` are resolved against the
samples root in use. A listed tab file that cannot be read emits
`CampaignTabSampleMissing`.

### `anomalies-report`

Count the corpus's `anomalies.jsonl` events per type per election, worst
severity first, and diff them against `docs/anomaly-baseline.tsv`.

```bash
python -m scraper anomalies-report                    # every election
python -m scraper anomalies-report 2020-seimo         # one election
python -m scraper anomalies-report --errors-only      # severity "error" only
python -m scraper anomalies-report --update-baseline  # after a deliberate change
```

- `election_id`: optional, repeatable; default every election under the data root.
- `--data-root <path>`: default `data`.
- `--errors-only`: only `severity: "error"` events.
- `--baseline <path>`: default `docs/anomaly-baseline.tsv`.
- `--update-baseline`: rewrite the baseline. Refused when the run is narrowed.

Exit 1 when the run has an event type the baseline lacks, more of a type than
it records, or an election whose total fell below half the baseline's (a wiped
`anomalies.jsonl`). Fewer events is printed, not failed. See
[ANOMALY_DETECTION.md](ANOMALY_DETECTION.md).

## Workflow

One election, by hand:

```bash
python -m scraper fetch-sample <election-id>
python -m scraper sitemap <election-id>
python -m scraper build-results <election-id>    # results-joined elections only
python -m scraper fetch-candidate-samples <election-id> --candidate-id <id> --allow-new-samples
python -m scraper parse-anketa-samples <election-id>
```

A full scrape of one election, resumable:

```bash
scripts/run_election_batches.sh <election-id>
```

It fetches into `samples-full/<election-id>/` (kept, so a later parser fix is
an offline re-parse) and tracks state under `.run-state/<election-id>/`.
Environment: `BATCH_SIZE` (200), `MAX_BATCHES` (0 = until done),
`THROTTLE_SECONDS` (0.4), `STOP_ON_ANOMALY` (0), `SAMPLES_ROOT`,
`KEEP_SAMPLES` (1; 0 deletes each candidate's HTML after parsing), `STATE_DIR`,
`PYTHON_BIN`.

Every election, or the named ones:

```bash
scripts/run_all_elections.sh [election-id ...]
```

Per election it runs the batch runner, then `backfill_url_portraits.py`, then
`reparse_diff.py --full --apply`. `FETCH_PORTRAITS=0` stops after the scrape
and leaves the linked portraits unarchived. `REPARSE_JOBS` (8) sets the
re-parse processes.

### Per-election notes

| elections | what differs |
|---|---|
| the 35 results-joined elections (1996–2015) | run `build-results` before parsing |
| `2019-kovo-3-savivaldybiu-tarybu`, `2023-kovo-5-savivaldybiu-tarybu-ir-meru` | `fetch-sample` also saves 465 / 467 party-list pages under `lists/`; the sitemap merges mayoral and council candidacies on VRK's candidate id |
| `2015-kovo-1-savivaldybiu`, `2011-vasario-27-savivaldybiu`, `2007-vasario-25-savivaldybiu`, `2002-gruodzio-22-savivaldybiu-tarybu`, `2000-kovo-19-savivaldybiu-tarybu`, `1997-kovo-23-savivaldybiu-tarybu`, the 2015 repeats | `fetch-sample` walks every district and list page |
| the municipal generals | candidate ids are `<name-slug>-<vrkCandidateId>`, because many candidates share a name |
| `2015-birzelio-7-pakartotiniai-sirvintos-trakai` | `markerJoinMismatch` is 1: Marija Puč has two VRK ids. Don't merge on name |
| `2002-prezidento` | questionnaires and declarations are scans: archived and linked, never OCR'd |
| `2002-prezidento`, `2004-prezidento` | biographies and programmes are Word documents, read by `scraper/shared/word_doc.py` |
| small elections and the archive by-elections | the fixture set is the whole field; no batch run needed |

Each module's docstrings describe its page layout.

## The re-parse gate (`scripts/reparse_diff.py`)

Re-parses elections from their retained HTML into a scratch tree and diffs the
result against `data/`. Each differing JSON path is `added`, `removed`,
`changed`, `type`, `length` or `order` (same keys, other sequence), with list
indices collapsed to `[]`.

```bash
python scripts/reparse_diff.py                      # all elections, fixtures
python scripts/reparse_diff.py 2019-ep 2020-seimo   # named elections
python scripts/reparse_diff.py --full --jobs 8 2019-ep
python scripts/reparse_diff.py --full --jobs 8 --apply 2019-kovo-3-savivaldybiu-tarybu
```

- `--full`: parse every retained candidate (`samples-full/<id>/`) instead of
  the fixtures. A candidate or election missing from the retained tree falls
  back to its fixtures; the output line says how many.
- `--apply`: copy the re-parsed records that differ over `data/<id>/`, with
  their photo sidecars, and regenerate the `parse`-stage events in
  `anomalies.jsonl`. Requires `--full`.
- `--jobs N`: parser processes (default 1).
- `--top N`, `--repo-root`, `--work-root`.

Exit **0** when nothing differs, **1** when something does, **2** when the run
could not be made. A parser change is not done until this is 0.

### `scripts/backfill_url_portraits.py`

Every era except 2016–2019 links portraits by URL. This fetches them into the
retained trees as `portrait.<ext>` plus `portrait.json` (URL, fetch time,
hash), beside the candidate's pages. It does not touch `data/`; the next
`reparse_diff.py --full --apply` turns them into `photos/` sidecars.

```bash
python scripts/backfill_url_portraits.py                  # every election
python scripts/backfill_url_portraits.py 2020-seimo       # named elections
python scripts/backfill_url_portraits.py --dry-run        # count, no network
python scripts/backfill_url_portraits.py --only-fixtures  # the fixture trees first
python scripts/backfill_url_portraits.py --retry-failed 2000-seimo
python scripts/reparse_diff.py --full --jobs 8 --apply <election-id> …   # then
```

A candidate whose `portrait.json` already names the URL is skipped. A URL that
returns anything but an image is recorded as a failure in `portrait.json`,
stamped onto the record's `photoMeta`, and logged as a `PortraitFetchFailed`
event. Only `--retry-failed` asks again.

## The nominator gate (`scripts/nominator_report.py`)

Resolves every record's nominator (`scraper/shared/nominator.py`, using the
`iskele` paths in `docs/concept-map.json`), joins it to `scraper/parties.json`,
and reports records that resolve null on a mapped election, resolved strings
no registry entry claims, and forms `docs/nominator-forms.tsv` lacks.

```bash
python scripts/nominator_report.py                  # check, exit 1 on a finding
python scripts/nominator_report.py 2024-seimo       # one election
python scripts/nominator_report.py --update         # rewrite the forms table and the registry's unmatched block
```

After `--update`, classify each new form in the registry (an alias of an
entry, or a new entry) until `tests/test_party_registry.py` passes. The
per-election table goes to `data/nominator-report.tsv`.

## The lineage report (`scripts/party_lineage_report.py`)

Proposes registry `predecessors` links from shared candidates: every ordered
pair of nominators where the earlier one's last election precedes the later
one's first and at least a third of the smaller side's persons (three or more)
stood for both. Each pair must be linked or listed in `reviewedDistinct` with
a reason.

```bash
python scripts/build_person_index.py                 # the index it reads
python scripts/party_lineage_report.py               # findings, exit 1 on any
python scripts/party_lineage_report.py --all         # every pair, linked ones too
```

Settle a finding by adding the earlier id to the later entry's `predecessors`,
or the pair to `reviewedDistinct`. The pair table goes to
`data/party-lineage-report.tsv`.

## What is in `scripts/`, and what is spent

**Gates and builders**, run when the corpus or parsers change:
`reparse_diff.py`, `field_coverage.py`, `value_plausibility.py`,
`fixture_record_hashes.py`, `build_person_index.py`,
`build_candidacy_table.py`, `build_distribution.py`, `unpack_corpus.py`,
`nominator_report.py`, `party_lineage_report.py`, `tracked_fixtures.py`,
`pii_inventory.py`, `serve_dashboard.py`.

**Per-election steps**, run for a new election: `backfill_url_portraits.py`,
`refetch_campaign_subtabs.py` (campaign sub-tabs an interrupted scrape left
behind).

**Reports**: `constituency_report.py`, `build_place_vocabulary.py`,
`find_identity_merge_candidates.py`.

**Spent one-offs.** Each did a job the parsers now do and changes nothing
today; each says so at the top of its docstring.

| script | what it did |
|---|---|
| `backfill_provenance.py` | stamped `provenance` onto older records |
| `backfill_conviction_details.py` | `anketa.teistumo-detales` for six elections |
| `backfill_1997_card_fields.py` | four 1996–1998 card fields |
| `backfill_archive_birthplaces.py` | birthplaces from 1996–1997 prose |
| `backfill_archive_declarations.py` | the archive `kpdl.htm` declarations |
| `backfill_value_hygiene.py` | value rules for records without a retained page |
| `renormalize_declarations.py` | the declaration block from `rawData` |
| `reshape_1997_education.py` | `issilavinimas` into the corpus shape |

## Helpful Checks

```bash
python -m scraper --help
python -m scraper parse-anketa-samples --help
python scripts/reparse_diff.py          # the corpus still matches the parsers
python scripts/nominator_report.py      # every record still resolves and joins a nominator
python scripts/party_lineage_report.py  # every continuity pair is linked or reviewed
pytest tests/
```
