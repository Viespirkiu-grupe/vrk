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

For `2011-vasario-27-savivaldybiu` the allowlist
(`tests/test_savivaldybiu_2011_sample_allowlist.py`) is **ten candidates out
of 16,403**, chosen for the shapes the record depends on in the one general
election where individuals stood for the council on their own:

- `darius-norkus-42302`, `mindaugas-kaknevicius-26835` — self-nominated
  individuals (Vilnius, Alytus): a ballot number, no list, the card's
  "Išsikėlęs kandidatas" flag
- `valdemaras-stancikas-42569`, `visvaldas-matijosaitis-29278`,
  `arturas-zuokas-42680` — leaders of coalitions of self-nominated
  candidates; Zuokas the elected one, and the one with a conviction
  explanation after Q9
- `arunas-karlonas-43800`, `arunas-burksas-27707` — leaders of party
  coalitions (Kauno rajonas, Neringa), whose cards carry the member party as
  a second `(Iškėlė` nomination
- `viktor-uspaskich-48972` — party list head (Darbo partija, Vilnius)
- `rimvydas-buinickas-59139` — party list, position 60
- `diana-jokimciene-kachabrisvili-44060` — a double surname, position 31

Its samples directory also holds the listing tree: `index.html` (VRK's
municipality index), the three roll-ups used as the sitemap's cross-checks
(`issikele.html`, `koalicijos.html`, `issikele-koalicijos.html`), 60
`district-<id>.html` pages (ids 7131–7190) and a `lists/` directory of 599
list pages. Every candidate has exactly the four tabs; there is no
Biografija and no campaign subtree in this election.

For `2007-vasario-25-savivaldybiu` the allowlist
(`tests/test_savivaldybiu_2007_sample_allowlist.py`) is **ten candidates out
of 13,422**, chosen for the shapes the record depends on in the oldest
municipal election with candidate pages (party lists only, no
self-nomination of any kind):

- `arvydas-vysniauskas-7357` — party list head (LSDP, Elektrėnai), elected;
  the FR0462 income filed on the main form, two flats and two employers in
  the interest declaration (the rows the record-table fix keeps)
- `algirdas-strignatavicius-7436` — the same list's last position, 33 of a
  ballot numbered 1–33 with 29 withdrawn
- `arturas-zuokas-12711`, `rolandas-paksas-1537` — list heads in Vilnius,
  the largest municipality (687 candidates); Zuokas has the
  "Moksliniai laipsniai" line
- `viktor-uspaskich-9852` — position 25 of the Kėdainiai Darbo partija
  list, seated third on preference votes; Russian nationality on the form
- `vigantas-giedraitis-2544`, `bronis-rope-660`, `danute-mileikiene-3258` —
  leaders of three of the four party coalitions (Neringa and Ignalina
  elected, Telšiai not); their cards carry a second "Numeris partijos
  sąraše" line, and Mileikienė's five FR0462 lines are all zero
- `giedre-ramanauskaite-kedikiene-9665` — a double surname, position 21
- `zigfridas-herbertas-pilvinis-996` — a three-part name whose
  questionnaire stops after an empty "Gimimo vieta" and "Tautybė" (the
  empty-answer row boundary), and an "Einu" on the incompatible-office
  question

Its samples directory also holds the listing tree: `index.html` (VRK's
index of municipalities and parties), a `parties/` directory of the 24
by-party pages used as the sitemap's cross-check, 60 `district-<id>.html`
pages (ids 6776–6835) and a `lists/` directory of 600 list pages. Every
candidate has exactly the three tabs; there is no Biografija, no Kita and
no campaign subtree in this election.

For `1996-spalio-20-seimo` the allowlist (`tests/test_seimo_1996_sample_allowlist.py`)
is a curated five of the 879 candidates:

- `asmolkov-vasilij` — party-nominated, dual candidacy (single-mandate seat
  plus a `Daugiamandatė` multi-mandate list position)
- `butkevicius-audrius` — self-nominated (`Išsikėlė pats`), single candidacy
- `andriukaitis-vytenis-povilas` — party-nominated, single candidacy, a
  well-known figure to sanity-check the biography text against
- `saltiene-irena` — has no photo
- `astrauskas-vytautas` — has no biography link, and is also dual-candidacy

The samples tree also carries a `constituencies/` directory with all 71
`apgtl.htm` crawl pages the sitemap is built from — discovery scaffolding,
allowlisted separately from the candidate fixtures.

For `1997-kovo-23-seimo-pakartotiniai` and `1997-gruodzio-21-seimo-pakartotiniai`
the allowlists (`tests/test_seimo_pakartotiniai_1997_kovo_sample_allowlist.py`,
`tests/test_seimo_aukstaitijos_1997_gruodzio_sample_allowlist.py`) are the
complete fields — 23 and 4 candidates — since both re-run elections are this
small already. The March re-run's fixture set covers both a masculine and a
feminine self-nomination spelling (`Išsikėlė pats` / `Išsikėlė pati`).

