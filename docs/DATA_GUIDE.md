# Data Guide

The consumer entry point to the corpus: everything a third party needs to
query 90,195 candidate records across 43 Lithuanian elections (1996–2025)
without reading the per-election schema appendices first. Every path and
count on this page was verified against the full corpus on 2026-08-19; the
election and record totals were refreshed on 2026-08-21 when the 2012–2014
elections joined and on 2026-08-22 for the 2007–2011 Seimo by-elections, the 2008 Seimo, the two
2009 elections and the 2011 municipal general, and on 2026-08-23 for the
2007 municipal general (see DATASET.md).

Records live at `data/<election-id>/<candidateId>-<electionId>.json`, one
file per candidacy. `data/` is not version controlled; see
[DATASET.md](DATASET.md) for the inventory and how to regenerate it.

## Record anatomy

Six top-level fields on every record:

- `electionId`, `candidateId`, `candidateName`
- `source` — the VRK page URL(s) the record was parsed from
- `rawData` — source-close parse of the page, camelCase sections
  (`profile`, `anketa`, `turtoIrPajamuDeklaracijos`, …)
- `normalized` — the analysis-ready layer, Lithuanian kebab-case sections
  (`profilis`, `anketa`, `biografija`, `turto-ir-pajamu-deklaracijos`,
  `privaciu-interesu-deklaracija`, `politines-kampanijos-dalyvio-duomenys`,
  `kita`)

Query `normalized`; fall back to `rawData` when you need the verbatim source
text (nearly every normalized value is traceable to a byte-identical string
there). Sections can be absent — two records are missing sections upstream
(`gintaras-binkauskas-2016-seimo` has no `biografija`;
`jonas-korsakas-2020-seimo` has neither `biografija` nor
`turto-ir-pajamu-deklaracijos`) — so do not assume fixed section presence.

The municipal elections extend the envelope: `candidateNote` (both municipal
generals and `2025-kovo-16-meru`) and `kandidatavimas` (the two municipal
generals only) — a camelCase block carrying municipality, role(s), party
list (`tarybosNarys.partyList.{id, number, name}`), list positions and
per-role `elected` flags.

## Cross-election invariants

**Money.** `turto-ir-pajamu-deklaracijos` carries the same seven keys in all
20 elections, at 100% presence:

- `privalomas-registruoti-turtas`
- `vertybiniai-popieriai-meno-kuriniai-juvelyriniai-dirbiniai`
- `pinigines-lesos`
- `suteiktos-paskolos`
- `gautos-paskolos`
- `gautos-pajamos`
- `sumoketas-pajamu-mokestis`

Values are parsed numbers in EUR — never strings — and `null` where VRK's
own page renders the figure malformed (e.g. `,35 EUR` with the integer part
missing; the source text stays in `rawData`).

**Conviction declaration.**
`anketa.pareiskimai.ar-buvote-pripazintas-kaltu` is the yes/no field to
count on, present in 19 of 20 elections — the 2019 presidential
questionnaire asks constitutional eligibility questions instead and has no
conviction declaration. Structured conviction *details* are another matter;
see the traps below.

**Elected.** A candidate was elected iff `profilis.pastaba` starts with
`Išrink` (`Išrinktas…`/`Išrinkta…`) **or** `kandidatavimas.isrinktas` is
`true`. The second form is the 2012–2015 family, whose pages mark no winner:
there `pastaba` is always null and the flag is joined in from VRK's results
trees (`isrinktasKaip` names the seat, `rezultatuSaltinis` the page; a
`false` means the results were consulted and the candidate is not among the
winners, a `null` that no results file exists). Three traps:

- *Presidential:* `pastaba` is non-null for every candidate (`Dalyvavo
  I ture` and the like), so non-null ≠ elected there.
- *Party names:* the note inflects the party into the genitive (`Išrinkta
  pagal Demokratų sąjungos „Vardan Lietuvos“ sąrašą`) — never match parties
  against this string. In the municipal generals use `kandidatavimas`
  instead: per-role `elected` flags, and join lists on
  `kandidatavimas.tarybosNarys.partyList.id`, not on the name.
- *Annulled results:* 48 March 2015 council winners in Šilutė and Trakai
  carry `kandidatavimas.rezultataiPanaikinti` (the VRK decision) and
  `isrinktas: false` — VRK's results page named them, its decision unmade
  it, and the June repeat elections' records hold the seats actually won.

**Placeholders.** Exactly three placeholder forms normalize to `null`:
`Nenurodė`, `-`, and the empty string. A `null` means "not answered on the
page"; the source text is always in `rawData`. Candidate-*typed* variants
survive verbatim as answers — `Nėra`, `nėra`, `Nenurodyta`, `Nenurodoma`,
`--`, `.` and similar — because an answered "none" is not the same as
unanswered. Account for them when counting.

