# Adding an Election Module

Every election gets its own module because VRK's page layouts differ by year and
election type. This is the route from a VRK listing URL to a scraped election,
distilled from the modules that exist.

## 1. Identify the election

Fetch the wrapper page and read its title — it gives the official name and date:

```bash
curl -sS -L "<listing URL>" | grep -oE "[^<>]{0,140}(20[0-9]{2} m\.)[^<>]{0,140}"
```

Election ids follow the date and scope, e.g. `2023-spalio-8-kupiskio-mero`,
`2021-spalio-10-meru`, `2017-balandzio-23-seimo-anyksciai-panevezys`. Package
names mirror them: `kupiskio_mero_2023`, `meru_2021`, `seimo_anyksciu_panevezio_2017`.

## 2. Find which existing module the pages match

This is the whole job. Fetch one candidate page and run existing parsers against
it before writing anything. The layout families are:

- **2004 static site** (`ep_2004`): VRK's original LRS-ITD page template
  (`rinkimai/2004/euro/`), between the 1996-1998 Teleport archive and the
  2015-era layout — a profile card over one `r1`/`r2` table row per
  question in `N. Prompt: <b>answer</b>` form, separate `kand_biog_l_` and
  `kand_pajam_l_` pages instead of tabs, no interest declaration and no
  campaign page. Its sitemap is the 2014 EP walk with other link patterns
  and its fetcher the 2015-era one with its own link extractor; the page
  readers are the module's own. The October 2004 Seimas general
  (`seimo_2004`) is the second member: `ep_2004`'s readers with the Seimas
  question mapping, a card that states both candidacies and the campaign
  registration, and its own two-structure listing walk (lists and
  constituencies, as 2008/2012, on the 2004 template); the November 2005
  Kėdainiai by-election (`seimo_kedainiu_2005`) is thin wiring over it.
  The June 2004 presidential election (`prezidento_2004`) is the third
  member, with a different publication shape: one shared listing of five
  profile cards instead of per-candidate pages, the biography and
  programme as Word 97 `.doc` documents (read by
  `scraper/shared/word_doc.py`, fetched as bytes with `fetch_bytes`),
  the declaration page the only per-candidate HTML (`ep_2004`'s readers
  parse it unchanged), birth facts recovered from the biography prose
  under the 1990s family's keys, and a two-round results walk of its own
  joined by VRK's registration record id.
- **2000 archive** (`seimo_2000`): the 1996-1998 Teleport archive's
  template (`statiniai/puslapiai/n/rinkimai/20001008/`, the
  `kandvl.htm-<ID>.htm` candidate page) carrying the 2004 static site's
  content in one document — card with the candidacies and a winner note,
  the Q8/Q9 declarations, the questionnaire fields as labelled
  paragraphs, the 1990s declaration form inline with decimal litas, the
  autobiography. Its listing is the 2004 Seimas two-structure walk
  (`seimo_2004.sitemap.merge_listing_records` is shared; the page readers
  and the coalition-kind resolution are the module's own) and its
  declaration parser the 1990s one. The 1996-1998 archive family
  (`scraper/shared/seimo_archive_1990s.py`, next bullet) is the same
  template without the questionnaire. The March 2000 municipal general
  (`savivaldybiu_2000`) is the same document for the municipal form on
  the 1997 municipal archive's three-hop listing (municipality → list →
  candidate, plus a by-party roll-up that names coalition members), with
  a results tree that five municipalities were captured without.
- **2016 era** (`seimo_2016`): one anketa table with the whole Q5–Q21 set,
  elected note inside the name cell, base64 photos, GPM308 income labels,
  `ID001x` private-interest sections.
- **2017 mayoral** (`meru_2017`): the 2016 anketa narrowed to the savivaldybių
  tarybų rinkimų įstatymas — five declarations instead of nine — with free-text
  biography and base64 photos. The March 2019 municipal general election
  (`savivaldybiu_2019`) is this family, not the 2023 one: despite being a
  municipal general election like `savivaldybiu_2023`, its pages are four years
  older and reuse these parsers. Only the income aliases had to be restated,
  because the GPM308 rows were reworded between 2017 and 2019.
