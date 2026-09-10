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
python3 scripts/serve_dashboard.py     # serve dashboard/, data/, docs/, gzipped
```

Then open <http://127.0.0.1:8791/dashboard/>. Both commands run from the repo
root — the index builder reads `data/`, and the page fetches candidate JSONs
and `docs/concept-map.json` relative to the server root. `serve_dashboard.py`
is the stdlib server plus gzip: the index compresses 4.1× (29 MB → 7 MB) and
the page fetches it `no-store` on every load, so plain `python3 -m
http.server 8791` works but pays the full weight each time.

It serves those **three directories and nothing else** (issue #160). It used
to hand out the whole repository root with listings — `/` indexed `.git`,
`.run-state/`, `samples-full/` and `.venv/`, and `/.git/config`,
`/conftest.py` and `/scraper/person_overrides.json` all answered 200 — and it
checked no `Host`, so a page open in the same browser could read every byte
under the root as same-origin after a DNS rebind. A foreign `Host` is
refused, a path outside the three is refused, a directory gets no listing,
and every response carries `nosniff`, a narrow CSP and `no-referrer`. It also
answers `/dashboard` with a 301 rather than serving the page under a base URL
one level too high — which is what made the page report a wrong working
directory when only the trailing slash was missing — sends `ETag` and
`Last-Modified` so a reload gets a 304 instead of 7 MB, and evicts one cache
entry instead of clearing all 512.

A person page is
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
- the pair collides for **zero** same-election record pairs — nobody stands
  twice on one ballot, which makes a shared election the discriminator the
  identity review reaches for when the names and dates agree,
- **1,849 names** are shared by people with distinct birth keys — real
  namesakes that name-only grouping would have merged wrongly. It read 1,989
  until issue #141: 140 of those "namesakes" were one person, split by a
  short key rather than by a different one, with 154 candidacies on the wrong
  side (`VYTAUTAS LANDSBERGIS|?` beside `|1932-10-18`). 157 merges and 23
  `distinct` decisions are in `scraper/person_overrides.json`, each with its
  evidence,
- the join yields **60,568 persons**, 23,204 of them in more than one
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

**A split person is healed by hand, not by rule.**
`scripts/find_identity_merge_candidates.py` finds the plausible splits in
four passes, and the key splits a person three ways:

- **a changed surname** — marriage, mostly. Within each birth key, persons
  sharing a first name are paired and scored `strong` (a surname token or the
  maiden→married stem links them), `given-name` (only a shared middle given
  name — the scorer's known false-positive shape) or `weak`, with the pairs
  where one name is the other plus appended tokens marked;
- **a key shorter than a birth date** (issue #141) — the 1996-1999 Seimas
  archive publishes none, so a person who stood then and later has a
  `NAME|?` or `NAME|~YYYY` entry beside their real one. 147 such pairs sat in
  the index, holding 154 candidacies, and this review could not form one of
  them: it bucketed on the exact birth string, so a `~YYYY` bucket could
  never contain a full-date person and a dateless one was skipped outright.
  It printed `1,370 pairs, 0 strong, 0 undecided`, which reads as a reviewed
  corpus;
- **two spellings of one given name** on one birth date and surname
  (issue #141) — VIKTOR/VIKTORAS USPASKICH, EDUARD/EDVARD TRUSEVIČ. 64 pairs
  the first-name bucketing could not form either.

Two discriminators settle a pair the other way, and both are hard: a pair
whose halves stand in **one election** is two people, because nobody is on a
ballot twice (this is what separates VIKTOR/VIKTORAS from 21 same-birthday
sibling pairs); and a half whose birth date makes them **a minor** at an
election the other half contested is somebody else (`VYTAUTAS ASTRAUSKAS`,
born 1982 and 14 at the 1996 Seimas election). The run also prints how many
fragment keys it could pair with *nothing*, so "0 undecided" stops reading as
"clean".

Decisions live in `scraper/person_overrides.json` — checked in, one entry per
reviewed pair with the evidence written down: `merge` folds the fragments into
one person (the former keys land in `"ak"`, so old links and maiden-name
searches still work), `distinct` records that the pair is genuinely two
people. The file now holds **259 merges and 24 `distinct`** decisions — the
2026-08-30 review's 102 merges plus issue #141's 157, whose evidence is a
shared birthplace token, education entry or workplace on 120 of them and an
absence of any contradiction on the rest. Merging another pair is a one-line
edit of the override file, not a code change; the builder fails if any
override key stops matching — `distinct` included, which it used to skip.

## What the page offers

The left pane is search plus facets, all answered from `people.json` alone:
free text over names, canonical party names and each candidacy's
workplace/position string; selects for election, nominating party/committee,
municipality, single-mandate constituency, office, outcome and declared
nationality (issue #162: the 45 census groups `scraper/shared/tautybe.py`
folds 117 spellings into). The election select lists terms, newest
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
first 300 rows; see *What the page renders, and what it exports* below for
what a cell looks like). Checking rows collects persons for **Palyginti**, a
side-by-side table whose columns are persons and whose cells show each
person's newest resolving answer tagged with its election. **📊 Rinkimų
suvestinė** aggregates one election — party mix, votes, campaign finance,
declared nationality, education mix, money medians — with the denominator
printed beside every figure, because the higher-education share alone swings
up to 28.9 points on that choice. **🏛 Iškėlėjai** is the same summary with
the grouping key swapped: one nominator across every election it fielded
candidates in. **▦ Aprėptis** is the concept × election grid of what each
form asks. **📈 Didžiausi pokyčiai** ranks first-to-last declared money deltas.

**What issue #162 brought up from the records.** Three layers the corpus held
and no view read:

- **Campaign money.** €25.7 M of declared donations over 4,729 campaigns.
  `people.json` carries a top-level `campaigns` table — `k` the campaignKey,
  `d` the donations in euro, `n` the candidacies sharing it — and each
  candidacy's `ck` points into it, because a campaign is not a candidate: a
  party's campaign is one participant for its whole list, and summing its
  total per candidate reads €2.68 bn (issue #97). So every figure carries its
  count. The comparison row prints `276 968 € — visa kampanija, bendra 105
  kandidatavimams`; the election summary's *Kampanijų finansavimas* counts
  campaigns, not candidacies, and names a shared campaign by its nominators;
  the CSV adds `kampanijos_aukos_eur` beside `kampanijos_kandidatavimu`.
- **Concepts measured and never shown.** Comparison rows for *Tautybė*,
  *Visuomeninė veikla*, *Pomėgiai*, *Anksčiau išrinktas* (the offices, one
  line each, or the candidate's own "Nebuvo"), *Deklaracijos forma* and
  *Deklaracijos apimtis*, and a derived *Pareiškimai* row: the statutory
  declarations the election's form asks, listing only the answers that depart
  from each question's usual one (`eina nesuderinamas pareigas: Einu`), else
  `Įprasti atsakymai (N klausimų)`, else `Neklausta` — never a blank that
  reads as a denial. The usual answer is the concept map's
  `iprastas-atsakymas`, which `scraper/shared/pareiskimai.py` reads too;
  `tests/test_pareiskimai.py` holds the two readings together. The spouse's
  and children's names and the address are left out on purpose, and the
  concept map's description says so.
- **The aggregates' blind spots.** The party table's top-15 rule left 227 of
  312 nominators in no aggregate anywhere; *rodyti visus* now lists them all,
  and the nominator view gives each its own summary: per election its
  candidacies, their share of the election, the elected, the higher-education
  share, the median income and its campaigns' donations, then the people it
  fielded most.

**A view never states what it does not know** (issue #148). Three of them
did:

- The party-mix table folds everything past the top 15 nominators into a
  `kiti (N)` row whose *Išrinkta* cell was the empty string while its count
  and share were filled — and an empty cell in a column of numbers reads as
  a zero. 2019 municipal printed `išrinkta 1 505` above a column summing to
  1 184, with **321 winners hidden in the blank**; 17 of the 55 terms hid at
  least one, 1,101 elected candidacies in all. The cell is filled, and the
  column now sums to the summary line.
- The comparison view discarded failed record loads
  (`records.filter(([, r]) => !r._error)`) and rendered its 16 concept rows
  as em dashes over them, with the two index-derived rows above still looking
  authoritative — so a reader concluded those people had answered nothing.
  Both it and the person view now show one banner, which says that the empty
  cells below it are not answers. Neither the missing trailing slash nor a
  data-less checkout is hypothetical; both produce exactly that page. The
  asset pane's empty state used to say "nothing was declared in any of this
  person's elections", a claim about the data, where the truth was that
  nothing had loaded.
- **Rinkimų suvestinė** copied one facet across — the election — and then
  walked every person, and **Didžiausi pokyčiai** read none at all: with an
  election, a nominator and *tik išrinkti* chosen, the list said one number
  and the summary reported the whole election, with the three selects still
  showing the filters and nothing saying two had been dropped. Both apply
  every facet now, name them above the figures, and offer *rodyti visus* to
  clear them.

## What the page renders, and what it exports

Everything here was measured over the whole corpus and re-measured against
the running page (issue #149).

**The export is for a Lithuanian spreadsheet.** The separator and the BOM
always were; the numbers were not. Money went through `String(number)`, and
`build_person_index` rounds with a dot: 199,626 of the export's 308,135 money
cells carried a `.` decimal, which an lt-LT import reads as *text* — no sum,
no sort, no chart. `csvMoney` writes the comma the locale expects, and since
the separator is `;` the comma needs no quoting. Ninety cells — 88
`darbovietė` strings and two negative figures — began with one of
`= + - @ TAB CR`, which Excel evaluates and renders as `#NAME?`; `csvField`
prefixes those with an apostrophe. And the election column, the one a reader
groups by, held only the slug while the nominator had carried an id/name pair
since issue #82: `rinkimu_pavadinimas` now sits beside `rinkimai` with the
registry name.

