# Data Guide

How to query the corpus: 113,073 candidate records across 55 Lithuanian
elections (1996–2025).

Records live at `data/<election-id>/<candidateId>-<electionId>.json`, one file
per candidacy. Get them from a `corpus-YYYY-MM-DD` release
([CANDIDACIES.md](CANDIDACIES.md#distribution)) or by scraping
([DATASET.md](DATASET.md)).

**If you want one table** (education, money, party or electedness across
elections), run `python scripts/build_candidacy_table.py`: one row per
(person, election), joined, EUR-converted and measure-tagged.
[CANDIDACIES.md](CANDIDACIES.md) documents every column. The rest of this page
is for the record files.

## Record anatomy

Seven top-level fields on every record, and two optional ones. There are
exactly three root key-sets:

| records | elections | root fields |
| --- | --- | --- |
| 78,259 | 44 | the seven, plus `kandidatavimas` |
| 27,478 | 4 | the seven, plus `kandidatavimas` and `candidateNote` |
| 7,336 | 8 | the seven |

The seven:

- `electionId`, `candidateId`, `candidateName`
- `source`: the VRK page URL(s) the record was parsed from
- `rawData`: source-close parse, camelCase sections (`profile`, `anketa`,
  `turtoIrPajamuDeklaracijos`, …)
- `normalized`: the analysis layer, Lithuanian kebab-case sections in one fixed
  order (`profilis`, `anketa`, `kandidatavimas`, `gyvenamoji-vieta`,
  `biografija`, `programa`, `turto-ir-pajamu-deklaracijos`,
  `privaciu-interesu-deklaracija`, `patiketiniai`,
  `politines-kampanijos-dalyvio-duomenys`, `kita`). Each record carries a
  subset; [OUTPUT_SCHEMA.md](OUTPUT_SCHEMA.md#normalized) says which.
- `provenance`: fetch time, parse time, parser commit and the source page's
  sha256 ([OUTPUT_SCHEMA.md](OUTPUT_SCHEMA.md#provenance)). Compare records by
  content, not by `parsedAt`/`parserCommit`; `parserCommit` is `null` on
  49,586 records written before provenance existed.

The two optional:

- `kandidatavimas`: the candidacy block (municipality, roles, party list
  `tarybosNarys.partyList.{id, number, name}`, list positions, per-role
  `elected` flags, results-join URLs). A root field on
  105,737 records across 47 of the 55 elections. The 1996–1999 archive family
  (eight elections, 7,336 records) carries it *inside* `normalized` instead.
- `candidateNote`: VRK's note beside the candidate, on 27,478 records of
  `2016-seimo`, `2019-kovo-3-savivaldybiu-tarybu`,
  `2023-kovo-5-savivaldybiu-tarybu-ir-meru` and `2025-kovo-16-meru`.

Query `normalized`; fall back to `rawData` for the verbatim source text.
**Sections can be absent.** In elections that publish a section on over 99 %
of records, eleven records lack one: `biografija` on
`gintaras-binkauskas-2012-seimo`, `gintaras-binkauskas-2016-seimo` and
`jonas-korsakas-2020-seimo`; `turto-ir-pajamu-deklaracijos` on three of
`2002-gruodzio-22` (`stasys-stankus-205466`, `saulius-jancys-205870`,
`mindaugas-kucinskas-205871`), `genovaite-ziobakiene-2004-seimo`,
`darius-juodeska-72579-2015-kovo-1-savivaldybiu` and
`jonas-korsakas-2020-seimo`; `politines-kampanijos-dalyvio-duomenys` on
`algimantas-matulevicius-2009-ep` and `valdemar-tomasevski-2009-ep`.

## Cross-election invariants

**Money.** From 2004 on, `turto-ir-pajamu-deklaracijos` carries the same eleven
value keys on every record that has the section:

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

Values are always **floats** (`202000.0`), EUR from 2016 and litas before.
`,35 EUR` reads as 0.35. `null` means not published or not a number. The last
four exist only on the 2018 GPM308/GPM311 rewording.

The same holds for every money value: `id001s[].sandorio-suma`,
`id001s[].sandorio-suma-lt`, `vii-sandoriai[].suma-skaiciais`, campaign
`amountEur`/`amountLt`. Where the currency is in the value, it is a sibling key
(`sandorio-suma-valiuta`: `"EUR"` or `"Lt"`). Value-band codes
(`sandorio-vertes-litais-kodas` and siblings) are strings, not money.

The 1996–2003 pages use their own key set
(`turtas-ir-pinigines-lesos-metu-pabaigoje`, `gautos-pajamos-darbo-santykiu`,
…), sharing only `gautos-pajamos`, `sumoketas-pajamu-mokestis` and
`pinigines-lesos`.

**A shared key is not a shared measure:**

- `gautos-pajamos` is **net of tax** on 1996–2002 forms (2002's is
  family-scoped too) and **gross** from 2004. Re-gross the early figures as
  `gautos-pajamos + sumoketas-pajamu-mokestis`.
- `sumoketas-pajamu-mokestis` switches from tax *paid* to tax *payable* with
  the 2018 rewording.
- The archive eras hold wealth in combined rows, with the modern split keys
  always null.

Resolve all three through `scraper/shared/deklaracijos.py`
(`pajamu_matas()`, `mokescio_matas()`, `deklaruotas_turtas()`,
`deklaruotos_pajamos_bruto()`), or read the candidacy table's measure columns.

**What each declaration is.** A `deklaracijos` list carries each declaration
the page printed, each with these keys:

| key | values |
|---|---|
| `deklaracijos-metai` | the tax year, where the page states it (33,494 of 84,402 sectioned declarations). The 2004, 2007, 2011 and 2015 pages, `2016-seimo` and `2020-seimo` state none |
| `deklaracijos-forma` | `GPM302`/`GPM305`/`GPM308`/`GPM311`, or `FR0462` for 2004 and 2007 |
| `deklaracijos-apimtis` | `gyventojo`, `seimos`, or `gyventojo-seimos` (every page from 2008); also on the 2002–2003 municipal form |

**Do not compare amounts across elections without reading
`deklaracijos-metai`.** Null means the year is not on the page.

**Conviction declaration.** `anketa.pareiskimai.ar-buvote-pripazintas-kaltu`
is the yes/no field, in 19 of 20 elections (`2019-prezidento` has none). For
details, see the traps.

**Elected.** `kandidatavimas.isrinktas` is `true`/`false` on every record:

- 1996–2015: joined from VRK's results trees. `isrinktasKaip` names the seat,
  `rezultatuSaltinis` the page.
- 2016–2025: derived from `profilis.pastaba` starting `Išrink`.

Traps:

- *1996–1999 Seimas archive:* `kandidatavimas` is a **list**, one entry per
  candidacy. Read `any(c["isrinktas"] for c in kandidatavimas)`. Keys are
  kebab-case (`isrinktas-kaip`, `rezultatu-saltinis`, `rezultatu-turas`), and
  `isrinktas` is never null.
- *1997 municipal pair:* kebab-case keys on a dict. The March Švenčionys
  result (Nr. 47) was voided: `isrinktas: false` with the decision under
  `kandidatavimas.rezultatai-negalioja`.
- *Presidential:* `pastaba` is non-null for every candidate.
- *Party names:* the note puts the party in the genitive. Never match parties
  on it; use `kandidatavimas.tarybosNarys.partyList.id`.
- *Annulled results:* 48 March 2015 council winners in Šilutė and Trakai carry
  `kandidatavimas.rezultataiPanaikinti` and `isrinktas: false`.

**Votes.** 1996–2015 only; the 2016–2025 records hold none.
`kandidatavimas` has `pirmumoBalsai` (with `porinkiminisNumerisSarase`,
`pirmumoBalsuSaltinis`, and `reitingoBalai` where VRK computed it) for list
candidates, and `vienmandatesBalsai` `{balsadezese, pastu, isViso, procentai,
vieta, saltinis}` for constituency candidates (`vienmandatesBalsai2` for a
runoff). The archive family uses kebab-case in its `turai` list. Resolve
through `scraper/shared/kandidatura.py`; the candidacy table has
`preference_votes`, `list_votes`, `constituency_votes`.

**Placeholders.** `Nenurodė`, `-`, the empty string and a lone `U+FFFD`
normalize to `null`. Typed "none" answers (`Nėra`, `Nenurodyta`, `--`, `.`)
survive verbatim; account for them when counting.

**Trailing separators.** A normalized string never ends in `,` or `;`.
`rawData` keeps the published text.

## The era map: concept → path

[concept-map.json](concept-map.json) gives, per concept, the normalized path
for each election, plus a `derived` section for concepts no single path
resolves (`teistumas` is a function). How often each path is filled is in
`data/coverage.tsv` and [coverage-baseline.tsv](coverage-baseline.tsv)
([FIELD_COVERAGE.md](FIELD_COVERAGE.md)).

The table below summarizes the two modern eras only. The pre-2016 elections
mostly use the 2016 era's `anketa.*` keys; the 1996–1998 Seimas archive
publishes almost none of these concepts.

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
| nationality | `anketa.tautybe` | `biografija.tautybe` | not published in 2024/2025 |
| education | `anketa.issilavinimas.irasai` | `biografija.issilavinimas.irasai` | same item keys |
| foreign languages | `anketa.uzsienio-kalbos` | `biografija.uzsienio-kalbos` | |
| marital status | `anketa.seimine-padetis` | `biografija.seimine-padetis` | |
| spouse name | `anketa.sutuoktinio-vardas-pavarde` | `biografija.sutuoktinio-vardas-pavarde` | 2020 era: `2020-seimo` only |
| children | `anketa.vaiku-vardai-pavardes` | `biografija.vaiku-vardai-pavardes` | 2020 era: `2020-seimo` only |
| hobbies | `anketa.pomegiai` | `biografija.pomegiai` | |
| current position | — | `anketa.einamos-pareigos` | |
| main workplace | `anketa.pagrindine-darboviete` | — | near-equivalent of the above |
| public activity | `anketa.visuomenine-veikla` | `biografija.visuomenine-veikla` | `2020-seimo` asks more widely |
| other about self | `anketa.kita-apie-save` | `biografija.kita-apie-save` | 2020 era: `2020-seimo` only |
| party membership | `anketa.politine-organizacija` (string) | `anketa.narystes-politinese-organizacijose.tekstas` (2020–2023) / `.irasai` (2024 on) | three value shapes |
| nominator | `profilis.kita.<iskele-variant>.reiksme` | same | five key names, see below |
| post-election list number | `profilis.kita.porinkiminis-eiles-numeris.reiksme` (Seimas) / `…porinkiminis-numeris-sarase.reiksme` (municipal/EP) | same | absent for presidential |
| conviction declaration | `anketa.pareiskimai.ar-buvote-pripazintas-kaltu` | same | absent in `2019-prezidento` |
| conviction details | `anketa.teistumo-detales.irasai` | same | no table in the 2017 mayoral elections or `2019-prezidento`; use `teistumas` |
| money (×11) | `turto-ir-pajamu-deklaracijos.<key>` | same | last four from the 2018 rewording |
| declaration year / form / scope | `turto-ir-pajamu-deklaracijos.deklaracijos-{metai,forma,apimtis}` | same | |

The nominator's five key names under `profilis.kita`: `iskele` (Seimas),
`iskele-i-tarybos-narius-merus` (2017/2019/2021 municipal),
`iskele-i-savivaldybes-merus` and `iskele-i-tarybos-narius-ir-merus` (2023+
municipal, by role), `kandidata-iskele` (`2024-prezidento`). The card names no
nominator on `2019-ep`/`2024-ep`, for council candidates, or for list-only
Seimas candidates. **Do not walk these paths by hand:** use
`scraper/shared/nominator.py::resolve_nominator(record)`, non-null on every
record except the five presidential elections.

## Joining people across elections

There is **no cross-election person id**, and `candidateId` must not be
joined on. It is a name slug plus VRK's candidate id
(`ada-grakauskiene-2420696`) on 92,357 records of seven elections (the
municipal generals from 2000), and elsewhere the name slug with a positional
`-2`/`-3` on collisions (64 records over nine elections).

The key is **normalized name + birth date**: NFC, uppercase, collapsed
whitespace, diacritics kept, paired with `gimimo-data`, falling back to
`~gimimo-metai` where only a year is published.

The person index (`dashboard/people-list.json`) gives each person a **`pid`**:
`p` + 12 hex digits of blake2s over `NAME|birth`, anchored at the earliest
fragment so it is stable. `scraper/person_overrides.json` holds reviewed
decisions the key cannot make (a changed surname: merged, with old keys under
`"ak"`, or recorded as distinct). `scripts/find_identity_merge_candidates.py`
finds candidate pairs; [DASHBOARD.md](DASHBOARD.md) has the workflow.

## Joining parties across elections

There is **no cross-election party id**, and raw nominator strings split
parties on glyphs and grammatical case. Party identity comes from
[`scraper/parties.json`](../scraper/parties.json): one entry per organisation
(party, coalition with members under `nariai`, committee, self-nomination),
with every one of the 393 measured nominator surface forms an exact alias of
exactly one entry.

- **A rename is an alias** of one entry.
- **A continuation is a `predecessors` link** on the successor: a merger
  (`ts-lkd` ← `tevynes-sajunga`, `lkd`), a change of legal form, a taken-over
  registration, a re-brand that kept at least a third of its candidates. The
  links form a forest; `dist/vrk.sqlite` ships them as `party_predecessors`.
- Each entry's `note` records the evidence (JAR code, register dates,
  shared-candidate count). The Ministry of Justice register is the source.
- „Lietuvos liaudies partija“ names two registrations and cannot be split,
  because matching is by string.

```python
from scraper.shared.parties import partija
partija(record)
# {"partija-id": "ts-lkd",
#  "partija-vardas-raw": "Tėvynės sąjunga-Lietuvos krikščionys demokratai",
#  "tipas": "partija"}
```

Matching is exact alias → punctuation/case fold → `None`, never a guess. The
measured forms are in [nominator-forms.tsv](nominator-forms.tsv).

The **nominator** (who put the candidate on the ballot) is not
**membership** (`anketa.politine-organizacija`,
`anketa.narystes-politinese-organizacijose`, what the candidate typed). Only
the 2024-on membership table is machine-usable, and the registry does not
canonicalise any of it.

## Traps

- **Donations are per campaign, not per candidate.** Every candidate on a list
  carries the whole campaign's donations; naive summing inflates the corpus
  104×. Group by `rawData…campaigns[].campaignKey` (not the VRK decision
  number), or use the candidacy table's `campaigns` table
  ([DATASET.md](DATASET.md#caveats-for-analysis)).
- **Municipal sections are role-dependent.** In
  `2019-kovo-3-savivaldybiu-tarybu`, biography, photo and nominator exist only
  for mayoral candidates; in `2023-kovo-5` the nominator keys exist only on
  mayoral-role records.
- **Convictions: read the `teistumas` concept**
  (`scraper/shared/conviction_details.py`), which returns `neklausta` / `ne` /
  `deklaruota-be-detaliu` / `deklaruota`. By hand:
  - the affirmative follows the wording: `Taip`, `Yra` (2000 and 2004 forms),
    `Buvo`, `Turiu`;
  - the 2000–2014 forms ask neighbouring questions (grave crime, foreign
    court, persecution, unserved sentence); `teistumas` returns those under
    `kiti-pareiskimai`;
  - an absent key is not "no" (`2019-prezidento`, the 1990s archive);
  - `nusikalstama-veika` (string, 2016–2021) and `nusikalstamos-veikos` (list,
    2023 on) differ. The container is `{irasai: [...]}` everywhere.
- **`Neskelbiamas` fills contact fields** (`anketa.adresas`, and in
  `2020-seimo` the phone and e-mail) at 100 % in `2019-kovo-3`, `2019-ep`,
  `2019-prezidento`, `2020-seimo` and the 2021 mayoral elections.
- **A 2004/2007 declaration can be the family's or the spouse's.** The value
  keys carry the candidate's own where published, else the family's;
  `deklaracijos-apimtis` says which, and `sutuoktinio` holds a spouse's asset
  figures. Filter on `deklaracijos-apimtis` before ranking by assets.
- **The 1990s income total is often refused.** Where row 20 (total) reads 0
  against a non-zero row 1, `gautos-pajamos` is null and
  `gautos-pajamos-darbo-santykiu` holds row 1. Use the `deklaruotos-pajamos`
  concept, whose `saltinis` says which you got.
- **Pre-2016 money is in litas: divide by 3.4528 whenever `valiuta == "Lt"`.**
  That is all 79,098 declaration records from 1996 through 2015. **No record
  says `"EUR"`**; the euro era is the key's absence.
  `deklaracijos.py::deklaracijos_valiuta()` makes it explicit, and the
  candidacy table ships EUR with the rate in its own column.
- **Photos are sidecar files.** `profilis.nuotrauka` (and
  `rawData.profile.photoSrc`, or `photoUrl` in the 1996–1999 archive) is the
  relative path `photos/<candidateId>.<ext>` in `data/<election-id>/photos/`.
  `rawData.profile.photoMeta` has size and sha256, plus `url` and `fetchedAt`
  for fetched ones. A reference that is still a URL failed to fetch
  (`photoMeta.error`), or was never tried if there is no `photoMeta`. **Copy
  the `photos/` folder with the records.** The extension follows the bytes
  (one `.zip`, some `.png`).
- **6 values still hold a replacement character** (`U+FFFD`), destroyed in
  VRK's own bytes: five `2000-seimo` biographies with a lost `š`/`Š`, and one
  `2004-seimo` biography with lost quotes. They are left as published;
  `tests/test_corpus_value_hygiene.py` pins the count.
- **`VšĮ` is not a parsing bug.** 20,711 values have a lowercase letter
  followed by an uppercase one; 12,950 of them are `VšĮ`, the rest company
  names and VRK's typing. Do **not** insert spaces.

## Going deeper

- [CANDIDACIES.md](CANDIDACIES.md): the derived candidacy table.
- [concept-map.json](concept-map.json): the concept→path bridge. Derived
  concepts: `teistumas` (`scraper/shared/conviction_details.py`),
  `deklaruotos-pajamos`, `deklaruotas-turtas`, `pajamu-matas`
  (`scraper/shared/deklaracijos.py`), `issilavinimo-lygis`
  (`scraper/shared/education.py`), `partija` (`scraper/shared/parties.py`),
  `kandidatura` (`scraper/shared/kandidatura.py`).
- [FIELD_COVERAGE.md](FIELD_COVERAGE.md): fill rates per mapped path.
- [OUTPUT_SCHEMA.md](OUTPUT_SCHEMA.md): per-election schema.
- [DATASET.md](DATASET.md): inventory and analysis caveats.
- [DASHBOARD.md](DASHBOARD.md): the browser that joins candidacies into persons.
