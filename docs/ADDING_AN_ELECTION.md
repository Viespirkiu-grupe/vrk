# Adding an Election Module

Every election gets its own module because VRK's page layouts differ by year and
election type. This is the route from a VRK listing URL to a scraped election,
distilled from the modules that exist.

## 1. Identify the election

Fetch the wrapper page and read its title — it gives the official name and date:

```bash
curl -sS -L "<listing URL>" | grep -oE "[^<>]{0,140}(20[0-9]{2} m\.)[^<>]{0,140}"
```

Election ids follow the date and scope, e.g. `2023-spalio-8-kupiskio-mero`,
`2021-spalio-10-meru`, `2017-balandzio-23-seimo-anyksciai-panevezys`. Package
names mirror them: `kupiskio_mero_2023`, `meru_2021`, `seimo_anyksciu_panevezio_2017`.

## 2. Find which existing module the pages match

This is the whole job. Fetch one candidate page and run existing parsers against
it before writing anything. The layout families are:

- **2016 era** (`seimo_2016`): one anketa table with the whole Q5–Q21 set,
  elected note inside the name cell, base64 photos, GPM308 income labels,
  `ID001x` private-interest sections.
- **2019 EP era** (`ep_2019`): anketa split across sibling tables with standalone
  record tables between them, question numbers sometimes lacking the trailing dot.
- **2020 era** (`seimo_2020`): Q6.x contacts, Q7.x position and membership.
- **2023 mayoral** (`kupiskio_mero_2023`): tab bodies wrapped in their own
  `<div>`, biography numbering with nationality as Q2.
- **2024 era** (`ep_2024`, `seimo_2024`, `prezidento_2024`): tab bodies are
  siblings of the tab navigation, Q8 membership table, Rinkimų kodekso
  declarations.

Import the matching module's parsers rather than restating them. Several modules
are thin wiring over another era's parsers — `marijampoles_mero_2017` over
`meru_2017`, `radviliskio_mero_2021` over `meru_2021`.

## 3. Build the module

Three files, mirroring the closest existing election:

- `sitemap.py` — listing URL, `ELECTION_ID`, candidate-row selection. Watch for
  listings whose candidate table has no id, or whose first cell links somewhere
  other than the candidate.
- `candidate_samples.py` — `EXPECTED_TABS` for this election. Tab slugs vary
  (`privaciu-interesu-deklaracija` vs `...deklaracijos`), and the campaign tab is
  absent for some elections and some candidates.
- `anketa_parser.py` — the question-to-key mapping, reusing shared helpers.

Then wire five dispatch points in `scraper/cli.py`.

## 4. Verify against the whole field before trusting it

```bash
python -m scraper fetch-sample <id> && python -m scraper sitemap <id>
python -m scraper fetch-candidate-samples <id> --allow-new-samples --candidate-id ...
python -m scraper parse-anketa-samples <id>
```

Read the output for every fixture candidate, not just one. Anything null or
empty is a question to answer, not a result to accept: trace it back to the
page and confirm the source is genuinely blank. That habit is what surfaced
every defect listed in `docs/DATASET.md`.

## 5. Tests and docs

- `tests/test_<module>_anketa_parser.py` — pin the key lists, the elected-note
  forms, record tables, and anything election-specific. Mutating the parser
  should make them fail; check that it does.
- `tests/test_<module>_sample_allowlist.py` — the fixture set.
- `docs/CLI_REFERENCE.md`, `docs/FIXTURE_SAMPLES.md`, `docs/OUTPUT_SCHEMA.md`.

## 6. Full scrape

```bash
scripts/run_election_batches.sh <election-id>
```
