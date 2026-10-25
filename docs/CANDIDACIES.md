# The canonical candidacy table

One row per (person, election) over the whole corpus. The 55 per-election
schemas stay as they are; this table makes them comparable: education on one
ordinal, money in one currency with its measure named, party through the
registry, identity through the person id.

```bash
python scripts/build_candidacy_table.py                    # build + fill gate
python scripts/build_candidacy_table.py --update-baseline  # after a deliberate change
python scripts/build_candidacy_table.py 2024-seimo         # subset, no gate
```

Reads `data/`, `docs/concept-map.json` and the registries; writes to `dist/`
(gitignored):

| file | contents |
|---|---|
| `candidacies.csv.gz` | 113,073 rows × 73 columns, ~13 MB gzipped |
| `campaigns.csv.gz` | one row per campaign-finance participant (4,729) |
| `vrk.sqlite` | the same two as tables, plus `elections`, `persons`, `parties`, `party_predecessors`, `municipalities`, with indexes |

The projector only reads: every value is derivable again from the record
files. `SOURCE_ERRORS` in the script lists three declarations whose figures
match VRK's page while the page is arithmetically impossible; they carry
`quality_flags: saltinio-klaida` and are not filtered.

```bash
sqlite3 dist/vrk.sqlite "SELECT election_id, AVG(education_higher)
  FROM candidacies WHERE education_level IS NOT NULL GROUP BY 1"
```

## Columns

**Identity and context.**

- `person_id` — the pid ([DASHBOARD.md](DASHBOARD.md)): blake2s over the
  name+birth key, with `scraper/person_overrides.json` merges applied.
- `election_id`, `election_date`, `election_kind` (`seimo` | `savivaldybiu`
  | `prezidento` | `ep` | `mero`), from `scraper/elections.json`.
- `candidate_id`, `candidate_name`, `source_url`, `birth_date`,
  `birth_place`.
- `nationality` — declared nationality folded from 117 spellings into 45
  census groups (`lietuviai`, `lenkai`, `rusai`, …;
  `scraper/shared/tautybe.py`). Empty where the form does not ask (the 2000
  municipal and Seimas cards, the 2002 and 2004 presidential pages, every
  form from 2024). It is special-category data; see
  [PERSONAL_DATA.md](PERSONAL_DATA.md).

**Candidacy** (`scraper/shared/kandidatura.py`).

- `role` — `seimo-narys` | `tarybos-narys` | `meras` | `prezidentas` |
  `ep-narys`. A council-and-mayor dual candidacy takes `meras` and keeps its
  list fields.
- `party_id`, `party_name_raw`, `nomination_kind` — the nominator join
  (`scraper/parties.json`).
- `municipality`, `municipality_id` — the body's official name and id
  (`scraper/municipalities.json`), whatever the era's card said. The two
  1997 Marijampolė bodies merged in 2000 keep their own ids.
- `constituency` — the district's one name across label eras
  (`scraper/shared/apygardos.py`); `constituency_number` its number in that
  election. The boundary is (election, number); the name is for reading.
  Era-split names like "Dainavos (iki 2016)" are the dashboard's only.
- `list_name`, `list_position`, `post_election_position`; `list_movement` =
  `list_position − post_election_position`, positive when preference votes
  moved the candidate up.
- `elected` — 1/0 for any office on this ballot; empty only where no results
  exist (the five 2000 municipalities whose results VRK does not publish).
- `elected_council`, `elected_mayor` — each office's own outcome on a
  council-and-mayor dual candidacy. **Read the mayoralty off
  `elected_mayor`**, never `role = 'meras' AND elected = 1`, which also
  counts mayoral candidates who won only a council seat. 2015 has 57 elected
  mayors because three races were re-run in June.

**Electoral result** (26 elections carry votes).

- `preference_votes` — the candidate's votes on the list;
  `preference_votes_measure` is `pirmumo-balsai`, or `teigiami-balsai` on
  `1996-spalio-20-seimo` (positive votes under a points system).
- `list_votes` — the list's total (2000 and 2002 municipal only).
- `constituency_votes`, `constituency_round` (1 or 2), `constituency_place`,
  `constituency_votes_pct` (of valid ballots) — the single-winner race's last
  round contested; the whole country for a presidential candidate.
- `votes_source` — the VRK page the figures came from.

Other elections' vote columns are empty and their baseline rows say
`parser-gap`: VRK publishes those results on pages the corpus does not read.

