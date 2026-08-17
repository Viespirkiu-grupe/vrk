# Dataset Inventory and Review

State of the scraped corpus after the full run of 2026-08-16, and the caveats
worth knowing before analysing it.

Regenerate any part of it with:

```bash
scripts/run_all_elections.sh                 # every election, sequentially
scripts/run_election_batches.sh <election-id> # one election
```

Both are resumable: a candidate whose output JSON already exists is skipped, so
an interrupted run continues where it stopped. Candidate samples go to a
temporary directory, so the test-protected fixtures under `samples/html/` are
never touched by a full run.

## Inventory

5,624 candidate records across 15 elections, 2016–2025. The full run took
~2h45m end to end, with **zero fetch failures and zero parse anomalies**.

| election | records | elected | declared a conviction | with campaign data |
|---|---:|---:|---:|---:|
| `2016-seimo` | 1415 | 141 | 38 | 672 |
| `2017-balandzio-23-meru` | 11 | 2 | 0 | 11 |
| `2017-balandzio-23-seimo-anyksciai-panevezys` | 11 | 1 | 0 | 11 |
| `2017-rugsejo-10-marijampoles-mero` | 8 | 1 | 0 | 8 |
| `2019-ep` | 301 | 11 | 0 | 279 |
| `2019-prezidento` | 9 | 9 | 0 | 9 |
| `2020-seimo` | 1754 | 141 | 41 | 758 |
| `2021-balandzio-11-radviliskio-mero` | 7 | 1 | 1 | 7 |
| `2021-spalio-10-meru` | 14 | 2 | 1 | 14 |
| `2023-rugsejo-3-seimo-raseiniai-kedainiai` | 8 | 1 | 1 | 8 |
| `2023-spalio-8-kupiskio-mero` | 5 | 1 | 1 | 5 |
| `2024-ep` | 319 | 11 | 7 | 0 |
| `2024-prezidento` | 8 | 8 | 0 | 0 |
| `2024-seimo` | 1740 | 141 | 62 | 699 |
| `2025-kovo-16-meru` | 14 | 2 | 0 | 10 |
| **total** | **5624** | **473** | **153** | **2491** |

Records live under `data/<election-id>/` (~750 MB) and are **not** version
controlled — `data/`, `sitemaps/` and `samples/` are gitignored, so the corpus is
reproduced by running the scrapers rather than by cloning.

### Not yet scraped: the 2023 municipal general election

`2023-kovo-5-savivaldybiu-tarybu-ir-meru` has a module and a verified sitemap
but no full run yet, so it is deliberately absent from the table above. Its
sitemap totals, cross-checked against VRK's own `savKandidataiSuvestine.html`
summary, are:

| | count |
|---|---:|
| candidates (union of both listings) | 13,796 |
| mayoral candidates | 433 |
| council candidates | 13,769 |
| standing for both | 406 |
| party/committee lists | 467 |
| elected mayors | 60 |
| elected council members | 1,498 |

The two listings overlap rather than nest: 406 people appear in both under the
same VRK candidate id, and 27 mayoral candidates appear on no list, so
433 + 13,769 − 406 = 13,796.

Scraping it in full would take the corpus from 5,624 records to roughly 19,400 —
about 3.5× its current size, and larger than every implemented election put
together. Nothing here should be read as a record count: 13,796 is what the
listings publish, not what has been parsed.

## Caveats for analysis

### Campaign donations are per campaign, not per candidate

Donation records belong to a *campaign participant*. In list-based elections one
participant covers many candidates, and each of those candidates' records
contains the whole shared donation list. Summing donations across candidates
therefore multiplies the same money:

| election | candidates with campaign data | distinct campaigns | largest share |
|---|---:|---:|---:|
| `2019-ep` | 279 | 15 | one campaign across 22 candidates |
| `2024-seimo` | 699 | 205 | one campaign across 70 candidates |
| `2020-seimo` | 758 | 298 | none shared |
| `2016-seimo` | 672 | 324 | none shared |

The effect is large. For 2019 EP, naively adding donation amounts across
candidate records gives €29.2M; de-duplicating by campaign gives **€1.44M** — a
20× inflation. Always group by campaign identity (`sprendimo-numeris`, or the
`campaignKey` in `rawData`) before summing.

### Conviction data has two different shapes

Every election records the yes/no declaration under
`normalized.anketa.pareiskimai.ar-buvote-pripazintas-kaltu`, and that is the
field to count on. Structured conviction *details* (date, court, offence) exist
only where the page publishes them:

