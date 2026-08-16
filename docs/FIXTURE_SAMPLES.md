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
