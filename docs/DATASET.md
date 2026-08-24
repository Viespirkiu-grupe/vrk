# Dataset Inventory and Review

State of the scraped corpus after the full run of 2026-08-16 and the
re-scrape of the five largest non-municipal elections on 2026-08-18, and the
caveats worth knowing before analysing it.

Regenerate any part of it with:

```bash
scripts/run_all_elections.sh                 # every election, sequentially
scripts/run_election_batches.sh <election-id> # one election
```

Both are resumable: a candidate whose output JSON already exists is skipped, so
an interrupted run continues where it stopped. Candidate samples go to a
temporary directory, so the test-protected fixtures under `samples/html/` are
never touched by a full run.

## Inventory

113,002 candidate records across 51 elections, 1996–2025, with **zero fetch
failures** other than three 2011, three 2007, two 2000 and one 2002
candidate pages VRK never published (see Known gaps).

**The table below is an aggregate, not an inventory of any one directory.**
`data/` is gitignored, so it never travels with a branch or a merge, and the
corpus has in practice been scraped from several checkouts and worktrees at
different times. A given clone holds whatever was scraped *there*; the counts
here are the union. Before trusting a local `data/` for analysis, count it
(`ls data/*/ | wc -l` per election) rather than assuming this table describes
it, and re-run `scripts/run_election_batches.sh <id>` for anything missing.
Every election in the table has now been scraped in full; the last three
fixture-only rows (the 2015 municipal general and the two June 2015 repeat
elections) were completed on 2026-08-21.

Two named parse-time flags are worth distinguishing: the single
2015 candidacy whose questionnaire VRK never published (`AnketaNotPublished`,
see Known gaps), and nine `ResidenceMissing` warnings across the two new
1996-1998 archive general elections (one 1996 Seimo candidate, eight 1997
municipal candidates) — each verified by re-fetching the source page, where
the `Gyvenamoji vieta` label is absent entirely, so these are genuinely
unpublished fields rather than a parser fault. The two municipal general
elections from the modern eras are together larger than everything else in
the corpus by a factor of three; each was scraped separately in ~6h. The
1996-1998 archive family's two general elections (`1996-spalio-20-seimo`,
`1997-kovo-23-savivaldybiu-tarybu`) were scraped in full the same night they
were built — 879 and 6,276 candidates respectively, in under two hours
combined, since neither approaches the modern municipal generals' scale.
Every row now reflects the post-fix parse: the five largest non-municipal
corpora were re-scraped on 2026-08-18 (run record below) and every other
election was re-parsed offline the same day.

| election | records | elected | declared a conviction | with campaign data |
|---|---:|---:|---:|---:|
| `2015-kovo-1-seimo-zirmunai` | 12 | 1 | 0 | 12 |
| `2015-birzelio-7-seimo-varena-eisiskes` | 8 | 1 | 0 | 8 |
| `2015-lapkricio-8-telsiu-mero` | 7 | 1 | 0 | 7 |
| `2015-birzelio-7-pakartotiniai-sirvintos-trakai` | 327 | 26 | 2 | 285 |
| `2015-birzelio-21-pakartotiniai-silutes` | 366 | 25 | 12 | 182 |
| `2015-kovo-1-savivaldybiu` | 15149 | 1473 | 266 | 13855 |
| `2016-seimo` | 1415 | 141 | 38 | 672 |
| `2017-balandzio-23-meru` | 11 | 2 | 0 | 11 |
| `2017-balandzio-23-seimo-anyksciai-panevezys` | 11 | 1 | 0 | 11 |
| `2017-rugsejo-10-marijampoles-mero` | 8 | 1 | 0 | 8 |
| `2018-rugsejo-16-seimo-zanavykai` | 6 | 1 | 0 | 6 |
| `2019-ep` | 301 | 11 | 6 | 279 |
| `2019-prezidento` | 9 | 1 | 0 | 9 |
| `2019-rugsejo-8-seimo` | 27 | 3 | 2 | 27 |
| `2020-seimo` | 1754 | 141 | 41 | 758 |
| `2021-balandzio-11-radviliskio-mero` | 7 | 1 | 1 | 7 |
| `2021-spalio-10-meru` | 14 | 2 | 1 | 14 |
| `2023-rugsejo-3-seimo-raseiniai-kedainiai` | 8 | 1 | 1 | 8 |
| `2023-geguzes-7-visagino-mero` | 2 | 1 | 0 | 0 |
| `2023-spalio-8-kupiskio-mero` | 5 | 1 | 1 | 5 |
| `2024-ep` | 319 | 11 | 7 | 0 |
| `2024-prezidento` | 8 | 1 | 0 | 0 |
| `2024-seimo` | 1740 | 141 | 62 | 699 |
| `2025-kovo-16-meru` | 14 | 2 | 0 | 10 |
| `2023-kovo-5-savivaldybiu-tarybu-ir-meru` | 13796 | 1557 | 541 | 433 |
| `2019-kovo-3-savivaldybiu-tarybu` | 13666 | 1502 | 244 | 410 |
| `1996-spalio-20-seimo` | 879 | 0 | 0 | 0 |
| `1997-kovo-23-seimo-pakartotiniai` | 23 | 0 | 0 | 0 |
| `1997-gruodzio-21-seimo-pakartotiniai` | 4 | 0 | 0 | 0 |
| `1997-kovo-23-savivaldybiu-tarybu` | 6276 | 0 | 0 | 0 |
| `1997-birzelio-29-svenciniu-tarybos-pakartotiniai` | 110 | 0 | 0 | 0 |
| `2012-seimo` | 1927 | 139 | 45 | 1927 |
| `2013-kovo-3-seimo-birzai-zarasai-ukmerge` | 37 | 3 | 2 | 37 |
| `2014-prezidento` | 7 | 1 | 0 | 7 |
| `2014-ep` | 215 | 11 | 4 | 215 |
| `2007-spalio-7-seimo-dzukija` | 10 | 1 | 0 | 4 |
| `2008-seimo` | 1603 | 141 | 25 | 0 |
| `2009-prezidento` | 7 | 1 | 0 | 7 |
| `2009-ep` | 262 | 12 | 3 | 260 |
| `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai` | 17 | 2 | 0 | 17 |
| `2011-vasario-13-seimo-marijampole` | 9 | 1 | 0 | 9 |
| `2011-vasario-27-savivaldybiu` | 16400 | 1526 | 200 | 0 |
| `2007-vasario-25-savivaldybiu` | 13419 | 1550 | 78 | 0 |
| `2002-prezidento` | 17 | 1 | 0 | 0 |
| `2002-gruodzio-22-savivaldybiu-tarybu` | 10138 | 1560 | 27 | 0 |
| `2004-ep` | 241 | 14 | 3 | 0 |
| `2004-prezidento` | 5 | 1 | 0 | 0 |
| `2004-seimo` | 1251 | 141 | 8 | 0 |
| `2005-lapkricio-20-seimo-kedainiai` | 5 | 1 | 0 | 0 |
| `2000-seimo` | 1271 | 141 | 5 | 0 |
| `2000-kovo-19-savivaldybiu-tarybu` | 9879 | 1433 | 9 | 0 |
| **total** | **113002** | **11729** | **1634** | **20199** |