## The era map: concept → path

The questionnaire moved between VRK page eras, so the same concept lives
under different paths. The machine-readable bridge is
[concept-map.json](concept-map.json) — per concept, the exact normalized
path for each election id.

**The table below covers the two modern eras only — 20 of the corpus's 42
elections.** `concept-map.json` is the authority and is the thing to read
programmatically; this table is a human summary of the 2016 and 2020 eras.
The twenty-three pre-2016 elections (six 2007–2011, four 2012–2014, six 2015, five 1996-1998, the 2007 and 2011 municipal generals)
are mapped in `concept-map.json` but not summarized here: the 2012–2015
family and the 1997 municipal archive both resolve most concepts under
`anketa.*` with the same kebab-case keys as the 2016 era, while the 1996-1998 Seimas archive publishes
almost none of these concepts at all (see its `docs/OUTPUT_SCHEMA.md`
appendix).

The two era groups:

- **2016 era** (9): `2016-seimo`, `2017-balandzio-23-meru`,
  `2017-balandzio-23-seimo-anyksciai-panevezys`,
  `2017-rugsejo-10-marijampoles-mero`, `2018-rugsejo-16-seimo-zanavykai`,
  `2019-ep`, `2019-kovo-3-savivaldybiu-tarybu`, `2019-prezidento`,
  `2019-rugsejo-8-seimo`
- **2020 era** (11): `2020-seimo`, `2021-balandzio-11-radviliskio-mero`,
  `2021-spalio-10-meru`, `2023-geguzes-7-visagino-mero`,
  `2023-kovo-5-savivaldybiu-tarybu-ir-meru`,
  `2023-rugsejo-3-seimo-raseiniai-kedainiai`, `2023-spalio-8-kupiskio-mero`,
  `2024-ep`, `2024-prezidento`, `2024-seimo`, `2025-kovo-16-meru`

| concept | 2016 era | 2020 era | exceptions |
|---|---|---|---|
| birth date | `anketa.gimimo-data` | `biografija.gimimo-data` | |
| birth place | `anketa.gimimo-vieta` | `biografija.gimimo-vieta` | |
| nationality | `anketa.tautybe` | `biografija.tautybe` | not published in the 2024/2025 elections |
| education | `anketa.issilavinimas.irasai` | `biografija.issilavinimas.irasai` | same item keys in both eras |
| foreign languages | `anketa.uzsienio-kalbos` | `biografija.uzsienio-kalbos` | |
| marital status | `anketa.seimine-padetis` | `biografija.seimine-padetis` | |
| spouse name | `anketa.sutuoktinio-vardas-pavarde` | `biografija.sutuoktinio-vardas-pavarde` | 2020 era: `2020-seimo` only |
| children | `anketa.vaiku-vardai-pavardes` | `biografija.vaiku-vardai-pavardes` | 2020 era: `2020-seimo` only |
| hobbies | `anketa.pomegiai` | `biografija.pomegiai` | |
| current position | — | `anketa.einamos-pareigos` | 2020-era question |
| main workplace | `anketa.pagrindine-darboviete` | — | 2016-era question; near- but not exact equivalent of the above |
| public activity | `anketa.visuomenine-veikla` | `biografija.visuomenine-veikla` | `2020-seimo`'s question wording is wider (scientific + pedagogical activity) |
| other about self | `anketa.kita-apie-save` | `biografija.kita-apie-save` | 2020 era: `2020-seimo` only |
| party membership | `anketa.politine-organizacija` (string) | `anketa.narystes-politinese-organizacijose.tekstas` (2020–2023) / `.irasai` (2024 on) | three value shapes |
| nominator | `profilis.kita.<iskele-variant>.reiksme` | same | five key names — see below |
| post-election list number | `profilis.kita.porinkiminis-eiles-numeris.reiksme` (Seimo family) / `…porinkiminis-numeris-sarase.reiksme` (municipal/EP family) | same split | absent in the presidential elections |
| conviction declaration | `anketa.pareiskimai.ar-buvote-pripazintas-kaltu` | same | absent in `2019-prezidento` |
| conviction details | — | `anketa.teistumo-detales.irasai` (2019/2021 flat) / `anketa.teistumo-detales` (2023 on, nested) | see traps |
| money (×7) | `turto-ir-pajamu-deklaracijos.<key>` | same | identical in all 20 |

The nominator's five key names, all under `profilis.kita`: `iskele` (Seimo
family), `iskele-i-tarybos-narius-merus` (2017/2019/2021 municipal),
`iskele-i-savivaldybes-merus` and `iskele-i-tarybos-narius-ir-merus` (2023+
municipal, split by role), `kandidata-iskele` (`2024-prezidento`). It is
absent from `2019-ep`, `2019-prezidento` and `2024-ep`, appears only on
mayoral candidacies in the municipal generals, and only on a subset of
records in `2020-seimo` and `2024-seimo` (758/1754 and 699/1740).
[concept-map.json](concept-map.json) has the per-election resolution.

