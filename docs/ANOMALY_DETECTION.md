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
baseline in the same commit — up to a point. An election whose total fell to
less than half of what the baseline records exits 1 too, because that is what
a wiped file looks like: issue #139 measured a one-candidate re-parse taking
the 1997 municipal election from 8,636 events to 8, and the report printing
`3 row(s) below the baseline` followed by `Nothing new against the baseline`.
A parser fix that removes most of an election's events is a deliberate change
and updates the baseline in the same commit (`--update-baseline`).

The baseline keys on `(election, event type, severity)`. Reclassifying an event
is a real change to what stops an unattended run, so it shows up as a resolved
row and a new one rather than passing as "the same 8,597 events".

## What the corpus does not hold

The report also reconciles every `sitemaps/<id>.json` against `data/<id>/`,
because a candidate the corpus never got leaves no event of its own to read
(issue #158). Nine candidates across four elections have no record —
2000-kovo-19 2 of 9,881, 2002-gruodzio-22 1 of 10,139, 2007-vasario-25 3 of
13,422, 2011-vasario-27 3 of 16,403 — every one a VRK 404, and all four
gates passed with them absent.

`scripts/run_election_batches.sh`'s `final_report` does diff the two, but
only during a scrape and into a `.run-state/` directory that is gitignored;
`docs/DATASET.md` pointed at those files for the explanation of each group,
and only one of the four survived on the scraping machine — the rest died
with the worktrees those scrapes ran in. So the nine now carry a
`CandidateFetchFailed` event in their election's own `anomalies.jsonl`, which
is what the runner writes for a candidate it could not get, and the
reconciliation is a standing check: **a gap with such an event against it is
recorded and explained; a gap with none exits 1**, whether or not there is a
baseline, because it is about what the corpus holds rather than about what
changed.

Two things made those gaps easy to miss, and both are closed.
`fetch-candidate-samples` returned 0 whatever it recorded — driven with every
tab answering 503 it produced six `TabDownloadFailed` and one
`TabDownloadPartial`, all `severity: error`, and exited 0, so the batch
runner's `if ! fetch_candidate` never fired, the id went into `done_ids.txt`
and the run reported "complete". It exits 1 on an error-severity event now,
which is what a transient outage should mean: the candidate stays pending. And
`final_report` no longer prints "complete" while an error-severity `fetch`
event stands against the election, because a record on disk is not the same
as a complete fetch — a candidate whose anketa landed and whose tabs all
failed has one.

## Who writes the file

`data/<election-id>/anomalies.jsonl` has several writers, and one rule holds
them together (`scraper/shared/anomalies.py`, issue #139): **a run owns the
events of its own stage for the candidates it processed, replaces exactly
those, and leaves every other line as it found it.**

- `parse-anketa-samples` defaults to the election's file and applies the rule
  per candidate: re-parsing one candidate replaces that candidate's `parse`
  events and nothing else. Until issue #139 it opened the file with `"w"` and
  wrote its own run alone, so the documented one-candidate form emptied the
  file — including the `fetch`-stage `PortraitFetchFailed` rows that no
  re-parse can regenerate.
- `scripts/reparse_diff.py --apply` re-parses a whole election and applies the
  same rule with every candidate owned: all `parse` events are regenerated,
  every other stage's are kept.
- `scripts/run_election_batches.sh` points both stages at a fresh per-candidate
  file and appends it to the election's, which is the rule's append form.
- `fetch-candidate-samples` has no default path and writes the file it is
  given whole; the runner's per-candidate file is the only one it should be
  pointed at.
- `scripts/backfill_url_portraits.py` owns the `PortraitFetchFailed` rows and
  replaces them by event type on every run.

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

Until 2026-09-02 every event in the corpus was a `parse` event. That was not
because fetching never failed: until issue #85 the fetch command computed its
events, printed a count and dropped them — `--anomalies-path` existed only on
the parse subparser, and the batch runner sent the fetch command's output to
`/dev/null`. The plumbing exists now; the corpus's record of past page
fetches does not, and cannot be recovered. The first `fetch`-stage events in
the corpus are the `PortraitFetchFailed` rows `scripts/backfill_url_portraits.py`
writes (issue #118): one per candidate whose portrait URL answered anything
but an image, replaced on every run of the script so that a retry which
succeeds clears the row and one which fails again does not double it.
`scripts/reparse_diff.py --apply` regenerates an election's `parse`-stage
events from the re-parse and keeps every other stage's as they are.

## Severities

| severity | meaning | in the corpus |
| --- | --- | --- |
| `critical` | the page's structure was not found at all | 0 (41 call sites) |
| `error` | a page was lost — unreadable, or never fetched | 12 |
| `warning` | a page was doubted — present, and contradicting itself or missing a field | 417 |
| `info` | the source has already said this is its own fault | 8,598 |

`info` exists so that `STOP_ON_ANOMALY=1` is usable. 8,598 of the corpus's
9,027 events are one archive declaration page type whose totals contradict its
own rows *below VRK's own "Klaida užklausoje" banner* — the source printed, in
so many words, that its query failed. At `warning` those drowned the other 429
events completely and stopped every archive run on its first batch.
`scripts/run_election_batches.sh` counts only events above `info`.

## The eleven types that fire

Measured over all 55 elections on 2026-09-10 (the `ElectedCandidacyMismatch`
row 2026-08-31 with issue #92's join, `PortraitFetchFailed` 2026-09-03 with
issue #118's portrait archive, `CandidateFetchFailed` 2026-09-09 with issue
#158's sitemap reconciliation). Twenty-three event types are emitted from
`build_anomaly_event` call sites in the parsers; these eleven are the ones the
corpus has ever recorded, and the counts below sum to its 9,027 events.

| count | type | severity | what it means |
| --- | --- | --- | --- |
| 8,598 | `DeclarationTotalBelowItsOwnRow` | `info` | An archive declaration whose row-20 total is below its own row 1, on a page carrying VRK's query-error banner. The total is refused rather than published, so the record has `null` and not a false zero. |
| 327 | `DeclarationTotalBelowItsOwnRow` | `warning` | The same contradiction on a page that printed no banner. A readable page contradicting itself is a finding. |
| 9 | `CandidateFetchFailed` | `error` | A candidate the election's sitemap lists and the corpus holds no record for: nine across four elections, every one a page VRK never published (issue #158 reconciled them, and `scraper/shared/anomaly_report.py` fails the report for any gap without one of these against it). |
| 38 | `PortraitFetchFailed` | `warning` | A candidate's portrait URL that answered anything but an image when `scripts/backfill_url_portraits.py` fetched it — the corpus's only `fetch`-stage events. 32 (2000 Seimas) and 5 (2005 Kėdainiai) point at lrs.lt hosts that answer 520 and 503; one 2020 Seimas image is a 404 on vrk.lt itself. The record keeps the URL with a `photoMeta` naming the error. |
| 31 | `ElectedCandidacyMismatch` | `warning` | A 1997 municipal winner whose elected-page list position disagrees with the card's own (a renumbering after withdrawals; the join keys on VRK's candidate id, so electedness is unaffected). |
| 11 | `ResidenceMissing` | `warning` | A 1996–2000 card with no residence line. |
| 3 | `DeclarationPageUnreadable` | `error` | A declaration page with no figures on it at all. |
| 3 | `DeclarationSectionMissing` | `warning` | The 2002 municipal page published the declaration table as an empty cell. |
| 2 | `ElectedNoteMismatch` | `warning` | The 2000 Seimas card's own winner note disagrees with the members page. |
| 2 | `AnketaNotPublished` | `warning` | The candidate's questionnaire page is a placeholder. Upstream, not a parse failure. |
| 2 | `CampaignRootMissing` | `warning` | A campaign the candidate page linked whose root never fetched. The record simply has no campaign section. |
| 1 | `BirthDateMissing` | `warning` | A 2002 municipal card with no birth date. |

The other twelve are the structural checks — `TabnavSelectorNotFound`,
`AnketaTableNotFound`, `AnketaTableEmpty`, `TabDownloadFailed`,
`CampaignTabSampleMissing` and the rest. They have never fired against a real
page, and four of them are what an earlier version of this file named as its
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
