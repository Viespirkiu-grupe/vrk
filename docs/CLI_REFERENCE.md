# CLI Reference

This project currently exposes one election module through a shared CLI entrypoint.

Run all commands from repository root:

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
- `2023-kovo-5-savivaldybiu-tarybu-ir-meru` (2023-03-05 municipal council and mayoral elections, all 60 municipalities)
- `2019-kovo-3-savivaldybiu-tarybu` (2019-03-03 municipal council elections, all 60 municipalities; mayors were elected as council members)
- `2023-spalio-8-kupiskio-mero` (2023-10-08 early Kupiškis district mayoral election)
- `2023-geguzes-7-visagino-mero` (2023-05-07 repeat Visaginas municipality mayoral vote)
- `2023-rugsejo-3-seimo-raseiniai-kedainiai` (2023-09-03 early Seimo by-election in Raseiniai–Kėdainiai No. 42)
- `2025-kovo-16-meru` (2025-03-16 early mayoral elections in Jonava, Joniškis and Panevėžys)
- `2017-balandzio-23-meru` (2017-04-23 new mayoral elections in Jonava and Šakiai districts)
- `2017-rugsejo-10-marijampoles-mero` (2017-09-10 new Marijampolė municipality mayoral election)
- `2021-spalio-10-meru` (2021-10-10 new mayoral elections in Kelmė and Trakai districts)
- `2021-balandzio-11-radviliskio-mero` (2021-04-11 new Radviliškis district mayoral election)
- `2017-balandzio-23-seimo-anyksciai-panevezys` (2017-04-23 new Seimo by-election in Anykščiai–Panevėžys No. 49)
- `2018-rugsejo-16-seimo-zanavykai` (2018-09-16 new Seimo election in Zanavykai No. 64)
- `2019-rugsejo-8-seimo` (2019-09-08 new Seimo elections in Žirmūnai No. 4, Gargždai No. 31 and Žiemgala No. 46)
- `2015-kovo-1-seimo-zirmunai` (2015-03-01 new Seimo by-election in Žirmūnai No. 4)
- `2015-birzelio-7-seimo-varena-eisiskes` (2015-06-07 new Seimo by-election in Varėna–Eišiškės No. 70)
- `2015-lapkricio-8-telsiu-mero` (2015-11-08 new Telšiai district council member-mayor election)
- `2015-birzelio-7-pakartotiniai-sirvintos-trakai` (2015-06-07 repeat Širvintos member-mayor and Trakai council/mayor elections)
- `2015-birzelio-21-pakartotiniai-silutes` (2015-06-21 repeat Šilutė district council election)
- `2015-kovo-1-savivaldybiu` (2015-03-01 municipal council elections and the first direct mayoral elections, all 60 municipalities)
- `2011-vasario-27-savivaldybiu` (2011-02-27 municipal council elections, all 60 municipalities; the last without a direct mayoral vote)
- `2007-vasario-25-savivaldybiu` (2007-02-25 municipal council elections, all 60 municipalities; party lists only)
- `1996-spalio-20-seimo` (1996-10-20 Seimas general election, 71 single-member constituencies)
- `1997-kovo-23-seimo-pakartotiniai` (1997-03-23 Seimo repeat election in four Vilnius-region constituencies)
- `1997-gruodzio-21-seimo-pakartotiniai` (1997-12-21 Seimo repeat election in Aukštaitijos No. 28)
- `1997-kovo-23-savivaldybiu-tarybu` (1997-03-23 municipal council general election, all 56 municipalities)
- `1997-birzelio-29-svenciniu-tarybos-pakartotiniai` (1997-06-29 Švenčionys district council repeat election)
- `2007-spalio-7-seimo-dzukija` (2007-10-07 Seimo new election in Dzūkijos No. 69)
- `2008-seimo` (2008-10-12 Seimas general election, 16 party lists and 71 single-member constituencies)
- `2009-prezidento` (2009-05-17 presidential election)
- `2009-ep` (2009-06-07 European Parliament election, 15 party lists)
- `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai` (2009-11-15 Seimo new elections in Šilalės–Šilutės No. 33 and Vilniaus–Šalčininkų No. 56)
- `2011-vasario-13-seimo-marijampole` (2011-02-13 Seimo new election in Marijampolės No. 29)
- `2012-seimo` (2012-10-14 Seimas general election, 18 party lists and 71 single-member constituencies)
- `2013-kovo-3-seimo-birzai-zarasai-ukmerge` (2013-03-03 Seimo repeat elections in Biržų–Kupiškio No. 48 and Zarasų–Visagino No. 52 and new election in Ukmergės No. 61)
- `2014-prezidento` (2014-05-11 presidential election)
- `2014-ep` (2014-05-25 European Parliament election)
- `2002-prezidento` (2002-12-22 presidential election, seventeen candidates, runoff 2003-01-05; the 2002 LRS-ITD site — HTML biographies, Word-document programmes, the questionnaire and declarations as scans)
- `2002-gruodzio-22-savivaldybiu-tarybu` (2002-12-22 municipal council general election, all 60 municipalities, party and coalition lists; the 2002 LRS-ITD site — two static pages per candidate)
- `2003-birzelio-15-seimo-nauji` (2003-06-15 new Seimo elections in Senamiesčio No. 2, Antakalnio No. 3, Šeškinės No. 6 and Nevėžio No. 26 — 27 candidates, all four constituencies below the turnout threshold, nobody elected; the 2004 static site one generation early)
- `2004-ep` (2004-06-13 European Parliament election — Lithuania's first, 12 party lists; VRK's original 2004 static site)
- `2004-prezidento` (2004-06-13 presidential election, five candidates, runoff June 27; VRK's original 2004 static site, the biography and programme as Word documents)
- `2004-seimo` (2004-10-10 Seimas general election, 15 party lists and 71 single-member constituencies; VRK's original 2004 static site)
- `2005-lapkricio-20-seimo-kedainiai` (2005-11-20 Seimo new election in Kėdainių No. 43; the 2004 static site one year on)
- `2000-seimo` (2000-10-08 Seimas general election, 15 party lists and 71 single-member constituencies; the 1996-2000 LRS-ITD archive template)
- `2000-kovo-19-savivaldybiu-tarybu` (2000-03-19 municipal council general election, all 60 municipalities, party and coalition lists; the 1997 municipal archive template)

## Election Separation

Each election ID uses its own parser module, HTML samples, sitemap, and output folder.
Running or editing workflows for `2020-seimo` should not require touching `2016-seimo`, and vice versa, because election HTML layouts differ.
The election ID in each command is the isolation boundary that selects the correct scraper implementation.

## Commands

### `fetch-sample`

Download and save the listing HTML sample for an election.

```bash
python -m scraper fetch-sample 2016-seimo
```

Output:

- Updates the listing sample file under `samples/html/2016-seimo/`.

Two elections download more than a listing file. The municipal general
elections publish their candidates in two structures, so `fetch-sample` also
fetches every party-list page: 467 of them for
`2023-kovo-5-savivaldybiu-tarybu-ir-meru` and 465 for
`2019-kovo-3-savivaldybiu-tarybu`. A list page already saved and non-empty is
skipped, so an interrupted capture resumes and only fetches what is missing.
See their workflow sections below.

### `sitemap`

Build sitemap JSON from a saved listing sample.

```bash
python -m scraper sitemap 2016-seimo
python -m scraper sitemap 2016-seimo --sample samples/html/2016-seimo/list.html
```

Options:

- `--sample <path>`: Override source HTML sample path.

Output:

- Writes `sitemaps/2016-seimo.json`.
- Prints row/extraction stats.

### `fetch-first-candidate-samples`

Download first sitemap candidate page and tab pages into sample fixtures.

```bash
python -m scraper fetch-first-candidate-samples 2016-seimo
```

Options:

- `--sitemap <path>`: Defaults to `sitemaps/2016-seimo.json`.
- `--samples-root <path>`: Defaults to `samples/html/2016-seimo`.
- `--allow-new-samples`: Allows creating new candidate directories. Disabled by default.

Output:

- Creates/updates `anketa.html`, tab pages, and `index.json` under candidate sample directory.

### `fetch-candidate-samples`

Download selected candidates and all candidate tabs.

```bash
python -m scraper fetch-candidate-samples 2016-seimo --candidate-id agne-sirinskiene
python -m scraper fetch-candidate-samples 2016-seimo --candidate-id agne-sirinskiene --candidate-id gabrielius-landsbergis
```

Options:

- `--candidate-id <id>`: Required. Repeatable.
- `--sitemap <path>`: Defaults to `sitemaps/2016-seimo.json`.
- `--samples-root <path>`: Defaults to `samples/html/2016-seimo`.
- `--allow-new-samples`: Allows creating new candidate directories. Disabled by default.
- `--anomalies-path <path>`: Optional, and there is no default. The fetch
  stage's events (`TabDownloadFailed`, `MissingExpectedTab`,
  `CampaignRootFetchFailed`, ...) are written there as JSONL. Without it they
  are named on stdout and dropped, which is why the corpus holds 8,949 anomaly
  events and not one of them says `stage: "fetch"` (issue #85). No default,
  because `data/<election-id>/anomalies.jsonl` belongs to the parse command,
  which writes it whole; `scripts/run_election_batches.sh` passes a
  per-candidate path and appends.

Output:

- Updates candidate sample directories and prints per-candidate tab stats.
- Writes the fetch stage's anomalies when `--anomalies-path` is given.

### `build-results`

Fetch VRK's results pages for an election whose candidate pages mark no
winner — every static-page family from 1996 to 2015 — and write
`sitemaps/<election-id>.results.json`, the map of VRK candidate id → seat
that `parse-anketa-samples` then joins into `kandidatavimas.isrinktas`.
Pages are cached under `samples/results/<election-id>/` so a re-run is
offline. The command prints the reconciliation stats; read them before
trusting the file (`unresolved`, `*NotInSitemap`, `seatCountMismatches`
should be zero or explained — see the 2012–2015 results section below).

```bash
python -m scraper build-results 2012-seimo
python -m scraper parse-anketa-samples 2012-seimo --samples-root samples-full/2012-seimo
```

### `parse-anketa-samples`

Parse saved candidate samples into output JSON records.

```bash
python -m scraper parse-anketa-samples 2016-seimo
python -m scraper parse-anketa-samples 2016-seimo --candidate-id regina-ablom
python -m scraper parse-anketa-samples 2020-seimo --candidate-id agne-sirinskiene
```

Options:

- `--candidate-id <id>`: Optional, repeatable. If omitted, parse all sampled candidates.
- `--samples-root <path>`: Defaults to `samples/html/2016-seimo`.
- `--output-root <path>`: Defaults to `data/2016-seimo`.
- `--anomalies-path <path>`: Optional. Defaults to `<output-root>/anomalies.jsonl`.

The campaign tab paths recorded inside each candidate's `index.json` are
re-anchored onto the samples root in use, so with an explicit `--samples-root`
this command works from any directory. A listed tab file that cannot be found
or read emits a `CampaignTabSampleMissing` anomaly.

Output:

- Writes one JSON file per parsed candidate in output root.
- Writes anomalies JSONL summary file.
- Prints parsed row counts and anomaly summary.

### `anomalies-report`

Read the corpus's `anomalies.jsonl` files back: counts per event type per
election, worst severity first, and a diff against `docs/anomaly-baseline.tsv`
so a new failure stands out against the 8,598 known ones.

```bash
python -m scraper anomalies-report                    # every election
python -m scraper anomalies-report 2020-seimo         # one election
python -m scraper anomalies-report --errors-only      # a page lost, not a page doubted
python -m scraper anomalies-report --update-baseline  # after a deliberate change
```

Options:

- `election_id`: Optional, repeatable. Defaults to every election under the data root.
- `--data-root <path>`: Defaults to `data`.
- `--errors-only`: Only `severity: "error"` events.
- `--baseline <path>`: Defaults to `docs/anomaly-baseline.tsv`.
- `--update-baseline`: Rewrite the baseline from this run. Refused when the run
  is narrowed to some elections or one severity.

Exit status: 1 when the run holds an event type the baseline does not name, or
more of one than it records; 0 otherwise. Fewer events than the baseline is
progress — printed, not failed. See `docs/ANOMALY_DETECTION.md`.

## European Parliament (`2019-ep`) Workflow

The 2019 EP election uses the same command surface as the Seimo modules; only
the election ID changes. Its candidate pages differ structurally from the Seimo
pages (the anketa is split across several sibling tables and the private
interest tab is pluralised), but the output schema is kept parallel.

```bash
python -m scraper fetch-sample 2019-ep
python -m scraper sitemap 2019-ep
python -m scraper fetch-candidate-samples 2019-ep --candidate-id petras-austrevicius --allow-new-samples
python -m scraper parse-anketa-samples 2019-ep --candidate-id petras-austrevicius
```

Resumable batch processing:

- `scripts/run_election_batches.sh 2019-ep`, tracking run state under
  `.run-state/2019-ep/`.

## European Parliament (`2024-ep`) Workflow

The 2024 EP election shares the 2024-era page layout with `2024-seimo`
(candidate anketa links use the `KandidatasAnketa_rkndId-*` stem and tab
content sits directly after the tab navigation), while keeping the EP tab set
of `2019-ep`. Candidate pages carry no campaign tab — campaigns were run by
the party lists.

```bash
python -m scraper fetch-sample 2024-ep
python -m scraper sitemap 2024-ep
python -m scraper fetch-candidate-samples 2024-ep --candidate-id vitalijus-mitrofanovas --allow-new-samples
python -m scraper parse-anketa-samples 2024-ep --candidate-id vitalijus-mitrofanovas
```

Resumable batch processing:

- `scripts/run_election_batches.sh 2024-ep`, tracking run state under
  `.run-state/2024-ep/`.

## Presidential (`2024-prezidento`) Workflow

The 2024 presidential election shares the 2024-era page layout with `2024-ep`
(candidate anketa links use the `KandidatasAnketa_rkndId-*` stem and tab content
sits directly after the tab navigation) and the same five-tab set (no trustees
tab and no campaign tab, unlike `2019-prezidento`). The listing keeps the
presidential shape: a stats table (`table1`) plus a candidate table (`table2`)
whose name cell follows a leading photo cell. The anketa reuses the EP Q6–Q14
declarations but swaps in the presidential eligibility questions for Q15–Q18
(dual citizenship, foreign oath, citizen by origin, three-year residency).

```bash
python -m scraper fetch-sample 2024-prezidento
python -m scraper sitemap 2024-prezidento
python -m scraper fetch-candidate-samples 2024-prezidento --candidate-id gitanas-nauseda --allow-new-samples
python -m scraper parse-anketa-samples 2024-prezidento --candidate-id gitanas-nauseda
```

## Municipal councils and mayors (`2023-kovo-5-savivaldybiu-tarybu-ir-meru`) Workflow

The 2023-03-05 municipal elections are the largest election in the repository:
13,796 candidates across all 60 municipalities. Candidate pages are the same
vintage as `2023-spalio-8-kupiskio-mero` and reuse that module's parsers whole —
the `10 .` question numbering, the hyphen-separated conviction table and the
`<div>`-wrapped tab bodies are all the same. What differs is the listing side.

This is the only election that publishes its candidates in **two structures**,
and neither is a superset of the other:

- `savKandidataiMerai.html` — 433 mayoral candidates, all 60 municipalities, on
  one page;
- `savKandidataiSarasai.html` — an index of 467 party, coalition and political
  committee lists, whose 13,769 council candidates live one page deeper under
  `savKandidataiTarNarApygardoje_rpgId-<municipality>_rorgId-<list>.html`.

406 people run for both and appear in both structures under the same VRK
candidate id; 27 mayoral candidates appear on no list. The union is 13,796,
which is the total VRK publishes on `savKandidataiSuvestine.html`.

`fetch-sample` therefore downloads more than the usual listing file. It saves
the wrapper page as `page.html`, the mayoral listing as `list.html` (keeping the
convention of the other elections), the list index as `lists-index.html`, and
then **one file per party list — 467 of them — under `lists/`**, named
`rpgId-<municipality>_rorgId-<list>.html`. A list page that is already saved and
non-empty is skipped, so re-running the command after an interruption fetches
only what is missing. Fetches are paced at 0.2 s apart and progress is printed
every 50 pages.

`sitemap` reads all of it back — `list.html`, `lists-index.html` and every file
under `lists/` — and merges the two structures on VRK's candidate id, so one
entry carries both candidacies for a dual candidate. A list page named in the
index but missing from `lists/` is recorded in the sitemap's `skipped` list as
`missing-list-sample` rather than failing the run. Expected stats:

```
rows 14202, extracted 13796, skipped 0, duplicateCandidateIds 0,
partyLists 467, mayoralCandidates 433, councilCandidates 13769,
dualCandidates 406, electedMayors 60, electedCouncilMembers 1498
```

Two further details specific to this module:

- candidate ids are `<name-slug>-<vrkCandidateId>`, e.g.
  `mykolas-majauskas-2420485`. 244 candidates share a name slug with someone
  else, and the positional suffix the other modules use would make an id depend
  on traversal order — which the resumable batch runner treats as its resume
  marker;
- the campaign tab is expected only for candidates standing for mayor. A council
  candidate's campaign is run by the party list, so expecting the tab
  unconditionally would raise a `MissingExpectedTab` warning for each of the
  13,363 council-only candidates.

```bash
python -m scraper fetch-sample 2023-kovo-5-savivaldybiu-tarybu-ir-meru
python -m scraper sitemap 2023-kovo-5-savivaldybiu-tarybu-ir-meru
python -m scraper fetch-candidate-samples 2023-kovo-5-savivaldybiu-tarybu-ir-meru --candidate-id mykolas-majauskas-2420485 --allow-new-samples
python -m scraper parse-anketa-samples 2023-kovo-5-savivaldybiu-tarybu-ir-meru
```

## Municipal councils (`2019-kovo-3-savivaldybiu-tarybu`) Workflow

The 2019-03-03 municipal elections are the second-largest election in the
repository: 13,666 candidates across all 60 municipalities. The listing side is
the same two-structure shape as `2023-kovo-5-savivaldybiu-tarybu-ir-meru`, and
since this module was added that machinery lives in
`scraper/shared/municipal_sitemap.py` and is shared by both:

- `savKandidataiMerai.html` — 410 mayoral candidates, all 60 municipalities, on
  one page;
- `savKandidataiSarasai.html` — an index of 465 party, coalition and
  "visuomeninis rinkimų komitetas" lists, whose 13,635 council candidates live
  one page deeper under
  `savKandidataiTarNarApygardoje_rpgId-<municipality>_rorgId-<list>.html`.

379 people run for both and appear in both structures under the same VRK
candidate id; 31 mayoral candidates appear on no list. The union is 13,666,
the total VRK publishes on `savKandidataiSuvestine.html`.

`fetch-sample` saves the wrapper page as `page.html`, the mayoral listing as
`list.html`, the list index as `lists-index.html`, and then **one file per party
list — 465 of them — under `lists/`**, named
`rpgId-<municipality>_rorgId-<list>.html`. A list page that is already saved and
non-empty is skipped, so re-running after an interruption fetches only what is
missing. Fetches are paced at 0.2 s apart and progress is printed every 50
pages.

`sitemap` reads all of it back and merges the two structures on VRK's candidate
id. Expected stats:

```
rows 14045, extracted 13666, skipped 0, duplicateCandidateIds 0,
partyLists 465, mayoralCandidates 410, councilCandidates 13635,
dualCandidates 379, markerJoinMismatch 0, electedMayors 60,
electedCouncilMembers 1442
```

Every one of those numbers reconciles with `savKandidataiSuvestine.html`.

What differs from the 2023 module, each of which would break a copy-paste:

- the candidate pages are **not** the 2023 vintage. They are the 2016 era, the
  same as `2017-balandzio-23-meru`, whose parsers this module reuses: the whole
  Q5–Q21 anketa with the biography questions inside it, five `pareiskimai`
  under the savivaldybių tarybų rinkimų įstatymas rather than the nine of the
  Rinkimų kodeksas, free-text biography, base64 photos, `ID001x`
  private-interest sections;
- candidate URLs use the `savKandidatasAnketa_rkndId-*` stem, with no `_2023`
  in it;
- the dual-candidacy marker on the listing reads `(kandidatas/kandidatė į
  savivaldybės tarybos narius - merus)`, because mayors were elected as council
  members under the rules of the time. The 2023 marker (`į savivaldybės merus`)
  matches none of these rows, and both gender inflections are published;
- the profile card labels the nomination row `Iškėlė į tarybos narius - merus`,
  with no "ir";
- the income rows of the GPM308 extract are worded in prose rather than by
  field number, so the asset/income aliases are local to this module. Reusing
  the 2017 ones leaves both income figures null.

Unchanged from 2023: candidate ids are `<name-slug>-<vrkCandidateId>`, the
campaign tab is expected only for candidates standing for mayor (expecting it
unconditionally is 13,256 spurious warnings), and elected candidates are marked
only by a blue-font name link on the listing.

```bash
python -m scraper fetch-sample 2019-kovo-3-savivaldybiu-tarybu
python -m scraper sitemap 2019-kovo-3-savivaldybiu-tarybu
python -m scraper fetch-candidate-samples 2019-kovo-3-savivaldybiu-tarybu --candidate-id nerijus-cesiulis-2406286 --allow-new-samples
python -m scraper parse-anketa-samples 2019-kovo-3-savivaldybiu-tarybu
```

## Municipal mayor (`2023-spalio-8-kupiskio-mero`) Workflow

The 2023-10-08 early Kupiškis district mayoral election is a five-candidate
single-municipality race, so the fixture set is the complete field. Its pages
mix layouts: the anketa follows the 2024 form (Q6–Q8 plus the Rinkimų kodekso
76 str. declarations Q9–Q14, with no EP or presidential extras), while the
biography keeps the 2020 Seimo numbering (nationality is Q2, so education and
work history shift by one). Three page-level quirks are handled by this module
only:

- some anketa questions are numbered with a space before the dot (`10 .`), which
  the shared strict question-number regex rejects;
- the Q13.4 conviction detail table separates label from value with a plain
  hyphen instead of the 2024 en dash;
- declaration and "Kita" tab bodies are wrapped in their own `<div>` instead of
  following the tab navigation as siblings.

The listing keeps the mayoral shape: a stats table (`table1`) plus a candidate
table (`table2`) whose municipality cell carries its own link, so the anketa
anchor is selected by the `KandidatasAnketa` marker. Candidate pages do carry a
campaign tab.

```bash
python -m scraper fetch-sample 2023-spalio-8-kupiskio-mero
python -m scraper sitemap 2023-spalio-8-kupiskio-mero
python -m scraper fetch-candidate-samples 2023-spalio-8-kupiskio-mero --candidate-id algirdas-raslanas --allow-new-samples
python -m scraper parse-anketa-samples 2023-spalio-8-kupiskio-mero
```

## Municipal mayor repeat vote (`2023-geguzes-7-visagino-mero`) Workflow

The 2023-05-07 repeat Visaginas mayoral vote re-ran the runoff of the March
2023 municipal election after the Supreme Administrative Court set the original
second-round result aside and ordered it re-run.
It is a separate VRK election (`/rinkimai/1344/rnk1664/`) with two candidates —
the March runoff pair — so the fixture set is the complete field. The pages
are the `2023-spalio-8-kupiskio-mero` vintage throughout (same listing shape,
`10 .` question numbering, 2020-numbered biography, `<div>`-wrapped tab
bodies), so that module's parsers are reused whole.

One difference: candidate pages publish five tabs, not six. There is no
campaign tab — the candidates' campaign finance is published with the
March election (`2023-kovo-5-savivaldybiu-tarybu-ir-meru`) — so, as in
`2025-kovo-16-meru`, the campaign tab is not an expected tab but would still
be fetched if present. Both profile cards carry `Turas: II`, and the list
fields (`Sąrašas`, `Numeris sąraše`, `Porinkiminis numeris sąraše`) are
published empty: this vote had no list component.

```bash
python -m scraper fetch-sample 2023-geguzes-7-visagino-mero
python -m scraper sitemap 2023-geguzes-7-visagino-mero
python -m scraper fetch-candidate-samples 2023-geguzes-7-visagino-mero --candidate-id erlandas-galaguz --allow-new-samples
python -m scraper parse-anketa-samples 2023-geguzes-7-visagino-mero
```

## Seimo by-election (`2023-rugsejo-3-seimo-raseiniai-kedainiai`) Workflow

The 2023-09-03 early Seimo by-election in the single-member Raseiniai–Kėdainiai
constituency (No. 42) fielded eight candidates, so the fixture set is the
complete field. Unlike the 2023 mayoral pages, these carry none of that
election's layout quirks: the listing is the `2024-seimo` full-list shape (stats
tables `table1`/`table2` followed by the candidate table `table3`, name link in
the first cell, winner marked with a `(V)` suffix), and tab bodies follow the tab
navigation as siblings, so the 2024 page parsers apply directly.

Two details differ from `2024-seimo`:

- the biography questionnaire keeps the 2023 numbering (nationality is Q2, so
  education and work history shift by one), shared with
  `2023-spalio-8-kupiskio-mero`;
- Q8 asks for a single membership and is answered inline rather than with a
  membership table.

Candidates run either their own campaign (`Savarankiškas`, publishing all five
campaign tabs) or a party-represented one (`Atstovaujamasis`, donations only).

```bash
python -m scraper fetch-sample 2023-rugsejo-3-seimo-raseiniai-kedainiai
python -m scraper sitemap 2023-rugsejo-3-seimo-raseiniai-kedainiai
python -m scraper fetch-candidate-samples 2023-rugsejo-3-seimo-raseiniai-kedainiai --candidate-id matas-skamarakas --allow-new-samples
python -m scraper parse-anketa-samples 2023-rugsejo-3-seimo-raseiniai-kedainiai
```

## Municipal mayor (`2025-kovo-16-meru`) Workflow

The 2025-03-16 early mayoral elections cover three municipalities — Jonavos
rajono, Joniškio rajono and Panevėžio miesto — with fourteen candidates, so the
fixture set is the complete field.

The listing is the mayoral shape shared with `2023-spalio-8-kupiskio-mero`
(stats table `table1` plus candidate table `table2`, anketa anchor picked by the
`KandidatasAnketa` marker because the municipality cell carries its own link),
but the candidate pages are pure 2024 layout: tab bodies follow the tab
navigation as siblings, Q8 is answered with a membership table, and the biography
questionnaire has no nationality question. The anketa itself is the mayoral
Q6–Q14 set, with no EP or presidential eligibility questions.

Two election-specific details:

- The listing appends a status note to the name of a candidate whose
  registration was revoked — `Povilas BEIŠYS(išbrauktas - Seimo nutarimu)`. The
  note is split from the name into `candidateNote` rather than discarded; the
  candidate page itself leaves that line blank. All four Jonava candidates
  carry it.
- Struck-off candidates publish five tabs instead of six (no campaign tab), so
  the campaign tab is fetched when present but is not an expected tab.

```bash
python -m scraper fetch-sample 2025-kovo-16-meru
python -m scraper sitemap 2025-kovo-16-meru
python -m scraper fetch-candidate-samples 2025-kovo-16-meru --candidate-id gediminas-cepulis --allow-new-samples
python -m scraper parse-anketa-samples 2025-kovo-16-meru
```

## Municipal mayor (`2017-balandzio-23-meru`) Workflow

The 2017-04-23 new mayoral elections cover Jonavos and Šakių rajonai — eleven
candidates, so the fixture set is the complete field. This is the oldest
election in the repository and predates the 2024 page layout entirely:

- the anketa is split across sibling tables with standalone record tables
  between them, and sub-questions are numbered without a trailing dot
  (`8.2 Ar nesate ...`), which the strict question-number pattern reads as
  question `8`. Both are the 2019 EP shape, so that module's profile and anketa
  parsers are reused;
- Q9 quotes the statute it refers to in a row of its own and the answer is
  rendered on that continuation row, not on the question row;
- photos are base64 data URIs, the private-interest declaration uses the
  `ID001x` section blocks, and the income summary is taken from the GPM308 form,
  whose labels name their own field numbers — so the asset/income aliases are
  local to this module;
- candidate pages link every campaign participant through the treasurer page
  (`savarankiskasIzdininkas_pkdId-...`), but party-represented participants have
  no treasurer page and that link 404s upstream. The fetcher falls back to
  `atstovaujamasis_pkdId-...`, which recovers the campaign data for four of the
  eleven candidates.

```bash
python -m scraper fetch-sample 2017-balandzio-23-meru
python -m scraper sitemap 2017-balandzio-23-meru
python -m scraper fetch-candidate-samples 2017-balandzio-23-meru --candidate-id eugenijus-sabutis --allow-new-samples
python -m scraper parse-anketa-samples 2017-balandzio-23-meru
```

## Municipal mayor (`2017-rugsejo-10-marijampoles-mero`) Workflow

The 2017-09-10 new Marijampolė municipality mayoral election fielded eight
candidates, so the fixture set is the complete field. Its pages are the same
vintage as `2017-balandzio-23-meru` — same question numbering, same Q9
continuation row, same GPM308 income labels, same base64 photos — so this module
reuses that one's parsing rules and only carries its own election id, listing URL
and paths.

One difference in the campaign data: candidates whose campaign is run by their
party have a participant page with no tab navigation at all, so only the
participant metadata is recorded and the donation sections stay empty. The
treasurer-link fallback of the April election is reused for the rest.

```bash
python -m scraper fetch-sample 2017-rugsejo-10-marijampoles-mero
python -m scraper sitemap 2017-rugsejo-10-marijampoles-mero
python -m scraper fetch-candidate-samples 2017-rugsejo-10-marijampoles-mero --candidate-id irena-lunskiene --allow-new-samples
python -m scraper parse-anketa-samples 2017-rugsejo-10-marijampoles-mero
```

## Municipal mayor (`2021-spalio-10-meru`) Workflow

The 2021-10-10 new mayoral elections cover Kelmės and Trakų rajonai — fourteen
candidates, so the fixture set is the complete field. The pages sit between the
two eras already in the repository: the profile card, the `<div>`-wrapped tab
bodies and the biography questionnaire match `2023-spalio-8-kupiskio-mero`
(whose helpers this module reuses), while the anketa is numbered like the 2020
Seimo one — Q6.x contacts, Q7.x position and membership — with the municipal
36 str. 11 d. declarations under Q8.x, the conviction questions under Q9.x and
the former-USSR question as Q10.

Two details are specific to this election:

- Q7.1 is written without a trailing dot, which the strict question-number
  pattern reads as question `7` — the position question — so numbers are
  re-derived with the tolerant pattern;
- the Q9.1 conviction table names its columns after the sub-question numbers
  (`9.1.1. Apkaltinamojo nuosprendžio (sprendimo) data:`), which are mapped to
  the field names the other elections use.

```bash
python -m scraper fetch-sample 2021-spalio-10-meru
python -m scraper sitemap 2021-spalio-10-meru
python -m scraper fetch-candidate-samples 2021-spalio-10-meru --candidate-id stasys-jokubauskas --allow-new-samples
python -m scraper parse-anketa-samples 2021-spalio-10-meru
```

## Municipal mayor (`2021-balandzio-11-radviliskio-mero`) Workflow

The 2021-04-11 new Radviliškis district mayoral election fielded seven
candidates, so the fixture set is the complete field. The pages are the same
vintage as `2021-spalio-10-meru` — same question numbering, the same dotless
Q7.1, the same Q9.1 conviction table — so this module reuses that one's parsing
rules and carries only its own election id, listing URL and paths.

Two things to expect in the output: every candidate answered "Nenurodė" to Q10
(the former-USSR question), which normalizes to null, and this is the first
election in the repository found to carry a document on its "Kita" tab — one
candidate published a signed pledge not to bribe voters, captured under
`normalized.kita.nuorodos`. A small minority of `2019-kovo-3-savivaldybiu-tarybu`
candidates publish the same kind of pledge.

```bash
python -m scraper fetch-sample 2021-balandzio-11-radviliskio-mero
python -m scraper sitemap 2021-balandzio-11-radviliskio-mero
python -m scraper fetch-candidate-samples 2021-balandzio-11-radviliskio-mero --candidate-id vytautas-simelis --allow-new-samples
python -m scraper parse-anketa-samples 2021-balandzio-11-radviliskio-mero
```

## Seimo by-election (`2017-balandzio-23-seimo-anyksciai-panevezys`) Workflow

The 2017-04-23 new Seimo by-election in the single-member Anykščiai–Panevėžys
constituency (No. 49) fielded eleven candidates, so the fixture set is the
complete field. It was held the same day as `2017-balandzio-23-meru`, but the
candidate pages follow the 2016 Seimo layout rather than the mayoral one: the
whole Q5–Q21 question set sits in a single table, the profile card keeps the
elected note inside the name cell, and the declarations use the 2016 GPM308
income labels and `ID001x` sections. The 2016 Seimo parsers therefore apply.

Three things differ from the mayoral elections of the same day:

- the candidate table on the listing carries no id — the ids later elections use
  for it belong to layout tables here — so it is identified as the `partydata`
  table that actually holds candidate anketa links;
- the private-interest tab is singular (`Privačių interesų deklaracija`);
- the education (Q12) and prior-mandate (Q15) tables are rendered in a row of
  their own, so the normalization reads the question row *and* the table row
  that follows it.

```bash
python -m scraper fetch-sample 2017-balandzio-23-seimo-anyksciai-panevezys
python -m scraper sitemap 2017-balandzio-23-seimo-anyksciai-panevezys
python -m scraper fetch-candidate-samples 2017-balandzio-23-seimo-anyksciai-panevezys --candidate-id antanas-baura --allow-new-samples
python -m scraper parse-anketa-samples 2017-balandzio-23-seimo-anyksciai-panevezys
```

## Seimo by-elections (`2018-rugsejo-16-seimo-zanavykai`, `2019-rugsejo-8-seimo`) Workflow

Both are the 2016 Seimo page layout, the same as
`2017-balandzio-23-seimo-anyksciai-panevezys`, so both modules reuse that one's
parsing rules and carry only their own election id, listing URL and paths. The
2018 election ran in one constituency (6 candidates); the 2019 one ran in three
at once (27 candidates, one winner each).

One thing changed between April 2017 and these two: the asset rows keep the
I.–V. labels, but the income rows switched to the modern wording (`Deklaruota
apmokestinamųjų ir neapmokestinamųjų pajamų suma`) even though the section is
still headed GPM308. Both modules therefore take the income aliases from the
2024 EP module; with the 2016 aliases as they then stood, every income figure
normalized to null — which is exactly what happened to `2020-seimo`, whose
module kept the 2016 wiring (issue #81). Since that fix the 2016 normalizer
matches the two money rows on their opening words rather than on the slug of
VRK's whole sentence, so either wiring reads the modern wording.

The 2019 listing also has a candidate nominated by two parties. Her second
nominator is a listing row of its own with no candidate link — correctly skipped
by the sitemap — and a profile row with an empty label cell, which is folded
into the field above it (see `docs/OUTPUT_SCHEMA.md`).

```bash
python -m scraper fetch-sample 2019-rugsejo-8-seimo
python -m scraper sitemap 2019-rugsejo-8-seimo
python -m scraper fetch-candidate-samples 2019-rugsejo-8-seimo --candidate-id liudas-jonaitis --allow-new-samples
python -m scraper parse-anketa-samples 2019-rugsejo-8-seimo
```

## Seimo by-elections (`2015-kovo-1-seimo-zirmunai`, `2015-birzelio-7-seimo-varena-eisiskes`) Workflow

The 2015-03-01 new Seimo by-election in Žirmūnai (No. 4) — the same
constituency `2019-rugsejo-8-seimo` later voted in — is the first module of the
pre-2016 static layout, older than every other family in the repository. Twelve
candidates, fixture set is the complete field. The 2015-06-07 Varėna–Eišiškės
(No. 70) by-election is the same layout under election path `459_lt` — its
module is thin wiring over the Žirmūnai one's parameterized machinery (8
candidates, complete field, 7 of them represented by their nominating party's
campaign). Nothing about the pages matches the 2016 era:

- the listing is a bare static district page (no Liferay wrapper, no `srcUrl`),
  and candidate links use the genitive `Kandidato<ID>Anketa.html` stem that the
  other eras' `KandidatasAnketa` marker cannot match;
- the candidate "tabs" are five separate static files
  (`Anketa`/`Biografija`/`Deklaracijos`/`InteresuDeklaracija`/`Kita`) linked
  from bare `<li>` siblings — there is no `ul#tabnav` on candidate pages;
- the anketa is one table cell of inline numbered questions with answers in
  `<b>`, with self-labeled nested tables for Q12/Q15;
- photos are external JPGs, declared amounts are litas, and no page anywhere
  marks the winner;
- the campaign participant link sits in the profile card and leads to
  `PolitiniuKampanijuFinansavimas/Dalyvis<ID>/` pages.

```bash
python -m scraper fetch-sample 2015-kovo-1-seimo-zirmunai
python -m scraper sitemap 2015-kovo-1-seimo-zirmunai
python -m scraper fetch-candidate-samples 2015-kovo-1-seimo-zirmunai --candidate-id sarunas-gustainis --allow-new-samples
python -m scraper parse-anketa-samples 2015-kovo-1-seimo-zirmunai
python -m scraper parse-anketa-samples 2015-birzelio-7-seimo-varena-eisiskes
```

## Telšiai mayor (`2015-lapkricio-8-telsiu-mero`) Workflow

The 2015-11-08 new Telšiai district council member-mayor election is the same
2015-era layout with the municipal anketa variant: the savivaldybių tarybų
rinkimų įstatymo declarations (Q8.1–8.5 plus the Q9 conviction-declaration
question) with verbose first-person answers ("Neturiu", "Nesu", "Neinu").
Its module is thin wiring over the Žirmūnai machinery with the municipal
question mapping plugged in — the mapping later 2015 municipal elections
reuse. Two path quirks: the static pages live under
`2015_4_savivaldybiu_tarybu_rinkimai/469_lt/` rather than `rinkimai/`, while
the campaign participant pages sit under `rinkimai/469_lt/` anyway. Seven
candidates, fixture set is the complete field, mayoral section only (the
council-lists section of the district page is empty).

```bash
python -m scraper fetch-sample 2015-lapkricio-8-telsiu-mero
python -m scraper sitemap 2015-lapkricio-8-telsiu-mero
python -m scraper fetch-candidate-samples 2015-lapkricio-8-telsiu-mero --candidate-id petras-kuizinas --allow-new-samples
python -m scraper parse-anketa-samples 2015-lapkricio-8-telsiu-mero
```

## Repeat municipal elections (`2015-birzelio-7-pakartotiniai-sirvintos-trakai`) Workflow

One VRK election (452) covering two districts that repeated different votes:
Širvintos only the member-mayor election (7 candidates, no party lists),
Trakai both the mayor and the council (8 mayoral, 319 council across 9 lists).
The anketa is the municipal variant, same mapping as Telšiai. What is specific
here is the listing:

- the district ids read backwards against the election title —
  `Apygarda7921` is **Širvintos** and `Apygarda7911` is **Trakai**;
- `fetch-sample` walks both district pages and every party-list page under
  them, skipping files already on disk so an interrupted capture resumes;
- the two structures merge on VRK's candidate id, giving one entry with both
  candidacies for the 7 people who ran for both seats, and the listing's own
  prose marker cross-checks that join;
- **one person has two candidate ids.** Marija Puč is 87693 as a mayoral
  candidate and 87694 on the council list, so the id join cannot merge her.
  Both entries are kept and `stats.markerJoinMismatch` reports 1 rather than
  the mismatch passing silently. Do not "fix" this by merging on name — the
  rule against that is what keeps 244 same-name people apart in 2023;
- her council page is a `Rengiama` placeholder with no questionnaire, which
  parses to an `AnketaNotPublished` warning, not a parse error;
- Biografija is a mayoral-only tab, so expected tabs are computed per
  candidate from the sitemap role.

```bash
python -m scraper fetch-sample 2015-birzelio-7-pakartotiniai-sirvintos-trakai
python -m scraper sitemap 2015-birzelio-7-pakartotiniai-sirvintos-trakai
python -m scraper fetch-candidate-samples 2015-birzelio-7-pakartotiniai-sirvintos-trakai --candidate-id zivile-pinskuviene --allow-new-samples
python -m scraper parse-anketa-samples 2015-birzelio-7-pakartotiniai-sirvintos-trakai
```

## Repeat municipal election (`2015-birzelio-21-pakartotiniai-silutes`) Workflow

The 2015-06-21 repeat Šilutė council election (457) is the same two-structure
listing in a single district, so its module is wiring over the June 7th one's
walk and id merge plus the municipal anketa mapping. 366 candidates across 8
party lists — one of them a `Visuomeninis rinkimų komitetas`, this era's other
nominator type.

It is the clean counterpart to the June 7th election: every one of the 8
mayoral candidates also stands for the council, so the prose marker and the id
join agree exactly (`markerJoinMismatch` 0). The one duplicate candidate id is
a genuine name collision — two different people called Jonas Šakurskis, born
1953 and 1957, on different lists — so the positional `-2` suffix is right
here, unlike Marija Puč in the June election.

```bash
python -m scraper fetch-sample 2015-birzelio-21-pakartotiniai-silutes
python -m scraper sitemap 2015-birzelio-21-pakartotiniai-silutes
python -m scraper fetch-candidate-samples 2015-birzelio-21-pakartotiniai-silutes --candidate-id alfredas-stasys-nauseda --allow-new-samples
python -m scraper parse-anketa-samples 2015-birzelio-21-pakartotiniai-silutes
```

## Municipal general election (`2015-kovo-1-savivaldybiu`) Workflow

The 2015-03-01 municipal general — 15,149 candidates in all 60 municipalities,
and Lithuania's first direct mayoral election, held on the same ballot.

It deliberately does **not** use `scraper/shared/municipal_sitemap.py`. That
module is built for the 2019/2023 listing: one flat index of party lists,
`table3` table ids, `rpgId`/`rorgId` URLs and blue-anchor elected markers. The
2015 pages have none of them — they publish a district page per municipality
with the lists hanging off it, which is the shape the 2015 repeat elections
already walk. So this module discovers the 60 district pages from VRK's
municipality index and reuses that walk with a stable id builder.

- `fetch-sample` saves the municipality index, VRK's mayoral roll-up, all 60
  district pages and all 478 list pages, skipping what is already on disk so
  an interrupted capture resumes. Expect roughly 540 requests on a cold run.
- `sitemap` merges the mayoral and council structures on VRK's candidate id
  (412 people stand for both) and cross-checks the result against the mayoral
  roll-up: `mayoralOnlyInListing` and `mayoralOnlyInDistrictWalk` must both be
  0, as they are — 434 mayoral candidates either way.
- **Candidate ids carry VRK's own id** — `valius-azuolas-77601` — because 140
  candidates share a name slug. A positional suffix would make an id depend on
  traversal order, and the batch runner uses the output filename as its resume
  marker.

```bash
python -m scraper fetch-sample 2015-kovo-1-savivaldybiu
python -m scraper sitemap 2015-kovo-1-savivaldybiu
python -m scraper fetch-candidate-samples 2015-kovo-1-savivaldybiu --candidate-id adele-dimsiene-85873 --allow-new-samples
python -m scraper parse-anketa-samples 2015-kovo-1-savivaldybiu
```

Resumable full scrape:

- `scripts/run_election_batches.sh 2015-kovo-1-savivaldybiu`, with
  `KEEP_SAMPLES=1` — at this size a later parser fix should be an offline
  re-parse, not hours of repeat traffic to vrk.lt.

## Municipal general election (`2011-vasario-27-savivaldybiu`) Workflow

The 2011-02-27 municipal general (VRK election 409, issue #42) — 16,403
candidates in all 60 municipalities, council seats only: the last municipal
election before mayors were elected directly, and the only general election
in which self-nominated individuals stood for the council on their own.

The listing is the 2015 shape — VRK's municipality index, a district page per
municipality, the lists hanging off it — but a district-page row is one of two
things. A party (560 lists), a party coalition (11) or a coalition of
self-nominated candidates (28) links its list page; a self-nominated
individual (143) links the candidate page directly, at one seat each. The
2015 walker reads a direct candidate link on a district page as a mayoral
candidacy, the one thing it cannot be here, so
`scraper/elections/savivaldybiu_2011/sitemap.py` walks the same files with
its own row reader and reuses the 2015 modules' list reader, fetcher, id
builder and candidacy block. The pages are the 2015-era static layout with
the municipal question set (Q8.1–8.5, Q9), so the candidate stage is
`telsiu_mero_2015`'s mapping over `seimo_zirmunu_2015`'s walkers.

- `fetch-sample` saves the municipality index, VRK's three roll-ups
  (`KandidataiIssikele.html`, `KandidataiKoalicijos1.html`,
  `KandidataiIssikeleKoalicijos.html`), all 60 district pages and all 599
  list pages, resuming past what is on disk. About 660 requests cold.
- `sitemap` cross-checks the walk against the roll-ups: the self-nominated
  roll-up names every self-nominated candidate — the 143 individuals *and*
  the 362 members of the self-nominated coalitions, 505 in all — and the two
  coalition roll-ups declare each coalition's member count. All four checks
  (`selfNominatedOnlyInListing`, `selfNominatedOnlyInDistrictWalk`,
  `coalitionListsNotWalked`, `coalitionSizeMismatches`) are 0. The list kind
  is recorded on every council candidacy (`listKind`: `partija`,
  `partiju-koalicija`, `issikelusiu-kandidatu-koalicija`, or null for an
  individual, who carries `selfNominated: true` and the ballot number as
  `listNumber`).
- The list pages print names in capitals and the district pages in title
  case; the sitemap keeps title case for both (`Valdemaras Stančikas`).
- Candidate ids carry VRK's own id, as in 2015 (`darius-norkus-42302`).
- Four tabs for everyone — no Biografija (council candidates only) and no
  campaign participant link on any page (VRK published none for 2011, as for
  2008).
- `build-results` walks the `2011_savivaldybiu_tarybu_rinkimai` tree with the
  municipal walker: 1,526 council seats, 18 of them won by self-nominated
  individuals on their own row of the results table (method
  `self-nominated`); no mayoral field anywhere, so the seat total is the whole
  council. All 60 composition pages contain every derived winner.

```bash
python -m scraper fetch-sample 2011-vasario-27-savivaldybiu
python -m scraper sitemap 2011-vasario-27-savivaldybiu
python -m scraper build-results 2011-vasario-27-savivaldybiu
python -m scraper fetch-candidate-samples 2011-vasario-27-savivaldybiu --candidate-id darius-norkus-42302 --allow-new-samples
python -m scraper parse-anketa-samples 2011-vasario-27-savivaldybiu
```

Resumable full scrape, with the HTML retained for offline re-parses:

```bash
KEEP_SAMPLES=1 scripts/run_election_batches.sh 2011-vasario-27-savivaldybiu
```

## Municipal general election (`2007-vasario-25-savivaldybiu`) Workflow

The 2007-02-25 municipal general (VRK election 3, issue #34) — 13,422
candidates in all 60 municipalities, council seats only, and the oldest
municipal election with candidate pages: the same year as the Dzūkija Seimo
by-election, one tree older than the 2008 Seimo general (the path is
`rinkimai/3/`, without `_lt`). Only parties and coalitions of parties could
nominate, so every candidate is on one of the 600 lists (596 party lists,
4 coalitions); nobody stood on their own or twice.

The listing is the 2011/2015 shape one rename away: VRK's index lists the
60 municipality pages ("Pagal apygardą",
`Apygardoje<ID>DalyvaujanciosPartijos.html` rather than
`KandidataiApygardos<ID>.html`) and the 24 parties ("Pagal partiją"), each
municipality page is a ballot of numbered list rows, each list page the
numbered candidates. The 2015 walker's fetcher, list reader and sample-file
naming do the work (its district-id pattern now accepts both file names);
`scraper/elections/savivaldybiu_2007/sitemap.py` reads the index and the
by-party pages, which the later trees do not have.

- `fetch-sample` saves the index, the 24 by-party pages (`parties/`), all
  60 municipality pages and all 600 list pages, resuming past what is on
  disk. About 690 requests cold.
- `sitemap` cross-checks the walk against the by-party pages: every party
  list walked is linked from its party's page, and of the 604 links on the
  party pages the 8 that lead nowhere on any ballot are the coalition
  members' empty shells (a member party's page links a list under its own
  id in the municipality where it stood in coalition; the page has a
  heading and no candidates). Those 8 name the coalitions' members — two
  each — which the sitemap records under `coalitions`. The list kind is on
  every council candidacy (`listKind`: `partija` or `partiju-koalicija`;
  `selfNominated` is false throughout).
- The list pages print names in capitals; the sitemap keeps title case
  (`Artūras Zuokas`), as the 2011 module does. The municipality pages are
  headed as electoral districts ("Elektrėnų rinkimų apygarda"); the
  sitemap names the municipality (`Elektrėnų savivaldybė`).
- A withdrawn candidate keeps their number on the ballot: `listPosition`
  is the printed number, so a list can run 1–33 with no 29.
- Candidate ids carry VRK's own id (`arturas-zuokas-12711`).
- Three tabs for everyone — Anketa, the declarations and the interest
  declaration: no Biografija, no Kita (first published in 2008), and no
  campaign participant link on any page.
- The pages are the family's oldest shape, the one the Dzūkija by-election
  has: a plain-text card read by the era's legacy-card branch and an
  unnumbered "label: <b>answer</b>" questionnaire, so
  `savivaldybiu_2007/anketa_parser.py` keys the rows by their prompts.
  Income is five FR0462 prose lines (the form and its S, S0, S15 and S33
  variants; the candidate filed one) summed by the era normalizer; the
  interest declaration is record tables with bold column-name rows, read
  as columns and rows. Both were shared defects — see DATASET.md.
- `build-results` walks the `2007_savivaldybiu_tarybu_rinkimai/` tree (no
  `output_lt` level): each municipality's results page gives the lists'
  mandate counts and links a "Mandatus gavę kandidatai" page that rows
  every winner with an anketa link, so the 1,550 seats are read by id, not
  derived by ranking. The results table's total, the lists' mandate sum
  and the composition page's `Mandatų skaičius` agree in all 60.

```bash
python -m scraper fetch-sample 2007-vasario-25-savivaldybiu
python -m scraper sitemap 2007-vasario-25-savivaldybiu
python -m scraper build-results 2007-vasario-25-savivaldybiu
python -m scraper fetch-candidate-samples 2007-vasario-25-savivaldybiu --candidate-id arvydas-vysniauskas-7357 --allow-new-samples
python -m scraper parse-anketa-samples 2007-vasario-25-savivaldybiu
```

Resumable full scrape, with the HTML retained for offline re-parses:

```bash
KEEP_SAMPLES=1 scripts/run_election_batches.sh 2007-vasario-25-savivaldybiu
```

## Seimas archive (`1996-spalio-20-seimo`, `1997-kovo-23-seimo-pakartotiniai`, `1997-gruodzio-21-seimo-pakartotiniai`, `1998-kovo-22-seimo-pakartotiniai`, `1998-lapkricio-15-seimo-pakartotiniai`, `1999-kovo-21-seimo-pakartotiniai`) Workflow

The 1996-10-20 Seimas general election and the 1997-1999 repeat votes are the
oldest family in the repository — static pages captured by Teleport Pro from
`lrs.lt/cgi-bin/ora7dbcgi/...`, older than the 2015 family and shaped nothing
like it. The shared parser lives in `scraper/shared/seimo_archive_1990s.py`;
these six modules differ only in which directory (`seim96`, `seimpk`, `19990321`),
"phase" prefix and constituency numbers they target.

- The listing is a two-level walk: a directory page (`apgseiml.htm-1.htm` for
  1996's 71 constituencies) links to `apgtl.htm-<phase>+<constituency>.htm`
  pages, each holding a plain two-column table (name, nominator) with no
  party-list hop — the constituency page *is* the candidate list. The two
  by-elections skip the directory: VRK names their handful of constituencies
  directly on `seimpk/index.html#1997`, so `TARGETS` in each module's
  `sitemap.py` hardcodes them instead of crawling for them.
- The candidate page (`kandvl.htm`) carries a data-corrupting quirk: a
  malformed `<!--sql format>` comment, left by a failed backend query, opens
  after the real candidacy paragraphs and swallows **three real fields** —
  "Gimimo vieta", "Gyvenamoji vieta" and "Tautybė" — along with a block of
  boilerplate eligibility Q&A that always reads the same "Neturi"/"Nėra", not
  real per-candidate data. A normal HTML parser drops comment contents
  entirely, so the three are recovered with targeted regexes over the raw
  HTML instead; the eligibility junk is discarded on purpose.
  `tests/test_archive_1990s_card.py` and
  `tests/test_seimo_1996_anketa_parser.py` guard this against regression.
- Below the comment the card prints the rest of its questionnaire as ordinary
  paragraphs — education level, foreign languages, academic degree and title,
  bodies previously elected to, main workplace, public activity, marital
  status, family members, and a free-text "Ką dar norėtų parašyti apie save".
  This whole block went unread until issue #69 (2026-08-26). It shares its
  `<p>Label: <b>value</b>` grammar with the 1997 municipal card, so both
  families read it through `scraper/shared/archive_1990s_card.py`, and it
  lands under the corpus's usual `anketa.*` keys. Unlike the municipal card,
  no paragraph here carries two labels (measured over all 906 cards), so no
  stop list is needed on this side.
- A candidate can carry two candidacies — their single-member constituency
  and, optionally, a `Daugiamandatė` (multi-mandate party list) entry with its
  own list number — both are kept as separate objects in
  `rawData.candidacies`/`normalized.kandidatavimas` rather than merged.
- The `kpdl.htm` income declaration is fetched alongside the candidate page
  (saved as `declaration.html`) and parsed by
  `scraper/shared/deklaracija_archive_1990s.py` into the corpus's usual
  `turto-ir-pajamu-deklaracijos` key. The 1990s form sums turtas and piniginės
  lėšos rather than splitting them, so the two modern split keys are null and
  the combined figures get their own; see `docs/OUTPUT_SCHEMA.md`.
  The free-text biography page (`biogr.htm`), when linked, is captured
  verbatim as `rawData.biography.text`.
- 1996 is the only general election of the four (879 candidates, 71
  constituencies); the March 1997 repeat covers four constituencies (Naujosios
  Vilnios, Vilniaus-Šalčininkų, Vilniaus-Trakų, Trakų — 23 candidates,
  complete field); the December 1997 repeat is one constituency, Aukštaitijos
  No. 28 (4 candidates, complete field); the March 1998 repeat is two
  constituencies at once, Naujosios Vilnios No. 10 and Vilniaus Trakų No. 57,
  phase prefix `8` (11 candidates, 5 + 6, complete field — VRK's index names
  the pair as one election, so it is one module, and GitHub's #22 was closed
  as a duplicate of #21 on that reading); the November 1998 repeat is one
  constituency, Nevėžio No. 26, phase prefix `10` (11 candidates, complete
  field); the March 1999 repeat is three constituencies, Naujosios Vilnios
  No. 10, Nevėžio No. 26 and Vilniaus Trakų No. 57, phase prefix `11` (22
  candidates, 7 + 8 + 7, complete field).
- **A date-named directory says nothing about the page era.** The March 1999
  election lives under `19990321`, the same convention as `20000319`
  (`savivaldybiu_2000`) and `20001008` (`seimo_2000`) — which are the *next*
  layout generation. Its pages are this family's. `constituency_url` takes the
  directory as a parameter, so the two are independent; read the markup, not
  the directory name.
- How much each candidate links varies sharply by election, and a thin block
  is the source, not a scrape failure: biography/declaration coverage is
  854/879 and 879/879 for 1996, 23/23 and **1/23** for the March 1997 repeat,
  4/4 and 4/4 for December 1997, 11/11 and **2/11** for March 1998, 11/11 and
  11/11 for November 1998, 22/22 and 22/22 for March 1999.
- Each by-election's constituencies are hardcoded in its `sitemap.py`
  `CONSTITUENCIES`, so adding another is that list, the phase prefix and the
  usual five CLI dispatch points — no parser work. The 1998-11-15 Nevėžio
  module (`seimo_nevezio_1998_lapkricio`) is the shortest example.

```bash
python -m scraper fetch-sample 1996-spalio-20-seimo
python -m scraper sitemap 1996-spalio-20-seimo
python -m scraper fetch-candidate-samples 1996-spalio-20-seimo --candidate-id asmolkov-vasilij --allow-new-samples
python -m scraper parse-anketa-samples 1996-spalio-20-seimo

python -m scraper fetch-sample 1997-kovo-23-seimo-pakartotiniai
python -m scraper sitemap 1997-kovo-23-seimo-pakartotiniai
python -m scraper parse-anketa-samples 1997-kovo-23-seimo-pakartotiniai

python -m scraper fetch-sample 1997-gruodzio-21-seimo-pakartotiniai
python -m scraper sitemap 1997-gruodzio-21-seimo-pakartotiniai
python -m scraper parse-anketa-samples 1997-gruodzio-21-seimo-pakartotiniai

python -m scraper fetch-sample 1998-kovo-22-seimo-pakartotiniai
python -m scraper sitemap 1998-kovo-22-seimo-pakartotiniai
python -m scraper parse-anketa-samples 1998-kovo-22-seimo-pakartotiniai

python -m scraper fetch-sample 1999-kovo-21-seimo-pakartotiniai
python -m scraper sitemap 1999-kovo-21-seimo-pakartotiniai
python -m scraper parse-anketa-samples 1999-kovo-21-seimo-pakartotiniai

python -m scraper fetch-sample 1998-lapkricio-15-seimo-pakartotiniai
python -m scraper sitemap 1998-lapkricio-15-seimo-pakartotiniai
python -m scraper fetch-candidate-samples 1998-lapkricio-15-seimo-pakartotiniai --allow-new-samples \
    --candidate-id terleckas-antanas
python -m scraper parse-anketa-samples 1998-lapkricio-15-seimo-pakartotiniai
```

Resumable full scrape (1996 general election only — the five by-elections
are already small enough that `fetch-candidate-samples` covers the complete
field in one call):

- `scripts/run_election_batches.sh 1996-spalio-20-seimo`

## Municipal archive (`1997-kovo-23-savivaldybiu-tarybu`, `1997-birzelio-29-svenciniu-tarybos-pakartotiniai`) Workflow

The 1997-03-23 municipal council general election and the 1997-06-29
Švenčionys repeat share the `19970323` directory and the shared parser in
`scraper/shared/savivaldybiu_archive_1997.py`. Unlike the Seimas archive
above, listing candidates here is a **three**-hop crawl and richer once you
reach a candidate:

- `apgtl.htm-<phase>+<municipality>.htm` (municipality) → table of
  parties/coalitions, each linking to `pkal.htm-<...>.htm` (that party's
  numbered candidate list in that municipality) → `kandvl.htm` (candidate).
  A directory page (`apgsavl.htm-3.htm`) enumerates all 56 municipalities for
  the general election; the Švenčionys repeat hardcodes its one municipality
  (No. 47) instead, the same way the Seimas by-elections hardcode theirs.
- The general election's phase prefix is `3` (filed 1997-05, before the
  1997-03-23 vote); the Švenčionys repeat's is `5` (filed 1997-05-20/23,
  after VRK invalidated the original result there and re-ran it 1997-06-29) —
  confirmed by diffing the two municipality pages, which differ only in
  filing dates and candidate rosters, not in page shape.
- The candidate page has no comment-corruption quirk (unlike the Seimas
  family): birth date/place, residence, nationality, education, academic
  degree and title, foreign languages, main workplace, public activity,
  family status and family members are all plain labelled paragraphs, carried
  into `rawData.personal`/`normalized.anketa`. The academic degree and title
  went unread until issue #69 (156 and 112 records in the general election),
  because the shared label list did not name them — and that list is a stop
  list as well as a dispatch list, so an unnamed label can also be swallowed
  into the value before it, which is what once put
  `1945 04 17 Gyvenamoji vieta: Kaunas Tautybė: …` into 91% of birth dates.
  Both families now share `scraper/shared/archive_1990s_card.py`, which
  carries the union of their labels. As with the Seimas
  archive, `kpdl.htm` (income declaration) is fetched and parsed into
  `normalized.turto-ir-pajamu-deklaracijos`. This is the family whose section
  III "Iš viso" row usually prints 0 against a non-zero row 1, so most of its
  records carry a null `gautos-pajamos` and a populated
  `gautos-pajamos-darbo-santykiu`; see `docs/OUTPUT_SCHEMA.md`, and resolve
  income through the `deklaruotos-pajamos` concept rather than the key
  (`scraper/shared/deklaracijos.py`).
- 46 candidate name collisions across the 6,276-candidate general election
  resolve with the same positional `-2` suffix the other families use — e.g.
  two different people named `Tamulevičius Kęstutis` (VRK ids 37862 and
  37809) become `tamulevicius-kestutis` and `tamulevicius-kestutis-2`; see
  `tests/test_savivaldybiu_1997_anketa_parser.py`.

```bash
python -m scraper fetch-sample 1997-kovo-23-savivaldybiu-tarybu
python -m scraper sitemap 1997-kovo-23-savivaldybiu-tarybu
python -m scraper fetch-candidate-samples 1997-kovo-23-savivaldybiu-tarybu --candidate-id pilvelis-algirdas --allow-new-samples
python -m scraper parse-anketa-samples 1997-kovo-23-savivaldybiu-tarybu

python -m scraper fetch-sample 1997-birzelio-29-svenciniu-tarybos-pakartotiniai
python -m scraper sitemap 1997-birzelio-29-svenciniu-tarybos-pakartotiniai
python -m scraper parse-anketa-samples 1997-birzelio-29-svenciniu-tarybos-pakartotiniai
```

Resumable full scrape (the general election only — 449 party lists, 6,276
candidates across all 56 municipalities; the Švenčionys repeat's 110
candidates are the complete field already covered above):

- `scripts/run_election_batches.sh 1997-kovo-23-savivaldybiu-tarybu`, with
  `KEEP_SAMPLES=1` — at this size a later parser fix should be an offline
  re-parse, not hours of repeat traffic to vrk.lt.

## Presidential 2002 (`2002-prezidento`) Workflow

The 2002-12-22 presidential election (GitHub issue #27; VRK's
`rinkimai/2002/Prezidentas/` tree — capital P), held with the municipal
general on one day; Rolandas Paksas beat Valdas Adamkus in the
January 5, 2003 runoff. The 2002 LRS-ITD site is one generation before
the 2004 static site, read by `scraper/elections/prezidento_2002/`, and
it splits a candidate three ways: **text that survives as text, Word
documents, and scans**. The module's rule: parse the first two, archive
and link the third, never OCR — a guessed transcription of a 2002 paper
form photograph would be worse than none.

- **Listing**: `kandidatai.htm`, the seventeen candidates as profile
  cards. Each card carries the name, VRK's candidate id (the card's own
  `<a name>` anchor), the photo, the registration sentence with the
  decision linked on lrs.lt ("2002 m spalio 29 dienos VRK sprendimu
  Nr. 91 registruotas kandidatu…" — "m" without the dot), the campaign
  site for eleven (V. A. Matulevičius's card links two), and the
  document links. The trustee index survives as the **id map**: each
  name links `asm_rduom_id=<RID>`, VRK's registration record id — the
  id space the results pages key on — while every per-candidate trustee
  page behind it is a 404, so `patiketiniai` is an unpublished tab. The
  sitemap joins listing and trustee index on the candidate's name
  (unique among the seventeen on both pages) and reconciles rather
  than skips.
- **Parseable pages**: the biography is HTML
  (`docs/Biografijos/<Name>_biografija.htm` — header headings, then the
  prose as sibling blocks), the programme a Word 97 `.doc`
  (`docs/Programos/…`, read by `scraper/shared/word_doc.py` — Bobelis's
  runs to 86 KB of manifesto; Šerėnas's is one line, his campaign aired
  on LNK). Birth facts are recovered from the biography's opening
  sentence under the 1990s archive family's keys: sixteen of seventeen
  full dates, and Bernatonis's "Gimė 1940 metais" — the spelled-out
  year that widened the shared year pattern (three 1996 records and one
  1997 record gained a year from the same fix).
- **Scans, archived and linked**: the pretender's statement
  (`_pareiskimas.jpg`), the two-page data questionnaire
  (`_anketa1/_anketa2.jpg`), the asset-and-income declaration
  (`_deklaracija.jpg` — the link label names the form, "Šeimos" on
  eleven cards and "Gyventojo" on six) and the health certificate on
  four cards. The JPGs are fetched as bytes into the sample set and their
  URLs live on the record (`rawData.skenai`, the profile fields); no
  `turto-ir-pajamu-deklaracijos` section exists, because no declaration
  figures exist as text. Two gaps are the source's own: the four
  health-certificate scans are 404 on VRK's mirror (the Wayback Machine
  holds four of the five files), and Šustauskas's second questionnaire
  page was a 404 on the original 2002 site already — both recorded as
  unpublished, neither fetched nor warned about.
- **Results**: the tree's two national pages
  (`rezultatai/rezl.htm-14+1.htm`, `-14+2.htm`) — summary paragraph and
  one row per candidate with votes at the stations / by post / in total
  and both percentages, rows keyed `rezkapgl.htm-<RID>+<round>.htm` by
  the registration record id — and the final protocol
  (`rezultatai/protokolas/index.html`), whose verdict names the winner
  in the accusative ("išrinko Rolandą Paksą Respublikos Prezidentu"),
  resolved against the two runoff candidates by word-stem prefix.
  Both rounds' votes are joined into each record as
  `kandidatavimas.turai` (the 2004 module's loader reads them, the
  shape is one and the same); the winner gets `isrinktas: true`,
  `isrinktasKaip: "prezidentas"`, `rezultatuTuras: 2`.

```bash
python -m scraper fetch-sample 2002-prezidento
python -m scraper sitemap 2002-prezidento
python -m scraper fetch-candidate-samples 2002-prezidento --allow-new-samples --candidate-id rolandas-paksas
python -m scraper build-results 2002-prezidento
python -m scraper parse-anketa-samples 2002-prezidento
```

Fixtures are the complete seventeen-candidate field
(`tests/test_prezidento_2002_sample_allowlist.py`), so the fixture
capture *is* the full scrape. Scraped 2026-08-24: 17/17, 0 fetch
failures, 0 anomalies; ~9 MB with the scans.

## Municipal general 2002 (`2002-gruodzio-22-savivaldybiu-tarybu`) Workflow

The 2002-12-22 municipal council general election (GitHub issue #28;
VRK's `rinkimai/2002/savivaldybes/` tree), held the same day as the
presidential first round, on the same 2002 LRS-ITD site generation —
but published as per-candidate static pages, not scans, so unlike
`2002-prezidento` everything parses. Read by
`scraper/elections/savivaldybiu_2002/`:

- **Listing**: two structures. The constituency index links the 60
  municipality pages
  (`kandidatai_apygardoje_jsp_ri_id_15_apyg_id_<APYG>.htm`), each the
  full field grouped under bold "N. <list name>" headings — the
  position, the anketa link and the "pajamų deklaracijos" link per
  candidate, both keyed by `asm_kod`, VRK's person id. The party index
  links the 25 party pages, each linking the party's per-municipality
  pages (the same document narrowed to the party's own candidates) —
  the overlay that resolves each list's kind and a coalition's members:
  a heading exactly one party claims under its own name is that party's
  list, anything else a coalition of the claimants (A. Zuoko koalicija
  in Vilnius stands under the Liberals' number 26 and is claimed by the
  Liberals and the Moderate Christian Democrats). **10,139 candidates
  on 521 lists (15 coalitions) in 60 municipalities**, every candidate
  claimed by exactly one party page at the same position, no duplicate
  ids anywhere (ids are `<slug>-<asm_kod>` as for the other municipal
  generals), a declaration link on every row. The heading numbers are
  the party index's own ballot numbers (gapped — no 7), constant across
  municipalities, and the join key to the results tree's list rows.
- **Candidate pages**: two per candidate, each one table cell of
  `<br>`-separated `N. Prompt: <b>answer</b>` lines — the anketa
  (Q5–Q19 with gaps: birth date already ISO, residence, the 8.1–8.3
  declarations, the 88 str. conviction question at Q9 with the
  article's text as an italic boilerplate block, birth place,
  nationality, education as a level, languages in one bold with
  commas, prior mandates at Q15 inline ("Nebuvo") or as indented
  "nuo/iki + institution" lines, workplace, public activity, marital
  status with unnumbered spouse/children lines trailing it; Q19
  omitted entirely on some pages) and the declaration extract
  ("Lietuvos Respublikos gyventojo turto ir pajamų deklaracija",
  saved as `turto-ir-pajamu-deklaracijos.html`) — litas summary lines
  matched on wording because an inserted joint-bank-accounts item
  shifts the numbering between the 11- and 12-item variants. The
  pages carry no candidacy facts: municipality, list and position are
  the sitemap's, in the 2000/2007 municipal candidacy shape.
- **Results**: `savivaldybiu_2002/results.py`. Per municipality
  `rezultatai/rapgpl_<APYG>.htm` (voters, turnout, valid/invalid
  ballots, quota, votes and mandates per list — "-" below the
  threshold — with a totals row), `rezultatai/rikl_<APYG>.htm`
  ("Kandidatai, gavę mandatus", the `isrinktas` source), per list
  `rezultatai/rpbapgl_<APYG>_<SEQ>.htm` (post-election rank,
  preference votes, pre-election number, winners in bold, the list's
  own total above) and `savtaryb/sav_apg_l_<APYG>_1.htm` — the council
  **as frozen**, where a substitute's row (dated by its entry) replaces
  a departed member's; the dates join as `tarybosNarysNuo`. **1,560
  seats across all 60 municipalities**, every count reconciling: the
  members pages against their own declared seat counts, the mandate
  columns and the totals rows, the bold preference rows and the top-N
  ranks; all 10,139 candidates ranked with the listing's pre-election
  number; every election-day council row an elected member, 562
  members replaced mid-term by 562 substitutes (all of them
  candidates of the same election); the national mandate summary
  (`mandatai/mlt_15_1.html`, per member party) summing to the same
  1,560 — all at 0 mismatches.

```bash
python -m scraper fetch-sample 2002-gruodzio-22-savivaldybiu-tarybu
python -m scraper sitemap 2002-gruodzio-22-savivaldybiu-tarybu
python -m scraper fetch-candidate-samples 2002-gruodzio-22-savivaldybiu-tarybu --candidate-id anicetas-lupeika-132972 --allow-new-samples
python -m scraper build-results 2002-gruodzio-22-savivaldybiu-tarybu
python -m scraper parse-anketa-samples 2002-gruodzio-22-savivaldybiu-tarybu
KEEP_SAMPLES=1 scripts/run_election_batches.sh 2002-gruodzio-22-savivaldybiu-tarybu
```

Fixtures are ten candidates chosen by shape
(`tests/test_savivaldybiu_2002_sample_allowlist.py`). The full field was
scraped 2026-08-24 with retention: 10,138 of 10,139 (one candidate's
pages are 404s — see `docs/DATASET.md` Known gaps), 4 anomalies, all of
them verified source blanks.

## European Parliament 2004 (`2004-ep`) Workflow

Lithuania's first EP election (2004-06-13, VRK's `rinkimai/2004/euro/`
tree; GitHub issue #31), one month after accession — and the only election
of the corpus published on VRK's **original 2004 static site** (the LRS-ITD
page template), which sits between the 1996-1998 Teleport archive and the
2015-era layout that every election from 2007 on shares. A layout family
of its own, read by `scraper/elections/ep_2004/`:

- **Listing**: the same index-and-lists shape as 2009/2014 EP — an index
  of the 12 party lists (VRK number, name, declared size), each a page of
  candidates in list order, no constituencies — so `ep_2014`'s walk runs
  with this tree's link patterns (`kand_part_l_<ID>.htm`,
  `kand_anketa_l_<ID>.htm`; the `_l_` is the Lithuanian page, an `_e_`
  English twin exists and is not read). One thing the walk had to learn:
  the 2004 pages lay everything out in nested tables, so an outer layout
  row *contains* every candidate anchor — only the row an anchor sits in
  directly is a candidate row (a no-op on the flat 2009/2014 tables; read
  naively the walk counted 277 rows for 241 and lost every list position).
  241 candidates on 12 lists, every list equal to its declared size, no
  name collisions.
- **Candidate pages**: three static pages, no tab bar. The questionnaire
  (`kand_anketa_l_`) is a profile card — photo, "Iškėlė:" linking the
  list page, "priešrinkiminis numeris sąraše:" — over one `r1`/`r2` row
  per question in `N. Prompt: <b>answer</b>` form: list-type answers as
  several `<b>` with commas between (languages, hobbies, children; the
  joined string is the row's answer, the items kept as `answerItems`),
  the education and prior-mandate record tables as bordered `table.basic`
  with a bold column-name row, and two unnumbered "label: <b>…</b>" pairs
  trailing a question in the same cell (the degree and academic title after
  the education table — "Moksliniai laipsniai" / "Moksliniai vardai" — and
  the spouse after Q19). An unanswered question is printed with an empty
  `<b>`, which closes its row. The biography (`kand_biog_l_`) is one
  free-text paragraph in a blockquote. The declarations page
  (`kand_pajam_l_`, "Pajamų ir turto deklaracijų pagrindinių duomenų
  išrašai") prints two extracts — the asset declaration (family form on
  144 pages, individual form on 97; sections I–V with one total each) and
  the resident's income declaration (one income/tax pair for each of the
  five FR0462 form variants VRK knew of, "-" for the ones not filed; the
  declared income is the sum of the lines; two candidates filed on more
  than one form) — each with the issuing tax office, receipt date, filing
  date and workplace. No private-interest declaration (the ID001 form was
  not yet required of EP candidates), no "Kita", no campaign page (the
  2004 site publishes campaign finance as per-party PDF reports). The
  fetcher is the 2015-era one with this module's link extractor; files
  land under the corpus's usual names (`anketa.html`, `biografija.html`,
  `turto-ir-pajamu-deklaracijos.html`).
- **Question set**: the 2009 EP form five years earlier, keyed with
  `ep_2009`'s names — `ep_2004.normalize_ep_2004_anketa_rows`. Birth date
  is Q3 (printed "1942.01.01"; `anketa.gimimo-data` is the corpus's ISO
  form, the key the person index joins on); the rinkimų į Europos
  Parlamentą įstatymo declarations are Q8.1, 8.2 and **8.4** (another
  member state's citizenship, with 8.4.1 "Kurios" and 8.4.2 on the vote
  there — the 2009 form's 8.3/8.3.1/8.3.2; there is no 8.3), kept under
  the 2009 keys; the lustration and conviction questions are Q9.1–9.3;
  the Q9 block's free-text explanation is printed as an **unlabelled
  emphasised row right after 9.3** on the five pages that have one →
  `pareiskimai.teisiniai-argumentai`. Answers are the form's third-person
  wording — `Neturi`/`Turi`, `Nėra`/`Yra`, `Nebuvo`/`Buvo` — kept as
  published, as every era's are; count convictions on 9.2 = `Yra`
  (three) and 9.3 = `Buvo` (one more). Q10–Q21 are as every later form
  asks them. One page (Šiškauskienė) omits Q19, the spouse line and Q20
  altogether; two (Imbrasas, Kundrotas) answer almost nothing.
- **Results**: the 2004 tree's own pages, walked by `ep_2004/results.py`
  (the shared EP builder keys on the later `Kandidato<ID>Anketa` pattern).
  `rez_isrinkti_l_18_1.htm` lists the 13 members with anketa links and
  names, in a footnote, the one substitution: Prunskienė's mandate was
  declared terminated at her own request (VRK decision Nr. 180 of
  2004-06-21) and the list's next member, Didžiokas, recognised as elected
  in her place (Nr. 181), both linked to the decisions on lrs.lt. **Both
  are recorded as elected** — VRK's page lists both and calls the
  replacement "išrinktu" — so 14 records carry the flag for 13 seats,
  with `kandidatavimas.mandatasNutrauktas` on hers (decision, statement,
  `replacedBy`) and `pakeiteNari` / `vrkSprendimas` on his. Two
  cross-checks, both at 0: the national page's mandate column per list
  (5+2+2+2+1+1) against the members table, and the 12 per-list ranking
  pages (`rez_pirm_l_<list>.htm`, winners in bold) against the members.
  The ranking pages also give every candidate's post-preference rank and
  preference votes, joined into the record as
  `kandidatavimas.porinkiminisNumerisSarase` / `pirmumoBalsai` (the modern
  cards print the former; here it is a results join); the pre-election
  position they repeat equals the listing's for all 241.

```bash
python -m scraper fetch-sample 2004-ep
python -m scraper sitemap 2004-ep
python -m scraper fetch-candidate-samples 2004-ep --candidate-id justas-vincas-paleckis --allow-new-samples
python -m scraper build-results 2004-ep
python -m scraper parse-anketa-samples 2004-ep
KEEP_SAMPLES=1 scripts/run_election_batches.sh 2004-ep
```

Fixtures are thirteen candidates chosen by shape
(`tests/test_ep_2004_sample_allowlist.py`); the full field was scraped
2026-08-23 with retention (241/241, 0 fetch failures, 0 anomalies, 8.7 MB
under `samples-full/2004-ep/`).

## Presidential 2004 (`2004-prezidento`) Workflow

The 2004-06-13 presidential election (GitHub issue #30; VRK's
`rinkimai/2004/prezidentas/` tree) — called early after the April 2004
impeachment, held with the EP election on one day, won by Valdas Adamkus
over Prunskienė in the June 27 runoff. The third member of the 2004
static site family, read by `scraper/elections/prezidento_2004/`, and
unlike its siblings it publishes **one shared listing page, not a page
per candidate** — and the biography and programme as **Word documents**,
the corpus's only non-page source:

- **Listing**: `kandidatai_l_19.htm`, the five candidates as profile
  cards. Each card carries the name and VRK's candidate id (the card's
  own `<a name>` anchor), the photo thumbnail (full portrait behind
  `nuotrauka_<ID>.htm`), the registration sentence with the VRK decision
  linked on lrs.lt ("2004 m. gegužės 12 dienos VRK sprendimu Nr. 120
  registruotas kandidatu…"), and the candidate's links: the declaration
  extracts (`kand_pajam_l_<ID>.htm`, the family's usual page and the
  card's only per-candidate HTML), the trustees
  (`patiketiniai_l_<RID>.htm` — a **second id space**, VRK's
  registration record id, which the results tree reuses; the page itself
  is a 404 for all five, linked but never published, so it goes to
  `unpublishedTabs` as the 2009 presidential trustees did), the
  biography and programme as Word 97 `.doc` (Auštrevičius published no
  programme), the scanned statement GIF (and, on Adamkus's card only,
  the health certificate GIF), and the campaign site. The sitemap
  reconciles rather than skips: five cards, both ids on every card, the
  declaration id equal to the card anchor.
- **Candidate page-set**: the module's own fetcher (the era fetcher
  assumes text pages) saves the shared listing as each candidate's
  `anketa.html`, the declarations under the corpus's usual name, the
  documents as `biografija.doc` / `programa.doc` — fetched as **bytes**
  (`fetch_bytes`; a `.doc` run through text decoding is corrupt beyond
  repair) — and the portrait page as `nuotrauka.html`. `programa` is
  expected per entry, only where the card links one.
- **Word documents**: `scraper/shared/word_doc.py`, a dependency-free
  Word 97 reader — OLE container, FIB, the Clx piece table (document
  order even for fast-saved files), main-document range only (the VRK
  files keep a page-header subdocument beyond `ccpText`), field codes
  keep result text and lose instruction text. All ten documents extract
  clean Lithuanian text. The record keeps the text under
  `rawData.biografija` / `rawData.programa` (with the source URL) and
  `normalized.biografija.tekstas` / `normalized.programa.tekstas`.
- **Birth facts**: no questionnaire exists in this tree, so the birth
  date is recovered from the biography's opening sentence ("Valdas
  Adamkus gimė 1926 m. lapkričio 3 d. Kaune…") under the 1990s archive
  family's keys and caveats — `anketa.gimimo-data` with
  `gimimo-data-saltinis: biografijos-tekstas`. All five biographies
  state the full date; the person index joins all five to their careers
  across the corpus (Adamkus to his residency-establishing 1997 Šiauliai
  council run, Prunskienė to nine elections).
- **Results**: the tree's two national pages, walked by
  `prezidento_2004/results.py`: `rez_l_19_1.htm` (first round — summary
  block, one row per candidate with votes at the stations / by post / in
  total and both percentages, the runoff qualifiers' names in bold) and
  `rez_l_19_2.htm` (the runoff, closed by the verdict "Respublikos
  Prezidentu išrinktas - Valdas ADAMKUS" with the name linked to the
  listing's card anchor). Every join is by id: candidate rows link
  `rez_kand_l_<RID>_<round>_1.htm` under the registration record id from
  the sitemap, the verdict's anchor fragment is the candidate id itself.
  Both rounds' votes are joined into each record as
  `kandidatavimas.turai`; the winner gets `isrinktas: true`,
  `isrinktasKaip: "prezidentas"`, `rezultatuTuras: 2`.

```bash
python -m scraper fetch-sample 2004-prezidento
python -m scraper sitemap 2004-prezidento
python -m scraper fetch-candidate-samples 2004-prezidento --allow-new-samples \
  --candidate-id valdas-adamkus --candidate-id petras-austrevicius \
  --candidate-id vilija-blinkeviciute --candidate-id ceslovas-jursenas \
  --candidate-id kazimira-danute-prunskiene
python -m scraper build-results 2004-prezidento
python -m scraper parse-anketa-samples 2004-prezidento
```

Fixtures are the complete five-candidate field
(`tests/test_prezidento_2004_sample_allowlist.py`), so the fixture
capture *is* the full scrape — as for the 2005 Kėdainiai by-election.
Scraped 2026-08-24: 5/5, 0 fetch failures, 0 anomalies.

## Seimas 2004 (`2004-seimo`) Workflow

The 2004-10-10 Seimas general election (GitHub issue #32; VRK's
`rinkimai/2004/seimas/` tree), four months after the EP election on the
same original static site: the same candidate pages, read by `ep_2004`'s
readers with the Seimas question mapping and a richer profile card, and
the 2008/2012 two-structure listing on the 2004 template.
`scraper/elections/seimo_2004/`:

- **Listing**: `part_sar_l_20.htm` indexes the party pages — the 15
  numbered lists, three "tik vienmandatėse" parties and the four coalition
  member parties ("koalicijos sąrašas Nr. 6/8"), as in 2012 — and
  `vapg_sar_l_20.htm` the 71 constituencies (two cells of
  "N. <a>name</a>" runs, not a table). Three things the 2004 party pages
  do that the module's own walk reads: a party's page lists **every**
  nominee of the party — its list in order and, unnumbered below it, the
  people it nominated in a constituency only — so the index's declared
  count is the party's nominees and an unnumbered row carries no list
  candidacy (9 such rows on the numbered lists, all on a constituency
  page under the same party); a coalition's page rows the coalition list
  with each candidate's member party and position on the member's own
  list (`koalicijosPartija`, `numerisPartijosSarase`), which the member
  party's page repeats the other way round and the walk cross-checks
  (140 = 99 + 41, 137 = 121 + 16, every position agreeing); and a list
  page's "Vienmandatė apygarda" column shows only constituencies where
  the *same* party nominated the candidate, so the constituency page is
  the authority on the single-member candidacy (17 people sit on one
  party's list and another's constituency nomination — the Lietuvos rusų
  sąjunga, a constituency-only party, ran its people where they also sat
  on the LLRA list). Merged on VRK's id: **1,251 candidates** — 534 in
  both structures, 649 list-only, 68 constituency-only (10 of the
  constituency-only parties, 46 self-nominated "Išsikėlė pats/pati", 3
  coalition-member nominees standing in a constituency only, 9 numbered-
  list parties' constituency-only nominees), every declared count met,
  no name collisions.
- **Candidate pages**: the three 2004 pages (`ep_2004` workflow above),
  with the Seimas card: "Apygarda: <constituency> (Nr.N)" and "Iškėlė:"
  for the single-member candidacy, "Apygarda: Daugiamandatė", "Iškėlė:
  <list>, priešrinkiminis numeris sąraše: N" for the list one, the
  coalition member party and its position in parentheses (2012's
  `iskele-3`), and for the 455 independent campaign participants a
  closing "Kandidatas registruotas savarankišku politinės kampanijos
  dalyviu. Sprendimas - <a>Nr…, date</a>" linking the registration
  decision as a PDF — a card field (`profilis.kita`) and
  `kandidatavimas.savarankiskasKampanijosDalyvis`, not a page. Two cards
  carry two constituency blocks (a party nominee who also self-nominated
  there; the constituency page says only "Išsikėlė pats") →
  `vienmandate.kitiIskelejai`. One candidate (Žiobakienė) has no
  declarations page at all — no link on the card, the URL a 404 — so the
  fetcher records a `MissingExpectedTab` and the record has no
  declarations section; one page (Matkevičius) prints the income extract
  only. The 2004 page readers learned one thing here, a no-op on the EP
  pages: an unanswered degree or title drops its `<b></b>`, so
  "Moksliniai laipsniai: Moksliniai vardai:" arrives as one text run and
  is split into its two rows.
- **Question set**: the Seimo rinkimų įstatymo form the 2008–2013 pages
  ask, keyed with the 2016 Seimo names — `seimo_2004.normalize_seimo_2004_anketa_rows`:
  Q8.3 another state's citizenship (`ar-turite-kitos-valstybes-pilietybe`),
  Q8.4 an oath to a foreign state (`ar-susijes-priesaika-uzsienio-valstybei`),
  Q9.1–9.3 the 98 str. questions; birth date Q3 (ISO in normalized), the Q9
  explanation the unlabelled row after 9.3 (ten pages), answers in the
  form's third person as on the EP pages (`Yra`/`Nėra`, `Buvo`/`Nebuvo`).
  Uniform across all 1,251 pages.
- **Results**: the tree's own pages, `seimo_2004/results.py`.
  `rez_isrinkti_l_20_1.htm` lists the 141 members by anketa id with the
  seat — "Daugiamandatė", or the constituency's number and name linking
  `rezv_apg_l_<district>_<round>.htm`, so the constituency id and the
  deciding round are on the row (5 first-round, 66 runoff) — and the
  party. Cross-checked by id against the list-seat page
  (`rezd_isrinkti_l_20_1.htm`, 70) and the two constituency-winner pages
  (`rezv_isrinkti_l_20_1_1.htm`, `…_2_1.htm`), against the national
  page's mandate column per list, against the sitemap's roles and
  constituency ids, all at 0. The 15 `rez_pirm_l_<list>.htm` ranking
  pages give every list candidate's rank and preference votes, joined as
  for the EP election — except the LLRA list, which "Lietuvos lenkų
  rinkimų akcijos prašymu … nebuvo reitinguojamas": its page prints rank
  (= list order) and name only, so its 128 candidates carry
  `porinkiminisNumerisSarase` and a null `pirmumoBalsai`. The
  per-constituency results pages row candidates under a results-system id
  of their own, not the anketa id, so constituency vote counts are not
  joined.

```bash
python -m scraper fetch-sample 2004-seimo
python -m scraper sitemap 2004-seimo
python -m scraper fetch-candidate-samples 2004-seimo --candidate-id valentinas-mazuronis --allow-new-samples
python -m scraper build-results 2004-seimo
python -m scraper parse-anketa-samples 2004-seimo
KEEP_SAMPLES=1 scripts/run_election_batches.sh 2004-seimo
```

Fixtures are fourteen candidates chosen by shape
(`tests/test_seimo_2004_sample_allowlist.py`); the full field was scraped
2026-08-23 with retention (see `docs/DATASET.md`).

## New Seimo elections 2003 (`2003-birzelio-15-seimo-nauji`) Workflow

The 2003-06-15 vote for four seats that fell vacant in the 2000-2004
Seimas — Senamiesčio No. 2, Antakalnio No. 3, Šeškinės No. 6 and Nevėžio
No. 26 (GitHub issue #29; VRK's `rinkimai/2003/seimas/` tree) — is the
2004 static site one generation early, with the servlet's own page names
(`w3_smn_kand.<view>_l-id=<ID>.htm`). `scraper/elections/seimo_nauji_2003/`
reuses `ep_2004`'s row reader, `seimo_2004`'s question mapping and
`savivaldybiu_2002`'s declaration key map, and owns the page readers:

- **Listing**: `kand_vien_l-p_ri_id=17.htm` indexes the four
  constituencies (one row of "N&nbsp;<a>name</a>" cells, no trailing dot
  unlike 2004's) and `part_sar_l-p_ri_id=17.htm` the 12 nominating
  parties. The constituency pages are the source — name linking the
  anketa, "Iškėlė" linking the party — and the party pages, which name
  each nominee's constituency, are the cross-check: `partyPageDiff` is
  the symmetric difference of the two structures' (candidate,
  constituency, party) triples and must be 0. 27 candidates, all
  party-nominated, no lists.
- **Candidate**: the three 2004-era pages (anketa, autobiography,
  declaration extract) with four page-level deltas the module's readers
  handle — the profile card is the question table's first row and
  classed like a question, the birth date is Q5 not Q3, Q9.1-9.3 carry a
  `<sup>*</sup>` footnote marker between number and prompt, and the
  Q12/Q15 record tables print no header row (21 of the 27 education
  tables are a single row, which the era's reader would swallow whole as
  column names). The declaration is the 2002 municipal form in two
  variants — "gyventojo" on 18 pages, "šeimos" on 9 — with two prompts
  misspelled relative to 2002 ("negražintų", "paskolintų
  (nesugražintų)"), so the module extends the 2002 key map rather than
  restating it.
- **Results**: nobody was elected. Every constituency page says
  "Rinkimai apygardoje neįvyko" and the index footnotes all four, there
  is no members page and no second round, so `elected` is empty *by
  measurement* and all 27 records carry a known `isrinktas: false`.
  Unlike 2004's, these pages row candidates by the anketa id, so
  per-candidate votes join onto `kandidatavimas.turai`.

```bash
python -m scraper fetch-sample 2003-birzelio-15-seimo-nauji
python -m scraper sitemap 2003-birzelio-15-seimo-nauji
python -m scraper fetch-candidate-samples 2003-birzelio-15-seimo-nauji --candidate-id vilija-aleknaite-abramikiene --allow-new-samples
python -m scraper build-results 2003-birzelio-15-seimo-nauji
python -m scraper parse-anketa-samples 2003-birzelio-15-seimo-nauji
```

Fixtures are the complete 27-candidate field
(`tests/test_seimo_nauji_2003_sample_allowlist.py`), so the fixture
capture *is* the full scrape — as for the 2005 Kėdainiai by-election.
Scraped 2026-08-28: 27/27, 0 fetch failures, 0 anomalies.

**The photo URL carries the candidate's asmens kodas.** The filename is
the national ID number (`…/kandidatai/ 45705040120_17.jpg` for a
candidate whose Q5 reads `1957 05 04`, true on all 27), so it is kept as
a source link and nothing is derived from it — ids come from
`kand_anketa_l-id=` and birth dates from the questionnaire. The `src`
also has a stray space before the filename, which the reader strips
because the URL 404s with it.

## Seimo by-election 2005 (`2005-lapkricio-20-seimo-kedainiai`) Workflow

The 2005-11-20 new election in Kėdainių No. 43 (GitHub issue #33; the
seat Viktor Uspaskich gave up) is the 2004 Seimas tree one year on —
`rinkimai/2005/seimas/`, the same original static site — and
`scraper/elections/seimo_kedainiu_2005/` is thin wiring over
`seimo_2004`: its constituency reader for the one district (`apg_kand_l_1675.htm`,
five candidates with their nominators; the party index, five parties one
nominee each, is the cross-check), `ep_2004`'s fetcher links and page
readers with the Seimas mapping and card hook (four of the five are
independent campaign participants with the registration decision PDF),
and the 2004 members-page reader for the results: `rez_isrinkti_l_21_1.htm`
rows the one winner with the constituency linking
`rezv_apg_l_1675_2.htm` — decided in the runoff (26% turnout in the first
round) — cross-checked against the runoff winners page
(`rezv_isrinkti_l_21_2_1.htm`; the first-round page is a 404). Fixtures
are the complete five-candidate field.

```bash
python -m scraper fetch-sample 2005-lapkricio-20-seimo-kedainiai
python -m scraper sitemap 2005-lapkricio-20-seimo-kedainiai
python -m scraper fetch-candidate-samples 2005-lapkricio-20-seimo-kedainiai --candidate-id virginija-baltraitiene --allow-new-samples
python -m scraper build-results 2005-lapkricio-20-seimo-kedainiai
python -m scraper parse-anketa-samples 2005-lapkricio-20-seimo-kedainiai
```

## Seimas 2000 (`2000-seimo`) Workflow

The 2000-10-08 Seimas general election (GitHub issue #26; VRK's
`statiniai/puslapiai/n/rinkimai/20001008/` tree) is the last of the
LRS-ITD Oracle-CGI captures — the 1996-1998 Seimas archive's template
(`scraper/shared/seimo_archive_1990s.py`'s `kandvl.htm-<ID>.htm` candidate
page) carrying the 2004 static site's content — and
`scraper/elections/seimo_2000/` is its own module over two shared pieces:
`seimo_2004.sitemap.merge_listing_records` for the two-structure listing
merge and the 1990s declaration parser for the income extract.

- **Listing**: `partsarl.htm-13.htm` indexes the 15 numbered lists and,
  unnumbered below them, the 13 parties that "kandidatų daugiamandatėje
  apygardoje išvis nekelia arba dalyvauja koalicijoje"; `kandapgsarl.htm-13.htm`
  the 71 constituencies (`kandapgl.htm-13+<number>+<ID>.htm`). The party
  pages behave as the 2004 ones — a party's page lists every nominee (its
  list, then unnumbered constituency-only nominees; 19 such rows), a
  coalition's page rows the coalition list with the member party and its
  position on the member's own list, a member party's page repeats the
  coalition position — but the index does not say which unnumbered party
  is a coalition member: the pages do ("Partijos ir politinės
  organizacijos, dalyvaujančios koalicijoje:" on the coalition's,
  "Koalicija, kurioje partija dalyvauja:" on the member's), so the kinds
  are resolved after the pages are read and the two statements
  cross-checked (4 members of the one coalition, A.Brazausko
  socialdemokratinė koalicija, every link reciprocated; 9 constituency-
  only parties). Merged on VRK's id: **1,271 candidates** — 582 in both
  structures, 569 list-only, 120 constituency-only (52 of the
  constituency-only parties, 48 self-nominated, 19 numbered-list parties'
  constituency-only nominees and **one VRK gap**: Virginijus Šmigelskas
  is the Lietuvos centro sąjunga's nominee on the Širvintų–Vilniaus page
  but absent from the LCS party page, which lists his namesake Vidmantas
  at #48 — the constituency page is the authority, so he is in; the
  merge's `districtOnlyUnaccounted` names the count). 29 people sit on
  one party's list and another's constituency nomination (the LTS list's
  people standing for Lietuvos nacionaldemokratų partija and Lietuvos
  laisvės lyga, the TS list's for the political prisoners' union), 8
  self-nominated in a constituency while on a list. Three namesake pairs
  (different VRK ids and parties) take the positional `-2` id.
- **Candidate page**: one document per candidate — the card (photo, one
  "Apygarda:"/"Iškėlė:" block per candidacy with ", šioje apygardoje
  išrinktas Seimo nariu" where the candidate won that seat, the list
  number and, for the coalition's candidates, "(iškėlė <member party>,
  buvęs numeris sąraše: N)"; birth date, sometimes birthplace, residence),
  the seven Seimo rinkimų įstatymo declarations (8.1–8.4, 9.1–9.3, the
  2004–2013 Q8/Q9 set) in a small-font run — with 8.3.1 "Kurios" and
  8.4.1 "Jei yra, kaip ir kada raštu … atsisakė" printed under a
  non-default 8.3/8.4, the latter sometimes with no `<b>` at all so the
  next prompt runs on (the reader splits the run at every question
  number), and the Q9 explanation as an unlabelled run after 9.3 — the questionnaire fields as
  "Label: <b>value</b>…" paragraphs (education as "YYYY - school,
  qualification" lines, degree, title, languages, prior mandates,
  workplace, public activity, hobbies, marital status, family members
  with the relation — no nationality, no party membership; a blank field
  is not printed), the 1996-1997 income and asset declaration form inline
  with the figures to the centas and the section-I workplace lines filled
  in, and the autobiography. No tabs, no sub-pages: saved as
  `candidate.html`. Keys are the 2004 Seimas ones wherever the content is
  the same (`anketa.pareiskimai`, `issilavinimas.irasai`, …) plus
  `anketa.seimos-nariai`, and the 1990s family's declaration keys plus
  `darboviete`/`pareigos`. The card's winner note is kept in
  `profilis.pastaba` and cross-checked against the results join
  (`ElectedNoteMismatch`); the card's constituency, list number and member
  party against the sitemap (`Card…Mismatch`); a second constituency
  nominator on the card → `vienmandate.kitiIskelejai` (Juknevičienė:
  self-nominated and TS-nominated in Lazdynai). A card label outside the
  parser's table is an `UnmappedCardLabel` warning, so a new field would
  be noticed rather than lost.
- **Results**: `seimo_2000/results.py`. `ril.htm-13+2.htm` lists the 141
  members by candidate-page id with the seat ("Daugiamandatė", or the
  constituency linking `rvapgl.htm-<district>.htm`) and nominator;
  `rdl.htm-13.htm` the votes, share and mandates per list (70, matching
  the members page per list) and the links to the 15 `rdpbl.htm-<list>.htm`
  preference pages — every list ranked in 2000, LLRA included — giving
  rank, pre-election number, preference votes, VRK's party rating and the
  rating points (`porinkiminisNumerisSarase`, `pirmumoBalsai`,
  `partinisReitingas`, `reitingoBalai`); the 71 `rvapgl.htm-<district>.htm`
  pages row every constituency candidate under the candidate-page id
  (unlike 2004), so each gets `vienmandatesBalsai` (ballot-box, postal,
  total, share, place). Every constituency was decided in one round by
  plurality ("Rinkimai apygardoje įvyko. Seimo nariu išrinktas
  kandidatas, už kurį paduota daugiausia balsų" on all 71), the top row
  of every page is the members page's winner, and the list seats are
  exactly each list's top ranks after passing over the 54 constituency
  winners who also ranked — every cross-check at 0.

```bash
python -m scraper fetch-sample 2000-seimo
python -m scraper sitemap 2000-seimo
python -m scraper fetch-candidate-samples 2000-seimo --candidate-id andriukaitis-vytenis-povilas --allow-new-samples
python -m scraper build-results 2000-seimo
python -m scraper parse-anketa-samples 2000-seimo
KEEP_SAMPLES=1 scripts/run_election_batches.sh 2000-seimo
```

Fixtures are eighteen candidates chosen by shape
(`tests/test_seimo_2000_sample_allowlist.py`); the full field was scraped
2026-08-23 with retention (see `docs/DATASET.md`). 32 of the 1,271 pages
are VRK's pre-results capture (links to the live CGI, no winner note):
two winners among them get the `ElectedNoteMismatch` warning, and the
results join stands.

## Municipal general 2000 (`2000-kovo-19-savivaldybiu-tarybu`) Workflow

The 2000-03-19 municipal council general election (GitHub issue #25;
VRK's `statiniai/puslapiai/n/rinkimai/20000319/` tree) is the 1997
municipal archive three years on — the same Teleport capture of the
LRS-ITD CGI site and the same three-hop listing — with the October 2000
Seimas election's candidate document. `scraper/elections/savivaldybiu_2000/`
is its own module over the 1997 list-page reader, the 2000 Seimas page
readers and the 1990s declaration parser.

- **Listing**: the municipality directory the index links
  (`apgsarl.htm-12.htm`) is a 403 on vrk.lt, so the 60 municipalities
  come from the results index (`rapgsarl.htm-12.htm`: number, name and
  the municipality id — `apgl.htm-12+<number>.htm` keys on the number,
  `pkal`/`rapgpl` on the id). Each `apgl` page lists the lists standing
  there with VRK's registration decision (blank for a coalition) linking
  `pkal.htm-<id>+<list>.htm`, the 1997 numbered-candidates page. The
  by-party roll-up (`psarl.htm-12.htm`, 28 parties, each
  `papgsarl.htm-<party>.htm` naming the municipalities it stood in — its
  own list in bold, a coalition it joined in plain type) is the
  cross-check and the only source of a coalition's member parties:
  **9,881 candidates** on 651 lists (26 coalition lists) in 60
  municipalities, every list a party claims one the walk found and vice
  versa, every own-list claim under the party's own name, 1,562 seats
  declared, no id collisions (ids are `<slug>-<vrk id>` as for the other
  municipal generals).
- **Candidate page**: the 2000 Seimas document for the municipal form —
  card ("Apygarda: <municipality> (Nr. N)", "Sąrašas: <list, genitive>,
  priešrinkiminis numeris sąraše: N", for a coalition's candidate
  "(iškėlė <member party>, buvęs numeris sąraše: N)"; birth date,
  residence), five **unnumbered** declarations (sentence, service,
  citizenship, collaboration, conviction — no oath, no grave crime;
  8.3.1-style "Kurios" under a "Turi"), the fields as labelled paragraphs
  (education as a level, languages, degree, title, prior mandates,
  workplace, public activity, marital status — no family members,
  hobbies or birthplace printed on any page read), the 1990s declaration
  inline to the centas. No photo, no autobiography. Saved as
  `candidate.html`. Keys are the 2000 Seimas ones; the candidacy block is
  the 2007 municipal general's (`savivaldybe`, `tarybosNarys` with
  `listKind`, `listPosition`, `vrkSprendimas`, `koalicijosPartijos`, and
  from the card `koalicijosPartija`/`numerisPartijosSarase`). The card's
  municipality, position and member party are checked against the
  sitemap (`Card…Mismatch`).
- **Results**: `savivaldybiu_2000/results.py`. Per municipality
  `rapgpl.htm-<id>.htm` (voters, turnout, quota, votes and mandates per
  list, a totals row), `rikl.htm-<id>.htm` ("Kandidatai, gavę mandatus":
  every member by candidate-page id with list and rank) and per list
  `rpbapgl.htm-<id>+<list>.htm` (rank, preference votes, pre-election
  number, winners in bold). **Five municipalities — Jurbarko, Kelmės,
  Radviliškio, Raseinių, Vilkaviškio rajono — were captured only to the
  list level**: their `rapgpl` page prints the rows unlinked, the
  members link goes to the live CGI and none of the per-candidate pages
  exists statically. For the other 55: 1,433 members, every count equal
  to the page's "Mandatų skaičius", the mandate column and the totals
  row, every member in the sitemap on the right list in the right
  municipality, the bold rows exactly the members, each list's members
  exactly its top ranks, all 9,075 candidates of those municipalities
  ranked with the listing's pre-election number — all at 0. The 806
  candidates of the five keep `isrinktas` **null** with
  `rezultataiNeskelbiami` naming the missing page; every record carries
  its list's votes and mandates (`tarybosNarys.sarasoBalsai`,
  `sarasoMandatai`) from the municipality page, which the five do have
  (129 seats known by list, not by member).

```bash
python -m scraper fetch-sample 2000-kovo-19-savivaldybiu-tarybu
python -m scraper sitemap 2000-kovo-19-savivaldybiu-tarybu
python -m scraper fetch-candidate-samples 2000-kovo-19-savivaldybiu-tarybu --candidate-id paksas-rolandas-84817 --allow-new-samples
python -m scraper build-results 2000-kovo-19-savivaldybiu-tarybu
python -m scraper parse-anketa-samples 2000-kovo-19-savivaldybiu-tarybu
KEEP_SAMPLES=1 scripts/run_election_batches.sh 2000-kovo-19-savivaldybiu-tarybu
```

Fixtures are ten candidates chosen by shape
(`tests/test_savivaldybiu_2000_sample_allowlist.py`); the full field was
scraped 2026-08-23/24 with retention (see `docs/DATASET.md`).

## 2012–2014 national elections (`2012-seimo`, `2013-kovo-3-seimo-birzai-zarasai-ukmerge`, `2014-prezidento`, `2014-ep`) Workflow

The four elections between the 1990s archive and the 2015 backlog are the
same pre-2016 static layout family as the 2015 elections — separate static
files per candidate tab, the `Kandidato<ID>Anketa.html` stem, JPG photos,
litas declarations, campaign participant pages under
`PolitiniuKampanijuFinansavimas/Dalyvis<ID>/`, no winner marked anywhere —
so every module is wiring over `seimo_zirmunu_2015`'s parameterized
machinery with its own question mapping and listing walk. Three things
differ from 2015 and were added to the era code: the 2014 pages put the
tab links inside `ul#tabnav` (the era's `li a[href]` selector covers both
shapes), the presidential pages add a sixth tab (`Patiketiniai`, the
candidate's trustees), and the GPM308 income row cites "…14, 20 laukelių"
where 2015 cites "…14, 22" (both aliases resolve to `gautos-pajamos`).

Question sets, one per election type:

- **Seimo (2007, 2008, 2012, 2013)** — `seimo_birzu_zarasu_ukmerges_2013.normalize_seimo_2012_anketa_rows`:
  the 2015 Seimo variant plus Q9.3 (grave/very grave crime conviction),
  which the 2015 pages no longer carry, and the Q9 block's free-text
  explanation line (`teisiniai-argumentai`, on the 2008 and 2012 forms).
  Every 2013 form holds VRK's "Nenurodė" default for Q9.3. The 2008 form is
  the 2012 one verbatim; the 2007 form is the 2008 one without Q5 — the
  birth date is on the profile card ("Gimimo data: …"), and the era parser
  folds it into `anketa.gimimo-data`.
- **Presidential (2014)** — `prezidento_2014.normalize_presidential_anketa_rows`:
  Q8.1–8.7 are the Prezidento rinkimų įstatymo 2 str. eligibility
  questions (citizenship by origin, three years' residence, eligibility for
  the Seimas, then the four Seimo ones), so birthplace, nationality and
  education shift to Q9–Q11; an unnumbered academic-title line follows the
  education table; there is no Q15.
- **European Parliament (2014)** — `ep_2014.normalize_ep_anketa_rows`: the
  birth date is numbered Q3 (nowhere else in the corpus), Q8.3.1/8.3.2 ask
  about another member state's citizenship and voting rights, Q9.3 as for
  the Seimas, no Q21.
- **Presidential (2009)** — `prezidento_2009.normalize_presidential_anketa_rows`:
  the 2014 form one revision earlier. Q8.1–8.4 are the four 2 str.
  questions only (citizenship by origin, residence and Seimas eligibility
  were not asked yet); Q9 is the 3 str. lustration question (service in,
  schooling by or collaboration with the NKVD/KGB and equivalent foreign
  services), kept under the corpus-wide
  `ar-bendradarbiavote-su-uzsienio-tarnybomis`; birthplace, nationality and
  education sit at Q10–Q12; the unnumbered line after the education table
  asks for the academic degree only (`mokslo-laipsnis`); and unlike 2014
  the Q15 prior-mandates table *is* asked. The page omits a question it
  has no answer for (Q7 everywhere, Q15 for two candidates, Q20 and the
  spouse line for the unmarried), so a null is an absent row.
- **European Parliament (2009)** — `ep_2009.normalize_ep_anketa_rows`: the
  2014 EP form one revision earlier. The 37 str. questions (Q8.1–8.3 with
  8.3.1/8.3.2) and the 93 str. ones (Q9.1–9.3) are as in 2014; around them
  the birth date is Q5 (2014: Q3), the Q9 block closes with a free-text
  line for a "Taip" answer ("Tuo atveju, jei bent į vieną 9 punkto klausimą
  atsakėte Taip … paaiškinimą įrašykite čia" → `pareiskimai.teisiniai-argumentai`,
  the 2016 Seimo key for the same slot — also on the 2012 Seimo pages, where
  the 2012/2013 normalizer now reads it), the line after the education
  table asks for the degree *and* the pedagogical title ("…mokslo laipsnį
  …, vardą …" → `mokslo-laipsnis` and `pedagoginis-vardas`), and Q21 is
  asked (2014 dropped it).

Listings, one walk per structure:

- `2014-prezidento`: one table of seven candidates (each row links the
  anketa twice; the era's row walker takes the first). Fixtures are the
  whole field.
- `2007-spalio-7-seimo-dzukija` (VRK election 396, issue #35; the path has no `_lt` suffix): the
  oldest page of the family, one year before the 2008 general. The
  `Kandidatai/index.html` the ticket names is a meta-refresh to the one
  constituency's candidate page, so as for the 2015 single-constituency
  by-elections the district page itself is the listing, walked by the
  Žirmūnai machinery; the module then adds VRK's id and the nominator from
  the same rows so the records carry the Seimo `kandidatavimas` block. Ten
  candidates, whole field as fixtures. Three things are this election's
  own, each handled in the shared code it belongs to: the listing prints
  names in capitals ("ONA BALEVIČIŪTĖ" — the module restores the corpus's
  "Ona BALEVIČIŪTĖ"); the profile card is the family's oldest shape —
  plain-text name and "Gimimo data:" line, constituency and party in a
  header table above it, a campaign link with one `../` too many — read by
  the era parser's legacy-card branch and URL resolver; and the
  `2007_seimo_rinkimai` results tree has no `output_lt` level, keeps round
  two in the round-one folder and links candidate rows straight to the
  anketa pages (`RESULTS_TREE = "2007_seimo_rinkimai/"` — the trailing
  slash is the walker's cue). Four tabs (no *Kita*); six of the ten are
  represented candidates whose card says so in words and links no
  campaign. The income extract is the interim **GPM302** form, one older
  than 2008's GPM305.
- `2008-seimo`: the 2012 two-structure walk one term earlier (VRK election
  400) — 16 numbered lists (`list.html`) and 71 constituencies
  (`districts.html`), merged on VRK's candidate id into 1,603 entries (770
  in both, 813 list-only, 20 constituency-only). Two things differ from
  2012 and were generalised in `seimo_2012.sitemap`: the coalition list
  page links its member parties' plain list pages (2012 appends `_3`), so
  a member link is recognised by its key being one of the index's
  "koalicijos sąrašas" rows; and the index has no "Išsikėlę" page, so the
  district-only reconciliation counts the constituency pages' own
  "Išsikėlė pats" rows (`stats.selfNominatedNotOnSidePages`, 15 here, 0
  in 2012). The index's declared counts for the coalition's member
  parties (32, 37) are the members who also stood in a constituency for
  that party, not their list shares (67, 63). The candidate pages carry
  four tabs — no *Kita* — and **no campaign participant link** (VRK's
  2008 participants index under `400_lt/PolitiniuKampanijuFinansavimas/`
  lists the parties, but no candidate page links it), so the records have
  no campaign section. Fixtures are eight shape-chosen candidates.
- `2009-ep`: the 2014 EP index-and-lists walk one revision earlier (VRK
  election 404): an index of 15 party lists with declared sizes, each a
  page of candidates in list order. The sitemap reconciles every walked
  list against its declared size (262/262). Fixtures are the 15 list
  leaders; the full field is scraped by the batch runner. Every candidate
  links the *party's* campaign participant page; Tomaševski's page links
  his presidential campaign's participant id (`Dalyvis4000`, valid under
  `403_lt`) under the EP path where it does not exist — the one
  `CampaignRootFetchFailed` in the election, a VRK cross-link error left as
  the anomaly it is.
- `2009-prezidento`: the same one-table listing (VRK election 403), seven
  candidates, fixtures the whole field. The oldest election in this
  layout family, and the only one whose pages link a tab VRK never
  published: every `Kandidato<ID>Patiketiniai.html` (trustees) is a 404,
  so `prezidento_2009.candidate_samples.UNPUBLISHED_TABS` names it and
  the era fetcher records the link under `unpublishedTabs` in
  `index.json` instead of fetching it or reporting it missing. The
  records have no `patiketiniai` block. Its campaign pages are also one
  revision older — `<td><strong>` table headings instead of `<th>`, a
  single "Aukotojų sąrašas" donor table with unacceptable donations
  flagged inline after the donor's name (", nepriimtina auka"; the flag
  becomes the `notes` the later pages have as a column), financing
  reports with a kind (`reportType`: "Pradinė"/"Galutinė") where the
  later pages carry a verification status, and a company auditor
  labelled "Pavadinimas"/"Kodas" — and its declarations extract the
  GPM305 form (see the income alias note in `seimo_zirmunu_2015`).
- `2013-kovo-3-seimo-birzai-zarasai-ukmerge`: a constituency index
  (`Kandidatai/index.html`) linking three constituency pages. The module's
  index-driven walk saves the index as `list.html` and the pages under
  `districts/district-<id>.html`; the 2012 module reuses it. 37 candidates,
  fixtures are the whole field.
- `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai` (VRK election 406; issues #39 and #40 are one election — two seats
  vacated by the June 2009 EP election, voted on one day) and `2011-vasario-13-seimo-marijampole` (VRK
  election 410): the same index-driven walk, two and one constituency pages
  — `seimo_silales_silutes_vilniaus_salcininku_2009` and
  `seimo_marijampoles_2011` are thin wiring over the 2013 module. 17 and 9
  candidates, fixtures the whole field, every campaign link resolved (10 +
  4 represented, 7 + 5 independent). The cards carry no results links. The
  third 2011 by-election (Danės No. 19, VRK election 412, issue #43) has
  **no candidate data on VRK**: the constituency page's candidate table is
  empty, the "Balsavimo rezultatai" page is an empty Liferay shell, no
  `2011_*_seimo_rinkimai` results tree exists for July, and only the
  campaign participants index (`412_lt/PolitiniuKampanijuFinansavimas/`,
  ten participants) survives — nothing to build a module on.
- `2014-ep`: an index of ten party lists with declared sizes
  (`KandidatuSarasai/index.html`), each a page of candidates in list order
  (`lists/list-<id>.html`). The sitemap reconciles every walked list
  against its declared size (215/215). Fixtures are the ten list leaders.
- `2012-seimo`: both structures at once — 18 numbered lists
  (`list.html`, the EP walker) and 71 constituencies (`districts.html`, the
  2013 walker), merged on VRK's candidate id into 1,927 entries (929 in
  both, 949 list-only, 49 constituency-only). The list index also rows the
  coalition's four member parties and seven "tik vienmandatėse" pages;
  the sitemap fetches those too and uses them as cross-checks
  (`stats.districtOnlyReconciled`, `stats.listDistrictJoinMismatch`) — see
  the `2012-seimo` appendix in `OUTPUT_SCHEMA.md` for what each stat
  asserts. Fixtures are nine shape-chosen candidates.

Listing-only facts (constituency, nominator, list, list number, position,
coalition member party) travel in the `kandidatavimas` block on every 2012,
2013 and EP record.

```bash
python -m scraper fetch-sample 2007-spalio-7-seimo-dzukija
python -m scraper sitemap 2007-spalio-7-seimo-dzukija
python -m scraper build-results 2007-spalio-7-seimo-dzukija
python -m scraper fetch-sample 2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai
python -m scraper sitemap 2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai
python -m scraper build-results 2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai
python -m scraper fetch-sample 2008-seimo
python -m scraper sitemap 2008-seimo
python -m scraper fetch-candidate-samples 2008-seimo --candidate-id andrius-kubilius --allow-new-samples
python -m scraper build-results 2008-seimo
KEEP_SAMPLES=1 scripts/run_election_batches.sh 2008-seimo
python -m scraper fetch-sample 2009-ep
python -m scraper sitemap 2009-ep
python -m scraper fetch-candidate-samples 2009-ep --candidate-id vytautas-landsbergis --allow-new-samples
python -m scraper build-results 2009-ep
KEEP_SAMPLES=1 scripts/run_election_batches.sh 2009-ep
python -m scraper fetch-sample 2009-prezidento
python -m scraper sitemap 2009-prezidento
python -m scraper fetch-candidate-samples 2009-prezidento --candidate-id dalia-grybauskaite --allow-new-samples
python -m scraper build-results 2009-prezidento
python -m scraper parse-anketa-samples 2009-prezidento
python -m scraper fetch-sample 2014-prezidento
python -m scraper sitemap 2014-prezidento
python -m scraper fetch-candidate-samples 2014-prezidento --candidate-id dalia-grybauskaite --allow-new-samples
python -m scraper parse-anketa-samples 2014-prezidento
python -m scraper fetch-sample 2012-seimo
python -m scraper sitemap 2012-seimo
KEEP_SAMPLES=1 scripts/run_election_batches.sh 2012-seimo
```

## Elected status for 1996–2015 (`build-results`) Workflow

The 1996–2015 static pages carry no winner mark, so the elections of those
families (`2007-vasario-25-savivaldybiu`, `2007-spalio-7-seimo-dzukija`, `2008-seimo`, `2009-prezidento`, `2009-ep`, `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai`, `2011-vasario-13-seimo-marijampole`, `2011-vasario-27-savivaldybiu`, `2012-seimo`, `2013-kovo-3-seimo-birzai-zarasai-ukmerge`,
`2014-prezidento`, `2014-ep`, the six 2015 elections) get their
`kandidatavimas.isrinktas` from VRK's results trees
(`statiniai/puslapiai/<year>_<type>_rinkimai/output_lt/`). The walkers and
every source page are documented in `scraper/shared/election_results.py`;
each module's `results.py` is the configuration (tree name, and for the
2015 municipal general the three VRK annulment decisions). What the
reconciliation looked like when the files were built (2026-08-21):

| election | source | winners | reconciliation |
|---|---|---|---|
| `2007-spalio-7-seimo-dzukija` | 1 constituency page, runoff plurality (Čilinskas 56.4%; the 2007 pages state no verdict); the tree has no `output_lt`, keeps round two in the round-one folder and links rows to the anketa pages | 1 | resolved |
| `2008-seimo` | elected-members page (ids on the page) | 141 (70 list, 71 constituency) | all 141 in the sitemap; 70 of 71 constituency pages resolve to the same winner, the 71st (Varėnos–Eišiškių) being the one constituency where two candidates share a name — Algis KAŠĖTA of the LRLS and of the Lietuvos laisvės sąjunga — so name resolution declines and the member page's id decides |
| `2012-seimo` | elected-members page (ids on the page) | 139 (70 list, 69 constituency) | all 139 in the sitemap; 69 of 71 constituency pages name the same winner, the other two being the annulled Biržų–Kupiškio and Zarasų–Visagino |
| `2013-kovo-3-…` | 3 constituency pages, round two | 3 | all resolved by name within the constituency |
| `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai` | 2 constituency pages: Šilalės–Šilutės by runoff plurality (the 2009 round-two page states no verdict), Vilniaus–Šalčininkų from the tree's first-round elected page (`rezultatai_vienmand_apygardose/isrinkti_seimo_nariai.html` — decided outright, 77.8%, no round two) | 2 | resolved |
| `2011-vasario-13-seimo-marijampole` | 1 constituency page, runoff plurality | 1 | resolved |
| `2009-prezidento` | first-round nationwide vote table sentence ("Respublikos Prezidente išrinkta …"; the tree's certificate-style final page declines the name) | 1 | resolved |
| `2009-ep` | elected-members page (`rezultatai/index.html`; 2014's is `rezultatai/rezultatai.html`) | 12 | all in the sitemap |
| `2014-prezidento` | final-results page sentence | 1 | resolved |
| `2014-ep` | elected-members page | 11 | all in the sitemap |
| `2015-kovo-1-seimo-zirmunai` | round-two page (no verdict sentence: runoff plurality) | 1 | resolved |
| `2015-birzelio-7-seimo-varena-eisiskes` | round-two page sentence | 1 | resolved |
| `2015-kovo-1-savivaldybiu` | 60 municipality pages + 478 list rankings + 40 round-two pages | 57 mayors, 1,464 council (48 annulled) | 0 unresolved; 249 dual candidates resolved by name+list+position (two VRK ids each); 58/60 compositions contain every derived winner, the two exceptions the annulled councils |
| `2011-vasario-27-savivaldybiu` | 60 municipality pages + 599 list rankings (no mayoral vote, no round two); built 2026-08-22 | 1,526 council, 18 of them self-nominated individuals seated from their own row of the results table | every winner by id in the sitemap (no dual ids: one candidacy each); 0 seat mismatches; 60/60 compositions contain every derived winner |
| `2007-vasario-25-savivaldybiu` | 60 municipality pages + 60 "Mandatus gavę kandidatai" pages (the winners with anketa links; no ranking arithmetic), `2007_savivaldybiu_tarybu_rinkimai/` without `output_lt`; built 2026-08-22 | 1,550 council | every winner by id in the sitemap and in the municipality the sitemap places them; winners = results-table total = sum of list mandates = composition-page council size in all 60 |
| `2004-ep` | the 2004 tree's own members page (`rinkimai/2004/euro/rezultatai/rez_isrinkti_l_18_1.htm`, ids on the page) with its substitution footnote, the national page's mandate column and the 12 per-list ranking pages; built 2026-08-23 | 13 (14 records: Prunskienė's terminated mandate and Didžiokas seated by VRK decision Nr. 181) | all in the sitemap; mandates per list = members per list; bold ranking rows = members; 241/241 ranked, pre-election positions = listing |
| `2002-prezidento` | the 2002 tree's two national pages (`rezultatai/rezl.htm-14+1.htm`, `-14+2.htm`; rows keyed by the registration record id the trustee index carries) and the final protocol's accusative verdict, resolved by word-stem prefix against the runoff pair; both rounds' votes kept in the details for the `kandidatavimas.turai` join; built 2026-08-24 | 1 (Paksas, protocol verdict) | 17 round-one rows all in the sitemap; the runoff pair = round one's top two; each round's votes sum to its valid ballots; verdict = the runoff vote leader |
| `2004-prezidento` | the 2004 tree's two national pages (`rinkimai/2004/prezidentas/rezultatai/rez_l_19_1.htm` and `_2.htm`), joined by the registration record id the listing's trustee links carry and the runoff verdict's card-anchor fragment; both rounds' votes kept in the details for the `kandidatavimas.turai` join; built 2026-08-24 | 1 (Adamkus, runoff verdict) | 5 round-one rows all in the sitemap; bold round-one names = the runoff field; each round's votes sum to its valid ballots; winner resolved by id |
| `2004-seimo` | the 2004 tree's members page (`rinkimai/2004/seimas/rezultatai/rez_isrinkti_l_20_1.htm`, ids on the page, seat and deciding round on the row), cross-checked against the list-seat and the two constituency-winner pages and the national page's mandate column; the 15 per-list ranking pages for rank and preference votes; built 2026-08-23 | 141 (70 list, 71 constituency: 5 in round one, 66 in the runoff) | all in the sitemap with the right role and constituency; all three id cross-checks and the mandate column at 0; 1,183 list candidates ranked (128 on the unranked LLRA list with rank but no votes), pre-election positions = listing |
| `2003-birzelio-15-seimo-nauji` | the 2003 tree's four constituency pages (`rinkimai/2003/seimas/rezultatai/rez_v_apg_l_<APG>_1.htm`) and their index; built 2026-08-28 | 0 (all four `neįvyko`) | every page states the verdict, so all 27 records carry a known `isrinktas: false`; 27/27 rows resolved by id (the rows carry the anketa id, unlike 2004's); each page's votes sum to its valid ballots |
| `2005-lapkricio-20-seimo-kedainiai` | the 2005 tree's members page (`rinkimai/2005/seimas/rezultatai/rez_isrinkti_l_21_1.htm`, id and round on the row), cross-checked against the runoff winners page; built 2026-08-23 | 1 (runoff) | resolved |
| `2015-birzelio-7-pakartotiniai-sirvintos-trakai` | same walk, `2015_2_…` tree | 2 mayors, 24 council | clean |
| `2015-birzelio-21-pakartotiniai-silutes` | `2015_3_…` tree | 1 mayor, 24 council | clean |
| `2015-lapkricio-8-telsiu-mero` | `2015_4_…` tree | 1 mayor | clean |
| `1996-spalio-20-seimo` | the `seim96` elected-members page (`rsnl.htm-1.htm`, ids on the row with the nominator and the seat), cross-checked against all 71 + 65 constituency pages, the list results page's mandate column and the 19 `rkreitl` ranking pages; built 2026-08-27 | 137 seated on the night (70 list, 67 constituency: 2 in round one, 65 in the runoff); 120 of them in the corpus | the constituency pages' own verdicts are exactly the members page's constituency half (`constituencyPageDiff` 0); mandate column = list seats; striking each list's constituency winners and taking its top *M* reproduces the published list winners for all 5 mandate-winning lists; all 879 records on a results page, 0 unresolved rows |
| `1997-kovo-23-seimo-pakartotiniai` | 4 `rapgp20<n>` first-round pages plus the 1997-04-13 Trakų runoff (`rapgpl.htm-204+2.htm`); built 2026-08-27 | 2 (Senkevič outright in Nr. 56, Aleksiūnienė in the Nr. 58 runoff) | 23/23 rows resolved by id; 2 of 4 constituencies `neįvyko`; all four first-round pages are the mojibake capture and are repaired |
| `1997-gruodzio-21-seimo-pakartotiniai` | `rapgpl.htm-324+1.htm` and `-324+2.htm` | 1 (Velikonis, runoff) | 4/4 rows resolved by id |
| `1998-kovo-22-seimo-pakartotiniai` | `rapgpl.htm`, `rapgpl2.htm` | 0 (both constituencies `neįvyko`) | 11/11 rows resolved **by name** — the family's one capture whose rows carry no candidate id |
| `1998-lapkricio-15-seimo-pakartotiniai` | `rapgpl.htm-392+1.htm` | 0 (`neįvyko`) | 11/11 rows resolved by id |
| `1999-kovo-21-seimo-pakartotiniai` | three `19990321/rapgpl.htm-<n>+1.htm` pages | 0 (all three `neįvyko`) | 22/22 rows resolved by id |

Traps the walkers encode, worth knowing before touching them:

- **Round two re-issues ids.** The round-two tree's constituency ids and its
  `rezultatai_sm_kand<ID>` row ids do not match the candidate pages
  (Gustainis is 87277 on his page, 87559 in the runoff), so round-two
  winners are resolved by name within the constituency's own field.
- **Dual mayor+council candidates hold two VRK ids** (Telšiai's mayor
  three); the listings use one, the ranking pages the other. They are
  resolved by name, list and pre-election position — never by name alone.
- **The 2009 and 2011 by-election trees reuse the presidential template**
  for the candidate row pages (`rezultatai_prezidento_kand<ID>…` instead
  of `rezultatai_sm_kand<ID>…`), and their round pages state no verdict;
  a constituency decided outright in round one is named only on the
  tree's first-round elected page, which the 2008 and 2009 trees publish
  and the 2011/2013 trees do not.
- **"Meru išrinktas" / "Mere išrinkta"** — the noun inflects with the winner.
- **The composition pages are a snapshot a year on**, with replacements
  seated; they are the cross-check, not the source. The election-night
  source is the municipality results page: each list's mandate count, and
  the list's post-preference ranking with the mayor-elect marked.
- **A self-nominated individual has no ranking page** (2011): the seat is
  the mandate column of their own `savkand<ID>` row on the municipality
  results page, and the page's seat total counts it. The mayoral seat is
  added to that total only where the page carries a mayoral field at all —
  2011 pages carry none, and the composition pages say "Mandatų skaičius:"
  rather than "…, įskaitant merą:".
- **Annulments are configuration, not inference**: VRK decisions Sp-101
  (Trakai), Sp-126 (Šilutė) and Sp-121 (Širvintos mayoral race) are named
  in `savivaldybiu_2015/results.py`; the composition check cannot detect
  them because most of the annulled winners won again in June.
- **The 1996-1999 archive family's flag is per candidacy**, because its
  `kandidatavimas` is a list: a constituency win marks every candidacy for
  that constituency (so a coalition-plus-member-party double nomination
  carries two `true` rows for one seat), a list win every `Daugiamandatė`
  one, and everything else is a `false` that VRK's page actually states.
- **`seimpk/rapgp201.htm` … `204` are mojibake** — that one capture's
  Windows-1257 bytes were re-encoded as Latin-1 HTML entities. The repair is
  accepted only when the cp1257 round trip recovers Lithuanian letters, so a
  correctly-encoded page cannot be damaged by it.

```bash
for id in 2007-spalio-7-seimo-dzukija 2008-seimo 2009-prezidento 2009-ep 2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai 2011-vasario-13-seimo-marijampole 2012-seimo 2013-kovo-3-seimo-birzai-zarasai-ukmerge 2014-prezidento 2014-ep \
          2015-kovo-1-seimo-zirmunai 2015-birzelio-7-seimo-varena-eisiskes 2015-lapkricio-8-telsiu-mero \
          2015-birzelio-7-pakartotiniai-sirvintos-trakai 2015-birzelio-21-pakartotiniai-silutes 2015-kovo-1-savivaldybiu \
          2011-vasario-27-savivaldybiu 2007-vasario-25-savivaldybiu 2002-prezidento 2004-ep 2004-prezidento 2004-seimo 2005-lapkricio-20-seimo-kedainiai 2003-birzelio-15-seimo-nauji \
          1996-spalio-20-seimo 1997-kovo-23-seimo-pakartotiniai 1997-gruodzio-21-seimo-pakartotiniai \
          1998-kovo-22-seimo-pakartotiniai 1998-lapkricio-15-seimo-pakartotiniai 1999-kovo-21-seimo-pakartotiniai; do
  python -m scraper build-results "$id"
done
# then re-parse offline; the wrappers pick up sitemaps/<id>.results.json by default
python -m scraper parse-anketa-samples 2012-seimo --samples-root samples-full/2012-seimo
```

## The re-parse gate (`scripts/reparse_diff.py`)

A record is written by whichever parser existed the day its election was
scraped. A fix that lands afterwards reaches `data/` only if something
re-parses it, and until 2026-08-29 nothing did — issue #91 found 20,534
records across 15 elections that no longer re-parsed to what was stored.

This is that something. It re-parses an election from its retained HTML into a
scratch tree and structurally diffs the result against `data/`, classifying
every differing JSON path as `added` / `removed` / `changed` / `type` /
`length` with list indices collapsed to `[]`.

```bash
python scripts/reparse_diff.py                      # all 55 elections, fixtures
python scripts/reparse_diff.py 2019-ep 2020-seimo   # named elections
python scripts/reparse_diff.py --full --jobs 8 2019-ep
python scripts/reparse_diff.py --full --jobs 8 --apply 2019-kovo-3-savivaldybiu-tarybu
```

Options:

- `--full`: parse every retained candidate (`samples-full/<id>/`) instead of
  the fixture set. An election with no retained tree falls back to its
  fixtures, which for the archive families is every candidate anyway, and so
  does any single *candidate* the retained tree lacks and the fixture tree
  has — 96 of them across ten elections, which `--apply` could not reach at
  all until issue #101 while the fixture run went on reporting them as
  drifted. The per-election line always states how many of the stored records
  the run actually reached, and names the fixture fill-in when there is one
  (`re-parsed from retained + 9 from fixtures`).
- `--apply`: copy the freshly parsed records over `data/<id>/`, with any
  photo sidecars the parse externalized. Only the records that differ are
  written, so an election that re-parses identically is not touched at all.
  Requires `--full` — applying a fixture run would rewrite five records and
  leave the other 13,661 stale.
- `--jobs N`: parser processes. The default is 1, which lets each module
  enumerate its own sample tree; above 1 the script enumerates (a candidate
  directory is one with an `index.json` in it) and cross-checks the count
  against what the parsers returned.
- `--top N`, `--repo-root`, `--work-root`.

Exit status is the gate: **0** when nothing differs, **1** when something
does, **2** when the run could not be made (a missing sample tree, a parser
that raised).

Without `--full` the whole corpus is checked in about ten seconds, which is
what makes it a habit rather than an event. A full pass over all 113,073
records takes about an hour on eight processes and needs no network.

### `scripts/backfill_value_hygiene.py`

The 38 records a re-parse cannot reach — their page exists in neither sample
tree — cannot be brought forward by `--apply`, and a stale record in an
otherwise-uniform column is worse than a stale record. This applies the
corpus-wide value rules (`scraper/shared/values.py`) to what is already stored
in `normalized`, leaving `rawData` alone.

```bash
python scripts/backfill_value_hygiene.py --dry-run
python scripts/backfill_value_hygiene.py --election 2019-rugsejo-8-seimo
```

Idempotent, and `tests/test_backfill_value_hygiene.py` pins that a record the
parser just wrote is a fixed point of it.

## Helpful Checks

```bash
python -m scraper --help
python -m scraper parse-anketa-samples --help
python scripts/reparse_diff.py          # the corpus still matches the parsers
pytest tests/
```