For `1997-kovo-23-savivaldybiu-tarybu` the allowlist
(`tests/test_savivaldybiu_1997_sample_allowlist.py`) is **six candidates out
of 6,276** — a sample rather than the field, as with the other municipal
generals:

- `pilvelis-algirdas`, `kizelavicius-stasys`, `dapkus-ramualdas`,
  `margeviciene-vince-vaidevute` — spread across four different municipalities
  (Vilnius, Alytus, Birštonas, Kaunas cities), each a party-list head
- `tamulevicius-kestutis` / `tamulevicius-kestutis-2` — two different people
  (VRK ids 37862 and 37809) who share a name, in Alytus and Druskininkai; the
  pair that guards the positional `-2` suffix against a false merge
- `abariunas-bronius` — a page that prints **no** `Gimimo vieta` label. Every
  other fixture happens to carry the full label set, which is why all six
  passed while 91% of the election's real records had a birth date that had
  swallowed the following labels. Added as the regression guard once the full
  corpus was reconciled; the lesson is that a fixture set chosen for
  *content* variety can still be uniform in *structure*.

Its samples directory also holds the listing tree: `municipalities/` (56
`apgtl.htm` pages) and `lists/` (449 `pkal.htm` party-list pages), since the
sitemap is rebuilt from them offline the same way the Seimas archive's
`constituencies/` directory works.

For `1997-birzelio-29-svenciniu-tarybos-pakartotiniai` the allowlist
(`tests/test_svencioniu_tarybos_1997_sample_allowlist.py`) is the **complete
field — all 110 candidates** across the nine party lists Švenčionys fielded in
the repeat vote, small enough that a curated subset would not save much and
the full field is a stronger regression guard. Its samples directory holds the
same `municipalities/`/`lists/` scaffolding as the general election, scoped to
the one municipality.

For `2014-prezidento` the allowlist
(`tests/test_prezidento_2014_sample_allowlist.py`) is the complete
seven-candidate field:

- `zigmantas-balcytis`, `dalia-grybauskaite`, `arturas-paulauskas`,
  `naglis-puteikis`, `bronis-rope`, `valdemar-tomasevski`, `arturas-zuokas`

All seven are independent campaign participants with the five campaign tabs.
Every candidate directory also holds `patiketiniai.html`, the presidential
elections' sixth tab (trustees) — Balčytis's is a "Duomenų nėra" page, the
empty-list case; Balčytis is also the one candidate whose `Kita` tab links a
program PDF. Grybauskaitė's campaign link points at election path `423_lt`,
not the candidate pages' `424_lt`.

For `2007-spalio-7-seimo-dzukija` the allowlist (`tests/test_seimo_dzukijos_2007_sample_allowlist.py`)
is the complete ten-candidate field: four independent campaign participants
(Čilinskas, Truncė, Uspaskich, Kadžys — the donor tables and financing
reports) and six represented ones whose cards say so in words and link no
campaign. The samples directory holds the district page as `list.html` (the
index is a meta-refresh to it). No candidate directory holds a `kita.html`.

For `2008-seimo` the allowlist (`tests/test_seimo_2008_sample_allowlist.py`)
is **eight candidates out of 1,603**, chosen for shape as for 2012: a
list-only list leader (`gediminas-kirkilas`), a dual list+constituency
leader (`andrius-kubilius`), a coalition nominee from each member party
(`loreta-grauziniene`, `virginija-baltraitiene`), a self-nominated
constituency candidate (`valdemaras-puodziunas`), a single-member-only
party's candidate (`vytautas-aleksas-lazinka`), and both name collisions
(`arunas-rimkus-2`, `algis-kaseta-2` — the latter one of two Algis KAŠĖTAs
in the same constituency). The samples directory holds both indexes
(`list.html`, `districts.html`), the 16 list pages plus the 4 side pages
under `lists/` (no self-nominated page exists in 2008) and the 71
constituency pages under `districts/`. No candidate directory holds a
`kita.html` or a `campaigns/` tree: the 2008 pages publish neither.

For `2009-ep` the allowlist (`tests/test_ep_2009_sample_allowlist.py`) is
**fifteen candidates out of 262** — the leader of each of the fifteen lists,
the same rule as `2014-ep`: `saulius-stoma`, `algirdas-paleckis`,
`rolandas-paksas`, `vilija-blinkeviciute`, `egidijus-skarbalius`,
`ona-jukneviciene`, `leonidas-donskis`, `valdemar-tomasevski`,
`eugenijus-maldeikis`, `gediminas-vagnorius`, `vytautas-landsbergis`,
`viktor-uspaskich`, `jonas-viesulas`, `arturas-zuokas`, `gintaras-didziokas`.
Six of them were elected. The set covers the shapes the full field has:
Zuokas's Q9.2 "Taip" with the free-text explanation, Landsbergis's and
Maldeikis's two-answer degree line (degree and pedagogical title),
Tomaševski's dead campaign link (his presidential participant id under the
EP path — the fixture's `index.json` carries the one `CampaignRootFetchFailed`),
and the roman-numbered interest sections II–VIII across the fifteen. The
samples directory holds the list index (`list.html`) and the fifteen list
pages under `lists/`.

