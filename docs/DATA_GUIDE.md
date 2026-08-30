# Data Guide

The consumer entry point to the corpus: everything a third party needs to
query 113,073 candidate records across 55 Lithuanian elections (1996–2025)
without reading the per-election schema appendices first. The headline
numbers are no longer hand-maintained: `tests/test_doc_counts.py` fails
whenever this sentence disagrees with `scraper/elections.json` or, on a
checkout with a local corpus, with `data/` itself (issue #84 — the previous
revision sat three elections stale for a week and nothing said a word).

Records live at `data/<election-id>/<candidateId>-<electionId>.json`, one
file per candidacy. `data/` is not version controlled; see
[DATASET.md](DATASET.md) for the inventory and how to regenerate it — or
skip the scrape and download a `corpus-YYYY-MM-DD` release, which carries
every record (and portrait, and anomaly log) as one SQLite database plus
the flat table ([CANDIDACIES.md](CANDIDACIES.md#distribution)).

**If what you want is one table** — compare education, money, party or
electedness across elections without learning the 55 per-election schemas —
build the derived candidacy table first:
`python scripts/build_candidacy_table.py` writes one row per (person,
election) with everything already joined, EUR-converted and measure-tagged.
[CANDIDACIES.md](CANDIDACIES.md) documents every column. The rest of this
page is for reading the record files themselves.

Every record in the corpus is what today's parser produces from the page it
was fetched from: `python scripts/reparse_diff.py` re-parses each election
from its retained HTML and exits non-zero if any record disagrees. Two shape
divergences this page used to list as traps — `anketa.teistumo-detales`'s
flat/nested split and `privaciu-interesu-deklaracija.id001a`'s dict/list
split — turned out to be stale data rather than era differences, so they were
removed from the corpus instead of documented (issues #86 and #91).

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

**Money.** `turto-ir-pajamu-deklaracijos` carries the same eleven value keys on
every election from 2004 on — the ones whose pages publish the declaration as
titled sections — at 100% presence:

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

Values are parsed numbers — never strings — and always **floats**, in EUR from
2016 on and in litas before it (see the litas trap below). The type is a
property of the column, not of the figure: `202000` is stored `202000.0` so a
column does not change type between two candidates because one of them
happened to declare whole euro. (Until issue #101 it did, in 225 columns.) An
amount VRK renders without its leading zero (`,35 EUR`) is read as the
sub-euro figure it is — the page formatter drops the zero, and no election
prints such an amount as `0,35` — with the source text kept in `rawData`
either way. `null` means the row was not published or does not parse as a
number; the last four are published only by the GPM308/GPM311 form as reworded
in 2018, and are null in every earlier era.

The same rule holds for every money value in a record, not just this block:
the private-interest transaction sums (`id001s[].sandorio-suma`,
`id001s[].sandorio-suma-lt`, `vii-sandoriai[].suma-skaiciais`) and the
campaign-finance `amountEur`/`amountLt`. Where a column prints the currency in
the *value* rather than in its heading, the currency is a sibling key:
`sandorio-suma` is a float and `sandorio-suma-valiuta` is `"EUR"` or `"Lt"`.
The value-band codes (`sandorio-vertes-litais-kodas` and its siblings) are
**not** money and stay strings — `"001"` is a band, and its leading zeros
carry meaning.

The 1996–2003 pages publish a single un-sectioned form and keep their own key
set instead (`turtas-ir-pinigines-lesos-metu-pabaigoje`,
`gautos-pajamos-darbo-santykiu` and so on); `gautos-pajamos`,
`sumoketas-pajamu-mokestis` and `pinigines-lesos` are the keys they share with
the rest.

**A shared key is not a shared measure** (issue #97). Three eras' figures
sit under the same names while measuring different things, with nothing in
the record marking the switch:

- `gautos-pajamos` is income **net of tax** on every 1996–2002 form ("Gauta
  pajamų (be mokesčių) suma"; 2002's is family-scoped as well) and **gross**
  from 2004 on. This is provable from the numbers, not just the labels: the
  modal tax/income ratio in 1996–2002 is 0.40–0.52, above the era's 33 %
  statutory rate, which a gross base cannot produce. 23,141 populated
  records are on the net side, and a per-person income series drawn through
  2002→2004 steps 30–50 % for no real reason unless re-grossed
  (`gautos-pajamos + sumoketas-pajamu-mokestis`, the two rows of the same
  form).
- `sumoketas-pajamu-mokestis` switches from tax *paid* ("Išskaičiuota
  (sumokėta)…") to tax *payable* ("Deklaruota mokėtina…") with the 2018
  rewording.
- the archive eras hold their wealth in combined rows while carrying the
  modern split keys as always-null placeholders, so summing the eleven keys
  above reads €0 for 17,654 declarations that do state their wealth.

Resolve all three through `scraper/shared/deklaracijos.py` —
`pajamu_matas()`, `mokescio_matas()`, `deklaruotas_turtas()` and
`deklaruotos_pajamos_bruto()` name the measure and do the era-aware
arithmetic — or read the candidacy table
([CANDIDACIES.md](CANDIDACIES.md)), which carries the measure columns
alongside every figure.

**What each declaration is.** Three more keys say what the figures are an
extract *of*, and a `deklaracijos` list carries each declaration the page
printed with its own copy of them. The first two are present on the sectioned
eras (2004 on); `deklaracijos-apimtis` reaches the 2002 and 2003 municipal
form as well:

| key | values |
|---|---|
| `deklaracijos-metai` | the tax year, where the page states it — 33,494 of the 84,402 sectioned declarations. The 2004, 2007, 2011 and 2015 pages, `2016-seimo` and `2020-seimo` state none |
| `deklaracijos-forma` | `GPM302`/`GPM305`/`GPM308`/`GPM311`, or `FR0462` for the 2004 and 2007 family |
| `deklaracijos-apimtis` | `gyventojo`, `seimos`, or `gyventojo-seimos` for the combined heading every page from 2008 on prints |

A declaration filed for 2023 and one filed for 2015 used to be
indistinguishable; **do not compare amounts across elections without reading
`deklaracijos-metai`**, and note that where it is null the year is genuinely
not on the page rather than merely unparsed.

**Conviction declaration.**
`anketa.pareiskimai.ar-buvote-pripazintas-kaltu` is the yes/no field to
count on, present in 19 of 20 elections — the 2019 presidential
questionnaire asks constitutional eligibility questions instead and has no
conviction declaration. Structured conviction *details* are another matter;
see the traps below.

**Elected.** `kandidatavimas.isrinktas` is now `true`/`false` on every
record of every election except the 1997 municipal pair (issue #92) —
either joined in from VRK's results trees (the 1996–2015 families, whose
pages mark no winner and whose `pastaba` is always null; `isrinktasKaip`
names the seat, `rezultatuSaltinis` the page, a `null` means no results
file exists) or, on the 2016–2025 layouts, derived from the profile's
prose note (`profilis.pastaba` starting `Išrink`), which names the
complete winner set in every one of those elections — see
`docs/OUTPUT_SCHEMA.md`. Four traps:

- *`kandidatavimas` is a list in the 1996-1999 Seimas archive family*, one
  entry per candidacy — a 1996 candidate could stand in a constituency and on
  a party list at once. Read `any(c["isrinktas"] for c in kandidatavimas)`,
  not `kandidatavimas["isrinktas"]`, and expect kebab-case keys there
  (`isrinktas-kaip`, `rezultatu-saltinis`, `rezultatu-turas`) rather than the
  camelCase the other families use. `isrinktas` is never null in that family:
  its pages state an outcome for every constituency, `neįvyko` included.

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

**Placeholders.** Four placeholder forms normalize to `null`: `Nenurodė`,
`-`, the empty string, and a value that is nothing but the replacement
character `U+FFFD` (30 records, 28 of them `2008-seimo` biographies, where
VRK's page holds a bare NUL byte). A `null` means "not answered on the page";
the source text is always in `rawData`. Candidate-*typed* variants survive
verbatim as answers — `Nėra`, `nėra`, `Nenurodyta`, `Nenurodoma`, `--`, `.`
and similar — because an answered "none" is not the same as unanswered.
Account for them when counting.

**Trailing separators.** A normalized string never ends in a bare `,` or `;`.
VRK publishes 3,856 values that do (`"Jonas, Rasa, Živilė, Jovita,"`, one list
item per separator and one to spare); the separator is dropped because it
separates nothing and breaks any consumer that splits on it. A full stop is
kept — a sentence is allowed to end. `rawData` keeps the published text.

## The era map: concept → path

The questionnaire moved between VRK page eras, so the same concept lives
under different paths. The machine-readable bridge is
[concept-map.json](concept-map.json) — per concept, the exact normalized
path for each election id, plus a `derived` section for the concepts no
single path resolves (a conviction is published three different ways, so
`teistumas` is a function rather than a path).

**How often each of those paths is actually filled is measured**, not assumed:
`data/coverage.tsv` (from `python scripts/field_coverage.py`) carries a
records / keyPresent / nonNull count for all 1,295 mapped cells, and
[coverage-baseline.tsv](coverage-baseline.tsv) carries the checked-in rate and,
for the 24 cells no record fills, a status word saying why. Read it before
concluding a field is missing from an era —
[FIELD_COVERAGE.md](FIELD_COVERAGE.md) explains the vocabulary.

**The table below covers the two modern eras only — 20 of the corpus's 55
elections.** `concept-map.json` is the authority and is the thing to read
programmatically; this table is a human summary of the 2016 and 2020 eras.
The thirty-five pre-2016 elections
are mapped in `concept-map.json` but not summarized here: the 2012–2015
family, the 2004–2005 static-site elections, the two 2000 elections and the 1997 municipal archive all resolve most concepts under
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
| conviction details | `anketa.teistumo-detales.irasai` | same | one shape in all 17 elections that publish the block, all 11 of the 2020 era and 6 of the 2016 era — the two 2017 mayoral elections and `2019-prezidento` publish no detail table. Resolve with the `teistumas` concept, not by hand |
| money (×11) | `turto-ir-pajamu-deklaracijos.<key>` | same | identical wherever a declaration is published; the last four only from the 2018 GPM rewording on |
| declaration year / form / scope | `turto-ir-pajamu-deklaracijos.deklaracijos-{metai,forma,apimtis}` | same | see the money invariant above |

The nominator's five key names, all under `profilis.kita`: `iskele` (Seimo
family), `iskele-i-tarybos-narius-merus` (2017/2019/2021 municipal),
`iskele-i-savivaldybes-merus` and `iskele-i-tarybos-narius-ir-merus` (2023+
municipal, split by role), `kandidata-iskele` (`2024-prezidento`). The
profile card alone is not enough: it names no nominator on `2019-ep` and
`2024-ep` (their list is under `sarasas`), only mayoral candidacies carry it
in the municipal generals (a council candidate's list is the
`kandidatavimas.tarybosNarys.partyList` join), and only constituency
candidacies in `2016-seimo`, `2020-seimo` and `2024-seimo`. **Do not walk
these paths by hand** — resolve through
`scraper/shared/nominator.py::resolve_nominator(record)`, which walks the
ordered per-election path lists [concept-map.json](concept-map.json)
declares under `iskele` and returns a non-null string for every record of
every election but the five presidential ones whose candidates self-nominate
by law (see the next section for the canonical party join).

## Joining people across elections

There is **no cross-election person id**. The `rkndId` in candidate URLs is
a per-election registration id, and `candidateId` comes in two formats: a
name slug with positional `-2`/`-3` suffixes for namesakes (18 elections)
vs name-slug-plus-VRK-candidate-id (`ada-grakauskiene-2420696`) in the two
municipal generals. Never join on it.

The tested recipe (measured in [DASHBOARD.md](DASHBOARD.md)): **normalized
name + birth key** — NFC-normalize, uppercase and whitespace-collapse the
name, keep diacritics, pair it with `gimimo-data`, falling back to
`~gimimo-metai` for the 170 archive records that publish a year and no date
(the 64 records left group by name alone). The pair collides for zero
same-election record pairs, and 1,989 names are shared by distinct people
that name-only grouping would merge wrongly.

Two things ride on top of the key (issue #96). Each person in
`dashboard/people.json` carries a **`pid`** — `p` + 12 hex digits of blake2s
over the natural `NAME|birth` key, anchored for merged persons at the
chronologically earliest fragment so it survives rebuilds and new elections
— and **`scraper/person_overrides.json`** is the checked-in, hand-reviewed
record of the decisions the key cannot make: a person who changed surname
between elections is two natural keys, and each reviewed pair is either
merged (the former keys stay on the person as `"ak"`) or recorded as
genuinely distinct. `scripts/find_identity_merge_candidates.py` finds and
scores the candidate pairs; DASHBOARD.md documents the workflow.

## Joining parties across elections

There is **no cross-election party id** in the corpus either — the
`partyList.id` of the two municipal generals is a per-municipality list id,
and no `rorgId` in a nominator URL is shared between two elections — and
grouping by the raw string silently splits every major party: one party's
16,268 candidacies split three ways on nothing but the dash glyph between
the words, and the 2000/2002 profile cards print the same list in the
genitive (issue #82).

Party identity is therefore *created*, by
[`scraper/parties.json`](../scraper/parties.json): one entry per
organisation — parties, coalitions (with member party ids under `nariai`
where the coalition's own name states them), electoral committees,
self-nomination — with every one of the 427 measured nominator surface forms
an exact alias of exactly one entry. The registry, not the corpus, carries
renames (one entry, the old name an alias: LVŽS spans its 2001 and 2006
names) and mergers (a new entry with `predecessors`: `ts-lkd` points at
`tevynes-sajunga` and `lkd`, so pre-2008 candidacies group under the
predecessor rather than anachronistically under the merged party).

The join is `scraper/shared/parties.py`:

```python
from scraper.shared.parties import partija
partija(record)
# {"partija-id": "ts-lkd",
#  "partija-vardas-raw": "Tėvynės sąjunga-Lietuvos krikščionys demokratai",
#  "tipas": "partija"}
```

Matching is exact alias → punctuation/case fold → unmatched (`None`), never
a guess; `scripts/nominator_report.py` re-measures the corpus and lands any
new surface form in the registry's `unmatched` block, which
`tests/test_party_registry.py` asserts is empty. The measured forms are
checked in as [nominator-forms.tsv](nominator-forms.tsv). The records are
never rewritten — `partija-id` is derived, `partija-vardas-raw` is exactly
what the record says.

Two different concepts wear the party's name; do not mix them. The
**nominator** (this section) is who put the candidate on the ballot — VRK's
controlled vocabulary, 99.8 % coverage. **Membership**
(`anketa.politine-organizacija`, `anketa.narystes-politinese-organizacijose`)
is what the candidate *typed* about their own party history — thousands of
free-prose singletons, with "Nesu"/"Nepartinis" sitting in the same field as
party names. Only the 2024-on structured membership table is machine-usable,
and none of it is canonicalised by the registry.

## Traps

- **Donations are per campaign, not per candidate.** Every candidate on a
  shared list carries the whole campaign's donation list; naive summing
  inflates the corpus 104× overall and one election 1,182×. Group by
  `rawData…campaigns[].campaignKey` — the *only* correct key; a VRK
  decision number spans many participants and destroys money — or read the
  candidacy table's `campaigns` table, which is already de-duplicated. See
  the caveat in [DATASET.md](DATASET.md#caveats-for-analysis).
- **Municipal sections are role-dependent.** In
  `2019-kovo-3-savivaldybiu-tarybu`, free-text biography, photo and the
  profile-card nominator are published only for mayoral candidates (~410 of
  13,666, so ~97% of records carry none of them); in `2023-kovo-5` the
  nominator keys exist only on the 433 mayoral-role records. Upstream
  behaviour, not sparseness.
- **A conviction has three published shapes; read the `teistumas`
  concept.** `scraper/shared/conviction_details.py` resolves a record's
  normalized `anketa` to one answer — `neklausta` / `ne` /
  `deklaruota-be-detaliu` / `deklaruota` — over the structured table, the
  free-text explanation and the bare yes/no. Doing it by hand has three
  traps. **The affirmative follows the question's wording**: `Taip` on the
  Seimas and municipal forms, `Yra` on the 2000 and 2004 static-site ones
  (which ask whether there is anything to declare), `Buvo` and `Turiu` on
  their neighbouring questions — filtering on `Taip` alone misses sixteen of
  the main question's 1,630 declarers. **A conviction can be declared next
  door**: the 2000–2014 forms ask separately about a grave crime, a foreign
  court, political persecution and an unserved sentence, and 20 records
  answer one of those affirmatively while denying the main question, so
  1,650 records declare a conviction somewhere. `teistumas` returns them
  under `kiti-pareiskimai`. **An absent key is not a "no"**:
  `2019-prezidento` and the 1990s archive cards never ask the question.
  **The entries differ inside** — `nusikalstama-veika` (a string, the
  offence, 2016–2021) and `nusikalstamos-veikos` (a list of offence records,
  2023 on) are different things under near-identical names. Since issue #86
  the key itself is uniform: `{irasai: [...]}` on every record of all 17
  elections that publish it.
- **`Neskelbiamas` saturates contact fields in the 2019/2020 eras.** VRK's
  own "withheld" token fills `anketa.adresas` (and in `2020-seimo` also
  `anketa.kontaktai.telefonas`/`el-pastas`) at 100% in `2019-kovo-3`,
  `2019-ep`, `2019-prezidento`, `2020-seimo` and the 2021 mayoral
  elections. Coverage statistics on those fields are meaningless there;
  the 2023/2024 elections carry real city-level values instead.
- **A 2007 declaration can be the spouse's.** `2007-vasario-25-savivaldybiu`
  and the 2004 pages publish *separate* declarations for the candidate, the
  family and the spouse. The value keys carry the candidate's own where the
  page publishes one and the family's where it publishes that instead;
  `deklaracijos-apimtis` says which, `sutuoktinio` carries a spouse's five
  asset figures on the 352 records that have one, and `deklaracijos` lists
  every declaration the page printed. Until issue #98 the last section on the
  page won, so 243 records of that election reported a spouse's assets as the
  candidate's. **A 3,672-record slice of that election is family-scope and a
  9,664-record slice is not**, so filter on `deklaracijos-apimtis` before
  ranking anyone by declared assets.
- **The 1990s income total is often refused, and row 1 is not.** The
  1996–2000 form prints rows 1 (employment income) and 20 (the total) of its
  income section, and row 20 fails by rendering 0 against a non-zero row 1 —
  4,463 of `1997-kovo-23-savivaldybiu-tarybu`'s 6,276 records, 147 of
  `2000-kovo-19`, 9 of `1996-spalio-20-seimo`, 8 of `2000-seimo` and one of
  the 1997 Švenčionys repeat, 4,628 in all. The
  parser refuses such a total and leaves `gautos-pajamos` null;
  `gautos-pajamos-darbo-santykiu` holds row 1 and is present on every one of
  them. Resolve income with the `deklaruotos-pajamos` concept
  (`scraper/shared/deklaracijos.py`), which returns the figure and a
  `saltinis` saying whether it is a declared total or employment income
  alone; reading `gautos-pajamos` by itself reports those candidates as
  having declared nothing.
- **Pre-2016 money is in litas, and the rule is data-driven: divide by
  3.4528 whenever `valiuta == "Lt"`.** That key is `"Lt"` on every record
  that carries a declaration block from 1996 through 2015 — all 79,071 of
  them, not just the 2004–2015 slice an earlier revision of this page named
  — and absent from 2016 on. **No record anywhere says `"EUR"`**: in the
  stored corpus the euro era is marked by the key's absence, so a consumer
  who checks for `"EUR"` converts nothing.
  `scraper/shared/deklaracijos.py::deklaracijos_valiuta()` turns the absence
  into an explicit answer, and the candidacy table ships everything
  EUR-converted with the rate in its own column. The dashboard's index
  builder converts the same way and flags the converted candidacies.
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
- **20 values still hold a replacement character, and that is VRK's.**
  `U+FFFD` reached the corpus in 203 values. Fetching one of those pages live
  returns the replacement character in VRK's own bytes, so the original was
  destroyed upstream and no re-decode recovers it. 30 of them were the whole
  value (a NUL byte where a biography should be) and normalize to `null`; 153
  stood where a Lithuanian opening quote belongs, closed by a `"` that proves
  the pair, and are restored to `„` (`AB „Lietuvos geležinkeliai"`). The
  remaining **20 have nothing to prove what they were and are left as
  published** rather than guessed at — 9 in `2000-seimo`, 9 in `2004-seimo`,
  2 in `2004-ep`. `tests/test_corpus_value_hygiene.py` pins that 20 so it
  cannot grow.
- **`VšĮ` is not a parsing bug.** 20,651 normalized values contain a
  lowercase letter immediately followed by an uppercase one, which reads like
  a lost line break. It is not: 13,158 of them are the legal-form
  abbreviation `VšĮ`, and the rest are company names (`UAB "inChase"`, `DnB`,
  `GmbH`, `StepArc`) and VRK's own typing (`kAUNO`, `Partija tTvarka`). A
  sample of 835 such junctions checked against the retained HTML found 797
  present verbatim, with no tag boundary between the two letters, and the
  misses were a parser-authored enum value and one biography split across
  files. Do **not** insert spaces at these junctions.

## Going deeper

- [CANDIDACIES.md](CANDIDACIES.md) — the derived candidacy table: one row
  per (person, election), education on one ordinal, money EUR-converted with
  its measure named, the campaign grouping key, and typed absences. Built by
  `scripts/build_candidacy_table.py` and gated against
  [candidacy-baseline.tsv](candidacy-baseline.tsv).
- [concept-map.json](concept-map.json) — the machine-readable concept→path
  bridge this page's era map is built from. Its `derived` section covers the
  concepts no single path resolves: `teistumas`
  (`scraper/shared/conviction_details.py`), `deklaruotos-pajamos`,
  `deklaruotas-turtas` and `pajamu-matas`
  (`scraper/shared/deklaracijos.py`), `issilavinimo-lygis`
  (`scraper/shared/education.py`), `partija` (`scraper/shared/parties.py`)
  and `kandidatura` (`scraper/shared/kandidatura.py`).
- [FIELD_COVERAGE.md](FIELD_COVERAGE.md) and
  [coverage-baseline.tsv](coverage-baseline.tsv) — how often every mapped path
  is filled, and which cells are empty on purpose.
- [OUTPUT_SCHEMA.md](OUTPUT_SCHEMA.md) — per-election schema appendices.
- [DATASET.md](DATASET.md) — inventory, run history, analysis caveats.
- [DASHBOARD.md](DASHBOARD.md) — the reference consumer: a local browser
  that joins candidacies into persons.
