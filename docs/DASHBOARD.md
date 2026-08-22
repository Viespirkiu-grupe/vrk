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
python scripts/build_person_index.py   # writes dashboard/people.json (~4 MB)
python3 -m http.server 8791            # serve the repo root
```

Then open <http://127.0.0.1:8791/dashboard/>. Both commands run from the repo
root — the index builder reads `data/`, and the page fetches candidate JSONs
relative to the server root. A person page is deep-linkable via the URL hash.

## Identity: how candidacies become persons

VRK publishes no cross-election person identifier — the `rkndId` in candidate
URLs is a per-election registration id — so identity is resolved by
**normalized name + birth date**. Measured over the 33,119-record corpus:

- birth date is present on **33,118 records (100.0%)**; the one exception
  (`jonas-korsakas`, 2020 Seimas) groups by name alone,
- the pair collides for **zero** same-election record pairs,
- **305 names** are shared by people with distinct birth dates — real
  namesakes that name-only grouping would have merged wrongly,
- the join yields **23,358 persons**, 7,253 of them in more than one election.

Names are NFC-normalized, uppercased and whitespace-collapsed; diacritics are
preserved in the identity key (ŠIMONYTĖ ≠ SIMONYTE) and folded only in the
search box. Known limitation: a person who changes their surname between
elections (marriage) appears as two persons; same-birth-date same-first-name
pairs would be the starting point for a merge review if that ever matters.

## The comparison table

`dashboard/index.html` carries a curated field map (concept → normalized paths
tried in order), built from a measured key×election matrix. The asset and
income fields (`privalomas-registruoti-turtas`, `pinigines-lesos`,
`gautos-pajamos`) are already aligned across all 20 elections by the module
convention of reusing key names where questions match; biography-era splits
(`anketa.*` up to 2019, `biografija.*` from 2020) are bridged per concept in
the map. Extending the comparison is editing `FIELD_MAP` in the page.

**Won flag.** A candidacy is marked won (`"w": true`) when the record's
`profilis.pastaba` starts with `Išrink` or — for the 2012–2015 family, whose
pages mark no winner — when `kandidatavimas.isrinktas` is `true`, the flag
joined in from VRK's results trees (`python -m scraper build-results <id>`).

**Currency.** The 2012–2015 pages declare assets and income in litas
(`turto-ir-pajamu-deklaracijos.valiuta` is `"Lt"` on those records); 2016 on
is euro. The index builder (`money_of`) and both of the page's renderers --
`moneyEUR` for the chart, `moneyCell` for the comparison table -- convert
litas at the irrevocable changeover rate, 3.4528 Lt/€, so one person's series
is comparable across 2015→2016. A converted candidacy is flagged: `"lt": true`
in `people.json`, "(Lt→€)" on the chart's column label and in the
Biggest-movers table, and "Lt→€" under the election name in the comparison
table's header. The records themselves keep the litas figures as published.

The comparison table did not always convert. It read the stored number
straight through `compactValue`, so a litas figure printed raw, unlabelled,
and 3.4528× too large beside the euro columns next to it — the same field
disagreeing between two tabs of the same person, across the 36,362 of 76,776
records that declare in litas. `FIELD_MAP` rows may now carry an optional
`(value, record) => string` formatter, and the three money rows use
`moneyCell`.

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

`MONEY_SERIES` in the page and `MONEY_FIELDS` in
`scripts/build_person_index.py` are **order-dependent on each other**:
`people.json`'s `"m"` array follows `MONEY_FIELDS`, and the Biggest movers
picker indexes into it by position.

## Election names

`scraper/elections.json` is the **one** registry of elections: id, first-round
date, official Lithuanian name, and a short label for chart axes. The index
builder reads it, orders the corpus by its dates, and copies the entries into
`people.json`, so `dashboard/index.html` holds no election list of its own.

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

## Files

- `scraper/elections.json` — the election registry (version controlled).
- `scripts/build_person_index.py` — builds `dashboard/people.json`
  (gitignored); prints the audit counts on every run.
- `dashboard/index.html` — the whole app: no dependencies, vanilla JS, served
  statically next to `data/`.
- `tests/test_person_index.py` — pins the grouping rules on synthetic records.
- `tests/test_elections_registry.py` — pins the registry's shape, its
  chronology, and that every scraped election has an entry.
- `tests/test_dashboard_money_rendering.py` — pins that both renderers
  convert litas; lifts the helpers out of the page and runs them under node,
  skipping the behavioural half where node is absent.
- `tests/test_dashboard_ui.py` — pins the page's Lithuanian chrome, the
  sidebar's `nowrap`, and the plural rule across the 11/21 boundaries.