The elected column counts records whose `profilis.pastaba` starts with
`Išrink` — the note reads `Išrinktas`/`Išrinkta` (verb agreeing with the
candidate's gender) and is null for a candidate who won nothing, **except in
the presidential elections**, where every candidate carries a participation
note (`Dalyvavo I ture`, `Dalyvavo II ture`, or `Išrinktas II ture` for the
winner). Counting non-null `pastaba` there reports 9 and 8 "elected" for a
race one person won; match on the `Išrink` prefix, not on presence. The
2007–2015 pages mark no winner at all, so for those seventeen elections the column
counts `kandidatavimas.isrinktas == true` instead (and so does the 2000
row: its cards do carry a winner note, on 139 of the 141 — the other two
pages are VRK's pre-results capture — but the flag is the results join) — the flag joined in from
VRK's results trees (`python -m scraper build-results <id>`; the
reconciliation behind each file is in `docs/CLI_REFERENCE.md`'s results
section). The 48 annulled March 2015 council winners in Šilutė and Trakai
are not counted; the June repeat elections' rows carry those seats. The
2004 EP row counts 14 for 13 seats: Prunskienė, whose mandate VRK declared
terminated at her request eight days after the vote, and Didžiokas, whom
VRK recognised as elected in her place (see that election's record
below). Its conviction column counts Q9.2 (`Yra`, three candidates); a
fourth declared a grave conviction under Q9.3 alone. The 2004
presidential row's elected count is likewise the joined flag — the
runoff verdict names Adamkus alone — and its conviction column is 0 by
absence: that tree asked its five candidates no questionnaire at all.
The 2002 presidential row reads the same way (the protocol's verdict
names Paksas alone), and its conviction column is 0 by absence twice
over: the questionnaire exists only as a two-page scan of the paper
form, archived and linked but never OCR'd into data.

Records live under `data/<election-id>/` (~0.66 GB of JSON plus 362 MB of
photo sidecar files under `data/<election-id>/photos/` — 2,199 portraits from
the embedded-photo eras, externalized 2026-08-19 and verified byte-identical
to a pre-migration sha256 manifest, file for file) and are **not** version
controlled — `data/`, `sitemaps/` and `samples/` are gitignored, so the corpus is
reproduced by running the scrapers rather than by cloning.

### The 2026-08-18 re-scrape of the five largest non-municipal elections

`2016-seimo`, `2020-seimo`, `2024-seimo`, `2024-ep` and `2019-ep` were scraped
on 2026-08-16, before the parser fixes listed below landed, and the batch
runner discarded their raw HTML as it went — so the HTML-level fixes could
only reach them through a re-scrape. The sitemaps were rebuilt from fresh
listings first and came back identical to the old ones in candidate ids *and*
order for all five, so candidate identity was stable across the refresh. The
pre-fix corpus is archived at
`/Volumes/Disk 1/IT/scraping/vrk-archive/20260818-big-five-prefix/`.

The run took 1h22m for all five sequentially (1221s, 1542s, 1550s, 272s,
331s) — roughly half the 2026-08-16 durations, the shared keep-alive session
having replaced one TLS handshake per request — with zero fetch failures,
zero failed candidates and zero parse anomalies. It ran with
`KEEP_SAMPLES=1`, so the full raw HTML of all 5,529 candidates (1.9 GB under
`samples-full/`) is retained and any future parser fix lands by offline
re-parse. This should be the last re-scrape the corpus ever needs.

Measured against the archived pre-fix outputs, 2,463 records changed:

- **2019-ep's conviction count went from 0 to 6.** All six candidates carried
  the erased-questionnaire signature the nested-table defect left behind;
  their full questionnaires are recovered.
- **329 records gained private-interest free text** (62 in 2016 Seimo, 93 in
  2020, 145 in 2024, 29 in 2024 EP). The 146th predicted 2024 Seimo record
  (Kęstutis Sidabras) held only the placeholder `-` behind its mangled label
  — nothing to recover, and it now correctly normalizes to null.
- **235 campaign decision records** now appear across the five (118 in
  `2019-ep` alone), confirming the Sprendimai normalization matters most
  where campaigns are dense.

### The 2026-08-21 scrapes of the 2012-2014 national elections

The four elections between the 1990s archive and the 2015 backlog (GitHub
issues #44-#47) were built on the 2015-era parsers and scraped the same day,
both with `KEEP_SAMPLES=1` so their raw HTML sits under `samples-full/`:
`2014-ep` (215 candidates, 0 fetch failures, 0 anomalies) and `2012-seimo`
(1,927 candidates, 0 fetch failures, 0 anomalies). The two small ones —
`2014-prezidento` (7) and `2013-kovo-3-seimo-birzai-zarasai-ukmerge` (37) —
are complete fields as fixtures. Before any candidate page was fetched, the
2012 sitemap was reconciled against VRK's own list index: 1,878 list
candidacies exactly as declared, every list row's constituency agreeing with
the constituency page, and the 49 constituency-only candidates equal to the
52 distinct people on VRK's "tik vienmandatėse" pages less the 3 who also
hold a list seat (the index's declared 58 still counts five withdrawn
self-nominations). The `stats` block of `sitemaps/2012-seimo.json` records
each of these. Every null in the fixture records was traced to a genuinely
blank or omitted source line before the full runs started.

### The 2026-08-23 recovery of 1996-1997 birthplaces

GitHub issue #63. The 1996-1998 Seimas archive publishes no birth-place field,
so its 881 biographies were the only source. The text was already stored as
`biografija.tekstas`, making this a pure offline pass —
`scripts/backfill_archive_birthplaces.py`, no page fetched, nothing but
`anketa.gimimo-vieta` and its source marker touched.

**447 of 906 records gained a birthplace.** The conversion from the prose's
locative to the corpus's nominative is settled by lookup against
`scraper/shared/vietovardziai.json` (1,100 names, built from the rest of the
corpus by `scripts/build_place_vocabulary.py`), because suffix rules are
ambiguous — `-yje` yields both *Panevėžys* and *Radviliškis*.

Precision was measured against VRK itself: 247 of the recovered values belong
to people who also stood in an election that publishes the field outright, and
**all 247 name the same place**. They are frequently less specific — the
district where a later form gives the village — but none contradicts. The
country name was excluded after that check: three candidates whose sentence
gave only "Lietuvoje" had a real birthplace published elsewhere.

Nothing else is taken from the prose. Education and work history match on most
records but roughly a third of the matches are truncated, run on into the next
clause, or capture a specialty in place of an institution, which is below the
bar for writing into a normalized field. See `docs/OUTPUT_SCHEMA.md`.

### The 2026-08-23 backfill of the 1996-1997 archive declarations

GitHub issue #63. The five archive elections were scraped before their
`kpdl.htm` income and asset declarations were parsed, so 7,292 records carried
`profilis.pajamu-deklaracijos-nuoroda` and no figures -- the only elections in
the corpus without them.

`scripts/backfill_archive_declarations.py` fetched the one page per candidate
and merged the parsed block into the existing record. The candidate pages had
not changed, so this touched only the new key: 6,469 fetches rather than the
~20,000 a full re-scrape would have cost, and no window where the corpus was
missing records. `scripts/run_election_batches.sh` could not do it -- it skips
any candidate whose record already exists, being a resumable *initial* scrape.
Equivalence was measured rather than assumed: over the 124 archive fixture
candidates holding both a candidate page and a declaration, the merged record
is identical key for key to what `build_candidate_record` writes.

**0 fetch failures across 6,469 pages.** Coverage after the run:

| election | records | with declaration | turtas | income (total) | income (employment) |
|---|---:|---:|---:|---:|---:|
| `1996-spalio-20-seimo` | 879 | 879 | 877 | 868 | 877 |
| `1997-kovo-23-savivaldybiu-tarybu` | 6276 | 5477 | 5477 | 1014 | 5477 |
| `1997-birzelio-29-svenciniu-tarybos-pakartotiniai` | 110 | 108 | 108 | 107 | 108 |
| `1997-kovo-23-seimo-pakartotiniai` | 23 | 1 | 1 | 1 | 1 |
| `1997-gruodzio-21-seimo-pakartotiniai` | 4 | 4 | 4 | 4 | 4 |
| **total** | **7292** | **6469** | **6467** | **1994** | **6467** |

The 823 records without a declaration link none from their candidate page.
The gap between the two income columns is section III's total row: it renders
0 against a non-zero row 1 on 4,463 of the municipal general's declarations,
9 of 1996's and 1 of Švenčionys', and a total its own detail line contradicts
is refused rather than published (see `docs/OUTPUT_SCHEMA.md` and the module
docstring). The refused figure is kept in the anomaly, and the employment row
is published either way -- which is why every record but two has an income
figure even where the total is unusable.

Two 1996 declarations are permanently unreadable: VRK's archive froze an
Oracle error into them (`ORA-02391: exceeded simultaneous SESSIONS_PER_USER
limit`), still served at those URLs today. They are the two records missing
turtas and are recorded as `DeclarationPageUnreadable`.

The fetched HTML is retained under `samples-full/<election-id>/<candidate-id>/`
so a later parser fix can be an offline re-parse.

In the same pass, `scripts/reshape_1997_education.py` reshaped
`anketa.issilavinimas` on 5,192 municipal-archive records from a bare level
string into the corpus's `{"aprasas", "irasai": [...]}` object -- a pure local
reshape of a value already present, needing no fetch. `issilavinimas` was the
last concept in the corpus with two shapes.

### The 2026-08-22 scrape of the 2011 municipal general election

GitHub issue #42; VRK election 409 (2011-02-27) — the last municipal
general before mayors were elected directly, and the only general election
in which self-nominated individuals stood for the council on their own.
The listing is the 2015 municipal shape (index, 60 district pages, the
lists under them) walked by the 2015 repeat-election machinery with this
module's own district-row reader, because a direct candidate link on a
district page is an individual here rather than a mayoral candidate.
Sitemap: **16,403 candidates** — 16,260 on 599 lists (560 party, 11 party
coalitions, 28 coalitions of self-nominated candidates) and 143 individuals
— reconciled against VRK's three roll-ups with every check at 0 (the
self-nominated roll-up's 505 = the 143 individuals + the 362 coalition
members). Pages are the 2015-era static layout with the municipal question
set: four tabs, no biography, no campaign link anywhere. Results:
`2011_savivaldybiu_tarybu_rinkimai` via the municipal walker, generalised
for a seat won on an individual's own results row, a totals row without
percentage columns, and a mandate total that is the whole council (no
mayoral seat): 1,526 seats, 18 of them self-nominated individuals, all 60
composition pages containing every derived winner, 0 seat mismatches.

Full scrape with `KEEP_SAMPLES=1` (worktree symlinked onto the main
checkout's `data/` and `samples-full/`): 09:57–16:24 UTC, 83 batches,
**16,400 of 16,403** fetched and parsed, **0 anomalies**, 562 MB of HTML
retained. The three missing are candidate pages VRK never published (all
four tabs 404; see Known gaps) — the batch runner names them in
`failed_ids.txt`. Measured over the full corpus: 1,526 elected (every
results-file winner present), the card's "Išsikėlęs kandidatas" flag on
exactly the 505 self-nominated candidates, the parenthesised member-party
nomination on all 538 party-coalition members, 200 declared convictions
(79 with the Q9 explanation), income populated on all 16,400 once the
prose zero-income sentence parsed (20 records). Fixtures: ten candidates
chosen by shape. Two sibling defects surfaced and were fixed across the
2015 municipal family (the Q9 explanation, the prose zero income — rows
in the fix table above). Person index rebuilt: 47,125 persons (8,350 new;
the other 8,050 candidacies merged into people already in the corpus).

### The 2026-08-23/24 build and scrape of the 2000 municipal council general election

GitHub issue #25; VRK's `statiniai/puslapiai/n/rinkimai/20000319/` tree
(2000-03-19) — the 1997 municipal archive three years on (the same
Teleport capture, `tppabs` and all) carrying the 2000 Seimas candidate
document for the municipal form. `savivaldybiu_2000` reuses the 1997
list-page reader, the 2000 Seimas page readers and the 1990s declaration
parser; the candidacy block is the 2007 municipal general's. Listing:
the municipality directory is served as a 403, so the 60 municipalities
come from the results index; each municipality page lists its lists with
VRK's registration decision, and the 28 by-party pages (own list in
bold, coalition in plain type) are the cross-check and the only source
of a coalition's member parties. Sitemap: **9,881 candidates** on 651
lists (26 coalitions) in 60 municipalities, 1,562 seats declared, every
claim reconciling both ways, ids `<slug>-<vrk id>`. Results per
municipality (list votes and mandates, the members page, the preference
pages with winners in bold): 1,433 members in 55 municipalities, every
count matching the page's own seat number, the mandate column, the
totals row, the bold rows and each list's top ranks — all at 0. **Five
municipalities — Jurbarko, Kelmės, Radviliškio, Raseinių ir Vilkaviškio
rajono — exist in the archive only to the list level** (unlinked result
rows, the members and preference pages never captured), so their 806
candidates carry `isrinktas: null` with `rezultataiNeskelbiami` and the
129 seats are known per list, not per member; every record still gets
its list's votes and mandates (`tarybosNarys.sarasoBalsai`/`sarasoMandatai`).
Scraped overnight 2026-08-23/24 with `KEEP_SAMPLES=1` (116 MB):
**9,879/9,881 fetched — the two missing candidate pages are VRK's own
404s** (Binkauskas 84814, Kalendauskaitė 86936; their list rows and
preference votes exist, the pages do not — see Known gaps). Parse: after
one offline re-parse pass, **297 warnings + 1 error**, all source truth:
297 declaration totals refused by the row-20 guard (the guard learned on
this election that row 20 prints with the centai dropped, so a sub-litas
shortfall — 29 pages — is truncation and now stands; the 297 are the real
zero-or-short totals the 1990s family shows everywhere) and one
declaration section printed empty (Kaluina 87455). The municipal form
omits any question or field the candidate left unanswered — seven pages
print a single declaration question — so a missing question is a blank,
not an anomaly. What the field says: 9 declared a post-1990 conviction
("Taip"; the form has no explanation slot), 2 collaboration with foreign
services, 2 another citizenship (both Russia-adjacent lines with the
renunciation sub-question, one "Nesu atsisakęs"); 8,526 records carry an
education level, 7,786 languages, 286 a degree, 1,511 prior mandates;
all 9,879 a birth date, residence and declaration (9,731 with a trusted
income total). Fixtures are 10 candidates chosen by shape. Related
follow-up: none — the five list-level municipalities and two 404 pages
are permanent VRK gaps.

### The 2026-08-23 build and scrape of the 2000 Seimas general election

GitHub issue #26; VRK's `statiniai/puslapiai/n/rinkimai/20001008/` tree
(2000-10-08), the last of the LRS-ITD Oracle-CGI captures: the 1996-1998
Seimas archive's template carrying the 2004 static site's content in one
page per candidate — card, the seven Q8/Q9 declarations, the
questionnaire fields, the 1990s income and asset form inline with the
figures to the centas, the autobiography. `seimo_2000` is its own module
over two shared pieces: the 2004 Seimas listing merge, lifted out of
`seimo_2004` as `merge_listing_records` (its stats gained
`districtOnlyUnaccounted`; the 2004 sitemap is otherwise byte-for-byte
what it was), and the 1990s declaration parser, which learned decimal
amounts and section I's workplace lines (the 1996-1997 figures are whole
litas and their workplace lines blank, so their records are unchanged —
58 tests green). Sitemap: **1,271 candidates** (582 in both structures,
569 list-only, 120 constituency-only) from 15 lists, 13 unnumbered
parties (4 coalition members, resolved from the pages since the 2000
index does not say, 9 constituency-only) and 71 constituencies; every
cross-check at 0 but one — Virginijus Šmigelskas is the LCS nominee on
the Širvintų–Vilniaus page and absent from the LCS party page (which has
his namesake Vidmantas at #48), so the constituency-only reconciliation
is 119 + 1 unaccounted, the source's own gap; three namesake pairs take
positional ids. Results from the tree's own pages: **141 members by id**
(70 list, 71 constituency — every one decided in one round by plurality,
the 2000 rule, and every one the top of its vote page), 70 mandates
matching the members page per list, every list ranked (LLRA included;
rank, preference votes, VRK's party rating and rating points joined into
all 1,151 list candidates' records), the list seats exactly the top ranks
after the 54 constituency winners are passed over, and — unlike 2004 —
the 71 constituency pages keyed by the candidate-page id, so all 702
constituency candidates carry their ballot-box, postal and total votes,
share and place. Scraped the same afternoon with `KEEP_SAMPLES=1`:
**1,271/1,271 fetched, 0 fetch failures, 19 parse anomalies** after one
offline re-parse — the first pass lost Q9.1 on eleven cards where a
non-default 8.4 brings an 8.4.1 sub-question whose answer the page prints
with no `<b>` at all (the reader now splits the run at every question
number; 8.3.1 "Kurios" and 8.4.1 are new `pareiskimai` keys), fixed
against the retained HTML without a re-fetch. The 19: 15 declaration
totals refused by the family's row-20 guard (9 income totals of 0 against
a non-zero row 1, 6 tax totals below their row — income stands on 1,262
records), 2 cards with no residence line, and 2 `ElectedNoteMismatch` —
Babravičius and Žukauskas won seats but their cards carry no winner
note, because theirs are 2 of the **32 pages VRK's archive holds in the
pre-results vintage** (links to the live `cgi-bin/ora7dbcgi/`, the note
not yet added); the other 139 members' cards all carry it and no
non-member's does. What the field says: five candidates declared another
citizenship (JAV ×3, Kanada+Lenkija, JAV), one a foreign oath, five a
conviction on Q9.2 (three with a sentence of explanation; 25 others
answered the explanation slot "Ne"), none a grave one; 700 cards have a
photo and 699 an autobiography, all 1,271 a birth date and a declaration
(279 with a secondary workplace), 138 a birthplace, 11 an education line
the candidate left as an empty `<b></b>`; three cards name a second
constituency nominator (`kitiIskelejai` — self-nominated beside the
party), 46 list seats went to people who also stood in a constituency.
Fixtures are 18 candidates chosen by shape.

### The 2026-08-23 build of the 2005 Kėdainiai Seimo by-election

GitHub issue #33; VRK's `rinkimai/2005/seimas/` tree (2005-11-20, the
seat Viktor Uspaskich gave up) — the 2004 Seimas pages one year on, so
`seimo_kedainiu_2005` is thin wiring over `seimo_2004`: its constituency
reader for the one district, the 2004 card hook and question mapping, the
2004 members-page reader for the results. Five candidates, one each from
five parties (the party index declares exactly that), the complete field
as fixtures, 0 anomalies; Baltraitienė (Darbo partija) won the runoff —
first-round turnout was 26% — joined by id with `rezultatuTuras: 2` and
cross-checked against the runoff winners page. Four of the five are
independent campaign participants with their registration decision PDF.
Person index: all five merge into existing people (every one of them
stood in 2004 or later).

