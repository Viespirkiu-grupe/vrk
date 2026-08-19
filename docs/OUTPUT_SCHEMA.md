# Output Schema

This document is the record contract for the whole corpus. The body describes
the common record envelope and the shared normalized shapes that hold across
all nineteen elections; one appendix per election covers everything
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

These shapes are verified identical across all nineteen elections; the
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

The key set is identical in 19/19 elections at 100% presence. Values are
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

## Appendix: 2015 Seimo by-election (`2015-kovo-1-seimo-zirmunai`)

Records are written as
`data/2015-kovo-1-seimo-zirmunai/<candidate-id>-2015-kovo-1-seimo-zirmunai.json`
with the same top-level fields and the corpus's section order (`profilis`,
`anketa`, `biografija`, `turto-ir-pajamu-deklaracijos`,
`privaciu-interesu-deklaracija`, `politines-kampanijos-dalyvio-duomenys`,
`kita`). The pages are the pre-2016 static layout — the oldest family in the
repository — so several record shapes are this era's own:

- **No elected data anywhere.** The 2015 pages carry no `(V)` suffix, no blue
  anchors and no elected note, so `profilis.pastaba` is null on every record,
  the winner's included. Electedness for this era can only come from VRK's
  results pages and is not part of the candidate record.
- `profilis.nuotrauka` is a URL to an external JPG
  (`Kandidato<ID>Foto.jpg`) — this era never embedded base64 photos.
  `profilis.kita` holds `apygarda` and `iskele`, plus a
  `savarankisko-`/`atstovaujamojo-politines-kampanijos-dalyvio-duomenys` entry
  whose link is the campaign participant page.
- `normalized.anketa` carries the 2015 Seimo question set: the 2016 keys minus
  `pedagoginis-vardas`, and `pareiskimai` stops at `ar-buvote-pripazintas-kaltu`
  (Q9.2) — the 9.3.x follow-ups do not exist yet. `kita-apie-save` (Q21) is
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