- 2023 onward (Rinkimų kodekso era) and 2021: `anketa.teistumo-detales`
- 2016/2020 Seimo: no detail block at all — 2016 offers only the free-text
  `teisiniai-argumentai` justification
- 2017 mayoral: the declaration answer is on a continuation row (see the module
  docs), and there is no detail table

Counting `teistumo-detales` alone therefore under-reports; it returns 0 for the
two largest elections, which record 38 and 41 declared convictions respectively.

### Placeholder answers normalize to null

`Nenurodė` ("did not specify"), `-` and empty strings become `null`. A null
means "not answered on the page", not "no data collected" — the source text is
always preserved in `rawData`. Some declarations are genuinely blank upstream:
every 2021 Radviliškis candidate left Q10 unanswered, and individual candidates
elsewhere left single questions blank.

### Per-election schemas are deliberately not identical

`docs/OUTPUT_SCHEMA.md` documents each election's own shape. The questionnaire
changed repeatedly (Seimo rinkimų įstatymas → savivaldybių tarybų rinkimų
įstatymas → Rinkimų kodeksas), so key sets differ by design. Field names are
shared wherever the underlying question matches, which makes cross-election
comparison possible for the declarations, assets, income and biography, but the
key list itself is election-specific.

## Correctness fixes behind this corpus

Nine defects were found and fixed while building the newer modules. Each had
been invisible because the affected elections had thin or no test coverage, and
each was measured against live data after the fix:

| fix | effect on the corpus |
|---|---|
| donation tables of every published width | recovered donation rows for 2019 EP, 2019/2024 presidential, 2024 Seimo and the 2023 by-elections; previously only the 7-column 2016 layout parsed |
| 2024 Seimo profile and anketa numbering | name and photo went from null for 100% of candidates to populated for 100%; declarations from 0/11 to 11/11 answered |
| 2020 Seimo anketa numbering | current position, party membership and contact fields recovered for ~97% of 1754 candidates; declarations from 4/10 to 10/10 answered |
| record tables rendered in their own row | 525 of 1415 2016 Seimo candidates (37%) recovered their prior-mandate history: **+1,180 records** |
| nested `<tbody>` lookup | a candidate whose conviction table nested inside the anketa had their entire questionnaire collapse to one row |
| 2016 Seimo coverage audit | no defect found; the module gained the anketa tests it never had |
| campaign "Sprendimai" tab never normalized | the VRK decisions taken about a campaign — unlawful political advertising and the like — were fetched and kept in `rawData` but never reached `normalized`. Recovering them added **26 decisions to 23 records across 9 elections**. `2024-seimo` was unaffected: it has its own handler |
| private-interest items published without a label | free-text declaration sections such as "Kiti duomenys" are published as an unlabelled sentence, and any item without a key was dropped, so the whole declared text was lost from `normalized` while `rawData` kept it. It is now collected under a `tekstas` key |
| donations section whose heading carries its own empty-state marker | a campaign with nothing to declare renders `Gautos ir priimtos aukos: Duomenų nėra` inside the heading rather than as the text node that normally follows it. No table or text node follows, so the next heading overwrote the pending title and the section vanished — collapsing "declared no donations" into "section never published", and leaving the sections after it untitled. **6 sections recovered across 3 elections** in the fixture corpora |

Every fix was verified by re-parsing all elections and confirming the diff was
confined to the intended records.

The three most recent fixes are measured over the **fixture corpora only** — the
elections whose fixture set is the complete field are exact, the large elections
are not, and no full re-run has been done since. The 23/26 and 6-section figures
are floors for what a full re-run would recover, not totals.

All three were found the same way: by reading every field of every fixture
candidate in a new module and treating each null or empty value as a question
rather than a result. All three sat in shared code with no test coverage, and
each now has one.

## Known gaps

- The corpus covers the elections implemented so far. VRK publishes further
  by-elections and older elections that have no module yet.
- `2023-kovo-5-savivaldybiu-tarybu-ir-meru` is implemented and its sitemap is
  verified, but only the nine fixture candidates have been parsed. Until a full
  run lands, any cross-election total in this document excludes it.
- `2024-ep` and `2024-prezidento` candidate pages carry no campaign tab, so
  those elections have no donation data at all — campaigns were run by the party
  lists and are published outside the candidate pages.
- Donation *records* were historically dropped by the shared parser; the totals
  in older analyses of this repo predate that fix and should be recomputed.
