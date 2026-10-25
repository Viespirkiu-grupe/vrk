# Person Dashboard

A browser over the corpus that joins every election a person has stood in: a
searchable people list, per-election answers, and a comparison table of how
selected fields changed across their elections.

The interface is in Lithuanian. Counts use `Intl.PluralRules("lt")` (1 asmuo,
2 asmenys, 11 asmenų, 21 asmuo), and numbers are formatted `lt-LT`, with a
decimal comma (3,4528 Lt/€).

## Run it

Prerequisites: Python 3.11+ and Node.js 22.12+. `frontend/` is an independent
npm project: a static Astro site with local fonts and bundled scripts. Its
build needs no corpus, and its output `frontend/dist/` is separate from the
root `dist/`, which holds data releases.

From the repository root:

```bash
python scripts/build_person_index.py   # requires data/; writes dashboard/people-{list,details,version}.json
python scripts/build_web_portraits.py  # requires data/ + the index; writes portraits/, flags the index
cd frontend
npm ci
npm run build
npm run preview
```

Open <http://127.0.0.1:8791/>. `npm run preview` runs
`scripts/serve_dashboard.py`, the server production runs
([DEPLOY.md](DEPLOY.md)); `python3 scripts/serve_dashboard.py 8792` picks
another port. After a corpus change, rebuild the index, then the portraits.

For development, `cd frontend && npm run dev` starts Astro at
<http://127.0.0.1:4321/> and a data server on port 8793 (`VRK_DATA_PORT`).
Astro proxies the index, labels, concept map, records and portraits to it.
The dev server answers only `/`, so a reload on a view path is a 404; use
`npm run preview` to try direct links. Ctrl-C stops both.

To verify the frontend:

```bash
cd frontend
npm run check
npm run build
npx playwright install chromium        # once per machine
npm test
```

Browser tests run the built site against synthetic records, so they work on a
clean clone. `pytest` separately runs the domain and formatting regressions
against the client modules.

A missing corpus or index shows as a loading error, not an empty result. Get
the corpus from the release (see the README), then build the index.

## The server

`scripts/serve_dashboard.py` serves:

- the Astro build at `/`, and `frontend/dist/index.html` for each view path;
- the index and `field-labels.json` from `dashboard/`;
- `data/`, `portraits/` and, of `docs/`, only `concept-map.json`.

Everything else resolves inside the build, so no repository path is
reachable and there are no directory listings. It listens on 127.0.0.1:8791
and accepts loopback `Host` names only; `--bind`, `--allow-host` (or
`VRK_BIND`, `VRK_PORT`, `VRK_ALLOW_HOSTS`) open it to a public name. Every
response carries `nosniff`, a narrow CSP and `no-referrer`.

### URL layout

| Path | View |
|---|---|
| `/` | front page (Kandidatai) |
| `/asmuo/<slug>-<pid>` | a person, e.g. `/asmuo/birute-vesaite-p7d185515b624` |
| `/palyginti/<pid>,<pid>,…` | comparison of the selected people |
| `/suvestine` | Rinkimų suvestinė |
| `/iskelejai` | Iškėlėjai |
| `/apreptis` | Anketų aprėptis |
| `/pokyciai` | Didžiausi (deklaracijų) pokyčiai |
| `/partiju-keitimai` | Partijų keitimai |

- `frontend/src/lib/routes.js` holds the slugs. A person resolves by pid
  alone; the name slug is decoration.
- A wrong or missing slug, a bare pid, an old `/#<pid>` hash, a `name|birth`
  key or a merged-away key is rewritten to the canonical path with
  `replaceState`. Clicks use `pushState`, so Back and Forward work.
- A path naming nobody shows „Nuoroda … nieko neatitinka.“
- Filters and the search box are not in the URL.

| URL | File |
|---|---|
| `/`, `/_astro/*`, `/branding/*`, `/fonts/*` | `frontend/dist/` |
| `/people-version.json`, `/people-list.json`, `/people-details.json`, `/field-labels.json` | `dashboard/` |
| `/data/<election>/<file>.json` | `data/` |
| `/portraits/<pid>.webp?v=<version>` | `portraits/` |
| `/docs/concept-map.json` | `docs/concept-map.json` |

