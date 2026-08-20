# Plan: the six 2015 backlog elections (issues #48–#53)

> **Status (2026-08-20).** Four of six modules are built, tested, wired and
> documented: `seimo_zirmunu_2015` (#48), `seimo_varenos_eisiskiu_2015` (#50),
> `telsiu_mero_2015` (#53) and `pakartotiniai_sirvintu_traku_2015` (#51).
> Remaining: `pakartotiniai_silutes_2015` (#52), then `savivaldybiu_2015`
> (#49). What the build settled, beyond §2 below:
>
> - The era machinery lives in `seimo_zirmunu_2015` with election id, listing
>   URL, paths, expected tabs and the anketa-rows normalizer as call-time
>   parameters; sibling modules are three files of constants and wrappers.
> - The municipal question mapping lives in `telsiu_mero_2015`
>   (`normalize_municipal_anketa_rows`) and is what #52 and #49 should reuse.
> - #51's sitemap already does the two-structure walk and the id merge, so it
>   is the closer model for #52 than the by-election modules are.
> - Defect found and fixed mid-build: the municipal profile cards wrap the
>   name in `<p texttransform>`, and the walker was putting VRK's boilerplate
>   notice in `profilis.vardas-pavarde` on every municipal record. Any new
>   municipal module inherits the fix; check names explicitly anyway.
> - VRK can issue one person two candidate ids in one election (Marija Puč,
>   #51). The id join is still right — do not merge on name — but the
>   marker/join cross-check has to be read, not assumed zero.
> - A candidacy can have no questionnaire at all (`Rengiama`); that is an
>   `AnketaNotPublished` warning, not a parse failure.
> - Full scrapes are still outstanding for #51, #52 and #49 (fixture sets
>   only); the three small by-elections are complete fields already.
> - Downstream registration is done: person-index order, dashboard labels,
>   concept map and `goal.md` scope all know about the 2015 elections.
> - Elected status is **still not shipped** — see the rewritten §4 below.

Written 2026-08-19 from live-page research. All six `help wanted` / `missing-election`
issues are 2015 elections, and all of them share **one page-layout family that the
project has never parsed** — older than the 2016 era, with its own quirks. That makes
them one coherent project: build the era's parsers once against the smallest election,
then reuse them five times. Implementation has not started; this document is the map.

## 1. Inventory

Maintainer comments on each issue supply the entry URLs. Verified against the live
pages on 2026-08-19:

| Issue | Election | VRK id | Listing entry point | Scale |
|---|---|---|---|---|
| #48 | 2015-03-01 Seimo by-election, Žirmūnai Nr. 4 | 448 | `rinkimai/448_lt/Apygardos/Apygarda7822/KandidataiApygardos7822.html` | 12 candidates |
| #49 | 2015-03-01 municipal general (first direct mayors) | 440 | `rinkimai/440_lt/Kandidatai/index.html` | 434 mayoral anketa links + ~15k council candidates (confirm at sitemap stage) |
| #50 | 2015-06-07 Seimo by-election, Varėna–Eišiškės Nr. 70 | 459 | `rinkimai/459_lt/Apygardos/Apygarda7925/KandidataiApygardos7925.html` | 8 candidates |
| #51 | 2015-06-07 repeat: Širvintos mayor + Trakai | 452 | `rinkimai/452_lt/Apygardos/Apygarda7921/…` (Širvintos) and `…/Apygarda7911/…` (Trakai) | Širvintos 7 mayoral; Trakai 8 mayoral + ~7 council lists |
| #52 | 2015-06-21 repeat: Šilutė | 457 | `rinkimai/457_lt/Apygardos/Apygarda7923/KandidataiApygardos7923.html` | 8 mayoral + ~6 council lists |
| #53 | 2015-11-08 Telšiai mayoral by-election | 469 | `2015_4_savivaldybiu_tarybu_rinkimai/469_lt/Apygardos/Apygarda7935/KandidataiApygardos7935.html` | 7 mayoral candidates |

All paths relative to `https://www.vrk.lt/statiniai/puslapiai/`. Notes:

- **District ids in 452 are counterintuitive**: Apygarda7911 is *Trakai*,
  Apygarda7921 is *Širvintos*. Trust the `<h3>` on the page, not the issue title.
- The pages show **more than the official election titles claim**: Trakai (7911) and
  Šilutė (7923) each list mayoral candidates *and* council party lists; Širvintos
  (7921) and Telšiai (7935) list mayoral candidates only, with an empty lists
  section. Scrape what the pages hold, not what the title implies.
- **469 lives under a nonstandard base** — `2015_4_savivaldybiu_tarybu_rinkimai/469_lt/`
  instead of `rinkimai/469_lt/`. Module URL constants must not assume `rinkimai/`.
- #51 and #52 share one Liferay wrapper page
  (`vrk.lt/2015-pakartotiniai-savivaldybiu-tarybu-rinkimai`) but are separate VRK
  elections (452, 457) with separate `<h1>` titles → **separate modules**, one per issue.

## 2. The "2015 era" layout family (new)

Every candidate page across all six elections uses the same pre-2016 static layout.
Evidence pages: Žirmūnai candidate 87326 (Seimo variant), municipal candidate 73632
(municipal variant, Birštonas mayor).

**Tabs are separate static HTML files, not tabs on one page.** Per candidate:
`Kandidato<ID>Anketa.html`, `…Biografija.html`, `…Deklaracijos.html`
(labelled "Turto ir pajamų deklaracijos"), `…InteresuDeklaracija.html`, `…Kita.html`.
Two consequences for existing machinery:

- The tab links are **bare `<li>` siblings in the body, not inside `ul#tabnav`**
  (`ul#tabnav` exists on *district* pages but not candidate pages). The tab discovery
  in existing `candidate_samples.py` modules (`soup.select("ul#tabnav a[href]")`)
  finds nothing here — the 2015 module needs its own extraction
  (e.g. `a[href*='Kandidato']` filtered to the five known stems).
- The candidate-link stem is `Kandidato<ID>Anketa.html`. The marker used by later
  modules (`KandidatasAnketa`) does **not** match it. Use `re.compile(r"Kandidato\d+Anketa\.html")`.

**Tab slugs from labels** would come out as: `anketa`, `biografija`,
`turto-ir-pajamu-deklaracijos`, `interesu-deklaracija`, `kita` — note
`interesu-deklaracija`, not the 2017-era `privaciu-interesu-deklaracija`.

**Photos are already external JPG sidecars** — `Kandidato<ID>Foto.jpg` referenced by
`<img src>`, no base64 anywhere. This fits the new sidecar-photo pipeline (commit
df8803e) directly, but the fetch stage must download the JPG as a separate request,
and some candidates may have none (verify at fixture stage).

**Anketa markup**: one `<td>` holding the whole questionnaire as inline text —
`<br/>`-separated numbered questions with answers in `<b>`, plus nested `<table>`s
for Q12 (education) and Q15 (previously elected). Nothing like the row-per-question
tables of 2016+; the parser walks a single cell's mixed content. Two question sets:

- *Seimo variant* (448, 459): Q5 birth date, Q6 address, Q8.1–8.4 (Seimo rinkimų
  įstatymo 38 str. 4 d.), Q9.1–9.2 (98 str. 1/3 d.), Q10 birthplace, Q11 nationality,
  Q12 education table, Q13 languages, Q14 party, Q15 elected-history table,
  Q16 workplace, Q17 public activity, Q18 hobbies, Q19 marital status (+ spouse
  name), Q20 children.
- *Municipal variant* (440, 452, 457, 469): same skeleton, but Q8.1–8.3 cite the
  savivaldybių tarybų rinkimų įstatymo 36 str. 11 d., Q8.3 embeds a long statute
  quotation before the answer, and answers are verbose ("Neturiu", "Nesu") rather
  than "Ne". This mirrors the existing 2016-Seimo vs 2017-mayoral split — same era,
  two question mappings.

**Other tabs**:

- *Biografija*: free text (like `meru_2017`).
- *Deklaracijos*: turto declaration extract + GPM308 income extract, **amounts in
  litas (`Lt`), not EUR**, with its own row wording (another income-alias restatement,
  as happened between 2017 and 2019). The declaration period is stated on the page.
- *Interesų deklaracija*: `ID001J`/`ID001I`-style sections — closest to
  `seimo_2016`'s private-interest parsing; check reuse before writing new code.
- *Kita*: essentially "Kandidato programa" (often just the header). Mayoral
  candidates additionally link a **program PDF** (`KandidatoPrograma<N>.pdf`) from
  the header block — decide whether to record the URL (cheap) or fetch the PDF.
- *Campaign finance*: header links "Savarankiško/Atstovaujamojo politinės kampanijos
  dalyvio duomenys" → `PolitiniuKampanijuFinansavimas/Dalyvis<ID>/Dalyvio<ID>Izdininkas.html`.
  Different URL grammar from 2017's `savarankiskas…_pkdId-<N>.html`, so the existing
  campaign-link pattern won't match; same concept though (savarankiškas vs
  atstovaujamasis distinction survives into later eras).

**No elected markers anywhere in candidate-facing pages.** No "(V)" suffix, no blue
anchors, no elected note in the anketa (checked the Žirmūnai winner's page). Elected
status must come from the results pages — see §4.

## 3. Listing structures per module

- **448, 459 (Seimo by-elections)**: single district page, one `table.partydata`
  with name + nominator columns. Simplest possible sitemap; the pattern of
  `seimo_anyksciu_panevezio_2017` minus the "(V)" handling.
- **469 (Telšiai), 7921-Širvintos half of 452**: district page, mayoral section only:
  rows of "Name — iškėlė Nominator". No table columns; each row is one `<td>` with
  the anketa anchor plus trailing nominator anchors/text.
- **7911-Trakai half of 452, 457 (Šilutė)**: district page with *both* a mayoral
  section and a party-list index; each list page
  (`Apygarda<ID>PartijuKandidatai/Apygarda<ID>Partijos<ID>Kandidatai.html`) holds
  rows "seatNumber Name (kandidatas į savivaldybės tarybos narius - merus)?" with
  anketa links. Dual candidacies are real and merge **on the VRK candidate id in the
  URL** (e.g. Birštonas: id 73632 appears in both mayoral listing and LSDP list) —
  never on name.
- **440 (municipal general)**: the full dual structure at scale:
  - `Kandidatai/KandidataiMerai.html` — all mayoral candidates, grouped by
    municipality, 434 anketa links (official count was 431 — reconcile the
    difference at sitemap stage: duplicates/withdrawn registrations).
  - `Kandidatai/index.html` → 60 municipality district pages → each an index of
    party-list pages holding the council candidates.
  - This is the third municipal general election → per `docs/ADDING_AN_ELECTION.md`,
    it must be a **config module over `scraper/shared/municipal_sitemap.py`**, not a
    third copy. Differences to express in config: listing URLs; dual-candidacy
    marker `(kandidatas į savivaldybės tarybos narius - merus)` (note: the 2019
    marker text is a substring of this — pin tests so neither config matches the
    other's rows); elected flags from a results join instead of blue-anchor
    detection (§4); stable id suffixes (name collisions guaranteed at ~15k);
    per-role `EXPECTED_TABS` (program PDF is mayoral-only).
  - **Verify before building**: whether the shared machinery's fetch/resume/pacing
    accommodates 60 municipality index pages + ~500–800 party-list sub-pages (2019
    and 2023 had a flatter one-index shape). If not, generalize the shared code —
    that is the one place this plan may touch shared machinery.
  - 2015 has no `savKandidataiSuvestine.html`. Cross-check candidates against the
    alternate listing views (`KandidataiPartijos.html`, `KandidataiKoalicijos1.html`,
    `KandidataiKomitetai.html`) and the results pages; row counts, per-structure
    counts and the mayoral/council overlap must reconcile, per the shared-machinery
    doctrine.

## 4. Elected status: investigated, not shipped

Every 2015 record carries `isrinktas: null` / `profilis.pastaba: null`. The
candidate pages mark no winner anywhere, so electedness can only come from
VRK's results tree — and that tree turns out to be harder to read than it
looks. What was established on 2026-08-21, with the traps that make a naive
join wrong:

**The mayoral roll-up is *current* mayors, not election winners.**
`2015_savivaldybiu_tarybu_rinkimai/output_lt/savivaldybiu_tarybu_sudetis/merai_apygarda_ordered.html`
lists 60 mayors as of its 2016-03-08 update. Four of those ids are not even
March 2015 candidates — among them Živilė Pinskuvienė (Širvintos) and Petras
Kuizinas (Telšiai), who won the June and November *repeat* elections this
backlog also covers. Joining on that page would attribute to the March
election people who won a different one.

**The per-municipality pages are the council over the whole term.**
`savivaldybiu_tarybu_sudetis/rapg_<apygardaId>.html` (60 pages, one per
municipality, candidates linked by anketa URL so the join is on VRK's id)
carries the composition *and* a second table of members whose mandate ended
early. Both tables give the date each mandate was recognized. Members seated
on the earliest date on the page are the ones the election returned; anyone
dated later took a vacated seat and was not elected. Each page also states
`Mandatų skaičius, įskaitant merą: N`, which the derived set can be checked
against — a per-municipality invariant, not just a national total.

**Two municipalities legitimately break that invariant, and it is this
backlog's own doing.** Širvintos and Telšiai come out one short (20 of 21, 26
of 27) because neither elected a mayor in March — which is exactly why they
voted again in June and November. Do not "fix" this; assert it.

**Repeat elections also replaced two whole councils.** Trakai's and Šilutė's
March council results were re-run, so their `rapg` pages describe councils
elected in June, not March. Those two municipalities must be excluded from
the March election's elected set and attributed to `#51`/`#52` instead. A
national total that lands near 1,524 without excluding them is wrong in both
directions at once.

**The three small municipal elections state their winner in prose only** —
`.../output_lt/rezultatai_vienmand_apygardose2/apygardos_rezultatai<id>.html`
reads "Meru išrinktas Petras KUIZINAS" with no candidate link — so joining
them means name matching inside a field of 7–8, which is safe but is a second
mechanism, deliberately not mixed in here.

**No results source has been located for the two Seimo by-elections** (448,
459): `Rezultatai/` 404s under both.

Recommended shape when this is picked up: derive from the `rapg` pages only,
per municipality, keyed on the earliest recognition date; assert the mandate
count per municipality; exclude Trakai, Šilutė (councils) and treat Širvintos
and Telšiai as mayor-less; then reconcile the national total. Ship the mayoral
flag from the same pages' `(MERAS)`/`(MERĖ)` marker rather than from the
roll-up.

## 5. Build order and module layout

One shared era package + six thin modules, in this order (each its own
build → fixtures → tests → docs → commit cycle, per the established workflow):

1. **`seimo_zirmunu_2015`** (#48, 12 candidates) — carries the new era package:
   tab discovery for bare-`<li>` pages, the single-cell anketa walker with the
   Seimo question mapping, litas declarations, interest sections, photo sidecar
   fetch, campaign-link pattern. Everything after this is wiring.
2. **`seimo_varenos_eisiskiu_2015`** (#50, 8) — thin wiring over #1, the way
   `marijampoles_mero_2017` wraps `meru_2017`. Proves the family generalizes.
3. **`telsiu_mero_2015`** (#53, 7) — municipal anketa mapping on a tiny election,
   plus the nonstandard `2015_4_…/469_lt` base path and the mayoral-only listing
   parser. Municipal question mapping becomes shared era code here.
4. **`pakartotiniai_sirvintu_traku_2015`** (#51, ~170) — two districts with mixed
   shapes; introduces the party-list traversal and id-merge at toy scale.
5. **`pakartotiniai_silutes_2015`** (#52, ~160) — wiring over #4's listing logic
   (one district instead of two).
6. **`savivaldybiu_2015`** (#49, ~15k) — the big one, last, once every parser has
   been proven on five small elections: municipal_sitemap config module, results
   join, full cross-checks.

Election ids follow the date-scope convention: `2015-kovo-1-seimo-zirmunai`,
`2015-birzelio-7-seimo-varena-eisiskes`, `2015-lapkricio-8-telsiu-mero`,
`2015-birzelio-7-pakartotiniai-sirvintos-trakai`, `2015-birzelio-21-pakartotiniai-silutes`,
`2015-kovo-1-savivaldybiu`. Each module: `sitemap.py`, `candidate_samples.py`,
`anketa_parser.py` + five dispatch points in `scraper/cli.py`, tests, and doc
updates (`CLI_REFERENCE.md`, `FIXTURE_SAMPLES.md`, `OUTPUT_SCHEMA.md`), per
`docs/ADDING_AN_ELECTION.md`.

Where the era parsers live: start them inside `seimo_zirmunu_2015` and have later
modules import from it (the existing pattern — modules import other modules'
parsers); extract to `scraper/shared/` only what genuinely crosses the
Seimo/municipal split, the way `municipal_sitemap.py` was extracted when a second
user appeared.

## 6. Scrape volume

Requests ≈ candidates × (5 tabs + photo + campaign page) + listings:

- #48/#50/#53: trivial (≤100 requests each).
- #51/#52: a few hundred each.
- #49: ~15k candidates → **~100k polite requests**, on the order of
  `savivaldybiu_2019`. Run with `KEEP_SAMPLES=1` (the docs' explicit guidance for
  large elections) so parser fixes are offline re-parses, not re-scrapes. The five
  small elections are cheap enough to keep samples too.

## 7. Open questions (resolve during implementation, none block starting)

1. Seimo by-election results source for elected flags (§4) — needed for #48/#50
   only; can land as a follow-up.
2. Whether `municipal_sitemap.py` needs generalizing for the 60-municipality index
   shape (§3) — check before starting #49.
3. Litas amounts: confirm the output schema stores declaration amounts as raw
   strings (existing behavior) so `Lt` needs no conversion; if anything normalizes
   currency, 2015 must keep the unit.
4. Program PDFs (mayoral candidates): record URL only, or fetch as sidecar?
   Recommend URL-only in the first pass.
5. `docs/goal.md` scope says "starting with 2016" — these six issues deliberately
   extend it; update `goal.md` (or note the extension in `DATASET.md`) when the
   first 2015 module lands.

## 8. Issue bookkeeping

Each module's landing closes its issue with a pointer to the module and fixture
counts. None of the six warrant `wontfix`: every one has structured, per-candidate
pages that survive intact.