## Joining people across elections

There is **no cross-election person id**. The `rkndId` in candidate URLs is
a per-election registration id, and `candidateId` comes in two formats: a
name slug with positional `-2`/`-3` suffixes for namesakes (18 elections)
vs name-slug-plus-VRK-candidate-id (`ada-grakauskiene-2420696`) in the two
municipal generals. Never join on it.

The tested recipe (measured in [DASHBOARD.md](DASHBOARD.md)): **normalized
name + birth date** — NFC-normalize, uppercase and whitespace-collapse the
name, keep diacritics, pair it with `gimimo-data`. Birth date is present on
33,120 of 33,121 records (the one exception groups by name alone); the pair
collides for zero same-election record pairs, and 305 names are shared by
distinct people that name-only grouping would merge wrongly. Known
limitation: a person who changes surname between elections (marriage)
appears as two persons.

## Traps

- **Donations are per campaign, not per candidate.** Every candidate on a
  shared list carries the whole campaign's donation list; naive summing
  inflated 2019 EP donations 20×. Group by campaign identity first — see
  the caveat in [DATASET.md](DATASET.md#caveats-for-analysis).
- **Municipal sections are role-dependent.** In
  `2019-kovo-3-savivaldybiu-tarybu`, free-text biography, photo and the
  profile-card nominator are published only for mayoral candidates (~410 of
  13,666, so ~97% of records carry none of them); in `2023-kovo-5` the
  nominator keys exist only on the 433 mayoral-role records. Upstream
  behaviour, not sparseness.
- **`teistumo-detales` has two shapes.** Flat `{irasai: [...]}` records in
  2019/2021; a nested object whose `nusikalstamos-veikos.irasai` carries the
  offences from 2023 on — and `nusikalstama-veika` (a string, the offence)
  vs `nusikalstamos-veikos` (the wrapper) are different things under
  near-identical names. 2016/2020 Seimo and 2019 EP publish their detail
  tables only in `rawData.anketa.rows`, so counting the normalized key alone
  under-reports; count the declaration field instead.
- **`privaciu-interesu-deklaracija.id001a` has two shapes.** A dict
  `{tekstas}` in `2016-seimo`, `2018-rugsejo-16-seimo-zanavykai`,
  `2019-rugsejo-8-seimo` and `2020-seimo`, but a *list* of row objects
  (keyed by a 140-character sentence slug) in the 2017 mayoral elections,
  `2019-ep`, `2019-prezidento` and `2019-kovo-3-savivaldybiu-tarybu`.
- **`Neskelbiamas` saturates contact fields in the 2019/2020 eras.** VRK's
  own "withheld" token fills `anketa.adresas` (and in `2020-seimo` also
  `anketa.kontaktai.telefonas`/`el-pastas`) at 100% in `2019-kovo-3`,
  `2019-ep`, `2019-prezidento`, `2020-seimo` and the 2021 mayoral
  elections. Coverage statistics on those fields are meaningless there;
  the 2023/2024 elections carry real city-level values instead.
- **Pre-2016 money is in litas.** Every 2012–2015 record declares assets and
  income in litas, not euro — `turto-ir-pajamu-deklaracijos.valiuta` is
  `"Lt"` there and absent from 2016 on. Divide by 3.4528 (the irrevocable
  changeover rate) before comparing across 2015→2016; the dashboard's index
  builder does this and flags the converted candidacies.
- **Photos are sidecar files.** `profilis.nuotrauka` (and
  `rawData.profile.photoSrc`) is always a *reference*: a VRK URL from
  `2020-seimo` on, and the relative path `photos/<candidateId>.<ext>` in the
  2016–2019 page eras, whose file sits beside the records in
  `data/<election-id>/photos/`. `rawData.profile.photoMeta` carries the
  file's size and sha256, verifiable against the byte payload VRK served
  (the raw HTML retains the original data URI). **If you copy records
  elsewhere, bring the election's `photos/` folder along** — a record alone
  no longer contains its portrait. One curiosity survives faithfully: one
  candidate's "photo" is a ZIP archive, stored as `.zip`.

## Going deeper

- [concept-map.json](concept-map.json) — the machine-readable concept→path
  bridge this page's era map is built from.
- [OUTPUT_SCHEMA.md](OUTPUT_SCHEMA.md) — per-election schema appendices.
- [DATASET.md](DATASET.md) — inventory, run history, analysis caveats.
- [DASHBOARD.md](DASHBOARD.md) — the reference consumer: a local browser
  that joins candidacies into persons.