**No bar rises above the top gridline.** The asset chart scaled its bars to
the tallest value and drew its gridlines while `t <= max`, so the top label
was `floor(max/tick)*tick` and the tallest bar stood above it — 59,177 of the
60,379 charts with a value (98.01 %), median ratio 0.824, worst 0.667: a
316,000 € bar over an axis labelled to 240,000 €. `axisMax = ceil(max/tick) *
tick` drives the bars, the gridlines and the loop, and costs nothing but a
little headroom.

**A chart is sized to the pane it is drawn into.** It used to be
`cols.length * 132 + 100` px wide whatever it had to fit in: a 20-candidacy
person got 2,740 px in an 830 px wrapper, 4.9 screenfuls opening on 1996,
with nothing to say more lay off-screen. Columns narrow to fit, down to 52 px
— which still holds three bars and a rotated year — and only past that does
the wrapper scroll, opening on the most recent election. 99.03 % of the
60,568 people have eight candidacies or fewer and their chart fits whole on a
1280 px window; the 590 who do not scroll 306 px instead of 1,910. Every
`.tablewrap` on the page now carries the scrolling-shadows pair, so a wrapper
with more to show says so and one that fits shows nothing.

**A phone gets the record, not a letterbox.** Measured at 375×812 before the
fix: the header took 158.5 px, the result list 361.75 px and the person pane
291.75 px — 35.9 % of the screen for the thing the page is for — and
`body { overflow: hidden }` meant there was no scrolling to reclaim it (the
page has never overflowed *horizontally*, which is worth saying). Under
900 px the document scrolls, the person pane grows with its content (3,035 px
for the same person, in a 3,683 px document), the result list keeps a bounded
scroll of its own, the field list stacks label over value, and the six filter
selects fold behind a **Filtrai** button. `#filters[hidden] { display: none }`
has to be said because the `display: grid` rule above it beats the UA sheet —
which is also why the filters come back by themselves on a wide screen,
whatever the button was last left at.

