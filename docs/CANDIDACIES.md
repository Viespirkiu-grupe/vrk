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
| `candidacies.csv.gz` | 113,073 rows × 67 columns, ~12 MB gzipped |
| `campaigns.csv.gz` | one row per campaign-finance participant (4,729) |
| `vrk.sqlite` | the same two as tables, plus `elections`, `persons`, `parties`, `party_predecessors`, `municipalities`, with indexes |

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
single-mandate), `municipality` / `municipality_id`, `list_name`,
`list_position`, `post_election_position`. `party_id` / `party_name_raw` /
`nomination_kind` are the canonical nominator join (`scraper/parties.json`,
issue #82), and `municipality_id` the canonical municipality join
(`scraper/municipalities.json`, issue #137): `municipality` is the body's
official name — `Vilniaus miesto savivaldybė` whether the era's card said
`Vilniaus miesto` (1997/2000/2002/2019/2023) or `Vilniaus miesto savivaldybė`
(2007/2011/2015) — so the 60 municipalities are 60 values, not 127; the two
1997 Marijampolė bodies the 2000 reform merged keep ids of their own
(`marijampoles-miesto`, `marijampoles-rajono`, `until: 2000` in the
`municipalities` table). The published wording stays in the record file.
`constituency` is the district's one name across the four label eras
(`scraper/shared/apygardos.py`, issue #133: "Akmenės Joniškio", "Akmenės -
Joniškio", "Aukštaitijos (Nr. 28)" and "33. Aukštaitijos" used to be four
values; 315 labels are 136 names) and `constituency_number` its number in
that election — the number moves with the 2016 redistricting, so the pair
(election, number) is the boundary and the name is for reading; the
2000–2012 cards' "Daugiamandatė" row, which 2,980 list-only candidates
shipped as their constituency, is empty now. `list_movement` is
`list_position − post_election_position`, positive when the preference
votes moved the candidate up; for the 2016–2025 elections, which publish no
vote counts the records carry, it is the only preference signal (90,809 rows
have both positions).
`elected` is 1/0 for **any office on this ballot**, empty only where no
results exist: the five 2000 municipalities whose results tree VRK does not
publish (the 1997 municipal pair was the larger gap until issue #92 joined its
elected pages) — 99.3 % filled overall. A council-and-mayor dual candidacy
(1,212 rows in 2015/2019/2023) is two offices with two outcomes, so
`elected_council` and `elected_mayor` carry each office's own: 1/0 where the
office was on the ballot and the result is known, empty otherwise. Read the
mayoralty off `elected_mayor`, never off `role = 'meras' AND elected = 1` —
that query returned 410 rows for 2019 and 433 for 2023, in a country with 60
mayors, because 448 of them won a council seat and lost the mayoral race
(issue #140). The per-office outcome comes from the 2019/2023 records' own
flags and, on the 2015 ballots, from the seat VRK's results named
(`isrinktasKaip`); 2015 has 57 elected mayors rather than 60 because three
mayoral races were annulled and re-run in June.

**Electoral result** (issue #133; `scraper/shared/kandidatura.py`). The
26 elections whose records carry a vote figure — the 2000–2004 static sites
on the candidate's own pages, the 2007–2015 trees joined by issue #99, the
1996–1999 archive family's candidacy list — project it as `preference_votes`
(the candidate's votes on the list; `preference_votes_measure` is
`pirmumo-balsai`, or `teigiami-balsai` on 1996-spalio-20-seimo, whose
rating system counted positive and negative votes and ranked by points),
`list_votes` (the **list's** total, kept apart by name; only the 2000 and
2002 municipal trees carry it), and the single-winner race's last round
contested — `constituency_votes`, `constituency_round` (1 or 2),
`constituency_place`, `constituency_votes_pct` (of valid ballots) — which
for a presidential candidate is the whole country. `votes_source` names the
VRK page the figures came from. 57,809 rows carry preference votes (30.9
million of them), 3,562 a race round, 424 of them runoffs. Every other election's vote columns
are empty and their baseline rows say `parser-gap`: VRK publishes those
results on pages the corpus does not read, which is not the same as their
not existing.

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
Fill: 82.4 % of all records carry a mapped level; 59.8 % of all records are
higher-educated on the all-records denominator, 72.6 % on the answered-only
one — always print the denominator, the three municipal generals change
*direction* between the two conventions.

**Money** (issue #97; `scraper/shared/deklaracijos.py`). Everything in EUR:
`declared_currency` is `Lt` or `EUR` (`EUR` made explicit — in the records
the euro era is marked only by the *absence* of `valiuta`), and
`currency_rate` the divisor applied (3.4528, the irrevocable changeover
rate, or 1.0). `declaration_status` types the missing section: `yra` (112,218 records) /
`archyvo-skenai` (17 — `2002-prezidento`, published only as page scans) /
`nera` (838). The eleven declaration keys become
`assets_registered_eur`, `securities_eur`, `cash_eur`, `loans_given_eur`,
`loans_received_eur`, `income_eur`, `income_tax_eur`,
`self_employment_income_eur`, `self_employment_deductions_eur`,
`asset_sale_income_eur`, `asset_acquisition_cost_eur`, plus
`declaration_year` where the page states one.

Comparability is carried by the **measure columns**, because the same key
measures different things across eras:

| column | values | the trap it names |
|---|---|---|
| `assets_measure` | `skaidytas` \| `turtas-plius-lesos` \| `turtas-plius-vp` | `assets_total_eur` is property+securities+cash summed from split rows (2004 on), the 1996–2000 form's single combined row, or 2002's property-and-securities row plus its cash row. The archive eras leave the modern keys as null placeholders — summing the documented seven keys reads €0 for 17,799 declarations that do state their wealth |
| `income_measure` | `neto-archyvas` \| `fr0462` \| `gpm-bruto` \| `deklaruota-apmokestinamos` | 1996–2002 income is **net of tax** (provable from the numbers: the modal tax/income ratio there exceeds the era's statutory rate); everything from 2004 on is gross. 27,795 records carry a net figure (27,816 rows are typed `neto-archyvas`) |
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
rate of every gated column (3,465 cells). A plain build fails when a rate
falls more than `--max-drop` points below the baseline, or when a cell no
record fills appears without a classified reason — the shape of the
2020-income defect ([FIELD_COVERAGE.md](FIELD_COVERAGE.md)), which this
table would otherwise inherit silently. The 1,026 zero cells that are real all
carry a status and a note ("a single-mandate Seimas by-election; no party
list on the ballot"); `--update-baseline` auto-classifies only the zeros the
builder can structurally explain and refuses the rest.

Those structural reasons are hand-written lists of election ids, and a list
written against one corpus goes stale under the next: issue #99's results
join recovered the post-election ranking for six of the eleven elections
`POST_RANKING_ABSENT` said had never printed one, and six baseline rows went
on denying 35,507 values (issue #165). Two things now stop that. The gate
reports a classification that has gone false — *stale excuse*, in
[FIELD_COVERAGE.md](FIELD_COVERAGE.md) — instead of skipping a classified
zero unread; and `tests/test_candidacy_table.py` measures every rule against
the checked-in rates, so a rule that excuses a column the baseline says is
filled fails on a clone with no corpus present. That test found a seventh
stale reason the audit had not: the 2024 presidential cards do print a
`Kandidatą iškėlė` row, over a note saying presidential pages name no
nominator.

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
python scripts/build_distribution.py                    # full corpus + fill gate, public profile
python scripts/build_distribution.py 2019-prezidento    # subset, no gate
python scripts/build_distribution.py --profile full     # the archive verbatim
```

| release asset | contents |
|---|---|
| `candidacies.csv.gz` | the flat table above |
| `campaigns.csv.gz` | one row per campaign-finance participant |
| `vrk.sqlite.gz` | the analysis database above, gzipped |
| `vrk-corpus.sqlite.gz` | **everything but the image bytes**: the analysis tables plus `records`, `photos` (one row per portrait, naming the part that holds it), `anomalies` — under the public profile, less the third-party contacts (below) |
| `vrk-photos-N.sqlite` | the portraits themselves, one row per unique image, in as many parts as keep each asset under GitHub's 2 GiB per-asset cap (issue #130); not gzipped, since JPEG and PNG do not shrink; under the public profile, without their metadata (below) |
| `MANIFEST.json` | `schemaVersion`, per-election record counts, build date, `buildCommit` (dirty-aware), `corpusParserCommits`, `photoParts` (each part's image count, bytes and elections), sha256 + bytes per asset, and the terms (`license`, `dataLicense`, `attribution`, `terms`, `source` — [DATA_TERMS.md](../DATA_TERMS.md), issue #138) |

**And back again.** `scripts/unpack_corpus.py` turns `vrk-corpus.sqlite`
into a `data/` tree — one JSON file per record in the corpus's own key
order, each election's `anomalies.jsonl`, and every portrait sidecar the
records name, read from the photo parts beside the database — so a download
is an alternative to the scrape and not just to reading it:

```bash
gh release download --pattern 'vrk-corpus.sqlite.gz' --pattern 'vrk-photos-*.sqlite'
gunzip vrk-corpus.sqlite.gz
python scripts/unpack_corpus.py vrk-corpus.sqlite            # -> ./data
python scripts/unpack_corpus.py vrk-corpus.sqlite --into /tmp/corpus
python scripts/unpack_corpus.py vrk-corpus.sqlite --no-photos # records only
```

An election whose portraits sit in a part that is not at hand is refused,
naming the part, rather than unpacked without them; `--photos DIR` says
where the parts are when they are not beside the database. A release from
before the parts (schema 1, `corpus-2026-08-30`) kept the bytes inside the
corpus database and unpacks the same way.

After it, `build_person_index.py` and `build_candidacy_table.py` run against
the unpacked tree. Under `--profile full` the round trip is exact: same
records, same key order, same portrait bytes, which
`tests/test_build_distribution.py`'s `CorpusRoundTrip` holds file for file.
Under the public profile the redacted paths are absent (not nulled), which
is what the manifest's `redaction` block lists. Nothing in the repository
read a release asset before issue #156 — 0 of the 21 scripts — so the assets
existed and the corpus behind them could not be reassembled.

**Both databases say what they are.** `meta(key, value)` carries
`schemaVersion`, `profile`, `builtAt`, `buildCommit`, the row counts, the
licence and the attribution, and `PRAGMA user_version` carries the schema
version too — so a 602 MB download can be identified with two queries and
no repository. Before, it was an anonymous 2.5 GB file.

`elections` is the registry as a table — `id, date, kind, parent, name,
shortName, records` — where `parent` is the general election whose term a
by-election, repeat or re-vote fills, NULL for a general election, so
`COALESCE(parent, id)` groups candidacies by term (issue #122).
`municipalities(municipality_id, name, kind, until)` is the municipality
registry as a table (issue #137): the 60 bodies of the 2000 reform plus the two
it dissolved, `kind` ∈ `miesto` | `rajono` | `savivaldybe`.
`persons(person_id, name, birth_key, candidacies, elections, merged_keys)` is
the identity layer as a table (issue #96): `person_id` is the `pid` the
dashboard puts in its URL — `p` plus 12 hex digits of blake2s over the
natural key — `name` the display name (the latest election's spelling),
`birth_key` the natural key itself (`NAME|YYYY-MM-DD`, or `NAME|~YYYY` where
only a year is published and `NAME|?` where nothing is), `candidacies` and
`elections` how many of each the person has, and `merged_keys` how many
*other* natural keys were folded into this person by
`scraper/person_overrides.json` — 0 for the great majority, and the count of
former names for a reviewed merge.
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
record's own `photoMeta.sha256`, an inline base64 portrait (zero remain
since the 2026-08-29 re-parse; one reappearing means an election regressed),
and any asset larger than the 2 GiB GitHub accepts (issue #130) — measured
on the staged file, before anything reaches `dist/`.
The candidacy-table pass and the records pass must agree on the record
count.

**A build that names no election claims the whole archive** (issue #132), so
it refuses one that does not hold it — before writing anything — naming the
registered elections `data/` lacks. Nothing used to: `elections_present` is
whatever sits under `data/` and only an *unregistered* directory raised, the
fill gate iterates cells and a wholly absent election has none, and the
two-pass record count compares two passes over the same truncated list. A
build over 2 of the 55 registered elections therefore exited 0, said "Fill
gate: no findings", wrote all five assets and printed its `gh release
create` line — over a manifest indistinguishable in shape from a
113,073-record one. It is not a hypothetical: `data/` in a worktree is a
symlink set, and this project's history records corpus directories dying
with one. `counts.electionsRegistered` now sits beside `counts.elections`,
so a consumer can ask the manifest the same question; a partial build is
what naming elections is for, and marks the manifest `subset`.
`scripts/field_coverage.py` grew the matching rule at the other end — an
election it still maps with nothing under `data/` is a finding of its own.

**A build that dies partway leaves `dist/` as it was.** Everything is
written into `dist/.staging-<pid>/` and moved into place only once the
manifest exists, old manifest removed first: either there is no manifest, or
it checksums what sits beside it. Before, a record whose envelope had moved
— or a Ctrl-C, a full disk or an OOM during the 2.5 GB corpus write — left
MANIFEST describing the *previous* build, one asset from this one, three
from the old, `gzip.decompress(vrk.sqlite.gz) != vrk.sqlite`, and `SELECT
COUNT(*) FROM records` = 0 on a database whose `PRAGMA integrity_check` said
ok. The error mentioned none of it.

**The release is a profile of the archive** (issue #142). `--profile
public`, the default, removes from every record the campaign treasurer's
and auditor's phone and e-mail — both layers, eight paths listed in
[PERSONAL_DATA.md](PERSONAL_DATA.md#what-the-public-release-drops) and held
in `scripts/pii_inventory.py`'s `PUBLIC_PROFILE_DROPS` — and the campaign's
own contact line where it repeats one of those values; none of them reaches
this table, the coverage gate or the dashboard's comparison rows. It also
passes every portrait through `scraper/shared/image_metadata.py`, so the
`photos` table holds the picture without its Exif (GPS, camera serial,
`Artist`), XMP, IPTC and comment blocks. `--profile full` ships the archive
verbatim. `MANIFEST.json` records `profile`, the `redaction` paths and the
number of values removed, and `counts.photosStripped`.

In `vrk-corpus.sqlite` the three extra tables are:

- `records(election_id, candidate_id, candidate_name, record_file,
  source_json, kandidatavimas_json, candidate_note_json, photo_sha256,
  raw_json, norm_json, provenance_json)` — one row per record file, primary key
  `(election_id, candidate_id)`. `raw_json` / `norm_json` are the record's
  `rawData` / `normalized`, compact-serialized (the files are
  pretty-printed; 34.5 % of `data/` was whitespace). The original record
  reassembles from the row — `reconstruct_record` in the script is the
  contract and a test pins the round trip: lossless under `--profile full`,
  and under the public profile the record less the values the profile
  removes (the keys are absent, not nulled). `candidate_note_json` holds
  JSON and not text for a measured reason: `candidateNote` is present *and
  null* on 27,472 of the 27,478 records that carry it, a TEXT column cannot
  tell that from absent, and the round trip therefore dropped the key on
  every one of those records while three places called it lossless
  (issue #156).
- `photos(sha256, mime, bytes, stripped, stripped_sha256, part)` — every
  sidecar portrait, once by content hash, and the `vrk-photos-N.sqlite`
  part that holds its bytes; `records.photo_sha256` is the join and
  `sha256` is always the archive's hash, whatever the profile did to the
  bytes. Each part carries the same columns with `data` in place of
  `part`: under the public profile `data` is the picture with its metadata
  segments removed, `stripped` says whether anything was, and
  `stripped_sha256` hashes what is stored. The parts fill in build order,
  election by election, each closed before the next image would take it
  past 1.9 GB, so an era's portraits mostly share a part and
  `MANIFEST.json`'s `photoParts` says which elections each one holds
  (issue #130: in one database the 27,493 portraits made a ~6 GB asset,
  and GitHub takes 2 GiB). The pre-2016 and
  2020+ eras link their portraits rather than embedding them, and those are
  archived the same way since issue #118 (`scripts/backfill_url_portraits.py`);
  a record still carrying an `http(s)://` reference is one whose portrait
  could not be fetched — its `photoMeta.error` says why — and has no row
  here.
- `anomalies(election_id, event_json)` — the per-election
  `anomalies.jsonl` logs, so "what went wrong" travels with the data.

```sql
-- a candidacy, its full record and its portrait: one ATTACH per part that
-- MANIFEST.json's photoParts lists (three in the first build to have them),
-- and one view over their photos tables
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

Releases are tagged `corpus-YYYY-MM-DD` (the manifest's `version`), so the
corpus is versioned by release tag rather than by whatever happens to be on
one disk. `buildCommit` names the code that built the assets — dirty-aware,
so a build from a modified checkout says so — and `corpusParserCommits` the
spread of commits the *records* carry: the corpus is not from one commit, and
one string implied it was (issue #156). A full build prints the
`gh release create` line, filled in.
