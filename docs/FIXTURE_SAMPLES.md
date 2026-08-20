# Fixture Samples Policy (2016 Seimo)

Sample HTML fixtures under `samples/html/2016-seimo/` are intentionally versioned and test-protected.

## Why fixtures are versioned

Fixtures are used for:

- parser development without live network dependence
- regression tests
- reproducible schema and normalization checks

## Current allowlist

The repository enforces exactly these candidate fixture directories:

- `agne-sirinskiene`
- `ingrida-simonyte`
- `regina-ablom`
- `algirdas-butkevicius`
- `gabrielius-landsbergis`

This is enforced by:

- `tests/test_seimo_2016_sample_allowlist.py`

## Other elections

Each election folder keeps its own small, test-protected fixture set under
`samples/html/<election_id>/` with the same policy. For `2019-ep` the allowlist
(`tests/test_ep_2019_sample_allowlist.py`) is:

- `daiva-adutaviciene`
- `petras-austrevicius`
- `andrius-kubilius`
- `ausra-maldeikiene`
- `liudas-mazylis`
- `laima-liucija-andrikiene`

This mix covers a non-elected candidate, returning MEPs with prior-mandate and
education record tables, candidates with campaign donation data, and a candidate
holding an academic degree / pedagogic title (guards the `9.x` and `12.x`
question-number parsing that would otherwise silently drop those answers).

For `2024-ep` the allowlist (`tests/test_ep_2024_sample_allowlist.py`) is:

- `vitalijus-mitrofanovas`
- `edvinas-guobys`
- `zivile-pinskuviene`
- `tomas-baranauskas`
- `vilija-blinkeviciute`
- `petras-grazulis`

This mix covers an elected MEP (elected note in the profile), a candidate with
an academic degree (guards the 2024 `2.1`/`2.2` biography numbering), a
candidate with conviction and mandate-loss details (`13.1`-`13.4` and `14.1`
conditional answers), an extra private-interest section (`Ryšiai sudarius
sandorius`), and regular non-elected candidates.

For `2024-prezidento` the allowlist
(`tests/test_prezidento_2024_sample_allowlist.py`) is the complete eight-candidate
field (as with `2019-prezidento`, presidential elections are small enough to keep
every candidate):

- `andrius-mazuronis`
- `dainius-zalimas`
- `eduardas-vaitkus`
- `giedrimas-jeglinskas`
- `gitanas-nauseda`
- `ignas-vegele`
- `ingrida-simonyte`
- `remigijus-zemaitaitis`

This covers the winner (`Išrinktas II ture`), the run-off runner-up (`Dalyvavo
II ture`), and first-round candidates (`Dalyvavo I ture`); self-nominated vs
party-nominated candidates; a candidate whose Q8 membership answer is inline
text rather than a table (guards the empty-records path); an academic with a
pedagogic title (guards the `2.1`/`2.2` biography numbering); and a candidate
with an extra `Ryšiai su juridiniais asmenimis` private-interest section.

For `2023-spalio-8-kupiskio-mero` the allowlist
(`tests/test_kupiskio_mero_2023_sample_allowlist.py`) is the complete
five-candidate field of this single-municipality race:

- `algirdas-raslanas`
- `edmundas-jonutis`
- `egle-blazeviciene`
- `vytautas-mockus`
- `zilvinas-aukstikalnis`

This covers the elected mayor (elected note in the profile, second round), a
candidate with conviction details (`13.1`-`13.4`, whose detail table uses a
plain hyphen separator), candidates answering the space-numbered `10 .`-`12 .`
questions both ways, an academic with a pedagogic title, and candidates with the
extra `Ryšiai su juridiniais asmenimis` / `Ryšiai sudarius sandorius`
private-interest sections.

For `2023-geguzes-7-visagino-mero` the allowlist
(`tests/test_visagino_mero_2023_sample_allowlist.py`) is the complete
two-candidate field of the repeat Visaginas mayoral runoff:

- `dalia-straupaite`
- `erlandas-galaguz`

This covers the elected mayor (elected note in the profile) and the runner-up;
the five-tab page set with no campaign tab; empty list fields on the profile
card; and blank-upstream biography answers (`Nenurodė` nationality and work
history, a birth date published without a birth place).