**A label is VRK's word, or the key's own word spelled properly.**
`labelFor` resolves a record key against the record sections, the concept
map's `label-lt`, the map's path segments, then `dashboard/field-labels.json`,
then `deslug` — which lower-cases an ASCII-folded slug and cannot put a
diacritic back. Of the 442 keys that reach a label over the whole corpus, 398
fell through to `deslug`, 125 of them provably mis-spelled (`Pavarde`,
`Darboviete`, `Numeris sarase`, `Seimos nariu skaicius` — the last also
reading as *Seimas members*) and 47 printed in English: `Row number`, on
4,020,284 cells. The labels file holds 253 of those keys and **every entry
says where its label comes from**, which is what
`tests/test_dashboard_field_labels.py` gates:

- `printed` (118) — the string VRK prints, such that
  `scraper.shared.files.slugify(label) == key`. Slugifying the printed label
  is *how the parser made the key*, so the proof needs no corpus and no
  wording is ours. The one normalization is a capital first letter.
- `header` (21) — the column heading VRK prints above the value, for the
  campaign-finance tables whose columns the parsers named in English
  (`donor` → `Aukotojas`, `amountEur` → `Aukos suma, Eur`). Quoted from the
  archived pages under `samples/`, which the test reads back.
- `restored` (94) — the key's own words with their diacritics, case and
  punctuation restored, so folding the label reproduces what `deslug` makes
  of the key, word for word. No entry can quietly reword a field.
