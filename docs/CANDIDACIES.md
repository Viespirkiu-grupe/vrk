# The canonical candidacy table

One row per (person, election) over the whole corpus — the derived layer
issue #93 asked for. The 55 per-election schemas stay exactly as they are
(they are faithful to 55 genuinely different VRK page families); this table
is where they become *comparable*: education on one ordinal, money in one
currency with its measure named, party through the canonical registry,
identity through the persistent person id.

```bash
python scripts/build_candidacy_table.py                    # build + fill gate
python scripts/build_candidacy_table.py --update-baseline  # after a deliberate change
python scripts/build_candidacy_table.py 2024-seimo         # subset, no gate
```

Reads `data/`, `docs/concept-map.json` and the registries; writes to
`dist/` (gitignored):

| file | contents |
|---|---|
| `candidacies.csv.gz` | 113,073 rows × 52 columns, ~12 MB gzipped |
| `campaigns.csv.gz` | one row per campaign-finance participant (4,729) |
| `vrk.sqlite` | the same two as tables, plus `elections`, `persons`, `parties`, `party_predecessors`, with indexes |

Nothing here overwrites `normalized`: the projector only reads, and every
value it emits is derivable again from the record files. The one hand-curated
input beyond the registries is `SOURCE_ERRORS` in the script — three
declarations whose figures are byte-faithful to VRK's page while the page
itself is arithmetically impossible (a 334M Lt income against an 11k
employment row); they carry `quality_flags: saltinio-klaida` and are never
filtered.

```bash
sqlite3 dist/vrk.sqlite "SELECT election_id, AVG(education_higher)
  FROM candidacies WHERE education_level IS NOT NULL GROUP BY 1"
```

## Columns

**Identity & context.** `person_id` (the pid of
[DASHBOARD.md](DASHBOARD.md) — blake2s over the natural name+birth key, with
`scraper/person_overrides.json` merges applied, so it survives rebuilds),
`election_id` / `election_date` / `election_kind` (from
`scraper/elections.json`; kind ∈ `seimo` | `savivaldybiu` | `prezidento` |
`ep` | `mero`), `candidate_id`, `candidate_name`, `source_url`,
`birth_date`, `birth_place`.