For `2023-kovo-5-savivaldybiu-tarybu-ir-meru` the allowlist
(`tests/test_savivaldybiu_2023_sample_allowlist.py`) is **nine candidates out of
13,796** — the first election whose fixtures are a sample
rather than the complete field, because the field is three times the size of the
rest of the corpus combined. They were chosen to cover one of each archetype the
record shape depends on:

- `algimantas-rusteika-2423645` — council-only, coalition list, not elected
- `algirdas-gudaitis-2420505` — council-only, party list, elected to the council
  (the `Išrinktas pagal … sąrašą` note)
- `algirdas-zebrauskas-2424292` — dual candidate, coalition list, elected to the
  council but not as mayor, self-nominated for mayor. The only fixture that
  exercises both recovered fields: a campaign `sprendimai` decision and a
  `kiti-duomenys` private-interest free-text section
- `ingrida-sakalauskiene-2425331` — council-only, party list, not elected, low
  on the list
- `linas-urmanavicius-2421676` — council-only, political committee list, elected
  (guards the committee list name, which is neither a party nor a coalition)
- `mykolas-majauskas-2420485` — mayor-only, self-nominated, not elected; the
  largest campaign in the set (98 donation records, 19 contracts)
- `rasa-vitkauskiene-2423015` — dual, elected mayor in round II, party-nominated,
  `Atstovaujamasis` campaign participant. Her note is the feminine `Išrinkta …`
- `skirmantas-mockevicius-2422343` — mayor-only, self-nominated, elected mayor in
  round II
- `vitalijus-mitrofanovas-2425352` — dual, elected mayor in round I, whose
  `Atstovaujamasis` campaign publishes a donations tab with nothing in it

Between them these cover all three `profilis.kita` key sets (council-only,
mayor-only, dual), both nomination labels, both `pastaba` forms in both genders,
role-dependent presence of the campaign tab, and both campaign participant
types.

Because the fixture set is a sample rather than the field, it pins nothing about
coverage: an archetype not in the list above — a candidate with conviction
details, say — is not exercised by any test in this election.

Its samples directory also holds the listing fixtures, which are not candidate
directories and are allowlisted separately by the same test:

- `page.html` — the wrapper page
- `list.html` — the mayoral listing (433 candidates)
- `lists-index.html` — the index of 467 party, coalition and committee lists
- `lists/` — one file per list, `rpgId-<municipality>_rorgId-<list>.html`, 467
  files, and the test asserts that count. The sitemap needs all of them: a
  missing file is reported as `missing-list-sample` and its candidates are
  simply absent from the output.

For `2019-kovo-3-savivaldybiu-tarybu` the allowlist
(`tests/test_savivaldybiu_2019_sample_allowlist.py`) is **nine candidates out of
13,666** — a sample rather than the field, for the same reason as the 2023
municipal election. The archetypes are the ones the record shape depends on:
role (council-only, mayor-only, dual), list kind, nomination kind, and how the
person did:

- `agne-aleksejevaite-2409490` — council-only, party list, not elected. No
  campaign section, no photo, empty biography
- `gediminas-dauksys-2408494` — dual, `visuomeninis rinkimų komitetas` list,
  won the council seat but **lost** the mayoralty in round II (so `isrinktas`
  is true while `meras.elected` is false). The only fixture whose "Kita" tab
  carries a document — a signed pledge not to bribe voters
- `judita-ziliene-2409466` — council-only, party list, elected. Her note is the
  feminine `Išrinkta pagal … sąrašą`
- `kestutis-armonas-2404237` — council-only, **coalition** list, elected
  (guards the coalition list name, and the genitive inflection of every member
  party inside the elected note). Also the fixture that answered Q21, whose
  answer the parser currently drops — see `docs/OUTPUT_SCHEMA.md`
- `nerijus-cesiulis-2406286` — dual, elected mayor in **round II**
- `ricardas-juska-2413847` — mayor-only, party-nominated, not elected; the
  candidate who declared neither education, languages nor prior mandates
- `skirmantas-mockevicius-2400117` — mayor-only, **self-nominated**
  (`išsikėlė pats`), elected mayor. The only fixture with a `Savarankiškas`
  campaign participant: treasurer, auditor, donation records, a financing
  report and contracts
- `vitalijus-mitrofanovas-2406746` — dual, elected mayor in **round I**
- `vytas-jareckas-2404239` — dual, coalition list, elected mayor, and the only
  fixture answering a declaration with `Einu` rather than `Neinu`

