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

19,420 candidate records across 16 elections, 2016–2025, with **zero fetch
failures and zero parse anomalies**. The 2023 municipal general election is
larger than every other election combined; it was scraped separately in ~6h.

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
| `2023-kovo-5-savivaldybiu-tarybu-ir-meru` | 13796 | 1557 | 541 | 433 |
| **total** | **19420** | **2030** | **694** | **2924** |

Records live under `data/<election-id>/` (~750 MB) and are **not** version
controlled — `data/`, `sitemaps/` and `samples/` are gitignored, so the corpus is
reproduced by running the scrapers rather than by cloning.

### The 2023 municipal general election

`2023-kovo-5-savivaldybiu-tarybu-ir-meru` is on its own in the table above
because it is bigger than every other election combined. Its counts reconcile
exactly with VRK's own `savKandidataiSuvestine.html` summary:

| | scraped | VRK publishes |
|---|---:|---:|
| candidates (union of both listings) | 13,796 | 13,796 |
| mayoral candidates | 433 | 433 |
| council candidates | 13,769 | 13,769 |
| standing for both | 406 | — |
| party/committee lists | 467 | 467 |
| elected mayors | 60 | 60 |
| elected council members | 1,498 | 1,498 |

The two listings overlap rather than nest: 406 people appear in both under the
same VRK candidate id, and 27 mayoral candidates appear on no list, so
433 + 13,769 − 406 = 13,796. The elected total is 1,557 distinct people rather
than the 1,558 mandates, because one person — Erlandas Galaguz in Visaginas —
won a council seat and the mayoralty at once.

The full run took ~6h at the default 0.4s throttle (~1.6s per candidate) with
zero fetch failures, zero failed candidates and zero parse anomalies. Getting
there needed two fixes to `scripts/run_election_batches.sh`, which no earlier
election was large enough to stress: the pending-list rebuild ran one `grep`
per candidate per batch — around 965,000 subprocesses over an election this
size — and it re-queued permanently failing candidates forever, so a single
unfetchable page would have made an unattended `MAX_BATCHES=0` run loop without
end.

Two fields are null for a noticeable minority, and both are genuinely blank
upstream rather than parser misses: `biografija.tautybe` for 471 candidates
(3.4%), published as `Nenurodė`, and `anketa.einamos-pareigos` for 313 (2.3%),
published as `-`.

### The 2019 municipal general election is still being scraped

`2019-kovo-3-savivaldybiu-tarybu` has **no row in the inventory above**: its
full run is in progress as this is written, so any record count here would be
wrong by the time it is read. What is settled is the sitemap, every number of
which reconciles with VRK's own `savKandidataiSuvestine.html`:

| | in the sitemap | VRK publishes |
|---|---:|---:|
| candidates (union of both listings) | 13,666 | 13,666 |
| mayoral candidates | 410 | 410 |
| council candidates | 13,635 | 13,635 |
| standing for both | 379 | — |
| party/coalition/committee lists | 465 | 465 |
| elected mayors | 60 | 60 |
| elected council members | 1,442 | 1,442 |

The two listings overlap rather than nest, as in 2023: 410 + 13,635 − 379 =
13,666, with 31 mayoral candidates on no list at all. Roles partition as 13,256
council-only, 379 dual and 31 mayor-only.

When the run finishes, re-read the counts from `data/2019-kovo-3-savivaldybiu-tarybu/`
rather than from this page, and note that two of its fields are role-dependent
rather than sparse: the candidate photo and the free-text biography are
published only for candidates standing for mayor, so ~97% of records will have
neither. That is upstream behaviour, not a parse failure.

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
| `2023-kovo-5-savivaldybiu-tarybu-ir-meru` | 433 | 58 | one campaign across 59 candidates |
| `2020-seimo` | 758 | 298 | none shared |
| `2016-seimo` | 672 | 324 | none shared |

The effect is large. For 2019 EP, naively adding donation amounts across
candidate records gives €29.2M; de-duplicating by campaign gives **€1.44M** — a
20× inflation. Always group by campaign identity (`sprendimo-numeris`, or the
`campaignKey` in `rawData`) before summing.

The 2023 municipal election is the sharpest illustration of *why* the sharing
happens: only 11 of its 433 campaign participants are `Savarankiškas` (running
their own campaign), and the other 422 are `Atstovaujamasis` — their party runs
the campaign, so dozens of candidates share one participant record. Naive
summing gives €495,154; de-duplicated it is **€295,300**, a 1.7× inflation.
The factor is smaller than 2019 EP's only because most of those 422 candidates
share campaigns that declared nothing at all.

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

