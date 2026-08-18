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

Reference tests:

- `tests/test_seimo_2016_anomaly_detection.py`

## Batch script integration

`scripts/run_seimo_2016_batches.sh` parses candidates in batches, appends per-candidate anomaly files into:

- `data/2016-seimo/anomalies.jsonl`

The script stops with exit code 2 when a batch introduces new anomalies.
