# Fixture Samples Policy (2016 Seimo)

Sample HTML fixtures under `samples/html/2016-seimo/` are intentionally versioned and test-protected.

## Why fixtures are versioned

Fixtures are used for:

- parser development without live network dependence
- regression tests
- reproducible schema and normalization checks

## Current allowlist

The repository enforces exactly these candidate fixture directories:

- `agne-sirinskiene`
- `ingrida-simonyte`
- `regina-ablom`
- `algirdas-butkevicius`
- `gabrielius-landsbergis`

This is enforced by:

- `tests/test_seimo_2016_sample_allowlist.py`

## CLI behavior and guardrail

By default, sample-fetch commands do not allow creating new candidate directories:

- `fetch-first-candidate-samples`
- `fetch-candidate-samples`

To intentionally add a new fixture directory, pass:

- `--allow-new-samples`

## When adding fixtures intentionally

1. Capture new fixture with `--allow-new-samples`.
2. Validate parser output and anomaly behavior.
3. Update allowlist test if fixture set is intentionally changed.
4. Keep fixture set small and representative.

## Recommended baseline checks

```bash
pytest tests/test_seimo_2016_sample_allowlist.py
pytest tests/test_seimo_2016_candidate_samples.py
pytest tests/test_seimo_2016_campaign_parser.py
```