The page fetches these by absolute URL. Only the view paths fall back to
`index.html`; a mistyped asset or data URL stays a 404. The server's
`ROUTE_PATHS`/`ROUTE_PREFIXES` must equal the page's list
(`tests/test_dashboard_ui.py` checks), so a new view is added in both.

### Caching

| URL | `Cache-Control` |
|---|---|
| `/_astro/*` | `public, max-age=31536000, immutable` (content-hashed names) |
| `/portraits/<pid>.webp?v=<version>` | `public, max-age=31536000, immutable` (`v` is the portrait set's hash) |
| `/people-list.json?v=<hash>`, `/people-details.json?v=<hash>` | immutable **only while `<hash>` is the content hash of the file on disk**, else `no-cache` |
| everything else | `no-cache` |

- `no-cache` keeps the copy but revalidates it; the page's fetches say the
  same. An unchanged file costs a 304.
- The server answers `If-Modified-Since` alone with 304 (Cloudflare drops
  the `ETag` when it recompresses), and lets `If-None-Match` decide when both
  are sent.
- Only 200 and 304 carry `Cache-Control`; a 404 is never immutable. Every
  compressible response carries `Vary: Accept-Encoding`.
- `build_person_index.py` writes `.br` (quality 11, needs `brotli`) and
  `.gz` (level 9) beside the list and details files. The server sends the
  best one the client accepts, if it is not older than the file; anything
  else is gzipped on the fly into an mtime-keyed LRU.

`tests/test_serve_dashboard.py` holds all of this. The Cloudflare rule is in
[DEPLOY.md](DEPLOY.md).

## The index files

Three files in `dashboard/`, written by `scripts/person_index_files.py`
(sizes from the 2026-10-24 index):

| File | Holds | Raw | brotli |
|---|---|---|---|
| `people-version.json` | `build`, and `list` / `details`, the content hash of each (blake2s, 16 hex digits) | 79 B | |
| `people-list.json` | every top-level table but `campaigns`, plus `partyIds`; per person `pid`, `n`, `b`, `ph`, `ak`, `kn`; per candidacy `ei`, `pi`, `w`, `sv`, `ap`, `tb`, `wm`, `wt`, `r` | 9.4 MB | 1.3 MB |
| `people-details.json` | `campaigns`; per person, per candidacy `{wp, m, c, lt, ed, v, cv, ck, ds}` | 14.8 MB | 2.8 MB |

- `ei` indexes `elections`; `pi` indexes `partyIds`, the sorted keys of
  `parties`.
- The natural key `k` is not sent: the page rebuilds it as
  `n.toUpperCase() + "|" + (b || "")`, and `kn` carries it where that would
  be wrong.
- `people-details.json`'s `people[i][j]` belongs to the list's
  `people[i].e[j]`; the page merges them.
- Both files carry the same `build`. A page holding files from two builds
  re-reads the version file and reloads once.

The page draws the list, facets and name/party search from the list file;
views that need the details (person, comparison, statistics, nominators,
movers, CSV) show „kraunama…“ until it lands. Python reads the joined index
with `person_index_files.load_index()`; `join_index(split_index(x)) == x`
byte for byte.

## Identity: how candidacies become persons

VRK publishes no cross-election person id, so a person is **normalized name +
birth key**:

- Names are NFC-normalized, uppercased and whitespace-collapsed. Diacritics
  stay in the key (ŠIMONYTĖ ≠ SIMONYTE) and are folded only in search.
- The birth key is the birth date; records with only a year (the 1996–1999
  Seimas archive) use `~year`, and records with neither use `?`.
- The pair never collides within one election, and 1,849 names are shared by
  distinct birth keys (real namesakes).
- The join yields 60,568 persons, 23,204 of them in more than one election.

**The pid.** `p` + 12 hex digits of blake2s over the natural key, derived for
a merged person from the fragment with the earliest candidacy. It survives
rebuilds. Old `name|birth` links and merged-away keys (in `ak`) still resolve.

**Splits are healed by hand.** `scripts/find_identity_merge_candidates.py`
lists plausible splits: a changed surname, a key shorter than a birth date
(`NAME|?`, `NAME|~YYYY`), and two spellings of a given name. Two facts rule a
pair out: both halves in one election (nobody is on a ballot twice), or one
half a minor at an election the other contested. Decisions go in
`scraper/person_overrides.json`, one entry per pair with its evidence:
`merge` folds the fragments (old keys land in `ak`), `distinct` records two
people. The builder fails if any override key stops matching.

## What the page offers

- **Search and facets**, answered from the list file: free text over names,
  party names and workplace; selects for election, nominator, municipality,
  constituency, office, outcome and declared nationality. A person matches
  when one candidacy passes every active filter.
- **Election picker:** terms, newest first. Picking a general election
  (`2016 Seimas (visa kadencija)`) includes its by-elections; each
  by-election is also pickable alone.
- **Nominator picker:** a lineage is a group whose `… ir pirmtakai` row
  matches all of it; a party that ran in coalitions gets a
  `… su koalicijomis` row. Order (`partyOrder` in
  `frontend/src/lib/parties.js`): most distinct people elected, a lineage
  counting each person once, then people who ran, then name; nominators that
  elected nobody follow alphabetically, *Išsikėlė pats* last.
- **⬇ CSV** exports the whole selection: `;`-separated, BOM-prefixed, decimal
  commas, an apostrophe before a cell starting with `= + - @ TAB CR`, and
  `rinkimu_pavadinimas` beside `rinkimai`.
- **Palyginti** compares checked people side by side, each cell the newest
  answer tagged with its election.
- **📊 Rinkimų suvestinė** summarizes one election: party mix, votes,
  campaign finance, nationality, education, money medians, each figure with
  its denominator. **🏛 Iškėlėjai** is the same per nominator. **▦ Aprėptis**
  is the concept × election grid. **📈 Didžiausi pokyčiai** ranks
  first-to-last declared money changes.
- Every view applies every active facet and names them above its figures.
- Lists and cards show the newest elections first; charts stay chronological.

Display rules:

- A failed record load shows a banner saying the empty cells are not answers.
- A cell whose concept the election never asked is dimmed („form never
  asked“), apart from an unanswered question.
- Charts scale to `ceil(max/tick) * tick` and fit their pane down to 52 px a
  column, then scroll, opening on the latest election.
- Under 900 px the document scrolls and the filters fold behind **Filtrai**.
- Bare URLs render as links (`rel="noopener noreferrer"`).
- Result rows are a link plus a checkbox; Space ticks the box, Enter opens
  the person. The person pane takes focus on render and a `role="status"`
  region announces it. Search is debounced 120 ms.
- Each render carries a `renderToken`, so a slow load cannot draw over a
  later view.

**Labels.** `labelFor` tries the record sections, the concept map's
`label-lt`, the map's path segments, `dashboard/field-labels.json`, then
`deslug`. Each entry in the labels file states its proof, which
`tests/test_dashboard_field_labels.py` checks:

- `printed` — VRK's string, with `slugify(label) == key`;
- `header` — the column heading VRK prints above the value;
- `restored` — the key's own words with diacritics restored;
- `structural` — a key the parsers invented, from an enumerated list.

A key whose de-slugged form is already right needs no entry. The file is not
fatal: without it the page de-slugs.

## The comparison table

`CONCEPT_ROWS` in the page names concepts from `docs/concept-map.json`, which
supplies the labels and per-election paths. The JS resolver mirrors
`field_coverage.concept_value`; `tests/test_dashboard_concept_rows.py` holds
the two together. Rows split across page eras chain concepts
(`einamos-pareigos` falls back to `pagrindine-darboviete`). To add a row, add
a concept id to `CONCEPT_ROWS`; for a new concept, map it in the concept map
and run `field_coverage.py --update-baseline`. An entry may carry a
`(value, record, candidacy) => string` formatter.

The derived *Pareiškimai* row lists only the statutory declarations whose
answer departs from the usual one (the concept map's `iprastas-atsakymas`,
also read by `scraper/shared/pareiskimai.py`), else
`Įprasti atsakymai (N klausimų)`, else `Neklausta`. Spouse's and children's
names and the address are left out on purpose.

### Per-candidacy fields

| Field | Meaning |
|---|---|
| `w` | elected: `true`, `false`, or absent where VRK published no results (the five 2000-kovo-19 municipalities). From `kandidatura(record, kind)["isrinktas"]` |
| `r` | offices of a council-and-mayor ballot: `m` mayor alone, `tm` council and mayor; absent for a council run |
| `wt`, `wm` | on a `tm` candidacy, the council seat's and the mayoralty's own outcomes |
| `p` / `pi` | nominator id from `scraper/parties.json`; absent on presidential elections whose pages name none |
| `sv` | index into `municipalities` (62 official names); `municipalityCounties` parallel, `counties` the filter's order |
| `ap` | index into `constituencies` (one name across label eras; a name reused for a different place is one entry per era, e.g. *Dainavos (iki 2016)*); `constituencyCounties` and `constituencyGroups` parallel |
| `v` | preference votes on the list |
| `cv` | votes in the single-winner race's last contested round |
| `wp` | workplace/position, via `einamos-pareigos`/`pagrindine-darboviete` |
| `ed` | education rank on `scraper/shared/education.py`'s 13-tier ordinal; `educationLevels` holds the labels |
| `m` | money series, in `MONEY_FIELDS` order |
| `lt` | the declaration was in litas and has been converted |
| `ds` | the income figure is the employment row, not a declared total |
| `ck` | index into `campaigns` (`{k, d, n}`: campaignKey, donations in euro, candidacies sharing it) |
| `tb` | index into `nationalities` (45 groups; an unclaimed spelling fails the build) |
| `c` | record ids |

Everything comes from the shared resolvers: `kandidatura()`,
`issilavinimas()`, `field_coverage.concept_value()`,
`scraper/shared/kampanija.py`, `scraper/shared/tautybe.py`,
`scraper/shared/apygardos.py`. `scraper/constituency_counties.json` is built
from VRK's precinct lists by `scripts/build_constituency_counties.py`.

Top-level tables: `elections`, `parties` (`{n, t, f, pr, nr}`), `campaigns`,
`municipalities`, `constituencies`, `nationalities`, `educationLevels`,
`coverage` (the Aprėptis matrix: filled count per concept per election,
`null` where the form never asks) and `portraits` (`{v, n}`).

- **Outcome.** The page shows `laimėta: N` and `be rezultatų duomenų: M`
  apart, and the outcome facet offers all three states. *Meras* + *tik
  išrinkti* means mayors elected, not council seats.
- **Campaign money** is per campaign, not per candidate: a party's campaign
  covers its whole list. Every figure carries its count
  (`… — visa kampanija, bendra 105 kandidatavimams`), and the CSV adds
  `kampanijos_aukos_eur` beside `kampanijos_kandidatavimu`.
- **Votes** show inside the opened election card, not its header. An
  election without votes says so in the summary.

### Nominator labels

`n` comes from `scraper/shared/parties.py::display_name`:

1. the registry's `shortName`, if any;
2. for a coalition named only by its members, their labels joined with ` + `
   (`LLRA-KŠS + Rusų aljansas`);
3. for another coalition with a quoted brand, the first brand
   (`„Valdemaro Tomaševskio blokas“`);
4. else the name.

`f` is the full name whenever `n` differs, shown on hover. A coalition gets a
muted `koalicija` before its label unless the label says so; the CSV omits
it. `pr` lists predecessors (lineages), `nr` a coalition's member ids. The
comparison's *Iškėlė / sąrašas* row shows the raw per-election string.

## Photos

The page shows one **web portrait** per person, built by
`scripts/build_web_portraits.py` from the `data/*/photos/` sidecars:

- **Source:** the newest candidacy with a decodable sidecar.
- **Shape:** EXIF orientation applied, transparency on white, sRGB, cropped
  3:4 from the top, 192×256.
- **Encoding:** WebP q75, method 6, with no EXIF, XMP or ICC.
- **Output:** `portraits/<pid>.webp` (gitignored) and
  `portraits/manifest.json`, which makes re-runs incremental.

On the 2026-10-24 corpus: 19,402 portraits for 60,568 people, 75.3 MB, 3.8 KB
on average.

Both scripts stamp `ph: 1` on people with a portrait and the top-level
`portraits: {v, n}` (set hash and count). The page asks for
`/portraits/<pid>.webp?v=<version>` only when `ph` is set, and inserts the
image only once it decodes.

## Money

**Currency.** 1996–2015 declarations are in litas (`valiuta: "Lt"`); 2016 on
in euro. The index builder (`money_of`) and the page's `moneyEUR`,
`moneyCell` and `incomeCell` convert at 3.4528 Lt/€, so every figure shown is
euro, with no marker. The records keep the litas as published; the index
flags `lt` on a converted candidacy. That is 79,098 of 112,218 records with
a declaration block.

**Assets.** The first three chart series are the keys every election from
2007 declares. The fourth, **Turtas ir piniginės lėšos (metų pabaigoje)**, is
the 1996–1997 form's single summed figure: a different measure, so its own
series and row. The comparison table adds three archive-only rows: start of
year, acquired during the year, and **Gautos pajamos (darbo santykiai)**.

**Income** resolves through `deklaruotos-pajamos`
(`scraper/shared/deklaracijos.py`, mirrored as `declaredIncome()`), which
falls back to the employment row where the archive total is refused. The
table appends "(darbo santykiai)", the chart marks the cell `*`, and the index
sets `ds`.

`MONEY_SERIES` in the page and `MONEY_FIELDS` in
`scripts/build_person_index.py` must stay in the same order: `m` follows
`MONEY_FIELDS`, and the movers picker indexes it by position.

## Election names and terms

`scraper/elections.json` is the one election registry; the index copies its
entries, so the frontend holds no election list. A scraped `data/<id>/`
without an entry makes the builder exit non-zero and
`tests/test_elections_registry.py` fail. Same-day elections keep the file's
order.

- **`shortName`** — `YYYY <Institucija>` for a general election, `YYYY-MM
  <Institucija>` otherwise (Seimas, Savivaldybės, Prezidentas, EP, Merai); the
  day is added only to break a collision (`2015-06-07 Savivaldybės`). At most
  24 characters.
- **`name`** — VRK's heading form: the date in words (`2019 m. kovo 3 d.`),
  `nauji` or `pakartotiniai` when not a general, the body phrase, and for a
  Seimas by-election its constituencies.
- **`parent`** — on a by-election, repeat or re-vote, the general election
  whose term it fills: the latest earlier general of the same family, `mero`
  folding into `savivaldybiu`. Absent on a general. `vrk.sqlite` carries it,
  so `COALESCE(parent, id)` is the term key.

Ids are frozen. New ones follow
[ADDING_AN_ELECTION.md](ADDING_AN_ELECTION.md); the registry test pins every
rule.

## Files

- `scraper/elections.json` — the election registry.
- `scraper/person_overrides.json` — identity decisions with evidence.
- `docs/concept-map.json` — concepts → per-election paths;
  `scripts/field_coverage.py` gates it.
- `dashboard/field-labels.json` — label overrides with their proofs.
- `scripts/build_person_index.py` — builds the index and its `.br`/`.gz`
  copies (gitignored), applies overrides, assigns pids, prints audit counts.
- `scripts/build_web_portraits.py` — builds `portraits/` and stamps `ph`.
- `scripts/serve_dashboard.py` — the server.
- `scripts/find_identity_merge_candidates.py` — lists undecided splits;
  writes `dashboard/merge-review.csv` (gitignored).
- `frontend/src/pages/`, `layouts/`, `components/` — the Astro page and shell.
- `frontend/src/styles/` — tokens and responsive styles.
- `frontend/src/scripts/`, `lib/` — interactions and domain helpers.
- `frontend/tests/` — browser tests on synthetic data.

Tests: `test_person_index.py`, `test_person_index_files.py`,
`test_identity_merge_review.py`, `test_elections_registry.py`,
`test_serve_dashboard.py`, `test_web_portraits.py`,
`test_dashboard_ui.py`, `test_dashboard_money_rendering.py`,
`test_dashboard_field_labels.py`, `test_dashboard_concept_rows.py`,
`test_pareiskimai.py`, `test_tautybe.py`.