**Education** (`scraper/shared/education.py`).

| `education_status` | meaning |
|---|---|
| `nurodyta` | a level was published; `education_level` is empty only for the ~0.6 % of answers the taxonomy does not map |
| `nenurode` | the page prints the decline (`Išsilavinimas: Nenurodė`): an answer, not a gap |
| `neskelbta` | the election publishes no level for anyone: `2000-seimo`, `2002-prezidento`, `2004-prezidento` |
| `neatsakyta` | the form asks; this page shows no answer |

- `education_level` — 13 tiers: `pradinis` < `pagrindinis` <
  `nebaigtas-vidurinis` < `vidurinis` < `profesinis-vidurinis` <
  `aukstesnysis` < `nebaigtas-aukstasis` < `aukstasis-nedetalizuotas` <
  `aukstasis-neuniversitetinis` < `aukstasis-universitetinis` <
  `aukstasis-bakalauras` < `aukstasis-magistras` < `doktorantura`; the
  highest any level value states. `education_level_rank` is 1–13.
- The bare "Aukštasis", the only higher option the 1996–2007 forms offered,
  is `aukstasis-nedetalizuotas`. Compare eras with `education_higher` (rank ≥
  that tier).
- `education_unfinished`, `education_degree` (`nera` < `bakalauras` <
  `magistras` < `daktaras` < `habilituotas-daktaras`), `education_entries`
  (JSON).

82.4 % of all records carry a mapped level; 59.8 % of all records are
higher-educated on the all-records denominator, 72.6 % on the answered-only
one. Always print the denominator: three municipal generals change direction
between the two.

**Money** (`scraper/shared/deklaracijos.py`). Everything in EUR.

- `declared_currency` — `Lt` or `EUR`; `currency_rate` — the divisor applied
  (3.4528 or 1.0).
- `declaration_status` — `yra` (112,218 records) / `archyvo-skenai` (17 —
  `2002-prezidento`, published only as scans) / `nera` (838).
- `assets_registered_eur`, `securities_eur`, `cash_eur`, `loans_given_eur`,
  `loans_received_eur`, `income_eur`, `income_tax_eur`,
  `self_employment_income_eur`, `self_employment_deductions_eur`,
  `asset_sale_income_eur`, `asset_acquisition_cost_eur`, `declaration_year`.
- `declaration_form` — `FR0462` to 2007, then `GPM305`, `GPM308`, `GPM311`;
  none printed before 2004.
