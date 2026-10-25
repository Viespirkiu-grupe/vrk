# Fixture samples

HTML fixtures under `samples/html/<election_id>/` are versioned and
test-protected. They let parser work and regression tests run without the
network.

## What git carries

**A fixture unit is tracked when it is at most 1 MiB.**

- A *unit* is a candidate directory with all its files, a listing
  subdirectory (`lists/`, `districts/`, `municipalities/`, …), one election's
  `samples/results/<election-id>/` tree, a single top-level listing file, or
  one file of `sitemaps/`.
- Only files a parser opens count: `.html`, `.htm`, `.json`, `.doc`, and a
  candidate's retained portrait (`portrait.json` and the `portrait.<ext>` it
  names). The 2002 presidential declaration scans stay local.
- Every election keeps at least one tracked candidate to parse;
  `tests/test_tracked_fixtures.py` asserts that and that git agrees with the
  rule.
- A clone lacks the 2018–2019 candidates whose pages embed base64 portraits,
  some listing and `results/` trees, and the municipal generals' sitemaps.

```bash
python scripts/tracked_fixtures.py            # what the rule selects
python scripts/tracked_fixtures.py --check    # does git agree?
python scripts/tracked_fixtures.py --sync     # make git agree
```

`--sync` force-adds past the `samples/` and `sitemaps/` ignore rules, so new
fixtures need it; `git add` alone will not see them. In a worktree that reaches
these trees through symlinks, `--sync` replaces a selected symlink with a copy
first.

## Skips

A test that needs something outside the subset (`data/`, the large sitemaps,
`samples-full/`) skips and names the command that would produce it.
`tests/local_data.py` holds the machinery and the root `conftest.py` applies
it.

- The skip is **per unit**: a `FileNotFoundError` becomes a skip only when the
  unit the path belongs to is absent. A path missing inside a present unit is
  a parser bug and fails.
- Whole-corpus tests call `local_data.require_corpus()`; `complete=True` also
  requires every registered election.
- The suite never reaches the network: the conftest refuses `requests` for any
  host but loopback. `VRK_TESTS_ALLOW_NETWORK=1` lifts it for a deliberate
  live run.
- Under `CI` the conftest refuses to start without node, which the dashboard
  JavaScript tests need.

To keep the skipped set small:

- **Load fixtures lazily, one per attribute.** Declare each with
  `local_data.Fixture` as a class attribute parsed on first read, so only the
  tests reading an untracked one skip. Loop over a partly tracked set with one
  `subTest` per candidate.
- **Pin shapes on a tracked fixture.** Key and section order hold for every
  candidate of an election, so assert them on one in the election's
  `TRACKED_CANDIDATE_DIRS` and keep untracked ones for the values only they
  publish.

## Record hashes

`tests/fixture-record-hashes.tsv` holds one sha256 per tracked candidate over
the record the parsers produce, with `provenance` dropped. It is the CI
stand-in for `reparse_diff.py`, `field_coverage.py` and `anomalies-report`,
which all need `data/`. It says nothing about whether a value is right, only
that the parsers still produce the same bytes.

```bash
python scripts/fixture_record_hashes.py            # check
python scripts/fixture_record_hashes.py --update   # after a deliberate parser change, same commit
```

## Allowlists

Each election's allowlist test fixes its exact candidate directories and
support files; its comments say what each fixture covers.

