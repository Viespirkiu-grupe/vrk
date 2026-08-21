# Anomaly Detection

The parser emits anomaly events for structural or data-shape problems discovered during fetch and parse flows.

Core implementation:

- `scraper/shared/anomalies.py`

## Event shape

Each anomaly event is a JSON object with:

- `timestamp`
- `eventType`
- `severity`
- `stage`
- `electionId`
- `candidateId`
- `sourceUrl`
- `detail`

## Output format

Events are written as JSON Lines (`.jsonl`):

- one JSON object per line
- UTF-8 text file

Default parser output path:

- `data/2016-seimo/anomalies.jsonl`

`parse-anketa-samples` accepts override:

- `--anomalies-path <path>`

## Typical stages

- `fetch`: sample collection and linked page downloads
- parser stages from election module functions

## Typical severities

- `error`: failed fetches or hard-structure failures
- `warning`: suspicious or incomplete structures
- `info`: non-breaking trace-like signals when used

## Example event types covered by tests

- `TabnavSelectorNotFound`
- `AnketaTableNotFound`
- `AnketaTableEmpty`
- `CampaignRootMissing` — a campaign the candidate page linked whose root
  page never fetched (the fetch stage left a `CampaignRootFetchFailed` in
  the candidate's `index.json` and an empty campaign directory). A
  parse-stage warning, so a dead campaign link reaches `anomalies.jsonl`
  instead of only the per-candidate index; the record simply has no
  campaign section. Two 2009 EP candidates are the corpus's cases.
- `CampaignTabSampleMissing` — a campaign tab file listed in `index.json` is
  missing or unreadable at parse time. Recorded paths are re-anchored onto the
  samples root in use, so this fires only when the file is genuinely absent
  from the tree being parsed — absent inputs can no longer produce silently
  empty campaign sections.

Reference tests:

- `tests/test_seimo_2016_anomaly_detection.py`
- `tests/test_campaign_sample_path_resolution.py`

## Batch script integration

`scripts/run_election_batches.sh <election-id>` parses candidates in batches, appends per-candidate anomaly files into:

- `data/<election-id>/anomalies.jsonl`

With `STOP_ON_ANOMALY=1` the script stops with exit code 2 when a batch
introduces new anomalies; by default it records them and keeps going, so an
unattended full run is reviewed from the anomalies file afterwards.