- `declaration_scope` — `gyventojo` (the candidate's), `gyventojo-seimos`
  (with the family's) or `seimos`. Check it before comparing two figures.

The same key measures different things across eras, so read the **measure
columns**:

| column | values | the trap it names |
|---|---|---|
| `assets_measure` | `skaidytas` \| `turtas-plius-lesos` \| `turtas-plius-vp` | `assets_total_eur` is property+securities+cash from split rows (2004 on), the 1996–2000 form's single combined row, or 2002's property-and-securities row plus cash. Summing the seven split keys reads €0 for 17,799 declarations that do state their wealth |
| `income_measure` | `neto-archyvas` \| `fr0462` \| `gpm-bruto` \| `deklaruota-apmokestinamos` | 1996–2002 income is **net of tax**; from 2004 it is gross. 27,795 records carry a net figure (27,816 rows are typed `neto-archyvas`) |
| `tax_measure` | `sumoketas` \| `moketinas` | tax *paid* until the 2018 rewording, tax *payable* after |

- `income_gross_eur` — the comparable series: gross as declared, or net +
  tax re-grossed, empty where a net figure's tax row is unpublished.
- `income_floor_only` — the archive records whose figure is the employment
  row alone (a floor, not a total); `income_tax_eur` is that row's tax.

**Campaign finance.**

- `campaign_key` — **the one correct key for grouping donations**; any other
  grouping multiplies or loses money (see
  [DATASET.md](DATASET.md#campaign-donations-are-per-campaign-not-per-candidate)).
- `campaign_status` — `savarankiskas` | `atstovaujamasis`. An
  `atstovaujamasis` participant without donation data is financed through
  the party's campaign, not "declared nothing".
- The `campaigns` table: `campaign_key`, `election_id`, `label`, `status`,
  `candidacies` (rows sharing it), `donations_total_eur` (VRK's accepted
  donations total, in EUR; empty where unpublished).

**Conviction.** `conviction_status` — `neklausta` / `ne` /
`deklaruota-be-detaliu` / `deklaruota`; `conviction_details` — the entries
and explanation as JSON.

**Declarations** (`scraper/shared/pareiskimai.py`). Sixteen statutory yes/no
concepts: foreign citizenship, a foreign oath, military service, an
incompatible office, another state's elected body, collaboration with
foreign or Soviet special services, a lost mandate.

- `declarations_status` — `neklausta` (the form asks none), `iprasti` (every
  answer the usual one) or `nukrypstantys`.
- `declarations_flagged` — the departing answers as `{concept: answer}`.
- *Usual* is per question: presidential eligibility questions expect
  "Taip", and the answer echoes the verb (Esu/Nesu, Turiu/Neturiu). The
  commonest departure is an office-holder declaring the office they would
  leave.

**Prior office.** `prior_office` — the `anksciau-isrinktas` offices as
"institution (period)" joined by "; ", on the 39 elections that ask; empty
for "Nebuvo".

## The fill gate

`docs/candidacy-baseline.tsv` holds the per-column, per-election fill rate
of every gated column. A plain build fails when:

- a rate falls more than `--max-drop` points below the baseline;
- an unfilled cell appears without a classified reason;
- a classified reason has gone false (a *stale excuse*, see
  [FIELD_COVERAGE.md](FIELD_COVERAGE.md)).

`--update-baseline` classifies only zeros the builder can explain
structurally and refuses the rest. `tests/test_candidacy_table.py` checks
every structural rule against the checked-in rates, without a corpus.
`conviction_details`, `declarations_flagged` and `prior_office` are not
gated.

## What this table is not

A projection. Full questionnaires, per-declaration sections, private
interests, donation rows and photos stay in the record files
([DATA_GUIDE.md](DATA_GUIDE.md)). Go deeper from `candidate_id` +
`election_id`, or from the full-corpus database below.

## Distribution

`scripts/build_distribution.py` builds what a release ships:

```bash
python scripts/build_distribution.py                    # full corpus + fill gate, public profile
python scripts/build_distribution.py 2019-prezidento    # subset, no gate
python scripts/build_distribution.py --profile full     # the archive verbatim
```

| release asset | contents |
|---|---|
| `candidacies.csv.gz` | the flat table above |
| `campaigns.csv.gz` | one row per campaign-finance participant |
| `coverage.tsv` | every concept of `docs/concept-map.json` and every column of this table against every election (`mapped` 0 where the form never asks) |
| `vrk.sqlite.gz` | the analysis database, with `coverage.tsv` as its `coverage` table |
| `vrk-corpus.sqlite.gz` | **everything but the image bytes**: the analysis tables plus `records`, `photos`, `anomalies` |
| `vrk-photos-N.sqlite` | the portraits, one row per unique image, split to keep each asset under GitHub's 2 GiB cap; not gzipped |
| `vrk-web-portraits.tar` | `portraits/<pid>.webp`, the web portraits the browser shows; production unpacks this instead of the photo parts. Full builds only, refused if `portraits/` disagrees with its manifest |
| `MANIFEST.json` | `schemaVersion`, per-election counts, build date, `buildCommit` (dirty-aware), `corpusParserCommits`, `photoParts`, `webPortraits` (count, bytes, the version the index's `portraits.v` must match, encoder settings), sha256 + bytes per asset, and the terms (`license`, `dataLicense`, `attribution`, `terms`, `source` — [DATA_TERMS.md](../DATA_TERMS.md)) |

The build refuses:

- a table that fails the fill gate, or an envelope key it does not know;
- a photo sidecar that is missing or hashes differently from
  `photoMeta.sha256`, or an inline base64 portrait;
- any asset over 2 GiB;
- a whole-archive build (no election named) over a `data/` that lacks a
  registered election. Naming elections makes a subset build, marked
  `subset` in the manifest; `counts.electionsRegistered` sits beside
  `counts.elections`.

Everything is written into `dist/.staging-<pid>/` and moved into place only
once the manifest exists, so a failed build leaves `dist/` as it was.

**Profiles.** `--profile public`, the default, removes the campaign
treasurer's and auditor's phone and e-mail (both layers; listed in
[PERSONAL_DATA.md](PERSONAL_DATA.md#what-the-public-release-drops) and
`PUBLIC_PROFILE_DROPS` in `scripts/pii_inventory.py`) and the campaign's own
contact line where it repeats one. It also strips Exif, XMP, IPTC and
comment blocks from portraits (`scraper/shared/image_metadata.py`).
`--profile full` ships the archive verbatim. `MANIFEST.json` records
`profile`, the `redaction` paths, the number of values removed and
`counts.photosStripped`.

**Back to `data/`.** `scripts/unpack_corpus.py` rebuilds the record files,
each election's `anomalies.jsonl` and the portrait sidecars from the photo
parts:

```bash
gh release download --pattern 'vrk-corpus.sqlite.gz' --pattern 'vrk-photos-*.sqlite'
gunzip vrk-corpus.sqlite.gz
python scripts/unpack_corpus.py vrk-corpus.sqlite            # -> ./data
python scripts/unpack_corpus.py vrk-corpus.sqlite --into /tmp/corpus
python scripts/unpack_corpus.py vrk-corpus.sqlite --no-photos # records only
```

- An election whose photo part is missing is refused; `--photos DIR` points
  at the parts.
- Under `--profile full` the round trip is exact (records, key order,
  portrait bytes). Under the public profile the redacted keys are absent,
  not nulled.
- Then run `build_person_index.py` and `build_candidacy_table.py` on the
  tree.

### Tables

Both databases carry `meta(key, value)` (`schemaVersion`, `profile`,
`builtAt`, `buildCommit`, row counts, licence, attribution) and the schema
version in `PRAGMA user_version`.

- `elections(id, date, kind, parent, name, shortName, records)` — `parent`
  is the general election whose term a by-election fills, NULL on a general;
  `COALESCE(parent, id)` groups by term.
- `municipalities(municipality_id, name, kind, county, until)` — `kind` ∈
  `miesto` | `rajono` | `savivaldybe`; `county` in the genitive (`Vilniaus`,
  `Kauno`, …).
- `persons(person_id, name, birth_key, candidacies, elections,
  merged_keys)` — `name` is the latest spelling; `birth_key` is
  `NAME|YYYY-MM-DD`, `NAME|~YYYY` or `NAME|?`; `merged_keys` counts other
  keys folded in by overrides.
- `party_predecessors(party_id, predecessor_id)` — one row per organisation
  a nominator continues. The links form a forest:

```sql
WITH RECURSIVE lineage(party_id) AS (
  SELECT 'ts-lkd'
  UNION SELECT predecessor_id FROM party_predecessors JOIN lineage USING (party_id)
)
SELECT party_id, COUNT(*) FROM candidacies WHERE party_id IN lineage GROUP BY 1;
```

`vrk-corpus.sqlite` adds:

- `records(election_id, candidate_id, candidate_name, record_file,
  source_json, kandidatavimas_json, candidate_note_json, photo_sha256,
  raw_json, norm_json, provenance_json)` — one row per record file, key
  `(election_id, candidate_id)`. `raw_json`/`norm_json` are `rawData`/
  `normalized`, compact. `reconstruct_record` in the script rebuilds the
  record. `candidate_note_json` is JSON so a present-but-null
  `candidateNote` survives.
- `photos(sha256, mime, bytes, stripped, stripped_sha256, part)` — each
  portrait once by content hash, and the part holding its bytes. Each part
  has the same columns with `data` in place of `part`; `sha256` is always
  the archive's hash. A record still carrying an `http(s)://` portrait
  reference could not be fetched (`photoMeta.error` says why) and has no
  row.
- `anomalies(election_id, event_json)` — the per-election anomaly logs.

```sql
-- a candidacy, its full record and its portrait: one ATTACH per part that
-- MANIFEST.json's photoParts lists
ATTACH 'vrk-photos-1.sqlite' AS p1;
ATTACH 'vrk-photos-2.sqlite' AS p2;
ATTACH 'vrk-photos-3.sqlite' AS p3;
CREATE TEMP VIEW photo_data AS
  SELECT sha256, data FROM p1.photos UNION ALL
  SELECT sha256, data FROM p2.photos UNION ALL
  SELECT sha256, data FROM p3.photos;

SELECT c.candidate_name, c.income_eur, r.norm_json, d.data
FROM candidacies c
JOIN records r USING (election_id, candidate_id)
LEFT JOIN photo_data d ON d.sha256 = r.photo_sha256
WHERE c.election_id = '2019-prezidento';
```

Releases are tagged `corpus-YYYY-MM-DD` (the manifest's `version`). A full
build prints the `gh release create` line, filled in.
