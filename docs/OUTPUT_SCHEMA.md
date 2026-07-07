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
- Biography in 2020 is intentionally simplified: no raw `text`/`html` and no section-kind wrappers; normalized 2020 biography no longer stores `tekstas`/`sekcijos`.

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
