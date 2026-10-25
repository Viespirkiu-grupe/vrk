# Dataset Inventory and Review

What the corpus holds, how to get or rebuild it, and the caveats to know
before analysing it. Every record equals what its own parser produces from
the page it was fetched from; `python scripts/reparse_diff.py` checks this.

## Getting the corpus

Each `corpus-YYYY-MM-DD` GitHub release ships it ready-made:

- `candidacies.csv.gz`: the flat comparison table
- `vrk-corpus.sqlite.gz`: every record's raw and normalized JSON and the
  anomaly logs
- `vrk-photos-N.sqlite`: the portraits, deduplicated by content hash and
  split to stay under GitHub's 2 GiB per-asset cap
- `vrk-web-portraits.tar`: one small WebP per person, for the browser
- `MANIFEST.json`: parser commit, per-election counts, a checksum per asset

`python scripts/build_distribution.py` builds them;
[CANDIDACIES.md](CANDIDACIES.md#distribution) documents them. The corpus is
published under CC BY 4.0 with a required attribution and a removal contact:
[DATA_TERMS.md](../DATA_TERMS.md), repeated in every `MANIFEST.json`.

## Personal data

Every record names a person who stood for election, with their birth date
(112,839 records), birth place (86,453), declared wealth and income (112,104
with an income figure), declared convictions (1,630 candidacies, 1,321 with
detail), campaign finances and portrait, as VRK published them. It also
names people who never stood: children (67,141 records), spouses (59,590),
family members and business partners in private-interest declarations,
campaign donors, and 790 campaign treasurers and auditors with their phone
and e-mail.

- [PERSONAL_DATA.md](PERSONAL_DATA.md) classifies each of the 1,169 leaf
  paths by whose data it is and how sensitive. `scripts/pii_inventory.py`
  generates it, and a test fails when a parser emits a path it does not
  classify.
- `build_distribution.py --profile public`, the default, drops the
  treasurers' and auditors' phone and e-mail and strips Exif/XMP/IPTC from
  every portrait before writing `vrk-corpus.sqlite`. `data/` and
  `samples-full/` stay as fetched.

## Rebuilding it

```bash
scripts/run_all_elections.sh                 # every election, sequentially
scripts/run_election_batches.sh <election-id> # one election
```

Records live under `data/<election-id>/` (3.41 GB of JSON over the 113,073
files, plus 5.54 GB of photo sidecars under `data/<election-id>/photos/`:
27,493 portraits). `data/`, `samples/` and `samples-full/` are gitignored.
A given clone holds only what was scraped there, so count it before
trusting it.

`scripts/run_all_elections.sh` runs three
steps per election:

1. The batch runner builds the `isrinktas` results join, fetches and parses
   every sitemap id with the HTML retained, and writes a
   `CandidateFetchFailed`/`CandidateParseFailed` anomaly for any candidate it
   cannot land. It reports an election complete only when every sitemap id
   has a record.
2. `scripts/backfill_url_portraits.py` archives every portrait the pages
   link. It reads the finished records to find the URLs.
3. `scripts/reparse_diff.py --full --apply` turns those archived portraits
   into `photos/` sidecars.

`FETCH_PORTRAITS=0` stops after step 1 and says what is missing. Both
scripts are resumable: a candidate whose JSON exists is skipped. Candidate
samples go to a temporary directory, so the fixtures under `samples/html/`
are never touched.

### The re-parse gate

```bash
python scripts/reparse_diff.py                        # every election's fixtures
python scripts/reparse_diff.py --full --jobs 8 <id>   # every retained record
python scripts/reparse_diff.py --full --jobs 8 --apply <id>
```

It exits non-zero when any record differs from what its parser now produces.
A parser change is done when it is green; see
[ADDING_AN_ELECTION.md](ADDING_AN_ELECTION.md#8-changing-a-parser-that-already-has-a-corpus).
`--apply` writes only the records that differ.

## Inventory

113,073 candidate records across 55 elections, 1996–2025.

| election | records | elected | declared a conviction | with campaign data |
|---|---:|---:|---:|---:|
| `2015-kovo-1-seimo-zirmunai` | 12 | 1 | 0 | 12 |
| `2015-birzelio-7-seimo-varena-eisiskes` | 8 | 1 | 0 | 8 |
| `2015-lapkricio-8-telsiu-mero` | 7 | 1 | 0 | 7 |
| `2015-birzelio-7-pakartotiniai-sirvintos-trakai` | 327 | 26 | 2 | 285 |
| `2015-birzelio-21-pakartotiniai-silutes` | 366 | 25 | 12 | 182 |
| `2015-kovo-1-savivaldybiu` | 15149 | 1473 | 266 | 13855 |
| `2016-seimo` | 1415 | 141 | 38 | 672 |
| `2017-balandzio-23-meru` | 11 | 2 | 0 | 11 |
| `2017-balandzio-23-seimo-anyksciai-panevezys` | 11 | 1 | 0 | 11 |
| `2017-rugsejo-10-marijampoles-mero` | 8 | 1 | 0 | 8 |
| `2018-rugsejo-16-seimo-zanavykai` | 6 | 1 | 0 | 6 |
| `2019-ep` | 301 | 11 | 6 | 279 |
| `2019-prezidento` | 9 | 1 | 0 | 9 |
| `2019-rugsejo-8-seimo` | 27 | 3 | 2 | 27 |
| `2020-seimo` | 1754 | 141 | 41 | 758 |
| `2021-balandzio-11-radviliskio-mero` | 7 | 1 | 1 | 7 |
| `2021-spalio-10-meru` | 14 | 2 | 1 | 14 |
| `2023-rugsejo-3-seimo-raseiniai-kedainiai` | 8 | 1 | 1 | 8 |
| `2023-geguzes-7-visagino-mero` | 2 | 1 | 0 | 0 |
| `2023-spalio-8-kupiskio-mero` | 5 | 1 | 1 | 5 |
| `2024-ep` | 319 | 11 | 7 | 0 |
| `2024-prezidento` | 8 | 1 | 0 | 0 |
| `2024-seimo` | 1740 | 141 | 62 | 699 |
| `2025-kovo-16-meru` | 14 | 2 | 0 | 10 |
| `2023-kovo-5-savivaldybiu-tarybu-ir-meru` | 13796 | 1557 | 541 | 433 |
| `2019-kovo-3-savivaldybiu-tarybu` | 13666 | 1502 | 244 | 410 |
| `1996-spalio-20-seimo` | 879 | 120 | 0 | 0 |
| `1997-kovo-23-seimo-pakartotiniai` | 23 | 2 | 0 | 0 |
| `1997-gruodzio-21-seimo-pakartotiniai` | 4 | 1 | 0 | 0 |
| `1998-kovo-22-seimo-pakartotiniai` | 11 | 0 | 0 | 0 |
| `1998-lapkricio-15-seimo-pakartotiniai` | 11 | 0 | 0 | 0 |
| `1999-kovo-21-seimo-pakartotiniai` | 22 | 0 | 0 | 0 |
| `1997-kovo-23-savivaldybiu-tarybu` | 6276 | 1459 | 0 | 0 |
| `1997-birzelio-29-svenciniu-tarybos-pakartotiniai` | 110 | 25 | 0 | 0 |
| `2012-seimo` | 1927 | 139 | 45 | 1927 |
| `2013-kovo-3-seimo-birzai-zarasai-ukmerge` | 37 | 3 | 2 | 37 |
| `2014-prezidento` | 7 | 1 | 0 | 7 |
| `2014-ep` | 215 | 11 | 4 | 215 |
| `2007-spalio-7-seimo-dzukija` | 10 | 1 | 0 | 4 |
| `2008-seimo` | 1603 | 141 | 25 | 0 |
| `2009-prezidento` | 7 | 1 | 0 | 7 |
| `2009-ep` | 262 | 12 | 3 | 260 |
| `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai` | 17 | 2 | 0 | 17 |
| `2011-vasario-13-seimo-marijampole` | 9 | 1 | 0 | 9 |
| `2011-vasario-27-savivaldybiu` | 16400 | 1526 | 200 | 0 |
| `2007-vasario-25-savivaldybiu` | 13419 | 1550 | 78 | 0 |
| `2002-prezidento` | 17 | 1 | 0 | 0 |
| `2002-gruodzio-22-savivaldybiu-tarybu` | 10138 | 1560 | 27 | 0 |
| `2004-ep` | 241 | 14 | 3 | 0 |
| `2004-prezidento` | 5 | 1 | 0 | 0 |
| `2004-seimo` | 1251 | 141 | 8 | 0 |
| `2003-birzelio-15-seimo-nauji` | 27 | 0 | 0 | 0 |
| `2005-lapkricio-20-seimo-kedainiai` | 5 | 1 | 0 | 0 |
| `2000-seimo` | 1271 | 141 | 5 | 0 |
| `2000-kovo-19-savivaldybiu-tarybu` | 9879 | 1433 | 9 | 0 |
| **total** | **113073** | **13336** | **1634** | **20199** |

How to read the columns:

- **elected** counts records whose `profilis.pastaba` starts with `Išrink`
  (`Išrinktas`/`Išrinkta`). Match the prefix, not presence: in presidential
  elections every candidate carries a participation note (`Dalyvavo I ture`).
- The 1996–2015 pages mark no winner, so for those elections the column
  counts `kandidatavimas.isrinktas == true`, joined from VRK's results trees
  (`python -m scraper build-results <id>`; see
  [CLI_REFERENCE.md](CLI_REFERENCE.md)).
- In the six 1996–1999 Seimas archive elections `kandidatavimas` is a list,
  so the column counts records with any elected candidacy: 123 records for
  126 elected candidacies (three double-nominated winners).
- The 48 annulled March 2015 council winners in Šilutė and Trakai are not
  counted; the June repeat elections carry those seats.
- `2004-ep` counts 14 for 13 seats: Prunskienė, whose mandate ended at her
  request eight days after the vote, and Didžiokas, who replaced her.
- **declared a conviction** is 0 by absence for `2004-prezidento` (no
  questionnaire) and `2002-prezidento` (the questionnaire is a scan, not
  parsed). Its total, 1,634, is four more than the `teistumas` concept's
  1,630 because it also counts pre-2016 declarations under a neighbouring
  question; see [Conviction data](#conviction-data-one-concept-three-published-shapes).

## Caveats for analysis

### Campaign donations are per campaign, not per candidate

Donation records belong to a *campaign participant*. In list-based elections
one participant covers many candidates, and each of their records carries
the whole shared donation list. Summing across records multiplies the same
money: **€2.68 billion** naively against **€25.7 million** de-duplicated, a
104× inflation.

- **Group by `rawData.politinesKampanijosDalyvioDuomenys.campaigns[].campaignKey`**,
  present on every campaign entry (20,199 of 20,199), surfaced as
  `campaign_key` in the candidacy table. Its `campaigns` table already
  carries de-duplicated totals ([CANDIDACIES.md](CANDIDACIES.md)).
- **Do not group by `sprendimo-numeris`.** One VRK decision spans many
  participants: `PK1-2024LRS-S235` alone covers 70 campaign keys in
  `2024-seimo`, and grouping on it loses €626,553 there.
- An empty `Atstovaujamasis` participant (2,352 candidacies, 2009–2021)
  means *financed through the party's campaign*, not "no data". The
  candidacy table says so with `campaign_status: atstovaujamasis` and a null
  total, never a zero.

Worst cases:

| election | naive € | per campaign € | inflation | largest share |
|---|---:|---:|---:|---:|
| `2015-kovo-1-savivaldybiu` | 2,279,998,501 | 1,928,924 | **1,182×** | one campaign on 2,414 records |
| `2015-birzelio-21-pakartotiniai-silutes` | 626,514 | 14,493 | 43.2× | 49 |
| `2012-seimo` | 294,344,087 | 6,851,422 | 43.0× | 105 |
| `2015-birzelio-7-pakartotiniai-sirvintos-trakai` | 1,417,811 | 53,633 | 26.4× | 48 |
| `2009-ep` | 19,046,090 | 890,957 | 21.4× | 24 |
| `2014-ep` | 43,696,730 | 2,047,301 | 21.3× | 22 |
| `2019-ep` | 28,170,073 | 1,389,023 | 20.3× | 22 |

Every other election measures 1.0×, including the 2023 municipal general,
where every candidate has their own participant.

### Conviction data: one concept, three published shapes

**Read `teistumas`, not a path.** `scraper/shared/conviction_details.py`
resolves a record's `anketa` to one answer with a typed absence;
`docs/concept-map.json`'s `derived` section documents it.

| state | records | meaning |
|---|---|---|
| `neklausta` | 7,470 | no conviction question, or left unanswered (the 2019 presidential form, the 1990s archive cards). **Not a denial** |
| `ne` | 103,973 | asked and denied |
| `deklaruota-be-detaliu` | 352 | declared; the page publishes no detail |
| `deklaruota` | 1,278 | declared, with detail |

- The yes/no is at `normalized.anketa.pareiskimai.ar-buvote-pripazintas-kaltu`
  in every election except `2019-prezidento`. It takes four values, two of
  them affirmative: `Taip`/`Ne` on the Seimas and municipal forms,
  `Yra`/`Nėra` on the 2000 and 2004 ones. Filtering on `Taip` alone misses
  16 declarers.
- The 2000–2014 forms ask separately about a grave crime, a foreign court,
  political persecution and an unserved sentence. 53 records answer one of
  them yes, 20 of which deny the main question. `teistumas` returns them
  under `kiti-pareiskimai`.
- The detail comes as a structured table (`anketa.teistumo-detales.irasai`,
  2016 on), as free text (`anketa.pareiskimai.teisiniai-argumentai`,
  2000–2016), or not at all.

### Placeholder answers normalize to null, and the list is exact

Exactly three strings become `null`: `Nenurodė`, `-` and the empty string. A
null means "not answered on the page"; the source text stays in `rawData`.

Candidate-typed variants survive as answers by design: the `Nėra` family
(`Nėra`/`nėra`/`NĖRA`/`nera`/`Nera`/`NERA`, 1,942 values), `Nenurodyta` (35),
`Nenurodoma` (1), `Nenurodė.` (2), `--` (74), `.` (66), `–` (7) and
`N/A`/`n/a` (6). A null is a blank field; a variant is a candidate stating
they have none.

### `Neskelbiamas` saturates contact fields in 2019–2021

`Neskelbiamas` is VRK's "withheld" token, kept verbatim. It fills
`anketa.adresas` at 100 % in `2019-kovo-3-savivaldybiu-tarybu`, `2020-seimo`,
`2019-ep`, `2019-prezidento` and both 2021 mayoral elections, and
`telefonas`/`el-pastas` at 100 % where `kontaktai` exists (`2020-seimo`, the
2021 mayoral elections). Contact coverage is meaningless there. The 2023+
elections carry real city-level addresses.

### Municipal generals

- The mayoral and council listings overlap: a person standing for both
  appears in each under one VRK candidate id. 2023: 433 mayoral + 13,769
  council − 406 both = 13,796. 2019: 410 + 13,635 − 379 = 13,666.
- In 2019 an elected mayor takes no council seat (1,502 elected people). In
  2023 one person, Erlandas Galaguz (Visaginas), won both (1,557 people for
  1,558 mandates).
- Photo and free-text biography are published only for mayoral candidates,
  so about 97 % of records in these elections carry neither.
- In 2019, `anketa.issilavinimas` is `Nenurodė` for 5,091 candidates
  (37.3 %). Say which denominator an education share uses: 48.7 % of all
  records are higher-educated, 77.7 % of those who answered.

### Known upstream quirks

All verbatim from VRK's pages, documented rather than fixed:

- About 140 records carry a birth **date** in `gimimo-vieta` (birth place),
  e.g. `ramute-nalivaikiene-2016-seimo`.
- Campaign `agreementNumber` mixes bare numbers, three date formats and free
  text (`BK-16`, `be Nr.`, `b/n`).
- `nuosprendzio-data` is year-only for 272 values against 642 ISO dates.
- 42 values are impossible: 39 dates outside 1900–2100 (`1111-11-11`,
  `9999-12-31`, `0204.05.04`), two declaration totals far above their own
  income row (flagged `quality_flags: saltinio-klaida`), and one birth date:
  `damanskis-adolfas` (`1996-spalio-20-seimo`) reads 1995-05-22. None is
  corrected; `scripts/value_plausibility.py` gates the set against
  `docs/plausibility-register.tsv`.
- `kestutis-masiulis-2016-seimo` has a `\x06` where `Ė` belongs, and
  `algis-cepulis-2425844` a double-escaped `P&amp;C`.
- 20,711 values have a lowercase letter directly before an uppercase one.
  None is a lost line break: 12,950 of them carry `VšĮ`, the rest are
  company names (`DnB`, `GmbH`) and VRK's typing (`kAUNO`). Inserting spaces
  would corrupt institution names.
- 6 surviving `U+FFFD` characters were destroyed in VRK's own bytes (five
  `2000-seimo` biographies missing a letter, one `2004-seimo` biography).
  Where a pair proves a lost quote it is restored.

### Per-election schemas are deliberately not identical

The questionnaire changed with the law (Seimo rinkimų įstatymas →
savivaldybių tarybų rinkimų įstatymas → Rinkimų kodeksas), so key sets
differ. Field names are shared wherever the question matches.
[OUTPUT_SCHEMA.md](OUTPUT_SCHEMA.md) documents each election's shape.

## What guards the corpus

- `python scripts/reparse_diff.py`: records equal their parsers (above).
- `python scripts/field_coverage.py`: every `docs/concept-map.json` path
  against every record, against `docs/coverage-baseline.tsv`
  ([FIELD_COVERAGE.md](FIELD_COVERAGE.md)).
- `python -m scraper anomalies-report`: reads `data/*/anomalies.jsonl` back
  and diffs it against `docs/anomaly-baseline.tsv`. The corpus holds 9,027
  events ([ANOMALY_DETECTION.md](ANOMALY_DETECTION.md)).
- `tests/test_corpus_value_hygiene.py`: no trailing separators, no string or
  mixed-type money, no value that is only a replacement character, and the
  two pinned counts above.
- `tests/test_doc_numbers.py`: re-measures the figures the docs state.
- Every record's `provenance` block records the fetch time, parse time,
  parser commit and source-page sha256 ([OUTPUT_SCHEMA.md](OUTPUT_SCHEMA.md)).

## Known gaps

- VRK publishes further by-elections and older elections with no module yet.
- Nine candidate pages VRK never published, each with a
  `CandidateFetchFailed` event; `anomalies-report` fails on a sitemap gap
  without one:
  - 2011 municipal: Viktorija Zubovaitė-Steponavičienė (29964), Gerda
    Ivaškevičiūtė (61654), Aleksandras Bukinas (53039)
  - 2007 municipal: Antanas Katinas (1835), Genrika Rynkun (6582), Juzefa
    Bagdonienė (1336)
  - 2000 municipal: Gintaras Binkauskas (84814), Vilma Kalendauskaitė (86936)
  - 2002 municipal: Zita Vincentina Liubarskienė (158225)

  None was elected.
- Marija Puč's 2015 Trakai council page is `Rengiama`: the record has the
  profile card only and the corpus's one `AnketaNotPublished` warning. Her
  mayoral candidacy, under a second VRK id, is complete. The person index
  keeps the two apart.
- `2000-kovo-19-savivaldybiu-tarybu`: five municipalities (Jurbarko, Kelmės,
  Radviliškio, Raseinių, Vilkaviškio r.) have list-level results only, so
  their 806 records carry `isrinktas: null` with
  `kandidatavimas.rezultataiNeskelbiami`.
- 38 portraits link hosts that no longer serve them (32 cards of 2000 Seimas
  and all 5 of 2005 Kėdainiai on lrs.lt, one 2020 Seimas 404). Each keeps
  its URL and a `PortraitFetchFailed` event;
  `scripts/backfill_url_portraits.py --retry-failed` retries them.
- Votes: the 2016–2025 elections publish no results tree the records link,
  so they carry no vote counts. For 2007–2015 the mayoral
  `rezultatai_sav_kand` pages and 2011's 34 self-nominated candidates' rows
  are unread.
- The 2016–2020 campaign trees answer 404 for every derived
  `Atstovaujamasis` sub-page, recorded per campaign as `derivedTabsAbsent`.
  Those campaigns (2016, 2018, 2019, 2020) are root-only by the source's own
  absence.
- `2024-ep` and `2024-prezidento` candidate pages have no campaign tab, so
  those elections have no donation data.
- The 1996–1998 archive listings print names surname-first. `candidateName`
  follows the candidate page (given name first); `candidateId` follows the
  listing (`kubilius-andrius`).
- The 1996–1999 Seimas archive pages publish no birth date. It is recovered
  from the biography's opening sentence where possible
  (`anketa.gimimo-data-saltinis: "biografijos-tekstas"`; coverage in
  [OUTPUT_SCHEMA.md](OUTPUT_SCHEMA.md)). The rest group in the person index
  by name plus `~year`, or name alone, so a same-named person among them
  cannot be told apart.