- `structural` (20) — a key the parsers invented that no VRK page labels
  (`records`, `label`, `listKind`). No external proof exists, so the test
  holds these to an enumerated list: adding one is a deliberate act.

The 189 keys that still de-slug were read one by one — `adresas`, `data`,
`forma`, `metai`, `pareigos`, `turas`, `koalicijosPartija` and the rest carry
no diacritic, so de-slugging them is right and an entry for one would be dead
weight, which the test refuses. A new election that adds keys of its own
moves the pinned count, and that is the signal to look at its labels. The
file is fetched at boot beside the concept map and is *not* fatal: without it
the page de-slugs, as it did before the file existed, and says so in the
console.

**A bare URL is a link.** 17 keys hold one, and 802 of 1,329 sampled records
printed at least one as an 88-character string — while `appendSourceLinks`
had rendered the `nuorodos` shape as anchors all along. `renderValue`'s
scalar branch emits an anchor with `rel="noopener noreferrer"` for a string
matching `/^https?:\/\/\S+$/`.

## Keyboard, screen reader and the Back button

Also measured live, and also re-measured after (issue #147).

**A row is a link and a checkbox, not a button wrapping one.** Each result
row used to be a `role="button"` div containing the comparison checkbox —
which makes the checkbox *presentational* to ARIA (no role, no name, no
checked state) while the row's own keydown handler preventDefaulted Space and
opened the person instead. Space arrived at a focused checkbox with
`defaultPrevented: true` and the box stayed unticked, so **Palyginti was
mouse-only**. The name is an `<a href="#pid">` now, Enter opens the person,
Space is left to the checkbox — which says whom it would compare — and the
arrow keys still walk the list.

**The pane takes focus, and says what is on it.** The first focusable element
inside `#person` was the **614th** tab stop, after 300 rows and their 300
checkboxes, and `showPerson` moved no focus and announced nothing: the page
had **zero** `aria-live` nodes, **zero** `<label>` elements, and no
`aria-label` on the search box — the six facets carried only a `title`. Now
`#person` is `tabindex="-1"` and focused on every render (its top aligned to
the viewport, because plain `focus()` scrolls the nearest edge into view and
on a phone landed 1,095 px *below* the person's name), a visually hidden
`role="status"` region names the person and any records that failed, and the
search box and all six facets carry real labels.

**One way in: the URL.** `grep hashchange|popstate|pushState` matched
nothing. The hash was read once at boot, `showPerson` assigned it and three
views assigned `""`, so Back moved history while the pane kept the previous
person and the shared URL no longer matched the screen. `routeFromHash` is
now the single entry point — boot, a click on a row's link, and `hashchange`
all go through it — `showPerson` only *canonicalises* a legacy `name|birth`
or merged-away key to the pid, with `replaceState` so it adds no entry, and
the three header views drop the person from the URL the same way. A hash
naming nobody says so instead of leaving the last person on screen. Driven
live: two clicks, then Back brings the first person and their hash back, Back
again lands on the placeholder, Forward returns the person, and a legacy
`INGRIDA ŠIMONYTĖ|1974-11-15` link resolves and rewrites itself to
`#p0a1d6eb067f0`.

**A slow render cannot land on a later one.** `fetchRecord` memoises by file,
so an uncached 20-election person followed by a cached one could end with the
first rendered under the second's URL and row highlight. Every view takes a
`renderToken` and checks it after each await; the three synchronous views
bump it, which ends whatever was in flight. Driven live: the second person
stays, under their own hash and announcement.

**The facets are readable and typing is cheap.** `#filters` is a two-column
grid in a 360 px pane, which left 139 px of usable text: 299 of the 338
nominator options (88.5 %, the widest 7.1× over) and 50 of the 63
municipality ones were wider than their box, and only 25 options carried a
`title`. Those two facets take the whole grid row — 163 → 333 px, which
leaves 123 of 338 and 0 of 63 over — and `addOption` gives every option its
label as a tooltip. And `renderList`, bound straight to the `input` event,
rebuilt 300 rows over a scan costing 14.0 ms per keystroke; a 120 ms debounce
turns a burst into one render (measured: typing `KAZLAUSKAS` renders once,
not ten times), while the facet `change` handlers stay immediate because a
select fires once.

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
`municipalities` list — the 62 official names of `scraper/municipalities.json`
(issue #137; the eras' 127 wordings used to be 127 facet rows, every
municipality twice, each row hiding half its history), interned rather than
repeated 99,594 times — `"r"` names the offices of a council-and-mayor ballot
(`"m"` a mayoral run alone, `"tm"` council and mayor on one ballot, absent a
council run; the election's `kind` decides every other office), and a `"tm"`
candidacy carries `"wt"` and `"wm"`, the council seat's and the mayoralty's
own outcomes, beside `"w"` — issue #140: 448 people in 2019/2023 won a
council seat and lost the mayoralty, and one code with one flag showed them as
elected mayors, absent from the *Tarybos narys* facet. The page's `rolesOf` /
`electedAs` read both, so *Meras* + *tik išrinkti* is a year's 60 mayors, the
CSV's `pareigos` lists both offices and `isrinktas_kaip` the one won, and a
dual candidacy's election card says which. `"wp"` is the
workplace/position string the search box matches (resolved through the
concept map's `einamos-pareigos`/`pagrindine-darboviete`, whichever the era
asks), and `"ed"` is the education rank in
`scraper/shared/education.py`'s 13-tier ordinal — the top-level
`educationLevels` list carries the ladder with Lithuanian labels, because
the slugs are ASCII-folded and would de-slug without their diacritics. All
of it comes from the shared resolvers, not rules of the builder's own:
`kandidatura()` for office/municipality/elected, `issilavinimas()` for the
rank, `field_coverage.concept_value()` for the workplace.

**Votes and the constituency** (issue #133). Each candidacy carries `"v"`,
the preference votes on the list (57,809 candidacies; the 1996 rating
system's positive votes count as such), `"cv"`, the votes of the
single-winner race's last round contested (a Seimas constituency, or the
country for a presidential candidate), and `"ap"`, an index into the
top-level `constituencies` list — the district's one name across the four
label eras (`scraper/shared/apygardos.py`; 315 raw labels, 136 names; a name,
not a boundary — Kėdainių in 2000 and in 2020 are one row). The page offers
the constituency as a facet and a CSV column (`apygarda`), prints the
showing on each election card ("4 321 pirmumo balsų · 6 999 balsų
apygardoje"), exports `pirmumo_balsai` and `balsai_apygardoje`, adds three
comparison rows (*Pirmumo balsai*, *Balsai apygardoje* — every round, read
off the record the way `kandidatura()` reads it — and *Sąrašo balsai*), and
gives **Rinkimų suvestinė** a *Balsai* section: coverage, total and median,
and the ten candidacies with the most preference votes or race votes. An
election whose records carry no votes says so in that section rather than
showing an empty table: VRK publishes its results on pages the corpus does
not read.

**Campaigns, nationality and coverage** (issue #162). `"ck"` indexes the
top-level `campaigns` list (`{k, d, n}`: the campaignKey, the donations in
euro where the campaign publishes them, the candidacies sharing it; 4,729
rows over 20,199 candidacies), `"tb"` the `nationalities` list (the 45
groups, largest first; an unclaimed spelling fails the build, like an
unregistered municipality wording), and the top-level `coverage` block holds
the concept × election matrix the **▦ Aprėptis** grid draws: `concepts` in
the concept map's order, `records` per election, and per election the filled
count of each concept, `null` where the form never asks. All three come from
the shared resolvers — `scraper/shared/kampanija.py`,
`scraper/shared/tautybe.py`, `field_coverage.resolve_any` — and the index
build takes 35 s.

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
disagreeing between two tabs of the same person, across the 79,098 of 112,218
records with a declaration block that declare in litas (issue #150: the
figures here were 36,362 of 76,776, which corresponded to nothing measured). `CONCEPT_ROWS` entries may carry an optional
`(value, record, candidacy) => string` formatter — `candidacy` is the
`people.json` entry, which the campaign and declaration rows read (issue
#162); the asset rows use `moneyCell` and the income row `incomeCell`, which
converts the same way after resolving the `deklaruotos-pajamos` concept
(below).

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
- `scripts/serve_dashboard.py` — the stdlib server plus gzip, an LRU
  compression cache keyed on mtime, and the guards of issue #160 (three
  served directories, a loopback-only `Host`, no listings, conditional
  requests); run from the repo root. `tests/test_serve_dashboard.py` drives
  a real server on an ephemeral port.
- `scripts/find_identity_merge_candidates.py` — scores possible
  surname-change splits and prints the undecided ones; writes
  `dashboard/merge-review.csv` (gitignored — the record of decisions is the
  override file, this is derived output).
- `dashboard/index.html` — the whole app: no dependencies, vanilla JS, served
  statically next to `data/`.
- `dashboard/field-labels.json` — the Lithuanian label for each record key
  `deslug` spells wrong (version controlled), one entry per key with the
  proof of its label: `printed`, `header`, `restored` or `structural`. The
  page fetches it at boot and works without it.
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
  reporting, the term-grouped election pickers and their match rule, the
  archive-era concept rows end to end, issue #149's presentation and
  export pass (the CSV's comma decimals and formula guard, the chart axis and
  its width cap, the scroll affordance, the narrow-screen layout and the bare
  URL anchors) and issue #147's keyboard, screen-reader and routing pass (the
  row's link and checkbox, the focus move and the live region, the hash
  router, the render token, the facet widths and the search debounce).
- `tests/test_dashboard_field_labels.py` — holds `field-labels.json` to the
  four proofs its entries claim, and every key in it to still occurring in
  the corpus.
- `tests/test_pareiskimai.py` — pins the declarations rule (the answer-word
  classes, the per-question usual answer, "not asked" apart from "nothing to
  declare") and runs the page's `declarationsCell` against the Python reading
  under node (issue #162).
- `tests/test_tautybe.py` — every one of the corpus's 117 nationality
  spellings folds to a group, on a clone and against `data/` alike.
- `tests/test_dashboard_concept_rows.py` — closes issue #87's test gap: the
  rows name real, corpus-measured concepts; the page's resolver agrees with
  `field_coverage.concept_value` on the shapes a naive walker gets wrong;
  the era-fallback chain bridges both eras; and no dotted path can creep
  back into the row list.