**Candidacy** (resolved by `scraper/shared/kandidatura.py` across the five
`kandidatavimas` shapes). `role` — `seimo-narys` | `tarybos-narys` | `meras`
| `prezidentas` | `ep-narys`; a 2019/2023 council-and-mayor dual candidacy
takes `meras` and keeps its council list fields. `constituency` (Seimas
single-mandate), `municipality`, `list_name`, `list_position`,
`post_election_position`. `party_id` / `party_name_raw` / `nomination_kind`
are the canonical nominator join (`scraper/parties.json`, issue #82).
`elected` is 1/0, empty only where no results exist: the five 2000
municipalities whose results tree VRK does not publish (the 1997 municipal
pair was the larger gap until issue #92 joined its elected pages) — 99.3 %
filled overall.

**Education** (issue #88; `scraper/shared/education.py`).
`education_status` types the absence — the difference between a candidate
who declined and a page that never asked:

| `education_status` | meaning |
|---|---|
| `nurodyta` | a level answer was published; `education_level` is empty only for the ~0.6 % of answers the taxonomy does not map ("Nereglamentuojamas") |
| `nenurode` | the page itself prints the decline (`Išsilavinimas: Nenurodė`) — 7,810 records, an answer, not a gap |
| `neskelbta` | the election publishes no level for anyone: `2000-seimo` (whose true higher-education share is ~77 %, not the 0 % a naive read gives), `2002-prezidento`, `2004-prezidento` |
| `neatsakyta` | the form asks; this page shows no answer |

`education_level` is a 13-tier ordinal (`pradinis` < `pagrindinis` <
`nebaigtas-vidurinis` < `vidurinis` < `profesinis-vidurinis` <
`aukstesnysis` < `nebaigtas-aukstasis` < `aukstasis-nedetalizuotas` <
`aukstasis-neuniversitetinis` < `aukstasis-universitetinis` <
`aukstasis-bakalauras` < `aukstasis-magistras` < `doktorantura`), the
highest tier any of the record's level values states; `education_level_rank`
is its 1–13 number. The bare "Aukštasis" — 39 % of all level tokens, and the
*only* higher-education option the 1996–2007 forms offered — keeps its own
tier (`aukstasis-nedetalizuotas`) rather than being guessed into
university/non-university; era-comparable questions use `education_higher`
(rank ≥ `aukstasis-nedetalizuotas`). `education_unfinished` flags an
explicitly unfinished level, `education_degree` reads the academic-degree
fields (`nera` < `bakalauras` < `magistras` < `daktaras` <
`habilituotas-daktaras`), including the eight elections whose page fused the
degree and title questions into one row, and `education_entries` is the
entry list as JSON with `2004-ep`'s institution-key spelling folded in.
Fill: 82.4 % of all records carry a mapped level; 59.9 % of all records are
higher-educated on the all-records denominator, 72.7 % on the answered-only
one — always print the denominator, the three municipal generals change
*direction* between the two conventions.

**Money** (issue #97; `scraper/shared/deklaracijos.py`). Everything in EUR:
`declared_currency` is `Lt` or `EUR` (`EUR` made explicit — in the records
the euro era is marked only by the *absence* of `valiuta`), and
`currency_rate` the divisor applied (3.4528, the irrevocable changeover
rate, or 1.0). `declaration_status` types the missing section: `yra` /
`archyvo-skenai` (`2002-prezidento`, published only as page scans) / `nera`
(855 records). The eleven declaration keys become
`assets_registered_eur`, `securities_eur`, `cash_eur`, `loans_given_eur`,
`loans_received_eur`, `income_eur`, `income_tax_eur`,
`self_employment_income_eur`, `self_employment_deductions_eur`,
`asset_sale_income_eur`, `asset_acquisition_cost_eur`, plus
`declaration_year` where the page states one.

Comparability is carried by the **measure columns**, because the same key
measures different things across eras:

| column | values | the trap it names |
|---|---|---|
| `assets_measure` | `skaidytas` \| `turtas-plius-lesos` \| `turtas-plius-vp` | `assets_total_eur` is property+securities+cash summed from split rows (2004 on), the 1996–2000 form's single combined row, or 2002's property-and-securities row plus its cash row. The archive eras leave the modern keys as null placeholders — summing the documented seven keys reads €0 for 17,654 declarations that do state their wealth |
| `income_measure` | `neto-archyvas` \| `fr0462` \| `gpm-bruto` \| `deklaruota-apmokestinamos` | 1996–2002 income is **net of tax** (provable from the numbers: the modal tax/income ratio there exceeds the era's statutory rate); everything from 2004 on is gross. 23,141 populated records are net |
| `tax_measure` | `sumoketas` \| `moketinas` | the tax row flips from tax *paid* to tax *payable* with the 2018 rewording |

`income_gross_eur` is the comparable series: the declared figure where the
era is gross, `income + tax` re-grossed where it is net (the two rows of the
same form), empty where a net figure's tax row is unpublished.
`income_floor_only` marks the 4,628 archive records whose usable figure is
the employment row alone (a floor, not a total — the `deklaruotos-pajamos`
concept); their `income_tax_eur` is the employment tax row to match.

**Campaign finance.** `campaign_key` is
`rawData…campaigns[].campaignKey`, present on every record that has the
section (20,199 of 20,199) — **the one correct key for grouping donations**;
see the caveat in [DATASET.md](DATASET.md#campaign-donations-are-per-campaign-not-per-candidate)
for why every other grouping multiplies money (up to 1,182×) or destroys it.
`campaign_status` is `savarankiskas` | `atstovaujamasis`; an
`atstovaujamasis` participant with no donation data is *financed through the
party's campaign*, not "declared nothing". The `campaigns` table carries one
row per participant: `campaign_key`, `election_id`, `label`, `status`,
`candidacies` (how many rows share it), `donations_total_eur` (VRK's own
accepted-donations "Iš viso", EUR-converted, empty where the participant
publishes no donation data).

**Conviction.** `conviction_status` is the `teistumas` concept (`neklausta`
/ `ne` / `deklaruota-be-detaliu` / `deklaruota`), `conviction_details` the
flattened entries and free-text explanation as JSON where declared.

## The fill gate

`docs/candidacy-baseline.tsv` checks in the per-column, per-election fill
rate of every gated column (2,750 cells). A plain build fails when a rate
falls more than `--max-drop` points below the baseline, or when a cell no
record fills appears without a classified reason — the shape of the
2020-income defect ([FIELD_COVERAGE.md](FIELD_COVERAGE.md)), which this
table would otherwise inherit silently. The 519 zero cells that are real all
carry a status and a note ("a single-mandate Seimas by-election; no party
list on the ballot"); `--update-baseline` auto-classifies only the zeros the
builder can structurally explain and refuses the rest.

## What this table is not

It is a *projection*: the full questionnaires, the per-declaration sections,
the private-interest declarations, donation row lists and photos stay in the
record files (`data/<election-id>/…`, [DATA_GUIDE.md](DATA_GUIDE.md)). A
column here answers "compare candidates across elections"; anything deeper
starts from `candidate_id` + `election_id`, which every row carries — or
from the full-corpus database below, which carries the record files too.

## Distribution

Issue #94: the corpus had exactly one consumer because there was no way to
get it — `data/` is gitignored and the alternative was a ~27-hour scrape.
`scripts/build_distribution.py` builds what a release ships:

```bash
python scripts/build_distribution.py                    # full corpus + fill gate
python scripts/build_distribution.py 2019-prezidento    # subset, no gate
```

| release asset | contents |
|---|---|
| `candidacies.csv.gz` | the flat table above |
| `campaigns.csv.gz` | one row per campaign-finance participant |
| `vrk.sqlite.gz` | the analysis database above, gzipped |
| `vrk-corpus.sqlite.gz` | **everything**: the analysis tables plus `records`, `photos`, `anomalies` |
| `MANIFEST.json` | per-election record counts, build date, parser commit, sha256 + bytes per asset |

`elections` is the registry as a table — `id, date, kind, parent, name,
shortName, records` — where `parent` is the general election whose term a
by-election, repeat or re-vote fills, NULL for a general election, so
`COALESCE(parent, id)` groups candidacies by term (issue #122).
`party_predecessors(party_id, predecessor_id)` is the nominator registry's
lineage (issue #123): one row per organisation a party, coalition or
committee continues — the merged parties behind `ts-lkd`, the committee and
the 2011 coalition behind `vieningas-kaunas`. The links form a forest, so a
recursive CTE from a `party_id` down the `predecessor_id` column collects
its whole history without cycles:

```sql
WITH RECURSIVE lineage(party_id) AS (
  SELECT 'ts-lkd'
  UNION SELECT predecessor_id FROM party_predecessors JOIN lineage USING (party_id)
)
SELECT party_id, COUNT(*) FROM candidacies WHERE party_id IN lineage GROUP BY 1;
```

The build refuses a table that fails the fill gate, an envelope key it does
not know, a photo sidecar that is missing or hashes differently from the
record's own `photoMeta.sha256`, and an inline base64 portrait (zero remain
since the 2026-08-29 re-parse; one reappearing means an election regressed).
The candidacy-table pass and the records pass must agree on the record
count.

In `vrk-corpus.sqlite` the three extra tables are:

- `records(election_id, candidate_id, candidate_name, record_file,
  source_json, kandidatavimas_json, candidate_note, photo_sha256, raw_json,
  norm_json)` — one row per record file, primary key
  `(election_id, candidate_id)`. `raw_json` / `norm_json` are the record's
  `rawData` / `normalized`, compact-serialized (the files are
  pretty-printed; 34.5 % of `data/` was whitespace). The original record
  reassembles losslessly from the row — `reconstruct_record` in the script
  is the contract and a test pins the round trip.
- `photos(sha256, mime, bytes, data)` — every sidecar portrait, stored once
  by content hash; `records.photo_sha256` is the join. URL-form portraits
  (25,305 records, the pre-2016 and 2020+ eras) remain URLs pointing at
  vrk.lt — VRK never served this scraper those bytes, and archiving them is
  issue #94's still-open network job.
- `anomalies(election_id, event_json)` — the per-election
  `anomalies.jsonl` logs, so "what went wrong" travels with the data.

```sql
-- a candidacy, its full record and its portrait, in one query
SELECT c.candidate_name, c.income_eur, r.norm_json, p.data
FROM candidacies c
JOIN records r USING (election_id, candidate_id)
LEFT JOIN photos p ON p.sha256 = r.photo_sha256
WHERE c.election_id = '2019-prezidento';
```

Releases are tagged `corpus-YYYY-MM-DD` (the manifest's `version`), so the
corpus is versioned by release tag rather than by whatever happens to be on
one disk; `parserCommit` in the manifest names the exact code that produced
it. A full build prints the `gh release create` line, filled in.
