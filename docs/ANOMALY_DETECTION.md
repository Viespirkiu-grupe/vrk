# Anomaly detection

Every scrape records what it could not make sense of. The parsers and fetchers
emit **anomaly events** — one JSON object per problem — and the batch runner
appends them to `data/<election-id>/anomalies.jsonl`. This file is the corpus's
account of its own gaps, and reading it is how you tell an election that went
wrong from one whose source was already broken.

Core implementation:

- `scraper/shared/anomalies.py` — the event, and writing the file
- `scraper/shared/anomaly_report.py` — reading it back and diffing the baseline

## Reading them

```bash
python -m scraper anomalies-report                    # every election, against the baseline
python -m scraper anomalies-report 2020-seimo         # one election
python -m scraper anomalies-report --errors-only      # a page lost, not a page doubted
python -m scraper anomalies-report --update-baseline  # after a deliberate change
```

The report prints counts per event type per election, worst severity first, and
then diffs the run against `docs/anomaly-baseline.tsv`. An event type the
baseline does not name, or more of one than it records, exits 1. Fewer is
progress: it is printed and does not fail, so a parser fix need not touch the
baseline in the same commit.

The baseline keys on `(election, event type, severity)`. Reclassifying an event
is a real change to what stops an unattended run, so it shows up as a resolved
row and a new one rather than passing as "the same 8,597 events".

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

JSON Lines, UTF-8, one object per line. `detail` is free-form and is where the
measurement that justifies the event lives.

## Stages

- **`fetch`** — sample collection and linked page downloads. A failed tab
  download means a whole record section will be missing, which is why these are
  recorded at all. Both `fetch-candidate-samples` and `parse-anketa-samples`
  take `--anomalies-path`, and `scripts/run_election_batches.sh` appends both
  into the election's file.
- **`parse`** — everything the parsers find in a page they already have.

Every event now in the corpus is a `parse` event. That is not because fetching
never failed: until issue #85 the fetch command computed its events, printed a
count and dropped them — `--anomalies-path` existed only on the parse
subparser, and the batch runner sent the fetch command's output to
`/dev/null`. The plumbing exists now; the corpus's record of past fetches does
not, and cannot be recovered.

## Severities

| severity | meaning | in the corpus |
| --- | --- | --- |
| `critical` | the page's structure was not found at all | 0 (44 call sites) |
| `error` | a page was lost — unreadable, or never fetched | 3 |
| `warning` | a page was doubted — present, and contradicting itself or missing a field | 348 |
| `info` | the source has already said this is its own fault | 8,598 |

`info` exists so that `STOP_ON_ANOMALY=1` is usable. 8,598 of the corpus's
8,949 events are one archive declaration page type whose totals contradict its
own rows *below VRK's own "Klaida užklausoje" banner* — the source printed, in
so many words, that its query failed. At `warning` those drowned the other 351
events completely and stopped every archive run on its first batch.
`scripts/run_election_batches.sh` counts only events above `info`.

## The eight types that fire

Measured over all 55 elections on 2026-08-29. Forty-one event types are
declared in the code; these eight are the ones the corpus has ever recorded.

| count | type | severity | what it means |
| --- | --- | --- | --- |
| 8,598 | `DeclarationTotalBelowItsOwnRow` | `info` | An archive declaration whose row-20 total is below its own row 1, on a page carrying VRK's query-error banner. The total is refused rather than published, so the record has `null` and not a false zero. |
| 327 | `DeclarationTotalBelowItsOwnRow` | `warning` | The same contradiction on a page that printed no banner. A readable page contradicting itself is a finding. |
| 11 | `ResidenceMissing` | `warning` | A 1996–2000 card with no residence line. |
| 3 | `DeclarationPageUnreadable` | `error` | A declaration page with no figures on it at all. |
| 3 | `DeclarationSectionMissing` | `warning` | The 2002 municipal page published the declaration table as an empty cell. |
| 2 | `ElectedNoteMismatch` | `warning` | The 2000 Seimas card's own winner note disagrees with the members page. |
| 2 | `AnketaNotPublished` | `warning` | The candidate's questionnaire page is a placeholder. Upstream, not a parse failure. |
| 2 | `CampaignRootMissing` | `warning` | A campaign the candidate page linked whose root never fetched. The record simply has no campaign section. |
| 1 | `BirthDateMissing` | `warning` | A 2002 municipal card with no birth date. |

The other 33 are the structural checks — `TabnavSelectorNotFound`,
`AnketaTableNotFound`, `AnketaTableEmpty`, `TabDownloadFailed`,
`CampaignTabSampleMissing` and the rest. They have never fired against a real
page, and four of them are what the previous version of this file named as its
examples. A check that has only ever fired against a synthetic fixture is worth
keeping and is worth knowing about: it is a tripwire, not a finding.

## Batch script integration

`scripts/run_election_batches.sh <election-id>` fetches and parses candidates in
batches, appending both stages' events into `data/<election-id>/anomalies.jsonl`.

With `STOP_ON_ANOMALY=1` it stops with exit code 2 after a batch that recorded
an event above `info`; by default it records them and keeps going, so an
unattended full run is reviewed afterwards with `anomalies-report`.

## Reference tests

- `tests/test_anomaly_report.py` — reading the corpus back, the baseline diff,
  and the fetch stage's `--anomalies-path`
- `tests/test_deklaracija_archive_1990s.py` — where the `info`/`warning` split
  is decided
- `tests/test_seimo_2016_anomaly_detection.py` — the structural checks, against
  a deliberately broken fixture
- `tests/test_campaign_sample_path_resolution.py` — `CampaignTabSampleMissing`

## See also

- [FIELD_COVERAGE.md](FIELD_COVERAGE.md) — the other detector: an anomaly says a
  page went wrong, a fill rate says a field stopped arriving.