### The 2026-08-23 build and scrape of the 2004 Seimas general election

GitHub issue #32; VRK's `rinkimai/2004/seimas/` tree (2004-10-10), four
months after the EP election on the same original static site, built the
same day as `seimo_2004` over `ep_2004`'s page readers. What the election
adds is the listing and the card: the 2008/2012 two-structure listing on
the 2004 template — 15 numbered lists, three constituency-only parties and
four coalition member parties on one index, 71 constituencies on the other
— read by a walk of this module's own because of three things the 2004
party pages do (a party's page lists every nominee of the party, the
constituency-only ones unnumbered below its list; a coalition's page names
each candidate's member party and position there, which the member's page
repeats the other way and the walk cross-checks; and a list page's
constituency column shows same-party nominations only, so the constituency
page is the authority — 17 people sit on one party's list and another's
constituency nomination). Sitemap: **1,251 candidates** (534 in both
structures, 649 list-only, 68 constituency-only), every declared count
met, member positions agreeing with the coalition pages, no name
collisions. The card states every candidacy and, for 455 candidates, the
campaign registration decision (a PDF) — `savarankiskasKampanijosDalyvis`
— and two cards name a second nominator the constituency page does not
(`vienmandate.kitiIskelejai`). The question set is the Seimo rinkimų
įstatymo form under the 2016 keys; uniform on all 1,251 pages (eight
declared convictions on Q9.2, four grave ones on Q9.3, ten explanations).
Results from the tree's own pages: **141 members by id** (70 list, 71
constituency — 5 in the first round, 66 in the runoff, the round on the
row), cross-checked by id against the list-seat and constituency-winner
pages and the mandate column, all at 0; rank and preference votes from the
15 ranking pages joined into every list candidate's record, the LLRA list
(unranked at the party's request) with rank but no votes. Two source
gaps, both VRK's: Žiobakienė's declarations page was never published (no
link, a 404 — the fixture index records the `MissingExpectedTab`; the
record has no declarations section) and Matkevičius's prints the income
extract only. The 2004 page readers learned one thing, a no-op on the EP
pages: an unanswered degree/title drops its `<b></b>`, merging the two
labels into one text run, now split into two rows (EP's 241 records
re-parsed byte-identical). Scraped the same afternoon with
`KEEP_SAMPLES=1`: **1,251/1,251 fetched, 0 fetch failures, 0 parse
anomalies** — with one self-inflicted detour worth recording: the runner
marked 79 candidates failed because the parser module was being edited
under it mid-run (a mutation check on the tests overwrote a file for a
few seconds, and the runner invokes the parser afresh per candidate);
their pages had fetched fine and every record was rewritten by the
offline re-parse of the retained HTML that closed the run; the retained
pages are byte-identical to an independent download made while the
module was built (3,752 files; the 3,753rd is the 404). Fixtures are 14
candidates chosen by shape. Person index: 1,251 candidacies, 1,015
merged into existing people by name and birth date (705 also stood in
the 2007 municipal general, 510 in the 2008 Seimas election, 180 in the
EP election four months earlier), 236 new persons (53,175 in all); every
record carries a birth date.

### The 2026-08-23 build and scrape of the 2004 European Parliament election

GitHub issue #31; VRK's `rinkimai/2004/euro/` tree (2004-06-13) —
Lithuania's first EP election, one month after accession, and the first
election in the corpus published on VRK's **original 2004 static site**
(the LRS-ITD page template): a layout family of its own between the
1996-1998 Teleport archive and the 2015-era pages every election from 2007
on shares, read by `scraper/elections/ep_2004/`. The listing is the
2009/2014 EP index-and-lists shape, walked by `ep_2014`'s code with this
tree's link patterns and one generalisation measured a no-op on the flat
2009/2014 tables: the 2004 pages nest the whole layout in tables, so only
the row an anchor sits in directly is a candidate row (read naively, 277
rows for 241 and every list position lost). Sitemap: **241 candidates on
12 lists**, every list equal to its declared size, no name collisions.
The candidate is three pages — the questionnaire, the biography and the
income-and-asset extracts — linked from the profile card, read by page
readers of this module's own (the row shape, the trailing degree/title and
spouse pairs, the bold-headed record tables, the five FR0462 form lines
summed into the declared income); the normalizers, the results join and
the record writer are the shared ones. The question set is the 2009 EP
form five years earlier, under `ep_2009`'s keys (birth date at Q3, another
member state's citizenship at Q8.4 with 8.4.1/8.4.2 — one candidate, French
— and the Q9 explanation as an unlabelled row after 9.3 on five pages).
Results from the tree's own pages: the 13 members by id, the national
page's mandate column and the 12 per-list ranking pages all agreeing, the
ranking's rank and preference votes joined into every record; VRK's
footnote substitution (Prunskienė's mandate terminated by decision Nr.
180, Didžiokas seated by Nr. 181) recorded on both records, so **14
records carry `isrinktas` for 13 seats**. Scraped the same night with
`KEEP_SAMPLES=1`: **241/241, 0 fetch failures, 0 parse anomalies**,
8.7 MB of HTML retained; the retained pages are byte-identical to an
independent download made while the module was built. Fixtures are 13
candidates chosen by shape. Person index: 241 candidacies, 198 merged into
existing people by name and birth date (119 also stood in the 2008 Seimas
election, 113 in the 2007 municipal general, 63 in 2009 EP), 43 new
persons; every record carries a birth date (the page's "1942.01.01" is
written as the corpus's ISO form, which is what the join keys on).

### The 2026-08-22 build of the 2007 municipal general election

GitHub issue #34; VRK election 3 (2007-02-25) — the oldest municipal
election with candidate pages, the same year as the Dzūkija by-election and
one tree older than the 2008 Seimo general (the path is `rinkimai/3/`,
without `_lt`). Council seats only; only parties and coalitions of parties
could nominate. The listing is the 2011/2015 municipal shape one rename
away (VRK's index of 60 municipality pages and 24 by-party pages, a ballot
of list rows per municipality, the lists under them), walked by the 2015
repeat-election machinery with this module's index and by-party readers.
Sitemap: **13,422 candidates on 600 lists** (596 party lists, 4 party
coalitions — Ignalina, Neringa, Telšiai, Vilnius — each of two parties,
named from the member parties' own pages), nobody standing alone or twice,
reconciled against the by-party pages with every check at 0 (the 8 party
links that lead to no ballot are the coalition members' empty shells).
Pages are the family's oldest shape — the Dzūkija card and an unnumbered
"label: answer" questionnaire keyed by its prompts, three tabs, no
campaign link — and they surfaced three things in the shared era code,
each measured a no-op on the numbered 2008–2015 pages (2012 Seimo
re-parsed to scratch: 1,918 records byte-identical): the interest
declaration's record tables (the fix row above, 1,593 existing records
re-parsed), the income stated as five FR0462 prose lines of which one is
non-zero (the prose income reader now sums the lines — 2011 and 2015 print
one), and an empty `<b></b>` answer that did not close its row, so the
next label joined the prompt and would have taken the next value (one
fixture, Pilvinis, whose questionnaire stops after two empty answers).
Results: `2007_savivaldybiu_tarybu_rinkimai/` (no `output_lt`), where each
municipality's results page links a "Mandatus gavę kandidatai" page that
names every winner with an anketa link — **1,550 seats read by id**, the
results-table total, the lists' mandate sum and the composition page's
council size agreeing in all 60. Fixtures: ten candidates chosen by
shape, 0 anomalies.

Full scrape with `KEEP_SAMPLES=1`, from the main checkout: 17:26–22:04 UTC,
68 batches, **13,419 of 13,422** fetched and parsed, **0 anomalies**,
368 MB of HTML retained. The three missing are candidate pages VRK never
published — every tab of `Kandidatas<ID>/` a 404 (see Known gaps). The
full field then showed what ten fixtures could not, all in the unnumbered
questionnaire and all this election's own: a question printed with no
`<b>` at all (the pasyvioji rinkimų teisė question on 611 pages, the
citizenship one on 8) ran its label into the next label's prompt, so every
answer after it sat under the label before its own — "Ne" from the
conviction question under `ar-pasyvioji-…` on 611 records; the conviction
explanation is a bare text line after "Taip" that joined the "Gimimo
vieta:" prompt (39 records, with their birthplace gone null); the
"Moksliniai vardai" line (133) had no key; and the family line has more
roles than the fixtures showed (Partneris/partnerė, Augintinis, Anūkas,
and a bare name continuing the previous role). The normalizer now splits
a prompt wherever one of the form's labels begins inside it, reads the
explanation into `pareiskimai.teisiniai-argumentai` and the title into
`pedagoginis-vardas`; re-parsed offline from the retained HTML, after
which every declaration key holds only its own vocabulary (78 "Taip", 39
explanations, 37 birthplaces recovered). Measured over the corpus: 1,550
elected (every results-file winner present), income on 13,363 records
(56 pages say "duomenys nesuvesti", as do 384 interest declarations),
degree on 753, title on 133. Person index rebuilt: 52,896 persons (5,771
new; the other 7,648 candidacies merged into people already in the corpus).

### The 2026-08-22 build of the 2007 Dzūkija Seimo by-election

GitHub issue #35; VRK election 396 (Dzūkijos No. 69, 2007-10-07) — the
oldest page of the pre-2016 static family, one year before the 2008
general, and the only one so far under a path without the `_lt` suffix.
The listing is the one constituency page (the index is a meta-refresh to
it), walked by the Žirmūnai machinery and enriched with VRK's id and the
nominator; 10 candidates, the whole field as fixtures, 0 anomalies. Three
things are this election's own, each handled in the shared code it
belongs to and measured harmless elsewhere: the listing prints names in
capitals (restored to the corpus's "Ona BALEVIČIŪTĖ"); the profile card
is the family's oldest shape — plain-text name and "Gimimo data:" line
(the form asks no Q5; the card's date now fills `anketa.gimimo-data`),
constituency and party in a header table above the card, a campaign link
with one `../` too many — read by a legacy-card branch of the era's card
parser and a one-path rewrite in its URL resolver; and the
`2007_seimo_rinkimai` results tree has no `output_lt` level, keeps round
two in the round-one folder and links its candidate rows straight to the
anketa pages, all three taught to the shared walker (`tree_root`, a
round-two folder fallback, anketa-linked rows). Čilinskas (TS) joined as
the winner by runoff plurality (56.4%). The income extract is the interim
**GPM302** return, one form older than 2008's GPM305 — a fourth alias.
Six of the ten are represented candidates whose card says so in words
("Kandidatas nėra savarankiškas politinės kampanijos dalyvis") and links
no campaign; the four independents' campaign pages parsed in full. One
VRK-side mojibake: Orenienė's Q8.4.1 answer reads "NenurodÄ—" in the
source HTML (kept as published in `rawData`; the sub-question maps to
nothing). 7 of the 10 merged into existing people (38,775 persons).

### The 2026-08-22 builds of the 2009 and 2011 Seimo by-elections

GitHub issues #39, #40 (one VRK election, 406: the two seats the June 2009
EP election vacated, Šilalės–Šilutės No. 33 and Vilniaus–Šalčininkų No. 56,
voted on 2009-11-15) and #41 (VRK election 410, Marijampolės No. 29,
2011-02-13). Both are the March 2013 repeat election's shape exactly —
a constituency index, the 2012 question set, five tabs, campaign links —
so `seimo_silales_silutes_vilniaus_salcininku_2009` and
`seimo_marijampoles_2011` are thin wiring over that module. 17 and 9
candidates, complete fields as fixtures, 0 anomalies, every campaign link
resolved. Elected status joined from the constituency results trees
(`2009_seimo_rinkimai`, `2011_seimo_rinkimai`), which needed two
generalisations of the shared walker: their candidate row pages reuse the
presidential template's `rezultatai_prezidento_kand…` stem, and a
constituency decided outright in round one (Vilniaus–Šalčininkų, Talmont
at 77.8%) is named only on the tree's first-round elected page
(`rezultatai_vienmand_apygardose/isrinkti_seimo_nariai.html`), which the
walker now consults — the 2008 results rebuild identically.

Issue #43 (Danės No. 19, 2011-07-03, VRK election 412) has **no candidate
data on VRK**: the constituency page's candidate table is empty, the
"Balsavimo rezultatai" page is an empty Liferay shell, no July 2011 results
tree exists, and a probe of 164 candidate ids above Marijampolė's range
found no candidate page; only the campaign participants index survives
(ten participants). Not built.

### The 2026-08-22 scrape of the 2008 Seimo general election

GitHub issue #36; VRK election 400, the 2012 general election's
two-structure listing one term earlier — 16 numbered lists and 71
constituencies merged on VRK's candidate id into **1,603 candidates** (770
in both, 813 list-only, 20 constituency-only). Built on `seimo_2012`'s
walk, generalised for two 2008 differences (coalition member-party links
without the `_3` suffix; no "Išsikėlę" page, so the self-nominated are
counted from the constituency rows), and reconciled before any candidate
page was fetched: 1,583 list candidacies exactly as declared, every list
row's constituency agreeing with the constituency page, and the 20
district-only candidates equal to the 5 on VRK's "tik vienmandatėse" pages
plus the 15 self-nominated. Scraped the same night with `KEEP_SAMPLES=1`:
**1,603/1,603, 0 fetch failures**, one `AnketaNotPublished` warning
(Sigitas Bankauskas, coalition list #98, whose anketa page is an empty
content div — the parser now reads that as the unpublished case it is,
not as a broken table). 141 Seimas members joined from VRK's
elected-members page, all in the sitemap; 70 of 71 constituency pages
cross-check to the same winner, the 71st being Varėnos–Eišiškių, where
two Algis KAŠĖTAs stood against each other and name resolution rightly
declines. The 2008 pages carry **no campaign participant link** (VRK's
participants index for the election exists but no candidate page links
it) and no *Kita* tab, so the records have neither section. Fixtures are
ten shape-chosen candidates; 61 MB of HTML retained. Person index: 1,603
candidacies, 1,066 merged into existing people, 537 new persons (38,769
total; the one record without a birth date is Bankauskas's).

Its field surfaced the widest sibling gap of the week: the 2015-era
normalizer had never mapped the degree/title line after the education
table ("Jei turite, nurodykite mokslo laipsnį …, vardą …"), so
`mokslo-laipsnis` and `pedagoginis-vardas` — keys every 2019+ era has —
were absent from the whole family. Mapped and re-parsed offline across
eleven elections; the counts are in the correctness table.

### The 2026-08-22 scrape of the 2009 European Parliament election

GitHub issue #38; VRK election 404, the 2014 EP listing one revision
earlier (15 party lists, 262 candidates, every list walked equal to its
declared size). Built on `ep_2014`'s walkers with its own question mapping
and scraped the same evening with `KEEP_SAMPLES=1`: **262/262, 0 fetch
failures, 0 parse anomalies beyond two `CampaignRootMissing` warnings** —
Tomaševski's and Matulevičius's pages link campaign participant ids that
do not exist under the EP path (Tomaševski's is his presidential campaign's,
valid under `403_lt`), a VRK cross-link error recorded as what it is. 12
MEPs joined from the elected-members page, all in the sitemap. Fixtures are
the 15 list leaders. 20 MB of HTML retained under `samples-full/`.

Reading its fixtures back to the page added two things the 2012 Seimo
records had been missing as well: the Q9 block's free-text conviction
explanation (`pareiskimai.teisiniai-argumentai`, the 2016 Seimo key for the
same slot — **24 of 2012's 50 declared convictions carry one**, recovered
by offline re-parse), and a parse-stage `CampaignRootMissing` warning for a
campaign whose root never fetched, which until now vanished from both the
record and `anomalies.jsonl` (two 2009 EP cases; none elsewhere in the
retained scrapes). Person index: 262 candidacies, 204 merged into existing
people, 58 new persons (38,232 total).

### The 2026-08-22 build of the 2009 presidential election

The oldest election of the pre-2016 static layout (GitHub issue #37; VRK
election 403) — seven candidates, the complete field as fixtures, 0
anomalies, `isrinktas` joined from the first-round nationwide vote table
("Respublikos Prezidente išrinkta Dalia GRYBAUSKAITĖ"; the tree's
certificate-style final page declines the name, so the shared pattern now
ends a name at its upper-cased surname instead of at a period). Its pages
are one revision older than 2012's at every level — the four-question
eligibility set plus the KGB lustration question, the roman-numbered
interest form with value-band codes, `<td><strong>` table headings on the
campaign pages, a dead trustees tab on every candidate (recorded, not
fetched) — and reading every null in the seven records back to the page
surfaced two defects in the shared era parser that reached far beyond 2009
(the two rows at the foot of the correctness table): **15,837 records'
income and tax recovered** across the 2015 municipal family and **1,576
records' donation totals re-keyed** across the 2012–2014 elections. All
seven 2009 candidates merged into existing persons in the dashboard index
(Tomaševski now spans 1996–2019); the person count is unchanged at 38,174.

### The 2026-08-21 elected-status join for 2012–2015

The ten elections of the pre-2016 static layout then in the corpus had
`isrinktas: null` everywhere because their pages mark no winner. VRK's static results trees
do name the winners, and `python -m scraper build-results <id>` now walks
them — the elected-members page for 2012, constituency pages (two rounds,
round two under re-issued ids) for 2013 and the 2015 by-elections, the EP
members page, the presidential final-results page, and for the four 2015
municipal elections the per-municipality results pages with each list's
mandate count and post-preference ranking. Every winner resolved to a VRK
candidate id in the sitemap, with zero unresolved names; the 2012 members
list agrees with all 69 non-annulled constituency pages; in 58 of 60
municipalities every derived March 2015 winner appears on VRK's own
composition page, the two exceptions being the councils VRK annulled
(Šilutė, Trakai — 48 winners flagged `rezultataiPanaikinti`, not counted).
The records were re-parsed offline from the retained HTML.

Both municipal general elections were re-scraped overnight with
`KEEP_SAMPLES=1` — 2023 in 3h33m, 2019 in 3h29m, zero fetch failures, zero
failed candidates, zero anomalies in either. This was the corpus's last
planned scrape: with it, **every election's full raw HTML is retained**
(`samples-full/` for the seven large elections, the fixture tree for the
twelve small ones — 3.6 GB total), so any future parser fix lands by offline
re-parse.

Measured against the archived pre-scrape copies:

- **2019**: all 13,666 records now carry `teistumo-detales` (244 non-empty
  with the same 303 conviction rows the targeted re-fetch recovered); not a
  single record changed beyond that key — a fresh scrape reproduced the
  corpus byte-for-byte otherwise.
- **2023**: 13,794 of 13,796 records byte-identical. The two that changed are
  the last pre-fix remnants healing: both were written minutes before the
  `partyList.number` sitemap fix landed on 2026-08-17 and still carried the
  Akmenės group-header value (list 25); the fresh scrape corrected them to 5.
- The artifact scan over the fresh corpora matches the review baseline — no
  new artifact classes; the two known upstream quirks (one `&amp;`
  double-escape, the non-NFC file names) reproduce verbatim from VRK.

### The 2023 municipal general election

`2023-kovo-5-savivaldybiu-tarybu-ir-meru` is on its own in the table above
because it is bigger than every other election combined. Its counts reconcile
exactly with VRK's own `savKandidataiSuvestine.html` summary:

| | scraped | VRK publishes |
|---|---:|---:|
| candidates (union of both listings) | 13,796 | 13,796 |
| mayoral candidates | 433 | 433 |
| council candidates | 13,769 | 13,769 |
| standing for both | 406 | — |
| party/committee lists | 467 | 467 |
| elected mayors | 60 | 60 |
| elected council members | 1,498 | 1,498 |

The two listings overlap rather than nest: 406 people appear in both under the
same VRK candidate id, and 27 mayoral candidates appear on no list, so
433 + 13,769 − 406 = 13,796. The elected total is 1,557 distinct people rather
than the 1,558 mandates, because one person — Erlandas Galaguz in Visaginas —
won a council seat and the mayoralty at once.

The full run took ~6h at the default 0.4s throttle (~1.6s per candidate) with
zero fetch failures, zero failed candidates and zero parse anomalies. Getting
there needed two fixes to `scripts/run_election_batches.sh`, which no earlier
election was large enough to stress: the pending-list rebuild ran one `grep`
per candidate per batch — around 965,000 subprocesses over an election this
size — and it re-queued permanently failing candidates forever, so a single
unfetchable page would have made an unattended `MAX_BATCHES=0` run loop without
end.

Two fields are null for a noticeable minority, and both are genuinely blank
upstream rather than parser misses: `biografija.tautybe` for 471 candidates
(3.4%), published as `Nenurodė`, and `anketa.einamos-pareigos` for 313 (2.3%),
published as `-`.

### The 2019 municipal general election

`2019-kovo-3-savivaldybiu-tarybu` reconciles with VRK's own
`savKandidataiSuvestine.html` on every count:

| | scraped | VRK publishes |
|---|---:|---:|
| candidates (union of both listings) | 13,666 | 13,666 |
| mayoral candidates | 410 | 410 |
| council candidates | 13,635 | 13,635 |
| standing for both | 379 | — |
| party/coalition/committee lists | 465 | 465 |
| elected mayors | 60 | 60 |
| elected council members | 1,442 | 1,442 |

410 + 13,635 − 379 = 13,666, with 31 mayoral candidates on no list. Roles
partition as 13,256 council-only, 379 dual and 31 mayor-only. Unlike 2023, the
elected total is exactly 60 + 1,442 = 1,502 distinct people: VRK's mandate
columns are headed *"be merų"* and an elected mayor takes no council seat, so
no one appears in both counts.

The run took ~6h with zero fetch failures, zero failed candidates and zero
parse anomalies.

**244 candidates declared a conviction.** Every one of them would have had
their entire questionnaire discarded before the nested-table fix listed below
— the defect erased exactly the records this field exists to surface.

Three nulls to expect, all traced to the source and all genuine:

- `anketa.pagrindine-darboviete` for 4,572 candidates (33.5%) and
  `anketa.tautybe` for 2,992 (21.9%), both published as `Nenurodė`.
- Q9.2–Q9.4 for 110 candidates, whose pages print those questions with no
  answer between them.
- `gautos-pajamos` for 10 candidates whose declared income VRK itself renders
  malformed, with the integer part missing — `,35 EUR`, `,72 EUR` and so on.
  Reading those as 0.35 would be inventing a figure, so they normalize to null
  with the source text kept in `rawData`.

Photo and free-text biography are role-dependent rather than sparse: measured
across the corpus, they are published only for candidates standing for mayor,
so ~97% of records carry neither. That is upstream behaviour, not a parse
failure.

Campaign data is thinner than 2023's: 395 of 410 participants are
`Atstovaujamasis` and publish no donation figures at all, and the 15
`Savarankiškas` ones do not share a campaign with anyone, so the
per-campaign de-duplication that matters elsewhere is a no-op here —
€251,959.63 either way.

## Caveats for analysis

### Campaign donations are per campaign, not per candidate

Donation records belong to a *campaign participant*. In list-based elections one
participant covers many candidates, and each of those candidates' records
contains the whole shared donation list. Summing donations across candidates
therefore multiplies the same money:

| election | candidates with campaign data | distinct campaigns | largest share |
|---|---:|---:|---:|
| `2019-ep` | 279 | 15 | one campaign across 22 candidates |
| `2024-seimo` | 699 | 205 | one campaign across 70 candidates |
| `2023-kovo-5-savivaldybiu-tarybu-ir-meru` | 433 | 58 | one campaign across 59 candidates |
| `2019-kovo-3-savivaldybiu-tarybu` | 410 | 15 | none shared |
| `2020-seimo` | 758 | 298 | none shared |
| `2016-seimo` | 672 | 324 | none shared |

The effect is large. For 2019 EP, naively adding donation amounts across
candidate records gives €29.2M; de-duplicating by campaign gives **€1.44M** — a
20× inflation. Always group by campaign identity (`sprendimo-numeris`, or the
`campaignKey` in `rawData`) before summing.

The 2023 municipal election is the sharpest illustration of *why* the sharing
happens: only 11 of its 433 campaign participants are `Savarankiškas` (running
their own campaign), and the other 422 are `Atstovaujamasis` — their party runs
the campaign, so dozens of candidates share one participant record. Naive
summing gives €495,154; de-duplicated it is **€295,300**, a 1.7× inflation.
The factor is smaller than 2019 EP's only because most of those 422 candidates
share campaigns that declared nothing at all.

### Conviction data has two different shapes

Every election except `2019-prezidento` — whose pages ask the constitutional
eligibility questions instead — records the yes/no declaration under
`normalized.anketa.pareiskimai.ar-buvote-pripazintas-kaltu`, and that is the
field to count on. The answer is the page's own wording: `Taip`/`Ne` from
2008 on, first-person `Neturiu`/`Nesu` on the 2007 cards, and the 2004 EP
form's third person — `Yra`/`Nėra`, with `Buvo`/`Nebuvo` on its Q9.3 — so a
cross-era count matches on the yes-forms, not on one string. Structured conviction *details* (date, court, offence) exist
only where the page publishes them:

- 2023 onward (Rinkimų kodekso era), 2021 and — since the nested-row capture
  fix below — `2019-kovo-3-savivaldybiu-tarybu`: normalized
  `anketa.teistumo-detales`
- 2016/2020 Seimo and `2019-ep`: the same detail table sits in
  `rawData.anketa.rows` as a prompt-less records row keyed by the column
  headings — all 38 declarers in 2016 and all 41 in 2020 carry it, and after
  the capture fix so do the six in `2019-ep` — with no normalized
  representation
- 2017 mayoral: the declaration answer is on a continuation row (see the module
  docs), and no 2017 or 2019-presidential page publishes a detail table

Counting normalized `teistumo-detales` alone therefore under-reports; it
returns 0 for the 2016 and 2020 Seimas elections, which record 38 and 41
declared convictions respectively.

The conviction counts in the inventory above are post-fix throughout: the
2026-08-18 re-scrape left the 2016/2020/2024 counts unchanged (their parser
lineage always captured the detail row) and recovered the six 2019 EP
declarers whose questionnaires the nested-table defect had erased.

### Placeholder answers normalize to null — and the list is exact

Exactly three strings become `null`: `Nenurodė` ("did not specify"), `-` and
the empty string. A null means "not answered on the page", not "no data
collected" — the source text is always preserved in `rawData`. Some
declarations are genuinely blank upstream: every 2021 Radviliškis candidate
left Q10 unanswered, and individual candidates elsewhere left single questions
blank.

Candidate-typed variants survive as answers **by design** — an answered
"none" is not an unanswered field. The variants in the corpus: the `Nėra`
case/diacritic family (`Nėra`/`nėra`/`NĖRA`/`nera`/`Nera`/`NERA`, 1,942
values, concentrated in membership, current-position and speciality fields),
`Nenurodyta` (35 values), `Nenurodoma` (1), `Nenurodė.` (2, the trailing dot
keeping it off the exact-match list), plus `--` (74), `.` (66), `–` (7) and
`N/A`/`n/a` (6). Count nulls and these variants separately: a null is a blank
form field, a surviving variant is a candidate stating they have none.

### `Neskelbiamas` saturates contact fields in the 2019–2021 era

`Neskelbiamas` is VRK's own "withheld" token, kept verbatim because it means
"withheld by VRK", not "unanswered". It is not sporadic — it saturates
`anketa.adresas` at **100%** in `2019-kovo-3-savivaldybiu-tarybu`
(13,666/13,666), `2020-seimo` (1,754/1,754), `2019-ep` (301/301),
`2019-prezidento` (9/9) and both 2021 mero elections (14/14 and 7/7). In the
elections whose anketa carries `kontaktai` — `2020-seimo` and the two 2021
mero elections — `telefonas` and `el-pastas` are 100% `Neskelbiamas` as well.
Any "has address/phone/email" coverage stat is therefore meaningless in those
elections: the field is a constant privacy token. VRK changed publication
policy later — the 2023/2024-era elections carry real city-level address
values and zero `Neskelbiamas`.

### Known upstream quirks

All of these are verbatim from VRK's own pages (verified present in
`rawData`), so they are documented rather than fixed:

- ~140 records carry a birth **date** in `gimimo-vieta` (birth *place*) —
  candidates typed the date into the wrong form field
  (`ramute-nalivaikiene-2016-seimo` has `gimimo-vieta` = `1963-06-14`, equal
  to her `gimimo-data`). The parser is faithful; don't read it as a
  field-shift bug.
- Campaign contract `agreementNumber` mixes five formats — VRK's contract
  registry lets filers type anything: bare numbers (1,517), ISO dates (286),
  space-separated dates (333), dotted dates (75), and free text — registry
  codes like `BK-16` or `P19/386` alongside "no number" markers (`be Nr.`,
  `nėra`, `ND`, `b/n`).
- `nuosprendzio-data` (conviction date) is year-only for 272 values against
  642 full ISO dates — year-only is what VRK publishes.
- One control character: the fourth campaign contract subject of
  `kestutis-masiulis-2016-seimo` carries `\x06` where `Ė` belongs
  (`PIRK\x06JO ir PARDAV\x06JO`) — mangled in VRK's contract registry itself.
- One double-escaped entity: `algis-cepulis-2425844` (2023 municipal) has the
  employer `If P&amp;C Insurance AS` in `biografija.darbo-patirtis` — the
  source HTML carried `&amp;amp;`, an upstream double-encoding, not a parser
  unescape miss.

### Per-election schemas are deliberately not identical

`docs/OUTPUT_SCHEMA.md` documents each election's own shape. The questionnaire
changed repeatedly (Seimo rinkimų įstatymas → savivaldybių tarybų rinkimų
įstatymas → Rinkimų kodeksas), so key sets differ by design. Field names are
shared wherever the underlying question matches, which makes cross-election
comparison possible for the declarations, assets, income and biography, but the
key list itself is election-specific.

## Correctness fixes behind this corpus

Twenty-one defects were found and fixed while building the newer modules. Each had
been invisible because the affected elections had thin or no test coverage, and
each was measured against live data after the fix:

| fix | effect on the corpus |
|---|---|
| donation tables of every published width | recovered donation rows for 2019 EP, 2019/2024 presidential, 2024 Seimo and the 2023 by-elections; previously only the 7-column 2016 layout parsed |
| 2024 Seimo profile and anketa numbering | name and photo went from null for 100% of candidates to populated for 100%; declarations from 0/11 to 11/11 answered |
| 2020 Seimo anketa numbering | current position, party membership and contact fields recovered for ~97% of 1754 candidates; declarations from 4/10 to 10/10 answered |
| record tables rendered in their own row | 525 of 1415 2016 Seimo candidates (37%) recovered their prior-mandate history: **+1,180 records** |
| nested `<tbody>` lookup | a candidate whose conviction table nested inside the anketa had their entire questionnaire collapse to one row |
| 2016 Seimo coverage audit | no defect found; the module gained the anketa tests it never had |
| campaign "Sprendimai" tab never normalized | the VRK decisions taken about a campaign — unlawful political advertising and the like — were fetched and kept in `rawData` but never reached `normalized`. Recovering them added **26 decisions to 23 records across 9 elections**. `2024-seimo` was unaffected: it has its own handler |
| private-interest items published without a label | free-text declaration sections such as "Kiti duomenys" are published as an unlabelled sentence, and any item without a key was dropped, so the whole declared text was lost from `normalized` while `rawData` kept it. It is now collected under a `tekstas` key |
| private-interest free text read as a *label* by the sibling parsers | auditing the unpatched copies of the fix above (seimo_2016, seimo_2020, seimo_2024) against the full-run `rawData` showed the empty-key drop never fires there — in those page eras the "Kiti duomenys" sentence is a one-cell row in a header-bearing table, which the raw parsers read as a **key**, so the normalizers emitted an ASCII-slugified copy of the sentence as a key with a `null` value (diacritics, case and punctuation destroyed). One-cell rows in tables that carry column headers are now parsed as unlabelled data rows and collected under the same `tekstas` key; one-cell rows in header-less tables stay group labels ("Darbovietė" et al., thousands of them in the 2021–2023 mayoral pages). The empty-key rescue itself is also ported to all three copies — the 2024 engine demonstrably publishes both variants (`<b>`-wrapped text lands in the value, plain text in the key). Measured over the full runs: **340 records / 344 free-text items recovered** — 62/1415 in 2016 Seimo, 93/1754 in 2020 Seimo, 146/1740 in 2024 Seimo, 29/319 in 2024 EP, plus 10 records across the small 2018–2025 elections — landing when each corpus is next re-parsed or re-scraped |
| income aliases reworded between 2017 and 2019 | the 2019 municipal module first reused `2017-balandzio-23-meru`'s asset/income aliases, which name GPM308 field numbers (`Gautų pajamų suma (GPM308 formos 12, 13, 14 … laukelių suma)`). 2019 states the same two figures in prose, so both income keys normalized to null while the values sat in `rawData`. With module-local aliases, `gautos-pajamos` and `sumoketas-pajamu-mokestis` went from **0/9 to 9/9 fixture candidates populated** |
| a nested conviction table erasing the questionnaire | `_is_records_table` decided with `table.find("th")`, which searches descendants. VRK nests the conviction-detail table inside the anketa table for anyone who answers the conviction question "Taip", so the whole anketa was classified as a records table and dropped — birth date, address, every declaration, birthplace, nationality — with no anomaly and nothing left in `rawData`. Confirmed on a 2019 candidate: **13 parsed rows instead of 27, every field null, including the conviction declaration itself**. The helper is inherited by ten modules, so every election has been under-reporting exactly the people the field exists to identify. A stale pre-fix duplicate of the helper survived in `prezidento_2019` and was fixed separately: re-parsing the nine presidential records with and without that fix produced byte-identical output — no 2019 presidential page nests a table inside the anketa — so the copy was corrected before it could bite, and the shape is guarded by a synthetic regression test |
| declarations 2019 asks and 2017 does not | reusing the 2017 mayoral parser assumed the same question set. Q8.1 (unserved sentence), Q9.2 (decriminalised offence), Q9.3 (foreign court) and Q9.4 (political persecution) are published and answered on every 2019 page and were dropped from `normalized`; `pareiskimai` went from **five keys to nine**. Q21 free text was lost too — 2017 numbers that question at the end of the prompt and is matched on prompt text, 2019 numbers it at the front |
| donations section whose heading carries its own empty-state marker | a campaign with nothing to declare renders `Gautos ir priimtos aukos: Duomenų nėra` inside the heading rather than as the text node that normally follows it. No table or text node follows, so the next heading overwrote the pending title and the section vanished — collapsing "declared no donations" into "section never published", and leaving the sections after it untitled. **6 sections recovered across 3 elections** in the fixture corpora |
| campaign tab paths resolved against the CWD | `index.json` records each campaign tab file at its fetch-time repo-root-relative path, and the parse stage resolved it against the current directory instead of the `--samples-root` that located the index. Run from anywhere but the repo root, every campaign tab file counted as absent and was silently skipped: tabs, auditor, donations, contracts and financing reports all parsed as empty, with **zero anomalies emitted**. Re-parsing the fixture corpora from a directory without a samples tree restored campaign data for **92 of 156 candidates across 15 of 17 elections** — 396 tab sections and 72 auditors that the broken run had dropped. Recorded paths are now re-anchored onto the samples root in use (repo-root runs are byte-identical before and after), and a listed tab file that is missing or unreadable emits a `CampaignTabSampleMissing` anomaly instead of vanishing |
| conviction-detail table dropped by the 2019-era row loop | VRK nests the Q9.1 detail table — date, country, court and offence per conviction — inside an anketa row of its own. The 2019-era per-row extraction read only `<b>` text from the cell, found none (the detail cells carry plain or `<strong>` text), and the empty-row skip dropped the row, so the details reached neither `rawData` nor `normalized` anywhere in the ep_2019 parser family. A cell that hosts a nested table now parses as a records row — the same shape the standalone records path emits — and `2019-kovo-3-savivaldybiu-tarybu` folds it into `teistumo-detales.irasai` with meru_2021's keys, since both elections ask the same questions under the same statute. prezidento_2019's verbatim copy of the loop got the same capture. Measured: exactly the **six 2019 EP declarers** regain their conviction details, Gintas Orda's 1988 LTSR record lands in normalized, and the 2017 mayoral, Marijampolė and 2019 presidential corpora are byte-identical (no declarers) |
| a recurring profile-card label overwrote its first value | `_normalize_profile_data` keyed `profilis.kita` by label slug, so the second `Iškėlė` on a card replaced the first. Measured over all 40,469 records when the 2012 Seimo cards (one `Apygarda`/`Iškėlė` pair per candidacy) made it routine: exactly one existing record was affected — Marija Puč, 2015 Trakai, whose `iskele` named the parenthetical member party instead of the coalition that nominated her. Later occurrences now land under `-2`, `-3` suffixes; the one record was re-parsed |
| the GPM305 income form unknown to the 2015-era parser | the era's income aliases named the GPM308 return only. The 2009 presidential pages extract the earlier GPM305 form — and so, it turned out, does the entire 2015 municipal family: every March 2015 council/mayoral candidate, both June repeat elections and the November Telšiai race. Their `gautos-pajamos` and `sumoketas-pajamu-mokestis` had been null since the family was built, while the five asset lines above them parsed fine. Adding the alias for 2009 and re-parsing the family offline recovered income and tax for **15,837 records** (15,138 March municipal, 366 Šilutė, 326 Širvintos–Trakai, 7 Telšiai). Of the 13 then still null, ten turned out to be the prose zero-income sentence of the next row; the three that publish no declaration at all are one March municipal record, one Širvintos–Trakai candidacy whose anketa VRK never published, and one 2014 EP candidate |
| the 2012-era conviction explanation never normalized | the 2012 Seimo and 2009 EP forms close the Q9 block with "Tuo atveju, jei bent į vieną 9 punkto klausimą atsakėte Taip … paaiškinimą įrašykite čia", and the era normalizer read the numbered questions only, so the explanation stayed in `rawData.anketa.rows`. Now `pareiskimai.teisiniai-argumentai` (2016's key for the same slot): **24 of 2012's 50 declared convictions** and 2 of 2009 EP's 3 carry text; null on every 2013 record, whose form no longer asks |
| a campaign whose root never fetched vanished silently at parse time | `_parse_campaign_sample` returned None for a campaign directory with no tabs and no `root.html` — the shape a `CampaignRootFetchFailed` leaves behind — and the parse stage moved on, so the record had no campaign section and `anomalies.jsonl` said nothing; the only trace was the candidate's `index.json`. Now a `CampaignRootMissing` warning. Measured over every retained `index.json` (2009–2015, 18,246 candidates): the two 2009 EP dead links are the only cases |
| the 2008–2015 degree/title line never normalized | the line after the education table — "Jei turite, nurodykite mokslo laipsnį <b>…</b>, vardą <b>…</b>", or "…mokslo vardą" alone for a title without a degree — was split into prompt rows by the era parser and then read by no mapping, so the whole 2008–2015 static family lacked `mokslo-laipsnis` and `pedagoginis-vardas` while every 2019+ era has them. Mapped in the era normalizer, the municipal family's and `ep_2014`'s, and re-parsed offline: **2,822 records gained a degree and/or a title** — 2,210 `mokslo-laipsnis` and 1,056 `pedagoginis-vardas` across ten elections (1,912 records in the March 2015 municipal general alone, 513 in 2012 Seimo, 270 in 2008 Seimo) |
| litas-only donation totals filed under `amountEur` | the 2012–2015 donation-summary parser read the totals block positionally as label / Eur / Lt / note — the March 2015 column order. On the litas-only pages of 2012, 2013 and both 2014 elections the one amount is Lt, so every total landed in `amountEur` and the trailing note ("Nuo 2012-01-01 draudžiamos", VRK's reminder that corporate donations were banned) was parsed as a failed amount and lost. The sums are now keyed by the table's own amount headings — `amountLt` on litas-only pages, both on the March 2015 pages, `amountEur` on the later 2015 ones. Re-parsing re-keyed **19,966 summary rows in 1,576 records** (1,343 of 1,927 in 2012, 11 in 2013, all 7 presidential, all 215 EP) and restored the note to 1,576 of them; the per-donation rows had always been right |

| a zero income stated in one sentence read as no declaration | thirty 2011 and March 2015 municipal pages put the GPM305 extract on the form's own line as prose — "GPM305 formos deklaracijos: Gauta 0 Lt, išskaičiuota pajamų mokesčio 0 Lt" — instead of the two labelled rows the aliases match, so `gautos-pajamos` and `sumoketas-pajamu-mokestis` were null while the page said zero. Every one of the thirty declares zero. The sentence now parses into both keys: **20 records in 2011 and 10 in March 2015** gained a 0/0, re-parsed in place from the retained HTML with nothing else changed |
| the municipal conviction explanation never normalized | the same slot on the municipal form — an unnumbered row after Q9, "Jeigu į 9 p. klausimą atsakėte „Taip“ ir norite papildomai apie tai paaiškinti, tai įrašykite čia" — was read by the municipal mapping (`telsiu_mero_2015`, shared by the whole 2015 municipal family) no better than the Seimo one had been: the yes/no was kept, the explanation stayed in `rawData.anketa.rows`. Found on the 2011 municipal pages, which use the same form, and chased across the family: re-parsing it offline from the retained HTML gave **142 records their `pareiskimai.teisiniai-argumentai` text** (137 of the March 2015 general's 266 declared convictions, 4 of Šilutė's 12, 1 of Širvintos–Trakai's 2; Telšiai declares none), with every other field of all 15,849 records byte-identical |
| the 2007–2008 interest declaration read as key/value pairs | the roman-numbered interest form of the 2007 and 2008 pages publishes each section as a record table — "Tipas \| Vienetų skaičius \| Vietovės pavadinimas \| Įsigijimo būdas" under II. Turtas — whose column-name row is bold `<td>` cells rather than `<th>`, so the era's interest parser saw no header and read every row as a label/value pair: a section collapsed to one entry per distinct first column with the last row winning, plus a spurious `tipas: "Vienetų skaičius"` from the header itself. Two flats became one, two employers the last. Found on the first 2007 municipal page; the header is now recognised by the emphasis (no key/value row of the family is bold whole — measured over 1,627 pages of 2007, 2008, 2011 and 2015) and the sections normalize as record lists in the 2016-era shape. Re-parsed offline: **1,593 records (1,584 of 2008 Seimo, 9 of 2007 Dzūkija), 5,357 sections, 13,198 rows** recovered; every other election byte-identical |

Every fix was verified by re-parsing all elections and confirming the diff was
confined to the intended records.

Those figures were measured over the **fixture corpora only**. The 2023
municipal full run is the first real test of them, and it shows how badly a
fixture sample can understate a fix: across its 13,796 records the private-
interest fix recovered free text for **734 candidates** (the fixtures had
suggested 2), and the empty-donations fix kept **344 sections** that would
otherwise have vanished (the fixtures had suggested 6). The campaign-decisions
fix went the other way — only 1 record in this election carries a decision,
because just 433 of its candidates have a campaign at all; that fix matters
more to the Seimas and EP elections, where most candidates do.

Every election has now been re-run or re-parsed since these fixes landed: the
small elections were re-parsed offline from their retained HTML on 2026-08-18,
and the five large non-municipal corpora were re-scraped the same day (run
record above). The inventory reflects the post-fix parse throughout, and the
free-text figures above are confirmed at full scale — 339 of the predicted 340
records gained text, the one exception holding only a `-` placeholder.

All three were found the same way: by reading every field of every fixture
candidate in a new module and treating each null or empty value as a question
rather than a result. All three sat in shared code with no test coverage, and
each now has one.

## Known gaps

- The corpus covers the elections implemented so far. VRK publishes further
  by-elections and older elections that have no module yet.
- ~~The 2012–2015 pages publish no elected markers anywhere~~ — closed
  2026-08-21 by the results join: `kandidatavimas.isrinktas` is now a real
  true/false on every record of the ten elections of that family (twelve
  since the two 2009 elections joined on 2026-08-22), derived
  from VRK's results trees and reconciled against VRK's own counts (139
  Seimas members in 2012, 3 in 2013, 11 MEPs, the president, both 2015
  by-election winners, 57 mayors and 1,464 council seats in March 2015 — 48
  of them annulled and flagged — and the four repeat/new mayors with 48
  council seats). `profilis.pastaba` stays null for the family: the pages
  themselves still say nothing. The one derivation that is not VRK's own
  sentence is Žirmūnai 2015, whose round-two page states no verdict; the
  winner is the runoff plurality, recorded as such in the results file.
- One 2015 candidacy has no questionnaire at all: VRK published Marija Puč's
  Trakai council page as `Rengiama`. Its record keeps the profile card and
  carries the corpus's only `AnketaNotPublished` warning. The same person's
  mayoral candidacy, under a second VRK candidate id, is complete.
- Three 2011 municipal candidates have **no page at all**: the list pages
  link them and the results rankings carry their preference votes, but every
  tab of `Kandidatas<ID>/` is a 404 on vrk.lt — Viktorija
  Zubovaitė-Steponavičienė (29964, Mažeikiai, Naujoji sąjunga position 3, 131
  votes), Gerda Ivaškevičiūtė (61654, Vilnius, Jaunoji Lietuva position 31,
  92 votes) and Aleksandras Bukinas (53039, Vilnius, LLRA–Rusų aljansas
  coalition position 34, 239 votes). None was elected. They are in the
  sitemap (16,403 entries) and in `.run-state/…/failed_ids.txt`, and have no
  record (16,400); a record cannot be written without a candidate page.
- Likewise two 2000 municipal candidates: the March 2000 list pages carry
  their rows and the preference pages their votes, but `kandvl.htm-84814.htm`
  (Gintaras Binkauskas, Vilnius, Lietuvių nacionalinės partijos ir "Jaunosios
  Lietuvos" sąjungos list position 2, 1,198 preference votes) and
  `kandvl.htm-86936.htm` (Vilma Kalendauskaitė, Alytaus rajonas, TS list
  position 10, 42 votes) are 404s in VRK's archive. Neither was elected.
  They are in the sitemap (9,881 entries) and `.run-state/…/failed_ids.txt`,
  and have no record (9,879).
- Likewise one 2002 municipal candidate: the Kauno miesto constituency page
  links Zita Vincentina Liubarskienė (asm_kod 158225, list 8 position 4) and
  the preference page carries her 1,019 votes and rank 4, but both her
  anketa and declaration pages are 404s on vrk.lt. She was not elected. She
  is in the sitemap (10,139 entries) and `.run-state/…/failed_ids.txt`, and
  has no record (10,138). Four parse warnings in the same election are
  source blanks, verified in the retained HTML: three declaration pages VRK
  published with an empty table cell and one anketa whose birth-date bold is
  empty; one of the 27 conviction disclosures carries an empty explanation
  blockquote the same way.
- The March 2000 municipal election's per-candidate results exist for 55
  of the 60 municipalities: Jurbarko, Kelmės, Radviliškio, Raseinių and
  Vilkaviškio rajono were captured only to the list level (votes and
  mandates per list; the members and preference pages link the live CGI
  and were never archived), so those 806 records carry `isrinktas: null`
  with `kandidatavimas.rezultataiNeskelbiami` — 129 of the election's
  1,562 seats are known by list, not by member.
- Likewise three 2007 municipal candidates: the list pages link them but
  every tab of `Kandidatas<ID>/` is a 404 on vrk.lt — Antanas Katinas
  (1835, Skuodas, LVLS position 14), Genrika Rynkun (6582, Švenčionys,
  Lietuvos lenkų liaudies partija position 3) and Juzefa Bagdonienė (1336,
  Varėna, LRLS position 15). None was elected. In the sitemap (13,422) and
  `failed_ids.txt`, no record (13,419).
- ~~Three 2015 elections have not had their full scrapes yet~~ — completed
  2026-08-21 with `KEEP_SAMPLES=1`: 327 (Širvintos–Trakai), 366 (Šilutė)
  and 15,149 (the March municipal general, the corpus's third-largest
  election) candidates, zero fetch failures, raw HTML retained under
  `samples-full/`.
- ~~The Q9.1 capture landed after the 2019 municipal full run~~ — resolved by
  the 2026-08-19 municipal re-scrape (below): every record in every election
  now reflects the post-fix parse in full, and `teistumo-detales` is present
  on all 13,666 2019 municipal records (244 non-empty, 303 convictions).
- ~~The repeat Visaginas mayoral vote of 2023 has no module~~ — implemented as
  `2023-geguzes-7-visagino-mero` (2026-08-19): both runoff candidates scraped,
  zero anomalies. It is a separate two-record election, still not part of the
  13,796; its candidates' campaign finance is published with the March
  election, so it carries no campaign data of its own.
- `2024-ep` and `2024-prezidento` candidate pages carry no campaign tab, so
  those elections have no donation data at all — campaigns were run by the party
  lists and are published outside the candidate pages.
- Donation *records* were historically dropped by the shared parser; the totals
  in older analyses of this repo predate that fix and should be recomputed.
- The 1996-1998 archive listings print names **surname-first** ("Kubilius
  Andrius") while the candidate pages, and every modern era, print them
  given-name-first. `candidateName` therefore takes the candidate page's
  heading, not the listing row, so the same person's name is comparable
  across eras. `candidateId` still derives from the listing slug
  (`kubilius-andrius`), so ids and record filenames follow the listing order
  while the display name follows the corpus convention — do not assume the id
  and the name are in the same word order for these five elections.
- The 1996-1998 Seimas archive pages (`1996-spalio-20-seimo`,
  `1997-kovo-23-seimo-pakartotiniai`, `1997-gruodzio-21-seimo-pakartotiniai`)
  publish no elected markers, no private-interest declarations, and — unlike
  every other era, including 2015 — **no birth-date field**. (The linked
  `kpdl.htm` income declaration *is* parsed, into the corpus's usual
  `turto-ir-pajamu-deklaracijos` key; see `docs/OUTPUT_SCHEMA.md` for how the
  1990s form's summed sections map onto it.) A birth date is instead recovered from the biography's opening
  sentence and marked
  `anketa.gimimo-data-saltinis: "biografijos-tekstas"`; see
  `docs/OUTPUT_SCHEMA.md` for coverage (692 of 906) and the measured 89%
  agreement with independently published dates. The remaining 214 records of
  this family — 157 whose biography gives only a year, 57 with no usable
  biography — still group by name alone in
  `scripts/build_person_index.py`'s cross-election identity index, so a
  same-named person among them cannot be told apart from a namesake. Corpus
  records without a birth date: **217** (down from 908 before the biography
  pass). The 1997 municipal archive
  (`1997-kovo-23-savivaldybiu-tarybu`,
  `1997-birzelio-29-svenciniu-tarybos-pakartotiniai`) does publish birth date
  and resolves the same identity risk 2015 and later eras do; see
  `docs/OUTPUT_SCHEMA.md`'s appendices for both families.
- Both `1996-spalio-20-seimo` and `1997-kovo-23-savivaldybiu-tarybu` have
  completed their full scrapes: 879/879 candidates across 71 constituencies
  (one `ResidenceMissing` warning — `andrikiene-laima-liucija`, a genuinely
  blank field on the source page — zero duplicate-candidate-id collisions),
  and 6,276/6,276 candidates across 449 party lists in all 56 municipalities
  (eight `ResidenceMissing` warnings, 46 duplicate-candidate-id collisions —
  all confirmed genuine name collisions between different VRK candidate ids,
  not parser artifacts, see `docs/CLI_REFERENCE.md`), respectively. Zero fetch
  errors on either run. `1997-kovo-23-savivaldybiu-tarybu`'s fetched HTML was
  kept (`KEEP_SAMPLES=1`, `samples-full/1997-kovo-23-savivaldybiu-tarybu/`,
  ~49 MB) so a later parser fix is an offline re-parse rather than a second
  full crawl of vrk.lt.
