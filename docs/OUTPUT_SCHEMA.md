# Output Schema

This document is the record contract for the whole corpus. The body describes
the common record envelope and the shared normalized shapes that hold across
all twenty elections; one appendix per election covers everything
election-specific, and the per-election appendices remain authoritative for
those specifics. The body sections were written against the founding module:

```bash
python -m scraper parse-anketa-samples 2016-seimo
```

Every election has its own scraper module because the HTML differs, so
question numbering, key sets and section internals vary by election — read
the appendix. The top-level record fields, the `normalized` section names and
the shapes under "Shared normalized shapes" below are the cross-election
contract `docs/DATASET.md` refers to.

Records are written as:

- `data/2016-seimo/<candidate-id>-2016-seimo.json`

## Top-Level Record

Each record contains:

- `electionId`
- `candidateId`
- `candidateName`
- `source`
- `rawData`
- `normalized`

`source` currently includes:

- `candidateSourceUrl`

## `rawData`

`rawData` stores source-close parsed payloads from saved HTML.

Expected section order in current implementation:

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
- `photoSrc` — a VRK URL (2020+ page eras) or, for the eras whose pages embed
  the portrait as a base64 data URI, the relative sidecar path
  `photos/<candidateId>.<ext>` written beside the records; `photoMeta`
  (`mime`, `bytes`, `sha256`) then identifies the file against the bytes VRK
  served. `normalized.profilis.nuotrauka` carries the same reference.
- `fields[]` where each item contains:
  - `key`
  - `displayValue`
  - `urls[]`

### `rawData.anketa`

- `rows[]`
- Each row contains:
  - `rowIndex`
  - `questionNumber` (can be null)
  - `prompt`
  - `answer` (string or structured list for table rows)

### Other raw sections

- `biografija`:
  - 2016: source-close biography payload
  - 2020 (reference only, different election parser): simplified `rows[]` (anketa-like) where each row contains `rowIndex`, `questionNumber`, `prompt`, `answer`
    - scalar rows: `answer` is string
    - table rows (for education/work history): `answer` is a list of row objects
- `turtoIrPajamuDeklaracijos`: `sections[]` of `{title, items[]}`
- `privaciuInteresuDeklaracija`: `sections[]`
- `kita`: free text and links payload
- `politinesKampanijosDalyvioDuomenys` (optional): campaign list with shared metadata and tab-specific data payloads

## `normalized`

`normalized` stores analysis-ready structures.

Expected section order in current implementation:

1. `profilis`
2. `anketa`
3. `biografija`
4. `turto-ir-pajamu-deklaracijos`
5. `privaciu-interesu-deklaracija`
6. `politines-kampanijos-dalyvio-duomenys` (optional)
7. `kita`

Notes:

- Keys are source-close and often Lithuanian.
- Section order is fixed, but a section can be absent when the source page
  never published its tab: `gintaras-binkauskas-2016-seimo` has no
  `biografija`, and `jonas-korsakas-2020-seimo` has neither `biografija` nor
  `turto-ir-pajamu-deklaracijos`. Those are the only two such records in the
  corpus, but a consumer parser should treat every section as optional rather
  than crash on the promised order.
- Exactly three placeholder strings normalize to null: `Nenurodė`, `-` and the
  empty string. Candidate-typed "none" variants survive verbatim by design —
  an answered "none" is an answer, not an unanswered field. The variants that
  survive: the `Nėra` case/diacritic family (`Nėra`/`nėra`/`NĖRA`/`nera`/
  `Nera`/`NERA`, 1,942 values corpus-wide), `Nenurodyta` (35), `Nenurodoma`
  (1), `Nenurodė.` (2, trailing dot), plus `--`, `.`, `–` and `N/A`.
- Campaign section is omitted when candidate has no campaign participant tab.
- A candidate nominated by more than one nominator has each extra nominator on
  its own profile row with an empty label cell. Those rows are folded into the
  field above them, so `profilis.kita.iskele.reiksme` reads
  `"Party A; Party B"`. Kept separate they would be dropped, because a field
  without a key cannot be normalized.
- Free-text declaration sections — `ID001A KITI DUOMENYS` on the 2016-era
  pages — publish an unlabelled sentence as the only row of a single-column
  table, so they normalize to a `tekstas` key inside the section object
  (`privaciu-interesu-deklaracija.id001a.tekstas`). Every election sharing the
  2016-era private-interest parser behaves the same, 2020 Seimo and the
  2018–2019 Seimo by-elections included.
- Donation sections under `politines-kampanijos-dalyvio-duomenys[].aukos-pagal-sekcija`
  carry `totals` plus a `records[]` list. Every record has the same keys —
  `rowNumber`, `donor`, `municipality`, `date`, `incomeSourceCode`, `amount`,
  `notes` — regardless of election. VRK publishes these tables in several
  widths (the 2016 pages carry all seven columns; later pages drop the
  municipality column, the income-source column, or both, and some rename
  "Pastabos" to "VRK sprendimas, pastabos"), so columns are matched by heading
  and any column the page omits is null.
- Biography in 2020 is intentionally simplified: no raw `text`/`html` and no section-kind wrappers; normalized 2020 biography no longer stores `tekstas`/`sekcijos`.

### `normalized.anketa` (2016)

The 2016 questionnaire is the largest of the elections: the biography questions
are part of the anketa itself rather than a separate tab, so this section
carries them.

- `gimimo-data` (Q5), `adresas` (Q6)
- `pareiskimai` — the Seimo rinkimų įstatymo 38 str. 4 d. declarations
  (Q8.1–Q8.4) and the 98 str. 1 ir 3 d. ones (Q9.1, Q9.2, Q9.3.1–Q9.3.3), plus
  `teisiniai-argumentai` (Q9.3.4), the free-text justification filled only when
  Q9.2 is answered "Taip"
- `gimimo-vieta` (Q10), `tautybe` (Q11), `issilavinimas` (Q12, `aprasas` plus an
  `irasai` record table), `uzsienio-kalbos` (Q13, split into a list),
  `politine-organizacija` (Q14), `anksciau-isrinktas` (Q15, same
  `aprasas`/`irasai` shape), `pagrindine-darboviete` (Q16),
  `visuomenine-veikla` (Q17), `pomegiai` (Q18), `seimine-padetis` (Q19),
  `vaiku-vardai-pavardes` (Q20), `kita-apie-save` (Q21)
- `pedagoginis-vardas` and `sutuoktinio-vardas-pavarde` are rendered as rows
  without a question number, so they are matched on their prompt text
  ("Jei turite, nurodykite pedagoginį vardą…", "vyro arba žmonos vardas…")
- the `issilavinimas` and `anksciau-isrinktas` record tables are rendered either
  inside their question's row or in the row right after it, depending on the
  candidate, and both placements are collected. This shape is shared with
  `2019-ep`, `2019-prezidento` and the 2017 elections.

Unanswered optional questions are published as `Nenurodė` and normalize to null.

## Anomalies JSONL

Parser runs also produce anomalies JSONL (default path `data/2016-seimo/anomalies.jsonl`).

Each event row includes:

- `timestamp`
- `eventType`
- `severity`
- `stage`
- `electionId`
- `candidateId`
- `sourceUrl`
- `detail` (free-form object)

See also:

- `docs/ANOMALY_DETECTION.md`

## Shared normalized shapes

These shapes are verified identical across all twenty elections; the
appendices never need to restate them.

### `turto-ir-pajamu-deklaracijos`

The "seven canonical keys" the appendices refer to are:

- `privalomas-registruoti-turtas`
- `vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai`
- `pinigines-lesos`
- `suteiktos-paskolos`
- `gautos-paskolos`
- `gautos-pajamos`
- `sumoketas-pajamu-mokestis`

The key set is identical in 20/20 elections at 100% presence. Values are
parsed EUR amounts as JSON numbers (int or float), never strings — and null
when the source renders the figure malformed (VRK publishes a handful of
incomes with the integer part missing, e.g. `,35 EUR`; inventing `0.35` would
be making up a figure, so those normalize to null with the source text kept
in `rawData`).

### `profilis` and `kita`

`profilis` has the same four keys everywhere: `vardas-pavarde`, `pastaba`,
`nuotrauka`, `kita`. Every entry under `profilis.kita` is
`{pavadinimas, reiksme, nuorodos}`. `normalized.kita` is
`{tekstai, nuorodos}` in every election.

A label that recurs on one profile card keeps its first value under the
plain key and lands the later ones under `-2`, `-3` suffixes (`iskele`,
`iskele-2`). Two shapes produce this: the 2012 Seimo cards, which carry one
`Apygarda`/`Iškėlė` pair per candidacy, and coalition nominees in any
2011–2015 election, whose card repeats `Iškėlė` for the member party in
parentheses (the suffixed entry's `pavadinimas` is then the literal
`"(Iškėlė"`). Measured over the whole corpus when the rule was introduced
(2026-08-21), exactly one pre-existing record had a recurring label.

### Elected status in the 2012–2015 family (`kandidatavimas.isrinktas`)

No page of the 2007–2015 static layout marks a winner, so `profilis.pastaba`
is null on every record of those eighteen elections (the 2007 and 2011
municipal generals included), winners included. Their
electedness is **joined in from VRK's results trees** at parse time
(`python -m scraper build-results <id>` writes
`sitemaps/<id>.results.json`; `scraper/shared/election_results.py` documents
every source page and how each winner is resolved to a VRK candidate id) and
lands in `kandidatavimas`:

- `isrinktas` — `true` / `false` when a results file exists for the election
  (a false is then a real statement: the results pages name every winner,
  and this candidate is not among them); `null` only when no results file
  has been built, meaning unknown.
- `isrinktasKaip` — the seat: `vienmandate`, `daugiamandate` (Seimas / EP
  list), `prezidentas`, `meras`, `tarybos-narys`.
- `rezultatuSaltinis` — the results page the seat was read from;
  `rezultatuTuras` (1 or 2) where the page belongs to a round.
- `rezultataiPanaikinti` — present, naming the VRK decision, on the 48
  March 2015 council winners in Šilutė and Trakai whose results VRK declared
  void before anyone was seated; their `isrinktas` is `false`, and the June
  repeat elections' records carry the seats actually won.

Elections without a listing-derived `kandidatavimas` block (the 2014
presidential election, the 2015 Seimo by-elections, Telšiai) get a minimal
one — `vrkCandidateId` plus the keys above — from the join alone.

The person index and the inventory count a candidacy as won when
`profilis.pastaba` starts with `Išrink` **or** `kandidatavimas.isrinktas` is
`true`; see `docs/DATA_GUIDE.md`.

### Campaign entries

Every entry of `politines-kampanijos-dalyvio-duomenys[]` has the same ten
keys in all elections that publish campaigns: `statusas`,
`registravimo-data`, `sprendimo-numeris`, `kontaktai`, `izdininkas`,
`auditorius`, `aukos-pagal-sekcija`, `finansavimo-ataskaitos`, `sutartys`,
`sprendimai`. The 2015 era adds to (never replaces) that set — see the
`2015-kovo-1-seimo-zirmunai` appendix.

### The two `privaciu-interesu-deklaracija` families

Declaration sections are keyed two different ways depending on the page era:

- **Form-id sections** (`id001j`, `id001s`, `id001i`, `id001a`, `id001f`,
  `id001p`, …) on the 2016/2019-era pages: 2016 Seimo, the 2015 and 2017–2019
  Seimo by-elections, both 2017 mayoral elections, 2019 EP, 2019 presidential,
  the 2019 municipal general election and 2020 Seimo.
- **Slugged sections** (`deklaruojancio-darbovietes`, `sutuoktinio-darbovietes`,
  `rysiai-su-juridiniais-asmenimis`, `rysiai-sudarius-sandorius`,
  `kiti-duomenys`, …) on the 2021+ pages.

The concept pairs across the split are `id001j` ≈
`rysiai-su-juridiniais-asmenimis`, `id001s` ≈ `rysiai-sudarius-sandorius`
and `id001a` ≈ `kiti-duomenys`.

Within the form-id family the spouse block
(`deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris`) is dropped by
four elections — `2016-seimo` (0/1,415 records),
`2017-balandzio-23-seimo-anyksciai-panevezys` (0/11),
`2018-rugsejo-16-seimo-zanavykai` (0/6) and `2019-rugsejo-8-seimo` (0/27) —
and retained by the rest of the family (2020 Seimo carries it on
1,754/1,754 records; in 2019 EP and the 2019 municipal election it is absent
only from candidates who filed no declaration at all).

## Appendix: 2019 European Parliament (`2019-ep`)

The EP module is a separate parser but is intentionally kept schema-parallel to
2016 Seimo. Records are written as `data/2019-ep/<candidate-id>-2019-ep.json`
with the same top-level fields and the same `normalized` section order
(`profilis`, `anketa`, `biografija`, `turto-ir-pajamu-deklaracijos`,
`privaciu-interesu-deklaracija`, optional `politines-kampanijos-dalyvio-duomenys`,
`kita`).

EP-specific notes:

- The candidate anketa is rendered as several sibling tables rather than one
  table; the parser stitches them back into a single `anketa.rows` list and
  attaches standalone record tables (education for Q12, prior mandates for Q15)
  to the heading row that precedes them.
- `normalized.anketa.pareiskimai` carries the EP declaration questions
  (`8.1`–`8.3`, `9.1`–`9.5`); there is no `8.4`/`teisiniai-argumentai` field.
- `normalized.anketa` adds `mokslo-laipsnis` (Q12.1) and keeps
  `pedagoginis-vardas` (Q12.2). Marital status and spouse are split from the
  single Q19 row into `seimine-padetis` and `sutuoktinio-vardas-pavarde`.
- `biografija` is free text (`{"tekstas": ...}`), like 2016 Seimo.
- `profilis.pastaba` holds the "elected" note, present only for elected MEPs.
- `privaciu-interesu-deklaracija` hoists the declarant to `deklaruojantis-asmuo`
  and keys each declaration table by its section id (`id001j`, `id001s`,
  `id001i`, `id001a`, `id001f`, `id001p`, …). Following the 2020 model, the
  spouse block is retained under
  `deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris` rather than dropped.
  Candidates who filed no declaration yield an empty object.

## Appendix: 2024 European Parliament (`2024-ep`)

Records are written as `data/2024-ep/<candidate-id>-2024-ep.json` with the same
top-level fields. Candidate pages carry no campaign tab (campaigns were run by
the party lists), so the `normalized` section order is `profilis`, `anketa`,
`biografija`, `turto-ir-pajamu-deklaracijos`, `privaciu-interesu-deklaracija`,
`kita`.

2024 EP-specific notes:

- `normalized.anketa` follows the 2024 question numbering: `adresas` (Q6),
  `einamos-pareigos` (Q7), and `narystes-politinese-organizacijose.irasai`
  (the Q8 membership table, rendered in its own row after the heading).
- `normalized.anketa.pareiskimai` carries the Rinkimų kodekso 76 str.
  declarations (Q9–Q16, including the `13.5`–`13.7` sub-questions).
