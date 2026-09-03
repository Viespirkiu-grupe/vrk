# Person Dashboard

A local browser over the scraped corpus, joining every election a person has
stood in: searchable people list, per-election answers, and a comparison table
showing how selected fields (position, assets, income…) changed across their
elections.

The interface is in Lithuanian, like the data. Counts go through
`Intl.PluralRules("lt")` rather than an `n === 1` split, because Lithuanian
takes three forms on a rule that does not follow English's — 1 asmuo,
2 asmenys, 11 asmenų, 21 asmuo — and numbers and the litas rate are formatted
`lt-LT`, so the decimal separator is a comma (3,4528 Lt/€).

## Run it

```bash
python scripts/build_person_index.py   # writes dashboard/people.json (~28 MB)
python3 scripts/serve_dashboard.py     # serve the repo root, gzipped
```

Then open <http://127.0.0.1:8791/dashboard/>. Both commands run from the repo
root — the index builder reads `data/`, and the page fetches candidate JSONs
and `docs/concept-map.json` relative to the server root. `serve_dashboard.py`
is the stdlib server plus gzip: the index compresses 4.2× (29 MB → 7 MB) and
the page fetches it `no-store` on every load, so plain `python3 -m
http.server 8791` works but pays the full weight each time. A person page is
deep-linkable via the URL hash, which is the person's `pid` (below); a
pre-pid `name|birth` hash and a merged-away fragment's key still resolve and
are rewritten to the pid.

## Identity: how candidacies become persons

VRK publishes no cross-election person identifier — the `rkndId` in candidate
URLs is a per-election registration id — so identity is resolved by
**normalized name + birth key**. Measured over the 113,073-record corpus:

- birth date is present on all but 234 records; 170 of those (the 1996-1998
  Seimas archive, which publishes no birth date) carry a birth *year* and
  group by name + `~year`, and the 64 left group by name alone,
- the pair collides for **zero** same-election record pairs,
- **1,989 names** are shared by people with distinct birth keys — real
  namesakes that name-only grouping would have merged wrongly,
- the join yields **60,725 persons**, 23,163 of them in more than one
  election.

Names are NFC-normalized, uppercased and whitespace-collapsed; diacritics are
preserved in the identity key (ŠIMONYTĖ ≠ SIMONYTE) and folded only in the
search box.

**The pid** (issue #96). Every person carries `"pid"` — `p` + 12 hex digits
of blake2s over the natural `name|birth` key — which is what the page writes
into the URL hash. It survives a rebuild and a new election: for a merged
person it derives from the fragment holding the chronologically earliest
candidacy, and elections are only added at the recent end now that the
historical sweep is done. The old `name|birth` deep links keep resolving —
the page accepts a pid, a natural key, or a merged-away fragment's key (from
`"ak"`) and rewrites the hash to the pid.

**Surname changes are healed by hand, not by rule.** The natural key splits
anyone who changed surname between elections — marriage, mostly — into two
persons. `scripts/find_identity_merge_candidates.py` finds the plausible
splits: within each birth key it pairs persons sharing a first name and
scores each pair `strong` (a surname token or the maiden→married stem links
them), `given-name` (only a shared middle given name — the scorer's known
false-positive shape) or `weak`, marks the pairs where one name is the other
plus appended tokens, and prints whatever is still undecided. Decisions live
in `scraper/person_overrides.json` — checked in, one entry per reviewed pair
with the evidence written down: `merge` folds the fragments into one person
(the former keys land in `"ak"`, so old links and maiden-name searches still
work), `distinct` records that the pair is genuinely two people. The
2026-08-30 review worked through all 99 strong pairs of the corpus plus the
token-order, transliteration and no-birth-date splits: 102 merges, 1 pair
left distinct for lack of evidence. Merging another pair is a one-line edit
of the override file, not a code change; the builder fails if an override
key stops matching, so the file cannot rot silently.

## What the page offers

