# Deploying vrk.viespirkiai.org

Production runs `scripts/serve_dashboard.py` over a checkout of this
repository, behind Cloudflare. The same server you run locally serves the
public site. It serves the Astro build at `/`, the index beside it,
`data/`, `portraits/` and `docs/concept-map.json`, and nothing else
([DASHBOARD.md](DASHBOARD.md#url-layout) has the URL layout).

## What the server needs

- A checkout of this repository, and Python 3.11+ with
  `pip install -r requirements.txt` to build the index.
- Node.js 22.12+ to build the frontend (`frontend/dist/` is gitignored, so a
  pull alone never updates it; that was #183).
- **`data/`**, the records, from the latest public
  [release](https://github.com/Viespirkiu-grupe/vrk/releases). The server
  needs no full-size photos:

  ```bash
  gh release download corpus-YYYY-MM-DD --pattern 'vrk-corpus.sqlite.gz' --pattern 'vrk-web-portraits.tar'
  gunzip vrk-corpus.sqlite.gz
  python scripts/unpack_corpus.py vrk-corpus.sqlite --no-photos   # writes ./data
  tar -xf vrk-web-portraits.tar                                    # writes ./portraits/*.webp
  ```

  Or copy `data/` and `portraits/` from a machine that scraped and built them
  (`scripts/build_web_portraits.py`). A public release has the third-party
  contacts already removed ([PERSONAL_DATA.md](PERSONAL_DATA.md)). A scraping
  disk still has them.
- **The index**, `dashboard/people-{list,details,version}.json`, built on the server from `data/`
  with `python scripts/build_person_index.py` (about 35 s). It also stamps
  which people have a portrait in `portraits/`.

> **Docker: TODO from operator.** Production probably runs in a container
> set up by the operator. Add the image, the mounts for `data/`,
> `portraits/` and `dashboard/`, the restart command, and how requests reach
> the server here. The stock script binds `127.0.0.1` and refuses a
> non-loopback `Host` header (issue #160), so something in that setup
> already accounts for this.

## Updating

```bash
git pull --ff-only
(cd frontend && npm ci && npm run build)        # every pull that touched frontend/
python scripts/build_person_index.py            # after new data/ or portraits/
# restart serve_dashboard.py (see the Docker TODO above)
python3 scripts/smoke_check.py https://vrk.viespirkiai.org
```

A new corpus means unpacking the new release into `data/` and `portraits/`
first, as above.

## Cloudflare

Nothing in the repository changes the zone. The operator sets one cache rule
in the dashboard (Caching → Cache Rules):

- *When:* hostname is `vrk.viespirkiai.org` and the URI path starts with
  `/_astro/` or `/portraits/`.
- *Then:* Eligible for cache. Edge TTL: "Use cache-control header if
  present". Browser TTL: "Respect origin". Keep the default cache key,
  because the query string carries a portrait's `?v=` version.

And a second rule, the same but for the person index (issue #186):

- *When:* hostname is `vrk.viespirkiai.org` and the URI path equals
  `/people-list.json` or `/people-details.json`.
- *Then:* the same three settings, and the default cache key: `?v=` is the
  file's content hash. The origin answers `immutable` only when `v` is the
  hash of the file it holds, and `no-cache` otherwise, so the edge never
  keeps a mid-deploy answer. [DASHBOARD.md](DASHBOARD.md#caching) has the
  details and a curl check.

The origin marks only those URLs `immutable`. Everything else is
`no-cache`, and Cloudflare passes revalidations through, so they come back
as 304s. Do not add a "Cache Everything" rule for `/` or `/data/`, because
the edge would then serve a stale index after an update. Leave Auto Minify
and Rocket Loader off, since they would rewrite the hashed bundles. A rule
left over for `/dashboard/_astro/*` from before #184 is stale.

## Checking

```bash
python3 scripts/smoke_check.py https://vrk.viespirkiai.org
python3 scripts/smoke_check.py http://127.0.0.1:8791          # a local serve_dashboard.py
```

It exits non-zero if any check fails, and prints one line per check:

- `/` and the `/_astro/` files it links (immutable).
- The index (compressed, `no-cache`).
- One record, and that person's portrait and page.
- `/suvestine`.
- The repository paths that must 404.

`--record /data/…json` picks the record to probe.

## Access

The repository and its releases belong to the Viespirkiu-grupe
organisation. The server and the Cloudflare zone are held by the maintainer
([@debesyla](https://github.com/debesyla)). Ask there for access.