- `teistumo-detales` holds the conditional Q13.1–Q13.4 conviction details
  (only filled when Q13 is "Taip"); each conviction table is folded into one
  record under `nusikalstamos-veikos.irasai`. `mandato-netekimo-detales`
  holds the conditional Q14.1 answer.
- `biografija` is a structured questionnaire (unlike the 2019 free text):
  `gimimo-data`/`gimimo-vieta` (Q1), `issilavinimas.irasai` (Q2),
  `mokslo-laipsnis` (Q2.1), `pedagoginis-vardas` (Q2.2), `uzsienio-kalbos`
  (Q3), `darbo-patirtis.irasai` (Q4), `visuomenine-veikla` (Q5), `pomegiai`
  (Q6), `seimine-padetis` (Q7).
- `turto-ir-pajamu-deklaracijos` keeps the seven canonical keys shared with
  the other elections; the full GPM311 income breakdown stays in `rawData`.
- `privaciu-interesu-deklaracija` merges the leading summary table to the top
  level (`pateikimo-data`, `deklaruojantis-asmuo`,
  `sutuoktinis-sugyventinis-ar-partneris`) and keys each `h4` section by its
  slugified title (`deklaruojancio-darbovietes`, `sutuoktinio-darbovietes`,
  `rysiai-su-juridiniais-asmenimis`, `rysiai-sudarius-sandorius`, …), each a
  list of records. The `kiti-duomenys` section is free text published without
  a label, so it lands under a `tekstas` key inside the record.
- `profilis.nuotrauka` is a URL to the candidate photo (`kandImg/...`), not a
  base64 data URI as in 2019.

## Appendix: 2019 Presidential (`2019-prezidento`)

Records are written as `data/2019-prezidento/<candidate-id>-2019-prezidento.json`
with the same top-level fields. The candidate pages share the 2019 template
family, so this module is kept schema-parallel to 2019 EP. The `normalized`
section order is `profilis`, `anketa`, `biografija`,
`turto-ir-pajamu-deklaracijos`, `privaciu-interesu-deklaracija`, `patiketiniai`,
`politines-kampanijos-dalyvio-duomenys`, `kita`.

2019 presidential-specific notes:

- `profilis.pastaba` holds the participation/elected status line for **every**
  candidate, not only the winner: `Išrinktas II ture` (elected), `Dalyvavo II
  ture` (reached the run-off), or `Dalyvavo I ture` (first round only).
- `normalized.anketa` mirrors 2019 EP: free-text `biografija`, the Q12
  `issilavinimas.irasai` education table, `mokslo-laipsnis` (Q12.1),
  `pedagoginis-vardas` (Q12.2), the Q15 `anksciau-isrinktas` block, and the
  Q19 split into `seimine-padetis` and `sutuoktinio-vardas-pavarde`.
- `normalized.anketa.pareiskimai` carries the presidential eligibility
  questions under the Prezidento rinkimų įstatymas: citizenship by origin and
  residency (`8.1`, `8.2`), the Seimas-eligibility sub-questions (`8.3.1`–
  `8.3.4`), and the other-citizenship questions (`9.1`–`9.3`).
- `patiketiniai` is the presidential-only "Patikėtiniai" (trustees) tab,
  normalized to a list of text entries. It is empty for every 2019 candidate
  but is captured and parsed defensively.
- `turto-ir-pajamu-deklaracijos` keeps the seven canonical keys shared with the
  other elections; the full GPM308 income breakdown stays in `rawData`.
- `privaciu-interesu-deklaracija` follows the 2019 EP shape: the declarant is
  hoisted to `deklaruojantis-asmuo`, the spouse block is retained under
  `deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris`, and each
  declaration section is keyed by its id (`id001j`, `id001s`, `id001i`,
  `id001a`, `id001f`, …).
- `profilis.nuotrauka` is a base64 data URI, as in 2019 EP.

## Appendix: 2024 Presidential (`2024-prezidento`)

Records are written as `data/2024-prezidento/<candidate-id>-2024-prezidento.json`
with the same top-level fields. Candidate pages share the 2024-era layout and the
five-tab set of `2024-ep` — there is no trustees tab and no campaign tab (unlike
`2019-prezidento`), so the `normalized` section order is `profilis`, `anketa`,
`biografija`, `turto-ir-pajamu-deklaracijos`, `privaciu-interesu-deklaracija`,
`kita`.

2024 presidential-specific notes:

- `profilis.pastaba` holds the run-off / elected status line for **every**
  candidate: `Išrinktas II ture` (elected), `Dalyvavo II ture` (reached the
  run-off), or `Dalyvavo I ture` (first round only). The nomination line is
  captured under `profilis.kita.kandidata-iskele` (e.g. `išsikėlė pats` for a
  self-nominated candidate, or the nominating party name).
- `profilis.nuotrauka` is a URL to the candidate photo (`kandImg/...`), as in
  2024 EP.
- `normalized.anketa` follows the 2024 question numbering: `adresas` (Q6),
  `einamos-pareigos` (Q7), and `narystes-politinese-organizacijose.irasai`
  (the Q8 membership table). Candidates who declare no membership answer Q8 with
  inline text, yielding an empty `irasai`.
- `normalized.anketa.pareiskimai` carries the Rinkimų kodekso 76 str.
  declarations. Q9–Q14 (including the `13.5`–`13.7` sub-questions) share their
  wording — and keys — with the 2024 EP module. Q15–Q18 are the presidential
  eligibility questions and diverge from EP:
  `ar-esate-ar-buvote-kitos-valstybes-pilietis` (Q15),
  `ar-susijes-priesaika-uzsienio-valstybei` (Q16),
  `ar-esate-pilietis-pagal-kilme` (Q17), and
  `ar-gyvenate-lietuvoje-trejus-metus` (Q18).
- `teistumo-detales` holds the conditional Q13.1–Q13.4 conviction details and
  `mandato-netekimo-detales` the conditional Q14.1 answer. No 2024 presidential
  candidate answered Q13/Q14 "Taip", so these are null/empty in practice but are
  parsed defensively.
- `biografija` is the same structured questionnaire as 2024 EP:
  `gimimo-data`/`gimimo-vieta` (Q1), `issilavinimas.irasai` (Q2),
  `mokslo-laipsnis` (Q2.1), `pedagoginis-vardas` (Q2.2), `uzsienio-kalbos`
  (Q3), `darbo-patirtis.irasai` (Q4), `visuomenine-veikla` (Q5), `pomegiai`
  (Q6), `seimine-padetis` (Q7).
- `turto-ir-pajamu-deklaracijos` keeps the seven canonical keys shared with the
  other elections; the full GPM311 income breakdown stays in `rawData`.
- `privaciu-interesu-deklaracija` merges the leading summary table to the top
  level (`pateikimo-data`, `deklaruojantis-asmuo`,
  `sutuoktinis-sugyventinis-ar-partneris`) and keys each `h4` section by its
  slugified title (`deklaruojancio-darbovietes`, `sutuoktinio-darbovietes`,
  `rysiai-su-juridiniais-asmenimis`, …), each a list of records.

## Appendix: 2020 Seimo (`2020-seimo`)

Records are written as `data/2020-seimo/<candidate-id>-2020-seimo.json`. Pages
keep the 2016-era layout, so `profilis` is read with the 2016 profile parser,
but the questionnaire is numbered for the 2020 Seimo rinkimų įstatymas and has
its own, much smaller, shape:

- `adresas` (Q6) and `kontaktai` — `telefonas` (Q6.1), `el-pastas` (Q6.2),
  `socialiniu-tinklu-paskyros` (Q6.3). The first three are usually
  `Neskelbiamas`; the social-media row carries real values.
- `einamos-pareigos` (Q7) and `narystes-politinese-organizacijose.tekstas`
  (Q7.1), which is answered inline rather than with the membership table later
  elections use.
- `pareiskimai` holds the Seimo rinkimų įstatymo 38 str. 3 d. declarations
  (Q8.1–Q8.4 plus `ar-savanoriskos-karo-tarnybos-karys` for Q8.2.1) and the
  98 str. 1 ir 3 d. declarations (Q9.1–Q9.5). Answers are worded as
  `Neturiu`/`Nesu`/`Nesu/nebuvau`/`Ne` rather than the `Taip`/`Ne` of later
  elections.

There are no birth, education, language, hobby or family questions on the 2020
anketa — those live on the biography tab and are normalized under `biografija`,
whose key set is: `gimimo-data`, `gimimo-vieta`, `tautybe`, `issilavinimas`,
`mokslo-laipsnis`, `pedagoginis-vardas`, `uzsienio-kalbos`, `darbo-patirtis`,
`visuomenine-veikla`, `pomegiai`, `seimine-padetis`,
`sutuoktinio-vardas-pavarde`, `vaiku-vardai-pavardes`, `kita-apie-save`.
`visuomenine-veikla` is the key every election uses; note the 2020 form widens
that question's wording to scientific and pedagogical activity ("mokslinė,
pedagoginė, visuomeninė veikla"), so this election's answers cover more ground
than the shared key name suggests.

Despite the pages keeping the 2016-era layout, `profilis.nuotrauka` is a URL
to the candidate photo (`kandImg/...`) on all 1,754 records — not the base64
data URI the other 2016-era-layout elections embed.

## Appendix: 2024 Seimo (`2024-seimo`)

Records are written as `data/2024-seimo/<candidate-id>-2024-seimo.json` with the
same top-level fields and the full seven-section `normalized` order (candidate
pages carry a campaign tab).

2024 Seimo-specific notes:

- `profilis.pastaba` holds the elected note, which comes in two forms:
  `Išrinktas vienmandatėje <apygarda> apygardoje II ture` for constituency
  winners and `Išrinktas pagal sąrašą` for candidates elected from a party list.
  Non-elected candidates have `null`. Constituency fields land under
  `profilis.kita`: `vienmandate-apygarda`, `iskele`, `turas`, `sarasas`,
  `numeris-sarase`, `porinkiminis-eiles-numeris`.
- `profilis.nuotrauka` is a URL to the candidate photo (`kandImg/...`).
- `normalized.anketa` uses the 2024 numbering: `adresas` (Q6),
  `einamos-pareigos` (Q7) and `narystes-politinese-organizacijose.irasai` (the
  Q8 membership table, as in 2024 EP).
- `normalized.anketa.pareiskimai` carries the Rinkimų kodekso 76 str.
  declarations Q9–Q14 under the same keys as the other 2024 modules, plus the
  Seimo eligibility questions Q15 (`ar-esate-ar-buvote-kitos-valstybes-pilietis`)
  and Q16 (`ar-susijes-priesaika-uzsienio-valstybei`).
- `teistumo-detales` and `mandato-netekimo-detales` hold the conditional
  Q13.1–Q13.4 and Q14.1 answers. No sampled candidate answered Q13/Q14 "Taip",
  so they are null/empty in practice but are parsed defensively.
- `biografija` keeps its own numbering (`issilavinimas` is Q2, `mokslo-laipsnis`
  Q2.1, `darbo-patirtis` Q4), matching 2024 EP rather than the 2023 by-elections.
- `privaciu-interesu-deklaracija` follows the 2024 EP shape, including the
  free-text `kiti-duomenys` section landing under a `tekstas` key inside the
  record.

## Appendix: 2023 Kupiškis mayor (`2023-spalio-8-kupiskio-mero`)

Records are written as
`data/2023-spalio-8-kupiskio-mero/<candidate-id>-2023-spalio-8-kupiskio-mero.json`
with the same top-level fields. Candidate pages carry the six-tab set (the five
of `2024-ep` plus a campaign tab), so the `normalized` section order is
`profilis`, `anketa`, `biografija`, `turto-ir-pajamu-deklaracijos`,
`privaciu-interesu-deklaracija`, `politines-kampanijos-dalyvio-duomenys`,
`kita`.

Election-specific notes:

- `profilis.pastaba` holds the elected note for the winner only
  (`Išrinktas Kupiškio rajono (Nr.23) savivaldybėje II ture`); the other
  candidates have `null`. The municipal profile card fields land under
  `profilis.kita`: `savivaldybe`, `iskele-i-savivaldybes-merus`, `turas`
  (`I`/`II`, the round the candidate ran in), `sarasas`, `numeris-sarase`,
  `porinkiminis-numeris-sarase`.
- `profilis.nuotrauka` is a URL to the candidate photo (`kandImg/...`), as in
  2024 EP.
- `normalized.anketa` follows the 2024 question numbering: `adresas` (Q6) and
  `einamos-pareigos` (Q7). Q8 asks for a single membership
  ("Narystė politinėje partijoje, politiniame komitete, asociacijoje") and is
  answered inline, so `narystes-politinese-organizacijose` carries both
  `tekstas` (the answer) and `irasai` (empty unless a membership table appears).
- `normalized.anketa.pareiskimai` carries the Rinkimų kodekso 76 str.
  declarations Q9–Q14 (including the `13.5`–`13.7` sub-questions) under the same
  keys as the 2024 modules. There are no further questions: the EP free-movement
  and presidential eligibility questions have no municipal counterpart. Q10–Q12
  are numbered `10 .` on these pages, so question numbers are re-derived with a
  whitespace-tolerant pattern before normalization.
- `teistumo-detales` holds the conditional Q13.1–Q13.4 conviction details and
  `mandato-netekimo-detales` the conditional Q14.1 answer. The Q13.4 detail
  table separates label from value with a plain hyphen rather than the 2024 en
  dash.
- `biografija` keeps the 2020 Seimo numbering: `gimimo-data`/`gimimo-vieta`
  (Q1), `tautybe` (Q2), `issilavinimas.irasai` (Q3), `mokslo-laipsnis` (Q3.1),
  `pedagoginis-vardas` (Q3.2), `uzsienio-kalbos` (Q4), `darbo-patirtis.irasai`
  (Q5), `visuomenine-veikla` (Q6), `pomegiai` (Q7), `seimine-padetis` (Q8).
- `turto-ir-pajamu-deklaracijos` and `privaciu-interesu-deklaracija` follow the
  2024 shapes. Their page bodies are wrapped in a `<div>` instead of following
  the tab navigation as siblings, so the module flattens the tab body before
  handing it to the shared parsers.
- `kita` is empty for every candidate in this election — no programme documents
  were published on that tab.

## Appendix: 2023 Visaginas mayoral repeat vote (`2023-geguzes-7-visagino-mero`)

Records are written as
`data/2023-geguzes-7-visagino-mero/<candidate-id>-2023-geguzes-7-visagino-mero.json`
with the same top-level fields. The pages are the `2023-spalio-8-kupiskio-mero`
vintage throughout — same profile card, `<div>`-wrapped tab bodies, `10 .`
question numbering, inline Q8 membership answer, 2020-numbered biography — so
every page-level shape described in that appendix applies here too, except
that candidate pages carry five tabs, not six: this repeat vote re-ran the
March 2023 mayoral runoff, and neither candidate page publishes a campaign tab
(their campaign finance is published with
`2023-kovo-5-savivaldybiu-tarybu-ir-meru`). The `normalized` section order is
therefore `profilis`, `anketa`, `biografija`, `turto-ir-pajamu-deklaracijos`,
`privaciu-interesu-deklaracija`, `kita`, with no campaign section at all.

