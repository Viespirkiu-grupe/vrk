# Output Schema (2016 Seimo)

This document describes the current output shape produced by:

```bash
python -m scraper parse-anketa-samples 2016-seimo
```

Scope note: this page is election-specific.
`2016-seimo` and `2020-seimo` use separate scraper modules because their HTML differs, so schema details here should not be treated as a shared cross-election contract.

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
- `photoSrc`
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
- Placeholder strings like `Nenurode` are converted to null values by normalization logic.
- Campaign section is omitted when candidate has no campaign participant tab.
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
  list of records.
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
anketa — those live on the biography tab and are normalized under `biografija`.

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

## Appendix: 2025 mayors (`2025-kovo-16-meru`)

Records are written as
`data/2025-kovo-16-meru/<candidate-id>-2025-kovo-16-meru.json`. This is the only
election whose record carries an extra top-level field:

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
