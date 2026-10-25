# Adding an Election Module

Every election gets its own module, because VRK's page layouts differ by year
and election type. Conventions:

- Plain `requests` + `beautifulsoup4`, no browser automation.
- One JSON file per (candidate, election): `data/<id>/<candidate_id>-<id>.json`.
- Parser work is fixture-driven: save the HTML, then parse the saved copy.
- Changing one election's module does not change another's. Code a page family
  shares lives once in `scraper/shared/`.

## 1. Identify the election

Fetch the wrapper page and read its title for the official name and date:

```bash
curl -sS -L "<listing URL>" | grep -oE "[^<>]{0,140}(20[0-9]{2} m\.)[^<>]{0,140}"
```

Ids follow date and scope (`2023-spalio-8-kupiskio-mero`, `2021-spalio-10-meru`);
package names mirror them (`kupiskio_mero_2023`, `meru_2021`). Section 5 has the
id rule for `scraper/elections.json`.

## 2. Find which existing module the pages match

This is the whole job. Fetch one candidate page and run existing parsers against
it before writing anything. The layout families:

- **2002–2005 static site** (`ep_2004`): a profile card over one `r1`/`r2` row
  per question (`N. Prompt: <b>answer</b>`), separate `kand_biog_l_` and
  `kand_pajam_l_` pages instead of tabs, no interest declaration, no campaign
  page. Members:
  - `seimo_2004`: `ep_2004`'s readers with the Seimas question mapping and a
    two-structure listing walk (lists and constituencies);
    `seimo_kedainiu_2005` is thin wiring over it.
  - `seimo_nauji_2003`: one site generation earlier. Reuses the row reader, the
    Seimas mapping and `savivaldybiu_2002`'s declaration key map. Its deltas
    are worth checking in any new family member: a card inside the question
    table, a moved question number, and record tables with no header row.
  - `prezidento_2004`: one shared listing of five profile cards; biography and
    programme as Word 97 `.doc` (`scraper/shared/word_doc.py`, `fetch_bytes`);
    birth facts from the biography prose; its own two-round results walk.
  - `prezidento_2002`: the 2002 template, same shared-listing shape. The
    questionnaire, declaration and statement exist only as scans, archived as
    bytes in `rawData.skenai` and never OCR'd.
- **2000 archive** (`seimo_2000`): the 1996–1998 Teleport archive template
  (`kandvl.htm-<ID>.htm`) carrying the 2004 content in one document. Listing
  is the 2004 Seimas two-structure walk
  (`seimo_2004.sitemap.merge_listing_records`); declarations use the 1990s
  parser. `savivaldybiu_2000` is the municipal form on the 1997 municipal
  archive's three-hop listing (municipality → list → candidate).
- **1996–1999 archive**: `scraper/shared/seimo_archive_1990s.py` and
  `scraper/shared/savivaldybiu_archive_1997.py`, the same template without the
  questionnaire.
- **2007–2015 static layout** (`seimo_zirmunu_2015`): tabs as separate static
  files, no elected marker. See *If the election has more than one listing
  structure* for its municipal walkers.
- **2016 era** (`seimo_2016`): one anketa table with the whole Q5–Q21 set,
  elected note in the name cell, base64 photos, GPM308 income labels, `ID001x`
  private-interest sections.
- **2017 mayoral** (`meru_2017`): the 2016 anketa narrowed to five
  declarations, free-text biography. `savivaldybiu_2019` belongs here, not
  with 2023; only its income aliases are restated.
- **2019 EP era** (`ep_2019`): anketa split across sibling tables, question
  numbers sometimes without the trailing dot.
- **2020 era** (`seimo_2020`): Q6.x contacts, Q7.x position and membership.
- **2023 mayoral** (`kupiskio_mero_2023`): tab bodies in their own `<div>`,
  nationality as biography Q2. `savivaldybiu_2023` and `visagino_mero_2023`
  reuse it unchanged.
- **2024 era** (`ep_2024`, `seimo_2024`, `prezidento_2024`): tab bodies are
  siblings of the tab navigation, Q8 membership table, Rinkimų kodekso
  declarations.