Election-specific notes:

- `profilis.pastaba` holds the elected note for the winner only
  (`Išrinktas Visagino (Nr.59) savivaldybėje II ture`); the loser has `null`.
- `profilis.kita.turas` is `II` for both candidates — only the runoff was
  re-run, so there was no first round.
- The list fields under `profilis.kita` (`sarasas`, `numeris-sarase`,
  `porinkiminis-numeris-sarase`) are published empty for both candidates: the
  repeat vote had no list component.
- No candidate declared a conviction or a lost mandate, so `teistumo-detales`
  is `{"irasai": []}` and `mandato-netekimo-detales` is `null` throughout.
- `kita` is empty for both candidates.

## Appendix: 2023 Seimo by-election (`2023-rugsejo-3-seimo-raseiniai-kedainiai`)

Records are written as
`data/2023-rugsejo-3-seimo-raseiniai-kedainiai/<candidate-id>-2023-rugsejo-3-seimo-raseiniai-kedainiai.json`
with the same top-level fields. Candidate pages carry the six-tab 2024 Seimo set,
so the `normalized` section order is `profilis`, `anketa`, `biografija`,
`turto-ir-pajamu-deklaracijos`, `privaciu-interesu-deklaracija`,
`politines-kampanijos-dalyvio-duomenys`, `kita`.

Election-specific notes:

- `candidateName` drops the `(V)` winner suffix the listing appends.
- `profilis.pastaba` holds the elected note for the winner only
  (`Išrinktas vienmandatėje Raseinių–Kėdainių (Nr. 42) apygardoje II ture`).
  Constituency fields land under `profilis.kita`: `vienmandate-apygarda`,
  `iskele`, `turas` (`I`/`II`), `sarasas`, `numeris-sarase`,
  `porinkiminis-eiles-numeris`.
- `profilis.nuotrauka` is a URL to the candidate photo (`kandImg/...`).
- `normalized.anketa` follows the 2024 question numbering: `adresas` (Q6) and
  `einamos-pareigos` (Q7). Q8 is answered inline, so
  `narystes-politinese-organizacijose` carries both `tekstas` and `irasai`
  (empty unless a membership table appears), as in the 2023 mayoral module.
- `normalized.anketa.pareiskimai` carries the Rinkimų kodekso 76 str.
  declarations Q9–Q14 under the same keys as the 2024 modules, plus the Seimo
  eligibility questions Q15 (`ar-esate-ar-buvote-kitos-valstybes-pilietis`) and
  Q16 (`ar-susijes-priesaika-uzsienio-valstybei`), whose wording — and keys —
  match the presidential module.
- `teistumo-detales` holds the conditional Q13.1–Q13.4 conviction details; the
  detail table uses the 2024 en dash separator.
- `biografija` keeps the 2023 numbering shared with the mayoral module:
  `gimimo-data`/`gimimo-vieta` (Q1), `tautybe` (Q2), `issilavinimas.irasai`
  (Q3), `mokslo-laipsnis` (Q3.1), `pedagoginis-vardas` (Q3.2),
  `uzsienio-kalbos` (Q4), `darbo-patirtis.irasai` (Q5), `visuomenine-veikla`
  (Q6), `pomegiai` (Q7), `seimine-padetis` (Q8).
- `politines-kampanijos-dalyvio-duomenys` covers both participant types:
  `Savarankiškas` candidates publish all five campaign tabs (treasurer, auditor,
  donations, financing reports, contracts), while `Atstovaujamasis` candidates —
  whose campaign is run by their party — publish only donations.
- `kita` is empty for every candidate in this election.

## Appendix: 2023 municipal councils and mayors (`2023-kovo-5-savivaldybiu-tarybu-ir-meru`)

Records are written as
`data/2023-kovo-5-savivaldybiu-tarybu-ir-meru/<candidate-id>-2023-kovo-5-savivaldybiu-tarybu-ir-meru.json`.
The candidate pages are the same vintage as `2023-spalio-8-kupiskio-mero` — same
profile card, `<div>`-wrapped tab bodies, `10 .` question numbering, inline Q8
membership answer, hyphen-separated conviction details — so every page-level
shape described in that appendix applies here too. What is specific to this
election is the record around them.

`candidateId` is `<name-slug>-<vrkCandidateId>` (e.g.
`raimundas-markauskas-2429873`), not the bare name slug the other modules use.
244 of the 13,796 candidates share a name slug with someone else — four
different people are called Mindaugas BALČIŪNAS — and the positional `-2`/`-3`
suffix of the other modules would make an id depend on traversal order, which
the batch runner uses as its resume marker.

The record carries two top-level fields beyond the common set:

- `candidateNote` — the status note the listing may append to a name, as in
  `2025-kovo-16-meru`. Null for every fixture candidate.
- `kandidatavimas` — the candidacy context described below.

### `kandidatavimas`

Which municipality a candidate stood in, on whose list, at which position and
whether they won is published on the listing pages and nowhere on the candidate
page, so it is carried in from the sitemap rather than parsed out of the anketa.
It is the only block of its kind in the repository.

- `vrkCandidateId` — VRK's own candidate id, the one in every candidate URL.
- `savivaldybe` — `{id, number, name}`: VRK's `rpgId`, the municipality number
  as printed on the listing (1–60), and the name with that number stripped
  (`{"id": "22012", "number": 12, "name": "Jurbarko rajono"}`).
- `roles` — a list holding `tarybos-narys`, `meras`, or both. 406 candidates
  hold both; 13,363 are council-only and 27 mayor-only.
- `tarybosNarys` — `null` for a mayor-only candidate, otherwise
  `{partyList: {id, number, name}, listPosition, postElectionPosition, elected}`.
  `listPosition` is the pre-election order on the list, `postElectionPosition`
  the order after preference votes were counted; both are `null` if the cell is
  not a plain number. `partyList.name` covers parties, coalitions and political
  committees alike.
- `meras` — `null` for a council-only candidate, otherwise
  `{round, nominatedBy, elected}`. `round` is `I` or `II`; `nominatedBy` is
  `išsikėlė pats` for a self-nominated candidate or the nominating
  party/committee name.
- `isrinktas` — true when either candidacy was won. A dual candidate can be
  elected to the council while losing the mayoral race, and the reverse also
  occurs, so this is not the same as `meras.elected`.

`elected` on both sub-blocks comes from VRK colouring a winner's name link blue
on the listing; there is no field of its own for it.

### The campaign section is role-dependent

`normalized` section order is the full seven-section order —
`profilis`, `anketa`, `biografija`, `turto-ir-pajamu-deklaracijos`,
`privaciu-interesu-deklaracija`, `politines-kampanijos-dalyvio-duomenys`,
`kita` — for a candidate who stands for mayor, and the same order without
`politines-kampanijos-dalyvio-duomenys` for a council-only candidate.

This is a property of the role, not of the election: a council candidate's
campaign is run by the party list, so only candidates who also stand for mayor
register a campaign participant of their own. Measured over 30 sampled pages of
each kind, 0/30 council-only pages carry the tab and 30/30 mayoral ones do.

Both participant types appear among mayoral candidates. `Savarankiškas`
participants publish the full five campaign tabs (treasurer, auditor,
donations, financing reports, contracts); `Atstovaujamasis` ones publish only
the donations tab, and that tab can itself be empty when the party campaign
attributed nothing to the candidate.

Campaign records carry the `sprendimai` key shared with the other elections —
the VRK decisions taken about a campaign, each `{rowNumber, title, date,
number, note, urls}`. One fixture candidate has one (a decision about unlawful
outdoor political advertising).

### `profilis.kita` keys vary by role

The profile card publishes a different field set for each role, and the
nomination field is published under **two different labels**:

- council-only: `savivaldybe`, `sarasas`, `numeris-sarase`,
  `porinkiminis-numeris-sarase`. There is no nomination row and no `turas`.
- mayor-only: `savivaldybe`, `iskele-i-savivaldybes-merus`, `turas`, `sarasas`,
  `numeris-sarase`, `porinkiminis-numeris-sarase`. The last three keys exist but
  their `reiksme` is `null` — the candidate is on no list.
- dual: `savivaldybe`, `iskele-i-tarybos-narius-ir-merus`, `turas`, `sarasas`,
  `numeris-sarase`, `porinkiminis-numeris-sarase`, all populated.

Reading only `iskele-i-savivaldybes-merus` therefore misses the nominator of
every one of the 406 dual candidates. `kandidatavimas` is the stable place to
read all of this from: it carries the same facts under one key set regardless of
role.

### `profilis.pastaba` forms

`pastaba` is `null` for a candidate who won nothing, and otherwise takes one of
two forms, in both of which the verb agrees with the candidate's gender:

- list form, for the 1,498 elected council members —
  `Išrinktas pagal Demokratų sąjungos „Vardan Lietuvos“ sąrašą`,
  `Išrinkta pagal Lietuvos socialdemokratų partijos sąrašą`.
- mayoral form, for the 60 elected mayors —
  `Išrinktas Akmenės rajono (Nr.1) savivaldybėje I ture`,
  `Išrinkta Alytaus rajono (Nr.3) savivaldybėje II ture`.

A dual candidate elected to the council but not as mayor gets the list form.

The list name inside the note is in the genitive, so it does **not** match
`profilis.kita.sarasas.reiksme` or `kandidatavimas.tarybosNarys.partyList.name`
verbatim — `Demokratų sąjunga „Vardan Lietuvos“` becomes `Demokratų sąjungos
„Vardan Lietuvos“`, and a coalition inflects every member party
(`Koalicija „Geriausias pasirinkimas“ (Partija „Laisvė ir teisingumas“, …)` →
`Koalicijos „Geriausias pasirinkimas“ (Partijos „Laisvė ir teisingumas“, …)`).
Join on `partyList.id`, not on the string.

### `biografija` numbering

The 2023 numbering shared with `2023-spalio-8-kupiskio-mero` and
`2023-rugsejo-3-seimo-raseiniai-kedainiai`: `gimimo-data`/`gimimo-vieta` (Q1),
`tautybe` (Q2), `issilavinimas.irasai` (Q3), `mokslo-laipsnis` (Q3.1),
`pedagoginis-vardas` (Q3.2), `uzsienio-kalbos` (Q4), `darbo-patirtis.irasai`
(Q5), `visuomenine-veikla` (Q6), `pomegiai` (Q7), `seimine-padetis` (Q8).
Nationality being Q2 is what shifts education and work history by one relative
to the 2024 modules.

The Q3 and Q5 record tables are rendered either inside their question's row or
in the row right after it, depending on the candidate; both placements are
collected.

### Other sections

- `normalized.anketa` is the mayoral/municipal set of the 2023 pages:
  `adresas` (Q6), `einamos-pareigos` (Q7),
  `narystes-politinese-organizacijose` with both `tekstas` (Q8 is answered
  inline) and `irasai` (empty unless a membership table appears), the Rinkimų
  kodekso 76 str. declarations Q9–Q14 under `pareiskimai`, plus
  `teistumo-detales` and `mandato-netekimo-detales`. No fixture candidate
  answered Q13 or Q14 "Taip", so both are null/empty in the sampled output; with
  13,796 candidates in the field the full run will not be.
- `privaciu-interesu-deklaracija` follows the 2024 shape. Its `kiti-duomenys`
  section is free text published without a label, so it lands under a `tekstas`
  key inside the record rather than as a named field.
- `kita` is empty for every fixture candidate.

## Appendix: 2019 municipal councils and mayors (`2019-kovo-3-savivaldybiu-tarybu`)

Records are written as
`data/2019-kovo-3-savivaldybiu-tarybu/<candidate-id>-2019-kovo-3-savivaldybiu-tarybu.json`.
This is the March 2019 municipal general election: 13,666 candidates across all
60 municipalities, the second-largest election in the repository.

The record *around* the pages is the one
`2023-kovo-5-savivaldybiu-tarybu-ir-meru` introduced — `candidateNote`,
`kandidatavimas`, `candidateId` as `<name-slug>-<vrkCandidateId>` (e.g.
`nerijus-cesiulis-2406286`), and a campaign section whose presence depends on
the candidate's role. The pages themselves are four years older and belong to
the 2016-era family of `2017-balandzio-23-meru`, whose parsers this module
reuses: the whole Q5–Q21 anketa with the biography questions inside it,
free-text `biografija`, base64 photos, `ID001x` private-interest sections. None
of the 2023 page shapes apply.

### `kandidatavimas`

Same shape and same reason as in the 2023 module: municipality, list, seat
order and elected flags are published on the listing pages and nowhere on the
candidate page, so they are carried in from the sitemap.

- `vrkCandidateId`, `savivaldybe` (`{id, number, name}`), `roles`
  (`tarybos-narys`, `meras`, or both), `tarybosNarys`
  (`{partyList: {id, number, name}, listPosition, postElectionPosition,
  elected}` or `null`), `meras` (`{round, nominatedBy, elected}` or `null`),
  and `isrinktas`, true when either candidacy was won.
- The 2019 roles partition is 13,256 council-only, 379 dual and 31 mayor-only.
  As in 2023, `isrinktas` is not `meras.elected`: a dual candidate can take the
  council seat and lose the mayoralty, and one fixture candidate
  (`gediminas-dauksys-2408494`) does exactly that.
- `partyList.name` covers parties, coalitions and the 87 "visuomeniniai rinkimų
  komitetai" of this election alike — there were no politiniai komitetai in
  2019.

### `normalized.anketa` is the 2016-era key set

The questionnaire is the one described under "`normalized.anketa` (2016)" as
narrowed by the April 2017 mayoral module: `gimimo-data` (Q5), `adresas` (Q6),
`pareiskimai`, `gimimo-vieta` (Q10), `tautybe` (Q11), `issilavinimas` (Q12,
`aprasas` plus `irasai`), `pedagoginis-vardas`, `uzsienio-kalbos` (Q13, split
into a list), `politine-organizacija` (Q14), `anksciau-isrinktas` (Q15, same
`aprasas`/`irasai` shape), `pagrindine-darboviete` (Q16), `visuomenine-veikla`
(Q17), `pomegiai` (Q18), `seimine-padetis` (Q19),
`sutuoktinio-vardas-pavarde`, `vaiku-vardai-pavardes` (Q20), `kita-apie-save`.
`pedagoginis-vardas` and `sutuoktinio-vardas-pavarde` carry no question number
and are matched on their prompt text.

`pareiskimai` has **nine** keys. The election runs under the savivaldybių
tarybų rinkimų įstatymas (36 str. 11–12 d.), not the Rinkimų kodeksas, but 2019
asks four declarations the April 2017 mayoral pages do not, so the key set is
wider than that module's:

