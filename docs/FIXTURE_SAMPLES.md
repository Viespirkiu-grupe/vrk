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

## Other elections

Each election folder keeps its own small, test-protected fixture set under
`samples/html/<election_id>/` with the same policy. For `2019-ep` the allowlist
(`tests/test_ep_2019_sample_allowlist.py`) is:

- `daiva-adutaviciene`
- `petras-austrevicius`
- `andrius-kubilius`
- `ausra-maldeikiene`
- `liudas-mazylis`
- `laima-liucija-andrikiene`

This mix covers a non-elected candidate, returning MEPs with prior-mandate and
education record tables, candidates with campaign donation data, and a candidate
holding an academic degree / pedagogic title (guards the `9.x` and `12.x`
question-number parsing that would otherwise silently drop those answers).

For `2024-ep` the allowlist (`tests/test_ep_2024_sample_allowlist.py`) is:

- `vitalijus-mitrofanovas`
- `edvinas-guobys`
- `zivile-pinskuviene`
- `tomas-baranauskas`
- `vilija-blinkeviciute`
- `petras-grazulis`

This mix covers an elected MEP (elected note in the profile), a candidate with
an academic degree (guards the 2024 `2.1`/`2.2` biography numbering), a
candidate with conviction and mandate-loss details (`13.1`-`13.4` and `14.1`
conditional answers), an extra private-interest section (`Ryšiai sudarius
sandorius`), and regular non-elected candidates.

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