Import the matching module's parsers rather than restating them
(`marijampoles_mero_2017` is thin wiring over `meru_2017`).

**Where a shared helper lives.** Layout logic for one election (its question
mapping, a reader only its pages need) stays in its module. A helper a page
family shares lives in `scraper/shared/` under a public name. For the 2016-on
tabbed pages that is `scraper/shared/anketa_tabs.py`. Import from there, not
from another election's module; `tests/test_anketa_tabs.py` enforces it.

## 3. Build the module

Three files, mirroring the closest existing election:

- `sitemap.py`: listing URL, `ELECTION_ID`, candidate-row selection. Watch for
  candidate tables with no id, or a first cell that links elsewhere.
- `candidate_samples.py`: `EXPECTED_TABS`. Tab slugs vary, and the campaign tab
  is absent for some elections and candidates. A tab the pages link but VRK
  never published goes in the 2015-era fetcher's `unpublished_tabs`
  (`prezidento_2009`'s `UNPUBLISHED_TABS`): recorded in `index.json`, neither
  fetched nor reported missing.
- `anketa_parser.py`: the question-to-key mapping, reusing shared helpers.

Then wire it into `scraper/cli.py`, **ten edit sites**:

- three imports (`sitemap`, `candidate_samples`, `anketa_parser`);
- two id lists: `FETCHABLE_ELECTION_IDS` and `PARSABLE_ELECTION_IDS`, plus
  `RESULTS_ELECTION_IDS` when the elected flag comes from a results tree;
- five `if election_id == …` branches, one per command: `fetch-sample`,
  `sitemap`, `fetch-first-candidate-samples`, `fetch-candidate-samples`,
  `parse-anketa-samples`.

`tests/test_cli_dispatch.py` checks all of them.

### If the election has more than one listing structure

Municipal general elections list mayoral candidates on one page and council
candidates under an index of party lists; neither set contains the other.

For 2019 and 2023 this is shared machinery in
`scraper/shared/municipal_sitemap.py`. `savivaldybiu_2019` and
`savivaldybiu_2023` are config plus wrappers: election id, listing URLs, paths,
and the regex marking a dual candidacy. A third such election adds a config
module, not a copy. Rules:

- Merge the structures on VRK's candidate id, never on name.
- Reconcile the merged total against VRK's summary page
  (`savKandidataiSuvestine.html`): row counts, per-structure counts, overlap.
- Carry listing-only facts (municipality, list, seat order, elected flag) into
  the record's `kandidatavimas` block.
- Name slugs collide at this scale, so ids get a stable VRK-id suffix, not a
  positional `-2`.
- `EXPECTED_TABS` can depend on the role: only mayoral candidates publish a
  campaign tab.

The candidate pages are not shared: `savivaldybiu_2019` reuses `meru_2017`,
`savivaldybiu_2023` reuses `kupiskio_mero_2023`.

The 2007–2015 municipal listings have their own walker in
`pakartotiniai_sirvintu_traku_2015/sitemap.py`, driven by `savivaldybiu_2015`.
Read the district-page rows before reusing it: in 2015 a direct candidate link
is a mayoral candidate, in 2011 a self-nominated council candidate, so
`savivaldybiu_2011` reads those rows itself. `savivaldybiu_2007` is the same
walk under older file names. Cross-check against VRK's roll-up pages
(`KandidataiMerai.html`, `KandidataiIssikele.html`, by-party pages).

## 4. Verify against the whole field

```bash
python -m scraper fetch-sample <id> && python -m scraper sitemap <id>
python -m scraper fetch-candidate-samples <id> --allow-new-samples --candidate-id ...
python -m scraper parse-anketa-samples <id>
```

Read the output for every fixture candidate. Anything null or empty is a
question: trace it to the page and confirm the source is blank.

### If the pages mark no winner

No static layout from 1996 to 2015 marks a winner. Electedness is a separate
join:

1. A `results.py` in the module configures which results tree to walk. Walkers
   live in `scraper/shared/election_results.py`,
   `scraper/shared/seimo_archive_1990s_results.py` and
   `scraper/shared/savivaldybiu_archive_1997_results.py`.
2. `python -m scraper build-results <id>` writes `sitemaps/<id>.results.json`.
3. The parser joins it into `kandidatavimas.isrinktas`.

Read the reconciliation stats: every winner resolves to a sitemap candidate id,
and seat counts match VRK's, or the difference is a named annulment.

`null` means the results were never read; `false` means they were and this
candidate did not win.

## 5. Tests and docs

- `tests/test_<module>_anketa_parser.py`: pin key lists, elected-note forms,
  record tables, anything election-specific. Mutate the parser and check they
  fail.
- `tests/test_<module>_sample_allowlist.py`: the fixture set.
- `python scripts/tracked_fixtures.py --sync`: the only way a new fixture
  reaches git. It tracks every unit up to 1 MiB; `tests/test_tracked_fixtures.py`
  fails if the new election has no candidate small enough.
- `docs/CLI_REFERENCE.md`, `docs/FIXTURE_SAMPLES.md`, `docs/OUTPUT_SCHEMA.md`.
- `docs/concept-map.json`: every concept the election publishes, its path, and
  a `verified` sentence saying what you measured it against.
  `tests/test_field_coverage.py` fails on a mapped cell without a fill rate.
- **Nominators and parties.** The `iskele` entry in `docs/concept-map.json` is
  the ordered path list `scraper/shared/nominator.py` resolves through. Every
  non-presidential record must resolve (`tests/test_corpus_nominators.py`).
  `python scripts/nominator_report.py --update` writes new forms to
  `docs/nominator-forms.tsv` and unclaimed ones to `scraper/parties.json`'s
  `unmatched` block, which `tests/test_party_registry.py` keeps empty. Add
  each form as an alias (rename, glyph variant, new legal form) or a new
  entry; an organisation that continues another lists it under
  `predecessors`. After `build_person_index.py`,
  `python scripts/party_lineage_report.py` fails on carried-over nominators
  the registry neither links nor lists under `reviewedDistinct`.
- **`scraper/elections.json`**: id, first-round date, kind, official name,
  short label, and `parent` unless it is a general election.
  `tests/test_elections_registry.py` enforces:
  - `id`: `YYYY-<kind>` for a general election (`2028-seimo`), otherwise
    `YYYY-<menuo>-<D>-<kind>[-<vieta>...]` (`2026-kovo-15-seimo-zirmunai`):
    ASCII, genitive month, no leading zero, kind spelled as the `kind` field.
    Existing ids are frozen.
  - `name`: VRK's heading form: date in words (`2026 m. kovo 15 d.`), then
    `nauji` or `pakartotiniai` unless general, then the body phrase
    (`Lietuvos Respublikos Seimo rinkimai`, `savivaldybių tarybų rinkimai`,
    `Respublikos Prezidento rinkimai`, `Europos Parlamento rinkimai`,
    `<Vieta> savivaldybės mero rinkimai`), then for a Seimas by-election its
    constituencies (`Žirmūnų apygardoje Nr. 4`).
  - `shortName`: `YYYY <Institucija>` for a general election, `YYYY-MM
    <Institucija>` otherwise (Seimas, Savivaldybės, Prezidentas, EP, Merai),
    with the day only if another non-general label shares the month.
  - `parent`: the latest earlier general of the same family whose term it
    fills; mayoral races group under the municipal general.
- **Counts a new election moves.** Expect these to fail when the entry lands
  and again after the scrape, and update them in order:
  - `tests/test_elections_registry.py`;
  - `tests/test_cli_dispatch.py`;
  - `tests/test_doc_counts.py`: the README/DATA_GUIDE headline, the
    CLI_REFERENCE id list, FIXTURE_SAMPLES, the DATASET inventory row;
  - `tests/test_record_shape.py`: root key-sets, distinct-key count, section
    order;
  - `tests/test_doc_numbers.py`: storage, litas, anomaly and candidacy figures;
  - `tests/fixture-record-hashes.tsv`: `python scripts/fixture_record_hashes.py --update`.

  And the four baselines: `docs/coverage-baseline.tsv`
  (`field_coverage.py --update-baseline`), `docs/candidacy-baseline.tsv`
  (`build_candidacy_table.py --update-baseline`), `docs/anomaly-baseline.tsv`
  (`anomalies-report --update-baseline`), `docs/plausibility-register.tsv`
  (`value_plausibility.py --update`).

## 6. Full scrape

1. Scrape. `STOP_ON_ANOMALY=1` stops after a batch with anything above `info`;
   use it on a first run.

   ```bash
   scripts/run_election_batches.sh <election-id>
   ```

   HTML is retained under `samples-full/<election-id>/`, so later parser fixes
   are offline re-parses. `KEEP_SAMPLES=0` deletes it as it parses. The runner
   builds the results file first where needed, and reports "complete" only
   when every sitemap id has a record.
2. Archive linked portraits and turn them into `photos/` sidecars
   (`scripts/run_all_elections.sh` does this itself):

   ```bash
   python scripts/backfill_url_portraits.py <election-id>
   python scripts/reparse_diff.py --full --jobs 8 --apply <election-id>
   ```

   An unfetchable URL becomes a `PortraitFetchFailed` anomaly.
3. Rebuild the person index, then the web portraits:

   ```bash
   python scripts/build_person_index.py
   python scripts/build_web_portraits.py
   ```

   The portrait build is incremental and re-stamps `ph` and the portrait
   version in `dashboard/people-list.json`. Re-run it after anything that
   rewrites `photos/`. `build_distribution.py` refuses to run without a
   matching `portraits/`.

## 7. Before you open the PR

```bash
python scripts/field_coverage.py                     # the gate, before the baseline moves
python scripts/field_coverage.py --update-baseline   # then classify what it lists, and paste your rows
python scripts/nominator_report.py --update          # forms table + registry unmatched
python scripts/party_lineage_report.py               # nominator lineage vs the rebuilt index
python -m scraper anomalies-report <election-id>
python scripts/backfill_url_portraits.py --dry-run <election-id>   # 0 to fetch, or step 6 was skipped
python scripts/reparse_diff.py
python scripts/field_coverage.py                     # last: no findings
```

1. **Run the gate plain first.** It names every concept the closest mapped
   election of the same kind maps and yours does not (map it, or add a
   `not-mapped` row to `docs/coverage-baseline.tsv` saying why), and fails if
   your election is mapped nowhere.
2. **Then `--update-baseline`.** It adds your rows and exits 1 listing cells
   it wrote `unexplained`. Classify each by editing its status
   (`upstream-absent`, `parser-gap`, `empty-is-the-answer` for a zero;
   `partly-published`, `partly-answered` for a low cell) and writing the note.
3. **Paste your fill rates into the PR body:**

   ```bash
   awk -F'\t' '$2 == "<election-id>"' data/coverage.tsv
   ```

   See [FIELD_COVERAGE.md](FIELD_COVERAGE.md).
4. **Read the anomalies back.** A type `docs/anomaly-baseline.tsv` does not
   name exits 1; `--update-baseline` adds rows, each an assertion that it is
   expected. See [ANOMALY_DETECTION.md](ANOMALY_DETECTION.md).
5. **Leave the corpus equal to the parsers:** `reparse_diff.py` exits 0.

## 8. Changing a parser that already has a corpus

A parser fix does not reach `data/` by itself. **A parser change is not done
until the gate is green, or the elections it touches are regenerated.**

```bash
python scripts/reparse_diff.py                       # every election
python scripts/reparse_diff.py --full --jobs 8 <id>  # what exactly changed
python scripts/reparse_diff.py --full --jobs 8 --apply <id>
```

Read the path histogram before applying: it shows the change you meant and
sometimes one you did not. `--apply` regenerates from retained HTML, writing
only records that differ.

An election with no retained HTML needs a `scripts/` backfill from `rawData`
(`scripts/renormalize_declarations.py` is the example) or a re-scrape.