Twelve defects were found and fixed while building the newer modules. Each had
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
| income aliases reworded between 2017 and 2019 | the 2019 municipal module first reused `2017-balandzio-23-meru`'s asset/income aliases, which name GPM308 field numbers (`Gautų pajamų suma (GPM308 formos 12, 13, 14 … laukelių suma)`). 2019 states the same two figures in prose, so both income keys normalized to null while the values sat in `rawData`. With module-local aliases, `gautos-pajamos` and `sumoketas-pajamu-mokestis` went from **0/9 to 9/9 fixture candidates populated** |
| a nested conviction table erasing the questionnaire | `_is_records_table` decided with `table.find("th")`, which searches descendants. VRK nests the conviction-detail table inside the anketa table for anyone who answers the conviction question "Taip", so the whole anketa was classified as a records table and dropped — birth date, address, every declaration, birthplace, nationality — with no anomaly and nothing left in `rawData`. Confirmed on a 2019 candidate: **13 parsed rows instead of 27, every field null, including the conviction declaration itself**. The helper is inherited by ten modules, so every election has been under-reporting exactly the people the field exists to identify |
| declarations 2019 asks and 2017 does not | reusing the 2017 mayoral parser assumed the same question set. Q8.1 (unserved sentence), Q9.2 (decriminalised offence), Q9.3 (foreign court) and Q9.4 (political persecution) are published and answered on every 2019 page and were dropped from `normalized`; `pareiskimai` went from **five keys to nine**. Q21 free text was lost too — 2017 numbers that question at the end of the prompt and is matched on prompt text, 2019 numbers it at the front |
| donations section whose heading carries its own empty-state marker | a campaign with nothing to declare renders `Gautos ir priimtos aukos: Duomenų nėra` inside the heading rather than as the text node that normally follows it. No table or text node follows, so the next heading overwrote the pending title and the section vanished — collapsing "declared no donations" into "section never published", and leaving the sections after it untitled. **6 sections recovered across 3 elections** in the fixture corpora |

Every fix was verified by re-parsing all elections and confirming the diff was
confined to the intended records.

Those figures were measured over the **fixture corpora only**. The 2023
municipal full run is the first real test of them, and it shows how badly a
fixture sample can understate a fix: across its 13,796 records the private-
interest fix recovered free text for **734 candidates** (the fixtures had
suggested 2), and the empty-donations fix kept **344 sections** that would
otherwise have vanished (the fixtures had suggested 6). The campaign-decisions
fix went the other way — only 1 record in this election carries a decision,
because just 433 of its candidates have a campaign at all; that fix matters
more to the Seimas and EP elections, where most candidates do.

The other elections have **not** been re-run since these fixes landed, so their
rows in the inventory above still reflect the pre-fix parse. Re-running them is
the outstanding work.

All three were found the same way: by reading every field of every fixture
candidate in a new module and treating each null or empty value as a question
rather than a result. All three sat in shared code with no test coverage, and
each now has one.

## Known gaps

- The corpus covers the elections implemented so far. VRK publishes further
  by-elections and older elections that have no module yet.
- Every election except `2023-kovo-5-savivaldybiu-tarybu-ir-meru` was last
  scraped before the campaign-decisions, private-interest free-text and
  empty-donations fixes landed, so their records are stale in exactly the ways
  those fixes address. Their inventory rows are pre-fix counts.
- `2019-kovo-3-savivaldybiu-tarybu` does not normalize the Q9.1 conviction
  *detail* table — date, country, court and offence per conviction. VRK renders
  it in a row of its own inside the anketa, and the shared 2016-era row merging
  consumes that row before the record-table lookup can attach it, so the detail
  is absent from `rawData` too. The yes/no declaration
  `ar-buvote-pripazintas-kaltu` is captured correctly, and that is the field to
  count on; `2021-spalio-10-meru` normalizes the identical table as
  `teistumo-detales.irasai`, so the shape to copy exists. Fixing it means
  changing row-merging logic several elections share, which wants its own pass
  with measured impact rather than a change made alongside a full scrape.
- The repeat Visaginas mayoral vote of 2023 is a separate election with its own
  VRK path (`/rinkimai/1344/rnk1664/`) and has no module; it is not part of the
  13,796.
- `2024-ep` and `2024-prezidento` candidate pages carry no campaign tab, so
  those elections have no donation data at all — campaigns were run by the party
  lists and are published outside the candidate pages.
- Donation *records* were historically dropped by the shared parser; the totals
  in older analyses of this repo predate that fix and should be recomputed.