- **2019 EP era** (`ep_2019`): anketa split across sibling tables with standalone
  record tables between them, question numbers sometimes lacking the trailing dot.
- **2020 era** (`seimo_2020`): Q6.x contacts, Q7.x position and membership.
- **2023 mayoral** (`kupiskio_mero_2023`): tab bodies wrapped in their own
  `<div>`, biography numbering with nationality as Q2. The March 2023 municipal
  general election (`savivaldybiu_2023`) is the same family and reuses these
  parsers unchanged — 13,796 candidates and not one page-level difference. So
  is the May 2023 repeat Visaginas mayoral vote (`visagino_mero_2023`), whose
  only difference is page-set, not page-level: no campaign tab (the repeat
  runoff's campaign finance is published with the March election).
- **2024 era** (`ep_2024`, `seimo_2024`, `prezidento_2024`): tab bodies are
  siblings of the tab navigation, Q8 membership table, Rinkimų kodekso
  declarations.

Import the matching module's parsers rather than restating them. Several modules
are thin wiring over another era's parsers — `marijampoles_mero_2017` over
`meru_2017`, `radviliskio_mero_2021` over `meru_2021`.

## 3. Build the module

Three files, mirroring the closest existing election:

- `sitemap.py` — listing URL, `ELECTION_ID`, candidate-row selection. Watch for
  listings whose candidate table has no id, or whose first cell links somewhere
  other than the candidate.
- `candidate_samples.py` — `EXPECTED_TABS` for this election. Tab slugs vary
  (`privaciu-interesu-deklaracija` vs `...deklaracijos`), and the campaign tab is
  absent for some elections and some candidates. A tab the pages link but
  VRK never published (probe every candidate's URL — the 2009 presidential
  trustees tab is a 404 for all seven) goes in the 2015-era fetcher's
  `unpublished_tabs` (`prezidento_2009` names it in `UNPUBLISHED_TABS`):
  recorded in `index.json`, neither fetched nor reported missing.
- `anketa_parser.py` — the question-to-key mapping, reusing shared helpers.

Then wire five dispatch points in `scraper/cli.py`.

### If the election has more than one listing structure

The municipal general elections are the case that exists: VRK publishes the
mayoral candidates on one page and the council candidates one page below an
index of party lists, and neither set contains the other — in 2023, 406 people
are in both and 27 mayoral candidates are in neither list; in 2019, 379 and 31.

This is **shared machinery, not per-module code**: it lives in
`scraper/shared/municipal_sitemap.py`, extracted there when `savivaldybiu_2019`
was added. `savivaldybiu_2023` and `savivaldybiu_2019` are both thin config
plus wrappers — election id, listing URLs, paths, and the regex that marks a
dual candidacy on the listing (2019 says `į savivaldybės tarybos narius -
merus`, 2023 says `į savivaldybės merus`, and neither pattern matches the other
election's rows). Each wrapper resolves its module constants at call time, so a
test can monkeypatch the marker and see the effect. A third such election
should add a config module, not a third copy. What the shared code handles:

- `fetch_listing_sample` fetches every sub-page too, skips ones already saved so
  an interrupted capture resumes, and paces itself so a one-off capture does not
  hammer VRK. `build_sitemap_from_sample` reads them back from disk.
- The structures merge on VRK's own candidate id, and one sitemap entry carries
  both candidacies. Do not merge on name.
- Cross-check the merged total against whatever summary page VRK publishes
  (`savKandidataiSuvestine.html` here) before trusting anything downstream. Row
  counts, per-structure counts and the overlap should all reconcile.
- Facts that exist only on the listings — municipality, list, seat order, elected
  flags — have to be carried through to the record. Both modules put them in a
  `kandidatavimas` top-level block.
- At this scale name-slug ids collide (244 of 13,796 in 2023), so the id needs a
  stable suffix. The positional `-2`/`-3` of the other modules makes an id depend
  on traversal order, and the batch runner uses the output filename as its resume
  marker.
- An expected tab may depend on the candidate's role rather than the election —
  in both elections only mayoral candidates publish a campaign tab, so
  `EXPECTED_TABS` is computed per entry. Getting that wrong is 13,363 spurious
  warnings in 2023 and 13,256 in 2019.

What is *not* shared is the candidate page: the two elections belong to
different page eras, so `savivaldybiu_2019` reuses `meru_2017`'s parsers while
`savivaldybiu_2023` reuses `kupiskio_mero_2023`'s. Matching the listing
structure says nothing about matching the pages.

The 2015-era municipal listings (a municipality index, a district page per
municipality, the lists hanging off it) have their own walker in
`pakartotiniai_sirvintu_traku_2015/sitemap.py`, which `savivaldybiu_2015`
drives with the 60 discovered district pages. Read the district-page rows
before reusing it: in 2015 a direct candidate link there is a mayoral
candidate, in 2011 (`savivaldybiu_2011`) it is a self-nominated individual
standing for the council alone, so that module keeps the walker's fetcher,
list reader and id builder and reads the district rows itself. VRK's
roll-up pages (`KandidataiMerai.html` in 2015; `KandidataiIssikele.html` and
the two coalition pages in 2011) are the cross-check either way — and in
2011 the self-nominated roll-up counts coalition members too, so reconcile
against the union, not the individuals alone. The 2007 tree
(`savivaldybiu_2007`) is the same walk under older file names — the
walker's district-id pattern accepts both — with VRK's by-party pages as
the roll-up: a party's page links its list in every municipality it stood
in, and links an empty shell where it stood in a coalition, which is how
the coalitions' members are known at all.

## 4. Verify against the whole field before trusting it

```bash
python -m scraper fetch-sample <id> && python -m scraper sitemap <id>
python -m scraper fetch-candidate-samples <id> --allow-new-samples --candidate-id ...
python -m scraper parse-anketa-samples <id>
```

Read the output for every fixture candidate, not just one. Anything null or
empty is a question to answer, not a result to accept: trace it back to the
page and confirm the source is genuinely blank. That habit is what surfaced
every defect listed in `docs/DATASET.md`.

### If the pages mark no winner

The 2009–2015 static layout carries no elected marker of any kind. For those
elections electedness is a separate join: a `results.py` in the module
configures which VRK results tree to walk (`scraper/shared/election_results.py`
has walkers for the Seimas elected-members page, constituency pages with
rounds, the EP members page, the presidential final-results page and the
municipal results/ranking pages), `python -m scraper build-results <id>`
writes `sitemaps/<id>.results.json`, and the era parser joins it into
`kandidatavimas.isrinktas`. Read the builder's reconciliation stats before
shipping: every winner must resolve to a VRK candidate id that is in the
sitemap, and seat counts must match what VRK declares — or the difference
must be a named annulment, not a guess.

## 5. Tests and docs

- `tests/test_<module>_anketa_parser.py` — pin the key lists, the elected-note
  forms, record tables, and anything election-specific. Mutating the parser
  should make them fail; check that it does.
- `tests/test_<module>_sample_allowlist.py` — the fixture set.
- `docs/CLI_REFERENCE.md`, `docs/FIXTURE_SAMPLES.md`, `docs/OUTPUT_SCHEMA.md`.
- **`scraper/elections.json`** — add the election: id, first-round date,
  official Lithuanian name, short label for chart axes. This is what names it
  in the dashboard and places it in the cross-election chronology. Skipping it
  fails `tests/test_elections_registry.py` and makes
  `scripts/build_person_index.py` exit non-zero, because the id would
  otherwise reach the UI as a raw slug — which is how the 2011 municipal
  general stayed invisible (issue #63).

## 6. Full scrape

```bash
scripts/run_election_batches.sh <election-id>
```

By default the runner deletes each candidate's fetched HTML after parsing it,
so a later parser fix costs a full re-scrape. `KEEP_SAMPLES=1` retains the
HTML under `samples-full/<election-id>/` instead, making every future fix an
offline re-parse (`parse-anketa-samples` with `--samples-root` pointed there).
The price is disk on the order of the election itself — pay it for the large
elections, where a re-scrape costs hours of polite traffic to vrk.lt.