- `ar-nebaigta-teismo-paskirta-bausme` (Q8.1), `ar-atliekate-karo-tarnyba`
  (Q8.2), `ar-eina-nesuderinamas-pareigas` (Q8.3),
  `ar-kitos-valstybes-institucijos-narys` (Q8.4),
  `ar-turite-kitos-valstybes-pilietybe` (Q8.5), `ar-buvote-pripazintas-kaltu`
  (Q9), `ar-veika-dekriminalizuota` (Q9.2),
  `ar-buvote-pripazintas-kaltu-uzsienyje` (Q9.3),
  `ar-buvote-pripazintas-kaltu-del-politinio-persekiojimo` (Q9.4).
- Answers are worded `Neturiu`/`Nesu`/`Neinu`/`Esu`/`Einu`/`Ne` rather than the
  `Taip`/`Ne` of the Rinkimų kodeksas era.
- Q9 is answered on the question row here, not on a continuation row quoting
  the statute as in April 2017.
- Q9.1 is the conviction *detail* table, normalized as
  `anketa.teistumo-detales` — `{"irasai": [...]}` with the meru_2021 keys
  (`nuosprendzio-data`, `nuosprendzio-valstybe`, `nuosprendzio-institucija`,
  `nusikalstama-veika`), one record per conviction and an empty list when Q9
  is not answered `Taip`. It is the last top-level anketa key. Everything the
  page publishes is normalized.

A candidate who answers Q9 `Taip` is worth checking against when changing this
module: VRK nests the conviction-detail table inside the anketa table for
those pages, and that nesting has bitten twice — a recursive header lookup
used to classify the whole questionnaire as a record table and discard it,
and the row hosting the nested table used to die on the empty-row skip so the
details reached neither `rawData` nor `normalized`. `gintas-orda-2400958` is
the fixture that covers both.

Three nulls to expect, all genuine:

- `issilavinimas.aprasas` and `anksciau-isrinktas.aprasas` are null for every
  candidate. Q12 and Q15 render as record tables with no free-text description.
  The data is in `irasai`.
- `kita-apie-save` is null for most candidates because Q21 is answered
  `Nenurodė`, which normalizes to null. Candidates who did write something have
  it: the fixture `kestutis-armonas-2404237` reads "Esu optimistas, realiai
  žiūrintis į gyvenimą".

### `biografija` and `profilis.nuotrauka` are role-dependent

`biografija` is free text (`{"tekstas": ...}`) as in 2016 Seimo, and
`profilis.nuotrauka` is a base64 data URI as in 2019 EP — but both are
published only for candidates who stand for mayor. Measured over 158 records the
split is exact: 149/149 council-only candidates have neither — their biography
tab is an empty shell and the profile card carries no image — and 9/9 with a
`meras` role have both. Since only 410 of the 13,666 candidates stand for mayor,
roughly 97% of records will carry neither field. That is upstream behaviour, not
a parse failure.

### The campaign section is role-dependent

`normalized` section order is the full seven-section order — `profilis`,
`anketa`, `biografija`, `turto-ir-pajamu-deklaracijos`,
`privaciu-interesu-deklaracija`, `politines-kampanijos-dalyvio-duomenys`,
`kita` — for a candidate who stands for mayor, and the same order without
`politines-kampanijos-dalyvio-duomenys` for a council-only candidate. As in
2023 this follows from the role, not the election: a council candidate's
campaign is run by the party list.

Both participant types appear. `Savarankiškas` participants publish the full
five campaign tabs (treasurer, auditor, donations, financing reports,
contracts) with `registravimo-data` and `sprendimo-numeris` filled;
`Atstovaujamasis` ones publish only donations, and that tab is frequently empty
— five of the six fixture candidates with a campaign are `Atstovaujamasis` with
no donation section at all. Campaign records carry the `sprendimai` key shared
with the other elections; no fixture candidate has one.

### `profilis.kita` keys vary by role

Same three key sets as 2023, with one wording difference: the nomination row
reads `iskele-i-tarybos-narius-merus` — "into council members - mayors", with
no "ir" — because mayors were council members ex officio under the rules of the
time.

- council-only: `savivaldybe`, `sarasas`, `numeris-sarase`,
  `porinkiminis-numeris-sarase`. No nomination row and no `turas`.
- mayor-only: `savivaldybe`, `iskele-i-tarybos-narius-merus`, `turas`,
  `sarasas`, `numeris-sarase`, `porinkiminis-numeris-sarase`, the last three
  with a `null` `reiksme` — the candidate is on no list.
- dual: the same six keys, all populated.

`kandidatavimas` carries the same facts under one key set regardless of role
and is the stable place to read them from.

### `profilis.pastaba` forms

`null` for a candidate who won nothing; otherwise the list form for elected
council members (`Išrinktas pagal Visuomeninio rinkimų komiteto „Už Alytų“
sąrašą`, `Išrinkta pagal Lietuvos valstiečių ir žaliųjų sąjungos sąrašą`) or
the mayoral form for elected mayors (`Išrinktas Akmenės rajono (Nr.1)
savivaldybėje I ture`). The verb agrees with the candidate's gender, and a dual
candidate elected to the council but not as mayor gets the list form.

As in 2023 the list name inside the note is in the genitive and does not match
`profilis.kita.sarasas.reiksme` or
`kandidatavimas.tarybosNarys.partyList.name` verbatim. Join on `partyList.id`.

### Other sections

- `turto-ir-pajamu-deklaracijos` keeps the seven canonical keys. The
  asset/income aliases are **local to this module**: the asset rows keep the
  Roman-numeral labels of 2017, but the income rows were reworded between the
  two elections. April 2017 names the GPM308 field numbers (`Gautų pajamų suma
  (GPM308 formos 12, 13, 14 … laukelių suma)`); 2019 states the same two
  figures in prose (`Deklaruota apmokestinamųjų ir neapmokestinamųjų pajamų
  suma`, `Deklaruota mokėtina pajamų mokesčio suma`). Reusing the 2017 aliases
  leaves `gautos-pajamos` and `sumoketas-pajamu-mokestis` null for every
  candidate while the values sit in `rawData`. The resulting table is the same
  one `2024-ep` and the 2018/2019 Seimo by-election modules use, restated here
  rather than imported. The rest of the GPM308 breakdown — individual-activity
  income, asset-sale income and its acquisition cost — stays in `rawData`.
- `privaciu-interesu-deklaracija` follows the 2019 EP shape: the declarant is
  hoisted to `deklaruojantis-asmuo`, the spouse block is retained under
  `deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris`, and each
  declaration block is keyed by its section id (`id001j`, `id001s`, `id001i`,
  `id001a`, `id001f`, …).
- `kita` is empty for almost every candidate, but not all: one fixture
  candidate published a signed pledge not to bribe voters, captured under
  `kita.tekstai` and `kita.nuorodos`. 1 of the 232 records parsed at the time of
  writing carries anything there.

## Appendix: 2025 mayors (`2025-kovo-16-meru`)

Records are written as
`data/2025-kovo-16-meru/<candidate-id>-2025-kovo-16-meru.json`. The record
carries one field beyond the common top-level set. (It is not alone in that:
both municipal general elections carry `candidateNote` on every record too,
alongside `kandidatavimas` — see their appendices. No other election carries
either.)

- `candidateNote` — the status note the listing appends to the name of a
  candidate whose registration was revoked (`išbrauktas - Seimo nutarimu`),
  `null` for everyone else. The candidate page leaves that line of the profile
  card blank, so the listing is the only source for it.

Candidate pages otherwise follow the 2024 layout:

- `profilis.pastaba` holds the elected note for the two elected mayors
  (`Išrinktas Joniškio rajono (Nr.11) savivaldybėje II ture`); the municipal
  fields land under `profilis.kita` as `savivaldybe`,
  `iskele-i-savivaldybes-merus`, `turas`, `sarasas`, `numeris-sarase`,
  `porinkiminis-numeris-sarase`.
- `normalized.anketa` is the mayoral question set: `adresas` (Q6),
  `einamos-pareigos` (Q7), `narystes-politinese-organizacijose.irasai` (the Q8
  membership table — unlike the 2023 mayoral pages, which answer Q8 inline), and
  the Rinkimų kodekso 76 str. declarations Q9–Q14 under the keys shared with the
  2024 modules. There are no Q15/Q16 eligibility questions.
- `biografija` follows the 2024 EP numbering (no nationality question):
  `issilavinimas` is Q2, `mokslo-laipsnis` Q2.1, `darbo-patirtis` Q4.
- `politines-kampanijos-dalyvio-duomenys` is absent for struck-off candidates,
  who publish five tabs instead of six. Both participant types appear among the
  rest.
- `kita` is empty for every candidate in this election.

## Appendix: 2017 mayors (`2017-balandzio-23-meru`)

Records are written as
`data/2017-balandzio-23-meru/<candidate-id>-2017-balandzio-23-meru.json`. These
pages predate the 2024 layout, so the section shapes follow the 2016/2019 era:

- `profilis.pastaba` holds the elected note for the two elected mayors;
  `profilis.kita` carries `savivaldybe`, `iskele-i-tarybos-narius-merus`
  (mayors were also council members under the rules of the time), `turas`,
  `sarasas`, `numeris-sarase`, `porinkiminis-numeris-sarase`.
- `profilis.nuotrauka` is a base64 data URI, as in 2019 EP.
- `normalized.anketa` keeps the 2016 Seimo keys, because the biography
  questions are part of the anketa rather than a separate tab: `gimimo-data`
  (Q5), `adresas` (Q6), `gimimo-vieta` (Q10), `tautybe` (Q11), `issilavinimas`
  (Q12), `uzsienio-kalbos` (Q13), `politine-organizacija` (Q14),
  `anksciau-isrinktas` (Q15), `pagrindine-darboviete` (Q16),
  `visuomenine-veikla` (Q17), `pomegiai` (Q18), `seimine-padetis` (Q19),
  `vaiku-vardai-pavardes` (Q20). `pedagoginis-vardas`,
  `sutuoktinio-vardas-pavarde` and `kita-apie-save` are matched on their prompt
  text — the first two carry no question number, and Q21 is written with its
  number in brackets at the end.
- `pareiskimai` holds the savivaldybių tarybų rinkimų įstatymo 36 str. 11 d.
  declarations. There is no `8.1` on these pages, and the four that exist are
  numbered without a trailing dot. `ar-buvote-pripazintas-kaltu` comes from Q9,
  which asks whether the candidate has anything to declare under the conviction
  paragraph (36 str. 12 d.); its answer is rendered on the continuation row that
  quotes the statute.
- `biografija` is free text (`{"tekstas": ...}`), as in 2016 Seimo.
- `turto-ir-pajamu-deklaracijos` keeps the seven canonical keys, but the income
  rows are GPM308 fields and name their own field numbers, so the aliases are
  local to this module.
- `privaciu-interesu-deklaracija` hoists the declarant and keys each declaration
  block by its section id (`id001j`, `id001s`, …), as in 2019 EP.
- `kita` is empty for every candidate in this election.

## Appendix: 2017 Marijampolė mayor (`2017-rugsejo-10-marijampoles-mero`)

Records are written as
`data/2017-rugsejo-10-marijampoles-mero/<candidate-id>-2017-rugsejo-10-marijampoles-mero.json`.
The pages are the same vintage as `2017-balandzio-23-meru`, so every section has
the shape described in that appendix — the 2016-era anketa keys with the
municipal `pareiskimai` block, free-text `biografija`, base64 `profilis.nuotrauka`,
GPM308 asset/income aliases and `ID001x` private-interest sections.

The one behavioural difference is in the campaign section: candidates whose
campaign is run by their party publish a participant page with no tab navigation,
so `politines-kampanijos-dalyvio-duomenys[]` carries the participant metadata
with an empty `aukos-pagal-sekcija` and no financing reports or contracts.

## Appendix: 2021 mayors (`2021-spalio-10-meru`)

Records are written as
`data/2021-spalio-10-meru/<candidate-id>-2021-spalio-10-meru.json`. The page
shape matches `2023-spalio-8-kupiskio-mero` — same profile card,
`<div>`-wrapped tab bodies, biography numbering with nationality as Q2, and
`profilis.nuotrauka` as a URL — but the anketa follows the 2020 Seimo numbering:

- `adresas` (Q6) and `kontaktai` — `telefonas` (Q6.1), `el-pastas` (Q6.2),
  `socialiniu-tinklu-paskyros` (Q6.3)
- `einamos-pareigos` (Q7) and `narystes-politinese-organizacijose.tekstas`
  (Q7.1, answered inline). Q7.1 carries no dot after its number, so question
  numbers are re-derived with the tolerant pattern; the strict one reads it as
  Q7 and the membership answer is lost.
- `pareiskimai` holds the savivaldybių tarybų rinkimų įstatymo 36 str. 11 d.
  declarations (Q8.1–Q8.4), the 36 str. 12 d. conviction ones (Q9, Q9.2–Q9.4)
  and the former-USSR question (Q10), under the keys shared with the other
  modules.
- `teistumo-detales.irasai` holds the Q9.1 conviction table, present only when
  Q9 is answered "Taip". Its columns are named after the sub-question numbers
  and are mapped to `nuosprendzio-data`, `nuosprendzio-valstybe`,
  `nuosprendzio-institucija` and `nusikalstama-veika`.
- `kita` is empty for every candidate in this election.

## Appendix: 2021 Radviliškis mayor (`2021-balandzio-11-radviliskio-mero`)

Records are written as
`data/2021-balandzio-11-radviliskio-mero/<candidate-id>-2021-balandzio-11-radviliskio-mero.json`.
The pages are the same vintage as `2021-spalio-10-meru`, so every section has the
shape described in that appendix.

Two election-specific notes:

- every candidate answered "Nenurodė" to Q10, so
  `pareiskimai.ar-bendradarbiavote-su-ssrs-tarnybomis` is null throughout while
  the other eight declarations are answered;
- `kita` is populated for one candidate — the first election in the repository
  found to carry anything on that tab (`2019-kovo-3-savivaldybiu-tarybu` also
  does, for a small minority of its candidates). It holds the document title
  under `tekstai` and its download URL under `nuorodos`.

## Appendix: 2017 Seimo by-election (`2017-balandzio-23-seimo-anyksciai-panevezys`)

Records are written as
`data/2017-balandzio-23-seimo-anyksciai-panevezys/<candidate-id>-2017-balandzio-23-seimo-anyksciai-panevezys.json`.
The pages follow the 2016 Seimo layout, so `normalized.anketa` carries the 2016
key set described under "`normalized.anketa` (2016)" — biography questions
included — and `biografija` is free text, `profilis.nuotrauka` a base64 data URI
and `privaciu-interesu-deklaracija` keyed by section id.

Election-specific notes:

- `candidateName` drops the `(V)` winner suffix the listing appends, and
  `profilis.pastaba` holds the elected note, which is rendered inside the name
  cell of the profile card rather than in a row of its own.
