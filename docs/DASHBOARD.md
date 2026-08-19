# Person Dashboard

A local browser over the scraped corpus, joining every election a person has
stood in: searchable people list, per-election answers, and a comparison table
showing how selected fields (position, assets, income…) changed across their
elections.

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

## Files

- `scripts/build_person_index.py` — builds `dashboard/people.json`
  (gitignored); prints the audit counts on every run.
- `dashboard/index.html` — the whole app: no dependencies, vanilla JS, served
  statically next to `data/`.
- `tests/test_person_index.py` — pins the grouping rules on synthetic records.
