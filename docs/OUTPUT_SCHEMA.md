# Output Schema

The record contract for the whole corpus. The body covers the record
envelope and the normalized shapes shared by every election; one appendix
per election covers what is specific to it, and wins where the two differ.
Question numbering, key sets and section internals vary by election because
the HTML does.

Records are written as `data/<election_id>/<candidate-id>-<election_id>.json`.

## Top-Level Record

Every record carries these seven:

- `electionId`
- `candidateId`
- `candidateName`
- `source` — `{candidateSourceUrl}`
- `rawData`
- `normalized`
- `provenance`

Two more are optional (`tests/test_record_shape.py` holds both lists against
`data/`):

- `kandidatavimas` — the candidacy block: a **root** field on
  105,737 records across 47 of the 55 elections. The 1996–1999 archive
  family's eight elections carry it *inside* `normalized` instead.
- `candidateNote` — VRK's note beside the candidate, on 27,478 records of
  `2016-seimo`, `2019-kovo-3-savivaldybiu-tarybu`,
  `2023-kovo-5-savivaldybiu-tarybu-ir-meru` and `2025-kovo-16-meru`.

### `provenance`

Stamped by `write_candidate_record` on every parse. Every record carries
exactly these five keys:

- `fetchedAt` — when the primary page (`source.candidateSourceUrl`) was
  fetched: the retained file's mtime. For a record parsed from the tracked
  fixture tree, the sitemap's `generatedAt` stands in.
- `parsedAt` — when this record's content was produced.
- `parserCommit` — `git rev-parse --short HEAD` at parse time, `-dirty`
  appended for uncommitted changes. `null` on 49,586 records (43.9 %),
  written before provenance existed.
- `sourceSha256` — hash of the primary page's retained bytes.
  `scripts/reparse_diff.py` uses it to split "the parser changed" from "the
  page changed" and otherwise excludes the block from its diff.
- `schemaVersion` — `1`.

A record whose primary page is not retained would carry no block rather than
a fabricated one; no record is in that state.

## `rawData`

Source-close payloads parsed from saved HTML, in this order:

1. `profile`
2. `anketa`
3. `biografija`
4. `turtoIrPajamuDeklaracijos`
5. `privaciuInteresuDeklaracija`
6. `politinesKampanijosDalyvioDuomenys` (optional)
7. `kita`

### `rawData.profile`

- `candidateDisplayName`
- `electedNote`
- `photoSrc` — the relative sidecar path `photos/<candidateId>.<ext>` of the
  portrait file written beside the records, with `photoMeta` (`mime`,
  `bytes`, `sha256`). The 2016–2019 pages embed the portrait as base64; every
  other era links a URL, which `scripts/backfill_url_portraits.py` fetches,
  adding `url` and `fetchedAt` to `photoMeta`. A failed fetch keeps the URL
  with a `photoMeta` of only `url`, `fetchedAt` and `error` (38 records: the
  lrs.lt portraits of the 2000 Seimas and 2005 Kėdainiai elections, and one
  2020 Seimas 404). A URL with no `photoMeta` was never tried. The extension
  follows the bytes, not the URL. The 1996–1999 Seimas archive family calls
  the key `photoUrl`. `normalized.profilis.nuotrauka` carries the same
  reference.
- `fields[]` — `{key, displayValue, urls[]}`

### `rawData.anketa`

`rows[]` of `{rowIndex, questionNumber (nullable), prompt, answer}`; `answer`
is a string, or a list of row objects for table rows.

### Other raw sections

- `biografija` — 2016: source-close biography payload. 2020: anketa-like
  `rows[]`, with table rows (education, work) as lists of row objects.
- `turtoIrPajamuDeklaracijos` — `sections[]` of `{title, items[]}`
- `privaciuInteresuDeklaracija` — `sections[]`
- `kita` — free text and links
- `politinesKampanijosDalyvioDuomenys` (optional) — campaign list with shared
  metadata and per-tab payloads

## `normalized`

Analysis-ready structures with source-close, mostly Lithuanian keys. The
section order is fixed; each record carries a subset of:

1. `profilis`
2. `anketa`
3. `kandidatavimas` — the 1996–1999 archive family only (7,336 records,
   eight elections); everyone else has it at the root.
4. `gyvenamoji-vieta` — the six 1996–1999 Seimas elections, 950 records.
5. `biografija`
6. `programa` — `2002-prezidento` and `2004-prezidento`, 21 records.
7. `turto-ir-pajamu-deklaracijos`
8. `privaciu-interesu-deklaracija`
9. `patiketiniai` — a presidential candidate's trustees, `2014-prezidento`
   and `2019-prezidento`, 16 records.
10. `politines-kampanijos-dalyvio-duomenys` — omitted when the candidate has
    no campaign participant tab.
11. `kita`

Rules:

- **Treat every section as optional.** A section is absent when the page
  never published its tab. Within elections that publish a section on more
  than 99 % of records, eleven records lose one: `biografija` on
  `gintaras-binkauskas-2012-seimo`, `gintaras-binkauskas-2016-seimo` and
  `jonas-korsakas-2020-seimo`; `turto-ir-pajamu-deklaracijos` on
  `stasys-stankus-205466`, `saulius-jancys-205870` and
  `mindaugas-kucinskas-205871` of `2002-gruodzio-22`, on
  `genovaite-ziobakiene-2004-seimo`, on
  `darius-juodeska-72579-2015-kovo-1-savivaldybiu` and on
  `jonas-korsakas-2020-seimo`; `politines-kampanijos-dalyvio-duomenys` on
  `algimantas-matulevicius-2009-ep` and `valdemar-tomasevski-2009-ep`.
- **Three placeholders normalize to null:** `Nenurodė`, `-` and the empty
  string. Typed "none" answers survive verbatim: the `Nėra` family
  (`Nėra`/`nėra`/`NĖRA`/`nera`/`Nera`/`NERA`, 1,942 values), `Nenurodyta`
  (35), `Nenurodoma` (1), `Nenurodė.` (2), plus `--`, `.`, `–` and `N/A`.
- **Several nominators** fold into one field:
  `profilis.kita.iskele.reiksme` reads `"Party A; Party B"`.
- **Free-text declaration sections** (`ID001A KITI DUOMENYS` on the
  2016-era pages) normalize to a `tekstas` key:
  `privaciu-interesu-deklaracija.id001a.tekstas`.
- **Donations** under `politines-kampanijos-dalyvio-duomenys[].aukos-pagal-sekcija`
  are `totals` plus `records[]`, every record keyed `rowNumber`, `donor`,
  `municipality`, `date`, `incomeSourceCode`, `amount`, `notes`. Columns are
  matched by heading; a column the page omits is null.
- **2020 biography** has no raw `text`/`html`, no section-kind wrappers and no
  normalized `tekstas`/`sekcijos`.

### `normalized.anketa` (2016)

The 2016 questionnaire carries the biography questions itself:

- `gimimo-data` (Q5), `adresas` (Q6)
- `pareiskimai` — the Seimo rinkimų įstatymo 38 str. 4 d. declarations
  (Q8.1–Q8.4) and the 98 str. 1 ir 3 d. ones (Q9.1, Q9.2, Q9.3.1–Q9.3.3),
  plus `teisiniai-argumentai` (Q9.3.4), filled only when Q9.2 is "Taip"
- `teistumo-detales` — `{"irasai": [...]}`, one entry per conviction from
  the Q9.2 detail table (`nuosprendzio-data`, `-valstybe`, `-institucija`,
  `nusikalstama-veika`); present on every record, empty for all but the 38
  declarers
- `gimimo-vieta` (Q10), `tautybe` (Q11), `issilavinimas` (Q12, `aprasas`
  plus an `irasai` table), `uzsienio-kalbos` (Q13, a list),
  `politine-organizacija` (Q14), `anksciau-isrinktas` (Q15, same
  `aprasas`/`irasai` shape), `pagrindine-darboviete` (Q16),
  `visuomenine-veikla` (Q17), `pomegiai` (Q18), `seimine-padetis` (Q19),
  `vaiku-vardai-pavardes` (Q20), `kita-apie-save` (Q21)
- `pedagoginis-vardas` and `sutuoktinio-vardas-pavarde` have no question
  number and are matched on prompt text
- the `issilavinimas` and `anksciau-isrinktas` tables sit inside their
  question's row or in the next row; both placements are collected. Shared
  with `2019-ep`, `2019-prezidento` and the 2017 elections.

## Anomalies JSONL

Parser runs write `data/<election_id>/anomalies.jsonl`, one event per line:
`timestamp`, `eventType`, `severity`, `stage`, `electionId`, `candidateId`,
`sourceUrl`, `detail` (free-form object). See
[ANOMALY_DETECTION.md](ANOMALY_DETECTION.md).

## Shared normalized shapes

Identical across elections; the appendices do not restate them.

### `turto-ir-pajamu-deklaracijos`

One reading (`scraper/shared/deklaracijos.py`) covers every election from
2004 on, whose pages publish the declaration extract as titled sections. The
1996–2003 shape is at the end of this section.

**The eleven value keys**, in this order:

- `privalomas-registruoti-turtas`
- `vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai`
- `pinigines-lesos`
- `suteiktos-paskolos`
- `gautos-paskolos`
- `gautos-pajamos`
- `sumoketas-pajamu-mokestis`
- `individualios-veiklos-pajamos`
- `individualios-veiklos-atskaitymai`
- `turto-pardavimo-pajamos`
- `turto-isigijimo-kaina`

The first seven are "the seven canonical keys" the appendices refer to. The
last four are the rest of the GPM308/GPM311 income extract and are null
before 2018 and in the FR0462 family of 2004 and 2007.

Values are JSON floats (`202000.0`, never an int or string), `null` where the
row was not published or does not parse. Euro from 2016 on, litas before
(`valiuta` says so). An amount rendered without its leading zero (`,35 EUR`)
is the sub-euro figure.

**What the extract is**, from the section headings:

- `deklaracijos-metai` — the tax year ("… IŠRAŠAS **(2023 m.)**"); the
  2008–2015 Seimas pages state it in their closing note ("deklaracijos
  pateikiamos už laikotarpį nuo 2011-01-01 iki 2011-12-31"). `null` on the
  2004 and 2007 pages, the 2011 and 2015 municipal generals, `2016-seimo`
  and `2020-seimo`. Filled on 33,494 of the 84,402 sectioned declarations.
- `deklaracijos-forma` — `GPM302`, `GPM305`, `GPM308`, `GPM311`, or
  `FR0462` for the 2004/2007 family (the variant per line is in
  `pajamos-pagal-forma`).
- `deklaracijos-apimtis` — whose declaration the value keys carry:
  `gyventojo` (the candidate's), `seimos` (the family's), or
  `gyventojo-seimos` for the combined heading every page from 2008 on
  prints. Never `sutuoktinio`. `null` where no asset declaration was
  published.

**Every declaration.** `deklaracijos` lists each section in page order:

```json
{"pavadinimas": "Šeimos turto deklaracija", "rusis": "turto",
 "apimtis": "seimos", "metai": null, "forma": null,
 "reiksmes": {"privalomas-registruoti-turtas": 37000, ...}}
```

`rusis` is `turto` or `pajamu`; `reiksmes` holds only the keys that section
published. An identical repeat is listed once; a repeat that differs is kept.

**The spouse.** 2004 and 2007 published separate declarations for the
candidate, the family and the spouse. The value keys take the candidate's
own, else the family's, never the spouse's. The spouse's figures go under
`sutuoktinio` (the five asset keys), present only on the 352
`2007-vasario-25-savivaldybiu` records whose page publishes one.

**Era keys:**

- `valiuta` (`"Lt"`) and `pastaba` (the page's closing note) — every
  2004–2015 election
- `pajamos-pagal-forma` — the same elections: one
  `{forma, gautos-pajamos, sumoketas-pajamu-mokestis}` per income line,
  empty where the page uses the two labelled rows instead
- `israsai` — 2004 and 2005 only: who issued each extract, when it was
  received, and the workplace the candidate gave

**The 1996–2003 pages** publish one un-sectioned form with their own key set
(`turtas-ir-pinigines-lesos-metu-pabaigoje`,
`gautos-pajamos-darbo-santykiu`, …), sharing `gautos-pajamos`,
`sumoketas-pajamu-mokestis` and `pinigines-lesos`. No `deklaracijos` list,
`deklaracijos-metai` or `-forma`. The 2002 and 2003 municipal form carries
`deklaracijos-apimtis`. See the appendices, and
[DATA_GUIDE.md](DATA_GUIDE.md) for reading income across eras.

### `profilis` and `kita`

`profilis` has four keys everywhere: `vardas-pavarde`, `pastaba`,
`nuotrauka`, `kita`. Every `profilis.kita` entry is
`{pavadinimas, reiksme, nuorodos}`. `normalized.kita` is
`{tekstai, nuorodos}`.

The 2017–2025 pages add two keys from the office line above the profile
card:

- `kandidatuoja-i` — the line as printed (`"Kandidatas į savivaldybės
  tarybos narius ir merus"`); in the 2019 and 2023 municipal generals the
  one field that says which role was sought
- `dokumentu-pateikimo-data` — from the 2024 Seimo pages'
  `"(dokumentai pateikti 2024-07-29)"`; `null` elsewhere

A label that recurs on one card keeps its first value under the plain key
and later ones under `-2`, `-3` (`iskele`, `iskele-2`). This happens on the
2012 Seimo cards (one `Apygarda`/`Iškėlė` pair per candidacy) and for
coalition nominees in 2011–2015, whose suffixed entry's `pavadinimas` is the
literal `"(Iškėlė"`.

### Elected status in the 2012–2015 family (`kandidatavimas.isrinktas`)

No 2007–2015 page marks a winner, so `profilis.pastaba` is null on all
eighteen elections. Electedness is joined from VRK's results trees at parse
time (`python -m scraper build-results <id>` writes
`sitemaps/<id>.results.json`; `scraper/shared/election_results.py`
documents each source page) into `kandidatavimas`:

- `isrinktas` — `true`/`false` when a results file exists (a false is a
  real statement), `null` when none has been built. An empty `elected` map
  counts as no file unless it carries `"nobodyElected": true`, written only
  when every constituency says the election was not held (the 1998–1999
  Seimas by-elections, the 2003 new elections).
- `isrinktasKaip` — `vienmandate`, `daugiamandate` (Seimas/EP list),
  `prezidentas`, `meras`, `tarybos-narys`.
- `rezultatuSaltinis` — the results page; `rezultatuTuras` (1 or 2) where
  the page belongs to a round.
- `rezultataiPanaikinti` — the VRK decision voiding the 48 March 2015
  council wins in Šilutė and Trakai; their `isrinktas` is `false`, and the
  June repeat elections' records carry the seats actually won.

Elections without a listing-derived block (the 2014 presidential election,
the 2015 Seimo by-elections, Telšiai) get a minimal one: `vrkCandidateId`
plus the keys above.

### Votes in the 2007–2015 family

The same join writes every candidate's votes into `kandidatavimas` under the
pre-2005 records' field names:

- `pirmumoBalsai` + `porinkiminisNumerisSarase` (+ `reitingoBalai` where
  printed) + `pirmumoBalsuSaltinis` — preference votes and post-election
  list position. Seimas 2008/2012 from `partijos_pirmumo_balsai<listId>.html`
  (id join); 2011/2015 municipal from the per-list ranking pages.
- `vienmandatesBalsai` — constituency round one,
  `{balsadezese, pastu, isViso, procentai, vieta, saltinis}` as in the
  2000–2004 records (`balsadezese` is the "apylinkėse" column, `procentai`
  the share of valid ballots, `vieta` computed); `vienmandatesBalsai2` for a
  runoff. 2007–2008 rows join by anketa id; from 2012 by name within the
  constituency, unresolved rows going to the results file's
  `voteRowsUnresolved`.

Not read: mayoral votes (`rezultatai_sav_kand`) and the 2011 self-nominated
individuals' list rows. The 2016-on elections have no results tree, so no
votes.

### Elected status on the 2016–2025 pages (derived from `profilis.pastaba`)

The only elected signal is the profile note (`"Išrinktas pagal sąrašą"`,
`"Išrinkta vienmandatėje Zanavykų (Nr.64) apygardoje II ture"`,
`"Išrinktas II ture"`), which names the complete winner set. For those
eighteen elections `candidacy_from_elected_note`
(`scraper/shared/election_results.py`) derives a minimal `kandidatavimas`:
`{isrinktas: true, isrinktasKaip: vienmandate|daugiamandate|meras|prezidentas}`
on a noted record, `{isrinktas: false}` on the rest. The 2019 and 2023
municipal generals keep their richer sitemap-derived block.

A candidacy counts as won when `profilis.pastaba` starts with `Išrink`
**or** `kandidatavimas.isrinktas` is `true`.

### Campaign entries

Every `politines-kampanijos-dalyvio-duomenys[]` entry has the same ten keys:
`statusas`, `registravimo-data`, `sprendimo-numeris`, `kontaktai`,
`izdininkas`, `auditorius`, `aukos-pagal-sekcija`,
`finansavimo-ataskaitos`, `sutartys`, `sprendimai`. The 2015 era adds keys
(see the `2015-kovo-1-seimo-zirmunai` appendix).

### The two `privaciu-interesu-deklaracija` families

- **Form-id sections** (`id001j`, `id001s`, `id001i`, `id001a`, `id001f`,
  `id001p`, …) on the 2016/2019-era pages: 2016 Seimo, the 2015 and
  2017–2019 Seimo by-elections, both 2017 mayoral elections, 2019 EP, 2019
  presidential, the 2019 municipal general and 2020 Seimo.
- **Slugged sections** (`deklaruojancio-darbovietes`,
  `sutuoktinio-darbovietes`, `rysiai-su-juridiniais-asmenimis`,
  `rysiai-sudarius-sandorius`, `kiti-duomenys`, …) on the 2021+ pages.

Concept pairs: `id001j` ≈ `rysiai-su-juridiniais-asmenimis`, `id001s` ≈
`rysiai-sudarius-sandorius`, `id001a` ≈ `kiti-duomenys`.

Money columns are parsed floats; where the value carried the currency, it is
a sibling key:

| column | value | currency |
|---|---|---|
| `id001s[].sandorio-suma` | float | `sandorio-suma-valiuta` — `"EUR"` (8,111 rows) or `"Lt"` (547) |
| `id001s[].sandorio-suma-lt` | float | litas throughout |
| `vii-sandoriai[].suma-skaiciais` | float | litas throughout |

`*-vertes-litais-kodas` is VRK's value-band code (`"001"`–`"012"`) and stays
a string.

The 2007–2008 roman-numbered form's `Dovana, data` and `Paslauga, data`
columns print two values in one cell; they are split into `dovana`/`data`
and `paslauga`/`data`.

The form-id family's spouse block
(`deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris` —
`{vardas, pavarde, sutuoktinio-sugyventinio-partnerio-darboviete-…}`) is
present on every candidate who filed a declaration. On the 2016-era pages
its heading is the table's first row, and the normalizer titles the section
from it.

The pre-2016 roman-numbered form:

- `2008-seimo` says `Deklaruojantysis asmuo` (later years:
  `Deklaruojantis asmuo`); its records carry `deklaruojantysis-asmuo` plus
  `darboviete-ir-pareigos-valstybineje-tarnyboje` and
  `kitos-darbovietes-pareigos`, which no other era prints there.
- a section's `description` (the static form sentence under the heading) is
  left in `rawData` and not normalized.

## Appendix: 2019 European Parliament (`2019-ep`)

Schema-parallel to 2016 Seimo, same section order.

- The anketa is several sibling tables; the parser stitches them into one
  `anketa.rows` list and attaches the standalone record tables (education
  Q12, prior mandates Q15) to the heading row before them.
- `pareiskimai` carries the EP declarations (`8.1`–`8.3`, `9.1`–`9.5`); no
  `8.4`/`teisiniai-argumentai`.
- `teistumo-detales` — the Q9.2 detail table, non-empty for six declarers.
  Column headings are printed slugified
  (`9-2-1-apkaltinamojo-nuosprendzio-sprendimo-data`).
- `anketa` adds `mokslo-laipsnis` (Q12.1) and keeps `pedagoginis-vardas`
  (Q12.2). Q19 splits into `seimine-padetis` and
  `sutuoktinio-vardas-pavarde`.
- `biografija` is free text (`{"tekstas": ...}`).
- `profilis.pastaba` — the elected note, elected MEPs only.
- `privaciu-interesu-deklaracija` hoists the declarant to
  `deklaruojantis-asmuo`, keys tables by section id, and keeps the spouse
  block. No declaration filed → empty object.

## Appendix: 2024 European Parliament (`2024-ep`)

No campaign tab (campaigns were run by the party lists).

- `anketa`: `adresas` (Q6), `einamos-pareigos` (Q7),
  `narystes-politinese-organizacijose.irasai` (Q8 membership table, in its
  own row after the heading).
- `pareiskimai` — Rinkimų kodekso 76 str. declarations (Q9–Q16, including
  `13.5`–`13.7`).
- `teistumo-detales` — the conditional Q13.1–Q13.4 details: one entry with
  Q13.1–Q13.3 plus a `nusikalstamos-veikos` list of Q13.4 offences.
  `mandato-netekimo-detales` — the conditional Q14.1 answer.
- `biografija` is structured: `gimimo-data`/`gimimo-vieta` (Q1),
  `issilavinimas.irasai` (Q2), `mokslo-laipsnis` (Q2.1),
  `pedagoginis-vardas` (Q2.2), `uzsienio-kalbos` (Q3),
  `darbo-patirtis.irasai` (Q4), `visuomenine-veikla` (Q5), `pomegiai` (Q6),
  `seimine-padetis` (Q7).
- `privaciu-interesu-deklaracija` merges the leading summary table to the top
  level (`pateikimo-data`, `deklaruojantis-asmuo`,
  `sutuoktinis-sugyventinis-ar-partneris`) and keys each `h4` section by its
  slugified title, each a list of records; `kiti-duomenys` lands under
  `tekstas`.
- The portrait is a linked `kandImg/...` URL.

## Appendix: 2019 Presidential (`2019-prezidento`)

Schema-parallel to 2019 EP, plus `patiketiniai` and a campaign section.

- `profilis.pastaba` — a status line for **every** candidate:
  `Išrinktas II ture`, `Dalyvavo II ture` or `Dalyvavo I ture`.
- `anketa` mirrors 2019 EP (free-text `biografija`, Q12
  `issilavinimas.irasai`, `mokslo-laipsnis`, `pedagoginis-vardas`, Q15
  `anksciau-isrinktas`, the Q19 split).
- `pareiskimai` — Prezidento rinkimų įstatymas: citizenship by origin and
  residency (`8.1`, `8.2`), Seimas eligibility (`8.3.1`–`8.3.4`), other
  citizenship (`9.1`–`9.3`).
- `patiketiniai` — the trustees tab, a list of text entries; empty for every
  2019 candidate.
- `privaciu-interesu-deklaracija` follows 2019 EP.
- The portrait is embedded base64.

## Appendix: 2024 Presidential (`2024-prezidento`)

The `2024-ep` five-tab set: no trustees, no campaign tab.

- `profilis.pastaba` — a status line for every candidate, as in 2019. The
  nomination is `profilis.kita.kandidata-iskele` (`išsikėlė pats` or the
  party).
- `anketa` as 2024 EP; a candidate with no membership answers Q8 inline,
  giving an empty `irasai`.
- `pareiskimai` — Q9–Q14 share keys with 2024 EP. Q15–Q18 are presidential:
  `ar-esate-ar-buvote-kitos-valstybes-pilietis` (Q15),
  `ar-susijes-priesaika-uzsienio-valstybei` (Q16),
  `ar-esate-pilietis-pagal-kilme` (Q17),
  `ar-gyvenate-lietuvoje-trejus-metus` (Q18).
- `teistumo-detales`, `mandato-netekimo-detales` as 2024 EP; empty for every
  candidate.
- `biografija` and `privaciu-interesu-deklaracija` as 2024 EP.

## Appendix: 2020 Seimo (`2020-seimo`)

2016-era layout (profile read by the 2016 parser) with a smaller
questionnaire numbered for the 2020 Seimo rinkimų įstatymas:

- `adresas` (Q6) and `kontaktai` — `telefonas` (Q6.1), `el-pastas` (Q6.2),
  `socialiniu-tinklu-paskyros` (Q6.3). The first three are usually
  `Neskelbiamas`.
- `einamos-pareigos` (Q7), `narystes-politinese-organizacijose.tekstas`
  (Q7.1, answered inline).
- `pareiskimai` — 38 str. 3 d. (Q8.1–Q8.4 plus
  `ar-savanoriskos-karo-tarnybos-karys` for Q8.2.1) and 98 str. 1 ir 3 d.
  (Q9.1–Q9.5). Answers read `Neturiu`/`Nesu`/`Nesu/nebuvau`/`Ne`, except
  Q9.2 (`Taip`/`Ne`).
- `teistumo-detales` — non-empty for 41 declarers.

Birth, education, language, hobby and family live under `biografija`:
`gimimo-data`, `gimimo-vieta`, `tautybe`, `issilavinimas`,
`mokslo-laipsnis`, `pedagoginis-vardas`, `uzsienio-kalbos`,
`darbo-patirtis`, `visuomenine-veikla`, `pomegiai`, `seimine-padetis`,
`sutuoktinio-vardas-pavarde`, `vaiku-vardai-pavardes`, `kita-apie-save`.
The 2020 form widens `visuomenine-veikla` to "mokslinė, pedagoginė,
visuomeninė veikla".

The portrait is a linked `kandImg/...` URL on all pages, unlike other
2016-era-layout elections.

The two headline declaration figures are stated in prose ("Deklaruota
apmokestinamųjų ir neapmokestinamųjų pajamų suma") and are read from
`rawData.turtoIrPajamuDeklaracijos.sections[1]` by
`scripts/renormalize_declarations.py`; this election retains no HTML beyond
its six fixture candidates, so it is re-normalized, not re-parsed. Both are
populated on 1,753 of 1,753 declarations.

## Appendix: 2024 Seimo (`2024-seimo`)

Full section order, campaign tab included.

- `profilis.pastaba` — `Išrinktas vienmandatėje <apygarda> apygardoje II ture`
  or `Išrinktas pagal sąrašą`; `null` for the rest. `profilis.kita`:
  `vienmandate-apygarda`, `iskele`, `turas`, `sarasas`, `numeris-sarase`,
  `porinkiminis-eiles-numeris`.
- `anketa` as 2024 EP.
- `pareiskimai` — Q9–Q14 as the other 2024 modules, plus Q15
  (`ar-esate-ar-buvote-kitos-valstybes-pilietis`) and Q16
  (`ar-susijes-priesaika-uzsienio-valstybei`).
- `teistumo-detales`, `mandato-netekimo-detales` as 2024 EP.
- `biografija` numbering matches 2024 EP (`issilavinimas` Q2,
  `mokslo-laipsnis` Q2.1, `darbo-patirtis` Q4).
- `privaciu-interesu-deklaracija` as 2024 EP.

## Appendix: 2023 Kupiškis mayor (`2023-spalio-8-kupiskio-mero`)

The 2024-ep five tabs plus a campaign tab. This appendix is the reference for
the 2023 page vintage, which the other 2023 municipal modules share.

- `profilis.pastaba` — the winner only
  (`Išrinktas Kupiškio rajono (Nr.23) savivaldybėje II ture`).
  `profilis.kita`: `savivaldybe`, `iskele-i-savivaldybes-merus`, `turas`
  (`I`/`II`), `sarasas`, `numeris-sarase`, `porinkiminis-numeris-sarase`.
- `anketa`: `adresas` (Q6), `einamos-pareigos` (Q7). Q8 asks for a single
  membership and is answered inline, so `narystes-politinese-organizacijose`
  carries `tekstas` and `irasai` (empty unless a table appears).
- `pareiskimai` — Q9–Q14 (including `13.5`–`13.7`) under the 2024 keys; no
  further questions. Q10–Q12 are printed `10 .`, so numbers are re-derived
  whitespace-tolerantly.
- `teistumo-detales`, `mandato-netekimo-detales` as 2024 EP; the Q13.4 block
  separates label and value with a hyphen, not an en dash.
- `biografija` uses the 2020 Seimo numbering: `gimimo-data`/`gimimo-vieta`
  (Q1), `tautybe` (Q2), `issilavinimas.irasai` (Q3), `mokslo-laipsnis`
  (Q3.1), `pedagoginis-vardas` (Q3.2), `uzsienio-kalbos` (Q4),
  `darbo-patirtis.irasai` (Q5), `visuomenine-veikla` (Q6), `pomegiai` (Q7),
  `seimine-padetis` (Q8).
- Declarations follow the 2024 shapes; tab bodies are wrapped in a `<div>`
  and flattened before the shared parsers.
- `kita` is empty for every candidate.

## Appendix: 2023 Visaginas mayoral repeat vote (`2023-geguzes-7-visagino-mero`)

The `2023-spalio-8-kupiskio-mero` vintage, but five tabs: no campaign
section (its campaign finance is published with
`2023-kovo-5-savivaldybiu-tarybu-ir-meru`).

- `profilis.pastaba` — the winner only
  (`Išrinktas Visagino (Nr.59) savivaldybėje II ture`).
- `profilis.kita.turas` is `II` for both: only the runoff was re-run.
- `sarasas`, `numeris-sarase`, `porinkiminis-numeris-sarase` are empty.
- `teistumo-detales` is `{"irasai": []}` and `mandato-netekimo-detales`
  `null` throughout; `kita` is empty.

## Appendix: 2023 Seimo by-election (`2023-rugsejo-3-seimo-raseiniai-kedainiai`)

The six-tab 2024 Seimo set.

- `candidateName` drops the listing's `(V)` winner suffix.
- `profilis.pastaba` — the winner only
  (`Išrinktas vienmandatėje Raseinių–Kėdainių (Nr. 42) apygardoje II ture`).
  `profilis.kita`: `vienmandate-apygarda`, `iskele`, `turas` (`I`/`II`),
  `sarasas`, `numeris-sarase`, `porinkiminis-eiles-numeris`.
- `anketa` as the 2023 mayoral module (inline Q8).
- `pareiskimai` — Q9–Q14 plus Q15
  (`ar-esate-ar-buvote-kitos-valstybes-pilietis`) and Q16
  (`ar-susijes-priesaika-uzsienio-valstybei`), keyed as the presidential
  module.
- `teistumo-detales` — en dash separator.
- `biografija` — the 2023 numbering (see Kupiškis).
- Campaigns: `Savarankiškas` candidates publish all five tabs (treasurer,
  auditor, donations, financing reports, contracts); `Atstovaujamasis`
  candidates only donations.
- `kita` is empty.

## Appendix: 2023 municipal councils and mayors (`2023-kovo-5-savivaldybiu-tarybu-ir-meru`)

Candidate pages are the `2023-spalio-8-kupiskio-mero` vintage; that
appendix's page-level shapes apply.

`candidateId` is `<name-slug>-<vrkCandidateId>`
(`raimundas-markauskas-2429873`): 244 of the 13,796 candidates share a name
slug, and a positional suffix would depend on traversal order.

Root fields beyond the common set: `candidateNote` (the listing's status
note) and `kandidatavimas`.

### `kandidatavimas`

Carried in from the sitemap, because only the listing pages publish it:

- `vrkCandidateId` — VRK's id from the candidate URL.
- `savivaldybe` — `{id, number, name}`: VRK's `rpgId`, the municipality
  number (1–60) and the name without it
  (`{"id": "22012", "number": 12, "name": "Jurbarko rajono"}`).
- `roles` — `tarybos-narys`, `meras`, or both (406 both, 13,363
  council-only, 27 mayor-only).
- `tarybosNarys` — `null` for mayor-only, else
  `{partyList: {id, number, name}, listPosition, postElectionPosition, elected}`.
  Positions are pre- and post-preference-vote order, `null` if not a plain
  number. `partyList` covers parties, coalitions and committees.
- `meras` — `null` for council-only, else `{round, nominatedBy, elected}`;
  `round` is `I`/`II`, `nominatedBy` is `išsikėlė pats` or the nominator.
- `isrinktas` — true when either candidacy was won (not the same as
  `meras.elected`).

`elected` comes from VRK colouring the winner's name link blue on the
listing.

### The campaign section is role-dependent

Mayoral candidates carry `politines-kampanijos-dalyvio-duomenys`;
council-only candidates do not (their campaign is run by the list).
`Savarankiškas` participants publish all five campaign tabs;
`Atstovaujamasis` ones only donations, which can be empty. Campaigns carry
`sprendimai` — VRK decisions about the campaign, each
`{rowNumber, title, date, number, note, urls}`.

### `profilis.kita` keys vary by role

- council-only: `savivaldybe`, `sarasas`, `numeris-sarase`,
  `porinkiminis-numeris-sarase`; no nomination row, no `turas`.
- mayor-only: `savivaldybe`, `iskele-i-savivaldybes-merus`, `turas`,
  `sarasas`, `numeris-sarase`, `porinkiminis-numeris-sarase` (the last three
  `null`).
- dual: `savivaldybe`, `iskele-i-tarybos-narius-ir-merus`, `turas`,
  `sarasas`, `numeris-sarase`, `porinkiminis-numeris-sarase`.

The nominator sits under two labels; `kandidatavimas` carries the same facts
under one key set regardless of role.

### `profilis.pastaba` forms

`null` when nothing was won; otherwise, with the verb agreeing in gender:

- list form (1,498 council members) —
  `Išrinktas pagal Demokratų sąjungos „Vardan Lietuvos“ sąrašą`
- mayoral form (60 mayors) —
  `Išrinkta Alytaus rajono (Nr.3) savivaldybėje II ture`

A dual candidate elected only to the council gets the list form. The list
name is in the genitive (coalitions inflect every member party), so join on
`partyList.id`, not the string.

### `biografija` numbering

The 2023 numbering shared with `2023-spalio-8-kupiskio-mero` and
`2023-rugsejo-3-seimo-raseiniai-kedainiai` (nationality at Q2 shifts
education and work by one against the 2024 modules). The Q3 and Q5 tables
sit inside their question's row or the next; both are collected.

### Other sections

- `anketa` — the 2023 municipal set (see Kupiškis). 539 of the 13,796
  carry a conviction; several offences give several Q13.4 blocks, all in the
  one entry's `nusikalstamos-veikos`.
- `privaciu-interesu-deklaracija` as 2024; `kiti-duomenys` under `tekstas`.
- `kita` is empty for every fixture candidate.

## Appendix: 2019 municipal councils and mayors (`2019-kovo-3-savivaldybiu-tarybu`)

13,666 candidates across all 60 municipalities. The record around the pages
is the 2023 municipal one — `candidateNote`, `kandidatavimas`, `candidateId`
as `<name-slug>-<vrkCandidateId>` (`nerijus-cesiulis-2406286`), a
role-dependent campaign section. The pages are the 2016-era family of
`2017-balandzio-23-meru`, whose parsers this module reuses; none of the 2023
page shapes apply.

### `kandidatavimas`

As in 2023: `vrkCandidateId`, `savivaldybe`, `roles`, `tarybosNarys`,
`meras`, `isrinktas`.

- Roles: 13,256 council-only, 379 dual, 31 mayor-only. `isrinktas` is not
  `meras.elected` (`gediminas-dauksys-2408494` took the council seat and lost
  the mayoralty).
- `partyList.name` covers parties, coalitions and the 87 "visuomeniniai
  rinkimų komitetai"; there were no politiniai komitetai in 2019.

### `normalized.anketa` is the 2016-era key set

The 2016 questionnaire as narrowed by the April 2017 mayoral module:
`gimimo-data` (Q5), `adresas` (Q6), `pareiskimai`, `gimimo-vieta` (Q10),
`tautybe` (Q11), `issilavinimas` (Q12), `pedagoginis-vardas`,
`uzsienio-kalbos` (Q13), `politine-organizacija` (Q14),
`anksciau-isrinktas` (Q15), `pagrindine-darboviete` (Q16),
`visuomenine-veikla` (Q17), `pomegiai` (Q18), `seimine-padetis` (Q19),
`sutuoktinio-vardas-pavarde`, `vaiku-vardai-pavardes` (Q20),
`kita-apie-save`.

`pareiskimai` has **nine** keys (savivaldybių tarybų rinkimų įstatymas,
36 str. 11–12 d.):

- `ar-nebaigta-teismo-paskirta-bausme` (Q8.1), `ar-atliekate-karo-tarnyba`
  (Q8.2), `ar-eina-nesuderinamas-pareigas` (Q8.3),
  `ar-kitos-valstybes-institucijos-narys` (Q8.4),
  `ar-turite-kitos-valstybes-pilietybe` (Q8.5), `ar-buvote-pripazintas-kaltu`
  (Q9), `ar-veika-dekriminalizuota` (Q9.2),
  `ar-buvote-pripazintas-kaltu-uzsienyje` (Q9.3),
  `ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo` (Q9.4).
- Answers read `Neturiu`/`Nesu`/`Neinu`/`Esu`/`Einu`/`Ne`.
- Q9 is answered on the question row.
- `teistumo-detales` — the Q9.1 detail table, keys `nuosprendzio-data`,
  `nuosprendzio-valstybe`, `nuosprendzio-institucija`,
  `nusikalstama-veika`; empty unless Q9 is `Taip`. The last anketa key.

VRK nests the conviction table inside the anketa table on `Taip` pages;
`gintas-orda-2400958` is the fixture covering it.

Expected nulls: `issilavinimas.aprasas` and `anksciau-isrinktas.aprasas`
for everyone (the data is in `irasai`), and `kita-apie-save` for most
(`Nenurodė`).

### `biografija` and `profilis.nuotrauka` are role-dependent

`biografija` (free text) and `profilis.nuotrauka` (base64) are published
only for mayoral candidates, 410 of 13,666; about 97 % of records carry
neither.

### The campaign section is role-dependent

As in 2023: present for mayoral candidates only. `Savarankiškas`
participants publish all five tabs with `registravimo-data` and
`sprendimo-numeris`; `Atstovaujamasis` ones only donations, often empty.

### `profilis.kita` keys vary by role

The 2023 key sets, but the nomination row is
`iskele-i-tarybos-narius-merus` (no "ir": mayors were council members ex
officio):

- council-only: `savivaldybe`, `sarasas`, `numeris-sarase`,
  `porinkiminis-numeris-sarase`
- mayor-only: `savivaldybe`, `iskele-i-tarybos-narius-merus`, `turas`,
  `sarasas`, `numeris-sarase`, `porinkiminis-numeris-sarase` (the last three
  `null`)
- dual: the same six, all populated

### `profilis.pastaba` forms

As in 2023: list form for council members
(`Išrinktas pagal Visuomeninio rinkimų komiteto „Už Alytų“ sąrašą`),
mayoral form for mayors (`Išrinktas Akmenės rajono (Nr.1) savivaldybėje I
ture`). The list name is genitive; join on `partyList.id`.

### Other sections

- Declarations: the income rows read in prose (`Deklaruota
  apmokestinamųjų ir neapmokestinamųjų pajamų suma`, `Deklaruota mokėtina
  pajamų mokesčio suma`); the rest of the GPM308 breakdown stays in
  `rawData`.
- `privaciu-interesu-deklaracija` follows 2019 EP.
- `kita` is empty for almost every candidate; one published a signed pledge
  not to bribe voters (`kita.tekstai`, `kita.nuorodos`).

## Appendix: 2025 mayors (`2025-kovo-16-meru`)

- `candidateNote` — the listing's note on a revoked registration
  (`išbrauktas - Seimo nutarimu`), `null` otherwise. The listing is the only
  source.
- `profilis.pastaba` — the two elected mayors
  (`Išrinktas Joniškio rajono (Nr.11) savivaldybėje II ture`).
  `profilis.kita`: `savivaldybe`, `iskele-i-savivaldybes-merus`, `turas`,
  `sarasas`, `numeris-sarase`, `porinkiminis-numeris-sarase`.
- `anketa`: `adresas` (Q6), `einamos-pareigos` (Q7),
  `narystes-politinese-organizacijose.irasai` (a Q8 table, unlike 2023's
  inline answer), Q9–Q14 under the 2024 keys; no Q15/Q16.
- `biografija` follows 2024 EP (no nationality question).
- Struck-off candidates have no campaign section (five tabs).
- `kita` is empty.

## Appendix: 2017 mayors (`2017-balandzio-23-meru`)

The 2016/2019-era shapes:

- `profilis.pastaba` — the two elected mayors. `profilis.kita`:
  `savivaldybe`, `iskele-i-tarybos-narius-merus`, `turas`, `sarasas`,
  `numeris-sarase`, `porinkiminis-numeris-sarase`.
- The portrait is base64.
- `anketa` keeps the 2016 keys: `gimimo-data` (Q5), `adresas` (Q6),
  `gimimo-vieta` (Q10), `tautybe` (Q11), `issilavinimas` (Q12),
  `uzsienio-kalbos` (Q13), `politine-organizacija` (Q14),
  `anksciau-isrinktas` (Q15), `pagrindine-darboviete` (Q16),
  `visuomenine-veikla` (Q17), `pomegiai` (Q18), `seimine-padetis` (Q19),
  `vaiku-vardai-pavardes` (Q20). `pedagoginis-vardas`,
  `sutuoktinio-vardas-pavarde` and `kita-apie-save` (Q21, number in brackets
  at the end) are matched on prompt text.
- `pareiskimai` — 36 str. 11 d. declarations; no `8.1`, numbers without a
  trailing dot. `ar-buvote-pripazintas-kaltu` is Q9 (36 str. 12 d.), answered
  on the continuation row quoting the statute.
- `biografija` is free text.
- Income rows name their GPM308 field numbers.
- `privaciu-interesu-deklaracija` as 2019 EP.
- `kita` is empty.

## Appendix: 2017 Marijampolė mayor (`2017-rugsejo-10-marijampoles-mero`)

The `2017-balandzio-23-meru` vintage. A candidate whose campaign is run by
the party publishes a participant page without tabs, so the campaign entry
has the metadata, an empty `aukos-pagal-sekcija`, and no reports or
contracts.

## Appendix: 2021 mayors (`2021-spalio-10-meru`)

The `2023-spalio-8-kupiskio-mero` page shape (nationality at Q2 in the
biography, linked portrait), with the 2020 Seimo anketa numbering:

- `adresas` (Q6) and `kontaktai` — `telefonas` (Q6.1), `el-pastas` (Q6.2),
  `socialiniu-tinklu-paskyros` (Q6.3)
- `einamos-pareigos` (Q7), `narystes-politinese-organizacijose.tekstas`
  (Q7.1, printed without a dot, so numbers are re-derived tolerantly)
- `pareiskimai` — 36 str. 11 d. (Q8.1–Q8.4), 36 str. 12 d. (Q9, Q9.2–Q9.4)
  and the former-USSR question (Q10)
- `teistumo-detales.irasai` — the Q9.1 table when Q9 is "Taip", columns
  mapped to `nuosprendzio-data`, `nuosprendzio-valstybe`,
  `nuosprendzio-institucija`, `nusikalstama-veika`
- `kita` is empty

## Appendix: 2021 Radviliškis mayor (`2021-balandzio-11-radviliskio-mero`)

The `2021-spalio-10-meru` vintage.

- Everyone answered "Nenurodė" to Q10, so
  `pareiskimai.ar-bendradarbiavote-su-ssrs-tarnybomis` is null throughout.
- `kita` is populated for one candidate: a document title under `tekstai`
  and its URL under `nuorodos`.

## Appendix: 2017 Seimo by-election (`2017-balandzio-23-seimo-anyksciai-panevezys`)

The 2016 Seimo layout: the 2016 anketa key set, free-text `biografija`,
base64 portrait, form-id `privaciu-interesu-deklaracija`.

- `candidateName` drops the `(V)` suffix; `profilis.pastaba` (the elected
  note) is rendered inside the name cell.
- `profilis.kita`: `vienmandate-apygarda`, `iskele`, `turas`, `sarasas`,
  `numeris-sarase`, `porinkiminis-eiles-numeris`.
- The Q12 and Q15 tables are in a row of their own and collected from both
  rows.
- `kita` is empty.

## Appendix: 2018 and 2019 Seimo by-elections

`2018-rugsejo-16-seimo-zanavykai` (Zanavykai No. 64) and
`2019-rugsejo-8-seimo` (Žirmūnai No. 4, Gargždai No. 31, Žiemgala No. 46):
the 2016 Seimo layout, as above. In 2019 Gintautas Paluckas and Kazimieras
Juraitis carry one `teistumo-detales` entry each.

- `candidateName` drops the `(V)` suffix; `profilis.pastaba` holds one
  elected note per constituency.
- Income rows use the modern labels, though the heading still names GPM308.
- One 2019 candidate has two nominators in `profilis.kita.iskele.reiksme`.

## Appendix: 2015 Seimo by-elections (`2015-kovo-1-seimo-zirmunai`, `2015-birzelio-7-seimo-varena-eisiskes`)

Žirmūnai (No. 4) defines the 2015-era parsers; Varėna–Eišiškės (No. 70)
shares every shape. Full section order. The pre-2016 static layout:

- **No elected markers.** `profilis.pastaba` is null on every record;
  electedness is joined from the results tree (`kandidatavimas.isrinktas`).
  Both went to a second round; Žirmūnai's round-two page has no verdict, so
  its winner is the runoff plurality (`method: "runoff-plurality"` in the
  results file).
- The portrait is a linked JPG (`Kandidato<ID>Foto.jpg`). `profilis.kita`
  holds `apygarda`, `iskele` and a
  `savarankisko-`/`atstovaujamojo-politines-kampanijos-dalyvio-duomenys`
  entry linking the campaign participant page.
- `anketa` — the 2016 keys, with `mokslo-laipsnis` and `pedagoginis-vardas`
  read from the one line "Jei turite, nurodykite mokslo laipsnį <b>…</b>,
  vardą <b>…</b>" (true of the whole 2008–2015 family). `pareiskimai` stops
  at `ar-buvote-pripazintas-kaltu` (Q9.2). A bare `","` in
  `pagrindine-darboviete` normalizes to null.
- Declarations are in **litas**: `valiuta` (`"Lt"`) and `pastaba` (the note
  naming the declaration period, the source of `deklaracijos-metai`).
- `privaciu-interesu-deklaracija` is form-id keyed and keeps the spouse
  block.
- Campaigns: `registravimo-data` and `sprendimo-numeris` always null, plus
  four additions — donation records carry `amountEur` and `amountLt`; each
  donation section has a `suvestine` list (totals by source type);
  `auditorius.ataskaitos` lists the auditor's report PDFs; represented
  participants (`statusas: "Atstovaujamasis"`) carry `atstovauja`, the party
  whose campaign covers them.
- `kita` — the "Kandidato programa" text with the PDF URL in `nuorodos`
  (`Duomenų nėra` when none).

## Appendix: 2015 Telšiai mayor (`2015-lapkricio-8-telsiu-mero`)

The 2015 era above, with the municipal question set:

- `pareiskimai`: `ar-nebaigta-teismo-paskirta-bausme` (Q8.1),
  `ar-atliekate-karo-tarnyba` (Q8.2), `ar-eina-nesuderinamas-pareigas`
  (Q8.3), `ar-kitos-valstybes-institucijos-narys` (Q8.4),
  `ar-turite-kitos-valstybes-pilietybe` (Q8.5), `ar-buvote-pripazintas-kaltu`
  (Q9), and `teisiniai-argumentai` — the unnumbered explanation row after a
  "Taip" (null on every Telšiai record). Answers are first person
  (`Neturiu`, `Nesu`, `Neinu`, `Einu`).
- `profilis.kita`: `savivaldybe`, `iskele`, `numeris-sarase` for
  party-nominated candidates; a self-nominated candidate has an
  `issikeles-kandidatas` entry and no list fields.
- `kita` is `Duomenų nėra` for everyone.

## Appendix: 2015 repeat municipal elections (`2015-birzelio-7-pakartotiniai-sirvintos-trakai`, `2015-birzelio-21-pakartotiniai-silutes`)

Each district page has a mayoral section and a party-list index. Pages are
the 2015 municipal set (see Telšiai).

- Root `kandidatavimas`: `vrkCandidateId`, `savivaldybe`, `roles`,
  `tarybosNarys` (`partyList`, `listNumber`, `listPosition`), `meras`
  (`nominatedBy`). For a dual candidate the list position appears only here.
  `isrinktas` from the results join: the Širvintos mayor (round one), the
  Trakai mayor (round two) and Trakai's 24 council seats.
- The sitemap merges both listings on VRK's candidate id into `roles` plus
  `mayoralCandidacy` (`nominatedBy`) and/or `councilCandidacy` (`partyList`,
  `listNumber`, `listPosition`), with no `elected` key.
- **One person, two ids:** Marija Puč is 87693 (mayor) and 87694 (council),
  so two entries (`marija-puc`, `marija-puc-2`); `stats.markerJoinMismatch`
  is 1 for this. Count her once as a person, twice as candidacies.
- A candidacy whose questionnaire was never published reads `Rengiama`: the
  profile card is kept, every `anketa` field is null, with one
  `AnketaNotPublished` warning.
- `biografija` only for mayoral candidates.
- A council candidate with no campaign link has no campaign section
  (`jonas-sakurskis-2` in Šilutė).
- Šilutė's duplicate id is a real name collision — two Jonas Šakurskis,
  born 1953 and 1957 — so the `-2` suffix is right there.

## Appendix: 2015 municipal general (`2015-kovo-1-savivaldybiu`)

The 2015 municipal pages with the repeat elections' `kandidatavimas` block.

- `candidateId` is `<name-slug>-<vrkCandidateId>` (`valius-azuolas-77601`):
  140 of the 15,149 candidates share a name slug.
- `roles`: `["tarybos-narys"]` 14,715, `["meras", "tarybos-narys"]` 412,
  `["meras"]` 22. `isrinktas`: 57 mayors and 1,464 council seats (each
  list's top-M post-preference ranks, skipping the mayor-elect); the 48
  Šilutė and Trakai seats carry `rezultataiPanaikinti` and `false`.
  Širvintos, Šilutė and Trakai elected no mayor (the June repeats did).
- `meras.nominatedBy` is `null` for twelve mayoral candidates whose rows
  print no "- iškėlė …".

## Appendix: 2011 municipal general (`2011-vasario-27-savivaldybiu`)

The 2015 municipal pages (statute: 35 str. 12 d. and 89 str. 1 d.) with the
2015 `kandidatavimas` block. No direct mayoral vote; individuals could stand
alone.

- `roles` is `["tarybos-narys"]` everywhere and `meras` null.
  `candidateId` is `<name-slug>-<vrkCandidateId>`.
- `tarybosNarys` adds `listKind` — `partija` (560), `partiju-koalicija`
  (11) or `issikelusiu-kandidatu-koalicija` (28) — and `selfNominated`,
  `true` for the 143 individuals who stood alone (their `partyList`,
  `listKind` and `listPosition` are null and `listNumber` is their ballot
  number). A self-nominated coalition member is `false`; the card's
  `issikeles-kandidatas` flag marks them.
- `isrinktas`: 1,526 seats, 1,508 from list ranks and 18 from individuals'
  own rows (`method: "self-nominated"`).
- `profilis.kita` is the Telšiai shape; `issikeles-kandidatas` appears on
  an individual's card (no list fields) and a self-nominated coalition
  member's. A party-coalition member's card adds `iskele-2` and
  `numeris-sarase-2` (the recurring-label rule). `iskele.nuorodos` links the
  coalition's list page or the party's page.
- `profilis.vardas-pavarde` is in capitals (`ARTŪRAS ZUOKAS`);
  `candidateName` is title case.
- Sections: `profilis`, `anketa`, `turto-ir-pajamu-deklaracijos`,
  `privaciu-interesu-deklaracija`, `kita`. No `biografija`, no campaign
  section. Income is the GPM305 return in litas.
- `pareiskimai.teisiniai-argumentai` is the Q9 explanation row.

## Appendix: 2007 municipal general (`2007-vasario-25-savivaldybiu`)

The family's oldest pages (as the 2007 Dzūkija by-election: plain-text card,
unnumbered questionnaire, FR0462/GPM302 declarations, roman-numbered
interest form) with the 2011 `kandidatavimas` block. Only parties and
coalitions could nominate; no direct mayoral vote.

- `roles` is `["tarybos-narys"]` and `meras` null.
  `candidateId` is `<name-slug>-<vrkCandidateId>`.
- `tarybosNarys`: `partyList`, `listKind` (`partija` 596,
  `partiju-koalicija` 4; the sitemap's `coalitions` names their members),
  `listNumber` (the party's national number), `listPosition` (as printed; a
  withdrawn candidate keeps theirs, so gaps occur), `selfNominated` (false).
- `isrinktas`: 1,550 seats from each municipality's "Mandatus gavę
  kandidatai" page (`method: "mandates-page"`); no `rezultatuTuras`.
- `profilis.kita`: `apygarda` ("Elektrėnų rinkimų apygarda (8 )") and
  `iskele` from the header table, then `numeris-sarase` and `gimimo-data`
  from the card; a coalition member adds `numeris-partijos-sarase`. No
  links, photo or notice.
- `profilis.vardas-pavarde` is in capitals; `candidateName` is title case.
- `anketa` is keyed by prompts (`questionNumber` null throughout).
  `pareiskimai`: `ar-nebaigta-teismo-paskirta-bausme`,
  `ar-atliekate-karo-tarnyba`, `ar-eina-nesuderinamas-pareigas`,
  `ar-kitos-valstybes-institucijos-narys`,
  `ar-turite-kitos-valstybes-pilietybe`,
  **`ar-pasyvioji-rinkimu-teise-neapribota`** ("Neapribota" on 12,799 of
  13,419), `ar-buvote-pripazintas-kaltu` (72 "Taip") and
  `teisiniai-argumentai` (a bare text line after the answer; 39 of 78).
  `gimimo-data` is the card's date. `issilavinimas.irasai` and
  `anksciau-isrinktas.irasai` are tables with `aprasas` null.
  `mokslo-laipsnis` ("Moksliniai laipsniai", 753) and `pedagoginis-vardas`
  ("Moksliniai vardai", 133) appear only where printed; `kita-apie-save` is
  null. **`seimos-nariai`** (this election only) keeps the family line whole
  ("Sutuoktinis/sutuoktinė Vida, Vaikas Gintarė, Vaikas Ieva"), split into
  `sutuoktinio-vardas-pavarde` (Partneris/partnerė counts) and
  `vaiku-vardai-pavardes` (Augintinis counts, Anūkas does not; an unroled
  name continues the previous role). `seimine-padetis` is "Vedęs,
  ištekėjusi"; `tautybe` is verbatim ("Lietuvis (-ė)").
- An empty answer (`<b></b>`) leaves its key null. A question printed with
  no `<b>` (pasyvioji on 611 pages, citizenship on 8) runs into the next
  prompt; the normalizer splits on the form's labels so the missing answer
  is null and later answers keep their labels.
- Sections: `profilis`, `anketa`, `turto-ir-pajamu-deklaracijos`,
  `privaciu-interesu-deklaracija`. No `biografija`, `kita` or campaign
  section.
- Declarations are in litas. `gautos-pajamos` and
  `sumoketas-pajamu-mokestis` are the **sum of the five FR0462 lines**
  ("FR0462 Formos deklaracijos: Gauta 39019.30 Lt, išskaičiuota pajamų
  mokesčio 11613.00 Lt", then S33, S15, S0, S); the candidate filed one and
  the rest read zero, so all five at zero is a declared zero.
  `pajamos-pagal-forma` says which. A sentence with no tax figure (531)
  reads the income and leaves the tax null.
- Asset declaration headings: `Gyventojo turto deklaracija` (9,664),
  `Šeimos turto deklaracija` (3,672), `Sutuoktinio turto deklaracija`
  (352); 56 publish none. See "The spouse" in the shared section. A section
  repeated verbatim (16 records) is read once.
- `privaciu-interesu-deklaracija` is the roman-numbered 2007–2009 form.

## Appendix: Seimas archive (`1996-spalio-20-seimo`, `1997-kovo-23-seimo-pakartotiniai`, `1997-gruodzio-21-seimo-pakartotiniai`, `1998-kovo-22-seimo-pakartotiniai`, `1998-lapkricio-15-seimo-pakartotiniai`, `1999-kovo-21-seimo-pakartotiniai`)

1996 defines the parsers (`scraper/shared/seimo_archive_1990s.py`); the five
1997–1999 repeats share every shape. (The 1999 directory name, `19990321`,
is the next generation's naming; its pages are this family's.) The pages are
Teleport Pro snapshots of `lrs.lt/cgi-bin/ora7dbcgi/...` with no tabs, so
the record is a **subset** of the body's shape. Every one of the
family's 950 records carries an `anketa`; figures below are over all 950.

- `rawData` order: `profile`, `candidacies`, `residence`, `personal`,
  `biography`, `declaration`. `normalized` order: `profilis`, `anketa`,
  `kandidatavimas`, `gyvenamoji-vieta`, `biografija`,
  `turto-ir-pajamu-deklaracijos`.
- `normalized.profilis`: `vardas-pavarde`, `nuotrauka`,
  `biografijos-nuoroda`, `pajamu-deklaracijos-nuoroda`. No `pastaba`.
- `rawData.profile`: `candidateDisplayName`, `photoUrl` (this family's name
  for `photoSrc`), `biographyUrl`, `incomeDeclarationUrl`.
- `rawData.candidacies` is a **list**: usually the constituency plus
  optionally a `Daugiamandatė` list entry, but not at most two
  (`uksas-vladislovas`, 1996, has four). Each entry is
  `{apygardaName, apygardaNumber, apygardaUrl, nominator, nominatorUrl,
  listNumber}`; self-nominated reads `nominator: "Išsikėlė pats"` (or
  `"Išsikėlė pati"`) with `nominatorUrl: ""`. `normalized.kandidatavimas`
  mirrors it as a list with keys `apygarda`, `apygardos-numeris`,
  `apygardos-nuoroda`, `iskele`, `iskele-nuoroda`, `numeris-sarase` —
  **not one candidacy per record.**
- **The results join** writes onto each entry when
  `sitemaps/<election-id>.results.json` exists:
  - `isrinktas` — `true`/`false` on every candidacy (`neįvyko` included).
    Per candidacy, not per record: a constituency win marks every candidacy
    for that constituency, so 123 elected records hold 126 elected
    candidacies.
  - On the elected candidacy: `isrinktas-kaip` (`"vienmandate"` or
    `"daugiamandate"`), `rezultatu-saltinis`, and `rezultatu-turas` (1 or 2)
    for a constituency seat.
  - `turai` — on a constituency candidacy, its row on each round's page,
    oldest first: `{turas, apygardos-numeris, balsai-apygardoje,
    balsai-pastu, balsai, vieta, saltinis}` (`vieta` = placing by total
    votes). 1,002 candidacies.
  - On a ranked 1996 `Daugiamandatė` candidacy:
    `porinkiminis-numeris-sarase`, `teigiami-balsai`, `neigiami-balsai`,
    `reitingo-balai`, `reitingo-saltinis` (from
    `seim96/rkreitl.htm-<list>.htm`); 662 of 818. The by-elections had no
    list seats.
- **Three card fields sit inside a malformed HTML comment** and are read by
  regex over the raw HTML: `rawData.residence` (`Gyvenamoji vieta`, 949),
  `rawData.personal.birthPlace` (`Gimimo vieta`, 873) and
  `rawData.personal.nationality` (`Tautybė`, 483). The eligibility Q&A in
  the same comment is the failed query's default text and is not stored.
- **`rawData.personal`** is the questionnaire, keyed as the municipal
  archive keys it: `birthPlace`, `nationality`, `education`,
  `foreignLanguages`, `academicDegree`, `academicTitle`,
  `previouslyElected`, `mainWorkplace`, `publicActivity`, `aboutSelf`,
  `familyStatus`, `familyMembers`. Always complete (blank reads `""` or
  `[]`).
- **`normalized.anketa`**: `tautybe`, `issilavinimas`, `mokslo-laipsnis`,
  `pedagoginis-vardas`, `uzsienio-kalbos`, `anksciau-isrinktas`,
  `pagrindine-darboviete`, `visuomenine-veikla`, `kita-apie-save`,
  `seimine-padetis`, `sutuoktinio-vardas-pavarde`, `vaiku-vardai-pavardes`,
  `seimos-nariai`. A key is **absent** when the card left it blank.
  - `issilavinimas` — `{aprasas, irasai:[…]}` with the card's controlled
    level ("Aukštasis", "Aukštesnysis", …) in the entry's `issilavinimas`
    field, the others null.
  - `anksciau-isrinktas` — one entry per body named; `laikotarpis` null.
  - `seimos-nariai` — `[{name, relation}]`; `sutuoktinio-vardas-pavarde`
    and `vaiku-vardai-pavardes` are the comma-joined "Sutuoktinis/sutuoktinė"
    and "Vaikas" subsets ("Augintinis (ė)" and "Anūkas (ė)" appear only in
    `seimos-nariai`).
  - Coverage by election (1996-10 / 1997-03 / 1997-12 / 1998-03 / 1998-11 /
    1999-03): `gimimo-vieta` 838/21/3/9/5/16 (892), `seimine-padetis`
    733/19/2/6/7/12 (779), `uzsienio-kalbos` 710/18/4/7/10/21 (770),
    `seimos-nariai` 697/19/4/6/10/20 (756), `tautybe` 421/23/4/5/10/20
    (483), `issilavinimas` 337/19/1/8/10/21 (396), `anksciau-isrinktas`
    317/11/2/1/6/7 (344), `mokslo-laipsnis` 161/5/2/0/3/2 (173),
    `visuomenine-veikla` 99/11/2/0/4/16 (132), `pedagoginis-vardas`
    84/2/0/0/2/1 (89), `kita-apie-save` 38/0/0/0/0/0 (38),
    `pagrindine-darboviete` 1/23/4/8/10/20 (66) — 1996 candidates left the
    workplace blank almost universally.
- `rawData.biography` — `null` when no `Biografija` page is linked
  (`astrauskas-vytautas`), else `{"text", "birthDate", "birthYear"}`.
- **`turto-ir-pajamu-deklaracijos`** comes from the linked `kpdl.htm`,
  parsed by `scraper/shared/deklaracija_archive_1990s.py` (shared with the
  municipal archive):
  - `privalomas-registruoti-turtas` and `pinigines-lesos` are **always
    null**: the form sums them. The combined figures are
    `turtas-ir-pinigines-lesos-metu-pradzioje`,
    `turtas-ir-pinigines-lesos-metu-pabaigoje` and
    `kalendoriniais-metais-isigytas-turtas`.
  - `gautos-pajamos` and `sumoketas-pajamu-mokestis` come from section
    III's "20. Iš viso" row **only when it is not smaller than row 1**;
    otherwise null plus a `DeclarationTotalBelowItsOwnRow` anomaly. Row 1 is
    always `gautos-pajamos-darbo-santykiu` and
    `sumoketas-pajamu-mokestis-darbo-santykiu`.
  - `valiuta` is `"Lt"`.
  - Also: `israso-data`, `israsa-isdave` (municipal family only),
    `mokesciu-nepriemoka`, `privaloma-sumoketi-mokesciu-ir-sankciju`,
    `seimos-nariu-skaicius`, `islaikytiniu-skaicius`,
    `seimos-nariu-iki-18-metu`.
  - Absent when no declaration is linked.
- **`anketa.gimimo-vieta`** comes from the card (873 of 950), else from the
  biography's opening sentence (19 more), marked
  `gimimo-vietos-saltinis: "biografijos-tekstas"`; 58 have neither. The card
  form keeps its spacing (`"Melagėnų k. , Švenčionių raj."`). Prose
  candidates (locative → nominative) are accepted only if listed in
  `scraper/shared/vietovardziai.json`.
- **Nothing else is extracted from biography prose**: education and work
  captures were wrong about a third of the time. The text stays in
  `biografija.tekstas`.
- **`anketa.gimimo-data` is derived from biography prose** ("Gimė 1942 m.
  rugpjūčio 3 d. Panevėžyje"), marked
  `gimimo-data-saltinis: "biografijos-tekstas"`: a weaker source than a
  published field. These pages print no birth date.
  - Coverage over the 950 records of this family: 722 full dates (76 %), 169
    year-only, 59 neither.
  - `gimimo-metai` holds year-only cases ("Gimė 1950 m."); a year is never
    promoted to a date. The person index keys those records by name +
    `~year`.
- No private-interest declaration or campaign-finance sections.

## Appendix: Municipal archive (`1997-kovo-23-savivaldybiu-tarybu`, `1997-birzelio-29-svenciniu-tarybos-pakartotiniai`)

Both use `scraper/shared/savivaldybiu_archive_1997.py` and the `19970323`
directory, told apart by the phase prefix in
`apgtl.htm-<phase>+<municipality>.htm` (`3` general, `5` Švenčionys repeat).
Per-candidate facts land in `anketa` under the corpus's concept keys.

- `rawData` order: `profile`, `candidacy`, `personal`. `normalized` order:
  `profilis`, `kandidatavimas`, `anketa`.
- `normalized.anketa`: `gimimo-data`, `gimimo-vieta`, `gyvenamoji-vieta`,
  `tautybe`, `issilavinimas`, `mokslo-laipsnis`, `pedagoginis-vardas`,
  `uzsienio-kalbos`, `anksciau-isrinktas`, `pagrindine-darboviete`,
  `visuomenine-veikla`, `kita-apie-save`, `seimine-padetis`,
  `sutuoktinio-vardas-pavarde`, `vaiku-vardai-pavardes`, `seimos-nariai`.
  - The general election has 156 academic degrees and 112 titles;
    Švenčionys prints none.
  - `anksciau-isrinktas` and `kita-apie-save` are always null (no municipal
    page prints them; the card reader `scraper/shared/archive_1990s_card.py`
    is shared).
  - `gimimo-data` is normalized from `1944 03 04` to `1944-03-04` (in
    `rawData.personal` too), which identity matching depends on.
  - A field's value ends at whichever label comes next
    (`abariunas-bronius` guards this).
  - The source label *Šeimyninė padėtis* is keyed `seimine-padetis`;
    `seimos-nariai` is `[{name, relation}]`.
  - `issilavinimas` is `{"aprasas", "irasai": [...]}` with the controlled
    level ("Aukštasis", "Aukštesnysis", "Specialus vidurinis", "Vidurinis",
    "Nebaigtas aukštasis", "Nebaigtas vidurinis", "Aspirantūra",
    "Doktorantūra") in the entry's `issilavinimas`;
    `mokymo-istaigos-pavadinimas`, `specialybe` and `baigimo-metai` are null.
- `normalized.kandidatavimas` is a single object: `savivaldybe`,
  `savivaldybes-numeris`, `savivaldybes-nuoroda`, `iskele`,
  `iskele-nuoroda`, `numeris-sarase`, `isrinktas`, plus `isrinktas-kaip` and
  `rezultatu-saltinis` on winners and `rezultatai-negalioja` on the voided
  March Švenčionys records.
- `rawData.candidacy`: `{municipalityName, municipalityNumber,
  municipalityUrl, nominator, nominatorUrl, listNumber}`.
- `rawData.personal`: `birthDate`, `birthPlace`, `residence`,
  `nationality`, `education`, `foreignLanguages` (list), `mainWorkplace`,
  `publicActivity`, `familyStatus`, `familyMembers` (list of
  `{name, relation}`), `academicDegree`, `academicTitle`,
  `previouslyElected` (list), `aboutSelf`. A label missing from the page
  normalizes to `null`/`[]` (`pilvelis-algirdas` has no "Tautybė:").
- `rawData.profile`: `candidateDisplayName`, `incomeDeclarationUrl`. No
  portrait.
- **`turto-ir-pajamu-deklaracijos`** — as in the Seimas archive above. In
  the general election the "Iš viso" row is below row 1 on 4,463 of 5,477
  declarations (4,134 for tax), so most records have a null
  `gautos-pajamos` and a populated `gautos-pajamos-darbo-santykiu`
  (elsewhere: 9 of 879 in 1996, 1 of 108 in Švenčionys). The declarations
  also carry `darboviete`, `pareigos`, `nepagrindines-darbovietes` and
  `pareigos-nepagrindinese-darbovietese`.
- **Elected status** (`kandidatavimas.isrinktas`) is joined by VRK id from
  each municipality's `rikl.htm-<code>.htm` "Apygardoje išrinkti kandidatai"
  page, linked from its `rapgpl.htm-<code>.htm` votes page (`python -m
  scraper build-results <id>`,
  `scraper/shared/savivaldybiu_archive_1997_results.py`):
  - `isrinktas` — `true`/`false` on every record: 1,459 councillors across
    55 municipalities in the general election, 25 in Švenčionys.
  - On winners: `isrinktas-kaip` (`"tarybos-narys"`) and
    `rezultatu-saltinis`.
  - `rezultatai-negalioja` — on the 104 Švenčionių rajono (Nr. 47) general
    election records: VRK voided that result (decision Nr. 149 of
    1997-03-29) and re-ran it on 1997-06-29. Carries the decision text
    (`pastaba`) and page (`saltinis`).
  - 31 elected rows print a list position 1–3 below the card's (the elected
    page renumbers after withdrawals): `memberMismatches` in the results
    file and an `ElectedCandidacyMismatch` warning on each record.
- No biography, private-interest or campaign-finance sections.
- 46 name collisions in the general election take the positional `-2`
  suffix.

## Appendix: 2004 European Parliament (`2004-ep`)

VRK's original 2004 static site, a layout family of its own
(`scraper/elections/ep_2004/`). Four sections in both layers:
`profilis`/`profile`, `anketa`, `biografija`,
`turto-ir-pajamu-deklaracijos`/`turtoIrPajamuDeklaracijos`. No
private-interest declaration, `kita` or campaign section.

### `kandidatavimas`

The 2009/2014 EP shape — `vrkCandidateId`, `roles: ["daugiamandate"]`,
`vienmandate: null`, `daugiamandate` (`sarasas`, `sarasoNumeris` = VRK's
list number, `sarasoId` = the list page's id, `numerisSarase`), the results
join (`isrinktas`, `isrinktasKaip: "daugiamandate"`, `rezultatuSaltinis` =
the members page) — plus, from the list's ranking page, on every record:
`porinkiminisNumerisSarase`, `pirmumoBalsai`, `pirmumoBalsuSaltinis`.

One post-election substitution: Prunskienė (VNDPS, list 1, position 1) has
`isrinktas: true` and `mandatasNutrauktas` — `decision` (`label` "VRK 2004
m. birželio 21 d. sprendimu Nr. 180", `url`), `statementUrl`,
`replacedBy: "260979"`, `note`. Didžiokas has `isrinktas: true`,
`pakeiteNari: "260978"` and `vrkSprendimas` (decision Nr. 181). Fourteen
records are elected for thirteen seats; the other 227 are `false`.

### `profilis`

`vardas-pavarde` from the second heading ("Justas Vincas PALECKIS"),
`pastaba` always null, `nuotrauka` (linked under `2004/euro/nuotraukos/`),
and `kita` with exactly `iskele` (the list, linking its page) and
`priesrinkiminis-numeris-sarase` (as text).

### `normalized.anketa`

The 2009 EP key set, except:

- `gimimo-data` is Q3, printed `1942.01.01` and normalized `1942-01-01`.
- `pareiskimai`: `ar-turite-kitos-valstybes-pilietybe`,
  `kitos-valstybes-pilietybe-valstybe` and
  `ar-atimta-balsavimo-teise-kitoje-valstybeje` are Q8.4 / 8.4.1 / 8.4.2
  (no 8.3); the rest Q8.1, 8.2 and 9.1–9.3. Answers keep the third person
  (`Neturi`/`Turi`, `Nėra`/`Yra`, `Nebuvo`/`Buvo`). `teisiniai-argumentai`
  is the unlabelled row after 9.3 (five records).
- `issilavinimas.irasai` columns: `issilavinimas`,
  `mokyklos-istaigos-pavadinimas`, `specialybe`, `baigimo-metai` (2009+:
  `mokymo-istaigos-pavadinimas`); `aprasas` always null.
  `mokslo-laipsnis` and `pedagoginis-vardas` come from the "Moksliniai
  laipsniai:" / "Moksliniai vardai:" lines (78 and 28).
- List answers (Q13, Q18, Q20) are one `<b>` per item, joined with ", ";
  `uzsienio-kalbos` is a list; the raw row keeps `answerItems`.
- An empty `<b>` gives a null key. Šiškauskienė's page omits Q19, the
  spouse line and Q20.

### `biografija`

`tekstas` is the blockquote's paragraph, usually opening with the name and
nominator in capitals; `rawData.biografija.html` is the blockquote.

### `turto-ir-pajamu-deklaracijos`

Litas (`valiuta: "Lt"`, `pastaba` null), from two extracts:

- Assets: the family form ("METINĖ ŠEIMOS TURTO DEKLARACIJA", 144) or the
  individual form ("METINĖ GYVENTOJO TURTO DEKLARACIJA", 97), sections
  I–V with one total each, `privalomas-registruoti-turtas` …
  `gautos-paskolos`. A "-" total is null. `deklaracijos-apimtis` is
  `seimos` or `gyventojo`.
- Income: one pair per FR0462 variant (FR0462, S33, S15, S0, S); the
  candidate filed one or more, the rest "-". `gautos-pajamos` and
  `sumoketas-pajamu-mokestis` sum the filed lines; `pajamos-pagal-forma`
  keeps all five. Five records filed none: null.
- `israsai.turto-deklaracija` / `israsai.pajamu-deklaracija`:
  `pavadinimas`, `israsa-isdave` (the tax office), `gavimo-data`,
  `pildymo-data` (ISO), `darboviete`.

`rawData.turtoIrPajamuDeklaracijos.sections` holds both extracts with
`title`, `issuer`, `receivedDate` and `items`: roman section headings key
their totals (row label as `label`), form lines are `{form, income, tax}`.

## Appendix: 2002 Presidential (`2002-prezidento`)

Seventeen candidates on the 2002 LRS-ITD site
(`scraper/elections/prezidento_2002/`). **Text is parsed; scans are
archived and linked, never OCR'd.** Sections: `profilis`/`profile`, a
prose-recovered `anketa`, `biografija`, `programa` and
`rawData.skenai`. **No `turto-ir-pajamu-deklaracijos`**: the declaration
is only a photograph.

### `kandidatavimas`

As 2004 presidential: `vrkCandidateId`, `vrkRegistrationId`; `turai` with
both rounds' national votes (two entries for Paksas and Adamkus); the
winner's `isrinktas: true`, `isrinktasKaip: "prezidentas"`,
`rezultatuTuras: 2`, `rezultatuSaltinis` (the final protocol page).

### `profilis`

`vardas-pavarde` ("Rolandas Paksas"), `pastaba` null, `nuotrauka`, and
`kita`: `registracija` (linking the decision), `pareiskimas`,
`duomenu-anketa` (two scan URLs), the declaration keyed by its label —
`seimos-turto-pajamu-deklaracija` (11) or
`gyventojo-turto-pajamu-deklaracija` (6) — `sveikatos-pazyma` (4) and
`tinklalapis` (9).

### `rawData.skenai`

The scan inventory: `pareiskimas`, `duomenu-anketa` (list), `deklaracija`
(`url`, `forma`), `sveikatos-pazyma` (list). The health-certificate URLs
are dead on VRK's mirror.

### `normalized.anketa`

From biography prose: sixteen full `gimimo-data` (with
`gimimo-data-saltinis: "biografijos-tekstas"`), one `gimimo-metai`
(Bernatonis, 1940), `gimimo-vieta` for ten.

### `biografija` and `programa`

`biografija` from the HTML page (`rawData.biografija.text` per line, plus
`headingName`); `programa` from the Word 97 document via
`scraper/shared/word_doc.py`. All seventeen parse.

## Appendix: 2004 Presidential (`2004-prezidento`)

Five candidates on the 2004 static site
(`scraper/elections/prezidento_2004/`). **No questionnaire.** Sections:
`profilis`/`profile`, a prose-recovered `anketa`, `biografija`, `programa`,
`turto-ir-pajamu-deklaracijos`; `rawData` also keeps `nuotrauka`.

### `kandidatavimas`

`vrkCandidateId` (the card anchor, equal to the declaration page id) and
`vrkRegistrationId` (the id the results tree keys on,
`rez_kand_l_<RID>_…`). The winner has `isrinktas: true`,
`isrinktasKaip: "prezidentas"`, `rezultatuTuras: 2`, `rezultatuSaltinis`.
`turai` on every record, one entry per round: `turas`, `balsai`,
`balsai-apylinkese`, `balsai-pastu`, `procentai-nuo-galiojanciu`,
`procentai-nuo-dalyvavusiu`, `saltinis`.

### `profilis`

`vardas-pavarde`, `pastaba` null, `nuotrauka` the full portrait from
`nuotrauka.html` (thumbnail URL in `rawData.nuotrauka.thumbnailUrl`), and
`kita`: `registracija` (the registration sentence, linking the decision),
`pareiskimas` (scan URL), `sveikatos-pazymejimas` (Adamkus only),
`interneto-svetaine` (all five). The sitemap keeps `registeredDate` and
`decision`.

### `normalized.anketa`

From biography prose, as the Seimas archive: `gimimo-data` (all five) with
`gimimo-data-saltinis: "biografijos-tekstas"`; `gimimo-vieta` resolves for
none.

### `biografija` and `programa`

Word 97 text (`scraper/shared/word_doc.py`): `rawData.*` keep `text` and
`sourceUrl`, `normalized.*.tekstas` the one-line form. Auštrevičius
published no programme, so his record has no `programa`.

### `turto-ir-pajamu-deklaracijos`

The 2004 EP shape. Adamkus and Auštrevičius filed the individual form, the
rest the family form; Adamkus's `privalomas-registruoti-turtas` is an
explicit `0`. All five filed income on FR0462S alone.

## Appendix: 2004 Seimas (`2004-seimo`) and the 2005 Kėdainiai by-election (`2005-lapkricio-20-seimo-kedainiai`)

The 2004 EP pages and sections. Kėdainiai 2005 is the same shape for a
constituency-only field: `roles: ["vienmandate"]`, `daugiamandate` null, no
rank or preference votes, the winner's `rezultatuTuras` 2, four of five with
`savarankiskasKampanijosDalyvis`.

### `kandidatavimas`

The 2008/2012 Seimo shape: `roles` in first-seen order (lists first),
`vienmandate` (`apygarda`, `apygardosNumeris`, `apygardosId`, `iskele` —
the constituency page's nominator: a party, `Išsikėlė pats` or `Išsikėlė
pati`), `daugiamandate` (`sarasas`, `sarasoNumeris`, `sarasoId`,
`numerisSarase`, plus `koalicijosPartija` and `numerisPartijosSarase` for a
coalition's candidate), the other slot null. 534 both, 649 list only, 68
constituency only. Also:

- `vienmandate.kitiIskelejai` (two records) — a nominator the card names
  and the constituency page does not.
- `savarankiskasKampanijosDalyvis` (455) — `sprendimas` ("Nr.194,
  2004.09.16") and `nuoroda` (`kandidatai/pazym_l_<ID>.pdf`).

Results: `isrinktas`, `isrinktasKaip` (70 `daugiamandate`, 71
`vienmandate`), `rezultatuSaltinis`, and `rezultatuTuras` for constituency
seats (5 first round, 66 runoffs). Every list candidate has
`porinkiminisNumerisSarase`, `pirmumoBalsai`, `pirmumoBalsuSaltinis`; the
128 on the unranked LLRA list have the list order and a null
`pirmumoBalsai`. Constituency votes are not joined.

### `profilis.kita`

One `apygarda`/`iskele` pair per candidacy in card order: the constituency
(`apygarda` = "Dainų (Nr.25)", `iskele` the nominator), then `apygarda-2` =
"Daugiamandatė", `iskele-2` the list and `priesrinkiminis-numeris-sarase`;
a coalition's candidate adds `iskele-3` (the member party, `"(Iškėlė"`) and
`priesrinkiminis-numeris-sarase-2`. Independent campaign participants add
`kandidatas-registruotas-savarankisku-politines-kampanijos-dalyviu-sprendimas`.

### `normalized.anketa`

The EP key set with the Seimas Q8 block: `pareiskimai` has
`ar-nebaigta-teismo-paskirta-bausme` (8.1), `ar-atliekate-karo-tarnyba`
(8.2), `ar-turite-kitos-valstybes-pilietybe` (8.3),
`ar-susijes-priesaika-uzsienio-valstybei` (8.4),
`ar-bendradarbiavote-su-uzsienio-tarnybomis` (9.1),
`ar-buvote-pripazintas-kaltu` (9.2),
`ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo` (9.3) and
`teisiniai-argumentai`. `adresas` is Q6 "Nuolatinė gyvenamoji vieta".

### `turto-ir-pajamu-deklaracijos`

As 2004 EP (699 family, 550 individual asset extracts). Žiobakienė has no
section (no declarations page); Matkevičius has the income extract only.

## Appendix: June 2003 new Seimo elections (`2003-birzelio-15-seimo-nauji`)

The 2004 Seimas sections on `rinkimai/2003/seimas/`, the 2004 static site
one generation early. 27 records in four constituencies.

### `kandidatavimas`

Constituency-only: `vrkCandidateId`, `roles: ["vienmandate"]`,
`vienmandate` (`apygarda`, `apygardosNumeris`, `apygardosId`, `iskele` — a
party on all 27), `daugiamandate` null. No list fields, no
`savarankiskasKampanijosDalyvis`.

- `isrinktas` is `false` on every record, and known: all four
  constituencies fell below the turnout threshold. No `isrinktasKaip`,
  `rezultatuTuras` or `rezultatuSaltinis`.
- `turai` — one entry: `turas`, `apygardos-numeris`, `balsai-apylinkese`,
  `balsai-pastu`, `balsai`, `procentai-nuo-galiojanciu`, `vieta`,
  `saltinis`; joined by anketa id.

### `profilis`

`vardas-pavarde` from the `<h2>` ("Vilija ALEKNAITĖ ABRAMIKIENĖ"),
`pastaba` null, `nuotrauka`, and `kita` exactly `apygarda`/`iskele`.

**The photo URL contains the candidate's asmens kodas**
(`…/kandidatai/45705040120_17.jpg`, all 27). It is kept as the source link;
nothing is derived from it. The stray space before the filename is
stripped.

### `normalized.anketa`

The 2004 Seimas key set, but **the birth date is Q5**. Q9.1–9.3 carry a
`<sup>*</sup>` footnote marker. All 21 questions are answered on all 27
pages, "Nenurodė" included (null). `teisiniai-argumentai` is filled on one
record. `issilavinimas.aprasas` and `anksciau-isrinktas.aprasas` are null.

`issilavinimas.irasai` and `anksciau-isrinktas.irasai` keep the 2004
column keys (`issilavinimas`, `mokyklos-istaigos-pavadinimas`,
`specialybe`, `baigimo-metai`; `institucijos-pavadinimas-pareigos`,
`laikotarpis`), keyed positionally because **the 2003 tables have no
header row**.

### `turto-ir-pajamu-deklaracijos`

The **2002 municipal** extract: numbered summary lines in litas. Assets and
securities are summed (III S1 + IV S1), so
`privalomas-registruoti-turtas` and
`vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai` are always
null; the era keys are
`turtas-ir-vertybiniai-popieriai-laikotarpio-pradzioje`/`-pabaigoje`,
`pinigines-lesos-laikotarpio-pradzioje`/`-pabaigoje` and
`bendros-pinigines-lesos-banke-laikotarpio-pradzioje`/`-pabaigoje`.
`pinigines-lesos` is item 8's end figure. `deklaracijos-apimtis`:
`gyventojo` 18, `seimos` 9.

Own keys beside `valiuta: "Lt"`:

- `forma` — "Lietuvos Respublikos gyventojo turto ir pajamų deklaracija"
  (18, items 3–12, joint bank accounts as 9) or "Lietuvos Respublikos šeimos
  turto ir pajamų deklaracija" (9, items 3–11). `bendros-pinigines-lesos-banke-*`
  is null on all 27. `deklaracijos-forma` is null before 2007.
- `israsa-isdave` — the tax office.
- `isdavimo-data` — "Išdavimo data", ISO.

An unrecognised prompt would appear under `nezinomos-eilutes`; none does.

## Appendix: 2000 Seimas (`2000-seimo`)

The Seimas archive's candidate page carrying the 2004 Seimas content in one
document: the 2004 Seimas sections with the 1990s declaration block.

- `rawData` order: `profile` (`candidateDisplayName`, `electedNote`,
  `photoSrc`, `fields`), `candidacies` (`apygardaName`, `apygardaNumber`,
  `apygardaUrl`, `isMultiMember`, `electedNote`, `nominator`,
  `nominatorUrl`, `listNumber`, `memberParty`, `memberPartyUrl`,
  `memberListNumber`), `anketa` (`rows`: the seven Q8/Q9 questions, with
  `explanation` where a run follows; `fields`: each labelled paragraph as
  `label` and `items` of `value`/`note`), `residence`, `biography` (`text`,
  null without an "Autobiografija"), `declaration`.

### `kandidatavimas`

The 2004 Seimas shape: `roles`, `vienmandate`, `daugiamandate` (with
`koalicijosPartija`/`numerisPartijosSarase` for the Brazauskas coalition's
140 candidates), `vienmandate.kitiIskelejai`, and the results join
(`isrinktas`, `isrinktasKaip`, `rezultatuSaltinis`; no `rezultatuTuras`, one
round). No `savarankiskasKampanijosDalyvis`. Added:

- Beside `porinkiminisNumerisSarase`, `pirmumoBalsai` and
  `pirmumoBalsuSaltinis`: `partinisReitingas` (VRK's party rating) and
  `reitingoBalai` (its product with the preference votes, which the
  post-election order follows). Every list was ranked.
- `vienmandatesBalsai` on every constituency candidate: `balsadezese`,
  `pastu`, `isViso`, `procentai` (of valid ballots), `vieta` (1 = winner),
  `saltinis` (`rvapgl.htm-<district>.htm`).

### `profilis`

- `vardas-pavarde` — the heading, given name first ("Aloyzas SAKALAS").
- `pastaba` — **the card's own winner note** ("šioje apygardoje išrinktas
  Seimo nariu" / "išrinkta Seimo nare"), on 139 of the 141 members. The
  other two (Babravičius, Žukauskas) are among 32 pages archived in their
  pre-results vintage and carry an `ElectedNoteMismatch` warning;
  `kandidatavimas.isrinktas` is right either way.
- `nuotrauka` — the card's `lm…jpg`; for the 32 cards whose image was on
  lrs.lt, the URL with `photoMeta.error`; null without an image.
- `kita` — one `apygarda`/`iskele` pair per card block in card order,
  `priesrinkiminis-numeris-sarase`, and for a coalition's candidate
  `iskele-N` (the member party) and `buves-numeris-sarase`. `apygarda`
  keeps the note ("Žirmūnų (Nr. 4), šioje apygardoje išrinktas Seimo
  nariu.").

### `normalized.anketa`

In order:

- `gimimo-data` — ISO from "Gimimo data: 1951 08 09"
- `adresas` — "Gyvenamoji vieta"
- `pareiskimai` — the seven 2004 Seimas keys and `teisiniai-argumentai`
  (the run after 9.3), third-person answers, plus
  `kitos-valstybes-pilietybe-valstybe` (8.3.1 "Kurios", comma-joined:
  "KANADA, LENKIJA") and `priesaikos-uzsienio-valstybei-atsisakymas`
  (8.4.1, the "<STATE> -" prefix stripped; two records)
- `gimimo-vieta`
- `issilavinimas` — `aprasas` null; `irasai` one per "YYYY - school,
  qualification" line as `mokymo-istaigos-pavadinimas` / `specialybe` (after
  the last comma) / `baigimo-metai`
- `mokslo-laipsnis`, `pedagoginis-vardas`, `uzsienio-kalbos` (list)
- `anksciau-isrinktas` — `irasai` of `institucijos-pavadinimas-pareigos`,
  `laikotarpis` null
- `pagrindine-darboviete`, `visuomenine-veikla`, `pomegiai`,
  `seimine-padetis`, `sutuoktinio-vardas-pavarde`,
  `vaiku-vardai-pavardes`, `seimos-nariai` (`vardas`, `rysys`)

No `tautybe`, `politine-organizacija` or `kita-apie-save`. An unprinted field
is null (or `[]`).

### `turto-ir-pajamu-deklaracijos`

The Seimas archive block (summed `turtas-ir-pinigines-lesos-*` totals,
modern split keys null, rows 1 and 20 of section III with the same guard,
tax lines, family counts, `israso-data`, `israsa-isdave`, `valiuta` "Lt"),
with figures to the centas and section I's workplace lines: `darboviete`,
`pareigos`, and where filled `nepagrindines-darbovietes`,
`pareigos-nepagrindinese-darbovietese`.

## Appendix: 2000 municipal general (`2000-kovo-19-savivaldybiu-tarybu`)

The 2000 Seimas document for the municipal form, on the 1997 municipal
archive's listing. Three sections: `profilis`, `anketa`,
`turto-ir-pajamu-deklaracijos`. `candidateId` is `<name-slug>-<vrk id>`.

- `rawData` order: `profile` (`candidateDisplayName`, empty `electedNote`
  and `photoSrc`, `fields`), `candidacy` (`municipalityName`,
  `municipalityNumber`, `municipalityUrl`, `listName` (genitive),
  `listUrl`, `listPosition`, `memberParty`, `memberListNumber`), `anketa`
  (`rows`: the five unnumbered questions as `prompt`/`key`/`answer`;
  `fields`), `residence`, `declaration`.

### `kandidatavimas`

`vrkCandidateId`, `savivaldybe` ("Vilniaus miesto"), `savivaldybesNumeris`,
`savivaldybesId` (VRK's id), `roles` (`["tarybos-narys"]`), and
`tarybosNarys`: `partyList`, `listKind` (`partija`/`koalicija`),
`listNumber`, `sarasoId`, `listPosition`, `vrkSprendimas` (the registration
decision, "2000 01 21, Nr.13"; null for a coalition), for a coalition
`koalicijosPartijos` (members) plus the card's `koalicijosPartija` and
`numerisPartijosSarase`; and the list's result — `sarasoBalsai`,
`sarasoMandatai` (0 for "-"), `sarasoRezultatuSaltinis`.

Results: `isrinktas`, `isrinktasKaip` (`tarybos-narys`),
`rezultatuSaltinis`, and for ranked candidates
`porinkiminisNumerisSarase`, `pirmumoBalsai`, `pirmumoBalsuSaltinis`.
**Five municipalities — Jurbarko, Kelmės, Radviliškio, Raseinių and
Vilkaviškio rajono, 806 candidates — have list results only:** `isrinktas`
is **null** (unknown), no rank or votes, and `rezultataiNeskelbiami`
(`priezastis`, `nariuPuslapis`).

### `profilis`

`vardas-pavarde` (given name first), `pastaba` and `nuotrauka` always null,
`kita`: `apygarda` (municipality and number), `sarasas` (genitive, linking
the list page), `priesrinkiminis-numeris-sarase`, and for a coalition's
candidate `iskele` (member party) and `buves-numeris-sarase`.

### `normalized.anketa`

In order: `gimimo-data`, `adresas`, `pareiskimai`
(`ar-nebaigta-teismo-paskirta-bausme`, `ar-atliekate-karo-tarnyba`,
`ar-turite-kitos-valstybes-pilietybe`, `kitos-valstybes-pilietybe-valstybe`,
`ar-bendradarbiavote-su-uzsienio-tarnybomis`, `ar-buvote-pripazintas-kaltu`,
`teisiniai-argumentai`; no 8.4 or 9.3), `gimimo-vieta`, `issilavinimas`
(`aprasas` the level, `irasai` empty), `mokslo-laipsnis`,
`pedagoginis-vardas`, `uzsienio-kalbos`, `anksciau-isrinktas`,
`pagrindine-darboviete`, `visuomenine-veikla`, `seimine-padetis`,
`sutuoktinio-vardas-pavarde`, `vaiku-vardai-pavardes`, `seimos-nariai`,
`kita-apie-save`.

The card prints the family inside the marital-status paragraph
("Šeimyninė padėtis: **Vedęs** Šeimos nariai: **Laima** -
sutuoktinis/sutuoktinė **Inga** - vaikas…"); it is split into the family
keys (7,579 of 9,879 records; relations `vaikas`,
`sutuoktinis/sutuoktinė`, `augintinis (ė)`, `anūkas (ė)`), so
`seimine-padetis` holds only the status. No hobbies key.

### `turto-ir-pajamu-deklaracijos`

As 2000 Seimas.

## Appendix: 2002 municipal general (`2002-gruodzio-22-savivaldybiu-tarybu`)

Two text pages per candidate on the 2002 LRS-ITD template: the anketa and
the declaration extract. Three sections: `profilis`, `anketa`,
`turto-ir-pajamu-deklaracijos`. `candidateId` is `<name-slug>-<asm_kod>`.

- `rawData` order: `profile` (`candidateDisplayName` from the `<h2>`;
  `electedNote`, `photoSrc` and `fields` empty), `anketa.rows` (numbered
  lines as `questionNumber`/`prompt`/`answer`; Q15's mandate lines as
  `records` of `nuo`/`iki`/`institucija`; "Sutuoktinio vardas:" and "Vaikų
  vardai:" as their own rows), `deklaracija` (`items` of `prompt` and
  `value`, two-figure items with `periods.pradzioje`/`pabaigoje`).

### `kandidatavimas`

`vrkCandidateId` (the `asm_kod`), `savivaldybe`, `savivaldybesNumeris`,
`apygardosId`, `roles` (`["tarybos-narys"]`), and `tarybosNarys`:
`partyList`, `listKind` (`partija`/`koalicija`), `listNumber` (constant
across municipalities), `listPosition`, for a coalition
`koalicijosPartijos` and `koalicijosPartija`; then `sarasoBalsai`,
`sarasoMandatai` (0 for "-"), `sarasoRezultatuSaltinis`.

Results: `isrinktas`, `isrinktasKaip` (`tarybos-narys`),
`rezultatuSaltinis` (the `rikl` page), and for all 10,139
`porinkiminisNumerisSarase`, `pirmumoBalsai`, `pirmumoBalsuSaltinis`.
From the council composition (`savtaryb` page, the council **as frozen**):
`tarybosNarysNuo` (ISO; 2002-12-22 for a member since the election, later
for a substitute — on an `isrinktas: false` record the seat came mid-term)
and `tarybosSudetiesSaltinis`. An elected member with no `tarybosNarysNuo`
left before the page was frozen (562 of 1,560).

### `normalized.anketa`

In order: `gimimo-data` (printed ISO), `adresas`, `pareiskimai`
(`ar-nebaigta-teismo-paskirta-bausme`, `ar-atliekate-karo-tarnyba`,
`ar-turite-kitos-valstybes-pilietybe`, `ar-buvote-pripazintas-kaltu` (88
str. 1 d.), `teisiniai-argumentai` — the blockquote after a "Taip", 27
pages), `gimimo-vieta`, `tautybe`, `issilavinimas` (`aprasas` the level,
`irasai` empty), `uzsienio-kalbos`, `anksciau-isrinktas` (`aprasas` the
inline "Nebuvo"; `irasai` one per mandate line,
`institucijos-pavadinimas-pareigos` and `laikotarpis` "1997–2000",
duplicates included), `pagrindine-darboviete`, `visuomenine-veikla`,
`pomegiai` (an unanswered question is omitted; Q18 survives on one page),
`seimine-padetis`, `sutuoktinio-vardas-pavarde` (first name only),
`vaiku-vardai-pavardes`.

### `turto-ir-pajamu-deklaracijos`

Summary lines in litas (`valiuta: "Lt"`), matched on wording (numbering
differs between the 11- and 12-item variants). Corpus keys filled:
`gautos-pajamos`, `sumoketas-pajamu-mokestis`, `suteiktos-paskolos`,
`gautos-paskolos`, `pinigines-lesos` (item 8's end figure), `darboviete`.
Assets and securities are summed (III S1 + IV S1), so
`privalomas-registruoti-turtas` and
`vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai` are null; era
keys: `turtas-ir-vertybiniai-popieriai-laikotarpio-pradzioje`/`-pabaigoje`,
`pinigines-lesos-laikotarpio-pradzioje`/`-pabaigoje`,
`bendros-pinigines-lesos-banke-laikotarpio-pradzioje`/`-pabaigoje` (12-item
variant only), `grazintos-paskolos`, `pasiskolintos-ir-dovanotos-lesos`.

`deklaracijos-apimtis` is `gyventojo` on 10,135 of 10,138 records (read
from the items' "Deklaruotojo" wording) and null on three empty tables. No
`deklaracijos-forma` or `deklaracijos-metai`.

## Appendix: 2007–2014 national elections (`2007-spalio-7-seimo-dzukija`, `2008-seimo`, `2009-prezidento`, `2009-ep`, `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai`, `2011-vasario-13-seimo-marijampole`, `2012-seimo`, `2013-kovo-3-seimo-birzai-zarasai-ukmerge`, `2014-prezidento`, `2014-ep`)

The 2015-era static layout; every shape in the 2015 Seimo by-elections
appendix applies (no elected markers, linked portraits, litas with
`valiuta`/`pastaba`, the spouse block, the campaign additions). `isrinktas`
is the results join: 141 Seimas members in 2008 and 139 in 2012 (70 list,
71/69 constituency), the 2007 Dzūkija winner, the 2 + 1 by-election winners
of November 2009 and February 2011, the 3 winners of 2013, 12 MEPs in 2009
and 11 in 2014, the two presidents. The 2014 presidential election inserts
`patiketiniai` between `privaciu-interesu-deklaracija` and the campaign
section.

### `kandidatavimas` (2007, 2008, 2012, 2013, the 2009 and 2011 by-elections, 2009 and 2014 EP)

```json
{
  "vrkCandidateId": "66814",
  "roles": ["daugiamandate", "vienmandate"],
  "vienmandate": {"apygarda": "Vilkaviškio", "apygardosNumeris": 68, "apygardosId": "7277", "iskele": "Lietuvos socialdemokratų partija"},
  "daugiamandate": {"sarasas": "Lietuvos socialdemokratų partija", "sarasoNumeris": 8, "sarasoId": "4136-1", "numerisSarase": 1},
  "isrinktas": true,
  "isrinktasKaip": "vienmandate",
  "rezultatuSaltinis": "https://www.vrk.lt/statiniai/puslapiai/2012_seimo_rinkimai/output_lt/rinkimu_diena/isrinkti_seimo_nariai_kadencijaik.html"
}
```

- `roles` is in first-seen order (lists first). 2013 has `vienmandate`
  only, EP `daugiamandate` only; the other slot is null. 2012: 929 dual,
  949 list-only, 49 constituency-only.
- `vienmandate.iskele` is the listing's "Iškėlė" column verbatim: a party,
  `Išsikėlė pats`, or both (`"…demokratai, išsikėlė pats"`).
- 2012 coalition-list candidates carry `daugiamandate.koalicijosPartija`.
- `sarasoId` is the list page's `RinkimuOrganizacija` id (2012 adds the
  `_1`/`_2` suffix, `"4136-1"`). `numerisSarase` is null for six 2012 rows
  printed without a position.
- The presidential elections get the minimal results-join block.

### `profilis.kita` per election

- **2012 Seimo** — one `apygarda`/`iskele` pair per candidacy in card order:
  constituency first (`apygarda` = `"Vilkaviškio (Nr.68)"`), then
  `apygarda-2` = `"Daugiamandatė"`, `iskele-2`, `numeris-sarase`. Results
  links keyed by label: `daugiamandateje-apygardoje`, `i-turas`,
  `ii-turas`. Coalition nominees add `iskele-3` = `"(Iškėlė"`.
- **2007 Dzūkija** — `apygarda` ("Dzūkijos rinkimų apygarda (Nr. 69)") and
  `iskele` from the header table, `gimimo-data` (also in
  `anketa.gimimo-data`), then the campaign link or, for six represented
  candidates, a valueless
  `kandidatas-nera-savarankiskas-politines-kampanijos-dalyvis`, and
  `i-turas`/`ii-turas`.
- **2008 Seimo** — as 2012, but no campaign link.
- **2013** — `apygarda`, `iskele`, the campaign link, `i-turas`, and
  `ii-turas` for six candidates.
- **2009 and 2011 by-elections** — `apygarda`, `iskele`, the campaign link.
- **2014 presidential** — the campaign link only (path `423_lt`, not the
  candidate pages' `424_lt`).
- **2009 presidential** — the campaign link (`403_lt`) and, for five of
  seven, the campaign website keyed by its text
  (`www-grybauskaite2009-lt`: `pavadinimas` the text, `reiksme` null,
  `nuorodos` the URL).
- **2014 EP** — `iskele`, `numeris-sarase`, the campaign link; the
  coalition nominee adds `iskele-2`/`numeris-sarase-2`.
- **2009 EP** — `iskele`, `numeris-sarase`, the campaign link (the party's
  participant page, shared by the list).

### `normalized.anketa` per election type

- **Seimo (2007, 2008, 2012, 2013, the 2009/2011 by-elections)** — the 2015
  Seimo key set plus `pareiskimai.ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo`
  (Q9.3). Every 2013 form holds `Nenurodė` there (null). Sparse forms omit
  unanswered lines (Q12–Q15 can be absent). 2012 also reads
  `pareiskimai.teisiniai-argumentai` (24 candidates); null on every 2013
  record.
- **Presidential (2014)** — `pareiskimai`: `ar-esate-pilietis-pagal-kilme`,
  `ar-gyvenate-lietuvoje-trejus-metus`, `ar-galite-buti-renkamas-seimo-nariu`,
  `ar-nebaigta-teismo-paskirta-bausme`, `ar-atliekate-karo-tarnyba`,
  `ar-turite-kitos-valstybes-pilietybe`,
  `ar-susijes-priesaika-uzsienio-valstybei`. Birthplace, nationality and
  education are Q9–Q11; `pedagoginis-vardas` is the combined academic-title
  line; no `anksciau-isrinktas`.
- **European Parliament (2014)** — `gimimo-data` is Q3. `pareiskimai` adds
  `kitos-valstybes-pilietybe-valstybe` (Q8.3.1),
  `ar-atimta-balsavimo-teise-kitoje-valstybeje` (Q8.3.2) and
  `ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo` (Q9.3); no
  `kita-apie-save`.
- **European Parliament (2009)** — the 2014 EP set with `gimimo-data` at
  Q5, plus `mokslo-laipsnis` and `pedagoginis-vardas` (one line),
  `kita-apie-save` (Q21) and `pareiskimai.teisiniai-argumentai`.
- **Presidential (2009)** — `pareiskimai`:
  `ar-nebaigta-teismo-paskirta-bausme`, `ar-atliekate-karo-tarnyba`,
  `ar-turite-kitos-valstybes-pilietybe`,
  `ar-susijes-priesaika-uzsienio-valstybei` (Q8.1–8.4) and
  `ar-bendradarbiavote-su-uzsienio-tarnybomis` (Q9, the lustration question
  on the NKVD/NKGB/MGB/KGB and equivalents). Birthplace, nationality and
  education are Q10–Q12; `mokslo-laipsnis` is the degree-only line after
  the education table; `anksciau-isrinktas` is Q15. An unanswered question
  is omitted, so a null is an absent row.

### `patiketiniai` (2014 presidential only)

The trustees tab: a list of `{numeris, vardas-pavarde}` (7 to 114 per
candidate); `Duomenų nėra` is an empty list. The 2009 pages link the tab but
every `Kandidato<ID>Patiketiniai.html` is a 404, so 2009 records have no
key; the link is under `unpublishedTabs` in the fixture's `index.json`.

### `privaciu-interesu-deklaracija` (2007–2009: the roman-numbered forms)

- **2007 and 2008:** `ii-turtas`, `iii-pajamos`,
  `iv-vertybiniai-popieriai`, `v-turtines-prievoles`,
  `vi-individualios-imones-kitos-organizacijos-ir-istaigos`, `ix-naryste-…`,
  `x-asmenys-del-kuriu-gali-kilti-viesuju-ir-privaciu-interesu-konfliktas`,
  after a spouse card `deklaruojanciojo-asmens-sutuoktinis-partneris`.
- **2009 (both elections):** after the declarant and spouse
  (`deklaruojancio-…`) cards, `ii-dalyvavimas-juridiniuose-asmenyse`,
  `iii-individuali-veikla`,
  `iv-naryste-pareigos-imonese-istaigose-asociacijose-ar-fonduose`,
  `v-gautos-dovanos`, `vii-sandoriai`,
  `viii-fiziniai-ar-juridiniai-asmenys-del-kuriu-gali-kilti-interesu-konfliktas`
  (the presidential seven use II, IV and VII only). Transactions and gifts
  carry `sandorio-vertes-litais-kodas` (`"001"`–`"012"`); `suma-skaiciais`
  and `suma-zodziais` are blank.

Each section is present only when filed and is a **list of records** keyed
by its column names (`ii-turtas`: `tipas`, `vienetu-skaicius`,
`vietoves-pavadinimas`, `isigijimo-budas`; `iii-pajamos`: `tipas`,
`pajamu-saltinio-pavadinimas`).

### Declarations

The shared value keys plus `valiuta: "Lt"`. `pastaba` names the period on
the 2012 and 2013 pages ("nuo 2011-01-01 iki 2011-12-31"; 2013 reused the
2012 declarations) and is null on 2009 and 2014. Income forms, all resolving
to `gautos-pajamos`/`sumoketas-pajamu-mokestis`:

- 2012–2014: "GPM308 formos 12, 13, 13A, 14, 20 laukelių … V13 laukelių
  suma" (2015 Seimo: "…14, 22 … V13 laukelio")
- 2009 and the 2015 municipal family: **GPM305** ("GPM305 formos 12, 13, 14
  ir GPM305V formos V14 laukelių suma" / "…27,28,30 laukelių suma")
- 2007: **GPM302** ("12, 13, 14 ir 15 laukelių bei GPM302V priedo V14
  laukelio suma" / "Išskaičiuota mokesčio suma (36 laukelio suma)")

### Campaign pages (2009)

- 2008 records have no campaign section (no participant link).
- 2007 links one for the four independent candidates; the six represented
  ones link nothing.
- 2009 (both elections): in the EP election the participant is the party,
  so a list shares one campaign record (24 candidates on one). The donor
  list is one "Aukotojų sąrašas" section
  (`aukos-pagal-sekcija.aukotoju-sarasas`: `rowNumber`, `donor`,
  `municipality`, `amountLt`, `date`); an unacceptable donation is flagged
  after the donor's name (", nepriimtina auka" and variants) and moved to
  `notes`. Financing reports carry `reportType` ("Pradinė"/"Galutinė") and a
  null `status`. A company auditor's "Pavadinimas"/"Kodas" become
  `imones-pavadinimas`/`imones-kodas`. No contracts.

Totals (`suvestine`) are keyed by the table's amount columns: `amountLt` on
2009–2014, both on March 2015, `amountEur` on later 2015.

### Sitemap cross-checks (`sitemaps/2012-seimo.json`, `sitemaps/2008-seimo.json`)

The sitemap `stats` (2008 in parentheses where different):

- `listCandidacies` = `declaredListCandidates` (1,878; 2008: 1,583) and
  `listCountMismatches` = 0.
- `listDistrictJoinMismatch` = 0; `listRowsWithoutDistrictColumn` = 135
  (2008: 130) is the coalition list page.
- `districtOnlyReconciled`: `sidePageDistrictOnlyIds` (52) −
  `sidePageIdsAlsoOnLists` (3) = `districtOnlyCandidates` (49).
  `sidePageDistrictOnlyDeclared` (58) is the index's figure and does not
  match (withdrawn candidates stay in the count). 2008 has no
  self-nominated page, so `selfNominatedNotOnSidePages` (15) counts the
  constituency pages' "Išsikėlė pats" rows; 0 for 2012.

### Ids

Name slugs with a positional `-2` suffix for collisions: two in 2008 (Arūnas
RIMKUS; Algis KAŠĖTA), one in 2012 (Arūnas MARKŪNAS). Traversal order —
lists, then constituencies, each in index order — is stable.