- `profilis.kita` carries `vienmandate-apygarda`, `iskele`, `turas`, `sarasas`,
  `numeris-sarase`, `porinkiminis-eiles-numeris`.
- The education (Q12) and prior-mandate (Q15) record tables are rendered in a
  row of their own, so `issilavinimas.irasai` and `anksciau-isrinktas.irasai`
  are collected from the question row and the table row that follows it.
- `kita` is empty for every candidate in this election.

## Appendix: 2018 and 2019 Seimo by-elections

`2018-rugsejo-16-seimo-zanavykai` (Zanavykai No. 64) and `2019-rugsejo-8-seimo`
(Žirmūnai No. 4, Gargždai No. 31, Žiemgala No. 46) both follow the 2016 Seimo
layout, so `normalized.anketa` carries the 2016 key set described under
"`normalized.anketa` (2016)", `biografija` is free text, `profilis.nuotrauka` is
a base64 data URI and `privaciu-interesu-deklaracija` is keyed by section id.

Election-specific notes:

- `candidateName` drops the `(V)` winner suffix the listing appends;
  `profilis.pastaba` holds the elected note, one per constituency.
- `turto-ir-pajamu-deklaracijos` keeps the seven canonical keys, but the income
  rows use the modern labels rather than the GPM308 field-number wording of the
  2016 and April 2017 pages, despite the section heading still naming GPM308.
- The 2019 election includes a candidate nominated by two parties; both appear
  in `profilis.kita.iskele.reiksme`, separated by `; `.

## Appendix: 2015 Seimo by-elections (`2015-kovo-1-seimo-zirmunai`, `2015-birzelio-7-seimo-varena-eisiskes`)

The March by-election in Žirmūnai (No. 4) defines the 2015-era parsers; the
June one in Varėna–Eišiškės (No. 70) is thin wiring over the same machinery
and shares every shape below. Records are written as
`data/<election-id>/<candidate-id>-<election-id>.json`
with the same top-level fields and the corpus's section order (`profilis`,
`anketa`, `biografija`, `turto-ir-pajamu-deklaracijos`,
`privaciu-interesu-deklaracija`, `politines-kampanijos-dalyvio-duomenys`,
`kita`). The pages are the pre-2016 static layout — the oldest family in the
repository — so several record shapes are this era's own:

- **No elected markers on the pages.** The 2015 pages carry no `(V)` suffix,
  no blue anchors and no elected note, so `profilis.pastaba` is null on every
  record, the winner's included. Electedness is joined in from VRK's results
  tree instead — `kandidatavimas.isrinktas`, see the shared section above.
  Both by-elections were decided in a second round; Žirmūnai's round-two
  page states no verdict sentence, so its winner is read as the plurality of
  the two-candidate runoff (`method: "runoff-plurality"` in the results file).
- `profilis.nuotrauka` is a URL to an external JPG
  (`Kandidato<ID>Foto.jpg`) — this era never embedded base64 photos.
  `profilis.kita` holds `apygarda` and `iskele`, plus a
  `savarankisko-`/`atstovaujamojo-politines-kampanijos-dalyvio-duomenys` entry
  whose link is the campaign participant page.
- `normalized.anketa` carries the 2015 Seimo question set: the 2016 keys
  with `mokslo-laipsnis` and `pedagoginis-vardas` in place of 2016's one
  combined `pedagoginis-vardas` line — the page prints "Jei turite,
  nurodykite mokslo laipsnį <b>…</b>, vardą <b>…</b>" (or "…mokslo vardą"
  alone for a title without a degree), and both halves are read (since
  2026-08-22; the whole 2008–2015 family, the municipal elections
  included, lacked the two keys before) — and `pareiskimai` stops at
  `ar-buvote-pripazintas-kaltu` (Q9.2) — the 9.3.x follow-ups do not exist
  yet. `kita-apie-save` (Q21) is
  present but answered by a minority. A bare `","` in `pagrindine-darboviete`
  is the template's empty workplace/position join and normalizes to null.
- `turto-ir-pajamu-deklaracijos` keeps the seven canonical keys **but the
  amounts are litas, not euros**. Two extra keys make that explicit:
  `valiuta` (always `"Lt"`) and `pastaba` (the page's own note naming the
  declaration period, e.g. 2013 for this election).
- `privaciu-interesu-deklaracija` is form-id keyed and — unlike the 2016-era
  Seimo family — retains the spouse block
  (`deklaruojancio-asmens-sutuoktinis-sugyventinis-partneris`).
- `politines-kampanijos-dalyvio-duomenys` keeps the fixed ten keys with
  `registravimo-data` and `sprendimo-numeris` always null (never published this
  era) and four additions: donation records carry `amountEur` *and* `amountLt`
  (the pages print both currencies), each donation section carries a
  `suvestine` list (the totals block VRK prints under the records — totals by
  source type, with the "juridinių asmenų aukos" prohibition note),
  `auditorius.ataskaitos` lists the auditor's report PDFs, and represented
  participants (`statusas: "Atstovaujamasis"`) carry `atstovauja` naming and
  linking the party whose campaign covers them.
- `kita` holds the "Kandidato programa" text with the program PDF URL in
  `nuorodos`; one candidate published no program (`Duomenų nėra`, no link).

## Appendix: 2015 Telšiai mayor (`2015-lapkricio-8-telsiu-mero`)

Records are written as
`data/2015-lapkricio-8-telsiu-mero/<candidate-id>-2015-lapkricio-8-telsiu-mero.json`.
The pages are the 2015 era described in the appendix above — every era shape
there (no elected data, URL photos, litas amounts with `valiuta`/`pastaba`,
retained spouse block, the campaign additions) applies here too. What differs
is the municipal question set and the profile card:

- `normalized.anketa.pareiskimai` carries the savivaldybių tarybų rinkimų
  įstatymo declarations: `ar-nebaigta-teismo-paskirta-bausme` (Q8.1),
  `ar-atliekate-karo-tarnyba` (Q8.2), `ar-eina-nesuderinamas-pareigas` (Q8.3),
  `ar-kitos-valstybes-institucijos-narys` (Q8.4),
  `ar-turite-kitos-valstybes-pilietybe` (Q8.5) and
  `ar-buvote-pripazintas-kaltu` (the Q9 "anything to declare" question) and
  `teisiniai-argumentai` — the unnumbered explanation row a "Taip" may be
  followed by ("Jeigu į 9 p. klausimą atsakėte „Taip“ ir norite papildomai
  apie tai paaiškinti, tai įrašykite čia"; null for everyone else and on
  every Telšiai record). Keys shared with `meru_2017` where the questions
  match, and with the 2016 form for the explanation slot. Answers are the
  era's verbose first person (`Neturiu`, `Nesu`, `Neinu`; one candidate
  answers `Einu`).
- `profilis.kita` holds `savivaldybe`, `iskele` and `numeris-sarase` for
  party-nominated candidates; the self-nominated candidate instead carries an
  `issikeles-kandidatas` entry and no list fields.
- `kita` is `Duomenų nėra` for every candidate — no Telšiai candidate
  published a program.

## Appendix: 2015 repeat municipal elections (`2015-birzelio-7-pakartotiniai-sirvintos-trakai`, `2015-birzelio-21-pakartotiniai-silutes`)

Records are written as
`data/2015-birzelio-7-pakartotiniai-sirvintos-trakai/<candidate-id>-2015-birzelio-7-pakartotiniai-sirvintos-trakai.json`.
Both are one VRK election published through two listing structures — a
district page whose mayoral section and party-list index each hold candidates.
Pages are the 2015 era with the municipal question set, so the Telšiai
appendix describes the record; these elections add the listing block and some
data facts a consumer has to know about:

- Records carry a top-level `kandidatavimas` block — the same shape the
  municipal general elections write — holding what only the listings publish:
  `vrkCandidateId`, `savivaldybe`, `roles` (`meras`, `tarybos-narys` or both),
  `tarybosNarys` (`partyList`, `listNumber`, `listPosition`) and `meras`
  (`nominatedBy`). For a dual candidate this is the only place the list
  position appears at all — the mayoral profile card prints none.
  `isrinktas` comes from the results join (shared section above): the
  Širvintos mayor (round one), the Trakai mayor (round two) and Trakai's 24
  council seats; `false` for everyone else.

- The sitemap merges the mayoral listing and the party lists on VRK's
  candidate id, so one entry carries `roles` (`meras`, `tarybos-narys`, or
  both) plus a `mayoralCandidacy` (`nominatedBy`) and/or `councilCandidacy`
  (`partyList`, `listNumber`, `listPosition`) block. Neither block carries an
  `elected` key: the 2015 pages publish no elected markers, so the flag is
  absent rather than false.
- **One person holds two candidate ids.** Marija Puč is 87693 as a mayoral
  candidate and 87694 on the council list, so she appears as two entries
  (`marija-puc`, `marija-puc-2`) that the id join cannot merge, while the
  other seven dual candidates merge into one entry each. The sitemap's
  `stats.markerJoinMismatch` is 1 for exactly this reason — the listing's
  prose marker says she ran for both seats and the id join disagrees. Anyone
  counting distinct people in this election has to treat that pair as one
  person; anyone counting candidacies must not.
- A candidacy whose questionnaire VRK never published (her council one) has a
  page reading only `Rengiama`. The record keeps the profile card — name,
  municipality, list and position — with every `anketa` field null, and the
  parse records one `AnketaNotPublished` warning rather than the
  `AnketaTableNotFound`/`AnketaTableEmpty` pair that signals real breakage.
- `biografija` is present only for mayoral candidates; council-only records
  have no `biografija` section at all.
- A council candidate may have no campaign participant link at all, in which
  case the record has no `politines-kampanijos-dalyvio-duomenys` section
  (`jonas-sakurskis-2` in Šilutė).
- Šilutė is the clean counterpart to the June 7th election: all 8 of its
  mayoral candidates also stand for the council, so its `markerJoinMismatch`
  is 0. Its one duplicate candidate id is a real name collision — two
  different people called Jonas Šakurskis, born 1953 and 1957, on different
  lists — where the positional `-2` suffix is the correct treatment. Telling
  the two situations apart matters: Šilutė's pair are two people, Trakai's
  are one.

## Appendix: 2015 municipal general (`2015-kovo-1-savivaldybiu`)

Records are written as
`data/2015-kovo-1-savivaldybiu/<candidate-id>-2015-kovo-1-savivaldybiu.json`.
The pages are the 2015 era with the municipal question set, and the record
carries the same `kandidatavimas` block as the 2015 repeat elections, so those
two appendices describe the shape. What is specific to this election:

- `candidateId` is `<name-slug>-<vrkCandidateId>` (e.g. `valius-azuolas-77601`),
  not the bare name slug the small 2015 modules use. 140 of the 15,149
  candidates share a name slug — two different Albinas Klimas stood in Plungė
  and Akmenė — and the positional `-2`/`-3` suffix would make an id depend on
  traversal order, which the batch runner uses as its resume marker.
- `kandidatavimas.roles` is `["tarybos-narys"]` for 14,715 candidates,
  `["meras", "tarybos-narys"]` for 412 and `["meras"]` for 22. `isrinktas`
  comes from the results join (shared section above): 57 mayors and 1,464
  council seats derived from VRK's municipality results pages — each list's
  top-M post-preference ranks, skipping the mayor-elect — of which the 48
  council seats in Šilutė and Trakai carry `rezultataiPanaikinti` and a
  `false`. Širvintos, Šilutė and Trakai elected no mayor that stood (their
  mayoral results were annulled; the June repeats elected them). The
  derivation was reconciled against VRK's own composition pages: in 58 of 60
  municipalities every derived winner is seated there or in the
  early-termination table, the two exceptions being the annulled councils.
- `kandidatavimas.meras.nominatedBy` is `null` for twelve mayoral candidates.
  VRK published those rows as the bare name, with no "- iškėlė …" clause, so
  the nominator is genuinely absent rather than dropped.
- Counts reconcile with VRK's own `KandidataiMerai.html` roll-up: 434 mayoral
  candidates by the district walk, 434 on the roll-up, none in only one of
  them. The list pages' dual-candidacy marker agrees with the candidate-id
  join on all 412 dual candidates.

## Appendix: 2011 municipal general (`2011-vasario-27-savivaldybiu`)

Records are written as
`data/2011-vasario-27-savivaldybiu/<candidate-id>-2011-vasario-27-savivaldybiu.json`.
The pages are the 2015 era with the municipal question set (the Telšiai
appendix describes the questionnaire — the 2011 form numbers the same
questions the same way, under 35 str. 12 d. and 89 str. 1 d. of the statute
as it then stood), and the record carries the `kandidatavimas` block of the
2015 municipal elections. The election itself is the last before mayors
were elected directly and the only general election in which individuals
stood for the council on their own, so:

- `kandidatavimas.roles` is `["tarybos-narys"]` on every record and `meras`
  is null throughout — there was no mayoral vote, not merely no mayoral
  candidacy. `candidateId` is `<name-slug>-<vrkCandidateId>` as in 2015.
- `kandidatavimas.tarybosNarys` has two extra keys. `listKind` says what
  the list is — `partija` (560 lists), `partiju-koalicija` (11 party
  coalitions) or `issikelusiu-kandidatu-koalicija` (28 coalitions formed by
  self-nominated candidates) — as VRK's own roll-ups classify them.
  `selfNominated` is `true` for the 143 individuals who stood alone: their
  `partyList`, `listKind` and `listPosition` are null and `listNumber` is
  their own number on the ballot, in the one sequence the lists are
  numbered in (an individual is a one-seat "list" on the ballot and on the
  results page). For everyone on a list `selfNominated` is `false` — a
  member of a self-nominated coalition included, because the listing puts
  them on a list; their card's `issikeles-kandidatas` flag (below) says the
  other half.
- `isrinktas` comes from the results join: 1,526 council seats, 1,508 from
  each list's top-M post-preference ranks and 18 from a self-nominated
  individual's own row of the results table (`method: "self-nominated"` in
  the results file; the record's `isrinktasKaip` is `tarybos-narys` either
  way). Every winner resolved by VRK id — nobody holds two ids here, there
  being one candidacy each — and all 60 composition pages contain every
  derived winner.
- `profilis.kita` is the Telšiai shape: `savivaldybe`, then `iskele` and
  `numeris-sarase` for a list candidate. The `issikeles-kandidatas`
  valueless entry appears on two kinds of card: an individual's (no list
  fields at all) and a self-nominated coalition member's (alongside the list
  fields). A party-coalition member's card adds the coalition's member party
  as a second, parenthesised nomination — `iskele-2` (`pavadinimas` the
  literal `"(Iškėlė"`) and `numeris-sarase-2`, the position on that party's
  own share — under the recurring-label rule in the shared section.
  `iskele.nuorodos` links the list page for a coalition and the party's
  own page (`Partijos/Partijos<ID>Apygardos.html`) for a party list.