The left pane is search plus facets, all answered from `people.json` alone:
free text over names, canonical party names and each candidacy's
workplace/position string; selects for election, nominating party/committee,
municipality, office and outcome. The election select lists terms, newest
first: a general election is one row, or a group holding itself and its
seat-fills, and picking the general — `2016 Seimas (visa kadencija)` —
includes the 2017–2019 by-elections of that same Seimas, which an exact-id
match used to drop silently; a by-election stays pickable on its own from
its group (issue #122). The nominator select does the same for lineage: a
party that grew out of a committee, or a union of parties, is a group whose
`… ir pirmtakai` row matches all of them (issue #123). Filters conjoin at the candidacy level — a
person matches when at least one of their candidacies passes every active
filter — and **⬇ CSV** exports the current selection (semicolon-separated,
BOM-prefixed for lt-LT Excel, uncapped even when the list shows only the
first 300 rows). Checking rows collects persons for **Palyginti**, a
side-by-side table whose columns are persons and whose cells show each
person's newest resolving answer tagged with its election. **📊 Rinkimų
suvestinė** aggregates one election — party mix, education mix, money
medians — with the denominator printed beside every figure, because the
higher-education share alone swings up to 28.9 points on that choice.
**📈 Didžiausi pokyčiai** ranks first-to-last declared money deltas.

## The comparison table

The per-person comparison rows (`CONCEPT_ROWS` in the page) name **concepts
from `docs/concept-map.json`**, which the page fetches at boot; labels come
from the map's `label-lt` and the paths from its per-election tables, so the
page carries no dotted path of its own and cannot drift from the data the
way its old hand-maintained `FIELD_MAP` did (issue #87 found two era-split
rows permanently empty for half the corpus each). The JS resolver mirrors
`field_coverage.concept_value` — same root-section fallback, list-mapping
and mid-path fan-out rules — and `tests/test_dashboard_concept_rows.py`
holds the two together on fixtures while `scripts/field_coverage.py` gates
the map itself against the full corpus. A cell whose concept the election
never mapped renders dimmed with a "form never asked" tooltip, distinct from
an answer the form invited and did not get. Rows that are one question split
across page eras chain concepts (`einamos-pareigos` falls back to
`pagrindine-darboviete`), and `biografija.darbo-patirtis` — 17,666 records
that were displayed nowhere — is a row of its own. Extending the comparison
is adding a concept id to `CONCEPT_ROWS`; if the concept is new, map it in
`docs/concept-map.json` and re-run `field_coverage.py --update-baseline`.

**Won flag.** `"w"` is tri-state: `true`, `false`, or absent where VRK
published no results — the five 2000-kovo-19 municipalities whose results
tree VRK does not publish, 806 candidacies in all (the 1997 municipal pair
was the larger gap until issue #92 joined its elected pages). It is `kandidatura(record, kind)["isrinktas"]`
(`scraper/shared/kandidatura.py`), the one resolver over the corpus's five
`kandidatavimas` shapes; the prose-note pathway lives in the parsers
(`candidacy_from_elected_note`, issue #100), which emit the root block this
reads — measured 2026-08-30, all 3,522 `Išrink…`-noted records agree with
it. The page renders the three states apart: `laimėta: N` counts only
`true`, `be rezultatų duomenų: M` appears beside it, a no-results card says
so, and the outcome facet offers all three. The index used to emit `"w"`
only when won, which made "lost" and "no results data" the same absence.

**Party.** Each candidacy carries `"p"`, the canonical nominator id from
`scraper/parties.json` (issue #82) — the join that holds one party together
across its dash glyphs, genitives and renames — and `people.json`'s top-level
`"parties"` table maps each used id to `{n: short or full name, t: kind, f:
full name where n is short}` (`partija`/`koalicija`/`komitetas`/
`issikelimas`) so the page can label it without carrying the registry. The
key is absent on the five presidential elections whose pages name no
nominator. The raw string stays in the record file;
`scraper/shared/parties.py::partija(record)` returns both. On screen the
party shows on the list rows (latest candidacy), on each election card, as
the person header's nominator trajectory (`LLS → LiCS → …`), as a facet, and
in the search haystack; the comparison's *Iškėlė / sąrašas* row shows the
per-election raw string, which is where coalition compositions differ.

The parties table also carries `pr`, the registry's `predecessors` (issue
#123): the organisations an entry continues — the merged parties behind
TS-LKD, the committee and the 2011 independents' coalition behind the
Vieningas Kaunas party. The party facet turns each lineage root into a group:
its first row, `<name> ir pirmtakai`, matches the whole lineage, and the rows
below it — the root and everything it continues, indented by depth — match
one nominator each with the counts the flat list used to show. A group sorts
by its lineage's total, so Vieningas Kaunas sits where its 148 candidacies
put it rather than where its 44 as a party would. An organisation inside a
lineage is listed in its group only, never twice; a predecessor the index
lacks (a subset build) is skipped. The stats view, the CSV and the person
header keep the exact ids.

**The other per-candidacy fields** (issue #87): `"sv"` indexes the top-level
`municipalities` list (~127 names interned rather than repeated 99,594
times), `"r": "m"` marks a mayoral run on a council-and-mayor ballot (the
election's `kind` decides every other office), `"wp"` is the
workplace/position string the search box matches (resolved through the
concept map's `einamos-pareigos`/`pagrindine-darboviete`, whichever the era
asks), and `"ed"` is the education rank in
`scraper/shared/education.py`'s 13-tier ordinal — the top-level
`educationLevels` list carries the ladder with Lithuanian labels, because
the slugs are ASCII-folded and would de-slug without their diacritics. All
of it comes from the shared resolvers, not rules of the builder's own:
`kandidatura()` for office/municipality/elected, `issilavinimas()` for the
rank, `field_coverage.concept_value()` for the workplace.

**Photos.** The corpus stores portraits as externalized sidecars
(`photos/<candidateId>.<ext>`, 27,493 records — the 2,199 the pages embedded
and, since issue #118, the 25,294 they linked), keeps VRK's own hosted URL
only where the fetch failed (38 records, all on hosts that no longer serve
them), and has nothing for the other 85,542. The page accepts both of those
plus a legacy inline `data:` URI, prefers the **newest** election's
portrait, loads lazily, and drops the `<img>` on error rather than showing a
broken icon — which is what happens to the 38.

**Currency.** The 2012–2015 pages declare assets and income in litas
(`turto-ir-pajamu-deklaracijos.valiuta` is `"Lt"` on those records); 2016 on
is euro. The index builder (`money_of`) and both of the page's renderers --
`moneyEUR` for the chart, `moneyCell` for the comparison table -- convert
litas at the irrevocable changeover rate, 3.4528 Lt/€, so one person's series
is comparable across 2015→2016. The records themselves keep the litas figures
as published, and `people.json` still carries `"lt": true` on a converted
candidacy for anything downstream that wants it.

The page shows no conversion marker. Every figure it displays is in euro, so
labelling the pre-2015 ones "(Lt→€)" on each column and explaining the rate in
three separate footnotes was noise rather than information.

The comparison table did not always convert. It read the stored number
straight through `compactValue`, so a litas figure printed raw, unlabelled,
and 3.4528× too large beside the euro columns next to it — the same field
disagreeing between two tabs of the same person, across the 36,362 of 76,776
records that declare in litas. `CONCEPT_ROWS` entries may carry an optional
`(value, record) => string` formatter; the asset rows use `moneyCell` and the
income row `incomeCell`, which converts the same way after resolving the
`deklaruotos-pajamos` concept (below).

## Assets & income across two different forms

The chart's first three series are the keys every election from 2007 on
declares under. The fourth, **Turtas ir piniginės lėšos (metų pabaigoje)**,
exists because the 1996–1997 form does not split turtas from piniginės lėšos —
it publishes one summed figure — so those elections leave the first two null
and would chart no assets at all, despite the page stating them. It is a
different measure rather than a fallback, so it is its own series and its own
comparison row.

The comparison table carries three further archive-only rows: the start-of-year
and acquired-during-year totals, and **Gautos pajamos (darbo santykiai)**. That
last one matters — on `1997-kovo-23-savivaldybiu-tarybu` the declaration's own
total row is usually unusable (see `docs/OUTPUT_SCHEMA.md`), so the employment
row is the only income figure most of those records have.

**Income resolves through a concept, not a key.** The archive form prints rows
1 (employment income) and 20 (the total) of its income section, and row 20
fails by rendering 0 against a non-zero row 1; the parser refuses such a total,
so `gautos-pajamos` is null on 4,628 records that do publish row 1. Reading the
key alone charted them as having declared nothing. Both the chart and the
comparison table now read `deklaruotos-pajamos`
(`scraper/shared/deklaracijos.py`, mirrored as `declaredIncome()` in the page),
which returns the figure and says whether it is a declared total or the
employment row; the table appends "(darbo santykiai)", the chart's number
table marks the cell with a `*` and a footnote, and `people.json` carries
`"ds": true` on such a candidacy so Biggest movers can label it too.

`MONEY_SERIES` in the page and `MONEY_FIELDS` in
`scripts/build_person_index.py` are **order-dependent on each other**:
`people.json`'s `"m"` array follows `MONEY_FIELDS`, and the Biggest movers
picker indexes into it by position.

## Election names and terms

`scraper/elections.json` is the **one** registry of elections: id, first-round
date, kind, official Lithuanian name, a short label for chart axes, and for a
by-election, repeat or re-vote the general election whose term it fills. The
index builder reads it, orders the corpus by its dates, and copies the entries
into `people.json`, so `dashboard/index.html` holds no election list of its
own.

Adding an election means adding one entry there. If a scraped
`data/<id>/` has no entry, the builder names it in its output and exits
non-zero, and `tests/test_elections_registry.py` fails — the id would
otherwise reach the UI as a raw slug.

This replaced three hand-maintained lists (`ELECTION_ORDER` here plus
`ELECTION_LABELS`/`SHORT_LABELS` in the page). Keeping them in step was
manual, so they drifted: the 2011 municipal general — 16,400 records — was in
none of them and invisible to the dashboard, and six further elections
rendered as raw slugs. See GitHub issue #63.

Same-day elections keep the order the registry file lists them in; the sort is
stable on the date alone, because 2015-06-07 ran a Seimas by-election and two
repeat municipal votes and there is no other order between them.

Each field follows one convention (issue #121 for the two display fields —
the entries had accreted module by module, so the dropdown mixed `1996
Seimas`, `2002 prezidento`, `1997-12 Aukštaitija` and `2003 Seimas (nauji)` —
and issue #122 for `parent`):

- **`shortName`** — `YYYY <Institucija>` for a general election, `YYYY-MM
  <Institucija>` for a by-election, repeat or re-vote, the institution one
  capitalised nominative per kind: Seimas, Savivaldybės, Prezidentas, EP,
  Merai. The month is the signal that a label is not the general — `2019
  Seimas` cannot be the September 2019 seat-fills — and the day joins only
  where two non-general labels would otherwise collide (the two June 2015
  municipal repeats, `2015-06-07 Savivaldybės` and `2015-06-21 Savivaldybės`).
  Labels stay within the 24 characters a chart axis can show.
- **`name`** — VRK's own heading form: the registry date in words (`2019 m.
  kovo 3 d.`), then `nauji` or `pakartotiniai` when the election is not a
  general one, then one body phrase per kind (`Lietuvos Respublikos Seimo
  rinkimai`, `savivaldybių tarybų rinkimai`, `Respublikos Prezidento
  rinkimai`, `Europos Parlamento rinkimai`, the named municipality's council
  or mayor), and for a Seimas by-election its constituencies (`Žirmūnų
  apygardoje Nr. 4`; `Žirmūnų Nr. 4, Gargždų Nr. 31 ir Žiemgalos Nr. 46
  apygardose`).
- **`parent`** — on a by-election, repeat or re-vote, the id of the general
  election whose term it fills; absent from a general election, and that
  absence is what makes it one (28 of the 55 entries carry it). The rule is
  mechanical: the latest earlier general of the same family, `mero` folding
  into `savivaldybiu` — grouping is by term, not kind, so the 2015 Telšiai
  mayoral by-election belongs to `2015 Savivaldybės`, and the 2013
  Biržai–Zarasai–Ukmergė event, repeat and new in one, has the one parent
  `2012 Seimas`. The page's two election pickers fold each general's
  children under it, `candidacyMatches` accepts a candidacy whose election
  *or parent* is the selection, and the Rinkimų suvestinė names the
  seat-fills its figures cover. `people.json` copies the field with the rest
  of the entry; `vrk.sqlite`'s `elections` table carries it as a column, so
  `COALESCE(parent, id)` is the term key there.

Ids are frozen: they name `data/<id>/`, the sitemaps, the modules' constants,
the release assets and every export's join key, so the four slug shapes the
old ones carry stay. Only an election added from now on follows one pattern —
see [ADDING_AN_ELECTION.md](ADDING_AN_ELECTION.md). `tests/test_elections_registry.py`
pins every rule, so a new entry either follows them or fails there.

## Files

- `scraper/elections.json` — the election registry (version controlled).
- `scraper/person_overrides.json` — the hand-reviewed identity decisions
  (version controlled): every accepted merge and rejected pair, with the
  evidence.
- `docs/concept-map.json` — the concept → per-election-path bridge the
  comparison rows resolve through; `scripts/field_coverage.py` gates it
  against the corpus.
- `scripts/build_person_index.py` — builds `dashboard/people.json`
  (gitignored); applies the override merges, assigns pids, prints the audit
  counts on every run.
- `scripts/serve_dashboard.py` — the stdlib server plus gzip and an
  mtime-keyed compression cache; run from the repo root.
- `scripts/find_identity_merge_candidates.py` — scores possible
  surname-change splits and prints the undecided ones; writes
  `dashboard/merge-review.csv` (gitignored — the record of decisions is the
  override file, this is derived output).
- `dashboard/index.html` — the whole app: no dependencies, vanilla JS, served
  statically next to `data/`.
- `tests/test_person_index.py` — pins the grouping rules, the pid and the
  override merges on synthetic records.
- `tests/test_identity_merge_review.py` — pins the review scorer's tiers on
  the real shapes from the issue #96 review.
- `tests/test_elections_registry.py` — pins the registry's shape, its
  chronology, the naming conventions, the term grouping (`parent`), and
  that every scraped election has an entry.
- `tests/test_dashboard_money_rendering.py` — pins that both renderers
  convert litas and that `parseMoney`/`parse_money_text` follow one shared
  string rule over one fixture list; lifts the helpers out of the page and
  runs them under node, skipping the behavioural half where node is absent.
- `tests/test_dashboard_ui.py` — pins the page's Lithuanian chrome, the
  sidebar's `nowrap`, the plural rule across the 11/21 boundaries, the
  tri-state outcome rendering, keyboard reachability, boot failure
  reporting, the term-grouped election pickers and their match rule, and
  the archive-era concept rows end to end.
- `tests/test_dashboard_concept_rows.py` — closes issue #87's test gap: the
  rows name real, corpus-measured concepts; the page's resolver agrees with
  `field_coverage.concept_value` on the shapes a naive walker gets wrong;
  the era-fallback chain bridges both eras; and no dotted path can creep
  back into the row list.