Between them these cover all three `profilis.kita` key sets, both `pastaba`
forms in both genders, both election rounds, all three list kinds (party,
coalition, committee), self- and party-nomination, role-dependent presence of
the campaign section, the photo and biography, and both campaign participant
types. All nine parse with zero anomalies.

Because the fixture set is a sample, it pins nothing about coverage: an
archetype not listed above — a candidate who answered the conviction question
"Taip", say — is exercised by no test in this election.

Its samples directory also holds the listing fixtures, allowlisted separately
by the same test:

- `page.html` — the wrapper page
- `list.html` — the mayoral listing (410 candidates)
- `lists-index.html` — the index of 465 party, coalition and committee lists
- `lists/` — one file per list, `rpgId-<municipality>_rorgId-<list>.html`, 465
  files, and the test asserts that count. The sitemap needs all of them: a
  missing file is reported as `missing-list-sample` and its candidates are
  simply absent from the output.

For `2023-rugsejo-3-seimo-raseiniai-kedainiai` the allowlist
(`tests/test_seimo_raseiniu_kedainiu_2023_sample_allowlist.py`) is the complete
eight-candidate field of this single-constituency by-election:

- `algirdas-gricius`
- `andrius-bautronis`
- `antanas-tautkus`
- `darius-ulickas`
- `edvinas-demidavicius`
- `matas-skamarakas`
- `meida-sabuniene`
- `sandra-barzdiene`

This covers the elected candidate (elected note in the profile, second round), a
candidate with conviction details (`13.1`-`13.4`), and both campaign participant
types — self-standing (`Savarankiškas`, with treasurer, auditor, financing
reports and contracts) and party-represented (`Atstovaujamasis`, donations only).

For `2025-kovo-16-meru` the allowlist
(`tests/test_meru_2025_sample_allowlist.py`) is the complete fourteen-candidate
field across the three municipalities that voted:

- Jonavos rajono: `jolita-peleckiene`, `povilas-beisys`, `renata-sorakiene`,
  `romanas-steponavicius`
- Joniškio rajono: `benjaminas-rimdzius`, `gediminas-cepulis`,
  `liudas-jonaitis`, `saulius-kuzmarskis`
- Panevėžio miesto: `algimantas-kolpertas`, `ignas-gaiziunas`,
  `julius-limantas`, `loreta-masiliuniene`, `saulius-raziunas`, `solveiga-dage`

This covers the two elected mayors, both campaign participant types, and the
four Jonava candidates struck off by Seimas resolution — who carry a
`candidateNote` and publish no campaign tab.

For `2017-balandzio-23-meru` the allowlist
(`tests/test_meru_2017_sample_allowlist.py`) is the complete eleven-candidate
field:

- Jonavos rajono: `alina-batuleviciene`, `bronislovas-liutkus`, `darius-mockus`,
  `eugenijus-sabutis`, `remigijus-osauskas`, `rimantas-kiseliovas`
- Šakių rajono: `dinara-gudaitiene`, `edgaras-pilypaitis`,
  `raimondas-janusevicius`, `raminta-bastyte`, `vidas-cikana`

This covers the two elected mayors, a candidate who left a declaration blank,
candidates with prior-mandate record tables, and the four whose campaign data is
only reachable through the fallback participant URL.

For `2017-rugsejo-10-marijampoles-mero` the allowlist
(`tests/test_marijampoles_mero_2017_sample_allowlist.py`) is the complete
eight-candidate field:

- `algis-zvaliauskas`
- `dobilas-sinkevicius`
- `gediminas-akelaitis`
- `gintaras-skamarocius`
- `irena-lunskiene`
- `karolis-dvylys`
- `kestutis-traskevicius`
- `saulius-skinkys`

This covers the elected mayor, self-nominated and party-nominated candidates, a
candidate with six prior mandates, one who answered "Nenurodė" to the education
and prior-mandate questions, one who left a declaration blank, and both campaign
participant types.

For `2021-spalio-10-meru` the allowlist
(`tests/test_meru_2021_sample_allowlist.py`) is the complete fourteen-candidate
field:

- Kelmės rajono: `algirdas-sakalauskas`, `dalia-viliuniene`, `egidijus-uksas`,
  `ildefonsas-petkevicius`, `jolita-koryzniene`, `juozas-rimkus`,
  `lina-samulyte`, `stasys-jokubauskas`
- Trakų rajono: `adas-jakubauskas`, `andrius-satevicius`, `dainius-narkevicius`,
  `jaroslav-narkevic`, `jonas-kietavicius`, `ramunas-ausrotas`

This covers the two elected mayors, a self-nominated candidate, both campaign
participant types, and the one candidate with a conviction record — whose nested
detail table is what exposed the shared `<tbody>` lookup bug.

For `2021-balandzio-11-radviliskio-mero` the allowlist
(`tests/test_radviliskio_mero_2021_sample_allowlist.py`) is the complete
seven-candidate field:

- `aurimas-gaidziunas`
- `gediminas-lipnevicius`
- `jolanta-margaitiene`
- `jurgis-baublys`
- `kazimieras-rackauskis`
- `mantas-reutas`
- `vytautas-simelis`

This covers the elected mayor, a self-nominated candidate with both a conviction
record and the only populated "Kita" tab in the repository, and both campaign
participant types.

For `2017-balandzio-23-seimo-anyksciai-panevezys` the allowlist
(`tests/test_seimo_anyksciu_panevezio_2017_sample_allowlist.py`) is the complete
eleven-candidate field:

- `antanas-baura`, `aukse-kontrimiene`, `edita-tamosiunaite`,
  `egidijus-baltusis`, `kristupas-augustas-krivickas`, `lukas-pakeltis`,
  `mindaugas-pauliukas`, `ricardas-sargunas`, `romualdas-gegznas`,
  `valentinas-sapalas`, `valentinas-stundys`

This covers the elected member (whose elected note shares the name cell),
candidates with prior-mandate tables of several sizes, a candidate who declared
neither education nor mandates, and both campaign participant types.

For `2018-rugsejo-16-seimo-zanavykai` the allowlist
(`tests/test_seimo_zanavyku_2018_sample_allowlist.py`) is the complete
six-candidate field: `giedrius-surplys`, `irena-haase`, `mindaugas-bastys`,
`mindaugas-tarnauskas`, `paulius-visockas`, `vigilijus-jukna`. It covers the
elected member, self-nominated candidates, and prior-mandate tables of three and
five records.

For `2019-rugsejo-8-seimo` the allowlist
(`tests/test_seimo_2019_sample_allowlist.py`) is the complete twenty-seven
candidate field across the three constituencies that voted. It covers one winner
per constituency, both campaign participant types, and the candidate nominated by
two parties whose second nominator would otherwise be dropped.

For `2015-kovo-1-seimo-zirmunai` the allowlist
(`tests/test_seimo_zirmunu_2015_sample_allowlist.py`) is the complete
twelve-candidate field:

- `anzela-andruskevic`, `lilijana-astra`, `renata-cytacka`, `algis-caplikas`,
  `ricardas-garuolis`, `vanda-birute-gineviciene`, `sarunas-gustainis`,
  `radvile-morkunaite-mikuleniene`, `zydrunas-plytnikas`, `algirdas-raslanas`,
  `joana-tamkeviciute`, `gediminas-vagnorius`

This covers the winner (Gustainis — though no 2015 page marks him as such),
a self-nominated candidate, both campaign participant types (two candidates are
represented by their party), candidates with and without prior-mandate tables,
a `Nenurodė` marital status, a typed "Neturiu" child answer, and the one
candidate without a program PDF. Candidate directories also hold a
`campaigns/dalyvis-<id>/` capture of the participant's five campaign tabs (or
`root.html` for represented participants).

For `2015-birzelio-7-seimo-varena-eisiskes` the allowlist
(`tests/test_seimo_varenos_eisiskiu_2015_sample_allowlist.py`) is the complete
eight-candidate field:

- `andzej-andruskevic`, `juozas-baublys`, `vidmantas-bizokas`,
  `marius-juskevicius`, `gitana-markoviciene`, `vidas-mikalauskas`,
  `miroslavas-monkevicius`, `virginijus-varanavicius`

Seven candidates are represented by their nominating party's campaign
(`root.html` card captures); the one self-nominated candidate is the only
independent participant with the full five campaign tabs.