- `profilis.vardas-pavarde` is in capitals as the card prints it
  (`ARTŪRAS ZUOKAS`); the top-level `candidateName` is the sitemap's title
  case (`Artūras Zuokas`).
- Four sections only: `profilis`, `anketa`, `turto-ir-pajamu-deklaracijos`,
  `privaciu-interesu-deklaracija`, `kita`. No `biografija` (council
  candidates only) and no `politines-kampanijos-dalyvio-duomenys` on any
  record — the 2011 pages link no campaign participant, as the 2008 Seimo
  pages do not. Income is the GPM305 return in litas; `kita` is
  `Duomenų nėra` throughout the fixture set.
- `anketa.pareiskimai.teisiniai-argumentai` is the Q9 explanation row, as
  in Telšiai (Zuokas: "Teistumas buvo panaikintas …").

## Appendix: 2007 municipal general (`2007-vasario-25-savivaldybiu`)

Records are written as
`data/2007-vasario-25-savivaldybiu/<candidate-id>-2007-vasario-25-savivaldybiu.json`.
The pages are the family's oldest shape — the one the Dzūkija by-election of
the same year has (plain-text card, unnumbered questionnaire, FR0462 /
GPM302-era declarations, roman-numbered interest form) — and the record
carries the `kandidatavimas` block of the 2011 and 2015 municipal
elections. Only parties and coalitions of parties could nominate, and no
mayor was elected directly, so:

- `kandidatavimas.roles` is `["tarybos-narys"]` on every record and `meras`
  is null throughout. `candidateId` is `<name-slug>-<vrkCandidateId>`.
- `kandidatavimas.tarybosNarys` is the 2011 shape: `partyList`, `listKind`
  (`partija` for 596 lists, `partiju-koalicija` for the 4 coalitions — the
  sitemap's `coalitions` names each one's two member parties, read from
  the by-party pages), `listNumber` (the list's ballot number, the party's
  national number for a party list), `listPosition` (the printed number —
  a withdrawn candidate keeps theirs, so a list can run 1–33 without 29)
  and `selfNominated`, false on every record.
- `isrinktas` comes from the results join: 1,550 seats read from each
  municipality's "Mandatus gavę kandidatai" page, every winner by VRK id
  (`method: "mandates-page"` in the results file, with the list and the
  post-election number on it); `isrinktasKaip` is `tarybos-narys`, and
  there is no `rezultatuTuras` (one round).
- `profilis.kita` is the legacy-card reading: `apygarda` ("Elektrėnų
  rinkimų apygarda (8 )" — the page names the municipality as the
  electoral district it also is) and `iskele` from the header table above
  the card, then `numeris-sarase` and `gimimo-data` from the card's plain
  lines. A coalition member's card has `numeris-partijos-sarase` too — the
  position on the member party's own share of the list. No links, no
  photo, no notice.
- `profilis.vardas-pavarde` is in capitals as the card prints it; the
  top-level `candidateName` is the sitemap's title case (`Artūras Zuokas`).
- `anketa` keeps the municipal key order with two differences. The 2007
  form numbers nothing, so the rows are keyed by their prompts
  (`rawData.anketa.rows[*].questionNumber` is null throughout), and it asks
  one declaration the later forms do not — `pareiskimai` is
  `ar-nebaigta-teismo-paskirta-bausme`, `ar-atliekate-karo-tarnyba`,
  `ar-eina-nesuderinamas-pareigas`, `ar-kitos-valstybes-institucijos-narys`,
  `ar-turite-kitos-valstybes-pilietybe`,
  **`ar-pasyvioji-rinkimu-teise-neapribota`** ("Ar pasyvioji rinkimų teisė
  nėra apribota valstybėje, kurios pilietis yra" — "Neapribota" on 12,799
  of 13,419 records, Lithuanian-only citizens included), `ar-buvote-pripazintas-kaltu`
  (the 89 str. 1 d. question, as in 2011/2015; 72 "Taip") and
  `teisiniai-argumentai`, the explanation a "Taip" may be followed by —
  on this form a bare text line after the answer rather than a prompted
  row (39 of the 78). `gimimo-data` is the card's date (no Q5).
  `issilavinimas.irasai` and `anksciau-isrinktas.irasai` are the record
  tables, with `aprasas` null. `mokslo-laipsnis` is the "Moksliniai
  laipsniai" line and `pedagoginis-vardas` the "Moksliniai vardai" line,
  each printed only where there is one (753 and 133 records);
  `kita-apie-save` is null (not asked). The family line "Šeimos nariai:
  Sutuoktinis/sutuoktinė Vida, Vaikas Gintarė, Vaikas Ieva" is kept whole
  as **`seimos-nariai`** (a key only this election has) and split into
  `sutuoktinio-vardas-pavarde` ("Vida"; Partneris/partnerė counts) and
  `vaiku-vardai-pavardes` ("Gintarė, Ieva"; Augintinis counts, Anūkas does
  not, and a name with no role continues the role before it);
  `seimine-padetis` is the form's own both-gender wording ("Vedęs,
  ištekėjusi"). `tautybe` is verbatim ("Lietuvis (-ė)").
- Two page habits the normalizer undoes, both visible in `rawData.anketa.rows`
  as the page prints them: an empty answer (`<b></b>`) leaves its key null
  and closes its row; a question printed with **no `<b>` at all** (the
  pasyvioji question on 611 pages, the citizenship one on 8) runs its
  label into the next label's prompt, and the normalizer splits such a
  prompt on the form's labels so the missing question is null and every
  later answer stays with its own label — without which "Ne" from the
  conviction question sat under `ar-pasyvioji-…` on those 611 records.