| election | allowlist test | candidates |
| --- | --- | --- |
| `1996-spalio-20-seimo` | `test_seimo_1996_sample_allowlist.py` | 5 |
| `1997-kovo-23-savivaldybiu-tarybu` | `test_savivaldybiu_1997_sample_allowlist.py` | 7 |
| `1997-kovo-23-seimo-pakartotiniai` | `test_seimo_pakartotiniai_1997_kovo_sample_allowlist.py` | 23 |
| `1997-birzelio-29-svenciniu-tarybos-pakartotiniai` | `test_svencioniu_tarybos_1997_sample_allowlist.py` | 110 |
| `1997-gruodzio-21-seimo-pakartotiniai` | `test_seimo_aukstaitijos_1997_gruodzio_sample_allowlist.py` | 4 |
| `1998-kovo-22-seimo-pakartotiniai` | `test_seimo_pakartotiniai_1998_kovo_sample_allowlist.py` | 11 |
| `1998-lapkricio-15-seimo-pakartotiniai` | `test_seimo_nevezio_1998_lapkricio_sample_allowlist.py` | 11 |
| `1999-kovo-21-seimo-pakartotiniai` | `test_seimo_pakartotiniai_1999_kovo_sample_allowlist.py` | 22 |
| `2000-kovo-19-savivaldybiu-tarybu` | `test_savivaldybiu_2000_sample_allowlist.py` | 10 |
| `2000-seimo` | `test_seimo_2000_sample_allowlist.py` | 18 |
| `2002-prezidento` | `test_prezidento_2002_sample_allowlist.py` | 17 |
| `2002-gruodzio-22-savivaldybiu-tarybu` | `test_savivaldybiu_2002_sample_allowlist.py` | 10 |
| `2003-birzelio-15-seimo-nauji` | `test_seimo_nauji_2003_sample_allowlist.py` | 27 |
| `2004-ep` | `test_ep_2004_sample_allowlist.py` | 13 |
| `2004-prezidento` | `test_prezidento_2004_sample_allowlist.py` | 5 |
| `2004-seimo` | `test_seimo_2004_sample_allowlist.py` | 14 |
| `2005-lapkricio-20-seimo-kedainiai` | `test_seimo_kedainiu_2005_sample_allowlist.py` | 5 |
| `2007-vasario-25-savivaldybiu` | `test_savivaldybiu_2007_sample_allowlist.py` | 11 |
| `2007-spalio-7-seimo-dzukija` | `test_seimo_dzukijos_2007_sample_allowlist.py` | 10 |
| `2008-seimo` | `test_seimo_2008_sample_allowlist.py` | 10 |
| `2009-prezidento` | `test_prezidento_2009_sample_allowlist.py` | 7 |
| `2009-ep` | `test_ep_2009_sample_allowlist.py` | 15 |
| `2009-lapkricio-15-seimo-silale-silute-vilnius-salcininkai` | `test_seimo_silales_silutes_vilniaus_salcininku_2009_sample_allowlist.py` | 17 |
| `2011-vasario-13-seimo-marijampole` | `test_seimo_marijampoles_2011_sample_allowlist.py` | 9 |
| `2011-vasario-27-savivaldybiu` | `test_savivaldybiu_2011_sample_allowlist.py` | 10 |
| `2012-seimo` | `test_seimo_2012_sample_allowlist.py` | 9 |
| `2013-kovo-3-seimo-birzai-zarasai-ukmerge` | `test_seimo_birzu_zarasu_ukmerges_2013_sample_allowlist.py` | 37 |
| `2014-prezidento` | `test_prezidento_2014_sample_allowlist.py` | 7 |
| `2014-ep` | `test_ep_2014_sample_allowlist.py` | 10 |
| `2015-kovo-1-savivaldybiu` | `test_savivaldybiu_2015_sample_allowlist.py` | 9 |
| `2015-kovo-1-seimo-zirmunai` | `test_seimo_zirmunu_2015_sample_allowlist.py` | 12 |
| `2015-birzelio-7-seimo-varena-eisiskes` | `test_seimo_varenos_eisiskiu_2015_sample_allowlist.py` | 8 |
| `2015-birzelio-7-pakartotiniai-sirvintos-trakai` | `test_pakartotiniai_sirvintu_traku_2015_sample_allowlist.py` | 10 |
| `2015-birzelio-21-pakartotiniai-silutes` | `test_pakartotiniai_silutes_2015_sample_allowlist.py` | 10 |
| `2015-lapkricio-8-telsiu-mero` | `test_telsiu_mero_2015_sample_allowlist.py` | 7 |
| `2016-seimo` | `test_seimo_2016_sample_allowlist.py` | 5 |
| `2017-balandzio-23-meru` | `test_meru_2017_sample_allowlist.py` | 11 |
| `2017-balandzio-23-seimo-anyksciai-panevezys` | `test_seimo_anyksciu_panevezio_2017_sample_allowlist.py` | 11 |
| `2017-rugsejo-10-marijampoles-mero` | `test_marijampoles_mero_2017_sample_allowlist.py` | 8 |
| `2018-rugsejo-16-seimo-zanavykai` | `test_seimo_zanavyku_2018_sample_allowlist.py` | 6 |
| `2019-kovo-3-savivaldybiu-tarybu` | `test_savivaldybiu_2019_sample_allowlist.py` | 10 |
| `2019-prezidento` | `test_prezidento_2019_sample_allowlist.py` | 9 |
| `2019-ep` | `test_ep_2019_sample_allowlist.py` | 6 |
| `2019-rugsejo-8-seimo` | `test_seimo_2019_sample_allowlist.py` | 27 |
| `2020-seimo` | `test_seimo_2020_sample_allowlist.py` | 6 |
| `2021-balandzio-11-radviliskio-mero` | `test_radviliskio_mero_2021_sample_allowlist.py` | 7 |
| `2021-spalio-10-meru` | `test_meru_2021_sample_allowlist.py` | 14 |
| `2023-kovo-5-savivaldybiu-tarybu-ir-meru` | `test_savivaldybiu_2023_sample_allowlist.py` | 9 |
| `2023-geguzes-7-visagino-mero` | `test_visagino_mero_2023_sample_allowlist.py` | 2 |
| `2023-rugsejo-3-seimo-raseiniai-kedainiai` | `test_seimo_raseiniu_kedainiu_2023_sample_allowlist.py` | 8 |
| `2023-spalio-8-kupiskio-mero` | `test_kupiskio_mero_2023_sample_allowlist.py` | 5 |
| `2024-prezidento` | `test_prezidento_2024_sample_allowlist.py` | 8 |
| `2024-ep` | `test_ep_2024_sample_allowlist.py` | 6 |
| `2024-seimo` | `test_seimo_2024_sample_allowlist.py` | 5 |
| `2025-kovo-16-meru` | `test_meru_2025_sample_allowlist.py` | 14 |

## Adding fixtures

Sample-fetch commands (`fetch-first-candidate-samples`,
`fetch-candidate-samples`) refuse to create a new candidate directory unless
given `--allow-new-samples`.

1. Capture the fixture with `--allow-new-samples`.
2. Check the parser output and anomalies.
3. Update the election's allowlist test.
4. Keep the set small and representative.
5. Run `python scripts/tracked_fixtures.py --sync` so it reaches git and CI.

A fixture over 1 MiB stays untracked: leave it out of the allowlist test's
`TRACKED_CANDIDATE_DIRS` (see `tests/test_ep_2019_sample_allowlist.py`) and
declare it with `local_data.Fixture` (see
`tests/test_prezidento_2019_anketa_parser.py`). Prefer a smaller candidate with
the same shape.

## Checks

```bash
pytest                                        # the whole suite
pytest tests/test_tracked_fixtures.py         # git and the 1 MiB rule agree
python scripts/fixture_record_hashes.py       # the fixtures still parse to the recorded records
```

`.github/workflows/tests.yml` runs the suite on every push and pull request.
