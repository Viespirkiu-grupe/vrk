# Anomaly detection

Parsers and fetchers emit **anomaly events**, one JSON object per problem, into
`data/<election-id>/anomalies.jsonl`. They tell an election that went wrong
from one whose source was already broken.

- `scraper/shared/anomalies.py` writes the events.
- `scraper/shared/anomaly_report.py` reads them back and diffs the baseline.

## Reading them

```bash
python -m scraper anomalies-report                    # every election, against the baseline
python -m scraper anomalies-report 2020-seimo         # one election
python -m scraper anomalies-report --errors-only      # a page lost, not a page doubted
python -m scraper anomalies-report --update-baseline  # after a deliberate change
```

The report prints counts per event type per election, worst severity first,
then diffs against `docs/anomaly-baseline.tsv`, keyed on
`(election, event type, severity)`. It exits 1 when:

- an event type is new, or more frequent than the baseline;
- an election's total fell below half the baseline (what a wiped file looks
  like);
- a candidate in `sitemaps/<id>.json` has no record in `data/<id>/` and no
  `CandidateFetchFailed` event against it.

Fewer events otherwise is progress and does not fail. A fix that removes most
of an election's events updates the baseline in the same commit.

## Who writes the file

Rule: **a run owns the events of its own stage for the candidates it
processed, replaces exactly those, and leaves every other line alone.**

- `parse-anketa-samples` replaces the `parse` events of the candidates it
  parsed.
- `scripts/reparse_diff.py --apply` regenerates all `parse` events of an
  election and keeps every other stage's.
- `scripts/run_election_batches.sh` writes both stages to a per-candidate file
  and appends it to the election's.
- `fetch-candidate-samples` has no default path and writes the file it is
  given whole; point it only at the runner's per-candidate file. It exits 1 on
  an error-severity event, so the candidate stays pending.
- `scripts/backfill_url_portraits.py` replaces the `PortraitFetchFailed` rows
  on every run.

## Event shape

```json
{
  "timestamp": "2026-08-28T21:02:48+00:00",
  "eventType": "DeclarationTotalBelowItsOwnRow",
  "severity": "info",
  "stage": "parse",
  "electionId": "1997-kovo-23-savivaldybiu-tarybu",
  "candidateId": "abariunas-bronius",
  "sourceUrl": "https://www.vrk.lt/.../kpdl.htm-19288.htm",
  "detail": {"column": "gautos-pajamos", "row20Total": 0, "row1Employment": 2589,
             "queryErrorBanner": true}
}
```

JSON Lines, UTF-8. `detail` is free-form and holds the measurement behind the
event.

## Stages

- **`fetch`**: sample collection and linked downloads. A failed tab means a
  missing record section. Past page fetches were never recorded; the corpus's
  `fetch` events are the `PortraitFetchFailed` and `CandidateFetchFailed` rows.
- **`parse`**: everything the parsers find in a page they already have.

## Severities

| severity | meaning | in the corpus |
| --- | --- | --- |
| `critical` | the page's structure was not found at all | 0 (41 call sites) |
| `error` | a page was lost — unreadable, or never fetched | 12 |
| `warning` | a page was doubted — present, and contradicting itself or missing a field | 417 |
| `info` | the source has already said this is its own fault | 8,598 |

`info` keeps `STOP_ON_ANOMALY=1` usable: almost all of it is one archive
declaration page whose totals contradict its rows below VRK's own "Klaida
užklausoje" banner. `scripts/run_election_batches.sh` counts only events above
`info`.

## The eleven types that fire

Twenty-three types are emitted in code; these eleven are the ones the corpus
holds, summing to its 9,027 events.

| count | type | severity | what it means |
| --- | --- | --- | --- |
| 8,598 | `DeclarationTotalBelowItsOwnRow` | `info` | An archive declaration whose row-20 total is below its own row 1, on a page carrying VRK's query-error banner. The total is stored as `null`, not a false zero. |
| 327 | `DeclarationTotalBelowItsOwnRow` | `warning` | The same contradiction on a page with no banner. |
| 9 | `CandidateFetchFailed` | `error` | A sitemap candidate with no record: nine across four municipal generals, every one a VRK 404. |
| 38 | `PortraitFetchFailed` | `warning` | A portrait URL that answered anything but an image. The record keeps the URL with a `photoMeta` naming the error. |
| 31 | `ElectedCandidacyMismatch` | `warning` | A 1997 municipal winner whose elected-page list position disagrees with the card's. Electedness joins on VRK's id, so it is unaffected. |
| 11 | `ResidenceMissing` | `warning` | A 1996–2000 card with no residence line. |
| 3 | `DeclarationPageUnreadable` | `error` | A declaration page with no figures at all. |
| 3 | `DeclarationSectionMissing` | `warning` | The 2002 municipal page published the declaration table as an empty cell. |
| 2 | `ElectedNoteMismatch` | `warning` | The 2000 Seimas card's winner note disagrees with the members page. |
| 2 | `AnketaNotPublished` | `warning` | The questionnaire page is a placeholder upstream. |
| 2 | `CampaignRootMissing` | `warning` | A linked campaign whose root never fetched; the record has no campaign section. |
| 1 | `BirthDateMissing` | `warning` | A 2002 municipal card with no birth date. |

The other twelve (`TabnavSelectorNotFound`, `AnketaTableNotFound`,
`AnketaTableEmpty`, `TabDownloadFailed`, `CampaignTabSampleMissing`, …) are
structural tripwires that have never fired on a real page.

## Batch runs

`scripts/run_election_batches.sh <election-id>` appends both stages' events to
the election's file. With `STOP_ON_ANOMALY=1` it exits 2 after a batch with an
event above `info`; by default it keeps going, and the run is reviewed with
`anomalies-report`.

## Tests

- `tests/test_anomaly_report.py`: reading back, the baseline diff, `--anomalies-path`
- `tests/test_deklaracija_archive_1990s.py`: the `info`/`warning` split
- `tests/test_seimo_2016_anomaly_detection.py`: structural checks on a broken fixture
- `tests/test_campaign_sample_path_resolution.py`: `CampaignTabSampleMissing`
