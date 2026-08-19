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

## Helpful Checks

```bash
python -m scraper --help
python -m scraper parse-anketa-samples --help
pytest tests/
```