- Four sections only: `profilis`, `anketa`, `turto-ir-pajamu-deklaracijos`,
  `privaciu-interesu-deklaracija`. No `biografija`, no `kita` (first
  published in 2008) and no `politines-kampanijos-dalyvio-duomenys` on any
  record. `turto-ir-pajamu-deklaracijos` is in litas; `gautos-pajamos` and
  `sumoketas-pajamu-mokestis` are the **sum of the five FR0462 prose
  lines** ("FR0462 Formos deklaracijos: Gauta 39019.30 Lt, išskaičiuota
  pajamų mokesčio 11613.00 Lt", then the S33, S15, S0 and S variants) —
  the candidate filed one of the five and the rest read zero, so the sum
  is the declared income; all five at zero is a declared zero, not a
  missing declaration. `privaciu-interesu-deklaracija` is the
  roman-numbered record-table form of the 2007–2009 section above.

## Appendix: Seimas archive (`1996-spalio-20-seimo`, `1997-kovo-23-seimo-pakartotiniai`, `1997-gruodzio-21-seimo-pakartotiniai`)

Records are written as `data/<election-id>/<candidate-id>-<election-id>.json`.
1996 defines the parsers (`scraper/shared/seimo_archive_1990s.py`); both 1997
repeat elections are thin wiring over the same machinery and share every
shape below. These pages predate even the 2015 family — Teleport Pro
snapshots of `lrs.lt/cgi-bin/ora7dbcgi/...` with no anketa tabs at all — so
while the keys are the corpus's usual kebab-case and the sections it does
publish keep their corpus names (`profilis`, `biografija`), the record is a
**subset** of the shared body's shape: there is no `anketa` section and none
of the declaration sections, because these pages carry no questionnaire.

- `rawData` section order: `profile`, `candidacies`, `residence`,
  `biography`. `normalized` order: `profilis`, `kandidatavimas`,
  `gyvenamoji-vieta`, `biografija`.
- `normalized.profilis` holds `vardas-pavarde`, `nuotrauka` (the external
  photo URL), `biografijos-nuoroda` and `pajamu-deklaracijos-nuoroda`. There
  is no `pastaba`: nothing on these pages marks a winner.
- `rawData.profile` holds `candidateDisplayName`, `photoUrl` (an external URL,
  never downloaded — unlike the base64-embedded-photo eras, this family's
  photos stay as source links), `biographyUrl` and `incomeDeclarationUrl`
  (both fetched: the declaration is parsed into
  `normalized.turto-ir-pajamu-deklaracijos` as described below, while biography
  text is captured verbatim but not further structured).
- `rawData.candidacies` is a **list**, not a single object: typically the
  candidate's single-member constituency plus, optionally, a `Daugiamandatė`
  (multi-mandate party list) entry with its own `listNumber` — but do not
  assume a maximum of two. `uksas-vladislovas` (1996) has **four**: a
  coalition and one of its member parties each nominated him separately, for
  both the constituency seat and the multi-mandate list. Each entry is
  `{apygardaName, apygardaNumber, apygardaUrl, nominator, nominatorUrl,
  listNumber}`; a self-nominated candidate's row reads
  `nominator: "Išsikėlė pats"` (or `"Išsikėlė pati"`, feminine) with
  `nominatorUrl: ""`. `normalized.kandidatavimas` mirrors the list with
  kebab-case keys (`apygarda`, `apygardos-numeris`, `apygardos-nuoroda`,
  `iskele`, `iskele-nuoroda`, `numeris-sarase`) — so unlike most elections,
  **`kandidatavimas` here is a list, and a consumer counting candidacies must
  not assume one per record.**
- `rawData.residence` is recovered from inside a malformed HTML comment (see
  the module docstring and `docs/CLI_REFERENCE.md`'s Seimas archive section)
  rather than through normal DOM parsing.
- `rawData.biography` is `null` when the candidate page links no `Biografija`
  page (`astrauskas-vytautas` in the 1996 fixture set); otherwise
  `{"text", "birthDate", "birthYear"}` — the full free-text paragraph
  verbatim, plus whatever its opening sentence yields.
- **`normalized.turto-ir-pajamu-deklaracijos` comes from the linked
  `kpdl.htm` page**, parsed by `scraper/shared/deklaracija_archive_1990s.py`
  (shared with the other 1990s archive family). The 1990s form is not the
  modern one, so two things differ from every later era:
  - `privalomas-registruoti-turtas` and `pinigines-lesos` are **always
    null**. The form publishes turtas and piniginės lėšos as one summed
    figure per section, and the modern split is not recoverable from it. The
    combined figures are under `turtas-ir-pinigines-lesos-metu-pradzioje`,
    `turtas-ir-pinigines-lesos-metu-pabaigoje` and
    `kalendoriniais-metais-isigytas-turtas`.
  - `gautos-pajamos` and `sumoketas-pajamu-mokestis` come from section III's
    "20. Iš viso" row, but **only when that row is not smaller than row 1**,
    the employment row printed above it. Where it is smaller the key is null
    and a `DeclarationTotalBelowItsOwnRow` anomaly is written. Row 1 is always
    published as `gautos-pajamos-darbo-santykiu` and
    `sumoketas-pajamu-mokestis-darbo-santykiu`.
  - `valiuta` is `"Lt"`, so the corpus-wide litas→euro conversion applies.
  - Also carried: `israso-data`, `israsa-isdave` (municipal family only — the
    Seimas pages print no issuer), `mokesciu-nepriemoka`,
    `privaloma-sumoketi-mokesciu-ir-sankciju`, `seimos-nariu-skaicius`,
    `islaikytiniu-skaicius`, `seimos-nariu-iki-18-metu`.
  - The key is **absent** when the candidate page links no declaration.
- **`normalized.anketa.gimimo-vieta` is likewise recovered from the biography
  sentence**, and marked `gimimo-vietos-saltinis: "biografijos-tekstas"`. The
  prose prints it in the locative ("Kaune", "Šiaulių rajone") while the corpus
  stores the nominative, and suffix rules cannot settle it alone — `-yje`
  yields both *Panevėžys* and *Radviliškis* — so candidates are accepted only
  if they appear in `scraper/shared/vietovardziai.json`, the place names the
  rest of the corpus uses. That lookup is the precision guard: a mis-parsed
  fragment produces no candidate and is dropped.

  Recovered on **447 of 906** records. Of the 459 without it, 25 have no
  biography and the rest name a village, parish or region the corpus has no
  nominative for, or name no place at all. Cross-checked against the same
  people's later elections, where VRK publishes the field: **all 247
  checkable values name the same place**, though often less specifically —
  the district where a later form gives the village. The country name
  ("Lietuvoje") is refused as too coarse; it was wrong on all three candidates
  who had a specific birthplace published elsewhere.

- **Nothing else is extracted from the biography prose, on purpose.** Education
  and work history look extractable — "1972 m. baigė Vilniaus statybos
  technikumą", "1978-1988 m. dirbo ..." — and match on most records, but
  sampling the matches shows they are not reliable enough to write into
  `issilavinimas` or `darbo-patirtis`: the captures run on into the following
  clause ("25-ąją vidurinę mokyklą ir tais pačiais metais įstojo į..."), stop
  at an abbreviation's period ("Biržų J"), or return a specialty where an
  institution belongs ("transporto remonto ir eksploatacijos specialybę").
  Roughly a third of them are wrong in one of those ways. The full text stays
  in `biografija.tekstas`, which is the honest place for it, on the same
  precedent as the eligibility Q&A this family also declines to normalize.

- **`normalized.anketa.gimimo-data` here is derived from biography prose, not
  read from a field.** These pages publish no birth-date field at all, so the
  biography's opening sentence ("Gimė 1942 m. rugpjūčio 3 d. Panevėžyje") is
  the only source. It is written to the corpus's usual key so the person
  index, `docs/concept-map.json` and the dashboard resolve it with no
  special case, and **`gimimo-data-saltinis: "biografijos-tekstas"` marks the
  provenance** — treat it as a weaker source than every other era's published
  field. `anketa` is omitted entirely when the biography yields nothing.
  - Coverage over the 906 records of this family: 692 full dates (76%), 157
    year-only, 61 neither.
  - `gimimo-metai` holds the year-only cases ("Gimė 1950 m."). A year is
    **never** promoted to a birth date — name plus year would merge namesakes
    wholesale — so those records still group by name alone in the person
    index.
  - Accuracy, measured: of the 149 extracted dates whose candidate shares a
    name with a modern candidate who has a published birth date, 133 (89%)
    match exactly. 13 of the 16 that differ are plainly different people
    (born decades apart); the remaining 3 are genuine disagreements between
    VRK's own biography and questionnaire (Julius Sabatauskas: 1958-03-01 in
    the biography, 1958-04-01 in the modern record), not parse failures. A
    mis-extracted date fails to merge rather than merging wrongly, so the
    failure mode is a split person, not a conflated one.
- No elected data anywhere, same as the 2015 family: these pages carry no
  winner marker, so electedness is not part of the candidate record.
- No income declaration, private-interest declaration, or campaign-finance
  sections exist for this family — VRK published none of that structure on
  these pages in a form worth parsing at fixture scale. This mirrors the
  project's elected-status precedent (`docs/DATASET.md`): a fact that cannot
  be trusted or cheaply parsed is left out and documented, not guessed at.

## Appendix: Municipal archive (`1997-kovo-23-savivaldybiu-tarybu`, `1997-birzelio-29-svenciniu-tarybos-pakartotiniai`)

Records are written as `data/<election-id>/<candidate-id>-<election-id>.json`.
Both share the parser in `scraper/shared/savivaldybiu_archive_1997.py` and the
`19970323` directory (distinguished only by the phase prefix in
`apgtl.htm-<phase>+<municipality>.htm` — `3` for the general election, `5` for
the Švenčionys repeat). Like the Seimas archive above, this family predates
the 2016+ anketa-tab shape, but its normalized record slots into the shared
body cleanly: the per-candidate facts land in `anketa` under the same
kebab-case concept keys the 2015 and 2016 eras use, so
`docs/concept-map.json`, `scripts/build_person_index.py` and the dashboard's
field map all resolve them with no election-specific case.

- `rawData` section order: `profile`, `candidacy`, `personal`. `normalized`
  order: `profilis`, `kandidatavimas`, `anketa`.
- `normalized.anketa` carries `gimimo-data`, `gimimo-vieta`,
  `gyvenamoji-vieta`, `tautybe`, `issilavinimas`, `uzsienio-kalbos`,
  `pagrindine-darboviete`, `visuomenine-veikla`, `seimine-padetis` and
  `seimos-nariai`. **`gimimo-data` is normalized from the source's
  `1944 03 04` to the corpus's `1944-03-04`** (in `rawData.personal` too):
  every era from 2015 on writes the hyphenated form, and
  `scripts/build_person_index.py` keys identity on the literal string, so the
  un-normalized form silently prevented all cross-era matching — 949 people
  who stood here and in a later election were split in two until this landed.
- Most candidates omit some labels — only 582 of the 6,276 in the general
  election print `Gimimo vieta`, for instance — so a field's value ends at
  whichever label comes next, not at a fixed successor. Getting that wrong
  put `1945 04 17 Gyvenamoji vieta: Kaunas Tautybė: Lietuvis (-ė)` into 91%
  of birth dates; `abariunas-bronius` is the fixture that guards it. Note the last two: the source label reads *Šeimyninė
  padėtis*, but the key is the corpus's `seimine-padetis`, and
  `seimos-nariai` is a list of `{name, relation}` rather than the
  `sutuoktinio-vardas-pavarde`/`vaiku-vardai-pavardes` split later eras use.
- `normalized.kandidatavimas` is a single object here (contrast the Seimas
  archive's list): `savivaldybe`, `savivaldybes-numeris`,
  `savivaldybes-nuoroda`, `iskele`, `iskele-nuoroda`, `numeris-sarase`.
- `rawData.candidacy` is a single object (not a list — this family has no
  multi-mandate-list concept): `{municipalityName, municipalityNumber,
  municipalityUrl, nominator, nominatorUrl, listNumber}`.
- `rawData.personal` is this family's distinguishing richness over the Seimas
  archive: `birthDate`, `birthPlace`, `residence`, `nationality`, `education`,
  `foreignLanguages` (list), `mainWorkplace`, `publicActivity`,
  `familyStatus`, `familyMembers` (list of `{name, relation}`) — all plain
  labelled paragraphs on `kandvl.htm`, no comment-corruption quirk here. Any
  field genuinely absent from the source page (no matching label at all, not
  just an empty answer) normalizes to `null`/`[]` rather than an empty
  string — `pilvelis-algirdas`'s page has no "Tautybė:" line at all, for
  example, and `normalized.anketa.tautybe` is `null` for that
  record.
- `rawData.profile` holds only `candidateDisplayName` and
  `incomeDeclarationUrl` — no photo field, since this family's candidate pages
  carry no portrait.
- **`normalized.turto-ir-pajamu-deklaracijos` comes from the linked
  `kpdl.htm` page**, parsed by `scraper/shared/deklaracija_archive_1990s.py`
  (shared with the other 1990s archive family). The 1990s form is not the
  modern one, so two things differ from every later era:
  - `privalomas-registruoti-turtas` and `pinigines-lesos` are **always
    null**. The form publishes turtas and piniginės lėšos as one summed
    figure per section, and the modern split is not recoverable from it. The
    combined figures are under `turtas-ir-pinigines-lesos-metu-pradzioje`,
    `turtas-ir-pinigines-lesos-metu-pabaigoje` and
    `kalendoriniais-metais-isigytas-turtas`.
  - `gautos-pajamos` and `sumoketas-pajamu-mokestis` come from section III's
    "20. Iš viso" row, but **only when that row is not smaller than row 1**,
    the employment row printed above it. Where it is smaller the key is null
    and a `DeclarationTotalBelowItsOwnRow` anomaly is written. Row 1 is always
    published as `gautos-pajamos-darbo-santykiu` and
    `sumoketas-pajamu-mokestis-darbo-santykiu`.
  - `valiuta` is `"Lt"`, so the corpus-wide litas→euro conversion applies.
  - Also carried: `israso-data`, `israsa-isdave` (municipal family only — the
    Seimas pages print no issuer), `mokesciu-nepriemoka`,
    `privaloma-sumoketi-mokesciu-ir-sankciju`, `seimos-nariu-skaicius`,
    `islaikytiniu-skaicius`, `seimos-nariu-iki-18-metu`.
  - The key is **absent** when the candidate page links no declaration.
  **This election is the one where that total is usually wrong**: measured over
  all 5,477 of its declarations, the "Iš viso" row prints a figure below row 1
  on **4,463** of them (99% of those print 0) and on 4,134 for tax — so most of
  its records carry a null `gautos-pajamos` and a populated
  `gautos-pajamos-darbo-santykiu`. The same failure appears, rarely, elsewhere:
  9 of 879 in 1996 and 1 of 108 in Švenčionys.
- No elected data, no biography subpage, no private-interest or
  campaign-finance sections — same scope decision as the Seimas archive
  appendix above.
- `normalized.anketa.issilavinimas` is the corpus's education object,
  `{"aprasas", "irasai": [...]}`, like every era from 2007 on. These pages
  publish a single level from a controlled list ("Aukštasis",
  "Aukštesnysis", "Specialus vidurinis", "Vidurinis", "Nebaigtas aukštasis",
  "Nebaigtas vidurinis", "Aspirantūra", "Doktorantūra"), which is exactly the
  modern entry's own `issilavinimas` field, so it goes there and
  `mokymo-istaigos-pavadinimas`, `specialybe` and `baigimo-metai` are null —
  this era never published them. It was a bare string until 2026-08-22, the
  one concept in the corpus with two shapes; records already on disk were
  reshaped in place by `scripts/reshape_1997_education.py`.
- 46 candidate name collisions in the 6,276-candidate general election
  resolve with the corpus's standard positional `-2` suffix; see
  `docs/CLI_REFERENCE.md`'s municipal archive section for the concrete pair.

## Appendix: 2004 European Parliament (`2004-ep`)

Lithuania's first EP election, published on VRK's original 2004 static site
— a layout family of its own, read by `scraper/elections/ep_2004/`, whose
records keep the corpus's sections and keys. Written as
`data/2004-ep/<candidate-id>-2004-ep.json` with four sections in both
layers: `profilis`/`profile`, `anketa`, `biografija`,
`turto-ir-pajamu-deklaracijos`/`turtoIrPajamuDeklaracijos`. There is no
private-interest declaration, no `kita` and no campaign section: the 2004
pages publish none of them. What is this election's own:

### `kandidatavimas`

The 2009/2014 EP shape — `vrkCandidateId`, `roles: ["daugiamandate"]`,
`vienmandate: null`, `daugiamandate` (`sarasas`, `sarasoNumeris` = VRK's
list number, `sarasoId` = the list page's id, `numerisSarase`), the
results join (`isrinktas`, `isrinktasKaip: "daugiamandate"`,
`rezultatuSaltinis` = the members page) — plus three keys from the list's
post-preference ranking page, on every record:
`porinkiminisNumerisSarase` (the rank after preference votes),
`pirmumoBalsai` (the preference votes) and `pirmumoBalsuSaltinis` (the
page). The modern cards print the rank (`porinkiminis-numeris-sarase` in
`profilis.kita`); here it is a results-tree join, so it lives with the
other joined facts.

Two records carry the one post-election substitution VRK's members page
names in a footnote. Prunskienė (VNDPS, list 1, position 1, 48,852
preference votes) has `isrinktas: true` and `mandatasNutrauktas` —
`decision` (`label` "VRK 2004 m. birželio 21 d. sprendimu Nr. 180", `url`
on lrs.lt), `statementUrl` (her statement, a scanned image on VRK),
`replacedBy: "260979"` and the footnote's `note`. Didžiokas (the same list's
second) has `isrinktas: true`, `pakeiteNari: "260978"` and `vrkSprendimas`
(decision Nr. 181, by which VRK recognised him as the member elected under
the list). Fourteen records are elected for thirteen seats; `isrinktas` is
a plain false on the other 227 (the results file exists, so unknown is not
an option).

### `profilis`

`vardas-pavarde` from the page's second heading ("Justas Vincas
PALECKIS"), `pastaba` always null (no winner mark on any page),
`nuotrauka` a VRK URL under `2004/euro/nuotraukos/`, and `kita` with
exactly two keys on every record: `iskele` (the nominating list, linking
its page) and `priesrinkiminis-numeris-sarase` (the pre-election position,
as text). The card's Biografija / Pajamų links are the page-set, not
fields.

### `normalized.anketa`

The 2009 EP key set (`ep_2009`'s normalizer one form earlier — see that
appendix), with these differences:

- `gimimo-data` is Q3 and the page prints it dotted (`1942.01.01`);
  normalized is the ISO form (`1942-01-01`, the person index's key),
  `rawData.anketa.rows` keeps the page's text.
- `pareiskimai`: `ar-turite-kitos-valstybes-pilietybe`,
  `kitos-valstybes-pilietybe-valstybe` and
  `ar-atimta-balsavimo-teise-kitoje-valstybeje` are Q8.4 / 8.4.1 / 8.4.2
  here (the 2009 form's 8.3 block; there is no 8.3), the other keys Q8.1,
  8.2 and 9.1–9.3 as in 2009. Answers are the form's third-person wording
  — `Neturi`/`Turi`, `Nėra`/`Yra`, `Nebuvo`/`Buvo` — kept as published.
  `teisiniai-argumentai` is the unlabelled emphasised row the page prints
  right after 9.3 when the candidate wrote an explanation (five records;
  each under a `Yra`/`Buvo` answer).
- `issilavinimas.irasai` columns are the 2004 headings:
  `issilavinimas`, `mokyklos-istaigos-pavadinimas`, `specialybe`,
  `baigimo-metai` (2009+: `mokymo-istaigos-pavadinimas`). `aprasas` is
  always null (the question has no free-text form). `mokslo-laipsnis` and
  `pedagoginis-vardas` come from the two "Moksliniai laipsniai:" /
  "Moksliniai vardai:" pairs after the table (78 and 28 non-null).
- A list-type answer (Q13 languages, Q18 hobbies, Q20 children) is one
  `<b>` per item on the page; the row's `answer` is the items joined with
  ", " (so `pomegiai` and `vaiku-vardai-pavardes` read as every other
  era's), `uzsienio-kalbos` is the split list, and the row in
  `rawData.anketa.rows` keeps the items as `answerItems` when there were
  several.
- An unanswered question is printed with an empty `<b>`: the row exists
  with an empty answer and the key is null. One page (Šiškauskienė) omits
  Q19, the spouse line and Q20 altogether — null as well.

### `biografija`

`tekstas` is the blockquote's one paragraph, which on most pages opens
with the name and the nominator in capitals ("JUSTAS VINCAS PALECKIS
KANDIDATAS Į EUROPOS PARLAMENTĄ, IŠKELTAS …") before the prose;
`rawData.biografija.html` is the blockquote.

### `turto-ir-pajamu-deklaracijos`

The corpus's seven amount keys in litas (`valiuta: "Lt"`, `pastaba` null —
the page has no note paragraph), read from the two extracts of the
declarations page:

- The asset extract is either the **family** form ("METINĖ ŠEIMOS TURTO
  DEKLARACIJA", 144 records) or the **individual** form ("METINĖ
  GYVENTOJO TURTO DEKLARACIJA", 97), sections I–V with one total each —
  `privalomas-registruoti-turtas` … `gautos-paskolos`. A "-" total is
  null (nothing declared under that section), never zero.
- The income extract prints one income/tax pair for each of the five
  FR0462 form variants VRK knew of (FR0462, S33, S15, S0, S); the
  candidate filed one, occasionally two or three (Platelis: FR0462, S33
  and S15), the rest "-". `gautos-pajamos` and `sumoketas-pajamu-mokestis`
  are the sums of the filed lines; `pajamos-pagal-forma` keeps the five
  lines (`forma`, `gautos-pajamos`, `sumoketas-pajamu-mokestis`, null
  where "-"). Five records filed on no form at all: null, not zero.
- `israsai.turto-deklaracija` / `israsai.pajamu-deklaracija` carry what the
  page prints above and below each table: `pavadinimas` (the extract's
  title, which is how the family/individual form is told apart),
  `israsa-isdave` (the issuing tax office), `gavimo-data` and
  `pildymo-data` (ISO), and `darboviete` (the form's "3. Darbovietė").

`rawData.turtoIrPajamuDeklaracijos.sections` is the two extracts with their
`title`, `issuer`, `receivedDate` and `items` as the page labels them — the
roman section heading as the key of its total (with the page's row label,
"Visa šeimos turto vertė", as `label`), and the form line ("1) FR0462
formos deklaracijos") as a three-field item (`form`, `income`, `tax`).

## Appendix: 2007–2014 national elections (`2007-spalio-7-seimo-dzukija`, `2008-seimo`, `2009-prezidento`, `2009-ep`, `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai`, `2011-vasario-13-seimo-marijampole`, `2012-seimo`, `2013-kovo-3-seimo-birzai-zarasai-ukmerge`, `2014-prezidento`, `2014-ep`)

All ten are the 2015-era static layout described in the 2015 Seimo
by-elections appendix, and every era shape there applies: no elected markers
on the pages (`profilis.pastaba` is null on every record; `isrinktas` is the
results join — 141 Seimas members in 2008 and 139 in 2012 from VRK's
elected-members pages, 70 list and 71/69 constituency seats, the 2007
Dzūkija winner, the 2 + 1 by-election winners of November 2009 and
February 2011, the 3 constituency winners of 2013, the
12 MEPs of 2009 and 11 of 2014, the two presidents), URL photos, litas amounts with
`valiuta`/`pastaba`, the retained spouse block, the campaign additions.
Records are written as `data/<election-id>/<candidate-id>-<election-id>.json`
in the corpus's section order, with one insertion for the 2014 presidential
election (`patiketiniai` between `privaciu-interesu-deklaracija` and the
campaign section). What is this group's own:

### `kandidatavimas` (2007, 2008, 2012, 2013, the 2009 and 2011 by-elections, 2009 and 2014 EP)

The listing-only facts, under one shape for all three:

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

- `roles` is in first-seen order (lists are walked before constituencies).
  The 2013 election has `vienmandate` only, the EP election `daugiamandate`
  only, and the respective other slot is null. 2012 has all three
  combinations: 929 dual, 949 list-only, 49 constituency-only.
- `vienmandate.iskele` is the constituency listing's "Iškėlė" column
  verbatim: a party, `Išsikėlė pats`, or both in one cell
  (`"…demokratai, išsikėlė pats"`) when a party nominated someone who had
  also self-nominated.
- 2012 coalition-list candidates carry `daugiamandate.koalicijosPartija`,
  the member party the coalition's list page names on the row; every other
  list row has no such key.
- `sarasoId` is the list page's `RinkimuOrganizacija` id (2012 ids carry
  the page's `_1`/`_2` suffix, `"4136-1"`). `numerisSarase` is null where
  the list page prints an empty position cell — six 2012 rows, candidates
  VRK kept on the page (and in the declared count) without a number.
- The presidential election has no listing-derived block; the results join
  gives it the minimal one (`vrkCandidateId`, `isrinktas`, `isrinktasKaip:
  "prezidentas"`, `rezultatuTuras: 2` for the winner).

### `profilis.kita` per election

- **2012 Seimo**: one `apygarda`/`iskele` pair per candidacy in card order
  — single-member first (`apygarda` = `"Vilkaviškio (Nr.68)"` with the
  constituency link), then `apygarda-2` = `"Daugiamandatė"`, `iskele-2`
  linking the list page, `numeris-sarase`. A list-only card has the
  multi-member block alone, so there `apygarda` is `"Daugiamandatė"`. The
  results links are standalone anchors keyed by their label:
  `daugiamandateje-apygardoje` (the list's preference votes page),
  `i-turas` and, where a second round was held, `ii-turas` (the
  constituency results pages). Coalition nominees add `iskele-3` =
  `"(Iškėlė"` for the member party.
- **2007 Dzūkija**: the family's oldest card, read by the era parser's
  legacy-card branch: `apygarda` ("Dzūkijos rinkimų apygarda (Nr. 69)",
  as the header table prints it) and `iskele` from the header table above
  the card, `gimimo-data` (the card's own line — the form asks no Q5, and
  the same value is folded into `anketa.gimimo-data`), then either the
  campaign link (`politines-kampanijos-dalyvio-duomenys`, unqualified) or,
  for the six represented candidates, a valueless
  `kandidatas-nera-savarankiskas-politines-kampanijos-dalyvis`, and the
  `i-turas`/`ii-turas` results links.
- **2008 Seimo**: as 2012 — one `apygarda`/`iskele` pair per candidacy,
  `numeris-sarase`, the results links, `iskele-3` for a coalition
  nominee's member party — but **no campaign link**: the 2008 candidate
  pages do not link a participant page.
- **2013**: `apygarda`, `iskele`, the campaign link, `i-turas`, and
  `ii-turas` for the six candidates who went to a second round.
- **2009 and 2011 by-elections**: `apygarda`, `iskele` and the campaign
  link only — these cards carry no results links.
- **2014 presidential**: only the campaign link — presidential candidates
  are self-nominated and the card states no constituency or list. Note the
  link targets election path `423_lt`, VRK's id for the campaign, not the
  candidate pages' `424_lt`.
- **2009 presidential**: the campaign link (under the candidate pages' own
  `403_lt`) and, for five of the seven, the candidate's campaign website —
  a bare link in the card, so it is keyed by its own text
  (`www-grybauskaite2009-lt`: `pavadinimas` the link text, `reiksme` null,
  `nuorodos` the URL). The only cards in the corpus that carry one.
- **2014 EP**: `iskele` (linking the list page), `numeris-sarase`, the
  campaign link; the coalition nominee adds `iskele-2` / `numeris-sarase-2`.
- **2009 EP**: `iskele` (linking the list page), `numeris-sarase`, the
  campaign link — the party's participant page, the same one on every
  candidate of a list.

### `normalized.anketa` per election type

- **Seimo (2007, 2008, 2012, 2013, the 2009/2011 by-elections)**: the 2015 Seimo key set with one addition in
  `pareiskimai`, `ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo`
  (Q9.3, conviction for a grave or very grave crime). Every 2013 form holds
  VRK's `Nenurodė` default for it (null normalized, literal in the raw row);
  2012 forms answer it. Q16 and Q17 share one text run on these pages and
  split correctly at the question number. Sparse forms omit unanswered
  lines altogether (Q12–Q15 can be absent), which is what a null
  `issilavinimas.irasai`/`uzsienio-kalbos` means.
- **Presidential (2014)**: `pareiskimai` is the Prezidento rinkimų
  įstatymo 2 str. set — `ar-esate-pilietis-pagal-kilme`,
  `ar-gyvenate-lietuvoje-trejus-metus`, `ar-galite-buti-renkamas-seimo-nariu`
  (this election's own), then `ar-nebaigta-teismo-paskirta-bausme`,
  `ar-atliekate-karo-tarnyba`, `ar-turite-kitos-valstybes-pilietybe`,
  `ar-susijes-priesaika-uzsienio-valstybei`. Birthplace, nationality and
  education are Q9–Q11; `pedagoginis-vardas` is the unnumbered combined
  academic-title line, under the key the 2016 Seimo pages use for the same
  line; there is no `anksciau-isrinktas`.
- **European Parliament (2014)**: `gimimo-data` is Q3. `pareiskimai` adds
  `kitos-valstybes-pilietybe-valstybe` (Q8.3.1, null on every fixture —
  all answer `Nenurodė`), `ar-atimta-balsavimo-teise-kitoje-valstybeje`
  (Q8.3.2) and `ar-buvote-pripazintas-kaltu-del-sunkaus-nusikaltimo` (Q9.3);
  there is no `kita-apie-save` (no Q21).
- **European Parliament (2009)**: the 2014 EP key set with `gimimo-data`
  back at Q5, plus `mokslo-laipsnis` and `pedagoginis-vardas` (one line on
  the page, "…mokslo laipsnį …, vardą …"), `kita-apie-save` (Q21, which
  2014 dropped) and `pareiskimai.teisiniai-argumentai` — the Q9 block's
  free-text line for anyone who answered "Taip" ("Tuo atveju, jei bent į
  vieną 9 punkto klausimą atsakėte Taip … paaiškinimą įrašykite čia"),
  under the 2016 Seimo key for the same slot. The 2012 Seimo pages carry
  that line too (24 candidates wrote into it; the key is null on every
  2013 record, whose form no longer asks), so `normalize_seimo_2012_anketa_rows`
  reads it as well.
- **Presidential (2009)**: the 2014 form one revision earlier.
  `pareiskimai` is `ar-nebaigta-teismo-paskirta-bausme`,
  `ar-atliekate-karo-tarnyba`, `ar-turite-kitos-valstybes-pilietybe`,
  `ar-susijes-priesaika-uzsienio-valstybei` (Q8.1–8.4; the three
  citizenship/residence/eligibility questions 2014 opens with were not
  asked yet) and `ar-bendradarbiavote-su-uzsienio-tarnybomis` — Q9, the
  Prezidento rinkimų įstatymo 3 str. lustration question (service in,
  schooling by or collaboration with the NKVD/NKGB/MGB/KGB and equivalent
  foreign services), under the key the Seimo and EP forms use for their
  narrower "knowingly collaborated with other states' special services"
  wording. Birthplace, nationality and education are Q10–Q12;
  `mokslo-laipsnis` is the unnumbered line after the education table,
  which here asks for the degree only (no pedagogical title, so not
  `pedagoginis-vardas`); `anksciau-isrinktas` *is* asked (Q15, the 2015
  Seimo shape, empty list for the two candidates with no prior mandate).
  The page omits a question it has no answer for — Q7 everywhere, Q15 for
  two candidates, Q20 and the spouse line for the unmarried, the degree
  line for five — so a null there is an absent row.

### `patiketiniai` (2014 presidential only)

The trustees tab, a list of `{numeris, vardas-pavarde}` in the page's order
(7 to 114 per candidate); a `Duomenų nėra` page is an empty list, and the
key is absent from every other election's records. The 2009 pages link the
same tab but VRK never published the file behind it (every
`Kandidato<ID>Patiketiniai.html` is a 404), so the 2009 records have no
`patiketiniai` key; the link is recorded under `unpublishedTabs` in the
fixture's `index.json`.

### `privaciu-interesu-deklaracija` (2007–2009: the roman-numbered forms)

The 2007–2009 interest declarations predate the `ID001x` sections. The
2007 and 2008 form's sections are `ii-turtas`, `iii-pajamos`,
`iv-vertybiniai-popieriai`, `v-turtines-prievoles`,
`vi-individualios-imones-kitos-organizacijos-ir-istaigos`, `ix-naryste-…`
and `x-asmenys-del-kuriu-gali-kilti-viesuju-ir-privaciu-interesu-konfliktas`,
after a spouse card keyed `deklaruojanciojo-asmens-sutuoktinis-partneris`
(2009: `deklaruojancio-…`), each present only when filed. Each is a
**list of records** keyed by the table's column names — `ii-turtas` rows
are `tipas`, `vienetu-skaicius`, `vietoves-pavadinimas`, `isigijimo-budas`;
`iii-pajamos` rows `tipas` and `pajamu-saltinio-pavadinimas` — so two
flats or two employers are two rows. (Until 2026-08-22 these tables were
read as key/value pairs: the column-name row, bold cells rather than
`<th>`, was not recognised as one, so a section collapsed to its first
column with the last row winning and a spurious `tipas` entry; see
DATASET.md.) The 2009 declaration (both elections) after the declarant and spouse cards come roman-numbered
sections — `ii-dalyvavimas-juridiniuose-asmenyse`, `iii-individuali-veikla`,
`iv-naryste-pareigos-imonese-istaigose-asociacijose-ar-fonduose`,
`v-gautos-dovanos`, `vii-sandoriai`,
`viii-fiziniai-ar-juridiniai-asmenys-del-kuriu-gali-kilti-interesu-konfliktas`
— each a list of records keyed by the section's column headings and
present only when the candidate filed something under it (the presidential
seven use II, IV and VII only). Transactions and gifts carry a
`sandorio-vertes-litais-kodas` value-band code ("001"–"012") where the
later form has sums; `suma-skaiciais` and `suma-zodziais` are blank on
every row. Unique to 2009.

### Declarations

`turto-ir-pajamu-deklaracijos` keeps the seven keys plus `valiuta: "Lt"`.
`pastaba` names the period on the 2012 and 2013 pages ("nuo 2011-01-01 iki
2011-12-31" for both — the 2013 repeat reused the 2012 declarations) and is
null on the 2009 and 2014 pages, whose note paragraph is empty. The income
row cites "GPM308 formos 12, 13, 13A, 14, 20 laukelių … V13 laukelių suma"
on the 2012–2014 pages (2015 Seimo: "…14, 22 … V13 laukelio"); the 2009
pages — and, it turned out, the whole 2015 municipal family — extract the
earlier **GPM305** form ("GPM305 formos 12, 13, 14 ir GPM305V formos V14
laukelių suma" / "…27,28,30 laukelių suma"); the 2007 pages the interim
**GPM302** form one older still ("12, 13, 14 ir 15 laukelių bei GPM302V
priedo V14 laukelio suma" / "Išskaičiuota mokesčio suma (36 laukelio
suma)"). All four resolve to `gautos-pajamos` / `sumoketas-pajamu-mokestis`.

### Campaign pages (2009)

The 2008 records have no campaign section at all — the candidate pages
link no participant page, though VRK's participants index for the
election exists. The 2007 pages link one for the four independent
candidates (the same `<td><strong>`-headed tables as 2009); the six
represented candidates' cards say "Kandidatas nėra savarankiškas
politinės kampanijos dalyvis" and link nothing. The 2009 participant pages (both elections) are one
revision older than 2012's. In the EP election the participant is the party, linked from every
candidate of its list, so 24 candidates share one campaign record. Their
tables head columns with `<td><strong>` rather than `<th>`; the donor list
is a single "Aukotojų sąrašas" section (`aukos-pagal-sekcija.aukotoju-sarasas`,
columns `rowNumber`, `donor`, `municipality`, `amountLt`, `date`) with no
separate "Nepriimtinos aukos" section — an unacceptable donation is flagged
inline after the donor's name (", nepriimtina auka", once ", auka
nepriimtina", once with VRK's typo "nepriintina"), and the flag is moved to
`notes`, the key the later pages' notes column uses; the totals row carries
the full column count, label in an inner cell. Financing reports have a
kind instead of a verification status: `reportType` ("Pradinė"/"Galutinė")
alongside a null `status`, the key present on 2009 rows only. A company
auditor is labelled "Pavadinimas"/"Kodas" (→ `imones-pavadinimas`/
`imones-kodas`); two of the seven presidential candidates have one, the
other five an empty auditor table. No contracts tab content in either
election.

In the totals (`suvestine`) of every election in this family the sums are
now keyed by the table's own amount columns — `amountLt` on the litas-only
2009–2014 pages, both on the March 2015 pages, `amountEur` on the later
2015 ones. Until 2026-08-22 a positional read filed every litas-only total
under `amountEur` and lost the "Nuo 2012-01-01 draudžiamos" note; see
`DATASET.md`.

### Sitemap cross-checks (`sitemaps/2012-seimo.json`, `sitemaps/2008-seimo.json`)

The 2012 sitemap's `stats` record what was reconciled against VRK's own
index before the merge was trusted; read them rather than assuming zero
(2008's figures in parentheses where they differ):

- `listCandidacies` = `declaredListCandidates` (1,878; 2008: 1,583) and
  `listCountMismatches` = 0: every list page holds exactly as many
  candidates as the index declares for it.
- `listDistrictJoinMismatch` = 0 over the rows that have a constituency
  column; `listRowsWithoutDistrictColumn` = 135 (2008: 130) is the
  coalition list page, which shows the member party in that column's place.
- `districtOnlyReconciled`: the "tik vienmandatėse" side pages hold
  `sidePageDistrictOnlyIds` (52) distinct people, `sidePageIdsAlsoOnLists`
  (3) of whom also hold a list seat, and the difference equals
  `districtOnlyCandidates` (49). `sidePageDistrictOnlyDeclared` (58) is the
  index's figure and is *not* expected to match: the self-nominated page
  declares 36 but lists 31, the withdrawn having left the page but not the
  count. The 2008 index has no self-nominated page at all, so
  `selfNominatedNotOnSidePages` (15) counts the constituency pages' own
  "Išsikėlė pats" rows towards the 20 district-only candidates (5 from the
  two "tik vienmandatėse" pages); it is 0 for 2012.

### Ids

Name slugs with the 2016 Seimo module's positional `-2` suffix for
collisions (two in 2008: two Arūnas RIMKUS on different lists, and two
Algis KAŠĖTA standing against each other in Varėnos–Eišiškių; one in
2012: two Arūnas MARKŪNAS on different lists; none in the other five). The listing pages are static archives, so traversal order
— lists in index order, then constituencies in index order — is stable.