For `2015-lapkricio-8-telsiu-mero` the allowlist
(`tests/test_telsiu_mero_2015_sample_allowlist.py`) is the complete
seven-candidate field:

- `algirdas-bacevicius`, `petras-kuizinas`, `almantas-lukavicius`,
  `deivydas-rubezius`, `jolanta-rupeikiene`, `mantas-serva`, `saulius-urbonas`

This covers the municipal anketa variant, a self-nominated candidate whose
card carries "Išsikėlęs kandidatas" instead of list fields, both campaign
participant types, a candidate who answers the incompatible-duties question
"Einu", and one who answered almost nothing ("Nenurodė" throughout).

For `2015-birzelio-7-pakartotiniai-sirvintos-trakai` the allowlist
(`tests/test_pakartotiniai_sirvintu_traku_2015_sample_allowlist.py`) is a
curated ten of the 327 candidates, the municipal-general pattern rather than
the whole-field one the small by-elections use:

- `zivile-pinskuviene`, `rita-tamasuniene`, `marija-puc`, `marija-puc-2`,
  `dangute-mikutiene`, `vytautas-zalieckas`, `kestutis-vilkauskas`,
  `kestutis-mikulskas`, `julija-meskauskiene`, `albertas-malasauskas`

This covers both municipalities, mayoral-only, council-only and dual
candidacies, both campaign participant types, and the two ids VRK issued to
Marija Puč — including the `Rengiama` placeholder page whose questionnaire was
never published. The samples tree also carries the two district listing pages
and a `lists/` directory with all nine party-list pages, because the sitemap
is rebuilt from them offline.

For `2015-birzelio-21-pakartotiniai-silutes` the allowlist
(`tests/test_pakartotiniai_silutes_2015_sample_allowlist.py`) is a curated ten
of the 366 candidates:

- `alfredas-stasys-nauseda`, `sandra-tamasauskiene`, `arvydas-jakas`,
  `virgilijus-pozingis`, `tomas-budrikis`, `vytautas-laurinaitis`,
  `jonas-jatautas`, `daiva-zebeliene`, `jonas-sakurskis`, `jonas-sakurskis-2`

The first eight are this election's dual candidates, who between them stand on
all eight party lists including the `Visuomeninis rinkimų komitetas`. The last
two are different people who share a name, one of whom has no campaign
participant link at all. The district page and all eight list pages are
captured alongside them.

For `2015-kovo-1-savivaldybiu` the allowlist
(`tests/test_savivaldybiu_2015_sample_allowlist.py`) is **nine candidates out
of 15,149** — a sample rather than the field, as with the 2019 and 2023
municipal generals:

- `skirmantas-mockevicius-71130`, `mindaugas-filipavicius-71111` — mayor-only,
  both published as a bare name with no nominator clause
- `adele-dimsiene-85873` — dual, committee list, list head
- `irina-rozova-80134` — dual, coalition list
- `albinas-klimas-79174` / `albinas-klimas-85125` — two different people who
  share a name, in Plungė and Akmenė, born a year apart; the pair that shows
  why the id carries VRK's own candidate id
- `jelena-berezina-74643` — council-only, position 61 on its list
- `valius-micevicius-85875` — council-only, committee list, and the fixture
  with no campaign participant at all
- `antanas-gasparavicius-86679` — council-only, list head

Its samples directory also holds the listing tree, allowlisted separately:
`index.html` (VRK's municipality index), `merai.html` (the mayoral roll-up
used as the sitemap's cross-check), 60 `district-<id>.html` pages and a
`lists/` directory of 478 list pages. The tests assert both counts, because a
missing list page silently drops its candidates from the sitemap.

## CLI behavior and guardrail

By default, sample-fetch commands do not allow creating new candidate directories:

- `fetch-first-candidate-samples`
- `fetch-candidate-samples`

To intentionally add a new fixture directory, pass:

- `--allow-new-samples`

## When adding fixtures intentionally

1. Capture new fixture with `--allow-new-samples`.
2. Validate parser output and anomaly behavior.
3. Update allowlist test if fixture set is intentionally changed.
4. Keep fixture set small and representative.

## Recommended baseline checks

```bash
pytest tests/test_seimo_2016_sample_allowlist.py
pytest tests/test_seimo_2016_candidate_samples.py
pytest tests/test_seimo_2016_campaign_parser.py
```