For `2009-prezidento` the allowlist
(`tests/test_prezidento_2009_sample_allowlist.py`) is likewise the complete
seven-candidate field:

- `algirdas-butkevicius`, `loreta-grauziniene`, `dalia-grybauskaite`,
  `ceslovas-jezerskas`, `valentinas-mazuronis`,
  `kazimira-danute-prunskiene`, `valdemar-tomasevski`

All seven are independent campaign participants with five campaign tabs
(`izdininkas`, `auditorius`, `aukotoju-sarasas`, `finansavimo-ataskaitos`,
`sutartys`). No directory holds `patiketiniai.html`: the tab is linked on
every page but VRK never published the file (all seven are 404s), and each
`index.json` records the link under `unpublishedTabs`. Grybauskaitė's
donor list is the largest (141 rows, eight flagged unacceptable inline);
Jezerskas's is the smallest (3) and his is one of the five empty auditor
pages. Butkevičius's `Kita` tab links three PDFs (the foreign-services
questionnaire, a health certificate, the party's nomination decision);
Grybauskaitė's and Prunskienė's anketa carry the academic-degree line,
which the other five omit.

For `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai` (`tests/test_seimo_silales_silutes_vilniaus_salcininku_2009_sample_allowlist.py`)
and `2011-vasario-13-seimo-marijampole` (`tests/test_seimo_marijampoles_2011_sample_allowlist.py`) the
allowlists are the complete fields — 17 candidates across the two November
2009 constituencies (9 in Šilalės–Šilutės, 8 in Vilniaus–Šalčininkų) and
the 9 of Marijampolės — with both campaign participant types in each (10
represented + 7 independent; 4 + 5). The samples directories hold the
constituency index (`list.html`) and the constituency pages under
`districts/`.

For `2013-kovo-3-seimo-birzai-zarasai-ukmerge` the allowlist
(`tests/test_seimo_birzu_zarasu_ukmerges_2013_sample_allowlist.py`) is the
complete 37-candidate field across the three constituencies (11 in
Biržų–Kupiškio, 12 in Zarasų–Visagino, 14 in Ukmergės). It spans both
campaign participant types (24 represented, 13 independent), three
self-nominations, six candidates with a second-round results link, and the
sparse forms that omit Q12–Q15 entirely (`algimantas-dumbrava`). The samples
directory holds the constituency index (`list.html`) and the three
constituency pages under `districts/`.

For `2014-ep` the allowlist (`tests/test_ep_2014_sample_allowlist.py`) is
**ten candidates out of 215** — the leader of each of the ten lists:

- `gintaras-steponavicius`, `algirdas-saudargas`, `valdemar-tomasevski`,
  `viktor-uspaskich`, `rolandas-paksas`, `linas-balsys`, `julius-panka`,
  `arturas-melianas`, `ramunas-karbauskis`, `zigmantas-balcytis`

One per list pins list name, number and position for every list;
`valdemar-tomasevski` is the coalition nominee whose card repeats `Iškėlė`
for the member party. The samples directory holds the list index
(`list.html`) and the ten list pages under `lists/`. The field is scraped by
`scripts/run_election_batches.sh`.

For `2012-seimo` the allowlist (`tests/test_seimo_2012_sample_allowlist.py`)
is **nine candidates out of 1,927**, chosen for listing shape rather than
content:

- `algirdas-butkevicius` — list leader who also stood in a constituency
  (both candidacies, both results links)
- `alvydas-medalinskas` — coalition list nominee (member party on the list
  row and, in parentheses, on the card — the card's third `Iškėlė`)
- `naglis-puteikis` — party list candidate whom the constituency listing
  records as nominated by the party *and* self-nominated
- `gediminas-navaitis` — self-nominated in a constituency, on a coalition
  list; one of the three "tik vienmandatėse" page entries who also hold a
  list seat
- `vilija-blinkeviciute` — list only (the list page's empty `Apygardanull`
  constituency link)
- `linas-balsys` — self-nominated, constituency only, both rounds
- `tirkisas-amanovas` — nominee of a party that ran in constituencies only
- `arunas-markunas` / `arunas-markunas-2` — two different people who share a
  name, on two different lists; the one positional `-2` in the election

The samples directory holds both indexes (`list.html` for the lists,
`districts.html` for the constituencies), the 18 list pages plus the 11 side
pages (coalition members, single-member-only parties, the self-nominated)
under `lists/`, and the 71 constituency pages under `districts/`. The field
is scraped by `scripts/run_election_batches.sh`.

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
