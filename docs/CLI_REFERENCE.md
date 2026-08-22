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

Output:

- Updates candidate sample directories and prints per-candidate tab stats.

### `build-results`

Fetch VRK's results pages for an election whose candidate pages mark no
winner — the ten 2012–2015 elections — and write
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
2024 EP module; with the 2016 aliases every income figure normalizes to null.

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

## Seimas archive (`1996-spalio-20-seimo`, `1997-kovo-23-seimo-pakartotiniai`, `1997-gruodzio-21-seimo-pakartotiniai`) Workflow

The 1996-10-20 Seimas general election and its two 1997 repeat votes are the
oldest family in the repository — static pages captured by Teleport Pro from
`lrs.lt/cgi-bin/ora7dbcgi/...`, older than the 2015 family and shaped nothing
like it. The shared parser lives in `scraper/shared/seimo_archive_1990s.py`;
these three modules differ only in which directory (`seim96` vs `seimpk`),
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
  after the real candidacy paragraphs and swallows the "Gyvenamoji vieta"
  (residence) line along with a block of boilerplate eligibility Q&A that
  always reads the same "Neturi"/"Nėra" — not real per-candidate data. A
  normal HTML parser drops comment contents entirely, so residence is
  recovered with a targeted regex over the raw HTML instead; the eligibility
  junk is discarded on purpose. `tests/test_seimo_1996_anketa_parser.py`
  guards this against regression.
- A candidate can carry two candidacies — their single-member constituency
  and, optionally, a `Daugiamandatė` (multi-mandate party list) entry with its
  own list number — both are kept as separate objects in
  `rawData.candidacies`/`normalized.kandidatavimas` rather than merged.
- No income declaration parsing: `kpdl.htm` is captured only as a raw URL
  (`incomeDeclarationUrl`), out of scope for this family's fixture-sized
  ambition, same call as the elected-status gap recorded in `docs/DATASET.md`.
  The free-text biography page (`biogr.htm`), when linked, is captured
  verbatim as `rawData.biography.text`.
- 1996 is the only general election of the three (879 candidates, 71
  constituencies); the March 1997 repeat covers four constituencies (Naujosios
  Vilnios, Vilniaus-Šalčininkų, Vilniaus-Trakų, Trakų — 23 candidates,
  complete field); the December 1997 repeat is one constituency, Aukštaitijos
  No. 28 (4 candidates, complete field).

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
```

Resumable full scrape (1996 general election only — the two by-elections are
already small enough that `fetch-candidate-samples` covers the complete
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
  family) and is considerably richer: birth date/place, residence,
  nationality, education, foreign languages, main workplace, public activity,
  family status and family members are all plain labelled paragraphs, carried
  into `rawData.personal`/`normalized.anketa`. As with the Seimas
  archive, `kpdl.htm` (income declaration) is captured only as a raw URL.
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

## Elected status for 2012–2015 (`build-results`) Workflow

The 2007–2015 static pages carry no winner mark, so the eighteen elections of
that family (`2007-vasario-25-savivaldybiu`, `2007-spalio-7-seimo-dzukija`, `2008-seimo`, `2009-prezidento`, `2009-ep`, `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai`, `2011-vasario-13-seimo-marijampole`, `2011-vasario-27-savivaldybiu`, `2012-seimo`, `2013-kovo-3-seimo-birzai-zarasai-ukmerge`,
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
| `2015-birzelio-7-pakartotiniai-sirvintos-trakai` | same walk, `2015_2_…` tree | 2 mayors, 24 council | clean |
| `2015-birzelio-21-pakartotiniai-silutes` | `2015_3_…` tree | 1 mayor, 24 council | clean |
| `2015-lapkricio-8-telsiu-mero` | `2015_4_…` tree | 1 mayor | clean |

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

```bash
for id in 2007-spalio-7-seimo-dzukija 2008-seimo 2009-prezidento 2009-ep 2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai 2011-vasario-13-seimo-marijampole 2012-seimo 2013-kovo-3-seimo-birzai-zarasai-ukmerge 2014-prezidento 2014-ep \
          2015-kovo-1-seimo-zirmunai 2015-birzelio-7-seimo-varena-eisiskes 2015-lapkricio-8-telsiu-mero \
          2015-birzelio-7-pakartotiniai-sirvintos-trakai 2015-birzelio-21-pakartotiniai-silutes 2015-kovo-1-savivaldybiu \
          2011-vasario-27-savivaldybiu 2007-vasario-25-savivaldybiu; do
  python -m scraper build-results "$id"
done
# then re-parse offline; the wrappers pick up sitemaps/<id>.results.json by default
python -m scraper parse-anketa-samples 2012-seimo --samples-root samples-full/2012-seimo
```

## Helpful Checks

```bash
python -m scraper --help
python -m scraper parse-anketa-samples --help
pytest tests/
```
